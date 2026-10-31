"""Client sheet: one presentable 11x17 landscape page for a whole kitchen.

For the sales conversation, not the shop: front elevation (uppers over bases,
doors, drawers and the filler), plan, end view, and a shaded 3D view drawn from
the model3d boxes. Overall dimensions, a cabinet schedule and a title block.
No cut-list or manufacturing detail. Omacad is not involved.

    python3 -m cabgen.cli client jobs/sample-kitchen.csv --out out/client-sheet
"""

from __future__ import annotations

import re

import datetime as _dt
import math
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .kitchen import (
    apply_discovered_rules, end_facts, load_kitchen, place_kitchen, scene_of,
)
from .nest_project import cabinet_codes
from .params import STYLE_PRESETS, door_rule_warnings, enforce_upper_door_limit
from .svg import Svg, hatch
from .units import fmt_in

PAGE_W, PAGE_H = 17.0, 11.0          # tabloid, landscape
M = 0.4
INK = "#1f2933"
SOFT = "#6b7785"
DIM = "#3d4b5c"
FRONT = "#d7e0ea"                    # doors and drawer fronts
CASE = "#f5f3ee"                     # case (melamine)
FILL = "#e6dccb"                     # filler
PULL = "#3b3f44"
WALL = "#9aa3ad"
EDGE_T = 1.5
LAMTOP = "#d8cfbf"                   # laminate countertop
SOLID = "#ebe8e2"                    # solid surface countertop

SCALES = [  # (paper inches per real inch, words)
    (1 / 8, '1-1/2" = 1\'-0"'),
    (1 / 12, '1" = 1\'-0"'), (1 / 16, '3/4" = 1\'-0"'), (1 / 24, '1/2" = 1\'-0"'),
    (1 / 32, '3/8" = 1\'-0"'), (1 / 48, '1/4" = 1\'-0"'), (1 / 64, '3/16" = 1\'-0"'),
    (1 / 96, '1/8" = 1\'-0"'),
]


def ft_in(x: float) -> str:
    """75 -> 75" (6'-3")."""
    feet = int((x + 1e-6) // 12)
    rest = x - feet * 12
    tail = fmt_in(rest) if rest > 1e-6 else '0"'
    return f'{fmt_in(x)} ({feet}\'-{tail})' if feet else fmt_in(x)


def _scale(w: float, h: float, box_w: float, box_h: float) -> tuple[float, str]:
    """Largest scale that fits. Named when it is a standard one, else approximate."""
    s = min(box_w / w, box_h / h)
    for std, words in SCALES:
        if std <= s and std >= s * 0.92:
            return std, words
    return s, f"approx. 1:{round(1 / s)}"


# --------------------------------------------------------------------------- data
@dataclass
class Job:
    name: str
    cabs: list
    settings: dict
    boxes: list
    codes: dict
    filler: tuple[float, float] | None   # (x0, x1) of the base filler
    counter: object = None               # cabgen.counter.Counter or None
    finish_warnings: list = field(default_factory=list)

    @property
    def bases(self):
        return [c for c in self.cabs if c.run == "base"]

    @property
    def uppers(self):
        return [c for c in self.cabs if c.run == "upper"]

    def run_span(self, run: str) -> tuple[float, float] | None:
        cabs = self.bases if run == "base" else self.uppers
        if not cabs:
            return None
        x0 = min(c.x for c in cabs)
        x1 = max(c.x + c.params.width for c in cabs)
        if run == "base" and self.filler:
            x0, x1 = min(x0, self.filler[0]), max(x1, self.filler[1])
        return x0, x1

    @property
    def wall_y(self) -> float:
        return max((c.y + c.params.depth for c in self.cabs), default=24.0)


def load_job(sheet: Path, name: str | None = None) -> Job:
    settings, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, settings, sheet.name)
    apply_discovered_rules(cabs, settings)
    return job_from(cabs, settings, name or sheet.stem.replace("-", " ").replace("_", " ").title())


_PIECE_NO = re.compile(r"(?<=[A-Z])\d+[AB]?(?= )|\s\d+(?: (?:left|right) half)?$")


def join_counter_pieces(boxes: list) -> list:
    """Client views (this sheet's renderings and the AR model) show the countertop as the
    finished surface. A top longer than one sheet is cut in pieces (CT1-TOP1, CT1-TOP2, ...)
    that butt at a seam on a cabinet joint. Laminate covers that seam, so the pieces that
    touch end to end, with the same section, are drawn as one box here. The cut list,
    the nesting, the countertop page and Omacad keep the real pieces."""
    from .model3d import Box
    out, groups = [], {}
    for b in boxes:
        if not b.name.startswith("CT"):
            out.append(b)
            continue
        key = (_PIECE_NO.sub("", b.name), b.material,
               round(b.pos[1], 4), round(b.size[1], 4), round(b.pos[2], 4), round(b.size[2], 4),
               getattr(b, "color", ""))
        groups.setdefault(key, []).append(b)
        out.append(key)
    merged: dict = {}
    for key, items in groups.items():
        items = sorted(items, key=lambda b: b.pos[0])
        runs = [[items[0]]]
        for b in items[1:]:
            last = runs[-1][-1]
            if abs(b.pos[0] - (last.pos[0] + last.size[0])) < 1e-6:
                runs[-1].append(b)
            else:
                runs.append([b])
        boxes_out = []
        for run in runs:
            if len(run) == 1:
                boxes_out.append(run[0])
                continue
            x0 = run[0].pos[0]
            x1 = run[-1].pos[0] + run[-1].size[0]
            first = run[0]
            boxes_out.append(Box(key[0], (x0, first.pos[1], first.pos[2]),
                                 (round(x1 - x0, 4), first.size[1], first.size[2]),
                                 first.material, first.join, "", getattr(first, "color", "")))
        merged[key] = boxes_out
    final, seen = [], set()
    for item in out:
        if isinstance(item, tuple):
            if item not in seen:
                seen.add(item)
                final.extend(merged[item])
        else:
            final.append(item)
    return final


def job_from(cabs, settings: dict, name: str) -> Job:
    from .counter import build_counter
    boxes, _holes, _parts = scene_of(cabs, settings)
    counter = build_counter(cabs, settings)
    keep = [b for b in boxes if "Drawer box" not in b.name and "/ Shelf" not in b.name
            and "Spacer board" not in b.name]
    keep = join_counter_pieces(keep)
    from .model3d import expand_round
    keep = expand_round(keep)       # the microwave shelf's 2" R corners, as boxes
    filler = None
    bases = [c for c in cabs if c.run == "base"]
    if "base_walls" in settings and bases:
        facts = end_facts(settings)
        if facts["filler"]:
            if facts["filler_side"] == "left":
                x1 = min(c.x for c in bases)
                filler = (x1 - facts["filler"], x1)
            else:
                x0 = max(c.x + c.params.width for c in bases)
                filler = (x0, x0 + facts["filler"])
    return Job(name, cabs, settings, keep, cabinet_codes(cabs), filler, counter,
               list(settings.get("finish_warnings") or []))


def _color(box) -> str:
    chosen = str(getattr(box, "color", "") or "").strip()
    if len(chosen) == 7 and chosen.startswith("#"):
        return chosen
    mat = box.material
    if "pull" in mat or "hardware" in mat:
        return PULL
    if "solid surface" in mat:
        return SOLID
    if "plywood" in mat:
        return LAMTOP
    if "laminate" in mat:
        return FRONT
    return CASE


def _filler_box(job: Job):
    from .model3d import Box
    if not job.filler:
        return None
    depth = max(c.params.depth for c in job.bases)
    h = max(c.params.height for c in job.bases)
    return Box("filler", (job.filler[0], -0.75, 0.0), (job.filler[1] - job.filler[0], 0.75, h),
               "filler")


# --------------------------------------------------------------------------- helpers
def _shade(hex_color: str, k: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, min(255, int(c * k))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _hdim(svg: Svg, x1, x2, y, text, size=0.1, ext_to=None):
    """Horizontal dimension at paper y, with ticks and optional extension lines."""
    if ext_to is not None:
        for x in (x1, x2):
            svg.line(x, ext_to, x, y + (0.05 if y > ext_to else -0.05), stroke=SOFT, sw=0.004)
    svg.line(x1, y, x2, y, stroke=DIM, sw=0.006)
    for x in (x1, x2):
        svg.line(x - 0.025, y + 0.025, x + 0.025, y - 0.025, stroke=DIM, sw=0.012)
    svg.rect((x1 + x2) / 2 - len(text) * size * 0.29 - 0.03, y - size * 0.95,
             len(text) * size * 0.58 + 0.06, size * 0.85, fill="#ffffff", stroke="none", sw=0)
    svg.text((x1 + x2) / 2, y - 0.04, text, size=size, anchor="middle", fill=DIM)


def _vdim(svg: Svg, x, y1, y2, text, size=0.1, ext_to=None):
    if ext_to is not None:
        for y in (y1, y2):
            svg.line(ext_to, y, x + (0.05 if x > ext_to else -0.05), y, stroke=SOFT, sw=0.004)
    svg.line(x, y1, x, y2, stroke=DIM, sw=0.006)
    for y in (y1, y2):
        svg.line(x - 0.025, y + 0.025, x + 0.025, y - 0.025, stroke=DIM, sw=0.012)
    cy = (y1 + y2) / 2
    svg.rect(x - size * 0.95, cy - len(text) * size * 0.29 - 0.03, size * 0.85,
             len(text) * size * 0.58 + 0.06, fill="#ffffff", stroke="none", sw=0)
    svg.text(x - 0.04, cy, text, size=size, anchor="middle", fill=DIM, rotate=-90)


def _heading(svg: Svg, x, y, title, scale_words=""):
    svg.text(x, y, title, size=0.19, weight="bold", fill=INK)
    if scale_words:
        svg.text(x + len(title) * 0.19 * 0.7 + 0.2, y, f"scale {scale_words}", size=0.12, fill=SOFT)


def _wall_band(svg: Svg, x, y, w, h):
    svg.rect(x, y, w, h, fill="#ffffff", stroke="none", sw=0)
    hatch(svg, x, y, w, h, spacing=0.06, sw=0.005, stroke=WALL)


# --------------------------------------------------------------------------- views
def front_elevation(svg: Svg, job: Job, box) -> None:
    bx, by, bw, bh = box
    span_b, span_u = job.run_span("base"), job.run_span("upper")
    spans = [s for s in (span_b, span_u) if s]
    x0 = min(s[0] for s in spans)
    x1 = max(s[1] for s in spans)
    top = max(c.z + c.params.height for c in job.cabs)
    s, words = _scale(x1 - x0, top, bw - 2.6, bh - 2.2)
    _heading(svg, bx, by + 0.2, "FRONT ELEVATION", words)
    ox = bx + 0.6 + (bw - 2.6 - (x1 - x0) * s) / 2 - x0 * s
    floor = by + 1.25 + top * s
    X = lambda x: ox + x * s
    Z = lambda z: floor - z * s

    # walls at the ends that have one
    first = min(job.bases or job.cabs, key=lambda c: c.x)
    last = max(job.bases or job.cabs, key=lambda c: c.x)
    left_x = span_b[0] if span_b else x0
    right_x = span_b[1] if span_b else x1
    wall_h = top + 6
    if first.params.left_side == "wall":
        _wall_band(svg, X(left_x) - 0.18, Z(wall_h), 0.18, wall_h * s)
        svg.line(X(left_x), Z(0), X(left_x), Z(wall_h), stroke=INK, sw=0.01)
    if last.params.right_side == "wall" or (job.filler and job.settings.get("base_walls") == "both"):
        _wall_band(svg, X(right_x), Z(wall_h), 0.18, wall_h * s)
        svg.line(X(right_x), Z(0), X(right_x), Z(wall_h), stroke=INK, sw=0.01)
    svg.line(X(x0) - 0.5, floor, X(x1) + 0.5, floor, stroke=INK, sw=0.014)

    for b in sorted(job.boxes, key=lambda b: -(b.pos[1])):      # far first
        x, y, z = b.pos
        dx, dy, dz = b.size
        if "pull" in b.material:
            svg.rect(X(x), Z(z + dz), dx * s, dz * s, fill=PULL, stroke="none", sw=0)
            continue
        svg.rect(X(x), Z(z + dz), dx * s, dz * s, fill=_color(b), stroke=_edge(b, "#56606b"), sw=0.006)
    fb = _filler_box(job)
    if fb:
        fx, _, _ = fb.pos
        fw, _, fh = fb.size
        svg.rect(X(fx), Z(fh), fw * s, fh * s, fill=FILL, stroke="#56606b", sw=0.006)
        svg.text(X(fx + fw / 2), floor + 0.24, "F", size=0.15, anchor="middle",
                 weight="bold", fill=INK)
    _swing_marks(svg, job.boxes, X, Z)

    # tags
    for c in job.cabs:
        cx = X(c.x + c.params.width / 2)
        if c.run == "base":
            svg.text(cx, floor + 0.24, job.codes[c.name], size=0.15, anchor="middle",
                     weight="bold", fill=INK)
    # widths: bases below, uppers above, then overall
    if span_b:
        y = floor + 0.6
        for c in job.bases:
            _hdim(svg, X(c.x), X(c.x + c.params.width), y, fmt_in(c.params.width), size=0.12)
        if job.filler:
            _hdim(svg, X(job.filler[0]), X(job.filler[1]), y, "", size=0.07)
        _hdim(svg, X(span_b[0]), X(span_b[1]), y + 0.42, "bases " + ft_in(span_b[1] - span_b[0]),
              size=0.13)
    if span_u:
        utop = max(c.z + c.params.height for c in job.uppers)
        for c in job.uppers:
            svg.text(X(c.x + c.params.width / 2), Z(utop) - 0.14, job.codes[c.name], size=0.15,
                     anchor="middle", weight="bold", fill=INK)
            _hdim(svg, X(c.x), X(c.x + c.params.width), Z(utop) - 0.42, fmt_in(c.params.width),
                  size=0.12)
        _hdim(svg, X(span_u[0]), X(span_u[1]), Z(utop) - 0.82, "uppers " + ft_in(span_u[1] - span_u[0]),
              size=0.13)
    # heights on the right
    xr = X(x1) + 0.45
    if job.bases:
        bh_ = job.counter.top_z if job.counter else max(c.params.height for c in job.bases)
        _vdim(svg, xr, Z(0), Z(bh_), fmt_in(bh_), size=0.12)
        if job.counter:
            svg.text(xr + 0.12, Z(bh_) + 0.3, "top of", size=0.1, fill=SOFT)
            svg.text(xr + 0.12, Z(bh_) + 0.44, "counter", size=0.1, fill=SOFT)
    if job.uppers:
        ub = min(c.z for c in job.uppers)
        ut = max(c.z + c.params.height for c in job.uppers)
        if job.bases:
            _vdim(svg, xr, Z(bh_), Z(ub), fmt_in(ub - bh_), size=0.12)
        _vdim(svg, xr, Z(ub), Z(ut), fmt_in(ut - ub), size=0.12)
        _vdim(svg, xr + 0.4, Z(0), Z(ut), "overall " + ft_in(ut), size=0.13)
        svg.text(xr + 0.65, Z(ub) + 0.04, f"{fmt_in(ub)} floor to", size=0.1, fill=SOFT)
        svg.text(xr + 0.65, Z(ub) + 0.18, "bottom of uppers", size=0.1, fill=SOFT)
        svg.line(xr - 0.1, Z(ub), xr + 0.6, Z(ub), stroke=SOFT, sw=0.004, dash="0.03,0.03")


def plan_view(svg: Svg, job: Job, box) -> None:
    bx, by, bw, bh = box
    spans = [s for s in (job.run_span("base"), job.run_span("upper")) if s]
    x0 = min(s[0] for s in spans)
    x1 = max(s[1] for s in spans)
    wall = job.wall_y
    depth = wall + 0.75
    s, words = _scale(x1 - x0, depth, bw - 1.6, bh - 1.3)
    _heading(svg, bx, by + 0.2, "PLAN (TOP VIEW)", words)
    ox = bx + 0.7 + (bw - 1.6 - (x1 - x0) * s) / 2 - x0 * s
    oy = by + 0.75
    X = lambda x: ox + x * s
    Y = lambda y: oy + (wall - y) * s       # wall at the top
    _wall_band(svg, X(x0) - 0.15, Y(wall) - 0.15, (x1 - x0) * s + 0.3, 0.15)
    svg.line(X(x0) - 0.15, Y(wall), X(x1) + 0.15, Y(wall), stroke=INK, sw=0.012)
    for c in job.bases:
        p = c.params
        svg.rect(X(c.x), Y(c.y + p.depth), p.width * s, p.depth * s, fill=CASE, stroke=INK, sw=0.009)
        svg.rect(X(c.x + 0.25), Y(c.y), (p.width - 0.5) * s, 0.75 * s, fill=FRONT, stroke="#56606b",
                 sw=0.005)
        svg.text(X(c.x + p.width / 2), Y(c.y + p.depth * 0.28) + 0.05, job.codes[c.name], size=0.15,
                 anchor="middle", weight="bold", fill=INK)
    if job.filler:
        f0, f1 = job.filler
        dep = max(c.params.depth for c in job.bases)
        svg.rect(X(f0), Y(dep), (f1 - f0) * s, (dep + 0.75) * s, fill=FILL, stroke=INK, sw=0.007)
    ct = job.counter
    if ct:
        color = SOLID if ct.kind == "solid" else LAMTOP
        svg.rect(X(ct.x0), Y(ct.y_back), ct.length * s, ct.depth * s, fill=color, stroke=INK, sw=0.012)
        st = ct.splash_thk
        svg.rect(X(ct.x0), Y(ct.y_back), ct.length * s, st * s, fill=_shade(color, 0.85), stroke=INK, sw=0.006)
        for on, x in ((ct.splash_left, ct.x0), (ct.splash_right, ct.x1 - st)):
            if on:
                svg.rect(X(x), Y(ct.y_back), st * s, ct.depth * s, fill=_shade(color, 0.85), stroke=INK, sw=0.006)
        for c in job.bases:
            p = c.params
            svg.rect(X(c.x), Y(c.y + p.depth), p.width * s, p.depth * s, fill="none", stroke=SOFT,
                     sw=0.005, dash="0.02,0.03")
            svg.text(X(c.x + p.width / 2), Y(c.y + p.depth * 0.28) + 0.05, job.codes[c.name], size=0.15,
                     anchor="middle", weight="bold", fill=INK)
        svg.text(X(ct.x0 + ct.length / 2), Y(ct.y_back - ct.depth * 0.62), f"{ct.code} countertop",
                 size=0.11, anchor="middle", fill=DIM)
    for c in job.uppers:
        p = c.params
        svg.rect(X(c.x), Y(c.y + p.depth), p.width * s, p.depth * s, fill="none", stroke=SOFT,
                 sw=0.008, dash="0.06,0.04")
        svg.text(X(c.x + p.width / 2), Y(c.y + p.depth) + 0.2, job.codes[c.name], size=0.12,
                 anchor="middle", fill=SOFT)
    svg.text(bx + 0.7, by + 0.45, "Uppers shown dashed, hung on the same wall.", size=0.1, fill=SOFT)
    front = ct.y_front if ct else -0.75
    yb = Y(front) + 0.3
    span_b = job.run_span("base")
    if ct:
        _hdim(svg, X(ct.x0), X(ct.x1), yb, "countertop " + ft_in(ct.length), size=0.12,
              ext_to=Y(front) + 0.03)
    elif span_b:
        _hdim(svg, X(span_b[0]), X(span_b[1]), yb, ft_in(span_b[1] - span_b[0]), size=0.12,
              ext_to=Y(-0.75) + 0.03)
    xl = X(min(x0, ct.x0) if ct else x0) - 0.3
    if job.bases:
        dep = (wall - front)
        _vdim(svg, xl, Y(wall), Y(front), fmt_in(dep), size=0.12)
    if job.uppers:
        ud = max(c.params.depth for c in job.uppers)
        _vdim(svg, X(x1) + 0.3, Y(wall), Y(wall - ud - 0.75), fmt_in(ud + 0.75), size=0.12)


def end_view(svg: Svg, job: Job, box) -> None:
    bx, by, bw, bh = box
    wall = job.wall_y
    top = max(c.z + c.params.height for c in job.cabs)
    s, words = _scale(wall + 1, top, bw - 1.6, bh - 1.25)
    _heading(svg, bx, by + 0.2, "END VIEW", words)
    ox = bx + 0.75 + (bw - 1.6 - (wall + 1) * s) / 2 + 0.75 * s
    floor = by + 0.75 + top * s
    Yx = lambda y: ox + y * s            # front on the left, wall on the right
    Z = lambda z: floor - z * s
    for b in sorted(job.boxes, key=lambda b: b.pos[0] + b.size[0]):  # view from the right end
        x, y, z = b.pos
        dx, dy, dz = b.size
        svg.rect(Yx(y), Z(z + dz), dy * s, dz * s, fill=PULL if "pull" in b.material else _color(b),
                 stroke=_edge(b, "#56606b"), sw=0.005)
    _wall_band(svg, Yx(wall), Z(top + 6), 0.15, (top + 6) * s)
    svg.line(Yx(wall), floor, Yx(wall), Z(top + 6), stroke=INK, sw=0.012)
    svg.line(Yx(-6), floor, Yx(wall) + 0.15, floor, stroke=INK, sw=0.014)
    if job.bases:
        ct = job.counter
        front = ct.y_front if ct else -0.75
        dep = wall - front
        hb = ct.top_z if ct else max(c.params.height for c in job.bases)
        _hdim(svg, Yx(front), Yx(wall), floor + 0.25, fmt_in(dep), size=0.12)
        _vdim(svg, Yx(front) - 0.25, Z(0), Z(hb), fmt_in(hb), size=0.12)
    if job.uppers:
        ud = max(c.params.depth for c in job.uppers) + 0.75
        ub = min(c.z for c in job.uppers)
        ut = max(c.z + c.params.height for c in job.uppers)
        _hdim(svg, Yx(wall - ud), Yx(wall), Z(ut) - 0.15, fmt_in(ud), size=0.12)
        _vdim(svg, Yx(wall - ud) - 0.25, Z(ub), Z(ut), fmt_in(ut - ub), size=0.12)
        _vdim(svg, Yx(wall) + 0.4, Z(0), Z(ut), ft_in(ut), size=0.12)


def counter_paint_rank(box, deck_z: float | None) -> int:
    """Draw order for the 3D view, coarse layers.

    The painter's own order has cycles (a long counter, a tall splash, and the
    cabinets under them all overlap on screen). Breaking a cycle was drawing the
    deck, then drawing a base interior on top of it, so the last cabinet looked
    like it had a hole in the top and only the build-up frame showed. Layers keep
    the deck in one piece: everything under it, then the build-up, then the deck,
    then the splashes, then whatever stands above (the uppers).
    """
    if deck_z is None:
        return 0
    name = box.name
    if "Backsplash" in name or "Side splash" in name:
        return 3
    if "Countertop / Top" in name:
        return 2
    if "Countertop /" in name:
        return 1
    if box.pos[2] + box.size[2] <= deck_z + 1e-4:
        return 0
    return 4


def _deck_z(boxes) -> float | None:
    tops = [b.pos[2] for b in boxes if "Countertop / Top" in b.name]
    return min(tops) if tops else None


def _iso_faces(box) -> tuple[str, str, str]:
    """Fill for the top, right, and front faces.

    A side splash is a thin box, so the 3D view shows its side face. That face
    used to be shaded darker than the backsplash's front face, and the two
    splashes read as different colours. Both are the countertop, so every face
    of a splash is the countertop colour with no extra shade.
    """
    base = FILL if box.material == "filler" else _color(box)
    if "Backsplash" in box.name or "Side splash" in box.name:
        return base, base, base
    return _shade(base, 1.03), _shade(base, 0.82), _shade(base, 0.94)


def iso_view(svg: Svg, job: Job, box, phi_deg: float = 32.0, tilt: float = 0.55,
             ground: bool = True, dim_text: str | None = None) -> None:
    """Shaded 3D view from the front right, above. Boxes painted far to near."""
    bx, by, bw, bh = box
    _heading(svg, bx, by + 0.15, "3D VIEW")
    phi = math.radians(phi_deg)
    v = (-math.sin(phi), math.cos(phi), -tilt)
    n = math.sqrt(sum(c * c for c in v))
    v = tuple(c / n for c in v)
    r = (v[1], -v[0], 0.0)
    rn = math.hypot(r[0], r[1])
    r = (r[0] / rn, r[1] / rn, 0.0)
    u = (r[1] * v[2] - r[2] * v[1], r[2] * v[0] - r[0] * v[2], r[0] * v[1] - r[1] * v[0])
    dot = lambda a, b: a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    boxes = list(job.boxes)
    fb = _filler_box(job)
    if fb:
        boxes.append(fb)
    spans = [s for s in (job.run_span("base"), job.run_span("upper")) if s]
    x0 = min(s[0] for s in spans) - 4
    x1 = max(s[1] for s in spans) + 4
    wall = job.wall_y
    top = max(c.z + c.params.height for c in job.cabs) + 6
    z0 = min(c.z for c in job.cabs) - (0 if ground else 4)
    scene = [(x0, -14, z0), (x1, -14, z0), (x1, wall, z0), (x0, wall, z0),
             (x0, wall, top), (x1, wall, top)] if ground else [
             (x0, wall, z0), (x1, wall, z0), (x0, wall, top), (x1, wall, top)]
    pts2 = [(dot(p, r), dot(p, u)) for p in scene]
    for b in boxes:
        for cx in (0, 1):
            for cy in (0, 1):
                for cz in (0, 1):
                    p = (b.pos[0] + cx * b.size[0], b.pos[1] + cy * b.size[1], b.pos[2] + cz * b.size[2])
                    pts2.append((dot(p, r), dot(p, u)))
    minx = min(p[0] for p in pts2); maxx = max(p[0] for p in pts2)
    miny = min(p[1] for p in pts2); maxy = max(p[1] for p in pts2)
    s = min((bw - 0.3) / (maxx - minx), (bh - 0.5) / (maxy - miny))
    ox = bx + (bw - (maxx - minx) * s) / 2 - minx * s
    oy = by + 0.4 + (bh - 0.5 - (maxy - miny) * s) / 2 + maxy * s
    P = lambda p: (ox + dot(p, r) * s, oy - dot(p, u) * s)

    def poly(points, fill, stroke="none", sw=0.0):
        svg.poly([P(p) for p in points], fill=fill, stroke=stroke, sw=sw)

    if ground:
        poly([(x0, -14, z0), (x1, -14, z0), (x1, wall, z0), (x0, wall, z0)], "#eef0f2")
    poly([(x0, wall, z0), (x1, wall, z0), (x1, wall, top), (x0, wall, top)], "#f6f7f8")

    # order: a box behind (larger y), to the left (smaller x) or below another is drawn first
    def before(a, b) -> bool | None:
        ax0, ay0, az0 = a.pos; ax1, ay1, az1 = (a.pos[i] + a.size[i] for i in range(3))
        bx0, by0, bz0 = b.pos; bx1, by1, bz1 = (b.pos[i] + b.size[i] for i in range(3))
        e = 1e-6
        if ay0 >= by1 - e: return True
        if by0 >= ay1 - e: return False
        if ax1 <= bx0 + e: return True
        if bx1 <= ax0 + e: return False
        if az1 <= bz0 + e: return True
        if bz1 <= az0 + e: return False
        return None

    def bbox2(b):
        xs, ys = [], []
        for cx in (0, 1):
            for cy in (0, 1):
                for cz in (0, 1):
                    q = P((b.pos[0] + cx * b.size[0], b.pos[1] + cy * b.size[1], b.pos[2] + cz * b.size[2]))
                    xs.append(q[0]); ys.append(q[1])
        return min(xs), min(ys), max(xs), max(ys)

    bb = [bbox2(b) for b in boxes]
    depth = [dot((b.pos[0] + b.size[0] / 2, b.pos[1] + b.size[1] / 2, b.pos[2] + b.size[2] / 2), v)
             for b in boxes]
    nb = len(boxes)
    after: list[list[int]] = [[] for _ in range(nb)]
    indeg = [0] * nb
    for i in range(nb):
        for j in range(i + 1, nb):
            a, c = bb[i], bb[j]
            if a[2] <= c[0] or c[2] <= a[0] or a[3] <= c[1] or c[3] <= a[1]:
                continue
            o = before(boxes[i], boxes[j])
            if o is None:
                o = depth[i] > depth[j]
            if o:
                after[i].append(j); indeg[j] += 1
            else:
                after[j].append(i); indeg[i] += 1
    order, done = [], [False] * nb
    while len(order) < nb:
        ready = [i for i in range(nb) if not done[i] and indeg[i] == 0]
        if not ready:                         # a cycle: break it by depth
            ready = [i for i in range(nb) if not done[i]]
        i = max(ready, key=lambda k: depth[k])
        done[i] = True
        order.append(i)
        for j in after[i]:
            indeg[j] -= 1
    deck_z = _deck_z(boxes)
    order.sort(key=lambda i: counter_paint_rank(boxes[i], deck_z))

    for i in order:
        b = boxes[i]
        x, y, z = b.pos
        X1, Y1, Z1 = x + b.size[0], y + b.size[1], z + b.size[2]
        edge = "none" if "pull" in b.material else _edge(b, "#5d6770")
        sw = 0.0 if "pull" in b.material else 0.004
        top_f, right_f, front_f = _iso_faces(b)
        poly([(x, y, Z1), (X1, y, Z1), (X1, Y1, Z1), (x, Y1, Z1)], top_f, edge, sw)  # top
        poly([(X1, y, z), (X1, Y1, z), (X1, Y1, Z1), (X1, y, Z1)], right_f, edge, sw)  # right
        poly([(x, y, z), (X1, y, z), (X1, y, Z1), (x, y, Z1)], front_f, edge, sw)      # front

    span_b = job.run_span("base") or job.run_span("upper")
    if span_b:
        zb = min(c.z for c in job.cabs)
        a, b_ = P((span_b[0], -0.75, zb)), P((span_b[1], -0.75, zb))
        off = 0.18
        ang = math.degrees(math.atan2(b_[1] - a[1], b_[0] - a[0]))
        svg.line(a[0], a[1] + off, b_[0], b_[1] + off, stroke=DIM, sw=0.006)
        mx, my = (a[0] + b_[0]) / 2, (a[1] + b_[1]) / 2 + off + 0.2
        svg.text(mx, my, dim_text or ("bases " + ft_in(span_b[1] - span_b[0])), size=0.13, anchor="middle",
                 fill=DIM, rotate=ang)


def schedule(svg: Svg, job: Job, box) -> None:
    bx, by, bw, bh = box
    _heading(svg, bx, by + 0.15, "CABINETS")
    svg.text(bx + bw, by + 0.15, "Depth includes the doors and drawer fronts.", size=0.1,
             anchor="end", fill=SOFT)
    # uppers first, then the bases (Brook, 2026-10-24); filler and counter stay last
    ordered = sorted(job.cabs, key=lambda c: (c.run != "upper", c.x))
    rows = []
    for c in ordered:
        p = c.params
        label = STYLE_PRESETS[p.style]["label"].replace(" (no countertop)", "").replace(" — ", ", ")
        if p.doors == 1:
            label += f", handle {p.handle_side[0].upper()}"
        rows.append((job.codes[c.name], label, fmt_in(p.width), fmt_in(p.height), fmt_in(p.depth + 0.75)))
    if job.filler:
        side = job.settings.get("filler_side", "right")
        rows.append(("F", f"Filler, {side} end of the bases", fmt_in(job.filler[1] - job.filler[0]), "", ""))
    if job.counter:
        ct = job.counter
        rows.append((ct.code, "Countertop, " + ("laminate" if ct.kind == "laminate" else "solid surface"),
                     fmt_in(ct.length), fmt_in(EDGE_T), fmt_in(ct.depth)))
    room = bh - 0.75
    if len(rows) * 0.18 <= room:
        # one column, the full width
        cols = [("Tag", 0.0), ("Style", 0.55), ("Width", 3.9), ("Height", 4.75), ("Depth", 5.55)]
        y = by + 0.45
        for name, dx in cols:
            svg.text(bx + dx, y, name, size=0.11, weight="bold", fill=SOFT)
        svg.line(bx, y + 0.06, bx + bw, y + 0.06, stroke="#c9ced4", sw=0.006)
        line_h = min(0.21, room / max(1, len(rows)))
        for row in rows:
            y += line_h
            for (name, dx), val in zip(cols, row):
                svg.text(bx + dx, y, val, size=0.13, fill=INK, weight="bold" if name == "Tag" else "normal")
        return
    # a long job: two columns, the size as W x H x D, the style without its row word
    half = math.ceil(len(rows) / 2)
    line_h = min(0.18, room / half)
    size = min(0.11, line_h * 0.72)
    colw = bw / 2
    for k in range(2):
        x0 = bx + k * colw
        y = by + 0.45
        for name, dx in (("Tag", 0.0), ("Style", 0.42), ("W x H x D", colw - 1.4)):
            svg.text(x0 + dx, y, name, size=0.1, weight="bold", fill=SOFT)
        svg.line(x0, y + 0.06, x0 + colw - 0.15, y + 0.06, stroke="#c9ced4", sw=0.006)
        for tag, label, w, h, d in rows[k * half:(k + 1) * half]:
            y += line_h
            short = (label.replace("Wall upper, ", "").replace("Base, ", "")
                     .replace("microwave shelf, 2 doors above", "microwave + 2 doors")
                     .replace("1 drawer over 2 doors", "1 drawer, 2 doors")
                     .replace("Filler, ", "filler, ").replace(" end of the bases", " end"))
            sizes = " x ".join(v for v in (w, h, d) if v)
            svg.text(x0, y, tag, size=size, weight="bold", fill=INK)
            svg.text(x0 + 0.42, y, short, size=size, fill=INK)
            svg.text(x0 + colw - 1.4, y, sizes, size=size, fill=INK)


def title_block(svg: Svg, job: Job, box, date: str, drawing: str = "Kitchen layout - client presentation",
                cabinets: str | None = None, page: str = "") -> None:
    bx, by, bw, bh = box
    svg.rect(bx, by, bw, bh, fill="#ffffff", stroke=INK, sw=0.012)
    svg.line(bx, by + 0.55, bx + bw, by + 0.55, stroke=INK, sw=0.008)
    svg.text(bx + 0.15, by + 0.38, job.name, size=0.26, weight="bold", fill=INK)
    nb, nu = len(job.bases), len(job.uppers)
    rows = [
        ("Drawing", drawing),
        ("Date", date + (f"      Page {page}" if page else "")),
        ("Cabinets", cabinets or f"{nb + nu} ({nb} base, {nu} upper)"),
        ("Countertop", job.counter.description if job.counter else "none"),
        ("Prepared by", ""),
    ]
    y = by + 0.76
    for k, v in rows:
        svg.text(bx + 0.15, y, k.upper(), size=0.09, fill=SOFT)
        svg.text(bx + 1.3, y, v, size=0.13, fill=INK)
        if k == "Prepared by":
            svg.line(bx + 1.3, y + 0.03, bx + bw - 0.2, y + 0.03, stroke=SOFT, sw=0.005)
        y += 0.18
    svg.text(bx + 0.15, by + bh - 0.08,
             "Preliminary, for discussion. Not for construction.", size=0.1, fill=SOFT)


# --------------------------------------------------------------------------- detail pages
def style_groups(job: Job) -> list[tuple[str, list]]:
    """Styles in the order they first appear (bases left to right, then uppers)."""
    order: dict[str, list] = {}
    for c in sorted(job.cabs, key=lambda c: (c.run != "base", c.x)):
        order.setdefault(c.params.style, []).append(c)
    return list(order.items())


def _style_name(style: str) -> str:
    return STYLE_PRESETS[style]["label"].replace(" (no countertop)", "").replace(" — ", ", ")


def _single(cab, name: str) -> Job:
    """The one cabinet alone at the origin. Nothing from its neighbours."""
    from dataclasses import replace as _replace
    lone = _replace(cab, x=0.0, y=0.0, z=0.0, gap_after=0.0)
    job = job_from([lone], {"upper_bottom": 0.0, "counter": "none"}, name)
    job.codes = {lone.name: "W"}
    return job


def _edge(b, stroke: str) -> str:
    """No outline on the thin slices that draw a rounded corner (microwave shelf)."""
    return "none" if getattr(b, "shape", "") == "slice" else stroke


def _ortho(svg: Svg, boxes, view: str, X, Y) -> None:
    """Front, side (from the right) or top view of boxes, painted far to near."""
    if view == "front":
        key, uv = (lambda b: -b.pos[1]), (lambda b: (b.pos[0], b.pos[2], b.size[0], b.size[2]))
    elif view == "side":
        key, uv = (lambda b: b.pos[0] + b.size[0]), (lambda b: (b.pos[1], b.pos[2], b.size[1], b.size[2]))
    else:
        key, uv = (lambda b: b.pos[2] + b.size[2]), (lambda b: (b.pos[0], b.pos[1], b.size[0], b.size[1]))
    for b in sorted(boxes, key=key):
        u, v, du, dv = uv(b)
        x0, x1 = sorted((X(u), X(u + du)))
        y0, y1 = sorted((Y(v), Y(v + dv)))
        pull = "pull" in b.material
        svg.rect(x0, y0, x1 - x0, y1 - y0, fill=PULL if pull else _color(b),
                 stroke="none" if pull else _edge(b, "#56606b"), sw=0 if pull else 0.006)


def _swing_marks(svg: Svg, boxes, X, Z) -> None:
    """Dashed swing lines on a single door: the point of the V is the hinge side."""
    for b in boxes:
        name = b.name.split(" / ")[-1]
        if not name.startswith("Door, handle "):
            continue
        handle = name[-1]
        x, _y, z = b.pos
        dx, _dy, dz = b.size
        xh, xg = (x + dx, x) if handle == "R" else (x, x + dx)
        mid = z + dz / 2
        for zz in (z + dz, z):
            svg.line(X(xh), Z(zz), X(xg), Z(mid), stroke="#56606b", sw=0.006, dash="0.05,0.035")


def _features(p, has_counter: bool = False) -> list[str]:
    enforce_upper_door_limit(p)
    out = list(door_rule_warnings(p))
    if p.doors == 1:
        out.append(f"1 door, handle on the {p.handle_side}, hinged on the {p.hinge_side} "
                   "(dashed V points to the hinges)")
    if p.open_shelves:
        out.append(f"open: no doors, {p.open_shelves} adjustable shelves, finished inside")
    if p.is_microwave:
        from .params import MICROWAVE_SHELF_CALLED_DEPTH, MICROWAVE_SHELF_CORNER_R
        out.append(f"{fmt_in(p.depth)} deep box like the other uppers; open microwave shelf at the "
                   f"bottom, {fmt_in(p.mw_opening_h)} clear")
        out.append(f"the shelf projects to {fmt_in(MICROWAVE_SHELF_CALLED_DEPTH + p.back_thk)} "
                   f"overall, {fmt_in(MICROWAVE_SHELF_CORNER_R)} radius front corners")
        out.append("2 doors over a fixed divider above the microwave")
    if p.sink:
        out.append(f"sink base: false drawer front, {fmt_in(p.drawer_front_h)} tall, no pull; "
                   "open inside for the sink and plumbing (no drawer box, no shelf)")
    elif p.drawers:
        out.append(f"{p.drawers} drawer{'s' if p.drawers > 1 else ''}"
                   + (f", top drawer front {fmt_in(p.drawer_front_h)} tall"
                      if p.drawers == 1 and p.drawer_front_h else ", equal drawer fronts"))
    if p.doors > 1 and not p.is_microwave:
        out.append(f"{p.doors} doors")
    if p.has_shelf:
        out.append("adjustable shelf behind the doors")
    if p.has_toe_kick:
        out.append(f"recessed toe kick, {fmt_in(p.toe_kick_h)} high")
    out.append("fronts overlay the case; wire pulls" if p.doors or p.drawers
               else "case edges banded; no fronts")
    if str(p.style).startswith("upper"):
        out.append("hangs on the wall; top and bottom fit between full-height sides")
    else:
        out.append("countertop: see the countertop page" if has_counter else "no countertop in this job")
    return out


def detail_page(job: Job, style: str, cabs: list, date: str, page: str) -> Svg:
    rep = cabs[0]
    p = rep.params
    lone = _single(rep, job.name)
    boxes = lone.boxes
    W, H, D = p.width, p.height, p.depth + 0.75        # depth includes the fronts
    svg = Svg(PAGE_W, PAGE_H)
    svg.rect(M / 2, M / 2, PAGE_W - M, PAGE_H - M, fill="none", stroke=INK, sw=0.014)
    svg.text(M + 0.1, M + 0.32, _style_name(style).upper(), size=0.28, weight="bold", fill=INK)
    svg.text(M + 0.1, M + 0.58, f"{job.name}  -  cabinet detail. Drawn at W = {fmt_in(W)}; "
             "the other widths are the same cabinet, wider or narrower.", size=0.14, fill=SOFT)

    # one scale for front, side and top so they line up
    fit = min(6.9 / (H + D), 6.7 / (W + D))
    s, words = fit, f"approx. 1:{round(1 / fit)}"
    for std, w in SCALES:
        if std <= fit + 1e-9:
            s, words = std, w
            break
    fx, fy = M + 0.9, M + 1.35                       # front view top-left
    _heading(svg, M + 0.1, M + 1.0, "FRONT", words)
    X = lambda x: fx + x * s
    Z = lambda z: fy + (H - z) * s
    _ortho(svg, boxes, "front", X, Z)
    _swing_marks(svg, boxes, X, Z)
    if p.is_microwave:
        lo = p.case_bottom_z + p.carcass_thk
        _vdim(svg, X(0) - 0.3, Z(lo), Z(lo + p.mw_opening_h), f"opening {fmt_in(p.mw_opening_h)}",
              size=0.11, ext_to=X(0) - 0.03)
    _hdim(svg, X(0), X(W), Z(0) + 0.35, f"W = {fmt_in(W)}", size=0.13, ext_to=Z(0) + 0.03)
    _vdim(svg, X(W) + 0.35, Z(0), Z(H), f"H = {fmt_in(H)}", size=0.13, ext_to=X(W) + 0.03)
    if p.has_toe_kick:
        _vdim(svg, X(0) - 0.3, Z(0), Z(p.toe_kick_h), fmt_in(p.toe_kick_h), size=0.11, ext_to=X(0) - 0.03)
    if p.drawers == 1 and p.drawer_front_h and p.doors:
        fronts = [b for b in boxes if "Drawer front" in b.name or "False front" in b.name]
        top = max(b.pos[2] + b.size[2] for b in fronts)
        bot = min(b.pos[2] for b in fronts)
        _vdim(svg, X(0) - 0.3, Z(bot), Z(top), fmt_in(top - bot), size=0.11, ext_to=X(0) - 0.03)

    sx0 = X(W) + 1.2                                  # side view, same height
    _heading(svg, sx0, M + 1.0, "SIDE")
    SY = lambda y: sx0 + (y + 0.75) * s
    _ortho(svg, boxes, "side", SY, Z)
    _hdim(svg, SY(-0.75), SY(p.depth), Z(0) + 0.35, f"D = {fmt_in(D)}", size=0.13, ext_to=Z(0) + 0.03)
    _vdim(svg, SY(p.depth) + 0.35, Z(0), Z(H), fmt_in(H), size=0.12, ext_to=SY(p.depth) + 0.03)
    svg.text(SY(p.depth / 2), Z(H) - 0.1, "front left, wall right", size=0.1, anchor="middle", fill=SOFT)

    ty0 = Z(0) + 1.15                                 # top view under the front view
    _heading(svg, M + 0.1, ty0 - 0.15, "TOP")
    TY = lambda y: ty0 + (p.depth - y) * s
    _ortho(svg, boxes, "top", X, TY)
    _hdim(svg, X(0), X(W), TY(-0.75) + 0.35, f"W = {fmt_in(W)}", size=0.13, ext_to=TY(-0.75) + 0.03)
    _vdim(svg, X(W) + 0.35, TY(-0.75), TY(p.depth), fmt_in(D), size=0.12, ext_to=X(W) + 0.03)
    svg.text(X(W / 2), TY(p.depth) - 0.08, "wall side", size=0.1, anchor="middle", fill=SOFT)

    iso_view(svg, lone, (M + 9.9, M + 0.8, 6.3, 5.4), ground=not str(p.style).startswith("upper"),
             dim_text=f"W = {fmt_in(W)}")

    # what it is, and the widths of this style in the job
    bx, by = M + 9.9, M + 6.45
    feats = _features(p, job.counter is not None)
    svg.text(bx, by, "WHAT IT IS", size=0.15, weight="bold", fill=INK)
    for i, line in enumerate(feats):
        svg.text(bx + 0.1, by + 0.25 + i * 0.2, "- " + line, size=0.12, fill=INK)
    ty = by + 0.35 + len(feats) * 0.2 + 0.15
    svg.text(bx, ty, f"THIS STYLE IN {job.name.upper()}", size=0.15, weight="bold", fill=INK)
    cols = [("Tag", 0.0), ("Width", 0.7), ("Height", 1.6), ("Depth", 2.5)]
    if p.drawers == 1 and p.doors:
        cols.append(("Drawer", 3.4))
    if p.doors == 1:
        cols.append(("Handle", 3.4))
    for name, dx in cols:
        svg.text(bx + dx, ty + 0.25, name, size=0.11, weight="bold", fill=SOFT)
    for i, c in enumerate(cabs):
        y = ty + 0.47 + i * 0.2
        q = c.params
        vals = [job.codes[c.name], fmt_in(q.width), fmt_in(q.height), fmt_in(q.depth + 0.75)]
        if len(cols) == 5 and cols[4][0] == "Drawer":
            vals.append(fmt_in(q.drawer_front_h or 0))
        elif len(cols) == 5:
            vals.append(q.handle_side)
        for (name, dx), val in zip(cols, vals):
            svg.text(bx + dx, y, val, size=0.12, fill=INK, weight="bold" if name == "Tag" else "normal")
        if c is rep:
            svg.text(bx + 4.3, y, "drawn on this page", size=0.1, fill=SOFT)
    svg.text(bx, ty + 0.62 + len(cabs) * 0.2, "Depth includes the doors and drawer fronts.",
             size=0.1, fill=SOFT)
    title_block(svg, job, (M + 5.9, M + 8.45, 3.8, 1.75), date, drawing="Cabinet detail",
                cabinets=f"{len(cabs)} of this style", page=page)
    return svg


def _section(svg: Svg, ct, boxes, X, Z, xs: float) -> None:
    """Counter boxes cut by the plane x = xs, seen from the left end (front on the left)."""
    for b in sorted(boxes, key=lambda b: b.pos[0]):
        if not (b.pos[0] - 1e-6 <= xs <= b.pos[0] + b.size[0] + 1e-6):
            continue
        y, z, dy, dz = b.pos[1], b.pos[2], b.size[1], b.size[2]
        svg.rect(X(y), Z(z + dz), dy * abs(X(1) - X(0)), dz * abs(Z(0) - Z(1)), fill=_color(b),
                 stroke=INK, sw=0.01)


def _dogbone(svg: Svg, cx: float, cy: float, s: float) -> None:
    """A dogbone pocket across a seam, seen from below. s = paper inches per inch."""
    r, neck = 0.5 * s, 0.35 * s
    for side in (-1, 1):
        svg.circle(cx + side * 1.0 * s, cy, r, fill="#ffffff", stroke=INK, sw=0.01)
    svg.rect(cx - 1.0 * s, cy - neck / 2, 2.0 * s, neck, fill="#ffffff", stroke="none")
    svg.line(cx - 1.0 * s + r * 0.7, cy - neck / 2, cx + 1.0 * s - r * 0.7, cy - neck / 2, stroke=INK, sw=0.01)
    svg.line(cx - 1.0 * s + r * 0.7, cy + neck / 2, cx + 1.0 * s - r * 0.7, cy + neck / 2, stroke=INK, sw=0.01)


def _seam_detail(svg: Svg, x: float, y: float) -> None:
    """Typical laminate seam from below: 6" strip on the seam, dogbones across it."""
    s = 0.05
    svg.text(x, y, "TYPICAL LAMINATE SEAM, FROM BELOW", size=0.14, weight="bold", fill=INK)
    top, h, w = y + 0.15, 25 * s, 30 * s
    cx = x + w / 2
    svg.rect(x, top, w, h, fill=_shade(LAMTOP, 0.97), stroke=INK, sw=0.01)
    svg.rect(cx - 3 * s, top + 1.5 * s, 6 * s, h - 3 * s, fill=_shade(LAMTOP, 0.85), stroke=SOFT, sw=0.008)
    svg.line(cx, top - 0.05, cx, top + h + 0.05, stroke="#b03a2e", sw=0.014, dash="0.06,0.04")
    for k in range(2):
        _dogbone(svg, cx, top + 1.5 * s + (h - 3 * s) * (k + 0.5) / 2, s * 1.5)
    tx = x + w + 0.3
    for i, line in enumerate([
        '6" strip of 3/4" plywood centred on the seam',
        '(3" glued and stapled to each piece).',
        'Dogbone pockets routed 1/2" deep across the seam.',
        'At install: adhesive in the seam, dogbone clamps',
        'pull the two pieces into one countertop.',
    ]):
        svg.text(tx, top + 0.2 + i * 0.2, line, size=0.12, fill=INK)


def counter_page(job: Job, date: str, page: str) -> Svg:
    """Countertop detail: section, front-edge profile, how it is built."""
    ct = job.counter
    lam = ct.kind == "laminate"
    svg = Svg(PAGE_W, PAGE_H)
    svg.rect(M / 2, M / 2, PAGE_W - M, PAGE_H - M, fill="none", stroke=INK, sw=0.014)
    svg.text(M + 0.1, M + 0.32, ("COUNTERTOP - LAMINATE" if lam else "COUNTERTOP - SOLID SURFACE"),
             size=0.28, weight="bold", fill=INK)
    svg.text(M + 0.1, M + 0.58, f"{job.name}  -  {ct.description}. {fmt_in(ct.length)} long x "
             f"{fmt_in(ct.depth)} deep, top {fmt_in(ct.top_z)} off the floor.", size=0.14, fill=SOFT)
    boxes = ct.boxes
    # cut through the middle of the first cabinet, away from the strips
    first = min((c for c in job.bases), key=lambda c: c.x)
    xs = first.x + first.params.width / 2 + 0.01
    # 1) section at 3" = 1'-0"
    s = 0.25
    ox, base = M + 0.9, M + 3.6
    X = lambda y: ox + (y - ct.y_front) * s
    Z = lambda z: base - (z - ct.z0) * s
    _heading(svg, M + 0.1, M + 1.0, "SECTION THROUGH THE COUNTER", '3" = 1\'-0"')
    # cabinet top under it, dashed
    svg.rect(X(0), Z(ct.z0), (ct.y_back) * s, 1.6, fill="none", stroke=SOFT, sw=0.008, dash="0.05,0.04")
    svg.text(X(ct.y_back / 2), Z(ct.z0) + 0.45, "cabinet (case top)", size=0.11, anchor="middle", fill=SOFT)
    _section(svg, ct, boxes, X, Z, xs)
    svg.line(X(ct.y_back), Z(ct.z0) + 1.7, X(ct.y_back), Z(ct.top_z + 6), stroke=INK, sw=0.014)
    _wall_band(svg, X(ct.y_back), Z(ct.top_z + 6), 0.15, (ct.top_z + 6 - ct.z0) * s + 1.7)
    _hdim(svg, X(ct.y_front), X(ct.y_back), Z(ct.top_z + 4) - 0.25, f"{fmt_in(ct.depth)} deep", size=0.12)
    _vdim(svg, X(ct.y_front) - 0.3, Z(ct.z0), Z(ct.top_z), fmt_in(ct.top_z - ct.z0), size=0.11)
    _vdim(svg, X(ct.y_back) + 0.5, Z(ct.top_z), Z(ct.top_z + 4), '4" splash', size=0.11)
    _hdim(svg, X(ct.y_front), X(0), Z(ct.z0) + 0.35, fmt_in(-ct.y_front), size=0.1)
    svg.text(X(-ct.y_front * 0.5) + 0.05, Z(ct.z0) + 0.6, "overhang past the case", size=0.09, fill=SOFT)

    # 2) front edge, full size: the first 3" of the counter
    s2, reach = 1.0, 3.0
    ex, eb = M + 9.0, M + 3.4
    X2 = lambda y: ex + (y - ct.y_front) * s2
    Z2 = lambda z: eb - (z - ct.z0) * s2
    _heading(svg, M + 8.4, M + 1.0, "FRONT EDGE", "full size")
    for b in sorted(boxes, key=lambda b: b.pos[0]):
        if not (b.pos[0] <= xs <= b.pos[0] + b.size[0]):
            continue
        y0, z0, dy, dz = b.pos[1], b.pos[2], b.size[1], b.size[2]
        if y0 > ct.y_front + reach:
            continue
        dy = min(dy, ct.y_front + reach - y0)
        svg.rect(X2(y0), Z2(z0 + dz), dy * s2, dz * s2, fill=_color(b), stroke=INK, sw=0.012)
    svg.line(X2(ct.y_front + reach), Z2(ct.z0 - 0.2), X2(ct.y_front + reach), Z2(ct.top_z + 0.2),
             stroke=SOFT, sw=0.008, dash="0.05,0.04")
    _vdim(svg, X2(ct.y_front) - 0.35, Z2(ct.z0), Z2(ct.top_z), '1 1/2" edge', size=0.12)
    tx = X2(ct.y_front + reach) + 0.35
    if lam:
        brown = "#8a5a2b"
        svg.line(X2(ct.y_front), Z2(ct.top_z) - 0.03, X2(ct.y_front + reach), Z2(ct.top_z) - 0.03,
                 stroke=brown, sw=0.05)
        svg.line(X2(ct.y_front) - 0.03, Z2(ct.top_z), X2(ct.y_front) - 0.03, Z2(ct.z0),
                 stroke=brown, sw=0.05)
        callouts = [
            (X2(ct.y_front + 1.8), ct.top_z, "Laminate, step 3: the top (goes on last)"),
            (X2(ct.y_front + 2.4), ct.z0 + 1.1, '3/4" plywood top'),
            (X2(ct.y_front + 2.0), ct.z0 + 0.4, '3/4" plywood build-up, glued and stapled'),
        ]
        svg.text(X2(ct.y_front) - 0.1, Z2(ct.z0) + 0.35, "Laminate, step 2: the front edge.",
                 size=0.12, fill=INK)
        svg.text(X2(ct.y_front) - 0.1, Z2(ct.z0) + 0.55, "Step 1 is the side edges, when needed.",
                 size=0.12, fill=INK)
    else:
        callouts = [
            (X2(ct.y_front + 2.0), ct.z0 + 1.25, '1/2" solid surface top'),
            (X2(ct.y_front + 0.25), ct.z0 + 1.4, '1/4" lip left over the rabbet'),
            (X2(ct.y_front + 0.25), ct.z0 + 0.6, '1 1/4" solid surface edge strip, epoxied'),
            (X2(ct.y_front + 2.0), ct.z0 + 0.5, '1" plywood stiffener'),
        ]
    rows = sorted(callouts, key=lambda c: -c[1])
    for k, (px_, z, text) in enumerate(rows):
        ty = Z2(ct.top_z) - 0.15 + k * 0.42
        svg.circle(px_, Z2(z), 0.025, fill=INK)
        svg.line(px_, Z2(z), tx - 0.05, ty - 0.04, stroke=SOFT, sw=0.006)
        svg.text(tx, ty, text, size=0.12, fill=INK)

    # 3) how it is built, and the seams
    bx, by = M + 0.1, M + 6.1
    svg.text(bx, by, "HOW IT IS BUILT", size=0.16, weight="bold", fill=INK)
    if lam:
        lines = [
            '3/4" plywood top, laminated.',
            '3/4" plywood build-up strips, 4" wide, glued and stapled under the front edge, at each end,',
            "  and centred on every place two cabinets meet. That makes the 1-1/2\" front edge, and the",
            "  installers screw up through the cabinets into the strips.",
            "Laminate goes on in this order: side edges (when needed), front edge, then the top.",
            '4" backsplash on the wall; 4" side splash at a wall end. Every exposed splash edge is laminated.',
            'Open ends: 1" overhang with a laminated (finished) edge. Wall ends: flush.',
        ]
    else:
        lines = [
            '1/2" solid surface top, with a 1/2" wide x 1/4" deep rabbet under the front and finished edges.',
            "1-1/4\" solid surface edge strip epoxied into the rabbet: 1/4\" + 1-1/4\" = 1-1/2\" reveal.",
            '1" plywood stiffener strips under the top (front, back, ends, and centred where cabinets meet)',
            '  bring it to 1-1/2" overall, and give the installers plywood to screw into.',
            '4" solid surface backsplash; 4" side splash at a wall end.',
            'Open ends: 1" overhang with a finished edge. Wall ends: flush.',
        ]
    for i, line in enumerate(lines):
        svg.text(bx + 0.1, by + 0.3 + i * 0.22, line, size=0.13, fill=INK)
    y = by + 0.45 + len(lines) * 0.22
    import textwrap
    seam_lines = []
    for n in (ct.notes or [f"One piece: {fmt_in(ct.length)} long, no seam."]):
        seam_lines += textwrap.wrap(n, 100)
    svg.text(bx, y, "SEAMS", size=0.16, weight="bold", fill=INK)
    for i, n in enumerate(seam_lines[:6]):
        svg.text(bx + 0.1, y + 0.28 + i * 0.22, n, size=0.13, fill=INK)
    if lam:
        _seam_detail(svg, M + 9.9, M + 6.95)

    # small underside plan showing the strips
    px, py, pw = M + 9.9, M + 5.0, 6.2
    sp = min(pw / ct.length, 1.2 / ct.depth)
    svg.text(px, py, "UNDERSIDE - WHERE THE STRIPS GO", size=0.14, weight="bold", fill=INK)
    PX = lambda x: px + (x - ct.x0) * sp
    PY = lambda y: py + 0.25 + (y - ct.y_front) * sp     # front at the top of this little plan
    svg.rect(PX(ct.x0), PY(ct.y_front), ct.length * sp, ct.depth * sp, fill="#ffffff", stroke=INK, sw=0.01)
    for b in boxes:
        if "plywood" not in b.material or b.pos[2] > ct.z0 + 0.5 or "Top" in b.name.split("/")[-1]:
            continue
        svg.rect(PX(b.pos[0]), PY(b.pos[1]), b.size[0] * sp, b.size[1] * sp, fill=_shade(LAMTOP, 0.9),
                 stroke=SOFT, sw=0.005)
    for c in job.bases:
        svg.line(PX(c.x), PY(ct.y_front) - 0.06, PX(c.x), PY(ct.y_front) - 0.02, stroke=INK, sw=0.01)
    for sx in ct.seams:
        svg.line(PX(sx), PY(ct.y_front) - 0.1, PX(sx), PY(ct.y_back) + 0.1, stroke="#b03a2e", sw=0.014,
                 dash="0.06,0.04")
    for dx, dy in ct.dogbones:
        svg.rect(PX(dx) - 0.09, PY(dy) - 0.025, 0.18, 0.05, fill=INK, stroke="none")
    svg.text(px, PY(ct.y_back) + 0.3, "front edge at the top; red dashes = seams", size=0.1, fill=SOFT)

    title_block(svg, job, (M + 9.9, M + 8.45, 6.3, 1.75), date, drawing="Countertop detail",
                page=page)
    return svg


def render_pages(job: Job, date: str | None = None) -> list[Svg]:
    date = date or _dt.date.today().strftime("%B %-d, %Y")
    groups = style_groups(job)
    extra = 1 if job.counter else 0
    total = 1 + extra + len(groups)
    pages = [render(job, date, page=f"1 of {total}")]
    if job.counter:
        pages.append(counter_page(job, date, f"2 of {total}"))
    for i, (style, cabs) in enumerate(groups, start=2 + extra):
        pages.append(detail_page(job, style, cabs, date, f"{i} of {total}"))
    return pages


def render(job: Job, date: str | None = None, page: str = "") -> Svg:
    """Page 1: the whole kitchen."""
    date = date or _dt.date.today().strftime("%B %-d, %Y")
    svg = Svg(PAGE_W, PAGE_H)
    svg.rect(M / 2, M / 2, PAGE_W - M, PAGE_H - M, fill="none", stroke=INK, sw=0.014)
    svg.text(M + 0.1, M + 0.32, job.name.upper(), size=0.28, weight="bold", fill=INK)
    svg.text(M + 0.1, M + 0.58, "Cabinet layout", size=0.14, fill=SOFT)
    front_elevation(svg, job, (M + 0.1, M + 0.8, 9.6, 5.6))
    iso_view(svg, job, (M + 9.9, M + 0.8, 6.3, 5.6))
    svg.line(M + 0.1, M + 6.55, PAGE_W - M - 0.1, M + 6.55, stroke="#d5dae0", sw=0.006)
    plan_view(svg, job, (M + 0.1, M + 6.7, 6.2, 3.5))
    end_view(svg, job, (M + 6.5, M + 6.7, 3.2, 3.5))
    schedule(svg, job, (M + 9.9, M + 6.7, 6.3, 1.7))
    title_block(svg, job, (M + 9.9, M + 8.45, 6.3, 1.75), date, page=page)
    return svg


def write_client_sheet(job: Job, out_dir: Path, stem: str = "client-sheet",
                       png: bool = True, date: str | None = None) -> dict:
    """<stem>.pdf: page 1 the kitchen, then one page per cabinet style.
    Also <stem>.svg (page 1) and, with png, <stem>.png (page 1) and <stem>-pN.png."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = render_pages(job, date)
    svgs = []
    for i, page in enumerate(pages, start=1):
        path = out_dir / (f"{stem}.svg" if i == 1 else f"{stem}-p{i}.svg")
        page.write(str(path))
        svgs.append(path)
    out = {"svg": svgs[0], "pages": len(pages)}
    rsvg = shutil.which("rsvg-convert")
    if not rsvg:
        raise RuntimeError("rsvg-convert is not installed; it turns the pages into a PDF")
    pdf = out_dir / f"{stem}.pdf"
    subprocess.run([rsvg, "-f", "pdf", "-o", str(pdf)] + [str(s) for s in svgs], check=True,
                   capture_output=True)
    out["pdf"] = pdf
    if png:
        pngs = []
        for path in svgs:
            png_path = path.with_suffix(".png")
            subprocess.run([rsvg, "-f", "png", "-d", "110", "-p", "110", "-b", "white",
                            "-o", str(png_path), str(path)], check=True, capture_output=True)
            pngs.append(png_path)
        out["png"] = pngs[0]
        out["pngs"] = pngs
    return out
