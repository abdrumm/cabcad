"""Coppinger Exhibits branding for client output (Brook, Oct 30).

Small but on every client page and image: the logo in the title block of every client
sheet page, and a corner mark on renders and image exports. Minimal, in the spirit of
Dieter Rams: one accent colour (navy), thin rules, lots of white space.

The logo is the PLACEHOLDER traced from the website PNG
(assets/branding/coppinger/coppinger-logo-traced.svg). Swap in the official master from
marketing by replacing that file; nothing else changes.
"""
from __future__ import annotations

import base64
import functools
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "assets" / "branding" / "coppinger" / "coppinger-logo-traced.svg"

COMPANY = "Coppinger Exhibits"
STREET = "9955 Westpoint Dr, Suite 150"
CITY = "Indianapolis, IN 46256"
PHONE = "(317) 913-1400"
ADDRESS_LINE = f"{COMPANY} · {STREET} · {CITY} · {PHONE}"

NAVY = "#263460"          # the one accent colour
RULE = "#c9ced4"          # hairlines
INK = "#1f2933"
SOFT = "#6b7785"


@functools.lru_cache(maxsize=1)
def _logo() -> tuple[str, float, float]:
    """(inner SVG markup, viewBox width, height) of the logo file."""
    text = LOGO.read_text(encoding="utf-8")
    m = re.search(r"<svg\b([^>]*)>(.*)</svg>", text, re.S)
    if not m:
        raise ValueError(f"{LOGO} is not an SVG")
    attrs, inner = m.group(1), m.group(2)
    vb = re.search(r'viewBox="([\d.\s-]+)"', attrs)
    if vb:
        _x, _y, w, h = (float(v) for v in vb.group(1).split())
    else:
        w = float(re.search(r'width="([\d.]+)', attrs).group(1))
        h = float(re.search(r'height="([\d.]+)', attrs).group(1))
    return inner.strip(), w, h


def logo_aspect() -> float:
    _inner, w, h = _logo()
    return w / h


def logo_svg(x: float, y: float, height: float, opacity: float = 1.0) -> str:
    """The logo as a nested <svg> at (x, y), `height` tall, in the page's units."""
    inner, w, h = _logo()
    width = height * w / h
    op = f' opacity="{opacity:g}"' if opacity < 1 else ""
    return (f'<svg x="{x:.4f}" y="{y:.4f}" width="{width:.4f}" height="{height:.4f}" '
            f'viewBox="0 0 {w:g} {h:g}" preserveAspectRatio="xMinYMid meet"{op}>{inner}</svg>')


def logo_data_uri() -> str:
    """For HTML pages (AR phone page, email bodies)."""
    return "data:image/svg+xml;base64," + base64.b64encode(LOGO.read_bytes()).decode("ascii")


def corner_mark(page_w: float, page_h: float, height: float | None = None,
                margin: float | None = None, corner: str = "br", opacity: float = 0.9) -> str:
    """A small logo in one corner of an image (renders, image exports)."""
    height = height or max(page_h * 0.045, 1e-6)
    margin = page_h * 0.03 if margin is None else margin
    width = height * logo_aspect()
    x = page_w - margin - width if "r" in corner else margin
    y = page_h - margin - height if "b" in corner else margin
    return logo_svg(x, y, height, opacity)
