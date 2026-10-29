"""Minimal SVG writer. Units are inches; the page is set in real inches so
rsvg-convert/inkscape produce a true 11x17 PDF."""

from __future__ import annotations

from typing import Optional


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class Svg:
    def __init__(self, width: float, height: float, bg: str = "white"):
        self.width = width
        self.height = height
        self.bg = bg
        self.parts: list[str] = []

    # --- primitives ---------------------------------------------------------
    def rect(self, x, y, w, h, fill="none", stroke="black", sw=0.01, dash=None,
             extra: str = "") -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        e = f" {extra}" if extra else ""
        self.parts.append(
            f'<rect x="{x:.4f}" y="{y:.4f}" width="{w:.4f}" height="{h:.4f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{e}/>'
        )

    def line(self, x1, y1, x2, y2, stroke="black", sw=0.01, dash=None, cap="butt"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<line x1="{x1:.4f}" y1="{y1:.4f}" x2="{x2:.4f}" y2="{y2:.4f}" '
            f'stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}"{d}/>'
        )

    def path(self, d: str, fill="none", stroke="black", sw=0.01, dash=None):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da}/>'
        )

    def circle(self, cx, cy, r, fill="black", stroke="none", sw=0.01):
        self.parts.append(
            f'<circle cx="{cx:.4f}" cy="{cy:.4f}" r="{r:.4f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def poly(self, pts, fill="none", stroke="black", sw=0.01, dash=None):
        p = " ".join(f"{x:.4f},{y:.4f}" for x, y in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}"{da}/>'
        )

    def text(self, x, y, s, size=0.12, anchor="start", fill="black", rotate: Optional[float] = None,
             weight="normal", family="DejaVu Sans, Verdana, sans-serif") -> None:
        tr = f' transform="rotate({rotate:.2f} {x:.4f} {y:.4f})"' if rotate is not None else ""
        self.parts.append(
            f'<text x="{x:.4f}" y="{y:.4f}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" fill="{fill}"{tr}>'
            f"{_esc(s)}</text>"
        )

    def group(self, content: str) -> None:
        self.parts.append(content)

    # --- output -------------------------------------------------------------
    def to_string(self) -> str:
        bg = f'<rect x="0" y="0" width="{self.width}" height="{self.height}" fill="{self.bg}"/>'
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}in" '
            f'height="{self.height}in" viewBox="0 0 {self.width} {self.height}">\n'
            f"{bg}\n" + "\n".join(self.parts) + "\n</svg>\n"
        )

    def write(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_string())


def hatch(svg: Svg, x, y, w, h, spacing=0.08, sw=0.006, stroke="#666", angle=45) -> None:
    """Simple diagonal hatch fill for sectioned material (45 degrees)."""
    t = -h
    while t <= w:
        seg = _clip_line(x, y, w, h, x + t, y, x + t + h, y + h)
        if seg:
            svg.line(seg[0], seg[1], seg[2], seg[3], stroke=stroke, sw=sw)
        t += spacing


def _clip_line(x, y, w, h, x1, y1, x2, y2):
    """Liang-Barsky clip of a segment to a rectangle; returns the clipped
    segment or None."""
    dx = x2 - x1
    dy = y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - x), (dx, x + w - x1), (-dy, y1 - y), (dy, y + h - y1)):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return None
            t0 = max(t0, t)
        else:
            if t < t0:
                return None
            t1 = min(t1, t)
    if t0 > t1:
        return None
    return (x1 + t0 * dx, y1 + t0 * dy, x1 + t1 * dx, y1 + t1 * dy)
