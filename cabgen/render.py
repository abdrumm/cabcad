"""Render: a clean still of the job for the client (Brook, Oct 30).

The shaded 3D view of the client sheet, alone on a quiet neutral ground, with the
Coppinger logo small in the corner and the job name opposite. Uses the job's finish
picks (the same palette as the client sheet and AR). One angle for now; PNG via
rsvg-convert. Studio lighting and more angles come with a real renderer later.

    python3 -m cabgen.cli render jobs/sample-kitchen.csv --out out/render
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import branding as br
from .svg import Svg

W, H = 12.0, 8.0            # inches; 150 dpi -> 1800 x 1200 px
GROUND = "#f3f3f1"


def render_svg(job, phi_deg: float = 32.0) -> Svg:
    from .client_sheet import iso_view, palette_for
    svg = Svg(W, H, bg=GROUND)
    with palette_for(job):
        iso_view(svg, job, (0.6, 0.35, W - 1.2, H - 1.25), phi_deg=phi_deg, heading=False,
                 dims=False, floor_fill="#e9e9e6", wall_fill=GROUND)
    svg.line(0.6, H - 0.62, W - 0.6, H - 0.62, stroke=br.RULE, sw=0.008)
    svg.text(0.6, H - 0.3, job.name, size=0.17, weight="bold", fill=br.INK)
    client = (job.settings or {}).get("client")
    if client:
        svg.text(0.6 + len(job.name) * 0.17 * 0.62 + 0.25, H - 0.3, client, size=0.13, fill=br.SOFT)
    svg.group(br.corner_mark(W, H, height=0.36, margin=0.22, corner="br"))
    return svg


def write_render(job, out_dir: Path, stem: str = "render", dpi: int = 150) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / f"{stem}.svg"
    render_svg(job).write(str(svg_path))
    rsvg = shutil.which("rsvg-convert")
    if not rsvg:
        raise RuntimeError("rsvg-convert is not installed; it turns the render into a PNG")
    png = out_dir / f"{stem}.png"
    subprocess.run([rsvg, "-f", "png", "-d", str(dpi), "-p", str(dpi), "-b", GROUND,
                    "-o", str(png), str(svg_path)], check=True, capture_output=True)
    return png
