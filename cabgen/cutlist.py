"""Cut list output: a shop-table friendly CSV plus a markdown version."""

from __future__ import annotations

import csv
import io

from .parts import Part
from .units import fmt_in


def to_csv(parts: list[Part]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["QTY", "PART", "MATERIAL", "THICKNESS", "WIDTH", "LENGTH", "EB", "EDGE BANDING", "LAMINATE", "NOTES"])
    for part in parts:
        w.writerow([
            part.qty,
            part.name,
            part.material,
            fmt_in(part.thk),
            fmt_in(part.width),
            fmt_in(part.length),
            part.eb,
            part.banding,
            part.laminate,
            part.notes,
        ])
    return buf.getvalue()


def to_markdown(parts: list[Part]) -> str:
    out = ["| QTY | PART | MATERIAL | THK | WIDTH | LENGTH | EB | EDGE BANDING | LAMINATE | NOTES |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for part in parts:
        out.append(
            f"| {part.qty} | {part.name} | {part.material} | {fmt_in(part.thk)} | "
            f"{fmt_in(part.width)} | {fmt_in(part.length)} | {part.eb} | {part.banding} | "
            f"{part.laminate} | {part.notes} |"
        )
    return "\n".join(out) + "\n"


def to_table_saw_sheet(parts: list[Part]) -> str:
    """One line per piece, the way it is read off a cut list on the saw."""
    out = []
    for part in parts:
        for i in range(part.qty):
            tag = "" if part.qty == 1 else f"  #{i + 1}"
            out.append(
                f"{fmt_in(part.length):>10}  x {fmt_in(part.width):>10}  x {fmt_in(part.thk):>8}"
                f"   {part.material:<16} {part.name}{tag}"
            )
    return "\n".join(out) + "\n"
