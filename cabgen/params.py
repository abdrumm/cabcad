"""Cabinet parameters and style presets.

Everything the shop can vary lives here as a named field so the generator
never hard-codes a job detail. Defaults follow ~/Work/cabinet-shop-standards.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from typing import Any

# --- styles -----------------------------------------------------------------
# Each style drives the part schedule; dimensions stay user-entered.

STYLE_BASE_1D2D = "base_1drawer_2doors"
STYLE_BASE_3D = "base_3drawers"
STYLE_BASE_SINK = "base_sink"
STYLE_UPPER_2D = "upper_2doors"
STYLE_UPPER_1D2D = "upper_1drawer_2doors"
STYLE_UPPER_1D = "upper_1door"
STYLE_UPPER_OPEN = "upper_open"
STYLE_UPPER_MW = "upper_microwave"

# --- upper-style placeholders (2026-10-24) ----------------------------------
# PLACEHOLDERS, to confirm with Brook's shop plans. Change them here.
UPPER_1DOOR_WIDTH = 18.0        # typical 1-door upper is 9" to 24" wide
UPPER_1DOOR_MIN_WIDTH = 9.0     # a 1-door upper may go down to 9"
# Exactly 24" may still be one door. Wider than this is a pair (Brook, 2026-10-30).
UPPER_1DOOR_MAX_WIDTH = 24.0
UPPER_OPEN_SHELVES = 2          # adjustable shelves in a 30" open upper
UPPER_DEPTH = 12.0              # every upper, the microwave upper too (Brook, 2026-10-27)
MW_WIDTH = 30.0                 # microwave upper, overall width
MW_HEIGHT = 30.0                # same height as the other uppers, so the tops line up
MW_DEPTH = UPPER_DEPTH          # the box matches the other uppers (Brook, 2026-10-27)
# The microwave shelf (bottom board) alone projects past the 12" box. CONFIRMED (Brook, 2026-10-27):
# 16" from the front face of the 1/2" back to the front of the shelf (16-1/2" overall),
# front corners rounded to a 2" radius.
MICROWAVE_SHELF_CALLED_DEPTH = 16.0
MICROWAVE_SHELF_CORNER_R = 2.0
MW_OPENING_H = 17.25            # clear opening, microwave shelf (bottom) to the divider above.
                                # 30 - 3/4 bottom - 17-1/4 = 12" for the divider + the 2-door box above
# 1-door hardware (placeholders): 35 mm cup hinges, cup centre 22.5 mm in from the
# hinge edge, 3" from the top and the bottom of the door. Pull 1-1/2" in from the handle edge.
HINGE_CUP_DIA = 1.378           # 35 mm
HINGE_CUP_DEPTH = 0.5
HINGE_CUP_EDGE = 0.886          # 22.5 mm, edge of the door to the cup centre
HINGE_FROM_END = 3.0
# Upper door pulls (Brook, 2026-10-24): stock wire pull, 2 screws from the back, 4" c-c.
# Vertical on the door. Every number is to a HOLE CENTRE. "For now" positions.
UPPER_PULL_CC = 4.0             # screw holes, centre to centre
UPPER_PULL_FROM_BOTTOM = 1.5    # bottom hole centre, up from the door's bottom edge
UPPER_PULL_EDGE_INSET = 2.0     # hole centre to the door's handle (opening) edge; pairs: meeting edges
UPPER_PULL_HOLE_DIA = 0.1875    # 3/16" through-hole, PLACEHOLDER for the screw size
PULL_EDGE_INSET = UPPER_PULL_EDGE_INSET   # kept for older imports

# --- sink base (Brook, 2026-10-27) -----------------------------------------
# Built like the 1 drawer over 2 doors base, with a false drawer front (no pull,
# no drawer box, no slides), no shelf and no shelf-pin holes. The flat front top
# stile is replaced by a vertical board right behind the false front, which the
# false front screws to. The back top stile stands on edge.
SINK_FRONT_BOARD_BELOW_DOOR_TOP = 0.5   # TO CONFIRM (Brook: "I think"): the front board runs
                                        # from the case top to this far below the top of the doors
SINK_BACK_STILE_H = 4.0                 # confirmed: back stile stands vertical, 4" tall

STYLE_PRESETS: dict[str, dict[str, Any]] = {
    STYLE_BASE_1D2D: {
        "label": "Base — 1 drawer over 2 doors",
        "has_counter": False,
        "has_toe_kick": True,
        "drawers": 1,
        "doors": 2,
        "drawer_front_h": 6.0,
        "width": 27.0,
        "height": 33.5,
        "depth": 23.5,
        "has_shelf": True,
    },
    STYLE_BASE_SINK: {
        "label": "Base — sink",
        "has_counter": False,
        "has_toe_kick": True,
        "drawers": 1,            # one FALSE drawer front, same size as the 1-drawer base
        "doors": 2,
        "drawer_front_h": 6.0,
        "width": 30.0,
        "height": 33.5,
        "depth": 23.5,
        "has_shelf": False,
        "sink": True,
    },
    STYLE_BASE_3D: {
        "label": "Base — 3 drawers",
        "has_counter": False,
        "has_toe_kick": True,
        "drawers": 3,
        "doors": 0,
        "drawer_front_h": 6.0,
        "width": 27.0,
        "height": 33.5,
        "depth": 23.5,
        "has_shelf": False,
    },
    STYLE_UPPER_2D: {
        "label": "Wall upper — 2 doors (no countertop)",
        "has_counter": False,
        "has_toe_kick": False,
        "drawers": 0,
        "doors": 2,
        "drawer_front_h": 6.0,
        "width": 27.0,
        "height": 30.0,
        "depth": UPPER_DEPTH,
        "has_shelf": False,
    },
    STYLE_UPPER_1D: {
        "label": "Wall upper — 1 door (no countertop)",
        "has_counter": False,
        "has_toe_kick": False,
        "drawers": 0,
        "doors": 1,
        "drawer_front_h": 6.0,
        "width": UPPER_1DOOR_WIDTH,
        "height": 30.0,
        "depth": UPPER_DEPTH,
        "has_shelf": False,
    },
    STYLE_UPPER_OPEN: {
        "label": "Wall upper — open shelves (no countertop)",
        "has_counter": False,
        "has_toe_kick": False,
        "drawers": 0,
        "doors": 0,
        "drawer_front_h": 6.0,
        "width": 30.0,
        "height": 30.0,
        "depth": UPPER_DEPTH,
        "has_shelf": False,
        "open_shelves": UPPER_OPEN_SHELVES,
        "finished_interior": True,
    },
    STYLE_UPPER_MW: {
        "label": "Wall upper — microwave shelf, 2 doors above (no countertop)",
        "has_counter": False,
        "has_toe_kick": False,
        "drawers": 0,
        "doors": 2,
        "drawer_front_h": 6.0,
        "width": MW_WIDTH,
        "height": MW_HEIGHT,
        "depth": MW_DEPTH,
        "has_shelf": False,
        "mw_opening_h": MW_OPENING_H,
        "finished_interior": True,
    },
    # No upper with a drawer: uppers never have drawers (Brook, 2026-10-23).
}

MIN_WIDTH = 12.0

# --- form default widths (2026-10-24) ---------------------------------------
# What the CabCad form fills in when a tile is added, or when its style is switched
# while the width is empty or still the old style's default. Common stock sizes
# (3" steps). Keys are the form's style keys.
DEFAULT_WIDTH_UPPER_2DOORS = 30.0   # W3030, the most common wall cabinet
DEFAULT_WIDTH_UPPER_1DOOR = 18.0    # single doors are stock 9"-21"; 24" is the most (UPPER_1DOOR_MAX_WIDTH)
DEFAULT_WIDTH_UPPER_OPEN = 24.0
DEFAULT_WIDTH_UPPER_MW = 30.0       # microwave shelf: 30" fits a countertop microwave + trim
DEFAULT_WIDTH_BASE_3DRAWERS = 18.0  # drawer bases are stock 12"-24"; 18" is the usual one
DEFAULT_WIDTH_BASE_1D2D = 30.0      # always 2 doors here: 2-door bases are stock 24"-36"
DEFAULT_WIDTHS = {
    "upper": DEFAULT_WIDTH_UPPER_2DOORS,
    "upper1": DEFAULT_WIDTH_UPPER_1DOOR,
    "open": DEFAULT_WIDTH_UPPER_OPEN,
    "microwave": DEFAULT_WIDTH_UPPER_MW,
    "3drawer": DEFAULT_WIDTH_BASE_3DRAWERS,
    "base": DEFAULT_WIDTH_BASE_1D2D,
    "sink": DEFAULT_WIDTH_BASE_1D2D,   # same as the 1 drawer over 2 doors base
}
MIN_WIDTH_BY_STYLE = {STYLE_UPPER_1D: UPPER_1DOOR_MIN_WIDTH}


def min_width(style: str) -> float:
    return MIN_WIDTH_BY_STYLE.get(style, MIN_WIDTH)

STYLE_LABELS = {k: v["label"] for k, v in STYLE_PRESETS.items()}


def style_fields() -> list[str]:
    """Names of the style-driven fields (not user-facing dimension fields)."""
    return list(STYLE_KEYS)


STYLE_KEYS = ("has_counter", "has_toe_kick", "drawers", "doors", "has_shelf",
              "open_shelves", "finished_interior", "mw_opening_h", "sink")


@dataclass
class Params:
    """One cabinet. All lengths in inches."""

    # --- identity -----------------------------------------------------------
    style: str = STYLE_BASE_1D2D
    name: str = "Base cabinet"

    # --- outer dimensions ---------------------------------------------------
    # None means "take it from the style preset" (see __post_init__).
    width: float | None = None       # case outer width
    height: float | None = None      # overall height, floor to top of countertop
    depth: float | None = None       # finished case depth: front of the sides to the back face of the back

    # --- style-driven -------------------------------------------------------
    has_counter: bool = True
    has_toe_kick: bool = True
    drawers: int = 1
    doors: int = 2
    has_shelf: bool = False
    open_shelves: int = 0             # open upper: adjustable shelves, no doors
    finished_interior: bool = False   # open upper / microwave opening: the inside shows
    mw_opening_h: float = 0.0         # microwave upper: clear opening at the bottom (0 = none)
    sink: bool = False                # sink base: false drawer front, front board, no drawer box
    handle_side: str = "right"        # 1-door: the pull is on this side, the hinges on the other

    # --- material -----------------------------------------------------------
    carcass_thk: float = 0.75
    back_thk: float = 0.5
    drawer_box_thk: float = 0.75
    drawer_box_bottom_thk: float = 0.25
    edge_banding: str = "0.5 mm"

    # --- counter ------------------------------------------------------------
    has_counter: bool = False        # countertop removed for now
    counter_depth: float = 25.0      # front edge of the counter to the back face
    counter_thk: float = 0.5         # Corian top piece
    counter_backer_thk: float = 1.0  # edge build-up below the Corian, before the rabbet
    counter_overhang_left: float = 1.0
    counter_overhang_right: float = 1.0
    counter_front_overhang: float = 1.5
    backsplash_h: float = 4.0
    backsplash_left: bool = True
    backsplash_back: bool = True
    counter_build_style: str = "edge_strips"   # "edge_strips" | "mdf_deck"

    # --- face frame / fronts ------------------------------------------------
    # door_overhang is how much of the 3/4" gable the front covers.
    # 1/2" on 3/4" stock leaves a 1/4" reveal, and the front stays inside the case.
    door_overhang: float = 0.5
    door_gap: float = 0.125           # gap between the two doors (total)
    door_overhang_bottom: float = 0.0
    drawer_front_h: float | None = None
    drawer_gap: float = 0.125         # gap between the drawer front and the doors

    # --- casework anatomy ---------------------------------------------------
    stretcher_w: float = 4.0          # flat stretchers, front to back
    toe_kick_h: float = 4.0
    toe_kick_recess: float = 3.0      # set back from the case front
    back_style: str = "applied"       # "applied" (behind the sides) | "dado"

    # --- drawer box ---------------------------------------------------------
    slide_clearance: float = 0.5      # each side, between the box and the gable
    drawer_box_h: float = 4.0         # typical drawer box height
    drawer_box_short: float = 2.0     # box is this much shorter than its front (fallback)
    drawer_box_above_rail: float = 0.25  # bottom of drawer/slides 0.25" from top face of bottom drawer stile
    drawer_groove: float = 0.25       # dado/groove for bottom
    drawer_bottom_up: float = 0.5     # bottom of dado, 0.5" up from bottom face of sides
    drawer_dado_w: float = 0.25       # dado width
    drawer_dado_d: float = 0.25       # dado depth into inside face

    # --- shelf --------------------------------------------------------------
    shelf_z: float = 16.0             # bottom of the shelf, on the 16" pin row
    shelf_side_gap: float = 0.125
    shelf_setback: float = 0.25
    shelf_pin_dia: float = 0.25
    shelf_pin_depth: float = 0.375    # from the inside face, stopped
    shelf_pin_rows: tuple[float, ...] = (10.0, 12.0, 14.0, 16.0, 18.0, 20.0)
    shelf_pin_y: tuple[float, ...] = (4.5, 18.0)

    # --- pulls --------------------------------------------------------------
    has_pulls: bool = True
    pull_span: float = 4.0
    pull_hole_dia: float = 0.2
    pull_from_top: float = 2.0        # upper door hole, down from the top of the door
    pull_off_center: float = 2.0      # holes sit this far off the case centerline

    # --- site ----------------------------------------------------------------
    left_side: str = "wall"           # "wall" | "open" | "reveal"
    right_side: str = "open"          # "wall" | "open" | "reveal"
    spacer_gap: float = 1.0           # used only when has_spacer is set
    has_spacer: bool = False
    spacer_side: str = ""             # "left" or "right" when both ends are walls; blank keeps the old side

    # --- laminate ------------------------------------------------------------
    laminate: bool = True
    laminate_right_side: bool = True  # right gable is a reveal -> laminate
    # Catalogue numbers (cabgen/laminates.csv). Blank case and interior are white
    # melamine. Blank doors keep the plain front colour. Blank top keeps the
    # counter's own laminate or solid-surface colour. A row or a # line can set these.
    finish_case: str = ""
    finish_doors: str = ""
    finish_top: str = ""
    finish_interior: str = ""

    # --- sheet goods ---------------------------------------------------------
    sheet_w: float = 48.0
    sheet_h: float = 96.0
    kerf: float = 0.1875              # 3/16" saw blade

    def __post_init__(self) -> None:
        for key in ("finish_case", "finish_doors", "finish_top", "finish_interior"):
            val = getattr(self, key)
            if val is None or val is False:
                setattr(self, key, "")
            else:
                setattr(self, key, str(val).strip())
        self.door_count_overridden = False
        preset = STYLE_PRESETS[self.style]
        for key in ("width", "height", "depth", "drawer_front_h"):
            if getattr(self, key) is None and key in preset:
                setattr(self, key, preset[key])
        self.apply_style(self.style, only_missing=True)

    # --- style --------------------------------------------------------------
    def apply_style(self, style: str, only_missing: bool = False) -> None:
        preset = STYLE_PRESETS[style]
        for key in STYLE_KEYS:
            if key in preset:
                setattr(self, key, preset[key])
            elif key in ("open_shelves", "finished_interior", "mw_opening_h", "sink"):
                setattr(self, key, type(getattr(self, key))(0))
        if not only_missing:
            for key in ("drawer_front_h", "width", "height", "depth"):
                if key in preset:
                    setattr(self, key, preset[key])
        enforce_upper_door_limit(self)

    # --- derived ------------------------------------------------------------
    @property
    def is_microwave(self) -> bool:
        return self.mw_opening_h > 0

    @property
    def hinge_side(self) -> str:
        return "left" if self.handle_side == "right" else "right"

    @property
    def mw_divider_z(self) -> float:
        """Bottom of the fixed divider over the microwave opening."""
        return self.case_bottom_z + self.carcass_thk + self.mw_opening_h

    @property
    def counter_build(self) -> float:
        """Total thickness of the counter assembly."""
        return self.counter_thk + self.counter_backer_thk

    @property
    def case_top_z(self) -> float:
        """Height of the top of the case above the floor."""
        if not self.has_counter:
            return self.height
        return self.height - self.counter_build

    @property
    def case_bottom_z(self) -> float:
        return self.toe_kick_h if self.has_toe_kick else 0.0

    @property
    def case_h(self) -> float:
        return self.case_top_z - self.case_bottom_z

    @property
    def width_in(self) -> float:
        """Inside width between the gables."""
        return self.width - 2 * self.carcass_thk

    @property
    def gable_depth(self) -> float:
        """Side depth. An applied back sits behind the sides and makes up the finished depth."""
        if self.back_style == "dado":
            return self.depth
        return self.depth - self.back_thk

    @property
    def has_filler(self) -> bool:
        """Fillers are for base cabinets only. Uppers never get one."""
        return bool(self.has_spacer) and self.spacer_gap > 0 and not str(self.style).startswith("upper")

    def side_extension(self, side: str, overhang: float, which: str = "") -> float:
        """How far the counter passes the case on one side.

        `which` is "left" or "right". A filler covers only that one end.
        Callers that omit it keep the older behavior: every wall end with a
        spacer is extended.
        """
        if side == "wall" and self.has_filler and self._filler_is(which):
            return self.spacer_gap
        return overhang

    def _filler_is(self, which: str) -> bool:
        if not which:
            return True
        if self.spacer_side in ("left", "right"):
            return which == self.spacer_side
        if which == "left":
            return self.left_side == "wall"
        return self.left_side != "wall"

    @property
    def counter_width(self) -> float:
        """Overall countertop width, overhang to overhang."""
        return (
            self.width
            + self.side_extension(self.left_side, self.counter_overhang_left, "left")
            + self.side_extension(self.right_side, self.counter_overhang_right, "right")
        )

    @property
    def edge_reveal(self) -> float:
        """Gable (or top, or bottom) edge left showing. 3/4" stock with a 1/2" overlay leaves 1/4"."""
        return max(0.0, self.carcass_thk - self.door_overhang)

    @property
    def front_width(self) -> float:
        """Overall width of a drawer front. It stays inside the case by the reveal on each side."""
        return self.width - 2 * self.edge_reveal

    @property
    def door_width(self) -> float:
        """Width of one door."""
        if self.doors <= 1:
            return self.front_width
        return (self.front_width - self.door_gap * (self.doors - 1)) / self.doors

    @property
    def edge_strip_h(self) -> float:
        """Counter edge strip: the build-up below the deck, plus the 1/4" rabbet into the Corian."""
        return self.counter_backer_thk + self.counter_thk / 2

    def drawer_box_height(self, front_h: float) -> float:
        return max(2.0, round(front_h - self.drawer_box_short, 4))

    @property
    def drawer_box_depth(self) -> float:
        """22" under a 23" side, leaving 1" at the back for the slide."""
        return max(8.0, self.gable_depth - 1.0)

    @property
    def drawer_box_outer_width(self) -> float:
        return max(8.0, self.width_in - 2 * self.slide_clearance)

    # --- io -----------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Params":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        clean = {k: _coerce(v) for k, v in clean.items()}
        p = cls(**clean)
        return p


def _is_wall_upper(p: Params) -> bool:
    """Wall cabinets only. A base style never starts with ``upper``."""
    return str(p.style).startswith("upper")


def enforce_upper_door_limit(p: Params) -> str | None:
    """A single-door wall upper is 24\" at most. Wider ones are built as a pair.

    Exactly 24\" stays one door. Open shelves and the microwave upper are not
    single-door cabinets, so they are left alone. Base cabinets are not touched.
    When a job asked for one door and this converts it, the cabinet keeps a
    warning (see ``door_rule_warnings``) instead of being built silently.
    """
    if not _is_wall_upper(p):
        return None
    too_wide = (
        p.doors == 1
        and p.width is not None
        and p.width > UPPER_1DOOR_MAX_WIDTH
        and not p.open_shelves
        and not p.is_microwave
    )
    if not too_wide:
        # A legal 1-door (24\" or under) should not keep a warning from an
        # earlier, wider size on the same object.
        if p.doors == 1 and p.width is not None and p.width <= UPPER_1DOOR_MAX_WIDTH:
            p.door_count_overridden = False
        return None
    p.doors = 2
    if p.style == STYLE_UPPER_1D:
        p.style = STYLE_UPPER_2D
    p.door_count_overridden = True
    return upper_door_warning(p)


def upper_door_warning(p: Params) -> str:
    from .units import fmt_in
    return (
        f"Warning: {p.name} is {fmt_in(p.width)} wide. "
        f"A single-door upper is {fmt_in(UPPER_1DOOR_MAX_WIDTH)} at most (Brook). "
        f"Asked for as one door; built as two doors."
    )


def door_rule_warnings(p: Params) -> list[str]:
    """The shop-standard warning when a single-door upper was over 24\"."""
    if getattr(p, "door_count_overridden", False):
        return [upper_door_warning(p)]
    return []


def _coerce(value: Any) -> Any:
    """Keep booleans from HTML form strings from becoming truthy strings."""
    if isinstance(value, str):
        v = value.strip()
        if v.lower() in ("true", "on", "yes"):
            return True
        if v.lower() in ("false", "off", "no", ""):
            return False
        try:
            return int(v)
        except ValueError:
            pass
        try:
            return float(v)
        except ValueError:
            return v
    return value


# Fields the web form / CLI exposes. Anything not here is a derived or internal value.
FORM_FIELDS: list[dict[str, Any]] = [
    {"name": "style", "label": "Style", "type": "select",
     "options": [{"value": k, "label": v} for k, v in STYLE_LABELS.items()]},
    {"name": "name", "label": "Job / cabinet name", "type": "text"},
    {"name": "width", "label": 'Case width (outer, in)', "type": "number"},
    {"name": "height", "label": 'Overall height (in)', "type": "number"},
    {"name": "depth", "label": 'Case depth (in)', "type": "number"},
    {"name": "counter_depth", "label": 'Countertop depth (in)', "type": "number"},
    {"name": "drawer_front_h", "label": 'Drawer front height (in)', "type": "number"},
    {"name": "toe_kick_h", "label": 'Toe kick height (in)', "type": "number"},
    {"name": "door_overhang", "label": 'Overlay onto the gable (in)', "type": "number"},
    {"name": "door_gap", "label": 'Gap between doors (in)', "type": "number"},
    {"name": "drawer_gap", "label": 'Reveal, drawer to doors (in)', "type": "number"},
    {"name": "stretcher_w", "label": 'Top stretcher width (in)', "type": "number"},
    {"name": "counter_overhang_left", "label": 'Counter overhang left (in)', "type": "number"},
    {"name": "counter_overhang_right", "label": 'Counter overhang right (in)', "type": "number"},
    {"name": "counter_front_overhang", "label": 'Counter overhang front (in)', "type": "number"},
    {"name": "backsplash_h", "label": 'Backsplash height (in)', "type": "number"},
    {"name": "spacer_gap", "label": 'Filler to wall, bases only (in)', "type": "number"},
    {"name": "toe_kick_recess", "label": 'Toe kick recess (in)', "type": "number"},
    {"name": "left_side", "label": "Left side", "type": "select",
     "options": [{"value": "wall", "label": "Wall"},
                 {"value": "open", "label": "Open"},
                 {"value": "reveal", "label": "Reveal (visible)"}]},
    {"name": "right_side", "label": "Right side", "type": "select",
     "options": [{"value": "wall", "label": "Wall"},
                 {"value": "open", "label": "Open"},
                 {"value": "reveal", "label": "Reveal (visible)"}]},
    {"name": "back_style", "label": "Back panel", "type": "select",
     "options": [{"value": "dado", "label": "Dadoed into sides"},
                 {"value": "applied", "label": "Applied to back"}]},
    {"name": "counter_build_style", "label": "Counter build", "type": "select",
     "options": [{"value": "edge_strips", "label": "Edge strips (front and reveal side)"},
                 {"value": "mdf_deck", "label": "Full MDF deck under the Corian"}]},
    {"name": "laminate", "label": "Apply laminate to reveal faces", "type": "checkbox"},
    {"name": "laminate_right_side", "label": "Right gable is a reveal", "type": "checkbox"},
]
