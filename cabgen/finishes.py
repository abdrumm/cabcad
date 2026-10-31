"""Laminate and solid-surface colours for the 3D model and the AR view.

The shop names a finish by its catalogue number (or its name, when it has no
number). ``cabgen/laminates.csv`` maps that to an approximate display colour.
The ``texture`` column is reserved for a later image; it stays blank. Colours
here are flat stand-ins, not manufacturer swatches.

Four surfaces:

- case: the box exterior (gables, toe kick, stiles). Blank means white melamine.
- doors: doors and drawer fronts. Blank keeps the plain front colour.
- top: the countertop show faces. Blank keeps the laminate or solid-surface colour.
- interior: shelves, back, drawer boxes. Blank means white melamine.

An unknown number never raises. It is drawn in a neutral gray and reported.
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
    fallback: bool = False
    warning: str = ""

    @property
    def label(self) -> str:
        return " ".join(bit for bit in (self.manufacturer, self.number, self.name) if bit)


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
            )
            rows.append(fin)
            aliases = [a.strip() for a in (raw.get("aliases") or "").split("|") if a.strip()]
            keys = [
                fin.number,
                fin.name,
                f"{fin.manufacturer} {fin.number}".strip(),
                f"{fin.manufacturer} {fin.name}".strip(),
                f"{fin.manufacturer} {fin.number} {fin.name}".strip(),
                *aliases,
            ]
            for text in keys:
                k = _key(text)
                if k and k not in index:
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
    if fin.fallback:
        return f"UNKNOWN laminate {text!r}. "
    return f"{fin.label}. "


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
    for box in boxes:
        role = part_role(box.name, box.material)
        if role == "hardware":
            box.color = PULL_HEX
            continue
        if role in ("substrate", "kick"):
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
