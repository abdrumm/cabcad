"""11x17 landscape shop drawing: front elevation, side elevation, cut list,
notes and title block.

The drawing is what the carpenter works from, so it carries the carpentry
information: finished dimensions, panel sizes, edge banding, laminate faces,
and the assumptions that still need confirming.
"""

from __future__ import annotations

import datetime
from typing import Optional

from .nesting import Sheet
from .params import Params
from .parts import Layout, Part
from .svg import Svg, hatch
from .units import fmt_in

PAGE_W = 17.0
PAGE_H = 11.0
MARGIN = 0.4

INK = "#111111"
HAIR = "#555555"
FILL_CASE = "none"


# --------------------------------------------------------------------------
# dimension helpers
# --------------------------------------------------------------------------

def _arrow(svg: Svg, x: float, y: float, dx: float, dy: float, size: float = 0.06) -> None:
    """Filled arrow head pointing along (dx, dy)."""
    import math

    ang = math.atan2(dy, dx)
    bx, by = x - dx * size, y - dy * size
    px, py = -dy * size * 0.35, dx * size * 0.35
    svg.poly([(x, y), (bx + px, by + py), (bx - px, by - py)], fill=INK, stroke="none")


def dim_h(svg: Svg, x1: float, x2: float, y: float, label: str,
          size: float = 0.085, ext: float = 0.12, above: bool = True) -> None:
    """Horizontal dimension between x1 and x2 on the line y."""
    if abs(x2 - x1) < 1e-6:
        return
    svg.line(x1, y, x2, y, stroke=INK, sw=0.008)
    _arrow(svg, x1, y, 1, 0)
    _arrow(svg, x2, y, -1, 0)
    ty = y - 0.035 if above else y + size + 0.03
    svg.text((x1 + x2) / 2, ty, label, size=size, anchor="middle")


def dim_v(svg: Svg, y1: float, y2: float, x: float, label: str,
          size: float = 0.085, ext: float = 0.12, left: bool = True) -> None:
    """Vertical dimension between y1 and y2 on the line x."""
    if abs(y2 - y1) < 1e-6:
        return
    svg.line(x, y1, x, y2, stroke=INK, sw=0.008)
    _arrow(svg, x, y1, 0, 1)
    _arrow(svg, x, y2, 0, -1)
    tx = x - 0.035 if left else x + 0.05
    svg.text(tx, (y1 + y2) / 2, label, size=size, anchor="middle", rotate=-90)


def leader(svg: Svg, x: float, y: float, tx: float, ty: float, label: str,
           size: float = 0.08, align: str = "start") -> None:
    svg.line(x, y, tx, ty, stroke=HAIR, sw=0.006)
    svg.circle(x, y, 0.018, fill=INK)
    svg.text(tx + (0.03 if align == "start" else -0.03), ty + 0.03, label,
             size=size, anchor=align)


# --------------------------------------------------------------------------
# elevations
# --------------------------------------------------------------------------

class _Transform:
    """Model inches -> page inches.

    x0 is the page x of model x_min, y0 is the page y of the floor (z = 0).
    """

    def __init__(self, x0: float, y0: float, scale: float, x_min: float):
        self.x0 = x0
        self.y0 = y0
        self.scale = scale
        self.x_min = x_min

    def x(self, model_x: float) -> float:
        return self.x0 + (model_x - self.x_min) * self.scale

    def y(self, model_z: float) -> float:
        return self.y0 - model_z * self.scale


def _front_elevation(svg: Svg, p: Params, layout: Layout, box: tuple[float, float, float, float]) -> None:
    """box = (x, y, w, h) of the drawing area in page inches."""
    bx, by, bw, bh = box
    svg.text(bx, by - 0.12, "FRONT ELEVATION", size=0.13, weight="bold")

    left_ext = p.side_extension(p.left_side, p.counter_overhang_left, "left")
    right_ext = p.side_extension(p.right_side, p.counter_overhang_right, "right")
    x_min = -left_ext
    x_max = p.width + right_ext
    model_w = x_max - x_min
    splash = p.backsplash_h if p.has_counter and (p.backsplash_back or p.backsplash_left) else 0.0
    model_h = p.height + splash

    dim_stack = 1.55          # room below the floor for the dimension rows
    scale = min((bw - 1.95) / model_w, (bh - dim_stack - 0.25) / model_h)
    t = _Transform(bx + 1.75, by + bh - dim_stack, scale, x_min)

    # --- floor ------------------------------------------------------------
    svg.line(t.x(x_min) - 0.3, t.y(0), t.x(x_max) + 0.3, t.y(0), stroke=INK, sw=0.014)
    for i in range(22):
        x = t.x(x_min) - 0.3 + i * 0.13
        svg.line(x, t.y(0), x - 0.07, t.y(0) + 0.07, stroke=HAIR, sw=0.005)

    # --- toe kick zone (hidden) ------------------------------------------
    if p.has_toe_kick:
        svg.rect(t.x(0), t.y(p.case_bottom_z), p.width * scale,
                 (p.case_bottom_z) * scale, stroke=HAIR, sw=0.006, dash="0.06 0.04")
        # toe kick plate (face of the toe kick) set back from the case front
        svg.line(t.x(0), t.y(p.case_bottom_z), t.x(p.width), t.y(p.case_bottom_z),
                 stroke=HAIR, sw=0.008)

    # --- case --------------------------------------------------------------
    svg.rect(t.x(0), t.y(p.case_top_z), p.width * scale, (p.case_top_z - p.case_bottom_z) * scale,
             stroke=INK, sw=0.012)
    # bottom plate (hidden behind the toe kick)
    svg.line(t.x(p.carcass_thk), t.y(p.case_bottom_z + p.carcass_thk),
             t.x(p.width - p.carcass_thk), t.y(p.case_bottom_z + p.carcass_thk),
             stroke=HAIR, sw=0.006, dash="0.06 0.04")
    # the flat rails show only as their 3/4" front edge, behind the gap
    for r_bot, r_top in layout.rails:
        svg.rect(t.x(p.carcass_thk), t.y(r_top), (p.width - 2 * p.carcass_thk) * scale,
                 (r_top - r_bot) * scale, fill="#f2f2f2", stroke=INK, sw=0.009)

    # sink base: the vertical front board, hidden behind the false front and the door tops
    if layout.sink_board:
        fb_bot, fb_top = layout.sink_board
        svg.rect(t.x(p.carcass_thk), t.y(fb_top), (p.width - 2 * p.carcass_thk) * scale,
                 (fb_top - fb_bot) * scale, stroke=HAIR, sw=0.006, dash="0.06 0.04")

    # --- countertop --------------------------------------------------------
    if p.has_counter:
        cy0, cy1 = t.y(p.case_top_z + p.counter_build), t.y(p.case_top_z)
        cw = (x_max - x_min) * scale
        svg.rect(t.x(x_min), cy0, cw, cy1 - cy0, fill="none", stroke=INK, sw=0.012)
        hatch(svg, t.x(x_min), cy0, cw, cy1 - cy0, spacing=0.07, sw=0.005, stroke="#8a8a8a")
        # left wall backsplash
        if p.backsplash_left:
            bs_h = p.backsplash_h * scale
            svg.rect(t.x(x_min), cy0 - bs_h, p.counter_thk * scale, bs_h,
                     fill="none", stroke=INK, sw=0.012)
            hatch(svg, t.x(x_min), cy0 - bs_h, p.counter_thk * scale, bs_h,
                  spacing=0.05, sw=0.005, stroke="#8a8a8a")

    # --- fronts ------------------------------------------------------------
    front_h = p.front_width
    dx0 = p.edge_reveal
    for b_bot, b_top in layout.drawer_bands:
        svg.rect(t.x(dx0), t.y(b_top), front_h * scale, (b_top - b_bot) * scale,
                 fill="none", stroke=INK, sw=0.012)
    if layout.door_heights:
        dw = p.door_width
        door_bot, door_top = layout.door_zone()
        for i in range(p.doors):
            x = dx0 + i * (dw + p.door_gap)
            svg.rect(t.x(x), t.y(door_top), dw * scale, (door_top - door_bot) * scale,
                     fill="none", stroke=INK, sw=0.012)

    # --- dimensions --------------------------------------------------------
    dim_y = t.y(0) + 0.45
    if p.has_counter:
        dim_h(svg, t.x(x_min), t.x(x_max), dim_y, f'COUNTERTOP {fmt_in(p.counter_width)}')
    dim_h(svg, t.x(0), t.x(p.width), dim_y + 0.34, f'CASE {fmt_in(p.width)}')
    if layout.door_heights:
        dim_h(svg, t.x(dx0), t.x(dx0 + p.door_width), dim_y + 0.68,
              f'DOOR {fmt_in(p.door_width)}', size=0.075)
    if layout.drawer_heights:
        dim_h(svg, t.x(dx0), t.x(dx0 + p.front_width), dim_y + 0.68,
              f'DRAWER FRONT {fmt_in(p.front_width)}', size=0.075)

    dim_x = t.x(x_min) - 0.55
    dim_v(svg, t.y(0), t.y(p.height), dim_x, f'OVERALL {fmt_in(p.height)}')
    if p.has_toe_kick:
        dim_v(svg, t.y(0), t.y(p.case_bottom_z), dim_x - 0.42, f'TOE KICK {fmt_in(p.toe_kick_h)}',
              size=0.075)
    if p.has_counter:
        dim_v(svg, t.y(p.case_top_z), t.y(p.case_top_z + p.counter_build), dim_x - 0.42,
              f'COUNTER {fmt_in(p.counter_build)}', size=0.075)
    if layout.door_heights:
        door_bot, door_top = layout.door_zone()
        dim_v(svg, t.y(door_bot), t.y(door_top), dim_x - 0.84,
              f'DOOR {fmt_in(layout.door_heights[0])}', size=0.075)
    if layout.drawer_heights:
        dz_bot, dz_top = layout.drawer_zone()
        label = "DRAWER" if len(layout.drawer_heights) == 1 else "DRAWER FRONTS"
        dim_v(svg, t.y(dz_bot), t.y(dz_top), dim_x - 0.84,
              f'{label} {fmt_in(layout.drawer_heights[0])}', size=0.075)

    # --- notes on the elevation (numbered bubbles -> key column) -----------
    keys: list[tuple[int, str]] = []
    bubble_x = t.x(x_max) + 0.22
    used_y: list[float] = []

    def bubble(model_x: float, model_z: float, text: str) -> None:
        n = len(keys) + 1
        keys.append((n, text))
        ty = t.y(model_z)
        while any(abs(ty - u) < 0.22 for u in used_y):
            ty += 0.23
        used_y.append(ty)
        svg.line(t.x(model_x), t.y(model_z), bubble_x - 0.09, ty, stroke=HAIR, sw=0.006)
        svg.circle(bubble_x, ty, 0.085, fill="white", stroke=INK, sw=0.008)
        svg.text(bubble_x, ty + 0.03, str(n), size=0.085, anchor="middle")

    if p.has_counter:
        bubble(p.width - 0.3, p.case_top_z + p.counter_build * 0.5,
               '1/2" Corian deck, edge strips on the front and the reveal side, 1.5" edge')
    if p.has_toe_kick:
        bubble(p.width * 0.5, p.case_bottom_z * 0.5,
               f'Toe kick {fmt_in(p.toe_kick_h)} high, recessed {fmt_in(p.toe_kick_recess)}')
    if layout.drawer_heights:
        dz_bot, dz_top = layout.drawer_zone()
        bubble(0.4, dz_top - 0.4,
               'False front (no pull) on a vertical front board' if p.sink else
               'Drawer front: overlay on a 3/4" rail (face to edge)')
    if layout.door_heights:
        door_bot, door_top = layout.door_zone()
        bubble(p.edge_reveal + p.door_width * 0.5, door_top - 1.2,
               f'Doors: {fmt_in(p.door_overhang)} overlay on the gable, {fmt_in(p.edge_reveal)} reveal, {fmt_in(p.door_gap)} gap')
    if p.left_side == "wall":
        bubble(0.4, p.case_top_z - 0.3,
               'Left: wall side' + (f', {fmt_in(p.spacer_gap)} spacer' if p.has_filler else ', side splash'))
    if p.right_side == "open":
        bubble(p.width + right_ext * 0.5, p.case_top_z - 0.3,
               f'Right: open side, {fmt_in(p.counter_overhang_right)} counter overhang')
    if p.laminate and p.laminate_right_side:
        bubble(p.width - 0.05, p.case_bottom_z + 2.0,
               'Right gable: reveal face, laminate per waterfall order')

    svg.text(bx, by + bh + 0.02,
             f'Scale: drawn to fit, {1 / scale:.3f}" = 1"  |  dimensions govern',
             size=0.075, fill=HAIR)
    return keys


def _side_elevation(svg: Svg, p: Params, layout: Layout, box: tuple[float, float, float, float]) -> None:
    bx, by, bw, bh = box
    svg.text(bx, by - 0.12, "SIDE ELEVATION", size=0.13, weight="bold")

    case_d = p.depth
    gable_d = p.gable_depth
    front_ext = p.counter_front_overhang if p.has_counter else 0.0
    model_w = case_d + front_ext
    splash = p.backsplash_h if p.has_counter and p.backsplash_back else 0.0
    model_h = p.height + splash
    scale = min((bw - 1.15) / model_w, (bh - 1.35) / model_h)
    t = _Transform(bx + 0.55, by + bh - 0.95, scale, -front_ext)
    x_front = -front_ext
    x_back = case_d

    svg.line(t.x(x_front) - 0.25, t.y(0), t.x(x_back) + 0.25, t.y(0), stroke=INK, sw=0.014)

    # side panel: full height above the kick, notched below it
    if p.has_toe_kick and p.toe_kick_recess > 0:
        svg.rect(t.x(0), t.y(p.case_top_z), gable_d * scale,
                 (p.case_top_z - p.toe_kick_h) * scale, stroke=INK, sw=0.012)
        svg.rect(t.x(p.toe_kick_recess), t.y(p.toe_kick_h),
                 (gable_d - p.toe_kick_recess) * scale, p.toe_kick_h * scale,
                 stroke=INK, sw=0.012)
    else:
        svg.rect(t.x(0), t.y(p.case_top_z), gable_d * scale,
                 p.case_top_z * scale, stroke=INK, sw=0.012)
    if p.back_style == "applied":
        svg.rect(t.x(gable_d), t.y(p.case_top_z), p.back_thk * scale,
                 p.case_top_z * scale, stroke=INK, sw=0.01)
    svg.line(t.x(0), t.y(p.case_bottom_z + p.carcass_thk),
             t.x(gable_d), t.y(p.case_bottom_z + p.carcass_thk),
             stroke=HAIR, sw=0.006, dash="0.06 0.04")

    if p.has_counter:
        cy0, cy1 = t.y(p.case_top_z + p.counter_build), t.y(p.case_top_z)
        cw = model_w * scale
        svg.rect(t.x(x_front), cy0, cw, cy1 - cy0, fill="none", stroke=INK, sw=0.012)
        hatch(svg, t.x(x_front), cy0, cw, cy1 - cy0, spacing=0.07, sw=0.005, stroke="#8a8a8a")
        if p.backsplash_back:
            bs_h = p.backsplash_h * scale
            svg.rect(t.x(case_d - p.counter_thk), cy0 - bs_h, p.counter_thk * scale, bs_h,
                     fill="none", stroke=INK, sw=0.012)
            hatch(svg, t.x(case_d - p.counter_thk), cy0 - bs_h, p.counter_thk * scale, bs_h,
                  spacing=0.05, sw=0.005, stroke="#8a8a8a")
        # wall line at the back
        svg.line(t.x(case_d), t.y(0), t.x(case_d), t.y(model_h), stroke=HAIR, sw=0.02)

    dim_y = t.y(0) + 0.4
    if p.has_counter:
        dim_h(svg, t.x(x_front), t.x(case_d), dim_y, f'COUNTER {fmt_in(p.counter_depth)}')
    dim_h(svg, t.x(0), t.x(case_d), dim_y + 0.3, f'CASE DEPTH {fmt_in(p.depth)}', size=0.075)
    if p.has_toe_kick and p.toe_kick_recess > 0:
        # The recess is the case front back to the face of the toe kick, door not
        # included (Brook, 2026-11-02). Bases have no countertop, so it takes the
        # first free row; a counter cabinet pushes it down one.
        row = 0.9 if p.has_counter else 0.6
        dim_h(svg, t.x(0), t.x(p.toe_kick_recess), dim_y + row,
              f'TOE KICK {fmt_in(p.toe_kick_recess)}', size=0.075)
    if p.has_counter and front_ext > 0:
        dim_h(svg, t.x(x_front), t.x(0), dim_y + 0.6, f'{fmt_in(front_ext)}', size=0.075)
    dim_x = t.x(x_front) - 0.45
    dim_v(svg, t.y(0), t.y(p.height), dim_x, f'OVERALL {fmt_in(p.height)}', size=0.075)
    if p.has_counter:
        dim_v(svg, t.y(p.case_top_z), t.y(p.case_top_z + p.counter_build), dim_x - 0.4,
              f'{fmt_in(p.counter_build)}', size=0.07)
        if p.backsplash_back:
            dim_v(svg, t.y(p.case_top_z + p.counter_build),
                  t.y(p.case_top_z + p.counter_build + p.backsplash_h), dim_x - 0.8,
                  f'BS {fmt_in(p.backsplash_h)}', size=0.07)


# --------------------------------------------------------------------------
# cut list, notes, title block
# --------------------------------------------------------------------------

def _cutlist_table(svg: Svg, parts: list[Part], box: tuple[float, float, float, float],
                   start: int = 0, page: int = 1, pages: int = 1) -> int:
    """Draw the cut list; returns how many rows were drawn."""
    bx, by, bw, bh = box
    svg.text(bx, by - 0.12, "CUT LIST" if pages == 1 else f"CUT LIST - SHEET {page}",
             size=0.13, weight="bold")
    cols = [
        ("QTY", 0.4, "start"),
        ("PART", 2.35, "start"),
        ("WIDTH", 0.7, "end"),
        ("LENGTH", 0.75, "end"),
        ("THK", 0.5, "end"),
        ("MATERIAL", 1.1, "start"),
        ("EDGE BANDING", 3.1, "start"),
    ]
    xs = []
    x = bx
    for _, w, _a in cols:
        xs.append(x)
        x += w
    row_h = 0.155
    y = by + 0.18
    for i, (title, w, align) in enumerate(cols):
        svg.text(xs[i], y, title, size=0.075, weight="bold",
                 anchor=align if align != "start" else "start")
    svg.line(bx, y + 0.04, bx + sum(c[1] for c in cols), y + 0.04, stroke=INK, sw=0.007)
    y += 0.17
    max_rows = int((bh - 0.42) / row_h)
    drawn = 0
    for part in parts[start:]:
        if drawn >= max_rows:
            break
        values = [
            str(part.qty),
            part.name,
            fmt_in(part.width),
            fmt_in(part.length),
            fmt_in(part.thk),
            part.material,
            part.banding,
        ]
        for i, (title, w, align) in enumerate(cols):
            val = values[i]
            if align == "end":
                svg.text(xs[i] + w - 0.05, y, val, size=0.068, anchor="end")
            else:
                svg.text(xs[i], y, val, size=0.068)
        y += row_h
        drawn += 1
    svg.line(bx, y - 0.02, bx + sum(c[1] for c in cols), y - 0.02, stroke=HAIR, sw=0.005)
    if drawn < len(parts) - start:
        svg.text(bx, y + 0.09, "continued on the cut list sheet", size=0.07, fill=HAIR)
    return drawn


def _key_block(svg: Svg, keys: list[tuple[int, str]], box: tuple[float, float, float, float]) -> None:
    """Numbered key for the callouts on the elevation."""
    bx, by, bw, bh = box
    if not keys:
        return
    svg.text(bx, by - 0.12, "KEY", size=0.13, weight="bold")
    y = by + 0.08
    for n, text in keys:
        svg.circle(bx + 0.08, y - 0.03, 0.075, fill="white", stroke=INK, sw=0.007)
        svg.text(bx + 0.08, y, str(n), size=0.075, anchor="middle")
        # wrap the text next to the bubble
        words = text.split()
        line_words: list[str] = []
        max_chars = int((bw - 0.28) / 0.040)
        first = True
        while words:
            line_words = []
            while words:
                w = words[0]
                used = sum(len(x) + 1 for x in line_words) + len(w)
                if used > max_chars and line_words:
                    break
                line_words.append(words.pop(0))
            if first:
                svg.text(bx + 0.21, y, " ".join(line_words), size=0.068)
                first = False
            else:
                svg.text(bx + 0.21, y, " ".join(line_words), size=0.068)
            y += 0.095
        y += 0.06


def _notes_block(svg: Svg, p: Params, layout: Layout, parts: list[Part],
                 box: tuple[float, float, float, float]) -> None:
    bx, by, bw, bh = box
    svg.text(bx, by - 0.12, "NOTES / EDGE BANDING / LAMINATE", size=0.13, weight="bold")
    y = by + 0.1
    lines: list[tuple[str, str]] = []

    # condensed, only what applies to this cabinet (cabgen.notes, Brook Oct 30)
    from .notes import extra_checks, facts_from_params, select
    lines.extend(select(facts_from_params(p), "shop"))
    lam = [pt.name for pt in parts if pt.laminate]
    if lam:
        lines.append(("LAMINATE ON", ", ".join(lam) + "."))
    for note in layout.notes:
        lines.append(("DRAWER", note))
    for a in extra_checks(layout.assumptions):
        lines.append(("CHECK", a))

    for title, text in lines:
        # wrap
        words = text.split()
        line_words: list[str] = []
        max_chars = int((bw - 0.95) / 0.043)
        for w in words:
            if sum(len(x) + 1 for x in line_words) + len(w) > max_chars and line_words:
                svg.text(bx, y, title + " - " + " ".join(line_words), size=0.072)
                y += 0.105
                line_words = []
                title = "        "
            line_words.append(w)
        if line_words:
            head = title if title.strip() == "" else title + " - "
            svg.text(bx, y, head + " ".join(line_words), size=0.072)
            y += 0.115
        y += 0.02


SHOP_BLOCK_H = round(PAGE_H / 3.0, 3)
SHOP_BLOCK_W = 5.2


def _shop_chrome(svg: Svg, p: Params, sheet: int = 1, sheets: int = 1):
    """Border and a bottom-right block. Returns (upper, lower_left)."""
    svg.rect(MARGIN / 2, MARGIN / 2, PAGE_W - MARGIN, PAGE_H - MARGIN,
             fill="none", stroke=INK, sw=0.014)
    x = PAGE_W - MARGIN - SHOP_BLOCK_W
    y = PAGE_H - MARGIN - SHOP_BLOCK_H
    svg.rect(x, y, SHOP_BLOCK_W, SHOP_BLOCK_H, fill="none", stroke=INK, sw=0.01)
    svg.line(x, y, x + SHOP_BLOCK_W, y, stroke=INK, sw=0.02)
    svg.text(x + 0.12, y + 0.28, "SHOP DRAWING", size=0.14, weight="bold")
    name = p.name
    size = 0.11
    room = SHOP_BLOCK_W - 0.24
    while size > 0.075 and len(name) * size * 0.56 > room:
        size -= 0.005
    shown = name if len(name) * size * 0.56 <= room else name[: max(8, int(room / (size * 0.56)) - 1)] + "…"
    svg.text(x + 0.12, y + 0.50, shown, size=size)
    rows = [
        ("CASE", f'{fmt_in(p.width)} x {fmt_in(p.depth)} x {fmt_in(p.height)}'),
        ("SHEET", f"{sheet} OF {sheets}"),
        ("DATE", datetime.date.today().isoformat()),
        ("KERF", fmt_in(p.kerf)),
        ("FRONTS", f'{p.doors} door, {p.drawers} drw'),
        ("COUNTER", "yes" if p.has_counter else "none"),
    ]
    yy = y + 0.78
    for i, (k, v) in enumerate(rows):
        col, row = i % 2, i // 2
        xx = x + 0.12 + col * (SHOP_BLOCK_W - 0.24) / 2
        svg.text(xx, yy + row * 0.42, k, size=0.055)
        svg.text(xx, yy + row * 0.42 + 0.14, v, size=0.08, weight="bold")
    ux, uy = MARGIN + 0.04, MARGIN + 0.08
    uw = PAGE_W - 2 * MARGIN - 0.1
    uh = y - uy - 0.08
    lx, ly = ux, y + 0.04
    lw = x - lx - 0.08
    lh = PAGE_H - MARGIN - ly - 0.02
    return (ux, uy, uw, uh), (lx, ly, lw, lh)


def _title_block(svg: Svg, p: Params, layout: Layout, box: tuple[float, float, float, float],
                 sheet: int = 1, sheets: int = 1) -> None:
    """Kept for callers. The sheet chrome draws the rail; this no longer paints a wide block."""
    _shop_chrome(svg, p, sheet, sheets)


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------

def shop_drawing(p: Params, parts: list[Part], layout: Layout) -> tuple[Svg, list[Part]]:
    """Sheet 1: elevations, key, notes, cut list, title block.

    Returns the drawing and any cut list rows that did not fit (they go on
    the cut list sheet).
    """
    svg = Svg(PAGE_W, PAGE_H)
    (cx, cy, cw, ch), (lx, ly, lw, lh) = _shop_chrome(svg, p, sheet=1, sheets=1)
    side_w = 4.4
    keys = _front_elevation(svg, p, layout, (cx, cy, cw - side_w - 0.12, ch))
    _side_elevation(svg, p, layout, (cx + cw - side_w, cy, side_w, ch * 0.46))
    _key_block(svg, keys, (cx + cw - side_w, cy + ch * 0.50, side_w * 0.46, ch * 0.48))
    _notes_block(svg, p, layout, parts, (cx + cw - side_w * 0.5, cy + ch * 0.50, side_w * 0.5, ch * 0.48))
    drawn = _cutlist_table(svg, parts, (lx, ly, lw, lh))
    sheets = 1 if len(parts) <= drawn else 2
    if sheets == 2:
        svg.text(PAGE_W - MARGIN - SHOP_BLOCK_W + 0.12, PAGE_H - MARGIN - 0.18,
                 "also sheet 2", size=0.06)
    return svg, parts[drawn:]


def cutlist_sheet(p: Params, parts: list[Part], page: int = 1, pages: int = 1) -> Svg:
    """Extra sheet when the cut list runs past sheet 1."""
    svg = Svg(PAGE_W, PAGE_H)
    (cx, cy, cw, ch), (lx, ly, lw, lh) = _shop_chrome(svg, p, sheet=page, sheets=pages)
    _cutlist_table(svg, parts, (cx, cy, max(cw, lw), ch), page=page, pages=pages)
    return svg


def nesting_drawing(sheets: list[Sheet], title: str, kerf: float = 0.1875,
                    sheet_w: float = 96.0, sheet_h: float = 48.0) -> Svg:
    """One sheet of stock per page, landscape, with the parts laid out."""
    svg = Svg(PAGE_W, PAGE_H)
    svg.rect(MARGIN / 2, MARGIN / 2, PAGE_W - MARGIN, PAGE_H - MARGIN,
             fill="none", stroke=INK, sw=0.014)
    svg.text(MARGIN + 0.1, MARGIN + 0.05, title.upper(), size=0.16, weight="bold")
    svg.text(PAGE_W - MARGIN - 0.1, MARGIN + 0.05,
             f'kerf {fmt_in(kerf)}  -  sheet {sheet_w:g}" x {sheet_h:g}"  -  grain along the length',
             size=0.1, anchor="end")

    if not sheets:
        svg.text(PAGE_W / 2, PAGE_H / 2, "nothing to nest", size=0.2, anchor="middle")
        return svg

    sh = sheets[0]
    area_w, area_h = PAGE_W - 2 * MARGIN - 0.4, PAGE_H - 2 * MARGIN - 1.1
    scale = min(area_w / sheet_w, area_h / sheet_h)
    ox = MARGIN + 0.2
    oy = MARGIN + 0.85

    def sx(x): return ox + x * scale
    def sy(y): return oy + y * scale

    svg.rect(sx(0), sy(0), sheet_w * scale, sheet_h * scale, fill="none", stroke=INK, sw=0.012)
    svg.text(sx(0), sy(0) - 0.08, "0", size=0.07, anchor="middle", fill=HAIR)
    svg.text(sx(sheet_w), sy(0) - 0.08, f'{sheet_w:g}"', size=0.07, anchor="middle", fill=HAIR)
    svg.text(sx(sheet_w) + 0.08, sy(sheet_h / 2), f'{sheet_h:g}"', size=0.07, fill=HAIR)

    for piece in sh.pieces:
        x, y = sx(piece.x), sy(piece.y)
        w, h = piece.w * scale, piece.h * scale
        svg.rect(x, y, w, h, fill="none", stroke=INK, sw=0.008)
        label = piece.label
        if w > 0.55 and h > 0.22:
            svg.text(x + w / 2, y + h / 2 - 0.02, label, size=0.075, anchor="middle")
            svg.text(x + w / 2, y + h / 2 + 0.11, f'{fmt_in(piece.w)} x {fmt_in(piece.h)}',
                     size=0.065, anchor="middle", fill=HAIR)
        elif w > 0.3:
            svg.text(x + w / 2, y + h / 2, fmt_in(piece.h), size=0.06, anchor="middle")

    ytxt = oy + sheet_h * scale + 0.28
    svg.text(ox, ytxt, f"SHEET {sh.index} of {len(sheets)}", size=0.11, weight="bold")
    svg.text(ox, ytxt + 0.17,
             f'Utilization {sh.utilization * 100:.0f}%   -   largest offcut {sh.offcut}',
             size=0.085)
    if len(sheets) > 1:
        svg.text(ox, ytxt + 0.34, "remaining sheets are identical in layout", size=0.08, fill=HAIR)
    return svg
