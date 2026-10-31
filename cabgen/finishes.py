"""Laminate and solid-surface colours for the 3D model and the AR view.

The shop names a finish by its catalogue number (or its name, when it has no
number). ``cabgen/laminates.csv`` maps that to an approximate display colour.
The ``texture`` column is reserved for a later image; it stays blank. The
``swatch_note`` column says the hex values are flat stand-ins, not
manufacturer swatches.

Four surfaces:

- case: the box exterior (gables, toe kick, stiles). Blank means white melamine.
- doors: doors and drawer fronts. Blank keeps the plain front colour.
- top: the countertop show faces. Blank keeps the laminate or solid-surface colour.
- interior: shelves, back, drawer boxes. Blank means white melamine.

An unknown number never raises. It is drawn in a neutral gray and reported.
A placeholder (White / Black / Woodgrain / Grey TBD) is a real pick for the
form: the drawing says "color TBD" until the client chooses a number.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

LIBRARY_PATH = Path(__file__).resolve().parent / "laminates.csv"

# Warm white, close to the sheet's case colour. Shop default for the box and the inside.
WHITE_HEX = "#F4F1EA"
# Wire pulls, the same dark metal the AR view already uses.
PULL_HEX = "#3B3F44"
# Neutral gray when the number is not in the library. Obvious, and not a real laminate.
FALLBACK_HEX = "#B7B1A8"
# Unfinished end of a cabinet: the raw case (particle / melamine core), not a laminate.
RAW_CASE_HEX = "#C6A56A"

# Dropdown group order after the placeholders and the shop staples.
GROUP_ORDER = ("white", "black", "grey", "woodgrain", "pattern", "color")
GROUP_LABELS = {
    "white": "White",
    "black": "Black",
    "grey": "Grey",
    "woodgrain": "Woodgrain",
    "pattern": "Pattern",
    "color": "Color",
}

# ``# key=value`` lines on a job sheet, and the Params field they fill.
JOB_KEYS = {
    "case": "finish_case",
    "finish_case": "finish_case",
    "exterior": "finish_case",
    "box": "finish_case",
    "doors": "finish_doors",
    "finish_doors": "finish_doors",
    "fronts": "finish_doors",
    "door": "finish_doors",
    "top": "finish_top",
    "finish_top": "finish_top",
    "countertop": "finish_top",
    "counter_finish": "finish_top",
    "interior": "finish_interior",
    "finish_interior": "finish_interior",
}

# Columns on a cabinet row, in the order they are tried. The first filled cell wins.
ROW_KEYS = {
    "finish_case": ("case", "finish_case", "exterior", "box"),
    "finish_doors": ("doors", "finish_doors", "fronts", "door"),
    "finish_top": ("top", "finish_top", "countertop", "counter_finish"),
    "finish_interior": ("interior", "finish_interior"),
}

_WORD = re.compile(r"[^a-z0-9]+")


def _key(text: str) -> str:
    return _WORD.sub("", (text or "").lower())


@dataclass(frozen=True)
class Finish:
    manufacturer: str
    number: str
    name: str
    hex: str
    approximate: bool
    texture: str
    kind: str
    finish: str = ""
    group: str = ""
    staple: bool = False
    tbd: bool = False
    fallback: bool = False
    warning: str = ""

    @property
    def label(self) -> str:
        return " ".join(bit for bit in (self.manufacturer, self.number, self.name) if bit)

    @property
    def display(self) -> str:
        """What the dropdown shows. ``Formica 949-58 White (matte)``, or ``White (TBD)``."""
        if self.tbd:
            return f"{self.name} (TBD)"
        bits = " ".join(bit for bit in (self.manufacturer, self.number, self.name) if bit)
        if self.finish and self.finish.upper() != "TBD":
            return f"{bits} ({self.finish.lower()})"
        return bits

    @property
    def drawing(self) -> str:
        """Words on a drawing. Placeholders are ``color TBD``, not the family name."""
        if self.tbd:
            return "color TBD"
        return self.display


def _load() -> tuple[list[Finish], dict[str, Finish]]:
    rows: list[Finish] = []
    index: dict[str, Finish] = {}
    if not LIBRARY_PATH.is_file():
        return rows, index
    with LIBRARY_PATH.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            fin = Finish(
                manufacturer=(raw.get("manufacturer") or "").strip(),
                number=(raw.get("number") or "").strip(),
                name=(raw.get("name") or "").strip(),
                hex=(raw.get("hex") or WHITE_HEX).strip(),
                approximate=str(raw.get("approximate") or "").strip().lower() in ("yes", "true", "1"),
                texture=(raw.get("texture") or "").strip(),
                kind=(raw.get("kind") or "").strip() or "laminate",
                finish=(raw.get("finish") or "").strip(),
                group=(raw.get("group") or "").strip().lower(),
                staple=str(raw.get("staple") or "").strip().lower() in ("yes", "true", "1"),
                tbd=str(raw.get("tbd") or "").strip().lower() in ("yes", "true", "1"),
            )
            rows.append(fin)
            aliases = [a.strip() for a in (raw.get("aliases") or "").split("|") if a.strip()]
            # Bare "White" must stay the melamine number. A placeholder named
            # White, or "Formica White", must not take that key.
            generic = {"white", "black", "grey", "gray"}
            number_key = _key(fin.number)
            keys = [
                fin.number,
                fin.display,
                f"{fin.manufacturer} {fin.number}".strip(),
                f"{fin.manufacturer} {fin.name}".strip(),
                f"{fin.manufacturer} {fin.number} {fin.name}".strip(),
                fin.name,
                *aliases,
            ]
            for text in keys:
                k = _key(text)
                if not k or k in index:
                    continue
                if k in generic and k != number_key:
                    continue
                index[k] = fin
    return rows, index


_CACHE: tuple[list[Finish], dict[str, Finish]] | None = None


def library() -> list[Finish]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load()
    return _CACHE[0]


def _index() -> dict[str, Finish]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load()
    return _CACHE[1]


def lookup(spec: str) -> Finish:
    """The finish for a catalogue number or a name. Unknown specs get a neutral gray."""
    text = str(spec or "").strip()
    if not text:
        return Finish("", "", "White melamine", WHITE_HEX, True, "", "melamine")
    hit = _index().get(_key(text))
    if hit is not None:
        return hit
    shown = text if len(text) < 80 else text[:77] + "..."
    return Finish(
        "", shown, shown, FALLBACK_HEX, True, "", "unknown",
        fallback=True,
        warning=(
            f"unknown laminate {shown!r}; using neutral {FALLBACK_HEX} "
            f"until it is added to cabgen/laminates.csv"
        ),
    )


def callout(spec: str) -> str:
    """A short prefix for the cut-list laminate cell. Blank when no finish was named."""
    text = str(spec or "").strip()
    if not text:
        return ""
    fin = lookup(text)
    if fin.tbd:
        return "color TBD. "
    if fin.fallback:
        return f"UNKNOWN laminate {text!r}. "
    return f"{fin.display}. "


def row_finish(row: dict, field: str, job_value: str = "") -> str:
    """A cabinet cell, or the job default when that cell is blank."""
    for name in ROW_KEYS[field]:
        if name in row and str(row.get(name) or "").strip():
            return str(row[name]).strip()
    return str(job_value or "").strip()


def part_role(name: str, material: str = "") -> str:
    """Which of the four finishes this solid takes. Hardware stays metal."""
    raw = (name or "").lower()
    part = raw.split("/")[-1].strip()
    mat = (material or "").lower()
    if any(word in mat for word in ("pull", "hardware")) or "wire pull" in part or part.startswith("hinge"):
        return "hardware"
    if part.startswith("kick plate"):
        return "kick"
    if "drawer box" in part:
        return "interior"
    if "false front" in part or "drawer front" in part or part.startswith("door"):
        return "doors"
    if "countertop" in raw or part.startswith("counter"):
        if any(word in part for word in ("backsplash", "side splash", "edge strip")):
            return "top"
        if "backer" in part or "stiffener" in part:
            return "substrate"
        if "build-up" in part and "front" not in part:
            return "substrate"
        return "top"
    if any(word in part for word in (
        "shelf", "back panel", "bottom plate", "microwave divider", "sink front board",
    )):
        return "interior"
    return "case"


def _spec_for(params, role: str) -> str:
    raw = str(getattr(params, {
        "case": "finish_case",
        "doors": "finish_doors",
        "top": "finish_top",
        "interior": "finish_interior",
    }.get(role, ""), "") or "").strip()
    if role in ("case", "interior") and not raw:
        return "white"
    return raw


def paint_boxes(boxes, params) -> list[str]:
    """Set ``box.color`` from this cabinet's finishes. Returns warnings, once each."""
    warnings: list[str] = []
    seen: set[str] = set()
    ends = resolved_finished_ends(params)
    for box in boxes:
        role = part_role(box.name, box.material)
        if role == "hardware":
            box.color = PULL_HEX
            continue
        if role in ("substrate", "kick"):
            continue
        side = gable_side(box.name)
        if side:
            # The colour is the outside face of that one gable. A base gable is
            # still one piece; the toe-kick notch is a cut in it, not a second panel.
            finished = ends == "both" or ends == side
            if not finished:
                box.color = RAW_CASE_HEX
                continue
        spec = _spec_for(params, role)
        if not spec:
            continue
        fin = lookup(spec)
        box.color = fin.hex
        if fin.warning and fin.warning not in seen:
            seen.add(fin.warning)
            warnings.append(fin.warning)
    return warnings


def paint_counter_boxes(boxes, spec: str) -> list[str]:
    """Colour the counter's show faces. Hidden build-up stays the substrate colour."""
    text = str(spec or "").strip()
    if not text:
        return []
    fin = lookup(text)
    for box in boxes:
        if part_role(box.name, box.material) == "top":
            box.color = fin.hex
    return [fin.warning] if fin.warning else []


def job_top_spec(cabs, settings: dict | None) -> str:
    """The counter is one surface. The job line wins; else the first base that names a top."""
    if settings:
        spec = str(settings.get("finish_top") or "").strip()
        if spec:
            return spec
    for cab in cabs:
        if getattr(cab, "run", "") == "base":
            spec = str(getattr(cab.params, "finish_top", "") or "").strip()
            if spec:
                return spec
    return ""


def resolved_finished_ends(params) -> str:
    """``left``, ``right``, ``both``, or ``none``.

    A blank ``finished_ends`` follows the sides: an end that is not against a
    wall (or the next cabinet, which is stored as a wall) is a finished end.
    """
    raw = str(getattr(params, "finished_ends", "") or "").strip().lower()
    if raw in ("left", "right", "both", "none"):
        return raw
    left_open = str(getattr(params, "left_side", "wall") or "") != "wall"
    right_open = str(getattr(params, "right_side", "open") or "") != "wall"
    if left_open and right_open:
        return "both"
    if left_open:
        return "left"
    if right_open:
        return "right"
    return "none"


def gable_side(name: str) -> str | None:
    """``left`` or ``right`` when this solid is that gable, including a notch piece."""
    part = (name or "").lower().split("/")[-1].strip()
    if part.startswith("gable l") or part.startswith("gable left"):
        return "left"
    if part.startswith("gable r") or part.startswith("gable right"):
        return "right"
    return None


def drawing_label(spec: str) -> str:
    """Short words for a drawing. Blank stays blank. A TBD pick is ``color TBD``."""
    text = str(spec or "").strip()
    if not text:
        return ""
    return lookup(text).drawing


def needs_laminate_skin(spec: str) -> bool:
    """True when this finish is a sheet of laminate (or a number we do not know yet).

    White melamine and solid surface are the sheet itself. They are not a skin
    cut from a laminate sheet.
    """
    text = str(spec or "").strip()
    if not text:
        return False
    fin = lookup(text)
    if fin.tbd or fin.fallback:
        return True
    return fin.kind == "laminate"


def is_woodgrain(spec: str) -> bool:
    text = str(spec or "").strip()
    if not text:
        return False
    return lookup(text).group == "woodgrain"


def dropdown_groups() -> list[tuple[str, list[Finish]]]:
    """Placeholders, then shop staples, then the colour groups. File order inside each."""
    rows = library()
    groups: list[tuple[str, list[Finish]]] = []
    placeholders = [r for r in rows if r.tbd]
    staples = [r for r in rows if r.staple and not r.tbd]
    rest = [r for r in rows if not r.tbd and not r.staple]
    if placeholders:
        groups.append(("Not picked yet", placeholders))
    if staples:
        groups.append(("Shop staples", staples))
    for key in GROUP_ORDER:
        items = [r for r in rest if r.group == key]
        if items:
            groups.append((GROUP_LABELS.get(key, key), items))
    other = [r for r in rest if r.group not in GROUP_ORDER]
    if other:
        groups.append(("Other", other))
    return groups


def option_value(fin: Finish) -> str:
    """The job-sheet value. A catalogue number when there is one."""
    return fin.number or fin.display


def posted_finish(form: dict, key: str) -> str:
    """The laminate a form posted for ``doors`` / ``case`` / ``interior`` / ``top``.

    The dropdown value wins. ``__custom__`` (or a typed number with nothing
    picked) is the catalogue number the shop typed.
    """
    picked = str((form or {}).get(key) or "").strip()
    custom = str((form or {}).get(f"{key}_custom") or "").strip()
    if picked == "__custom__":
        return custom
    return picked or custom


def paint_filler(box, job) -> None:
    """The filler is a finished end of the case, so it takes that end's case colour."""
    bases = list(getattr(job, "bases", []) or [])
    if not bases:
        box.color = WHITE_HEX
        return
    side = str((getattr(job, "settings", {}) or {}).get("filler_side") or "right")
    cab = bases[0] if side == "left" else max(bases, key=lambda c: c.x)
    spec = str(getattr(cab.params, "finish_case", "") or "").strip() or "white"
    box.color = lookup(spec).hex
