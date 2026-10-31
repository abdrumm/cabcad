"""Optional finished kick plate across a base run.

Off unless the job says ``# kickplate=yes``. Black or grey. Height is
``KICK_PLATE_H`` (3.75") unless ``# kickplate_h=`` overrides it. One piece per
stretch of bases that touch, including a filler on the end of that stretch.
It sits in the toe-kick recess, on the room side of the structural toe-kick
plate. The gables stay one piece.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model3d import Box
from .params import KICK_PLATE_COLORS, KICK_PLATE_H, KICK_PLATE_THK
from .parts import Part
from .units import fmt_in

# A run longer than a plywood sheet is still one plate; the nest flags it.
SHEET_L = 96.0


def _on(value, default: bool = False) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in ("1", "yes", "y", "true", "on")


def color_name(value) -> str:
    """``black`` or ``grey``. ``gray`` is the same as grey."""
    name = str(value or "black").strip().lower()
    if name == "gray":
        name = "grey"
    if name not in KICK_PLATE_COLORS:
        raise ValueError(f"kick plate colour {value!r} is black or grey")
    return name


def height_of(settings: dict, toe_h: float) -> float:
    raw = settings.get("kickplate_h")
    height = KICK_PLATE_H if raw is None or str(raw).strip() == "" else float(raw)
    if height <= 0:
        raise ValueError("kick plate height must be greater than 0")
    if height > toe_h + 1e-6:
        raise ValueError(
            f"kick plate height {fmt_in(height)} is taller than the {fmt_in(toe_h)} toe kick"
        )
    return height


def enabled(settings: dict | None) -> bool:
    return bool(settings) and _on(settings.get("kickplate"), default=False)


@dataclass
class KickPiece:
    label: str
    x0: float
    x1: float
    y: float
    height: float
    color: str
    hex: str

    @property
    def length(self) -> float:
        return self.x1 - self.x0

    def part(self) -> tuple[Part, list[str]]:
        long = f" Longer than a {SHEET_L:g}\" sheet." if self.length > SHEET_L + 1e-6 else ""
        part = Part(
            name="Kick plate",
            qty=1,
            material=f'{fmt_in(KICK_PLATE_THK)} kick plate, {self.color}',
            thk=KICK_PLATE_THK,
            width=self.height,
            length=self.length,
            notes=(
                f"{self.color.capitalize()} finished face, {fmt_in(self.height)} high, "
                f"recessed in the toe kick. Continuous across the bases it covers.{long}"
            ),
        )
        return part, [self.label]

    def box(self) -> Box:
        return Box(
            f"{self.label} Kick plate",
            (self.x0, self.y, 0.0),
            (self.length, KICK_PLATE_THK, self.height),
            f'{fmt_in(KICK_PLATE_THK)} kick plate, {self.color}',
            color=self.hex,
        )


def build_kick(cabs, settings: dict | None) -> list[KickPiece]:
    """Finished kick plates for the base run, or nothing when the option is off."""
    if not enabled(settings):
        return []
    settings = settings or {}
    bases = sorted((c for c in cabs if c.run == "base" and c.params.has_toe_kick), key=lambda c: c.x)
    if not bases:
        return []
    color = color_name(settings.get("kickplate_color"))
    toe_h = min(c.params.toe_kick_h for c in bases)
    height = height_of(settings, toe_h)
    recess = min(c.params.toe_kick_recess for c in bases)
    y = max(0.0, recess - KICK_PLATE_THK)
    spans = _spans(bases, settings)
    pieces = []
    for i, (x0, x1) in enumerate(spans, start=1):
        label = "KP1" if len(spans) == 1 else f"KP{i}"
        pieces.append(KickPiece(label, x0, x1, y, height, color, KICK_PLATE_COLORS[color]))
    return pieces


def _spans(bases, settings: dict) -> list[tuple[float, float]]:
    """One (x0, x1) per stretch of bases that touch. A filler on the end is included."""
    groups: list[list] = [[bases[0]]]
    for cab in bases[1:]:
        prev = groups[-1][-1]
        if cab.x <= prev.x + prev.params.width + 1e-3:
            groups[-1].append(cab)
        else:
            groups.append([cab])
    fl, fr = _filler(settings)
    spans = []
    for i, group in enumerate(groups):
        x0 = group[0].x
        x1 = group[-1].x + group[-1].params.width
        if i == 0 and fl:
            x0 -= fl
        if i == len(groups) - 1 and fr:
            x1 += fr
        spans.append((x0, x1))
    return spans


def _filler(settings: dict) -> tuple[float, float]:
    if "base_walls" not in settings:
        return 0.0, 0.0
    from .kitchen import end_facts
    facts = end_facts(settings)
    if not facts["filler"]:
        return 0.0, 0.0
    if facts["filler_side"] == "left":
        return facts["filler"], 0.0
    return 0.0, facts["filler"]


def phrase(settings: dict | None, cabs=None) -> str:
    """Short words for the title block. Empty when the kick plate is off."""
    if not enabled(settings):
        return ""
    try:
        pieces = build_kick(cabs or [], settings or {})
    except ValueError:
        pieces = []
    color = color_name((settings or {}).get("kickplate_color"))
    if pieces:
        height = pieces[0].height
    else:
        height = KICK_PLATE_H
    return f"{fmt_in(height)} {color}"
