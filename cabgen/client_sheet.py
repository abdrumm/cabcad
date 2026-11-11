"""Carpenter 2D: the 11x17 drawing set for a kitchen (Brook, Nov 11).

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
from dataclasses import dataclass
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
    return job_from(cabs, settings, name or settings.get("job")
                    or sheet.stem.replace("-", " ").replace("_", " ").title())


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
               round(b.pos[1], 4), round(b.size[1], 4), round(b.pos[2], 4), round(b.size[2], 4))
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
                                 first.material, first.join))
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
    return Job(name, cabs, settings, keep, cabinet_codes(cabs), filler, counter)


# The colours in use. The defaults are the drawing palette above; a job's finish picks
# (doors/fronts, box, countertop) swap them in for its pages, render and AR model.
import contextlib
import contextvars

DEFAULT_PALETTE = {"case": CASE, "front": FRONT, "pull": PULL, "laminate_top": LAMTOP,
                   "solid_top": SOLID}
_PALETTE: contextvars.ContextVar[dict] = contextvars.ContextVar("palette", default=DEFAULT_PALETTE)


def pal() -> dict:
    return _PALETTE.get()


@contextlib.contextmanager
def palette_for(job):
    """Draw with the job's finish colours inside this block."""
    from .finishes import palette_of
    token = _PALETTE.set(palette_of(getattr(job, "settings", None) or {}))
    try:
        yield pal()
    finally:
        _PALETTE.reset(token)


def role_of(box) -> str:
    """Which finish a box shows: front, case, pull, laminate_top or solid_top."""
    mat = box.material
    if "pull" in mat or "hardware" in mat:
        return "pull"
    if "solid surface" in mat:
        return "solid_top"
    if "plywood" in mat:
        return "laminate_top"
    if "laminate" in mat:
        return "front"
    return "case"


def _color(box) -> str:
    return pal()[role_of(box)]


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
def elevation_scale_words(job: Job, bw: float, bh: float) -> str:
    """The front-elevation scale, for the identity block. Not drawn on the view."""
    spans = [s for s in (job.run_span("base"), job.run_span("upper")) if s]
    if not spans:
        return "per view"
    x0 = min(s[0] for s in spans)
    x1 = max(s[1] for s in spans)
    top = max(c.z + c.params.height for c in job.cabs)
    _s, words = _scale(x1 - x0, top, bw - 2.6, bh - 2.2)
    return words


def front_elevation(svg: Svg, job: Job, box) -> None:
    bx, by, bw, bh = box
    span_b, span_u = job.run_span("base"), job.run_span("upper")
    spans = [s for s in (span_b, span_u) if s]
    x0 = min(s[0] for s in spans)
    x1 = max(s[1] for s in spans)
    top = max(c.z + c.params.height for c in job.cabs)
    s, _words = _scale(x1 - x0, top, bw - 2.6, bh - 2.2)
    _heading(svg, bx, by + 0.2, "FRONT ELEVATION")
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
    if job.uppers:
        ub = min(c.z for c in job.uppers)
        ut = max(c.z + c.params.height for c in job.uppers)
        if job.bases:
            _vdim(svg, xr, Z(bh_), Z(ub), fmt_in(ub - bh_), size=0.12)
        _vdim(svg, xr, Z(ub), Z(ut), fmt_in(ut - ub), size=0.12)
        _vdim(svg, xr + 0.4, Z(0), Z(ut), "overall " + ft_in(ut), size=0.13)
        svg.line(xr - 0.1, Z(ub), xr + 0.6, Z(ub), stroke=SOFT, sw=0.004, dash="0.03,0.03")


def plan_view(svg: Svg, job: Job, box) -> None:
    bx, by, bw, bh = box
    spans = [s for s in (job.run_span("base"), job.run_span("upper")) if s]
    x0 = min(s[0] for s in spans)
    x1 = max(s[1] for s in spans)
    wall = job.wall_y
    depth = wall + 0.75
    s, _words = _scale(x1 - x0, depth, bw - 1.6, bh - 1.3)
    _heading(svg, bx, by + 0.2, "PLAN (TOP VIEW)")
    ox = bx + 0.7 + (bw - 1.6 - (x1 - x0) * s) / 2 - x0 * s
    oy = by + 0.75
    X = lambda x: ox + x * s
    Y = lambda y: oy + (wall - y) * s       # wall at the top
    _wall_band(svg, X(x0) - 0.15, Y(wall) - 0.15, (x1 - x0) * s + 0.3, 0.15)
    svg.line(X(x0) - 0.15, Y(wall), X(x1) + 0.15, Y(wall), stroke=INK, sw=0.012)
    for c in job.bases:
        p = c.params
        svg.rect(X(c.x), Y(c.y + p.depth), p.width * s, p.depth * s, fill=pal()["case"], stroke=INK, sw=0.009)
        svg.rect(X(c.x + 0.25), Y(c.y), (p.width - 0.5) * s, 0.75 * s, fill=pal()["front"], stroke="#56606b",
                 sw=0.005)
        svg.text(X(c.x + p.width / 2), Y(c.y + p.depth * 0.28) + 0.05, job.codes[c.name], size=0.15,
                 anchor="middle", weight="bold", fill=INK)
    if job.filler:
        f0, f1 = job.filler
        dep = max(c.params.depth for c in job.bases)
        svg.rect(X(f0), Y(dep), (f1 - f0) * s, (dep + 0.75) * s, fill=FILL, stroke=INK, sw=0.007)
    ct = job.counter
    if ct:
        color = pal()["solid_top"] if ct.kind == "solid" else pal()["laminate_top"]
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
    s, _words = _scale(wall + 1, top, bw - 1.6, bh - 1.25)
    _heading(svg, bx, by + 0.2, "END VIEW")
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


def iso_view(svg: Svg, job: Job, box, phi_deg: float = 32.0, tilt: float = 0.55,
             ground: bool = True, dim_text: str | None = None, heading: bool = True,
             dims: bool = True, floor_fill: str = "#eef0f2", wall_fill: str = "#f6f7f8") -> None:
    """Shaded 3D view from the front right, above. Boxes painted far to near."""
    bx, by, bw, bh = box
    if heading:
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
        poly([(x0, -14, z0), (x1, -14, z0), (x1, wall, z0), (x0, wall, z0)], floor_fill)
    poly([(x0, wall, z0), (x1, wall, z0), (x1, wall, top), (x0, wall, top)], wall_fill)

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

    for i in order:
        b = boxes[i]
        x, y, z = b.pos
        X1, Y1, Z1 = x + b.size[0], y + b.size[1], z + b.size[2]
        base = FILL if b.material == "filler" else _color(b)
        edge = "none" if "pull" in b.material else _edge(b, "#5d6770")
        sw = 0.0 if "pull" in b.material else 0.004
        poly([(x, y, Z1), (X1, y, Z1), (X1, Y1, Z1), (x, Y1, Z1)], _shade(base, 1.03), edge, sw)  # top
        poly([(X1, y, z), (X1, Y1, z), (X1, Y1, Z1), (X1, y, Z1)], _shade(base, 0.82), edge, sw)  # right
        poly([(x, y, z), (X1, y, z), (X1, y, Z1), (x, y, Z1)], _shade(base, 0.94), edge, sw)      # front

    span_b = job.run_span("base") or job.run_span("upper")
    if span_b and dims:
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
    svg.text(bx, by + 0.15, "CABINETS", size=0.12, weight="bold", fill=INK)
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
    room = bh - 0.34
    if len(rows) * 0.125 <= room and bw >= 5.3:
        depth_x = bw - 0.85
        height_x = depth_x - 0.75
        width_x = height_x - 0.8
        cols = [("Tag", 0.0), ("Style", 0.42), ("Width", width_x), ("Height", height_x), ("Depth", depth_x)]
        y = by + 0.32
        for name, dx in cols:
            svg.text(bx + dx, y, name, size=0.08, weight="bold", fill=SOFT)
        svg.line(bx, y + 0.04, bx + bw, y + 0.04, stroke="#c9ced4", sw=0.005)
        line_h = min(0.15, room / max(1, len(rows)))
        size = 0.10 if line_h >= 0.13 else 0.09
        for row in rows:
            y += line_h
            for (name, dx), val in zip(cols, row):
                svg.text(bx + dx, y, val, size=size, fill=INK, weight="bold" if name == "Tag" else "normal")
        return
    # a long job: two columns, the size as W x H x D, the style without its row word
    half = math.ceil(len(rows) / 2)
    line_h = min(0.15, room / max(1, half))
    size = min(0.10, max(0.085, line_h * 0.7))
    colw = bw / 2
    for k in range(2):
        x0 = bx + k * colw
        y = by + 0.32
        for name, dx in (("Tag", 0.0), ("Style", 0.38), ("W x H x D", max(0.9, colw - 1.25))):
            svg.text(x0 + dx, y, name, size=0.08, weight="bold", fill=SOFT)
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


def _fit(text: str, size: float, width: float) -> str:
    """Trim text that would run past `width` (DejaVu Sans averages ~0.56 em a glyph)."""
    room = max(3, int(width / (size * 0.56)))
    return text if len(text) <= room else text[:room - 1].rstrip() + "\u2026"


# Identity block, bottom right. The 44d9aa1 block was 5.2 in wide and a third
# of the sheet tall (19.1 sq in). This one is half that width and about a
# quarter of that area: 2.6 x 1.83 in.
BLOCK_W = 2.6
BLOCK_H = 1.83
# Cabinets table sits immediately left of that block, same bottom edge.
SCHED_W = 5.85
SCHED_GAP = 0.12


def sheet_zones() -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """(upper full width, lower left of the identity block)."""
    ux, uy = M + 0.06, M + 0.08
    uw = PAGE_W - 2 * M - 0.12
    uh = PAGE_H - M - BLOCK_H - 0.08 - uy
    lx = ux
    ly = PAGE_H - M - BLOCK_H + 0.04
    lw = PAGE_W - M - BLOCK_W - 0.1 - lx
    lh = PAGE_H - M - 0.04 - ly
    return (ux, uy, uw, uh), (lx, ly, lw, max(lh, 0.5))


def _fit_line(text: str, width: float, max_size: float = 0.16, min_size: float = 0.085) -> tuple[str, float]:
    """One line. Shrink the type until it fits, then ellipsize. The line never wraps."""
    size = max_size
    while size > min_size + 1e-9 and len(text) * size * 0.56 > width:
        size = round(size - 0.005, 3)
    if len(text) * size * 0.56 > width:
        text = _fit(text, size, width)
    return text, size


def _identity_block(svg: Svg, job: Job, date: str, drawing: str, page: str,
                    cabinets: str | None, scale: str | None = None) -> None:
    """Small title block. Type stays at a readable size; the box is the part that shrank."""
    from . import branding as br
    x = PAGE_W - M - BLOCK_W
    y = PAGE_H - M - BLOCK_H
    w, h = BLOCK_W, BLOCK_H
    pad = 0.07
    svg.rect(x, y, w, h, fill="#ffffff", stroke=br.RULE, sw=0.008)
    svg.line(x, y, x + w, y, stroke=br.NAVY, sw=0.022)
    logo_h = 0.22
    logo_w = logo_h * 2860 / 960
    svg.group(br.logo_svg(x + w - pad - logo_w, y + 0.04, logo_h))
    inner = w - 2 * pad - logo_w - 0.06
    draw, draw_size = _fit_line(drawing, inner, max_size=0.11, min_size=0.08)
    svg.text(x + pad, y + 0.17, draw, size=draw_size, weight="bold", fill=br.INK)
    st = job.settings or {}
    raw = (job.name or "").strip()
    if raw.lower() == "cabinet group":
        raw = ""
    title = raw + (f"  \u00b7  No. {st['job_no']}" if st.get("job_no") else "")
    title = title.strip(" \u00b7")
    if title:
        shown, size = _fit_line(title, w - 2 * pad, max_size=0.08, min_size=0.065)
        svg.text(x + pad, y + 0.34, shown, size=size, fill=br.INK)
    nb, nu = len(job.bases), len(job.uppers)
    sheet = page.replace("Page ", "") if page else "1 of 1"
    kind = "none"
    if job.counter:
        kind = "laminate" if job.counter.kind == "laminate" else "solid surface"
    facts = [
        ("CLIENT", st.get("client") or "\u2014"),
        ("DATE", date),
        ("REV", st.get("rev") or "\u2014"),
        ("SHEET", sheet),
        ("SCALE", scale or "per view"),
        ("QTY", cabinets or f"{nb + nu} ({nb} base, {nu} upper)"),
        ("COUNTER", kind),
    ]
    col_w = (w - 2 * pad) / 2
    for i, (label, value) in enumerate(facts):
        col, row = i % 2, i // 2
        xx = x + pad + col * col_w
        yy = y + 0.52 + row * 0.18
        svg.text(xx, yy, label, size=0.048, fill=br.SOFT)
        svg.text(xx + 0.34, yy, _fit(str(value), 0.072, col_w - 0.36), size=0.072,
                 weight="bold", fill=br.INK)
    svg.text(x + pad, y + h - 0.32, br.COMPANY, size=0.065, weight="bold", fill=br.NAVY)
    svg.text(x + pad, y + h - 0.20, br.STREET, size=0.055, fill=br.SOFT)
    svg.text(x + pad, y + h - 0.09, f"{br.CITY}  {br.PHONE}", size=0.055, fill=br.SOFT)


def begin_sheet(svg: Svg, job: Job, date: str, drawing: str, page: str = "",
                cabinets: str | None = None, scale: str | None = None):
    """Border and the bottom-right block. Returns (upper, lower_left) rectangles."""
    svg.rect(M / 2, M / 2, PAGE_W - M, PAGE_H - M, fill="none", stroke=INK, sw=0.014)
    _identity_block(svg, job, date, drawing, page, cabinets, scale)
    return sheet_zones()


def title_block(svg: Svg, job: Job, box, date: str, drawing: str = "Carpenter 2D",
                cabinets: str | None = None, page: str = "", scale: str | None = None) -> None:
    """The bottom-right block. `box` is ignored so every sheet matches."""
    _identity_block(svg, job, date, drawing, page, cabinets, scale)


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
        out.append(f"recessed toe kick, {fmt_in(p.toe_kick_h)} high, "
                   f"{fmt_in(p.toe_kick_recess)} back from the case front")
    out.append("fronts overlay the case; wire pulls" if p.doors or p.drawers
               else "case edges banded; no fronts")
    if str(p.style).startswith("upper"):
        out.append("hangs on the wall; top and bottom fit between full-height sides")
    else:
        out.append("countertop: see the countertop page" if has_counter else "no countertop in this job")
    return out


def _std_scale(fit: float) -> tuple[float, str]:
    s, words = fit, f"approx. 1:{round(1 / max(fit, 1e-6))}"
    for std, w in SCALES:
        if std <= fit + 1e-9:
            s, words = std, w
            break
    return s, words


def detail_page(job: Job, style: str, cabs: list, date: str, page: str) -> Svg:
    """One style, drawings only. The prose list and the width table are gone (Brook)."""
    rep = cabs[0]
    p = rep.params
    lone = _single(rep, job.name)
    boxes = lone.boxes
    W, H, D = p.width, p.height, p.depth + 0.75        # depth includes the fronts
    (ux, uy, uw, uh), (lx, ly, lw, lh) = sheet_zones()
    iso_w = min(4.8, uw * 0.30)
    left_span = (ly + lh) - uy
    ortho_h = left_span * 0.56
    front_col = (uw - iso_w) * 0.54
    side_col = (uw - iso_w) - front_col
    fit = min((ortho_h - 0.9) / max(H, 1.0), (front_col - 1.15) / max(W, 1.0),
              (side_col - 1.15) / max(D + 0.8, 1.0))
    s, words = _std_scale(fit)
    top_y = uy + ortho_h + 0.04
    top_h = (ly + lh) - top_y
    fit_top = min((top_h - 0.7) / max(D, 1.0), (lw - 1.15) / max(W, 1.0))
    st, top_words = _std_scale(fit_top)
    scale = words if words == top_words else f"{words}  ·  top {top_words}"
    svg = Svg(PAGE_W, PAGE_H)
    begin_sheet(svg, job, date, _style_name(style).upper(), page,
                cabinets=f"{len(cabs)} of this style", scale=scale)

    fx, fy = ux + 0.62, uy + 0.32
    _heading(svg, ux, uy + 0.18, "FRONT")
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

    sx0 = ux + front_col + 0.55
    _heading(svg, ux + front_col, uy + 0.18, "SIDE")
    SY = lambda y: sx0 + (y + 0.75) * s
    _ortho(svg, boxes, "side", SY, Z)
    _hdim(svg, SY(-0.75), SY(p.depth), Z(0) + 0.35, f"D = {fmt_in(D)}", size=0.13, ext_to=Z(0) + 0.03)
    if p.has_toe_kick and p.toe_kick_recess > 0:
        _hdim(svg, SY(-p.toe_kick_recess), SY(0), Z(0) + 0.62,
              f"kick {fmt_in(p.toe_kick_recess)}", size=0.11, ext_to=Z(0) + 0.03)
    _vdim(svg, SY(p.depth) + 0.35, Z(0), Z(H), fmt_in(H), size=0.12, ext_to=SY(p.depth) + 0.03)

    iso_view(svg, lone, (ux + uw - iso_w, uy, iso_w, ortho_h),
             ground=not str(p.style).startswith("upper"), dim_text=f"W = {fmt_in(W)}")

    _heading(svg, lx, top_y + 0.16, "TOP")
    tx, ty0 = lx + 0.62, top_y + 0.36
    XT = lambda x: tx + x * st
    TY = lambda y: ty0 + (p.depth - y) * st
    _ortho(svg, boxes, "top", XT, TY)
    _hdim(svg, XT(0), XT(W), TY(-0.75) + 0.32, f"W = {fmt_in(W)}", size=0.12, ext_to=TY(-0.75) + 0.03)
    _vdim(svg, XT(W) + 0.32, TY(-0.75), TY(p.depth), fmt_in(D), size=0.11, ext_to=XT(W) + 0.03)
    return svg


def _counter_color(ct) -> str:
    """The countertop colour. Splashes are the same piece of material, so they use it too."""
    return pal()["solid_top"] if ct.kind == "solid" else pal()["laminate_top"]


def _show_fill(ct, box) -> str:
    """Finished faces, including the splashes, are the countertop colour.
    Build-up is a step darker so the strip reads against the top."""
    color = _counter_color(ct)
    if "Build-up" in box.name:
        return _shade(color, 0.84)
    return color


def _case_span(job: Job) -> tuple[float, float]:
    bases = job.bases
    return min(c.x for c in bases), max(c.x + c.params.width for c in bases)


def _counter_front(svg: Svg, job: Job, ct, box) -> None:
    """Front elevation of the countertop alone: the edge, the splash, the length."""
    from .counter import SPLASH_H
    bx, by, bw, bh = box
    top = ct.top_z + SPLASH_H
    height = top - ct.z0
    s, _words = _scale(ct.length, height, bw - 1.6, bh - 1.05)
    _heading(svg, bx, by + 0.16, "FRONT VIEW")
    ox = bx + 0.1 + max(0.0, (bw - 1.6 - ct.length * s) / 2)
    top_y = by + 0.40
    X = lambda x: ox + (x - ct.x0) * s
    Z = lambda z: top_y + (top - z) * s
    for b in sorted(ct.boxes, key=lambda b: -b.pos[1]):
        x, z, dx, dz = b.pos[0], b.pos[2], b.size[0], b.size[2]
        svg.rect(X(x), Z(z + dz), max(dx * s, 0.004), max(dz * s, 0.004),
                 fill=_show_fill(ct, b), stroke=INK, sw=0.006)
    _hdim(svg, X(ct.x0), X(ct.x1), Z(ct.z0) + 0.22, ft_in(ct.length), size=0.11)
    xr = X(ct.x1) + 0.28
    _vdim(svg, xr, Z(ct.z0), Z(ct.top_z), fmt_in(EDGE_T), size=0.1)
    _vdim(svg, xr + 0.46, Z(ct.top_z), Z(top), '4" splash', size=0.1)
    case0, case1 = _case_span(job)
    y_oh = Z(ct.z0) + 0.48
    if case0 - ct.x0 > 0.2:
        _hdim(svg, X(ct.x0), X(case0), y_oh, fmt_in(case0 - ct.x0) + " past case", size=0.09)
    if ct.x1 - case1 > 0.2:
        _hdim(svg, X(case1), X(ct.x1), y_oh, fmt_in(ct.x1 - case1) + " past case", size=0.09)


def _counter_plan(svg: Svg, job: Job, ct, box) -> None:
    """Top view: the deck, the splashes in the counter colour, the overhangs."""
    bx, by, bw, bh = box
    s, _words = _scale(ct.length, ct.depth, bw - 1.4, bh - 1.2)
    _heading(svg, bx, by + 0.16, "TOP VIEW")
    ox = bx + 0.58 + max(0.0, (bw - 1.4 - ct.length * s) / 2)
    oy = by + 0.42
    X = lambda x: ox + (x - ct.x0) * s
    Y = lambda y: oy + (ct.y_back - y) * s          # wall at the top of the view
    color = _counter_color(ct)
    svg.rect(X(ct.x0), Y(ct.y_back), ct.length * s, ct.depth * s, fill=color, stroke=INK, sw=0.012)
    _wall_band(svg, X(ct.x0) - 0.1, Y(ct.y_back) - 0.12, ct.length * s + 0.2, 0.12)
    svg.line(X(ct.x0) - 0.1, Y(ct.y_back), X(ct.x1) + 0.1, Y(ct.y_back), stroke=INK, sw=0.01)
    st = ct.splash_thk
    svg.rect(X(ct.x0), Y(ct.y_back), ct.length * s, max(st * s, 0.05), fill=color, stroke=INK, sw=0.008)
    mid = (ct.x0 + ct.x1) / 2
    svg.text(X(mid), Y(ct.y_back - ct.depth * 0.58), "countertop", size=0.11, anchor="middle", fill=DIM)
    svg.text(X(mid), Y(ct.y_back - 1.6), "backsplash", size=0.09, anchor="middle", fill=DIM)
    for on, x in ((ct.splash_left, ct.x0), (ct.splash_right, ct.x1 - st)):
        if on:
            svg.rect(X(x), Y(ct.y_back), max(st * s, 0.045), ct.depth * s, fill=color, stroke=INK, sw=0.008)
            svg.text(X(x + st / 2), Y(ct.y_front + ct.depth * 0.35), "side splash", size=0.08,
                     anchor="middle", fill=DIM, rotate=-90)
    for cab in job.bases[1:]:
        svg.line(X(cab.x), Y(ct.y_back), X(cab.x), Y(ct.y_front), stroke=SOFT, sw=0.005, dash="0.04,0.03")
    _hdim(svg, X(ct.x0), X(ct.x1), Y(ct.y_front) + 0.26, ft_in(ct.length), size=0.11,
          ext_to=Y(ct.y_front) + 0.02)
    _vdim(svg, X(ct.x0) - 0.28, Y(ct.y_back), Y(ct.y_front), fmt_in(ct.depth), size=0.1)
    oh = -ct.y_front
    if oh > 0.05:
        _vdim(svg, X(ct.x1) + 0.3, Y(0.0), Y(ct.y_front), fmt_in(oh) + " overhang", size=0.09)


def _counter_side(svg: Svg, ct, box) -> None:
    """Section at mid-length, front on the left. Build-up strips are hatched."""
    from .counter import SPLASH_H
    bx, by, bw, bh = box
    height = (ct.top_z + SPLASH_H) - ct.z0
    s, _words = _scale(ct.depth + 0.4, height, bw - 1.5, bh - 1.35)
    _heading(svg, bx, by + 0.16, "SIDE VIEW")
    ox = bx + 0.62
    top_y = by + 0.42
    X = lambda y: ox + (y - ct.y_front) * s
    Z = lambda z: top_y + ((ct.top_z + SPLASH_H) - z) * s
    xs = (ct.x0 + ct.x1) / 2
    for b in sorted(ct.boxes, key=lambda b: b.pos[0]):
        if not (b.pos[0] - 1e-6 <= xs <= b.pos[0] + b.size[0] + 1e-6):
            continue
        y, z, dy, dz = b.pos[1], b.pos[2], b.size[1], b.size[2]
        svg.rect(X(y), Z(z + dz), dy * s, dz * s, fill=_show_fill(ct, b), stroke=INK, sw=0.01)
        if "Build-up" in b.name:
            hatch(svg, X(y), Z(z + dz), dy * s, dz * s, spacing=0.05, sw=0.004, stroke=SOFT)
    wall_x = X(ct.y_back)
    svg.line(wall_x, Z(ct.z0) + 0.15, wall_x, Z(ct.top_z + SPLASH_H), stroke=INK, sw=0.012)
    _wall_band(svg, wall_x, Z(ct.top_z + SPLASH_H), 0.12, (height * s) + 0.15)
    _hdim(svg, X(ct.y_front), X(ct.y_back), Z(ct.z0) + 0.26, fmt_in(ct.depth) + " deep", size=0.1)
    oh = -ct.y_front
    if oh > 0.05:
        _hdim(svg, X(ct.y_front), X(0.0), Z(ct.z0) + 0.52, fmt_in(oh) + " overhang", size=0.09)
    _vdim(svg, X(ct.y_front) - 0.28, Z(ct.z0), Z(ct.top_z), fmt_in(EDGE_T), size=0.09)
    _vdim(svg, X(ct.y_back) + 0.34, Z(ct.top_z), Z(ct.top_z + SPLASH_H), '4" splash', size=0.09)
    front = next((b for b in ct.boxes if "Build-up, front" in b.name), None)
    if front:
        y0 = front.pos[1]
        _hdim(svg, X(y0), X(y0 + front.size[1]), Z(ct.z0) + 0.78, '4" build-up', size=0.09)


def _underside(svg: Svg, job: Job, ct, x: float, y: float, w: float, h: float) -> None:
    """Where the build-up strips sit, seen from below. Cabinet joints are marked."""
    svg.text(x, y, "BUILD-UP, FROM BELOW", size=0.13, weight="bold", fill=INK)
    sp = min((w - 0.1) / max(ct.length, 1.0), (h - 0.48) / max(ct.depth, 1.0))
    PX = lambda px: x + (px - ct.x0) * sp
    PY = lambda py: y + 0.2 + (py - ct.y_front) * sp
    svg.rect(PX(ct.x0), PY(ct.y_front), ct.length * sp, ct.depth * sp,
             fill="#ffffff", stroke=INK, sw=0.01)
    tone = _shade(_counter_color(ct), 0.86)
    for b in ct.boxes:
        if "Build-up" not in b.name:
            continue
        svg.rect(PX(b.pos[0]), PY(b.pos[1]), max(b.size[0] * sp, 0.01), max(b.size[1] * sp, 0.01),
                 fill=tone, stroke=INK, sw=0.006)
    for cab in job.bases[1:]:
        svg.line(PX(cab.x), PY(ct.y_front), PX(cab.x), PY(ct.y_back), stroke="#b03a2e",
                 sw=0.008, dash="0.04,0.03")


def _counter_front_words(ct, bw: float, bh: float) -> str:
    from .counter import SPLASH_H
    height = (ct.top_z + SPLASH_H) - ct.z0
    _s, words = _scale(ct.length, height, bw - 1.6, bh - 1.05)
    return words


def counter_page(job: Job, date: str, page: str) -> Svg:
    """Countertop sheet: front, top, side, and the build-up drawing. No prose."""
    ct = job.counter
    svg = Svg(PAGE_W, PAGE_H)
    (cx, cy, cw, ch), (lx, ly, lw, lh) = sheet_zones()
    front_h = 2.2
    under_extra = 1.7
    under_y = ly - under_extra
    begin_sheet(svg, job, date, "Countertop 2D", page,
                scale=_counter_front_words(ct, cw, front_h))
    rest_y = cy + front_h + 0.06
    rest_h = under_y - 0.06 - rest_y
    side_w = min(6.2, cw * 0.38)
    left_w = cw - side_w - 0.1
    _counter_front(svg, job, ct, (cx, cy, cw, front_h))
    _counter_plan(svg, job, ct, (cx, rest_y, left_w, rest_h))
    _counter_side(svg, ct, (cx + left_w + 0.1, rest_y, side_w, rest_h))
    _underside(svg, job, ct, lx, under_y, lw, (ly + lh) - under_y)
    return svg


def render_pages(job: Job, date: str | None = None) -> list[Svg]:
    with palette_for(job):
        return _render_pages(job, date)


def _render_pages(job: Job, date: str | None = None) -> list[Svg]:
    date = date or _dt.date.today().strftime("%B %-d, %Y")
    groups = style_groups(job)
    extra = 1 if job.counter else 0
    total = 1 + extra + len(groups)
    pages = [_render(job, date, page=f"1 of {total}")]
    if job.counter:
        pages.append(counter_page(job, date, f"2 of {total}"))
    for i, (style, cabs) in enumerate(groups, start=2 + extra):
        pages.append(detail_page(job, style, cabs, date, f"{i} of {total}"))
    return pages


def client_notes(job: Job, limit: int = 5) -> list[tuple[str, str]]:
    """The few notes that apply to this job, for the client (cabgen.notes)."""
    from .finishes import summary
    from .notes import facts_from_job, select
    fin = summary(job.settings or {})
    return fin + select(facts_from_job(job), "client")[:max(2, limit - len(fin))]


def notes_block(svg: Svg, notes, x: float, y: float, width: float = 5.0) -> None:
    if not notes:
        return
    from .branding import NAVY
    svg.text(x, y, "NOTES", size=0.1, weight="bold", fill=NAVY)
    yy = y + 0.18
    body_w = max(1.2, width - 0.95)
    for title, text in notes:
        svg.text(x, yy, _fit(title, 0.09, 0.9), size=0.09, weight="bold", fill=INK)
        words, line = text.split(), []
        for word in words:
            trial = " ".join(line + [word])
            if len(trial) * 0.085 * 0.56 > body_w and line:
                svg.text(x + 0.95, yy, " ".join(line), size=0.085, fill=DIM)
                yy += 0.13
                line = [word]
            else:
                line.append(word)
        if line:
            svg.text(x + 0.95, yy, " ".join(line), size=0.085, fill=DIM)
        yy += 0.16


def render(job: Job, date: str | None = None, page: str = "") -> Svg:
    """Page 1: the whole kitchen."""
    with palette_for(job):
        return _render(job, date, page)


def _render(job: Job, date: str | None = None, page: str = "") -> Svg:
    """Drawings above and left of a short bottom-right band: cabinets table, then the block."""
    date = date or _dt.date.today().strftime("%B %-d, %Y")
    svg = Svg(PAGE_W, PAGE_H)
    cx, cy = M + 0.06, M + 0.08
    block_x = PAGE_W - M - BLOCK_W
    block_y = PAGE_H - M - BLOCK_H
    sched_x = block_x - SCHED_GAP - SCHED_W
    left_w = sched_x - 0.10 - cx
    left_h = (PAGE_H - M - 0.04) - cy
    elev_h = left_h * 0.62
    begin_sheet(svg, job, date, "Carpenter 2D", page,
                scale=elevation_scale_words(job, left_w, elev_h))
    front_elevation(svg, job, (cx, cy, left_w, elev_h))
    plan_view(svg, job, (cx, cy + elev_h + 0.06, left_w, left_h - elev_h - 0.06))
    rx = sched_x
    rw = PAGE_W - M - 0.06 - rx
    rh = block_y - 0.08 - cy
    iso_view(svg, job, (rx, cy, rw, rh * 0.55))
    end_view(svg, job, (rx, cy + rh * 0.58, rw, rh * 0.40))
    schedule(svg, job, (sched_x, block_y, SCHED_W, BLOCK_H))
    return svg


def write_client_sheet(job: Job, out_dir: Path, stem: str = "client-sheet",
                       png: bool = True, date: str | None = None) -> dict:
    """Carpenter 2D PDF. Page 1 the kitchen, then the countertop page, then one page per style.
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


def render_counter(job: Job, date: str | None = None) -> Svg:
    """The countertop sheet by itself. Same drawing as its page in the Carpenter 2D PDF."""
    date = date or _dt.date.today().strftime("%B %-d, %Y")
    if job.counter is None:
        svg = Svg(PAGE_W, PAGE_H)
        begin_sheet(svg, job, date, "Countertop 2D", "1 of 1")
        svg.text(M + 0.2, M + 0.45, "No countertop in this job.", size=0.16, fill=INK)
        return svg
    with palette_for(job):
        return counter_page(job, date, "1 of 1")


def write_counter_sheet(job: Job, out_dir: Path, stem: str = "counter-2d",
                        png: bool = False, date: str | None = None) -> dict:
    """One 11x17 page: the countertop only, laminate or solid surface."""
    out_dir.mkdir(parents=True, exist_ok=True)
    page = render_counter(job, date)
    svg_path = out_dir / f"{stem}.svg"
    page.write(str(svg_path))
    out = {"svg": svg_path, "pages": 1}
    rsvg = shutil.which("rsvg-convert")
    if not rsvg:
        raise RuntimeError("rsvg-convert is not installed; it turns the page into a PDF")
    pdf = out_dir / f"{stem}.pdf"
    subprocess.run([rsvg, "-f", "pdf", "-o", str(pdf), str(svg_path)], check=True,
                   capture_output=True)
    out["pdf"] = pdf
    if png:
        png_path = svg_path.with_suffix(".png")
        subprocess.run([rsvg, "-f", "png", "-d", "110", "-p", "110", "-b", "white",
                        "-o", str(png_path), str(svg_path)], check=True, capture_output=True)
        out["png"] = png_path
    return out
