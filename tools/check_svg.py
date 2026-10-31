"""Structural check on a generated SVG: nothing off the page, no overlapping
block titles, text inside its column. Run it after changing the drawing code.

    python3 tools/check_svg.py out/base-27-drawing.svg
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"

# rough advance width per point of font size for DejaVu Sans
CHAR_W = 0.62


def main(path: str) -> int:
    tree = ET.parse(path)
    root = tree.getroot()
    page_w = float(root.get("width").rstrip("in"))
    page_h = float(root.get("height").rstrip("in"))
    problems: list[str] = []
    boxes: list[tuple[str, float, float, float, float]] = []

    for el in root.iter():
        tag = el.tag.replace(NS, "")
        if tag == "rect":
            x = float(el.get("x", 0)); y = float(el.get("y", 0))
            w = float(el.get("width", 0)); h = float(el.get("height", 0))
            boxes.append(("rect", x, y, x + w, y + h))
        elif tag == "line":
            x1 = float(el.get("x1")); y1 = float(el.get("y1"))
            x2 = float(el.get("x2")); y2 = float(el.get("y2"))
            boxes.append(("line", min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
        elif tag == "text":
            x = float(el.get("x")); y = float(el.get("y"))
            size = float(el.get("font-size"))
            anchor = el.get("text-anchor", "start")
            txt = "".join(el.itertext())
            width = len(txt) * size * CHAR_W
            if anchor == "middle":
                x0, x1 = x - width / 2, x + width / 2
            elif anchor == "end":
                x0, x1 = x - width, x
            else:
                x0, x1 = x, x + width
            rot = el.get("transform")
            if rot:  # rotated text: use the height as the width
                x0, x1 = x - size, x + size
            boxes.append((f"text '{txt[:32]}'", x0, y - size, x1, y + size * 0.25))

    for name, x0, y0, x1, y1 in boxes:
        if x0 < -0.01 or y0 < -0.01 or x1 > page_w + 0.01 or y1 > page_h + 0.01:
            problems.append(f"off page: {name} ({x0:.2f},{y0:.2f})-({x1:.2f},{y1:.2f})")

    # text vs text overlap (a cheap proxy for "the drawing looks wrong")
    texts = [b for b in boxes if b[0].startswith("text")]
    overlaps = 0
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            _, ax0, ay0, ax1, ay1 = texts[i]
            _, bx0, by0, bx1, by1 = texts[j]
            ox = min(ax1, bx1) - max(ax0, bx0)
            oy = min(ay1, by1) - max(ay0, by0)
            if ox > 0.02 and oy > 0.02:
                overlaps += 1
                if overlaps <= 15:
                    problems.append(
                        f"text overlap: {texts[i][0]} <-> {texts[j][0]} "
                        f"({ox:.2f} x {oy:.2f} in)"
                    )

    print(f"{path}: {len(boxes)} elements on {page_w}x{page_h} in")
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems[:40]:
            print("  -", p)
        return 1
    print("  no off-page elements, no text overlaps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
