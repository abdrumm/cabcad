"""Shop standards and notes, condensed and context-aware (Brook, Oct 30).

"The shop specs were poorly written. Condense them, and omit anything that is not
applicable to the model at hand." So every note is one short line with an
applies-when condition on the job's facts. A laminate job gets no solid-surface note,
a job with no drawers no drawer note, no sink no sink note, and so on.

Add a note: append a Note to NOTES. `when` gets a Facts and returns True when the
note belongs on that job. `text` is a string, or a function of the Facts.
Audience: "shop" (carpenter drawings) or "client" (client sheet).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Union


@dataclass
class Facts:
    """What is actually in the design."""
    bases: int = 0
    uppers: int = 0
    drawers: int = 0            # real drawers (not a sink's false front)
    doors: int = 0
    sink: bool = False
    shelves: bool = False       # adjustable shelf behind doors, or open shelves
    open_upper: bool = False
    microwave: bool = False
    counter: str = "none"       # laminate | solid | none
    filler: float = 0.0
    filler_side: str = ""
    laminate: bool = False      # laminate on fronts or reveal faces
    finished_top: float = 33.5
    upper_bottom: float = 54.0
    tags: set = field(default_factory=set)


Text = Union[str, Callable[[Facts], str]]


@dataclass
class Note:
    id: str
    audience: str               # "shop" | "client"
    title: str
    text: Text
    when: Callable[[Facts], bool] = lambda f: True

    def render(self, f: Facts) -> str:
        return self.text(f) if callable(self.text) else self.text


def _in(x: float) -> str:
    from .units import fmt_in
    return fmt_in(x)


NOTES: list[Note] = [
    # ---------------------------------------------------------------- shop
    Note("site", "shop", "SITE", "Measure the real opening before cutting; framing is rarely square."),
    Note("height", "shop", "HEIGHT",
         lambda f: f'{_in(f.finished_top)} finished with the countertop; 4" toe kick, recessed 3".',
         lambda f: f.bases > 0 and f.counter != "none"),
    Note("fronts", "shop", "FRONTS",
         '1/2" overlay: 1/4" reveal at the case edge, 1/8" between fronts.',
         lambda f: f.doors > 0 or f.drawers > 0 or f.sink),
    Note("banding", "shop", "BANDING", "0.5-2 mm on exposed edges; never changes a part size."),
    Note("laminate", "shop", "LAMINATE",
         'Cut +1" oversize, contact adhesive both faces, palm-router trim, file edges. '
         "Order: bottom, sides, top.",
         lambda f: f.laminate),
    Note("drawers", "shop", "DRAWERS",
         '3/4" melamine box, 1/4" bottom in a 1/4" groove 1/2" up; 1/2" slide clearance a side.',
         lambda f: f.drawers > 0),
    Note("shelves", "shop", "SHELVES", '1/8" side gap, 1/4" setback, on 1/4" pins.',
         lambda f: f.shelves),
    Note("sink", "shop", "SINK",
         "False front, no pull, no box; front board behind it. No shelf or pin holes.",
         lambda f: f.sink),
    Note("microwave", "shop", "MICROWAVE", "Check the microwave's size and venting before cutting.",
         lambda f: f.microwave),
    Note("filler", "shop", "FILLER",
         lambda f: f"{_in(f.filler)} filler at the {f.filler_side or 'wall'} end only; never on uppers.",
         lambda f: f.filler > 0),
    Note("counter-lam", "shop", "COUNTERTOP",
         '3/4" ply top on 4" build-up strips (front, ends, every joint). '
         "Laminate side edges, front edge, then top.",
         lambda f: f.counter == "laminate"),
    Note("counter-solid", "shop", "COUNTERTOP",
         '1/2" solid surface, 4" x 3/4" ply build-up glued under the sheet, no staples. '
         'Ease edges 1/8".',
         lambda f: f.counter == "solid"),
    Note("uppers", "shop", "UPPERS",
         lambda f: f"Bottoms at {_in(f.upper_bottom)}; backs on the base wall. No fillers.",
         lambda f: f.uppers > 0),
    # ---------------------------------------------------------------- client
    Note("c-height", "client", "Height",
         lambda f: f"Countertop {_in(f.finished_top)} off the floor (ADA: 34\" max).",
         lambda f: f.bases > 0 and f.counter != "none"),
    Note("c-counter-lam", "client", "Countertop",
         'Laminate, 1-1/2" front edge, 4" backsplash.', lambda f: f.counter == "laminate"),
    Note("c-counter-solid", "client", "Countertop",
         'Solid surface, 1-1/2" edge, 4" backsplash.', lambda f: f.counter == "solid"),
    Note("c-uppers", "client", "Uppers",
         lambda f: f"Wall cabinets hang {_in(f.upper_bottom)} to the bottom.", lambda f: f.uppers > 0),
    Note("c-filler", "client", "Filler",
         lambda f: f"A {_in(f.filler)} filler closes the gap at the {f.filler_side} wall.",
         lambda f: f.filler > 0),
    Note("c-sink", "client", "Sink",
         "Sink base: false drawer front, open inside for plumbing.", lambda f: f.sink),
    Note("c-microwave", "client", "Microwave",
         "Open shelf for a countertop microwave; confirm your model's size.", lambda f: f.microwave),
    Note("c-site", "client", "Sizes", "Final sizes are set from site measurements."),
]


def select(f: Facts, audience: str) -> list[tuple[str, str]]:
    """(title, text) of every note for that audience that applies to these facts."""
    return [(n.title, n.render(f)) for n in NOTES if n.audience == audience and n.when(f)]


def _from_cabs(cabs, settings: dict | None) -> Facts:
    settings = settings or {}
    f = Facts()
    for c in cabs:
        p = c.params
        upper = str(p.style).startswith("upper") or getattr(c, "run", "") == "upper"
        if upper:
            f.uppers += 1
        else:
            f.bases += 1
        if p.sink:
            f.sink = True
        else:
            f.drawers += p.drawers
        f.doors += p.doors
        f.shelves = f.shelves or bool(p.has_shelf) or bool(p.open_shelves)
        f.open_upper = f.open_upper or bool(p.open_shelves)
        f.microwave = f.microwave or bool(p.is_microwave)
        f.laminate = f.laminate or bool(p.laminate and (p.doors or p.drawers or p.laminate_right_side))
    try:
        from .counter import kind_of
        f.counter = kind_of(settings) if f.bases else "none"
    except ValueError:
        f.counter = "none"
    if settings.get("base_walls") == "both" and f.bases:
        f.filler = float(settings.get("filler") or 1.0)
        f.filler_side = settings.get("filler_side") or "right"
    f.upper_bottom = float(settings.get("upper_bottom", 54.0))
    from .params import FINISHED_COUNTER_TOP
    f.finished_top = FINISHED_COUNTER_TOP
    return f


def facts_from_job(job) -> Facts:
    return _from_cabs(job.cabs, job.settings)


def facts_from_params(p) -> Facts:
    """One cabinet (the single-cabinet shop drawing)."""
    from types import SimpleNamespace
    settings = {"counter": "solid" if p.has_counter else "none"}
    f = _from_cabs([SimpleNamespace(params=p, run="")], settings)
    if p.has_filler:
        f.filler, f.filler_side = p.spacer_gap, p.spacer_side or "wall"
    return f


# Long assumption lines the notes above already say, shorter. Dropped from drawings.
COVERED = ("Edge banding is", "Carcass is captured", "Drawer boxes:", "Fronts stay inside")


def extra_checks(assumptions: list[str]) -> list[str]:
    return [a for a in assumptions if not a.startswith(COVERED)]
