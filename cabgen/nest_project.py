"""Whole-project sheet nesting for the panel saw, then the table saw.

Brook, 2026-10-23: nest the whole kitchen together. Fill sheet 1 with the first
cabinet's parts, add the next cabinet's parts into what is left, and open a new
sheet only when nothing fits. Each material and thickness is its own nest. The
1/2" back panels always get their own nest across the project.

The layout is guillotine, three stages, so it matches the shop:

  1. Panel saw: rip the 96" sheet into full-length strips (rip widths).
  2. Crosscut each strip into blocks.
  3. Table saw: rip a block into its parts when it holds more than one.

When fewest cuts and least waste disagree, fewest cuts wins: same-width parts
share a strip, and same-length parts share a block. Melamine and MDF have no
grain, so parts may turn 90 degrees. A grain material (birch plywood) keeps the
part's length along the 96" direction. Leftovers big enough to keep are shown
as labeled offcuts; slivers are hatched as scrap. Kerf (3/16") is charged
between every two neighbours. The sheet edge is used as is (no trim cut).

Labels are short and unique across the project: B1-GL is base cabinet 1, gable
left. The same labels go on the CAD boxes (kitchen.scene_of).
"""

from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .parts import Part, build_parts
from .svg import Svg, hatch
from .units import fmt_in

SHEET_W = 48.0     # across the sheet (rip direction)
SHEET_L = 96.0     # along the sheet (grain direction)
KERF = 0.1875      # 3/16" saw blade
MIN_OFFCUT = 4.0   # a leftover narrower than this is scrap, not an offcut
EPS = 1e-6

GRAIN_WORDS = ("birch", "plywood", "ply", "oak", "maple", "walnut", "cherry", "veneer")

# Short part codes. Numbered parts get 1, 2, 3 ... when the cabinet has more than one.
PART_CODES = [
    ("Gable", "G"),
    ("Bottom plate", "BP"),
    ("Top plate", "TP"),
    ("Back panel", "BK"),
    ("Top stile, front", "TSF"),
    ("Top stile, back", "TSB"),
    ("Drawer stile", "DS"),
    ("Sink front board", "FB"),
    ("False front", "FF"),
    ("Toe kick plate", "TK"),
    ("Toe kick stile, back", "TKB"),
    ("Drawer front", "DF"),
    ("Door L", "DL"),
    ("Door R", "DR"),
    ("Door", "D"),                 # the one door of a 1-door upper
    ("Open shelf", "OS"),
    ("Microwave divider", "MD"),
    ("Microwave shelf", "MS"),
    ("Drawer box side", "DBS"),
    ("Drawer box front/back", "DBF"),
    ("Drawer box bottom", "DBB"),
    ("Shelf", "SH"),
    ("Spacer board", "SP"),
]
CODE_MEANING = {
    "GL": "gable (side) left", "GR": "gable (side) right", "BP": "bottom plate",
    "TP": "top plate", "BK": "back panel", "TSF": "top stile, front",
    "TSB": "top stile, back", "DS": "drawer stile", "FB": "sink front board (vertical)", "FF": "false drawer front (sink, no pull)", "TK": "toe kick plate",
    "TKB": "toe kick stile, back", "DF": "drawer front", "DL": "door left",
    "DR": "door right", "D": "door (1-door upper)", "OS": "open shelf", "MD": "microwave divider", "MS": "microwave shelf (projects, 2\" R front corners)", "DBS": "drawer box side", "DBF": "drawer box front/back",
    "DBB": "drawer box bottom", "SH": "shelf", "SP": "spacer board (filler)",
    "CT1-TOP": "countertop top", "CT1-BU": "counter build-up strip (F front, L/R ends, J joints)",
    "CT1-ST": "counter stiffener strip", "CT1-BS": "backsplash", "CT1-SS": "side splash",
}


class NestError(ValueError):
    pass


# --------------------------------------------------------------------------- labels
def cabinet_codes(cabs) -> dict[str, str]:
    """B1, B2 ... for the base run and U1, U2 ... for the uppers, left to right."""
    codes: dict[str, str] = {}
    counts = {"base": 0, "upper": 0}
    for cab in sorted(cabs, key=lambda c: (c.run != "base", c.x)):
        counts[cab.run] = counts.get(cab.run, 0) + 1
        codes[cab.name] = f"{'B' if cab.run == 'base' else 'U'}{counts[cab.run]}"
    return codes


def _code_for(name: str) -> tuple[str, str]:
    """(code, number already in the name)."""
    for start, code in PART_CODES:
        if name.startswith(start):
            m = re.search(r"(\d+)\s*$", name)
            return code, (m.group(1) if m else "")
    words = re.findall(r"[A-Za-z]+", name)
    return "".join(w[0].upper() for w in words[:3]) or "P", ""


def part_labels(code: str, parts: list[Part]) -> list[tuple[Part, list[str]]]:
    """Every part of one cabinet with one label per piece (qty)."""
    out = []
    used: set[str] = set()
    for part in parts:
        pcode, num = _code_for(part.name)
        labels = []
        if pcode == "G":
            names = ["GL", "GR"] + [f"G{i}" for i in range(3, part.qty + 1)]
            labels = [f"{code}-{n}" for n in names[: part.qty]]
        elif num:
            labels = [f"{code}-{pcode}{num}"] if part.qty == 1 else [
                f"{code}-{pcode}{num}.{i}" for i in range(1, part.qty + 1)]
        elif part.qty == 1:
            labels = [f"{code}-{pcode}"]
        else:
            labels = [f"{code}-{pcode}{i}" for i in range(1, part.qty + 1)]
        fixed = []
        for lab in labels:
            base, n = lab, 2
            while lab in used:
                lab = f"{base}-{n}"
                n += 1
            used.add(lab)
            fixed.append(lab)
        out.append((part, fixed))
    return out


_BOX_TO_PART = [
    (re.compile(r"^Drawer box (front|back) \d+$"), "Drawer box front/back"),
    (re.compile(r"^Drawer box side \d+( \(far\))?$"), "Drawer box side"),
    (re.compile(r"^Drawer box bottom \d+$"), "Drawer box bottom"),
    (re.compile(r"^Drawer stile \d+$"), "Drawer stile"),
    (re.compile(r"^Gable [LR]$"), "Gable (side panel)"),
]


def box_labels(box_names: list[str], labelled: list[tuple[Part, list[str]]]) -> list[str]:
    """The cut-sheet label for each CAD box of one cabinet ('' for hardware)."""
    pool: dict[str, list[str]] = {}
    for part, labels in labelled:
        pool.setdefault(part.name, []).extend(labels)
    taken: dict[str, int] = {}
    by_box: dict[str, str] = {}
    out = []
    for name in box_names:
        if name.startswith("Wire pull"):
            out.append("")
            continue
        if name.endswith(" heel"):          # the toe-kick heel is part of its gable
            out.append(by_box.get(name[: -len(" heel")], ""))
            continue
        if name in by_box and name.startswith("Gable"):
            out.append(by_box[name])
            continue
        target = name if name in pool else ""
        if not target:
            for rx, pname in _BOX_TO_PART:
                if rx.match(name) and pname in pool:
                    target = pname
                    break
        if not target:
            target = next((p for p in pool if p.startswith(name) or name.startswith(p)), "")
        label = ""
        if target:
            if name == "Gable R" and len(pool[target]) > 1:
                label = pool[target][1]
            elif name == "Gable L":
                label = pool[target][0]
            else:
                i = taken.get(target, 0)
                if i < len(pool[target]):
                    label = pool[target][i]
                    taken[target] = i + 1
        by_box[name] = label
        out.append(label)
    return out


# --------------------------------------------------------------------------- pieces
@dataclass
class Piece:
    label: str
    cabinet: str
    part: str
    group: str
    thk: float
    width: float      # across the grain
    length: float     # along the grain
    grain: bool = False


@dataclass
class Placed:
    piece: Piece
    x: float          # along the sheet (96), from the left end
    y: float          # across the sheet (48), from the top edge
    dx: float         # size along
    dy: float         # size across

    @property
    def turned(self) -> bool:
        return abs(self.dx - self.piece.length) > EPS or abs(self.dy - self.piece.width) > EPS


@dataclass
class Block:
    """A crosscut block of a strip. Its pieces share one length, stacked across."""
    x: float
    length: float
    pieces: list[Placed] = field(default_factory=list)
    stack: float = 0.0       # used across, from the strip edge


@dataclass
class Strip:
    y: float
    width: float             # rip width
    blocks: list[Block] = field(default_factory=list)
    used: float = 0.0        # used along

    def room(self, kerf: float) -> float:
        return self.used + (kerf if self.blocks else 0.0)


@dataclass
class Rect:
    x: float
    y: float
    dx: float
    dy: float
    kind: str                # "offcut" | "scrap"


@dataclass
class Sheet:
    group: str
    index: int
    sheet_w: float
    sheet_l: float
    kerf: float
    strips: list[Strip] = field(default_factory=list)

    @property
    def next_y(self) -> float:
        if not self.strips:
            return 0.0
        s = self.strips[-1]
        return s.y + s.width + self.kerf

    @property
    def placed(self) -> list[Placed]:
        return [p for s in self.strips for b in s.blocks for p in b.pieces]

    @property
    def area(self) -> float:
        return self.sheet_w * self.sheet_l

    @property
    def parts_area(self) -> float:
        return sum(p.dx * p.dy for p in self.placed)

    @property
    def yield_pct(self) -> float:
        return 100.0 * self.parts_area / self.area

    def leftovers(self, min_offcut: float = MIN_OFFCUT) -> list[Rect]:
        k = self.kerf
        raw: list[tuple[float, float, float, float]] = []
        for s in self.strips:
            for b in s.blocks:
                left = s.width - b.stack - k
                if left > EPS:
                    raw.append((b.x, s.y + b.stack + k, b.length, left))
            tail = self.sheet_l - s.used - k
            if tail > EPS:
                raw.append((s.used + k, s.y, tail, s.width))
        bottom = self.sheet_w - self.next_y
        if bottom > EPS:
            raw.append((0.0, self.next_y, self.sheet_l, bottom))
        out = []
        for x, y, dx, dy in raw:
            kind = "offcut" if min(dx, dy) >= min_offcut - EPS else "scrap"
            out.append(Rect(x, y, dx, dy, kind))
        return out

    def cut_count(self) -> int:
        n = 0
        for s in self.strips:
            if s.y + s.width < self.sheet_w - EPS:
                n += 1
            for b in s.blocks:
                if b.x + b.length < self.sheet_l - EPS:
                    n += 1
                for p in b.pieces:
                    if p.y + p.dy < s.y + s.width - EPS:
                        n += 1
        return n


@dataclass
class Group:
    key: str
    thk: float
    grain: bool
    sheets: list[Sheet] = field(default_factory=list)
    # Countertop pieces longer than the sheet: listed whole, not nested (seam TBD).
    oversize: list[Piece] = field(default_factory=list)

    @property
    def pieces(self) -> list[Placed]:
        return [p for sh in self.sheets for p in sh.placed]


def grain_for(material: str, overrides: dict | None = None) -> bool:
    if overrides and material in overrides:
        return bool(overrides[material])
    low = material.lower()
    return any(w in low for w in GRAIN_WORDS)


def group_name(part: Part) -> str:
    """Material and true thickness. Back panels are always their own nest."""
    body = re.sub(r'^\s*[\d /.-]+"\s*', "", part.material).strip() or part.material
    name = f"{fmt_in(part.thk)} {body}"
    if part.name.startswith("Back panel"):
        name += " - back panels"
    return name


def project_pieces(cabs, grain: dict | None = None, extra=None) -> list[Piece]:
    """Every piece of the project in cabinet order (bases left to right, then uppers)."""
    codes = cabinet_codes(cabs)
    ordered = sorted(cabs, key=lambda c: (c.run != "base", c.x))
    out: list[Piece] = []
    for cab in ordered:
        parts, _layout = build_parts(cab.params)
        for part, labels in part_labels(codes[cab.name], parts):
            for lab in labels:
                out.append(Piece(
                    label=lab, cabinet=cab.name, part=part.name,
                    group=group_name(part), thk=part.thk,
                    width=part.width, length=part.length,
                    grain=grain_for(part.material, grain),
                ))
    for part, labels in extra or []:
        if "solid surface" in part.material.lower():
            continue
        for lab in labels:
            out.append(Piece(
                label=lab, cabinet="Countertop", part=part.name, group=group_name(part),
                thk=part.thk, width=part.width, length=part.length,
                grain=grain_for(part.material, grain),
            ))
    return out


# --------------------------------------------------------------------------- nesting
def _orients(p: Piece, sheet_w: float, sheet_l: float) -> list[tuple[float, float]]:
    """(along, across) choices that fit an empty sheet."""
    opts = [(p.length, p.width)]
    if not p.grain and abs(p.length - p.width) > EPS:
        opts.append((p.width, p.length))
    return [(a, c) for a, c in opts if a <= sheet_l + EPS and c <= sheet_w + EPS]


def _same(a: Piece, b: Piece) -> bool:
    return {round(a.width, 4), round(a.length, 4)} == {round(b.width, 4), round(b.length, 4)}


def nest_pieces(pieces: list[Piece], sheet_w: float = SHEET_W, sheet_l: float = SHEET_L,
                kerf: float = KERF) -> dict[str, Group]:
    """Nest pieces (already in cabinet order) group by group."""
    if sheet_w > sheet_l:
        sheet_w, sheet_l = sheet_l, sheet_w
    groups: dict[str, Group] = {}
    queues: dict[str, list[Piece]] = {}
    for p in pieces:
        if not _orients(p, sheet_w, sheet_l) and p.cabinet == "Countertop" and p.width <= sheet_w + EPS:
            # Brook, Oct 27: one continuous top. Too long for a sheet: list it, flag it,
            # leave the seam to Brook. It is not drawn on a sheet.
            if p.group not in groups:
                groups[p.group] = Group(p.group, p.thk, p.grain)
            groups[p.group].oversize.append(p)
            continue
        if not _orients(p, sheet_w, sheet_l):
            raise NestError(
                f"{p.label} ({p.cabinet} / {p.part}) is {fmt_in(p.width)} x {fmt_in(p.length)}"
                f" and does not fit a {sheet_w:g} x {sheet_l:g} sheet"
                + (" with the grain along the length" if p.grain else ""))
        queues.setdefault(p.group, []).append(p)
        if p.group not in groups:
            groups[p.group] = Group(p.group, p.thk, p.grain)
    for key, queue in queues.items():
        _nest_group(groups[key], queue, sheet_w, sheet_l, kerf)
    return groups


def _nest_group(group: Group, queue: list[Piece], W: float, L: float, k: float) -> None:
    for i, p in enumerate(queue):
        orients = _orients(p, W, L)
        if not (_into_block(group, p, orients, k) or _into_strip_exact(group, p, orients, L, k)
                or _new_strip(group, p, orients, queue[i:], W, L, k)
                or _into_strip_wider(group, p, orients, L, k)):
            sheet = Sheet(group.key, len(group.sheets) + 1, W, L, k)
            group.sheets.append(sheet)
            if not _new_strip(group, p, orients, queue[i:], W, L, k, only=sheet):
                raise NestError(f"{p.label} could not be placed")  # cannot happen


def _add(strip: Strip, block: Block, p: Piece, along: float, across: float, k: float) -> None:
    y = strip.y + block.stack + (k if block.pieces else 0.0)
    block.pieces.append(Placed(p, block.x, y, along, across))
    block.stack = y + across - strip.y


def _into_block(group, p, orients, k) -> bool:
    """Same length as an open block, and room across: one more table-saw rip."""
    for sh in group.sheets:
        for s in sh.strips:
            for b in s.blocks:
                for along, across in orients:
                    if abs(along - b.length) < EPS and b.stack + k + across <= s.width + EPS:
                        _add(s, b, p, along, across, k)
                        return True
    return False


def _new_block(s: Strip, p, along, across, k) -> None:
    b = Block(x=s.room(k), length=along)
    s.blocks.append(b)
    s.used = b.x + along
    _add(s, b, p, along, across, k)


def _into_strip_exact(group, p, orients, L, k) -> bool:
    for sh in group.sheets:
        for s in sh.strips:
            for along, across in orients:
                if abs(across - s.width) < EPS and s.room(k) + along <= L + EPS:
                    _new_block(s, p, along, across, k)
                    return True
    return False


def _new_strip(group, p, orients, ahead, W, L, k, only: Sheet | None = None) -> bool:
    same = sum(1 for q in ahead if _same(q, p))
    sheets = [only] if only else group.sheets
    for sh in sheets:
        best = None
        for along, across in orients:
            if sh.next_y + across > W + EPS:
                continue
            fit = min(same, int((L + k) // (along + k)))
            score = (fit * along / L, -across)
            if best is None or score > best[0]:
                best = (score, along, across)
        if best:
            _, along, across = best
            s = Strip(y=sh.next_y, width=across)
            sh.strips.append(s)
            _new_block(s, p, along, across, k)
            return True
    return False


def _into_strip_wider(group, p, orients, L, k) -> bool:
    best = None
    for sh in group.sheets:
        for s in sh.strips:
            for along, across in orients:
                if across < s.width - EPS and s.room(k) + along <= L + EPS:
                    waste = (s.width - across) * along
                    if best is None or waste < best[0] - EPS:
                        best = (waste, s, along, across)
    if best:
        _, s, along, across = best
        _new_block(s, p, along, across, k)
        return True
    return False


def nest_project(cabs, sheet_w: float = SHEET_W, sheet_l: float = SHEET_L,
                 kerf: float = KERF, grain: dict | None = None, extra=None) -> dict[str, Group]:
    """`extra` is [(Part, [label])] nested after the cabinets (the countertop).
    Solid surface is listed, never nested on plywood sheets."""
    return nest_pieces(project_pieces(cabs, grain, extra), sheet_w, sheet_l, kerf)


# --------------------------------------------------------------------------- text out
STRIP_NAMES = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def _strip_name(i: int) -> str:
    return STRIP_NAMES[i] if i < len(STRIP_NAMES) else f"S{i + 1}"


def _sz(x: float) -> str:
    return fmt_in(x).replace('"', "")


def cut_steps(sheet: Sheet) -> list[str]:
    """Cut order for one sheet, in plain words."""
    lines = [f"1. Panel saw - rip the {sheet.sheet_l:g}\" sheet into strips, from the top edge:"]
    for i, s in enumerate(sheet.strips):
        lines.append(f"   Strip {_strip_name(i)}: {fmt_in(s.width)} wide")
    lines.append("2. Crosscut each strip, from the left end. 3. Table saw - rip blocks to width:")
    for i, s in enumerate(sheet.strips):
        for j, b in enumerate(s.blocks, start=1):
            name = f"{_strip_name(i)}{j}"
            if len(b.pieces) == 1 and abs(b.pieces[0].dy - s.width) < EPS:
                p = b.pieces[0]
                lines.append(f"   {name}: crosscut {fmt_in(b.length)} -> {p.piece.label}"
                             f"{' (turned)' if p.turned else ''}")
            else:
                rips = ", ".join(f"{p.piece.label} {fmt_in(p.dy)}" for p in b.pieces)
                lines.append(f"   {name}: crosscut {fmt_in(b.length)}, rip -> {rips}")
    return lines


def cutlist_csv(groups: dict[str, Group]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["MATERIAL", "SHEET", "STRIP", "RIP WIDTH", "BLOCK", "CROSSCUT", "ORDER",
                "LABEL", "CABINET", "PART", "THICKNESS", "WIDTH", "LENGTH", "TURNED",
                "X ON SHEET", "Y ON SHEET"])
    for g in groups.values():
        for sh in g.sheets:
            order = 0
            for i, s in enumerate(sh.strips):
                for j, b in enumerate(s.blocks, start=1):
                    for p in b.pieces:
                        order += 1
                        w.writerow([g.key, sh.index, _strip_name(i), fmt_in(s.width),
                                    f"{_strip_name(i)}{j}", fmt_in(b.length), order,
                                    p.piece.label, p.piece.cabinet, p.piece.part,
                                    fmt_in(p.piece.thk), fmt_in(p.piece.width),
                                    fmt_in(p.piece.length), "yes" if p.turned else "",
                                    fmt_in(p.x), fmt_in(p.y)])
        for p in g.oversize:
            w.writerow([g.key, "NOT NESTED", OVERSIZE_NOTE, "", "", "", "", p.label, p.cabinet,
                        p.part, fmt_in(p.thk), fmt_in(p.width), fmt_in(p.length), "", "", ""])
    return buf.getvalue()


OVERSIZE_NOTE = "LONGER THAN STOCK SHEET - seam TBD"


def oversize_pieces(groups: dict[str, Group]) -> list[tuple[str, Piece]]:
    return [(g.key, p) for g in groups.values() for p in g.oversize]


def _codes(cabs, groups) -> list[tuple[str, str]]:
    out = list(cabinet_codes(cabs).items())
    if any(p.piece.cabinet == "Countertop" for g in groups.values() for p in g.pieces) or \
            any(p.cabinet == "Countertop" for _k, p in oversize_pieces(groups)):
        out.append(("Countertop", "CT1"))
    return out


def summary_rows(groups: dict[str, Group]) -> list[dict]:
    rows = []
    for g in groups.values():
        area = sum(sh.area for sh in g.sheets)
        used = sum(sh.parts_area for sh in g.sheets)
        offc = sum(r.dx * r.dy for sh in g.sheets for r in sh.leftovers() if r.kind == "offcut")
        rows.append({
            "material": g.key, "sheets": len(g.sheets), "pieces": len(g.pieces) + len(g.oversize),
            "yield": 100 * used / area if area else 0.0,
            "offcut_sqft": offc / 144, "waste_sqft": (area - used - offc) / 144,
            "cuts": sum(sh.cut_count() for sh in g.sheets),
            "grain": g.grain,
        })
    return rows


def cutlist_text(groups: dict[str, Group], title: str, cabs, kerf: float) -> str:
    out = [f"# {title} - nested cut list", "",
           f"Sheets {SHEET_W:g} x {SHEET_L:g} unless noted. Kerf {fmt_in(kerf)}. "
           "Panel saw rips strips, then crosscut, then the table saw rips blocks to width.",
           "Labels match the nest PDF and the parts in the CAD model.", "",
           "## Summary", "",
           "| Material | Sheets | Pieces | Yield | Offcuts kept (sq ft) | Waste (sq ft) | Cuts |",
           "|---|---|---|---|---|---|---|"]
    for r in summary_rows(groups):
        out.append(f"| {r['material']} | {r['sheets']} | {r['pieces']} | {r['yield']:.0f}% | "
                   f"{r['offcut_sqft']:.1f} | {r['waste_sqft']:.1f} | {r['cuts']} |")
    big = oversize_pieces(groups)
    if big:
        out += ["", "## Not nested - longer than stock sheet, seam TBD", "",
                "One continuous piece each. Too long for a 96\" sheet; Brook decides the seam.", "",
                "| Label | Part | Material | Width | Length |", "|---|---|---|---|---|"]
        for key, p in big:
            out.append(f"| {p.label} | {p.part} | {key} | {fmt_in(p.width)} | {fmt_in(p.length)} |")
    out += ["", "## Cabinets", ""]
    for name, code in _codes(cabs, groups):
        out.append(f"- {code} = {name}")
    out += ["", "## Part codes", ""]
    out += [f"- {c} = {m}" for c, m in CODE_MEANING.items()]
    for g in groups.values():
        for sh in g.sheets:
            out += ["", f"## {g.key} - sheet {sh.index} of {len(g.sheets)}", "",
                    f"Yield {sh.yield_pct:.0f}%, {sh.cut_count()} cuts."
                    + (" Grain runs along the 96\" length; parts are not turned." if g.grain else ""),
                    ""]
            out += cut_steps(sh)
            out += ["", "| Label | Cabinet | Part | Width | Length | Strip | Turned |",
                    "|---|---|---|---|---|---|---|"]
            for i, s in enumerate(sh.strips):
                for b in s.blocks:
                    for p in b.pieces:
                        out.append(f"| {p.piece.label} | {p.piece.cabinet} | {p.piece.part} | "
                                   f"{fmt_in(p.piece.width)} | {fmt_in(p.piece.length)} | "
                                   f"{_strip_name(i)} | {'yes' if p.turned else ''} |")
            offs = [r for r in sh.leftovers() if r.kind == "offcut"]
            if offs:
                out.append("")
                out.append("Offcuts to keep: " + "; ".join(
                    f"{_sz(min(r.dx, r.dy))} x {_sz(max(r.dx, r.dy))}" for r in offs))
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------- drawing
PAGE_W, PAGE_H = 17.0, 11.0      # tabloid, landscape
SCALE = 1.0 / 8.0                # 1-1/2" = 1'-0"
SCALE_TEXT = '1-1/2" = 1\'-0" (1:8)'
INK, HAIR = "#111111", "#555555"
PART_FILL = {"back": "#f3e7cf", "other": "#dfeaf7"}


def _fit_text(svg: Svg, cx, cy, w, h, lines: list[tuple[str, float, str]]) -> None:
    """Centered lines that shrink to fit the box; turned 90 degrees if the box is tall."""
    vertical = h > w * 1.3
    bw, bh = (h, w) if vertical else (w, h)
    total = sum(s for _t, s, _wt in lines) * 1.25
    longest = max(len(t) * s * 0.6 for t, s, _wt in lines)
    k = min(1.0, (bw - 0.06) / longest if longest else 1.0, (bh - 0.04) / total if total else 1.0)
    if k * lines[0][1] < 0.05:      # too small to read: label only, on one line
        lines = lines[:1]
        total = lines[0][1] * 1.25
        longest = len(lines[0][0]) * lines[0][1] * 0.6
        k = min(1.0, (bw - 0.04) / longest, (bh - 0.02) / total)
    y = -total * k / 2
    for text, size, weight in lines:
        s = size * k
        y += s * 1.25
        if vertical:
            svg.text(cx + y - s * 0.3, cy, text, size=round(s, 4), anchor="middle",
                     weight=weight, rotate=-90)
        else:
            svg.text(cx, cy + y - s * 0.3, text, size=round(s, 4), anchor="middle", weight=weight)


def sheet_page(sheet: Sheet, group: Group, title: str, page: int, pages: int) -> Svg:
    svg = Svg(PAGE_W, PAGE_H)
    m = 0.4
    svg.rect(m / 2, m / 2, PAGE_W - m, PAGE_H - m, stroke=INK, sw=0.014)
    svg.text(m + 0.1, m + 0.25, f"{group.key.upper()}  -  SHEET {sheet.index} OF {len(group.sheets)}",
             size=0.22, weight="bold")
    svg.text(PAGE_W - m - 0.1, m + 0.25, f"{title}  -  page {page} of {pages}", size=0.13,
             anchor="end")
    svg.text(m + 0.1, m + 0.5,
             f'Sheet {sheet.sheet_w:g}" x {sheet.sheet_l:g}"   Kerf {fmt_in(sheet.kerf)}   '
             f'Thickness {fmt_in(group.thk)}   Yield {sheet.yield_pct:.0f}%   '
             f'{len(sheet.placed)} parts   {sheet.cut_count()} cuts'
             + ("   GRAIN along the 96\" length" if group.grain else "   no grain: parts may turn"),
             size=0.13)

    ox, oy = 1.0, 1.15
    def X(v): return ox + v * SCALE
    def Y(v): return oy + v * SCALE
    L, W = sheet.sheet_l, sheet.sheet_w
    svg.rect(X(0), Y(0), L * SCALE, W * SCALE, fill="#ffffff", stroke=INK, sw=0.02)

    for r in sheet.leftovers():
        if r.kind == "offcut":
            svg.rect(X(r.x), Y(r.y), r.dx * SCALE, r.dy * SCALE, fill="#f4f4f4",
                     stroke="#888", sw=0.008, dash="0.06,0.04")
            _fit_text(svg, X(r.x + r.dx / 2), Y(r.y + r.dy / 2), r.dx * SCALE, r.dy * SCALE,
                      [(f"offcut {_sz(r.dy)} x {_sz(r.dx)}", 0.13, "normal")])
        else:
            hatch(svg, X(r.x), Y(r.y), r.dx * SCALE, r.dy * SCALE, spacing=0.06, sw=0.006,
                  stroke="#999")

    fill = PART_FILL["back"] if "back" in group.key else PART_FILL["other"]
    for p in sheet.placed:
        x, y, w, h = X(p.x), Y(p.y), p.dx * SCALE, p.dy * SCALE
        if p.piece.part == "Microwave shelf":
            # drawn with its 2" R front corners; packed (and cut) as the rectangle first
            from .params import MICROWAVE_SHELF_CORNER_R
            svg.rect(x, y, w, h, fill="none", stroke=HAIR, sw=0.006, dash="0.05,0.04")
            svg.path(_round_end_path(x, y, w, h, MICROWAVE_SHELF_CORNER_R * SCALE, p.turned),
                     fill=fill, stroke=INK, sw=0.012)
        else:
            svg.rect(x, y, w, h, fill=fill, stroke=INK, sw=0.012)
        size = f"{_sz(p.piece.width)} x {_sz(p.piece.length)}" + (" T" if p.turned else "")
        if p.piece.part == "Microwave shelf":    # the nester packs rectangles; call out the radius
            size += '  2" R front corners'
        _fit_text(svg, x + w / 2, y + h / 2, w, h,
                  [(p.piece.label, 0.19, "bold"), (size, 0.14, "normal")])

    # strip letters and rip widths on the left, sheet sizes on top
    for i, s in enumerate(sheet.strips):
        cy = Y(s.y + s.width / 2)
        svg.text(ox - 0.12, cy + 0.02, _strip_name(i), size=0.16, anchor="end", weight="bold")
        svg.text(ox - 0.12, cy + 0.18, _sz(s.width), size=0.09, anchor="end", fill=HAIR)
    svg.text(X(L / 2), oy - 0.08, f'{L:g}"  (8 ft)', size=0.11, anchor="middle", fill=HAIR)
    svg.text(X(L) + 0.1, Y(W / 2), f'{W:g}"', size=0.11, fill=HAIR)

    # scale bar: 0 to 4 ft
    bx, by = ox, Y(W) + 0.35
    for f in range(4):
        svg.rect(bx + f * 12 * SCALE, by, 12 * SCALE, 0.08,
                 fill=INK if f % 2 == 0 else "#ffffff", stroke=INK, sw=0.008)
        svg.text(bx + f * 12 * SCALE, by + 0.25, f"{f}'", size=0.1, anchor="middle")
    svg.text(bx + 48 * SCALE, by + 0.25, "4'", size=0.1, anchor="middle")
    svg.text(bx + 48 * SCALE + 0.3, by + 0.08,
             f"SCALE {SCALE_TEXT} on 11x17 - print at 100% (actual size)", size=0.12, weight="bold")

    # legend
    lx, ly = X(L) + 0.6, oy + 0.1
    svg.text(lx, ly, "LEGEND", size=0.13, weight="bold")
    svg.rect(lx, ly + 0.15, 0.35, 0.2, fill=fill, stroke=INK, sw=0.01)
    svg.text(lx + 0.45, ly + 0.3, "part: label, width x length", size=0.1)
    svg.rect(lx, ly + 0.5, 0.35, 0.2, fill="#f4f4f4", stroke="#888", sw=0.008, dash="0.06,0.04")
    svg.text(lx + 0.45, ly + 0.65, f"offcut to keep (>= {_sz(MIN_OFFCUT)}\")", size=0.1)
    hatch(svg, lx, ly + 0.85, 0.35, 0.2, spacing=0.05, sw=0.006, stroke="#999")
    svg.rect(lx, ly + 0.85, 0.35, 0.2, stroke="#999", sw=0.006)
    svg.text(lx + 0.45, ly + 1.0, "scrap", size=0.1)
    svg.text(lx, ly + 1.3, "T = turned 90 degrees", size=0.1)
    svg.text(lx, ly + 1.48, "A, B ... = rip strips, top down", size=0.1)
    svg.text(lx, ly + 1.66, "B1-GL = base 1, gable left", size=0.1)
    svg.text(lx, ly + 1.84, "U2-DR = upper 2, door right", size=0.1)

    # cut order below the sheet, in columns
    steps = cut_steps(sheet)
    top = by + 0.6
    col_w, line_h, size = 5.2, 0.15, 0.1
    per_col = int((PAGE_H - m - top - 0.1) // line_h)
    svg.text(m + 0.1, top, "CUT ORDER", size=0.13, weight="bold")
    for n, line in enumerate(steps):
        col, row = divmod(n, per_col)
        if col > 2:
            svg.text(m + 0.1 + 2 * col_w, top + (per_col + 1) * line_h,
                     "... continued in the cut list (.md)", size=size, fill=HAIR)
            break
        svg.text(m + 0.1 + col * col_w, top + (row + 1) * line_h,
                 line[:95], size=size, family="DejaVu Sans Mono, monospace")
    return svg


def _round_end_path(x, y, w, h, r, turned: bool) -> str:
    """Outline with the two front corners rounded. The front is the far end of the
    piece's length: the right end on the sheet, or the bottom end when turned."""
    if not turned:      # length runs along x: round the right-hand corners
        return (f"M{x:.4f},{y:.4f} L{x + w - r:.4f},{y:.4f} A{r:.4f},{r:.4f} 0 0 1 {x + w:.4f},{y + r:.4f} "
                f"L{x + w:.4f},{y + h - r:.4f} A{r:.4f},{r:.4f} 0 0 1 {x + w - r:.4f},{y + h:.4f} "
                f"L{x:.4f},{y + h:.4f} Z")
    return (f"M{x:.4f},{y:.4f} L{x + w:.4f},{y:.4f} L{x + w:.4f},{y + h - r:.4f} "
            f"A{r:.4f},{r:.4f} 0 0 1 {x + w - r:.4f},{y + h:.4f} L{x + r:.4f},{y + h:.4f} "
            f"A{r:.4f},{r:.4f} 0 0 1 {x:.4f},{y + h - r:.4f} Z")


def summary_page(groups: dict[str, Group], title: str, cabs, kerf: float, pages: int) -> Svg:
    svg = Svg(PAGE_W, PAGE_H)
    m = 0.4
    svg.rect(m / 2, m / 2, PAGE_W - m, PAGE_H - m, stroke=INK, sw=0.014)
    svg.text(m + 0.1, m + 0.3, f"{title.upper()}  -  SHEET NESTING SUMMARY", size=0.26, weight="bold")
    svg.text(PAGE_W - m - 0.1, m + 0.3, f"page 1 of {pages}", size=0.13, anchor="end")
    svg.text(m + 0.1, m + 0.6,
             f'Sheets 48" x 96" (4x8)  -  kerf {fmt_in(kerf)}  -  panel saw rips strips, crosscut, '
             'then the table saw rips blocks to width  -  sheet pages drawn at ' + SCALE_TEXT,
             size=0.13)
    cols = [("Material", 0.0), ("Sheets", 4.6), ("Pieces", 5.6), ("Yield", 6.6),
            ("Offcuts kept", 7.6), ("Waste", 9.2), ("Cuts", 10.4), ("Grain", 11.3)]
    x0, y = m + 0.2, m + 1.2
    for name, dx in cols:
        svg.text(x0 + dx, y, name, size=0.14, weight="bold")
    svg.line(x0, y + 0.08, x0 + 12.5, y + 0.08, sw=0.01)
    rows = summary_rows(groups)
    for r in rows:
        y += 0.3
        vals = [r["material"], str(r["sheets"]), str(r["pieces"]), f"{r['yield']:.0f}%",
                f"{r['offcut_sqft']:.1f} sq ft", f"{r['waste_sqft']:.1f} sq ft", str(r["cuts"]),
                "yes" if r["grain"] else "no"]
        for (name, dx), v in zip(cols, vals):
            svg.text(x0 + dx, y, v, size=0.14)
    y += 0.3
    svg.line(x0, y - 0.18, x0 + 12.5, y - 0.18, sw=0.01)
    tot = lambda k: sum(r[k] for r in rows)
    area = tot("sheets") * 48 * 96 / 144
    svg.text(x0, y, "Total", size=0.14, weight="bold")
    for (name, dx), v in zip(cols[1:7], [str(tot("sheets")), str(tot("pieces")),
                                          f"{(area - tot('offcut_sqft') - tot('waste_sqft')) / area * 100:.0f}%" if area else "-",
                                          f"{tot('offcut_sqft'):.1f} sq ft", f"{tot('waste_sqft'):.1f} sq ft",
                                          str(tot("cuts"))]):
        svg.text(x0 + dx, y, v, size=0.14, weight="bold")

    big = oversize_pieces(groups)
    if big:
        y += 0.45
        svg.text(x0, y, "NOT NESTED - LONGER THAN STOCK SHEET, SEAM TBD (one continuous piece each):",
                 size=0.14, weight="bold", fill="#b00020")
        for key, p in big:
            y += 0.22
            svg.text(x0 + 0.2, y, f"{p.label}  {p.part}  -  {fmt_in(p.width)} x {fmt_in(p.length)}  -  {key}",
                     size=0.13, fill="#b00020")
    y += 0.7
    svg.text(x0, y, "CABINETS", size=0.15, weight="bold")
    svg.text(x0 + 6.5, y, "PART CODES", size=0.15, weight="bold")
    yy = y
    for name, code in _codes(cabs, groups):
        yy += 0.22
        svg.text(x0, yy, f"{code}  =  {name}", size=0.13)
    yy = y
    items = list(CODE_MEANING.items())
    for n, (c, meaning) in enumerate(items):
        col, row = divmod(n, 9)
        svg.text(x0 + 6.5 + col * 4.0, y + 0.22 * (row + 1), f"{c}  =  {meaning}", size=0.13)
    svg.text(x0, PAGE_H - m - 0.25,
             "Yield = part area / sheet area. Offcuts are leftovers at least "
             f"{_sz(MIN_OFFCUT)}\" each way; smaller leftovers and kerf count as waste. "
             "Back panels (1/2\") are nested on their own sheets.", size=0.12, fill=HAIR)
    return svg


def write_project_nest(groups: dict[str, Group], out_dir: Path, stem: str, title: str,
                       cabs, kerf: float = KERF) -> list[Path]:
    """PDF (summary + one page per sheet), cut list .csv and .md. Returns the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = out_dir / f"{stem}-nest-pages"
    pages_dir.mkdir(exist_ok=True)
    for old in pages_dir.glob("*.svg"):
        old.unlink()
    total = 1 + sum(len(g.sheets) for g in groups.values())
    svgs = []
    first = pages_dir / "p01-summary.svg"
    summary_page(groups, title, cabs, kerf, total).write(str(first))
    svgs.append(first)
    page = 1
    for g in groups.values():
        safe = re.sub(r"[^a-z0-9]+", "-", g.key.lower()).strip("-")
        for sh in g.sheets:
            page += 1
            path = pages_dir / f"p{page:02d}-{safe}-{sh.index}.svg"
            sheet_page(sh, g, title, page, total).write(str(path))
            svgs.append(path)
    written = []
    pdf = out_dir / f"{stem}-nest.pdf"
    if _svgs_to_pdf(svgs, pdf):
        written.append(pdf)
    csv_path = out_dir / f"{stem}-nest-cutlist.csv"
    csv_path.write_text(cutlist_csv(groups), encoding="utf-8")
    md_path = out_dir / f"{stem}-nest-cutlist.md"
    md_path.write_text(cutlist_text(groups, title, cabs, kerf), encoding="utf-8")
    written += [csv_path, md_path]
    return written


def _svgs_to_pdf(svgs: list[Path], pdf: Path) -> bool:
    rsvg = shutil.which("rsvg-convert")
    if not rsvg:
        return False
    res = subprocess.run([rsvg, "-f", "pdf", "-o", str(pdf)] + [str(s) for s in svgs],
                         capture_output=True, text=True)
    return res.returncode == 0 and pdf.is_file()
