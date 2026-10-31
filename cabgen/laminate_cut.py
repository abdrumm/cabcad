"""Laminate cut list: every skin, by catalogue number, plus edge-band footage.

Edge banding is not cut from these sheets. It is totaled in linear feet with
10% waste, one total per colour.

Sizes are the finished face plus ``OVERAGE`` (1/2\") each way, for trimming.
That is the same 1/2\" per side the shop already uses for contact cement.

Sheet count is a simple shelf nest with no saw kerf (laminate is cut with a
knife, pieces may touch). Grain pieces are not turned: the grain runs along
the long direction of a 4x8 (48 x 96) or a 5x12 (60 x 144). A piece that
does not fit that way is still counted as its own sheet and called out.
This is not a perfect nest.

Doors and drawer fronts are balanced: the same laminate on both faces.
Set ``BALANCE_FRONTS`` false if a job is one face only.

A finished end gets a skin of the case laminate on the outside face. The
blank is the full height by the depth. On a base the toe-kick notch is then
cut out of that same piece. It is not a solid un-notched rectangle.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from .edgeband import LEGEND, band_inches
from .finishes import (
    drawing_label, is_woodgrain, job_top_spec, lookup, needs_laminate_skin,
    resolved_finished_ends,
)
from .parts import build_parts
from .svg import Svg
from .units import fmt_in

# 1/2" each way, so each dimension grows by 1".
OVERAGE = 0.5
# Extra PVC ordered on top of the measured length.
BAND_WASTE = 0.10
# Both faces of a door or drawer front, same laminate.
BALANCE_FRONTS = True

SHEET_4X8 = (48.0, 96.0)     # across, along
SHEET_5X12 = (60.0, 144.0)

PAGE_W, PAGE_H = 17.0, 11.0


@dataclass
class LamRow:
    spec: str
    display: str
    cabinet: str
    part: str
    face: str
    grain: str            # "" or "along length" or "along the height"
    grain_along: str      # "" | "length" | "width"  (which cut dimension follows the sheet)
    finished_w: float
    finished_l: float
    qty: int = 1
    note: str = ""

    @property
    def cut_w(self) -> float:
        return self.finished_w + 2 * OVERAGE

    @property
    def cut_l(self) -> float:
        return self.finished_l + 2 * OVERAGE


@dataclass
class BandTotal:
    spec: str
    display: str
    inches: float = 0.0

    @property
    def feet(self) -> float:
        return self.inches / 12.0

    @property
    def feet_with_waste(self) -> float:
        return self.feet * (1 + BAND_WASTE)


@dataclass
class LaminateTakeoff:
    rows: list[LamRow] = field(default_factory=list)
    bands: list[BandTotal] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def sheets(self, spec: str) -> tuple[int, int]:
        pieces = []
        for row in self.rows:
            if row.spec != spec:
                continue
            pieces.extend([(row.cut_w, row.cut_l, row.grain_along)] * row.qty)
        return (
            sheet_count(pieces, *SHEET_4X8),
            sheet_count(pieces, *SHEET_5X12),
        )


def _display(spec: str) -> str:
    text = str(spec or "").strip()
    if not text:
        return "color TBD"
    return drawing_label(text) or text


def _grain(spec: str, along: str) -> tuple[str, str]:
    """(words, grain_along). ``along`` is ``length`` or ``width``."""
    if is_woodgrain(spec):
        if along == "width":
            return "along the height", "width"
        return "along the length", "length"
    return "", ""


def _row(spec, cabinet, part, face, fw, fl, qty=1, note="", grain_axis="length") -> LamRow:
    words, axis = _grain(spec, grain_axis)
    return LamRow(
        spec=spec, display=_display(spec), cabinet=cabinet, part=part, face=face,
        grain=words, grain_along=axis, finished_w=fw, finished_l=fl, qty=qty, note=note,
    )


def _skins(cabinet: str, part, params, kickplate_on: bool) -> list[LamRow]:
    name = part.name
    low = name.lower()
    out: list[LamRow] = []
    if low.startswith("door") or low.startswith("drawer front") or low.startswith("false front"):
        spec = str(params.finish_doors or "").strip()
        if needs_laminate_skin(spec):
            faces = ["front face", "back face (balanced)"] if BALANCE_FRONTS else ["front face"]
            for face in faces:
                out.append(_row(
                    spec, cabinet, name, face, part.width, part.length, part.qty,
                    note="Grain runs up the door." if is_woodgrain(spec) else "",
                    grain_axis="length",
                ))
        return out
    if low.startswith("gable"):
        spec = str(params.finish_case or "").strip()
        ends = resolved_finished_ends(params)
        count = {"both": 2, "left": 1, "right": 1}.get(ends, 0)
        if count and needs_laminate_skin(spec):
            if params.has_toe_kick:
                note = (
                    f"Outside face. Blank is the full height by the depth. "
                    f"Then cut the toe-kick notch {fmt_in(params.toe_kick_recess)} deep by "
                    f"{fmt_in(params.toe_kick_h)} high out of this one piece. Not a solid rectangle."
                )
            else:
                note = "Outside face of the finished end."
            which = {"left": "left", "right": "right", "both": "both ends"}[ends]
            out.append(_row(
                spec, cabinet, f"Finished end ({which})", "outside face",
                part.width, part.length, count, note=note, grain_axis="width",
            ))
        return out
    if low.startswith("toe kick plate") and not kickplate_on:
        spec = str(params.finish_case or "").strip()
        if needs_laminate_skin(spec):
            out.append(_row(
                spec, cabinet, name, "front face", part.width, part.length, part.qty,
                note="The face of the toe kick. Skipped when a finished kick plate covers it.",
            ))
        return out
    if low.startswith("spacer"):
        spec = str(params.finish_case or "").strip()
        if needs_laminate_skin(spec):
            out.append(_row(
                spec, cabinet, name, "exposed face", part.width, part.length, part.qty,
                note="The filler board in the cut list. Not a full-height skin.",
            ))
        return out
    spec_in = str(params.finish_interior or "").strip()
    if not needs_laminate_skin(spec_in):
        return out
    if low.startswith("open shelf"):
        for face in ("top face", "bottom face"):
            out.append(_row(
                spec_in, cabinet, name, face, part.width, part.length, part.qty,
                note="Open shelf, both faces show.",
            ))
    elif low.startswith("shelf") or low.startswith("bottom plate") or low.startswith("top plate"):
        out.append(_row(
            spec_in, cabinet, name, "inside face", part.width, part.length, part.qty,
        ))
    elif low.startswith("back panel"):
        out.append(_row(
            spec_in, cabinet, name, "room face", part.width, part.length, part.qty,
        ))
    elif low.startswith("gable"):
        pass
    return out


def _interiors_inside_gables(cabinet, params) -> list[LamRow]:
    """Inside faces of the sides, when the interior is a real laminate."""
    spec = str(params.finish_interior or "").strip()
    if not needs_laminate_skin(spec):
        return []
    # The outside of a finished end is a separate case skin. This is the inside.
    return [_row(
        spec, cabinet, "Side, inside", "inside face",
        params.case_top_z, params.gable_depth, 2,
        note="Inside face of each side. The outside finished end, if there is one, is the case laminate.",
        grain_axis="width",
    )]


def build_takeoff(cabs, settings: dict | None = None) -> LaminateTakeoff:
    """Skins and edge-band footage for these cabinets. Counter included when it is laminate."""
    settings = settings or {}
    kick_on = str(settings.get("kickplate") or "").strip().lower() in ("yes", "y", "true", "on", "1")
    rows: list[LamRow] = []
    bands: dict[str, BandTotal] = {}
    for cab in cabs:
        parts, _layout = build_parts(cab.params)
        for part in parts:
            rows.extend(_skins(cab.name, part, cab.params, kick_on))
            if not (part.eb or "").strip():
                continue
            spec = str(getattr(part, "eb_spec", "") or "").strip()
            key = spec or "(no colour named)"
            total = bands.get(key)
            if total is None:
                total = BandTotal(spec=spec, display=_display(spec) if spec else "colour not named")
                bands[key] = total
            total.inches += band_inches(part)
        rows.extend(_interiors_inside_gables(cab.name, cab.params))
    counter = None
    if cabs and settings:
        from .counter import build_counter
        counter = build_counter(cabs, settings)
    if counter is not None and counter.kind == "laminate":
        spec = job_top_spec(cabs, settings)
        for lp in counter.laminate:
            rows.append(_row(
                spec, "Countertop", lp.name, "show face", lp.width, lp.length, 1,
                note="Counter laminate, in the order it goes on (sides, front, top, then splashes).",
                grain_axis="length",
            ))
    takeoff = LaminateTakeoff(rows=rows, bands=list(bands.values()))
    takeoff.assumptions = [
        f"Each laminate piece is the finished face plus {fmt_in(OVERAGE)} each way, for trimming.",
        "Doors and drawer fronts are balanced: the same laminate on both faces.",
        "A finished end skin is the outside face only. On a base, cut the toe-kick notch out of that one piece.",
        "Blank case or interior means white melamine, the sheet itself, not a laminate skin.",
        "Drawer boxes stay melamine. Their banded edges are in the edge-band footage, not on a sheet.",
        "Edge banding is not cut from these sheets.",
        f"Edge band footage is the measured length plus {BAND_WASTE * 100:.0f}% waste, in linear feet, per colour.",
        "Sheet count assumes a 4x8 (48 x 96) or a 5x12 (60 x 144), picked separately. "
        "Simple shelf nest, no saw kerf, pieces may touch. Woodgrain is not turned: "
        "the grain runs along the long direction of the sheet. A piece that does not fit is its own sheet.",
        "Colours are the flat screen colours in cabgen/laminates.csv, not manufacturer swatches.",
        "White (TBD), Black (TBD), Woodgrain (TBD) and Grey (TBD) are labeled color TBD on the drawings.",
    ]
    return takeoff


def _specs(takeoff: LaminateTakeoff) -> list[str]:
    seen = []
    for row in takeoff.rows:
        if row.spec not in seen:
            seen.append(row.spec)
    for band in takeoff.bands:
        if band.spec not in seen:
            seen.append(band.spec)
    return seen


def to_laminate_csv(takeoff: LaminateTakeoff) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "LAMINATE", "LABEL", "CABINET", "PART", "FACE", "GRAIN",
        "FINISHED WIDTH", "FINISHED LENGTH", "CUT WIDTH", "CUT LENGTH", "QTY", "NOTE",
    ])
    for row in takeoff.rows:
        w.writerow([
            row.spec, row.display, row.cabinet, row.part, row.face, row.grain,
            fmt_in(row.finished_w), fmt_in(row.finished_l),
            fmt_in(row.cut_w), fmt_in(row.cut_l), row.qty, row.note,
        ])
    w.writerow([])
    w.writerow([
        "LAMINATE", "LABEL", "SHEETS 4x8 (48x96)", "SHEETS 5x12 (60x144)",
        "EDGE BAND LF", "EDGE BAND LF +10%",
    ])
    band_by = {b.spec: b for b in takeoff.bands}
    listed = set()
    for spec in _specs(takeoff):
        n4, n5 = takeoff.sheets(spec) if any(r.spec == spec for r in takeoff.rows) else (0, 0)
        band = band_by.get(spec)
        listed.add(spec)
        w.writerow([
            spec,
            _display(spec) if spec else "colour not named",
            n4, n5,
            f"{band.feet:.2f}" if band else "0.00",
            f"{band.feet_with_waste:.2f}" if band else "0.00",
        ])
    for spec, band in band_by.items():
        if spec in listed:
            continue
        w.writerow([spec, band.display, 0, 0, f"{band.feet:.2f}", f"{band.feet_with_waste:.2f}"])
    return buf.getvalue()


def sheet_count(pieces: list[tuple[float, float, str]], sheet_w: float, sheet_l: float) -> int:
    """How many sheets. ``pieces`` are ``(cut_w, cut_l, grain_along)``.

    ``sheet_w`` is the short side, ``sheet_l`` the long (grain) side.
    ``grain_along`` ``length`` keeps cut_l parallel to sheet_l.
    ``width`` keeps cut_w parallel to sheet_l. Blank may turn.
    """
    oversize = 0
    pending = []
    for cut_w, cut_l, grain in pieces:
        opts = _orientations(cut_w, cut_l, grain, sheet_w, sheet_l)
        if not opts:
            oversize += 1
        else:
            pending.append(opts)
    pending.sort(key=lambda opts: -min(o[1] for o in opts))
    sheets: list[list[list[float]]] = []
    for opts in pending:
        if any(_place(shelves, opts, sheet_w, sheet_l) for shelves in sheets):
            continue
        shelves = []
        if _place(shelves, opts, sheet_w, sheet_l):
            sheets.append(shelves)
        else:
            oversize += 1
    return len(sheets) + oversize


def _orientations(cut_w, cut_l, grain, sheet_w, sheet_l) -> list[tuple[float, float]]:
    opts = []

    def add(along, across):
        if along <= sheet_l + 1e-6 and across <= sheet_w + 1e-6:
            pair = (round(along, 4), round(across, 4))
            if pair not in opts:
                opts.append(pair)

    if grain in ("", "length"):
        add(cut_l, cut_w)
    if grain in ("", "width"):
        add(cut_w, cut_l)
    return opts


def _place(shelves: list[list[float]], opts, sheet_w, sheet_l) -> bool:
    for along, across in opts:
        for shelf in shelves:
            if across <= shelf[0] + 1e-6 and shelf[1] + along <= sheet_l + 1e-6:
                shelf[1] += along
                return True
    used = sum(s[0] for s in shelves)
    for along, across in sorted(opts, key=lambda o: o[1]):
        if used + across <= sheet_w + 1e-6 and along <= sheet_l + 1e-6:
            shelves.append([across, along])
            return True
    return False


def laminate_pages(takeoff: LaminateTakeoff, title: str) -> list[Svg]:
    """One or more 11x17 pages. The summary sits on the last page."""
    header = 1.15
    footer = 2.4
    row_h = 0.16
    room = PAGE_H - header - footer
    per = max(8, int(room / row_h))
    chunks = [takeoff.rows[i:i + per] for i in range(0, len(takeoff.rows), per)] or [[]]
    pages = []
    total = len(chunks)
    for n, chunk in enumerate(chunks, start=1):
        last = n == total
        pages.append(_page(takeoff, title, chunk, n, total, summary=last))
    return pages


def _page(takeoff, title, rows, page, pages, summary: bool) -> Svg:
    svg = Svg(PAGE_W, PAGE_H)
    m = 0.4
    svg.rect(m / 2, m / 2, PAGE_W - m, PAGE_H - m, fill="none", stroke="#111", sw=0.014)
    svg.text(m + 0.1, m + 0.32, "LAMINATE CUT LIST", size=0.22, weight="bold")
    svg.text(PAGE_W - m - 0.15, m + 0.32, f"{title}   {page} of {pages}", size=0.12, anchor="end")
    svg.text(m + 0.1, m + 0.52,
             f"Cut size is finished size plus {fmt_in(OVERAGE)} each way. "
             "Edge banding is not on these sheets.",
             size=0.09, fill="#333")
    cols = [
        ("LAMINATE", 2.6), ("PART", 2.4), ("FACE", 2.2), ("GRAIN", 1.5),
        ("FINISHED", 1.5), ("CUT", 1.6), ("QTY", 0.5),
    ]
    y = m + 0.78
    x = m + 0.1
    for name, width in cols:
        svg.text(x, y, name, size=0.08, weight="bold")
        x += width
    svg.line(m + 0.1, y + 0.06, PAGE_W - m - 0.1, y + 0.06, stroke="#111", sw=0.006)
    y += 0.22
    for row in rows:
        vals = [
            row.display if row.display != row.spec else row.spec,
            f"{row.cabinet} / {row.part}" if row.cabinet else row.part,
            row.face,
            row.grain or "—",
            f"{fmt_in(row.finished_w)} x {fmt_in(row.finished_l)}",
            f"{fmt_in(row.cut_w)} x {fmt_in(row.cut_l)}",
            str(row.qty),
        ]
        x = m + 0.1
        for val, (_name, width) in zip(vals, cols):
            svg.text(x, y, val[:42], size=0.075)
            x += width
        y += 0.16
    if summary:
        y += 0.12
        svg.text(m + 0.1, y, "SHEETS AND EDGE BAND", size=0.12, weight="bold")
        y += 0.2
        svg.text(m + 0.1, y,
                 "4x8 is 48 x 96.  5x12 is 60 x 144.  Simple shelf nest, no kerf.  "
                 "Woodgrain is not turned.  Edge band is linear feet plus 10% waste.",
                 size=0.08, fill="#333")
        y += 0.18
        for spec in _specs(takeoff):
            n4, n5 = takeoff.sheets(spec) if any(r.spec == spec for r in takeoff.rows) else (0, 0)
            band = next((b for b in takeoff.bands if b.spec == spec), None)
            feet = f"{band.feet_with_waste:.1f} lf band incl. waste" if band else "no edge band"
            label = _display(spec) if spec else "colour not named"
            svg.text(m + 0.15, y, f"{label}:  {n4} sheet(s) of 4x8,  {n5} of 5x12,  {feet}", size=0.085)
            y += 0.16
            if y > PAGE_H - 1.3:
                break
        y = min(y + 0.08, PAGE_H - 1.15)
        svg.text(m + 0.1, y, "ASSUMPTIONS", size=0.09, weight="bold")
        y += 0.14
        for line in takeoff.assumptions[:4]:
            svg.text(m + 0.1, y, line[:150], size=0.07, fill="#333")
            y += 0.12
    return svg


def write_laminate(cabs, settings, out_dir, stem: str, title: str) -> tuple[list, object]:
    """Write ``<stem>-laminate-cutlist.csv`` and return SVG pages plus the takeoff."""
    takeoff = build_takeoff(cabs, settings)
    path = out_dir / f"{stem}-laminate-cutlist.csv"
    path.write_text(to_laminate_csv(takeoff), encoding="utf-8")
    return laminate_pages(takeoff, title), takeoff


# Re-export so a drawing legend can import one place.
__all__ = ["LEGEND", "OVERAGE", "build_takeoff", "laminate_pages", "to_laminate_csv", "write_laminate"]
