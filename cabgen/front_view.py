"""Standalone front elevation, for the CE pipeline page.

One sheet: the front view of the whole cabinet run, with the same border and
title block as the client sheet. ``write_front_view`` also writes an HTML page
that embeds that drawing and links the job's render and AR files. CabCad
already writes both (``cabgen.render`` and ``cabgen.ar_export``). A file that
could not be written is a clearly marked placeholder link.

    python3 -m cabgen.cli front jobs/sample-kitchen.csv --out out/front
"""

from __future__ import annotations

import datetime as _dt
import html
import shutil
import subprocess
from pathlib import Path

from .client_sheet import (
    PAGE_H, PAGE_W, Svg, begin_sheet, front_elevation, palette_for,
)


def render_front(job, date: str | None = None) -> Svg:
    """The front elevation of the run, alone on an 11x17 sheet."""
    date = date or _dt.date.today().strftime("%B %-d, %Y")
    svg = Svg(PAGE_W, PAGE_H)
    with palette_for(job):
        (cx, cy, cw, ch), _lower = begin_sheet(svg, job, date, "Front elevation", page="1 of 1")
        front_elevation(svg, job, (cx, cy, cw, ch))
    return svg


def _inline_svg(svg: Svg) -> str:
    text = svg.to_string().split("?>", 1)[-1].strip()
    text = text.replace(f'width="{svg.width}in"', 'width="100%"', 1)
    return text.replace(f'height="{svg.height}in"', 'height="auto"', 1)


# (key, label, file name under the stem)
_LINKS = (
    ("render", "Render", "{stem}-render.png"),
    ("usdz", "AR — iPhone / iPad (USDZ)", "{stem}.usdz"),
    ("glb", "AR — Android (GLB)", "{stem}.glb"),
)


def pipeline_html(job, svg: Svg, stem: str, files: dict[str, str],
                  placeholders: set[str]) -> str:
    """A page that can be dropped into the CE pipeline: the elevation, then the links."""
    links = []
    for key, label, pattern in _LINKS:
        href = files.get(key) or pattern.format(stem=stem)
        if key in placeholders or key not in files:
            links.append(
                f'<a class="ce-link placeholder" href="{html.escape(href)}">'
                f'{html.escape(label)}'
                f'<span class="tag">Placeholder — file not produced</span></a>'
            )
        else:
            links.append(
                f'<a class="ce-link" href="{html.escape(href)}">{html.escape(label)}</a>'
            )
    note = ""
    if placeholders:
        note = ('<p class="sub">A dashed link is a placeholder. CabCad did not write that '
                'file for this job.</p>')
    title = html.escape(job.name)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — front elevation</title>
<style>
  body {{ margin: 0; background: #f4f5f6; color: #1f2933;
         font-family: system-ui, sans-serif; }}
  .ce-front {{ max-width: 1200px; margin: 0 auto; padding: 1.25rem 1rem 2rem; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 .25rem; }}
  .sub {{ margin: 0 0 .9rem; color: #6b7785; }}
  .ce-links {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 0 0 1rem; }}
  .ce-link {{ display: inline-flex; align-items: center; gap: .5rem;
             padding: .45rem .75rem; border: 1px solid #263460; border-radius: 6px;
             color: #263460; text-decoration: none; font-weight: 650; background: #fff; }}
  .ce-link.placeholder {{ border-style: dashed; color: #6b7785; }}
  .tag {{ font-size: .72rem; font-weight: 700; letter-spacing: .04em;
         text-transform: uppercase; color: #9a3412; }}
  .sheet {{ background: #fff; border: 1px solid #d5dae0; }}
  .sheet svg {{ display: block; }}
</style>
</head>
<body>
<article class="ce-front" id="ce-front-view">
<h1>{title}</h1>
<p class="sub">Front elevation of the cabinet run. This page is meant to drop into the CE pipeline.</p>
<nav class="ce-links" aria-label="Render and AR">{''.join(links)}</nav>
{note}<div class="sheet">
{_inline_svg(svg)}
</div>
</article>
</body>
</html>
"""


def _pdf(svg_path: Path) -> Path | None:
    rsvg = shutil.which("rsvg-convert")
    if not rsvg:
        return None
    pdf = svg_path.with_suffix(".pdf")
    subprocess.run([rsvg, "-f", "pdf", "-o", str(pdf), str(svg_path)], check=True,
                   capture_output=True)
    return pdf


def write_front_view(job, out_dir, stem: str = "front-view", date: str | None = None,
                     companions: bool = True) -> dict:
    """Write ``<stem>.svg``, ``.pdf`` (when rsvg-convert is installed) and ``.html``.

    With ``companions``, also write the render PNG and the AR files (USDZ and GLB)
    next to the page and link them. Anything that cannot be written stays a
    placeholder link on the page.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    svg = render_front(job, date)
    svg_path = out_dir / f"{stem}.svg"
    svg.write(str(svg_path))
    pdf = _pdf(svg_path)
    files: dict[str, str] = {}
    placeholders: set[str] = set()
    if companions:
        if shutil.which("rsvg-convert"):
            from .render import write_render
            png = write_render(job, out_dir, f"{stem}-render")
            files["render"] = png.name
        else:
            placeholders.add("render")
        try:
            from .ar_export import export_job
            res = export_job(job, out_dir, stem)
            files["usdz"] = Path(res["usdz"]).name
            files["glb"] = Path(res["glb"]).name
        except (OSError, RuntimeError, ValueError):
            placeholders.update(("usdz", "glb"))
    else:
        placeholders.update(key for key, _label, _pat in _LINKS)
    page = pipeline_html(job, svg, stem, files, placeholders)
    html_path = out_dir / f"{stem}.html"
    html_path.write_text(page, encoding="utf-8")
    return {"svg": svg_path, "pdf": pdf, "html": html_path, "files": files,
            "placeholders": placeholders}
