"""Part schedule: turns a Params into the flat list of parts to cut.

Rules taken from the Fusion reference `27 in 1 Drawer 2 doors.step`:
  * sides run to the floor and are notched for the toe kick
  * bottom is a full-depth panel on top of the kick
  * stretchers lie flat, 4" front to back; the 4" is not a face height
  * fronts cover 1/2" of each 3/4" edge and stay inside the case (1/4" reveal)
  * 1/8" gap between doors, and between the drawer and the doors
  * applied 1/2" back behind the sides
  * counter is a 1/2" deck with edge strips, not a full backer slab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .params import (
    Params,
    STYLE_BASE_1D2D,
    STYLE_BASE_3D,
    STYLE_UPPER_1D2D,
    STYLE_UPPER_2D,
    HINGE_CUP_EDGE,
    HINGE_FROM_END,
    UPPER_PULL_CC,
    UPPER_PULL_EDGE_INSET,
    UPPER_PULL_FROM_BOTTOM,
    UPPER_PULL_HOLE_DIA,
    SINK_BACK_STILE_H,
    MICROWAVE_SHELF_CALLED_DEPTH,
    MICROWAVE_SHELF_CORNER_R,
    SINK_FRONT_BOARD_BELOW_DOOR_TOP,
    door_rule_warnings,
    enforce_upper_door_limit,
)

MAT_3_4 = '3/4" melamine'
MAT_1_2 = '1/2" melamine'
MAT_1_2_CORIAN = '1/2" Corian'
MAT_1_MDF = '1" MDF'


def _finish_note(spec: str) -> str:
    from .finishes import callout
    return callout(spec)


def _front_laminate(p: Params, oversize: bool = True) -> str:
    """Cut-list laminate cell for a door or drawer front, with the catalogue number when set."""
    note = _finish_note(p.finish_doors)
    if not p.laminate:
        return note.rstrip()
    if oversize:
        body = (
            "Both faces + all edges, waterfall order: bottom face, side edges, "
            'top face. +1" oversize for spray, trim with palm router.'
        )
    else:
        body = (
            "Both faces + all edges, waterfall order: bottom face, side edges, "
            "top face."
        )
    return note + body


@dataclass
class Part:
    name: str
    qty: int
    material: str
    thk: float
    width: float          # across the grain (short way, when cut)
    length: float         # along the grain (long way)
    banding: str = ""     # edge banding callout, in carpenter words
    laminate: str = ""    # laminate face callout
    notes: str = ""       # anything the carpenter needs beyond the numbers
    # Edge-band code from cabgen/edgeband.py. "W1 N1" or "L1 L2 W1 W2".
    eb: str = ""
    eb_mask: str = "0000"             # L1 L2 W1 W2, each 0 or 1
    eb_spec: str = ""                 # laminate the PVC matches
    # (recess along the length, kick along the width) when this blank gets a toe-kick notch.
    notch: tuple | None = None

    @property
    def area(self) -> float:
        return self.width * self.length

    @property
    def label(self) -> str:
        return self.name if self.qty == 1 else f"{self.name} ({self.qty})"

    def dims(self) -> str:
        return f"{_fmt(self.width)} x {_fmt(self.length)} x {_fmt(self.thk)}"


def _fmt(x: float) -> str:
    from .units import fmt_in
    return fmt_in(x)


@dataclass
class Layout:
    """Everything the drawings need to place the parts."""

    params: Params
    door_heights: list[float] = field(default_factory=list)
    drawer_heights: list[float] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    opening_top_z: float = 0.0          # top of the fronts (under the perimeter reveal)
    opening_h: float = 0.0
    door_top_z: float = 0.0             # top of the door zone
    door_bottom_z: float = 0.0          # bottom of the door zone
    rails: list[tuple[float, float]] = field(default_factory=list)      # (bottom, top) of each flat rail's edge
    drawer_bands: list[tuple[float, float]] = field(default_factory=list)  # (bottom, top) of each front
    sink_board: tuple[float, float] | None = None   # sink base: (bottom, top) of the vertical front board

    # --- vertical zones (z above the floor) --------------------------------
    @property
    def case_bottom_z(self) -> float:
        return self.params.case_bottom_z

    @property
    def case_top_z(self) -> float:
        return self.params.case_top_z

    def drawer_zone(self) -> tuple[float, float]:
        """(bottom, top) of the drawer stack, front elevation z."""
        if not self.drawer_bands:
            return (0.0, 0.0)
        return (self.drawer_bands[0][0], self.drawer_bands[-1][1])

    def door_zone(self) -> tuple[float, float]:
        """(bottom, top) of the doors, front elevation z."""
        p = self.params
        if not self.door_heights:
            return (0.0, 0.0)
        return (self.door_bottom_z, self.door_top_z)


def build_parts(p: Params) -> tuple[list[Part], Layout]:
    """Return the part list and the layout used by the drawings."""
    # A 1-door upper over 24" becomes a pair before any door is cut or drawn.
    enforce_upper_door_limit(p)
    parts: list[Part] = []
    layout = Layout(params=p)
    notes: list[str] = []
    assumptions: list[str] = []

    style = p.style
    is_base = p.has_toe_kick
    has_doors = p.doors > 0
    has_drawers = p.drawers > 0

    # ------------------------------------------------------------------ heights
    # Fronts sit on the face of the case. A 1/2" overlay on 3/4" stock leaves a
    # 1/4" reveal at the case perimeter. Where two fronts meet, the gap is 1/8",
    # and a flat stretcher behind that gap is centered on it so each front laps
    # the stretcher's 3/4" edge by 5/16".
    reveal = p.edge_reveal
    opening_top = p.case_top_z - reveal
    opening_bot = p.case_bottom_z + reveal
    opening_h = opening_top - opening_bot
    layout.opening_top_z = opening_top
    layout.opening_h = opening_h

    def rail_on_gap(gap_top: float) -> None:
        """Place a flat rail so its front edge is centered on a gap whose top is gap_top."""
        if p.sink:          # sink base: the vertical front board takes the rail's place
            return
        mid = gap_top - p.drawer_gap / 2
        half = p.carcass_thk / 2
        layout.rails.append((round(mid - half, 4), round(mid + half, 4)))

    if has_drawers:
        if has_doors:
            heights = [p.drawer_front_h] * p.drawers
        else:
            avail = opening_h - p.drawer_gap * (p.drawers - 1)
            heights = [round(avail / p.drawers, 4)] * p.drawers
            notes.append(
                f"Drawer fronts split the {fmt(opening_h)} opening evenly: "
                + ", ".join(fmt(h) for h in heights)
                + ". Adjust heights per job if the drawer mix differs."
            )
        z = opening_top
        for i, h in enumerate(heights):
            z -= h
            layout.drawer_bands.append((round(z, 4), round(z + h, 4)))
            layout.drawer_heights.append(round(h, 4))
            if i < len(heights) - 1 or has_doors:
                rail_on_gap(z)
                z -= p.drawer_gap
        layout.door_top_z = round(z, 4) if has_doors else p.case_bottom_z
    else:
        layout.door_top_z = opening_top

    if p.sink and has_doors:
        layout.sink_board = (round(layout.door_top_z - SINK_FRONT_BOARD_BELOW_DOOR_TOP, 4),
                             round(p.case_top_z, 4))

    if has_doors:
        # Microwave upper: the doors sit over the fixed divider, not down to the bottom.
        layout.door_bottom_z = round(
            p.mw_divider_z + reveal if p.is_microwave else opening_bot, 4)
        door_h = round(layout.door_top_z - layout.door_bottom_z, 4)
        layout.door_heights = [door_h] * p.doors

    # ------------------------------------------------------------------ carcass
    gable_depth = p.gable_depth
    width_in = p.width_in

    parts.append(
        Part(
            name="Gable (side panel)",
            qty=2,
            material=MAT_3_4,
            thk=p.carcass_thk,
            width=p.case_top_z,          # gables run down to the floor behind the toe kick
            length=gable_depth,
            banding="Front edge; bottom edge (toe kick side). Sand and hand-file.",
            laminate=(
                _finish_note(p.finish_case)
                + "Reveal face(s) only: laminate per waterfall order "
                '(bottom face, side edges, top face). +1" oversize, trim with palm router.'
                if p.laminate
                else _finish_note(p.finish_case).rstrip()
            ),
            notes=(
                f"Notch the front bottom {fmt(p.toe_kick_recess)} deep by "
                f"{fmt(p.toe_kick_h)} tall. "
                if is_base else ""
            ) + (
                f"Shelf-pin holes {fmt(p.shelf_pin_dia)} dia, {fmt(p.shelf_pin_depth)} "
                f"deep from the inside face only. Columns "
                + " and ".join(fmt(y) for y in p.shelf_pin_y)
                + " from the front. Rows "
                + ", ".join(fmt(z) for z in p.shelf_pin_rows)
                + " off the floor."
                if p.has_shelf else ""
            ) + (
                f"Shelf-pin holes {fmt(p.shelf_pin_dia)} dia, {fmt(p.shelf_pin_depth)} deep, "
                f"inside face only, columns " + " and ".join(fmt(y) for y in open_pin_y(p))
                + " from the front, rows " + ", ".join(fmt(z) for z in open_pin_rows(p))
                + " up from the bottom of the case. "
                if p.open_shelves else ""
            ) + (
                "Finished interior: the inside face shows, so use a finished face "
                "and band every exposed front edge."
                if p.finished_interior else ""
            ),
        )
    )

    if p.is_microwave:
        parts.append(
            Part(
                name="Microwave shelf",
                qty=1,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in,
                length=MICROWAVE_SHELF_CALLED_DEPTH,
                banding="Front edge and the two rounded corners (it shows).",
                notes=(
                    f"The bottom of the cabinet, captured between the gables: fixed, glued and "
                    f"screwed. {fmt(MICROWAVE_SHELF_CALLED_DEPTH)} from the front face of the back "
                    f"to its front edge ({fmt(MICROWAVE_SHELF_CALLED_DEPTH + p.back_thk)} overall), so it "
                    f"projects {fmt(MICROWAVE_SHELF_CALLED_DEPTH - p.gable_depth)} past the "
                    f"{fmt(p.depth)} box. Round the two front corners to a "
                    f"{fmt(MICROWAVE_SHELF_CORNER_R)} radius. The microwave sits on it."
                ),
            )
        )
    else:
        parts.append(
            Part(
                name="Bottom plate (stretcher)",
                qty=1,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in,
                length=gable_depth,
                banding="Front edge only.",
                notes=(
                    "Captured between the gables, flush with the front and the back of "
                    "the sides. It sits on the toe-kick stretchers."
                    if is_base else
                    "Captured between the gables. It is the microwave shelf: fixed, glued "
                    "and screwed through the gables. The microwave sits on it."
                    if p.is_microwave else
                    "Captured between the gables. It is the floor of the cabinet."
                ),
            )
        )

    if p.back_style == "dado":
        back_w = width_in
        back_h = p.case_h - p.carcass_thk
        back_note = "Let into the back of the sides, seated on the bottom plate."
    else:
        back_w = p.width
        back_h = p.case_top_z
        back_note = (
            "Applied behind the sides, covering their back edges. Full case width, "
            "from the floor to the top of the sides."
        )
    parts.append(
        Part(
            name="Back panel",
            qty=1,
            material=MAT_1_2,
            thk=p.back_thk,
            width=back_w,
            length=back_h,
            banding="None (concealed).",
            notes=back_note,
        )
    )

    if not is_base:
        parts.append(
            Part(
                name="Top plate",
                qty=1,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in,
                length=gable_depth,
                banding="Front edge only.",
                notes="One piece captured between the gables, flush with the top of the sides. "
                      "The sides run full height.",
            )
        )
        if p.is_microwave:
            parts.append(
                Part(
                    name="Microwave divider",
                    qty=1,
                    material=MAT_3_4,
                    thk=p.carcass_thk,
                    width=width_in,
                    length=gable_depth,
                    banding="Front edge only.",
                    notes=(
                        f"Fixed shelf between the gables, bottom face {fmt(p.mw_divider_z)} up "
                        f"from the bottom of the case: {fmt(p.mw_opening_h)} clear over the "
                        "microwave shelf. It is the floor of the 2-door cabinet above, and "
                        "the doors lap its front edge."
                    ),
                )
            )
    elif p.sink:
        fb_bot, fb_top = layout.sink_board
        parts.append(
            Part(
                name="Sink front board",
                qty=1,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in,
                length=round(fb_top - fb_bot, 4),
                banding="Bottom edge only.",
                notes=(
                    "Stands vertical between the gables, flush with their front edges, from the "
                    f"top of the case down to {fmt(SINK_FRONT_BOARD_BELOW_DOOR_TOP)} below the top "
                    "of the doors (doors close against it). Replaces the front top stile and the "
                    "drawer stile. The false front screws to it from behind."
                ),
            )
        )
        parts.append(
            Part(
                name="Top stile, back",
                qty=1,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in,
                length=SINK_BACK_STILE_H,
                banding="None (concealed).",
                notes=(f"Stands vertical, {fmt(SINK_BACK_STILE_H)} tall, against the back, flush "
                       "with the top of the sides (open space for the sink plumbing below)."),
            )
        )
    else:
        parts.append(
            Part(
                name="Top stile, front",
                qty=1,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in,
                length=p.stretcher_w,
                banding="Front edge only.",
                notes="Flat stile, 4\" front to back, flush with the top and the front of the sides.",
            )
        )
        parts.append(
            Part(
                name="Top stile, back",
                qty=1,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in,
                length=p.stretcher_w,
                banding="None (concealed).",
                notes="Flat stile, 4\" front to back, flush with the top and the back of the sides.",
            )
        )

    # drawer stile: flat 3/4" board at the case front, over/under the drawer front as applicable.
    # The drawer front butts the stile; the stile carries the front and squares the case.
    if layout.drawer_heights and layout.rails:
        parts.append(
            Part(
                name="Drawer stile",
                qty=max(1, len(layout.rails)),  # one per rail, as in the 3D model
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in,
                length=p.stretcher_w,
                banding="Front edge only.",
                notes=(
                    "Flat stile, 4\" front to back. Its 3/4\" front edge is centered on the "
                    "1/8\" gap, and each front laps that edge 5/16\"."
                ),
            )
        )

    # ------------------------------------------------------------------ toe kick
    if is_base:
        parts.append(
            Part(
                name="Toe kick plate",
                qty=1,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in,
                length=p.toe_kick_h,
                banding="Top edge; ends.",
                notes=(
                    f"The face of the toe kick, butting up to the floor. Recessed "
                    f"{fmt(p.toe_kick_recess)} from the case front."
                ),
            )
        )
        parts.append(
            Part(
                name="Toe kick stile, back",
                qty=1,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in,
                length=p.toe_kick_h,
                banding="None (concealed).",
                notes="At the back of the sides, under the bottom, butting the floor.",
            )
        )
        if p.has_filler:
            parts.append(
                Part(
                    name="Spacer board (wall side)",
                    qty=1,
                    material=MAT_3_4,
                    thk=p.carcass_thk,
                    width=p.spacer_gap,
                    length=p.toe_kick_h,
                    banding="Top edge; exposed edge.",
                    notes=(
                        "Bridges the gap between the case side and the wall. "
                        "Nuanced piece - confirm height/position on site."
                    ),
                )
            )

    # ------------------------------------------------------------------ fronts
    if has_doors:
        for i in range(p.doors):
            parts.append(
                Part(
                    name=door_name(p, i),
                    qty=1,
                    material=MAT_3_4,
                    thk=p.carcass_thk,
                    width=p.door_width,
                    length=layout.door_heights[0],
                    banding="All four edges (both faces).",
                    laminate=_front_laminate(p),
                    notes=(
                        single_door_note(p)
                        if p.doors == 1 else
                        f"Covers {fmt(p.door_overhang)} of each gable "
                        f"({fmt(p.edge_reveal)} reveal). "
                        f"{fmt(p.door_gap)} gap between the doors. "
                        + upper_pull_note(p, "the meeting edge")
                        if p.has_pulls and str(p.style).startswith("upper") else
                        f"Covers {fmt(p.door_overhang)} of each gable "
                        f"({fmt(p.edge_reveal)} reveal). "
                        f"{fmt(p.door_gap)} gap between the doors. "
                        f"4\" wire pull, holes {fmt(p.pull_from_top)} and "
                        f"{fmt(p.pull_from_top + p.pull_span)} down from the top, "
                        f"{fmt(p.pull_off_center)} off the case centerline."
                        if p.has_pulls else
                        f"Covers {fmt(p.door_overhang)} of each gable "
                        f"({fmt(p.edge_reveal)} reveal). "
                        f"{fmt(p.door_gap)} gap between the doors."
                    ),
                )
            )

    if has_drawers and p.sink:
        parts.append(
            Part(
                name="False front",
                qty=1,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=p.front_width,
                length=layout.drawer_heights[0],
                banding="All four edges (both faces).",
                laminate=_front_laminate(p, oversize=False),
                notes=(
                    "False drawer front: same size and reveals as a real drawer front. "
                    "NO pull, drill no holes. Screw it to the sink front board from behind."
                ),
            )
        )
    elif has_drawers:
        for i, dh in enumerate(layout.drawer_heights, start=1):
            parts.append(
                Part(
                    name=f"Drawer front {i}",
                    qty=1,
                    material=MAT_3_4,
                    thk=p.carcass_thk,
                    width=p.front_width,
                    length=dh,
                    banding="All four edges (both faces).",
                    laminate=_front_laminate(p, oversize=False),
                    notes=(
                        f"Covers {fmt(p.door_overhang)} of each gable "
                        f"({fmt(p.edge_reveal)} reveal at the sides and the top). "
                        + (
                            f"4\" wire pull centered on the case."
                            if p.has_pulls else ""
                        )
                    ),
                )
            )

    # drawer boxes (a sink base has none: no box, no slides)
    if has_drawers and not p.sink:
        box_mat = MAT_3_4 if p.drawer_box_thk >= 0.7 else MAT_1_2
        box_outer = p.drawer_box_outer_width
        box_d = p.drawer_box_depth
        box_h = p.drawer_box_height(layout.drawer_heights[0])
        box_in = box_outer - 2 * p.drawer_box_thk
        bottom_w = box_in + 2 * p.drawer_groove
        bottom_d = box_d - 2 * p.drawer_box_thk + 2 * p.drawer_groove
        parts.append(
            Part("Drawer box side", qty=2 * len(layout.drawer_heights), material=box_mat,
                 thk=p.drawer_box_thk, width=box_h, length=box_d,
                 banding="Top edge; front edge.",
                 notes=f"{fmt(p.slide_clearance)} clearance each side for the slides.")
        )
        parts.append(
            Part("Drawer box front/back", qty=2 * len(layout.drawer_heights),
                 material=box_mat, thk=p.drawer_box_thk,
                 width=box_h, length=box_in, banding="Top edge.",
                 notes="Between the sides.")
        )
        parts.append(
            Part("Drawer box bottom", qty=len(layout.drawer_heights),
                 material=MAT_1_2, thk=p.drawer_box_bottom_thk,
                 width=bottom_w, length=bottom_d, banding="None (concealed).",
                 notes=(
                     f"In a {fmt(p.drawer_groove)} groove, "
                     f"{fmt(p.drawer_bottom_up)} up from the bottom of the sides."
                 ))
        )
        assumptions.append(
            f"Drawer boxes: {fmt(p.drawer_box_thk)} melamine, outside "
            f"{fmt(box_outer)} wide x {fmt(box_d)} deep x {fmt(box_h)} tall. "
            f"{fmt(p.slide_clearance)} slide clearance each side. "
            f"Box sits {fmt(p.drawer_box_above_rail)} above the rail under it."
        )

    if p.has_shelf:
        parts.append(
            Part(
                name="Shelf",
                qty=1,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in - 2 * p.shelf_side_gap,
                length=gable_depth - p.shelf_setback,
                banding="Front edge only.",
                notes=(
                    f"{fmt(p.shelf_side_gap)} clear of each side, "
                    f"{fmt(p.shelf_setback)} back from the front, flush with the back "
                    f"of the sides. Sits on the {fmt(p.shelf_z)} pin row."
                ),
            )
        )

    if p.open_shelves:
        parts.append(
            Part(
                name="Open shelf",
                qty=p.open_shelves,
                material=MAT_3_4,
                thk=p.carcass_thk,
                width=width_in - 2 * p.shelf_side_gap,
                length=gable_depth - p.shelf_setback,
                banding="Front edge only (it shows).",
                notes=(
                    f"Adjustable, on pins. {fmt(p.shelf_side_gap)} clear of each side, "
                    f"{fmt(p.shelf_setback)} back from the front. Spaced evenly: "
                    + ", ".join(fmt(z) for z in open_shelf_z(p))
                    + " up from the bottom of the case (bottom of each shelf). No doors."
                ),
            )
        )
        assumptions.append(
            f"Open upper: no doors, {p.open_shelves} adjustable shelves spaced evenly, "
            "finished interior (placeholder until Brook's shop plans)."
        )
    if p.is_microwave:
        assumptions.append(
            f"Microwave upper: {fmt(p.mw_opening_h)} clear opening at the bottom, "
            f"{fmt(p.depth)} deep like the other uppers, 2 doors over a fixed divider above. "
            f"The microwave shelf projects to {fmt(MICROWAVE_SHELF_CALLED_DEPTH + p.back_thk)} "
            f"overall with {fmt(MICROWAVE_SHELF_CORNER_R)} radius front corners (confirmed "
            "2026-10-27). Check the microwave's size and venting before cutting."
        )

    # ------------------------------------------------------------------ counter
    if p.has_counter:
        cw = p.counter_width
        cd = p.counter_depth
        parts.append(
            Part(
                name="Countertop top piece (Corian)",
                qty=1,
                material=MAT_1_2_CORIAN,
                thk=p.counter_thk,
                width=cw,
                length=cd,
                banding="N/A (solid surface).",
                laminate="",
                notes=(
                    "Rabbet the front and the reveal side 1/2\" wide by 1/4\" deep, "
                    "leaving 1/4\" of Corian. Epoxy the edge strips, sand flat, "
                    "ease the revealed edges with a 1/8\" quarter-round bit."
                ),
            )
        )
        if p.counter_build_style == "edge_strips":
            parts.append(
                Part(
                    name="Counter front edge",
                    qty=1,
                    material='1/2" MDF',
                    thk=p.counter_thk,
                    width=cw,
                    length=p.edge_strip_h,
                    banding="N/A.",
                    notes=(
                        "Full counter width. Runs from the top of the case and rabbits "
                        "1/4\" into the Corian. The side edge butts this strip."
                    ),
                )
            )
            reveal_sides = sum(1 for side in (p.left_side, p.right_side) if side != "wall")
            if reveal_sides:
                parts.append(
                    Part(
                        name="Counter side edge",
                        qty=reveal_sides,
                        material='1/2" MDF',
                        thk=p.counter_thk,
                        width=cd - p.counter_thk,
                        length=p.edge_strip_h,
                        banding="N/A.",
                        notes="Reveal side only. Butts the front edge. No edge on a wall side.",
                    )
                )
        else:
            parts.append(
                Part(
                    name="Counter backer (MDF)",
                    qty=1,
                    material=MAT_1_MDF,
                    thk=p.counter_backer_thk,
                    width=cw,
                    length=cd,
                    banding="N/A.",
                    notes="Full deck under the Corian. The visible edge reads 1.5\" deep.",
                )
            )
        if p.backsplash_back:
            parts.append(
                Part(
                    name="Backsplash, back wall",
                    qty=1,
                    material=MAT_1_2_CORIAN,
                    thk=p.counter_thk,
                    width=cw,
                    length=p.backsplash_h,
                    banding="N/A.",
                    notes="Full length including the overhangs; sits on the countertop.",
                )
            )
        if p.backsplash_left:
            parts.append(
                Part(
                    name="Backsplash, left wall",
                    qty=1,
                    material=MAT_1_2_CORIAN,
                    thk=p.counter_thk,
                    width=cd - p.counter_thk,
                    length=p.backsplash_h,
                    banding="N/A.",
                    notes="Butts up against the back-wall backsplash.",
                )
            )

    # ------------------------------------------------------------------ notes
    if p.sink:
        assumptions.append(
            f"Sink base: false drawer front (no pull, no drawer box or slides), no shelf. "
            f"A vertical front board from the top of the case to "
            f"{fmt(SINK_FRONT_BOARD_BELOW_DOOR_TOP)} below the top of the doors (TO CONFIRM) "
            f"carries the false front; the back stile stands vertical, {fmt(SINK_BACK_STILE_H)} tall."
        )
    if layout.drawer_heights and not p.sink:
        assumptions.append(
            f"Fronts stay inside the case. {fmt(p.edge_reveal)} reveal on the perimeter, "
            f"{fmt(p.drawer_gap)} gap where fronts meet. Stiles are flat, "
            f"{fmt(p.stretcher_w)} front to back, and the fronts lap the stile's "
            f"{fmt(p.carcass_thk)} edge."
        )
    if p.has_counter:
        assumptions.append(
            f"Countertop {fmt(cw)} x {fmt(cd)}, front overhang "
            f"{fmt(p.counter_front_overhang)}. The back of the counter is flush with "
            f"the back of the back panel. Overall height {fmt(p.height)} = "
            f"{fmt(p.case_top_z)} case (including the toe kick) + "
            f"{fmt(p.counter_build)} counter build. Backsplash {fmt(p.backsplash_h)}."
        )
    assumptions.append(
        "Carcass is captured construction (panels captured between the gables) so the "
        "stated outer dimensions are the finished outside dimensions."
    )
    if p.has_filler:
        assumptions.append(
            f"{fmt(p.spacer_gap)} spacer between the case and the wall. "
            "Re-measure the opening before cutting."
        )
    from .finishes import resolved_finished_ends
    ends = resolved_finished_ends(p)
    if p.laminate and ends != "none":
        notch = ""
        if p.has_toe_kick:
            notch = (
                " The side is one piece; the toe-kick notch is cut out of it, "
                "not a second board and not a solid rectangle."
            )
        assumptions.append(
            f"Finished end ({ends}): laminate the outside face with the case laminate "
            f"and band the visible edges.{notch}"
        )
    assumptions.append(
        "Edge banding is 0.5-2 mm PVC, color-matched, and does not change any part dimension. "
        "The code (L1 L2 W1 W2, and N1 on a base side) is the shop table in cabgen/edgeband.py."
    )
    from .edgeband import stamp_parts
    stamp_parts(parts, p)
    if p.has_toe_kick:
        assumptions.append(
            f"Toe kick: notch the gables {fmt(p.toe_kick_recess)} deep by "
            f"{fmt(p.toe_kick_h)} tall. The kick plate is recessed "
            f"{fmt(p.toe_kick_recess)} and a back stile sits at the back. "
            f"The bottom panel is full depth and sits on both."
        )

    layout.notes = notes
    layout.assumptions = door_rule_warnings(p) + assumptions
    return parts, layout


def fmt(x: float) -> str:
    from .units import fmt_in
    return fmt_in(x)


def door_name(p: Params, i: int) -> str:
    """Door L / Door R on a pair. A single door is just "Door"."""
    if p.doors == 2:
        return f"Door {'LR'[i]}"
    if p.doors == 1:
        return "Door"
    return f"Door {i + 1}"


def single_door_note(p: Params) -> str:
    hinge = p.hinge_side
    handle = p.handle_side
    pull = upper_pull_note(p, f"the {handle} edge") + " " if p.has_pulls else ""
    return (
        f"Covers {fmt(p.door_overhang)} of each gable ({fmt(p.edge_reveal)} reveal). "
        f"Handle {handle.upper()}, hinged {hinge.upper()}. " + pull
        + f"Two 35 mm cup holes on the back, {fmt(HINGE_CUP_EDGE)} from the {hinge} edge "
        f"to the centre, {fmt(HINGE_FROM_END)} from the top and the bottom."
    )


def open_shelf_z(p: Params) -> list[float]:
    """Bottom of each open shelf, evenly spaced in the clear inside height."""
    n = p.open_shelves
    if n <= 0:
        return []
    t = p.carcass_thk
    lo = p.case_bottom_z + t
    hi = p.case_top_z - t
    gap = (hi - lo - n * t) / (n + 1)
    return [round(lo + gap * (k + 1) + t * k, 4) for k in range(n)]


def open_pin_rows(p: Params) -> list[float]:
    """Pin rows: each shelf's spot and 2" either side, so the shelves can move."""
    rows = set()
    for z in open_shelf_z(p):
        for dz in (-2.0, 0.0, 2.0):
            rows.add(round(z + dz, 4))
    return sorted(rows)


def open_pin_y(p: Params) -> list[float]:
    """Two pin columns, 2" in from the front and the back of the gable."""
    return [2.0, round(p.gable_depth - 2.0, 4)]


def upper_pull_note(p: Params, edge: str) -> str:
    """Stock wire pull on an upper door (Brook, 2026-10-24). Dimensions are to hole centres."""
    return (
        f"Stock wire pull, vertical, 2 screws from the back on {fmt(UPPER_PULL_CC)} centres: "
        f"drill {fmt(UPPER_PULL_HOLE_DIA)} through. Hole centres {fmt(UPPER_PULL_EDGE_INSET)} "
        f"from {edge}, {fmt(UPPER_PULL_FROM_BOTTOM)} and "
        f"{fmt(UPPER_PULL_FROM_BOTTOM + UPPER_PULL_CC)} up from the bottom of the door."
    )
