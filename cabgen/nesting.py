"""Nesting suggestion for 4x8 sheet stock.

Simple shelf (row) packing with kerf, honouring grain: a part's "length"
always runs along the 96" direction of the sheet, so the grain is not
crossed. Kerf is 3/16" on the saw and is charged between every cut.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .parts import Part


@dataclass
class PlacedPiece:
    name: str
    label: str
    x: float      # along the sheet length (96 direction), from the left edge
    y: float      # across the sheet (48 direction), from the top edge
    w: float      # width (across the sheet)
    h: float      # length (along the sheet / grain)
    eb_mask: str = "0000"
    eb: str = ""
    eb_spec: str = ""
    notch: tuple | None = None
    part_w: float = 0.0
    part_l: float = 0.0


@dataclass
class Sheet:
    index: int
    material: str
    pieces: list[PlacedPiece] = field(default_factory=list)
    used_w: float = 0.0   # along the sheet
    used_h: float = 0.0   # across the sheet
    sheet_w: float = 96.0
    sheet_h: float = 48.0

    @property
    def utilization(self) -> float:
        area = sum(p.w * p.h for p in self.pieces)
        return area / (self.sheet_w * self.sheet_h)

    @property
    def offcut(self) -> str:
        return f"{self.sheet_w - self.used_w:.2f}\" x {self.sheet_h - self.used_h:.2f}\" remaining"


def _expand(parts: list[Part]) -> list[tuple]:
    """Flatten the part list into individual cut pieces."""
    out = []
    for part in parts:
        for _ in range(part.qty):
            out.append((
                part.name, part.label, part.width, part.length,
                getattr(part, "eb_mask", "") or "0000",
                getattr(part, "eb", "") or "",
                getattr(part, "eb_spec", "") or "",
                getattr(part, "notch", None),
            ))
    return out


def nest(parts: list[Part], sheet_w: float = 96.0, sheet_h: float = 48.0,
         kerf: float = 0.1875) -> list[Sheet]:
    """Shelf-pack the parts onto 4x8 sheets. Returns one list of sheets per
    material group is NOT done here - call nest_by_material for that."""
    pieces = _expand(parts)
    # longest along grain first: shelves then get packed in a stable order
    pieces.sort(key=lambda p: (-p[3], -p[2], p[1]))
    sheets: list[Sheet] = []
    current = Sheet(index=1, material=parts[0].material if parts else "",
                    sheet_w=sheet_w, sheet_h=sheet_h)
    shelf_y = 0.0
    shelf_h = 0.0
    shelf_x = 0.0

    def new_sheet() -> None:
        nonlocal current, shelf_y, shelf_h, shelf_x
        if current.pieces:
            sheets.append(current)
        current = Sheet(index=len(sheets) + 1, material=parts[0].material if parts else "",
                        sheet_w=sheet_w, sheet_h=sheet_h)
        shelf_y = 0.0
        shelf_h = 0.0
        shelf_x = 0.0

    for name, label, w, h, eb_mask, eb, eb_spec, notch in pieces:
        if h > sheet_h or w > sheet_w:
            continue  # cannot be cut from this sheet; reported by the caller
        if shelf_h == 0:
            shelf_h = h
        if shelf_x + w > sheet_w:            # start a new shelf (rip)
            shelf_y += shelf_h + kerf
            shelf_x = 0.0
            shelf_h = h
        if shelf_y + shelf_h > sheet_h:      # next sheet
            new_sheet()
            shelf_h = h
        current.pieces.append(
            PlacedPiece(name=name, label=label, x=shelf_x, y=shelf_y, w=w, h=h,
                        eb_mask=eb_mask, eb=eb, eb_spec=eb_spec, notch=notch,
                        part_w=w, part_l=h)
        )
        shelf_x += w + kerf
        current.used_w = max(current.used_w, shelf_x - kerf)
        current.used_h = max(current.used_h, shelf_y + shelf_h)

    if current.pieces:
        sheets.append(current)
    return sheets


def nest_by_material(parts: list[Part], sheet_w: float = 96.0, sheet_h: float = 48.0,
                     kerf: float = 0.1875) -> dict[str, list[Sheet]]:
    """Nest each material group separately (melamine, Corian, MDF...)."""
    groups: dict[str, list[Part]] = {}
    for part in parts:
        groups.setdefault(part.material, []).append(part)
    out: dict[str, list[Sheet]] = {}
    for material, group in groups.items():
        out[material] = nest(group, sheet_w, sheet_h, kerf)
    return out


def uncuttable(parts: list[Part], sheet_w: float = 96.0,
               sheet_h: float = 48.0) -> list[str]:
    """Parts that do not fit on one sheet."""
    out = []
    for part in parts:
        if part.length > sheet_h or part.width > sheet_w:
            out.append(f"{part.label}: {part.dims()}")
    return out
