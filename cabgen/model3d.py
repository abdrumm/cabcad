"""3D placement of the cabinet: every part as a box in space.

Coordinates (inches):
    X = width, 0 at the left face of the case
    Y = depth, 0 at the case front, +Y toward the wall
    Z = height, 0 at the floor

Sizes and positions follow shop construction.
Stiles are flat boards. Top stile flush with top of sides; back stile flush with back.
Fronts cover half of each 3/4 inch edge and stay inside the case.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .params import (
    HINGE_CUP_DEPTH, HINGE_CUP_DIA, HINGE_CUP_EDGE, HINGE_FROM_END, Params, SINK_BACK_STILE_H,
    MICROWAVE_SHELF_CALLED_DEPTH,
    MICROWAVE_SHELF_CORNER_R,
    UPPER_PULL_CC, UPPER_PULL_EDGE_INSET, UPPER_PULL_FROM_BOTTOM, UPPER_PULL_HOLE_DIA,
)
from .parts import Layout, door_name, open_pin_rows, open_pin_y, open_shelf_z


@dataclass
class Box:
    name: str
    pos: tuple[float, float, float]
    size: tuple[float, float, float]
    material: str = ""
    join: str = ""        # union this box into the first box that shares the key
    # "" = a plain box. "qdisc:+x+y" = a rounded corner: the box is the R x R corner square
    # and the round is a quarter circle centred on its +x/+y (or -x / -y) corner. Omacad
    # gets a true cylinder there; the client views and AR get it as fine steps.
    shape: str = ""


@dataclass
class HoleSpec:
    """A drilled hole. normal points out of the material, origin is on the face."""

    diameter: float
    depth: float
    origin: tuple[float, float, float]
    normal: tuple[float, float, float]


@dataclass
class Model:
    boxes: list[Box] = field(default_factory=list)
    holes: list[HoleSpec] = field(default_factory=list)


def build_model(p: Params, layout: Layout) -> Model:
    """Return every solid and the holes drilled into them."""
    model = Model()
    t = p.carcass_thk
    bt = p.back_thk
    w = p.width
    w_in = p.width_in
    gable_d = p.gable_depth
    top = p.case_top_z
    bot = p.case_bottom_z
    stretch = p.stretcher_w

    def add(name: str, pos, size, material: str = "", join: str = "", shape: str = "") -> None:
        model.boxes.append(Box(
            name,
            tuple(round(v, 4) for v in pos),
            tuple(round(v, 4) for v in size),
            material,
            join,
            shape,
        ))

    def gable(name: str, x: float) -> None:
        mat = '3/4" melamine'
        if p.has_toe_kick and p.toe_kick_h > 0 and p.toe_kick_recess > 0:
            add(name, (x, 0, p.toe_kick_h),
                (t, gable_d, top - p.toe_kick_h), mat, join=name)
            # overlap the upper piece by 0.01 so the union is one solid
            add(name + " heel", (x, p.toe_kick_recess, 0),
                (t, gable_d - p.toe_kick_recess, p.toe_kick_h + 0.01), mat, join=name)
        else:
            add(name, (x, 0, 0), (t, gable_d, top), mat)

    gable("Gable L", 0)
    gable("Gable R", w - t)

    if p.is_microwave:
        # projects past the 12" box: 16" from the front face of the back, 2" R front
        # corners (Brook, Oct 27). Built as one joined solid: the body behind the round,
        # the front strip between the rounds, and the two round corners.
        R = MICROWAVE_SHELF_CORNER_R
        d = MICROWAVE_SHELF_CALLED_DEPTH
        yf = gable_d - d
        mat = '3/4" melamine'
        key = "Microwave shelf"
        add("Microwave shelf", (t, yf + R, bot), (w_in, d - R, t), mat, join=key)
        add("Microwave shelf heel", (t + R, yf, bot), (w_in - 2 * R, R, t), mat, join=key)
        add("Microwave shelf heel", (t, yf, bot), (R, R, t), mat, join=key, shape="qdisc:+x+y")
        add("Microwave shelf heel", (t + w_in - R, yf, bot), (R, R, t), mat, join=key,
            shape="qdisc:-x+y")
    else:
        add("Bottom plate", (t, 0, bot), (w_in, gable_d, t), '3/4" melamine')

    if p.back_style == "dado":
        add("Back panel", (t, gable_d - bt, bot), (w_in, bt, p.case_h - t), '1/2" melamine')
    else:
        add("Back panel", (0, gable_d, 0), (w, bt, top), '1/2" melamine')

    if str(p.style).startswith("upper"):
        # Uppers: sides run full height; the top is one piece between them (Brook, 2026-10-23).
        add("Top plate", (t, 0, top - t), (w_in, gable_d, t), '3/4" melamine')
        if p.is_microwave:
            add("Microwave divider", (t, 0, p.mw_divider_z), (w_in, gable_d, t), '3/4" melamine')
    elif p.sink and layout.sink_board:
        # sink base: a vertical board right behind the false front, and the back stile on edge
        fb_bot, fb_top = layout.sink_board
        add("Sink front board", (t, 0, fb_bot), (w_in, t, fb_top - fb_bot), '3/4" melamine')
        add("Top stile, back", (t, gable_d - t, top - SINK_BACK_STILE_H),
            (w_in, t, SINK_BACK_STILE_H), '3/4" melamine')
    else:
        add("Top stile, front", (t, 0, top - t), (w_in, stretch, t), '3/4" melamine')
        add("Top stile, back", (t, gable_d - stretch, top - t), (w_in, stretch, t),
            '3/4" melamine')

    for i, (r_bot, _r_top) in enumerate(layout.rails, start=1):
        add(f"Drawer stile {i}", (t, 0, r_bot), (w_in, stretch, t), '3/4" melamine')

    if p.has_toe_kick:
        add("Toe kick plate", (t, p.toe_kick_recess, 0), (w_in, t, p.toe_kick_h),
            '3/4" melamine')
        add("Toe kick stile, back", (t, gable_d - t, 0), (w_in, t, p.toe_kick_h),
            '3/4" melamine')
        if p.has_filler:
            on_left = p.spacer_side == "left" or (
                p.spacer_side != "right" and p.left_side == "wall"
            )
            side = -p.spacer_gap if on_left else w
            add("Spacer board", (side, 0, 0), (p.spacer_gap, t, p.toe_kick_h),
                '3/4" melamine')

    if p.has_shelf and bot < p.shelf_z < top - t:
        add("Shelf",
            (t + p.shelf_side_gap, p.shelf_setback, p.shelf_z),
            (w_in - 2 * p.shelf_side_gap, gable_d - p.shelf_setback, t),
            '3/4" melamine')
        _shelf_pins(model, p)

    for k, z in enumerate(open_shelf_z(p), start=1):
        add(f"Open shelf {k}",
            (t + p.shelf_side_gap, p.shelf_setback, z),
            (w_in - 2 * p.shelf_side_gap, gable_d - p.shelf_setback, t),
            '3/4" melamine')
    if p.open_shelves:
        for x, normal in ((t, (1.0, 0.0, 0.0)), (w - t, (-1.0, 0.0, 0.0))):
            for y in open_pin_y(p):
                for z in open_pin_rows(p):
                    model.holes.append(HoleSpec(p.shelf_pin_dia, p.shelf_pin_depth,
                                                (x, y, z), normal))

    if layout.door_heights:
        dw = p.door_width
        d_bot, d_top = layout.door_zone()
        for i in range(p.doors):
            x = p.edge_reveal + i * (dw + p.door_gap)
            label = door_name(p, i)
            if p.doors == 1:
                # the 3D name carries the handle side, so it reads in Omacad's tree
                label = f"Door, handle {p.handle_side[0].upper()}"
            add(label, (x, -t, d_bot), (dw, t, d_top - d_bot), '3/4" melamine + laminate')
            if p.has_pulls and str(p.style).startswith("upper"):
                if d_top - d_bot > UPPER_PULL_FROM_BOTTOM + UPPER_PULL_CC + 0.5:
                    _upper_door_pull(model, p, i, x, dw, d_bot)
            elif p.has_pulls and d_top - d_bot > p.pull_from_top + p.pull_span:
                _door_pull(model, p, i, x, dw, d_top)
            if p.doors == 1:
                _hinge_cups(model, p, x, dw, d_bot, d_top)

    for i, (b_bot, b_top) in enumerate(layout.drawer_bands, start=1):
        if p.sink:          # false front: no pull, no holes
            add("False front", (p.edge_reveal, -t, b_bot),
                (p.front_width, t, b_top - b_bot), '3/4" melamine + laminate')
            continue
        add(f"Drawer front {i}", (p.edge_reveal, -t, b_bot),
            (p.front_width, t, b_top - b_bot), '3/4" melamine + laminate')
        if p.has_pulls:
            _drawer_pull(model, p, b_bot, b_top)

    if layout.drawer_heights and not p.sink:
        _drawer_boxes(add, p, layout)

    if p.has_counter:
        _counter(add, p)

    return model


def build_boxes(p: Params, layout: Layout) -> list[Box]:
    return build_model(p, layout).boxes


def _shelf_pins(model: Model, p: Params) -> None:
    t = p.carcass_thk
    faces = (
        (t, (1.0, 0.0, 0.0)),
        (p.width - t, (-1.0, 0.0, 0.0)),
    )
    for x, normal in faces:
        for y in p.shelf_pin_y:
            for z in p.shelf_pin_rows:
                model.holes.append(HoleSpec(
                    p.shelf_pin_dia, p.shelf_pin_depth, (x, y, z), normal,
                ))


def _pull_bar(model: Model, name: str, pos, size) -> None:
    model.boxes.append(Box(name, tuple(round(v, 4) for v in pos),
                           tuple(round(v, 4) for v in size), "wire pull"))


def upper_pull_x(p: Params, index: int, door_x: float, door_w: float) -> float:
    """Screw-hole CENTRE x on an upper door: 2" from the hole centre to the door's
    handle (opening) edge. A pair opens at the meeting edges."""
    if p.doors == 2:
        handle_right = index == 0           # left door's handle edge is its right edge
    elif p.doors == 1:
        handle_right = p.handle_side == "right"
    else:
        return door_x + door_w / 2
    return (door_x + door_w - UPPER_PULL_EDGE_INSET if handle_right
            else door_x + UPPER_PULL_EDGE_INSET)


def _upper_door_pull(model: Model, p: Params, index: int, door_x: float, door_w: float,
                     door_bot: float) -> None:
    """Stock wire pull, vertical, 2 screws from the back on 4" centres. Hole centres
    1-1/2" and 5-1/2" up from the door bottom. Through-holes in the door; a simple
    wire pull (two legs and a grip) stands off the face."""
    hole_x = upper_pull_x(p, index, door_x, door_w)
    z_lo = door_bot + UPPER_PULL_FROM_BOTTOM
    z_hi = z_lo + UPPER_PULL_CC
    y_face = -p.carcass_thk
    for z in (z_lo, z_hi):
        model.holes.append(HoleSpec(
            UPPER_PULL_HOLE_DIA, p.carcass_thk, (hole_x, y_face, z), (0.0, -1.0, 0.0),
        ))
    wire, stand = 0.22, 0.9
    tag = 'LR'[index] if p.doors == 2 else p.handle_side[0].upper()
    label = f"Wire pull, door {tag}"
    for z in (z_lo, z_hi):                                   # the two legs, centred on the holes
        _pull_bar(model, label, (hole_x - wire / 2, y_face - stand, z - wire / 2),
                  (wire, stand, wire))
    _pull_bar(model, label, (hole_x - wire / 2, y_face - stand - wire, z_lo - wire / 2),
              (wire, wire, UPPER_PULL_CC + wire))            # the grip


def _door_pull(model: Model, p: Params, index: int, door_x: float, door_w: float,
               door_top: float) -> None:
    """Base doors: vertical 4 inch pull, holes 2 inches off the case centerline."""
    center = p.width / 2
    if p.doors == 2:
        hole_x = center - p.pull_off_center if index == 0 else center + p.pull_off_center
    else:
        hole_x = door_x + door_w / 2
    if not (door_x + 0.3 < hole_x < door_x + door_w - 0.3):
        hole_x = door_x + door_w / 2
    z_hi = door_top - p.pull_from_top
    z_lo = z_hi - p.pull_span
    y_face = -p.carcass_thk
    for z in (z_hi, z_lo):
        model.holes.append(HoleSpec(
            p.pull_hole_dia, p.carcass_thk, (hole_x, y_face, z), (0.0, -1.0, 0.0),
        ))
    bar = 0.4
    stand = 0.55
    label = f"Wire pull, door {'LR'[index] if p.doors == 2 else p.handle_side[0].upper()}"
    _pull_bar(model, label,
              (hole_x - bar / 2, y_face - stand, z_lo),
              (bar, stand, p.pull_span))


def _hinge_cups(model: Model, p: Params, door_x: float, door_w: float,
                z0: float, z1: float) -> None:
    """Two 35 mm cups in the back of a single door, on the hinge side, plus a small
    hinge block on the gable so the hinge side reads in the model."""
    t = p.carcass_thk
    if p.hinge_side == "left":
        cx = door_x + HINGE_CUP_EDGE
        gx = t
    else:
        cx = door_x + door_w - HINGE_CUP_EDGE
        gx = p.width - t - 0.45
    for z in (z1 - HINGE_FROM_END, z0 + HINGE_FROM_END):
        model.holes.append(HoleSpec(HINGE_CUP_DIA, HINGE_CUP_DEPTH, (cx, 0.0, z), (0.0, 1.0, 0.0)))
        model.boxes.append(Box(f"Hinge plate {p.hinge_side[0].upper()}",
                               (round(gx, 4), 0.6, round(z - 1.0, 4)), (0.45, 1.6, 2.0),
                               "hinge hardware"))


def _drawer_pull(model: Model, p: Params, z0: float, z1: float) -> None:
    center = p.width / 2
    mid = (z0 + z1) / 2
    y_face = -p.carcass_thk
    for x in (center - p.pull_off_center, center + p.pull_off_center):
        model.holes.append(HoleSpec(
            p.pull_hole_dia, p.carcass_thk, (x, y_face, mid), (0.0, -1.0, 0.0),
        ))
    bar = 0.4
    stand = 0.55
    _pull_bar(model, "Wire pull, drawer",
              (center - p.pull_span / 2, y_face - stand, mid - bar / 2),
              (p.pull_span, stand, bar))


def _drawer_boxes(add, p: Params, layout: Layout) -> None:
    t = p.carcass_thk
    bt = p.drawer_box_thk
    outer = p.drawer_box_outer_width
    depth = p.drawer_box_depth
    x0 = t + p.slide_clearance
    inner_x = x0 + bt
    inner_w = outer - 2 * bt
    for i, (b_bot, _b_top) in enumerate(layout.drawer_bands, start=1):
        # the front laps the stile, so the stile's top is above the front's bottom
        rail_top = None
        for r_bot, r_top in layout.rails:
            if r_bot - 0.05 <= b_bot <= r_top + 0.05:
                rail_top = r_top
                break
        z0 = (rail_top if rail_top is not None else b_bot) + p.drawer_box_above_rail
        box_h = getattr(p, 'drawer_box_h', None) or p.drawer_box_height(_b_top - b_bot)
        add(f"Drawer box side {i}", (x0, 0, z0), (bt, depth, box_h), '3/4" melamine')
        add(f"Drawer box side {i} (far)", (x0 + outer - bt, 0, z0),
            (bt, depth, box_h), '3/4" melamine')
        add(f"Drawer box front {i}", (inner_x, 0, z0), (inner_w, bt, box_h), '3/4" melamine')
        add(f"Drawer box back {i}", (inner_x, depth - bt, z0),
            (inner_w, bt, box_h), '3/4" melamine')
        g = p.drawer_groove
        add(f"Drawer box bottom {i}",
            (inner_x - g, bt - g, z0 + p.drawer_bottom_up),
            (inner_w + 2 * g, depth - 2 * bt + 2 * g, p.drawer_box_bottom_thk),
            '1/4" melamine')


def _counter(add, p: Params) -> None:
    left = -p.side_extension(p.left_side, p.counter_overhang_left, "left")
    right = p.width + p.side_extension(p.right_side, p.counter_overhang_right, "right")
    cw = right - left
    cd = p.counter_depth
    y0 = -p.counter_front_overhang
    top = p.case_top_z
    deck_z = top + p.counter_backer_thk

    if p.counter_build_style == "edge_strips":
        strip_h = p.edge_strip_h
        add("Counter front edge", (left, y0, top), (cw, p.counter_thk, strip_h), '1/2" MDF')
        side_y = y0 + p.counter_thk
        side_d = cd - p.counter_thk
        if p.left_side != "wall":
            add("Counter side edge L", (left, side_y, top),
                (p.counter_thk, side_d, strip_h), '1/2" MDF')
        if p.right_side != "wall":
            add("Counter side edge R", (right - p.counter_thk, side_y, top),
                (p.counter_thk, side_d, strip_h), '1/2" MDF')
    else:
        add("Counter backer (MDF)", (left, y0, top), (cw, cd, p.counter_backer_thk), '1" MDF')

    add("Countertop (Corian)", (left, y0, deck_z), (cw, cd, p.counter_thk), '1/2" Corian')
    splash_z = top + p.counter_build
    if p.backsplash_back:
        add("Backsplash, back wall", (left, y0 + cd - p.counter_thk, splash_z),
            (cw, p.counter_thk, p.backsplash_h), '1/2" Corian')
    if p.backsplash_left:
        add("Backsplash, left wall", (left, y0, splash_z),
            (p.counter_thk, cd - p.counter_thk, p.backsplash_h), '1/2" Corian')


def qdisc_center(box: Box) -> tuple[float, float]:
    """Centre of a "qdisc" corner's round, in the box's x/y."""
    (x, y, _z), (sx, sy, _sz) = box.pos, box.size
    return (x + sx if "+x" in box.shape else x), (y + sy if "+y" in box.shape else y)


def expand_round(boxes: list[Box], steps: int = 8) -> list[Box]:
    """Plain boxes only: each rounded corner becomes `steps` thin slices that follow the
    quarter circle (for the client views and the AR model, which draw boxes). The slices
    carry shape "slice" so the client views paint them without outlines."""
    import math
    out = []
    for b in boxes:
        if not b.shape.startswith("qdisc"):
            out.append(b)
            continue
        (x, y, z), (sx, sy, sz) = b.pos, b.size
        cx, cy = qdisc_center(b)
        r = sx
        for i in range(steps):
            y0, y1 = y + sy * i / steps, y + sy * (i + 1) / steps
            dy = abs((y0 + y1) / 2 - cy)
            half = math.sqrt(max(r * r - dy * dy, 0.0))
            xa, xb = (cx - half, cx) if "+x" in b.shape else (cx, cx + half)
            if xb - xa < 1e-4:
                continue
            out.append(Box(b.name, (round(xa, 4), round(y0, 4), z),
                           (round(xb - xa, 4), round(y1 - y0, 4), sz), b.material, b.join,
                           "slice"))
    return out
