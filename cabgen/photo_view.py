"""Photorealistic still of the current job.

Brook remembers a Blender render of his cabinets staged in a kitchen. That
scene is not in this git repository: no ``.blend``, no Cycles script, and no
commit on any branch mentions Blender. ``cabgen.render`` is the flat shaded
still, and it says a real renderer is still to come. This module does not
invent that kitchen or call the flat still a photorealistic view.

When the iMac archive is copied into place, the button renders the current
design through that pipeline and caches the PNG. Until then it explains what
is missing. Nothing here calls a paid render service.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
import subprocess
from pathlib import Path

# Where to put the archived stage on the machine that has it. Not created here.
DEFAULT_DIR = Path.home() / "Work" / "cabcad-blender"


def fingerprint(job) -> str:
    """Stable id of the design. Ordinary form edits that do not change it reuse the cache."""
    settings = job.settings or {}
    cabs = []
    for cab in job.cabs:
        p = cab.params
        cabs.append({
            "name": cab.name, "style": p.style, "run": cab.run,
            "width": p.width, "height": p.height, "depth": p.depth,
            "toe": p.toe_kick_h, "recess": p.toe_kick_recess,
            "x": round(cab.x, 4),
        })
    payload = {
        "name": job.name,
        "counter": settings.get("counter"),
        "finishes": {k: settings.get(k) for k in
                     ("finish_fronts", "finish_box", "finish_counter")},
        "cabs": cabs,
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def discover() -> dict:
    """The Blender binary, the stage file, and the script that applies a CabCAD job.

    All three have to be on the machine. A binary alone is not the old kitchen.
    """
    folder = Path(os.environ.get("CABCAD_BLENDER_DIR", DEFAULT_DIR))
    blender = os.environ.get("CABCAD_BLENDER") or ""
    scene = Path(os.environ.get("CABCAD_BLENDER_SCENE", folder / "scene.blend"))
    script = Path(os.environ.get("CABCAD_BLENDER_SCRIPT", folder / "render_job.py"))
    binary = Path(blender) if blender else None
    if binary is None or not binary.is_file():
        found = shutil.which("blender")
        binary = Path(found) if found else None
    ready = bool(binary and binary.is_file() and scene.is_file() and script.is_file())
    return {"ready": ready, "blender": binary, "scene": scene, "script": script, "folder": folder}


def _missing_page(job, info: dict) -> str:
    folder = html.escape(str(info["folder"]))
    binary = html.escape(str(info["blender"] or "not found"))
    scene = html.escape(str(info["scene"]))
    script = html.escape(str(info["script"]))
    scene_ok = "found" if info["scene"].is_file() else "missing"
    script_ok = "found" if info["script"].is_file() else "missing"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Photorealistic view</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 42rem;
         line-height: 1.45; color: #1f2933; }}
  h1 {{ font-size: 1.3rem; }}
  .warn {{ background: #f59e0b22; border: 1px solid #f59e0b66; padding: .7rem .9rem;
          border-radius: 8px; }}
  code {{ font-size: .9em; }}
</style></head><body>
<h1>Photorealistic view is not available</h1>
<p class="warn">This is not the earlier Blender kitchen still, and CabCAD did not
invent a substitute. No Blender scene or render script is in the git repository,
on any branch.</p>
<p>The flat shaded PNG from <code>cabgen render</code> is a different picture.
Studio lighting was left for a real renderer and was never checked in.</p>
<p>Job: {html.escape(job.name)}. Nothing was rendered.</p>
<h2>What to copy off the iMac</h2>
<p>The working master is <code>~/Work/cabcad</code> (older tree:
<code>~/Work/cabinet-gen</code>). Search there, and the rest of <code>~/Work</code>,
for the <code>.blend</code> Brook remembers, the Python driver that builds the
stage from a CabCAD job, and the HDR or texture files that scene links. Also note
the Blender version (<code>blender --version</code>).</p>
<p>Put them here, or point the environment variables at them:</p>
<ul>
  <li>Folder: <code>{folder}</code></li>
  <li>Scene ({scene_ok}): <code>{scene}</code> or <code>CABCAD_BLENDER_SCENE</code></li>
  <li>Script ({script_ok}): <code>{script}</code> or <code>CABCAD_BLENDER_SCRIPT</code>.
      It must read the job JSON CabCAD passes and render <em>this</em> design.</li>
  <li>Binary ({binary}): <code>CABCAD_BLENDER</code> if it is not on <code>PATH</code></li>
</ul>
<p>The script is started as
<code>blender -b &lt;scene&gt; -P &lt;script&gt; -- &lt;job.json&gt; &lt;out.png&gt;</code>.
A second click with the same design reuses the PNG and does not render again.</p>
</body></html>
"""


def _result_page(job, png_name: str, cached: bool) -> str:
    word = "Cached still. The design did not change, so Blender was not run again." if cached \
        else "Rendered from the current design."
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(job.name)} — photorealistic</title>
<style>body {{ font-family: system-ui, sans-serif; margin: 1rem auto; max-width: 64rem; }}
img {{ max-width: 100%; }}</style></head><body>
<h1>{html.escape(job.name)}</h1>
<p>{word}</p>
<p><img src="/files/{html.escape(png_name)}" alt="Photorealistic view of {html.escape(job.name)}"></p>
</body></html>
"""


def run_blender(binary: Path, scene: Path, script: Path, job_json: Path, png: Path) -> None:
    """One headless render. Tests replace this. A missing tool raises."""
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(binary), "-b", str(scene), "-P", str(script), "--", str(job_json), str(png)],
        check=True, capture_output=True, timeout=60 * 30,
    )


def render_photo(job, out_dir: Path) -> tuple[str, bool]:
    """HTML for the new tab, and whether a new render was started.

    A cached PNG for this design is returned without calling Blender.
    """
    out_dir = Path(out_dir)
    fp = fingerprint(job)
    cache_dir = out_dir / "photo"
    png = cache_dir / f"{fp}.png"
    if png.is_file() and png.stat().st_size > 0:
        return _result_page(job, f"photo/{fp}.png", cached=True), False
    info = discover()
    if not info["ready"]:
        return _missing_page(job, info), False
    cache_dir.mkdir(parents=True, exist_ok=True)
    job_json = cache_dir / f"{fp}.json"
    job_json.write_text(json.dumps({"name": job.name, "fingerprint": fp}, indent=2),
                        encoding="utf-8")
    try:
        run_blender(info["blender"], info["scene"], info["script"], job_json, png)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        if png.is_file():
            png.unlink()
        info = dict(info)
        page = _missing_page(job, info)
        page = page.replace(
            "Nothing was rendered.",
            "Nothing was rendered. Blender was started and failed: " + html.escape(str(exc)[:500]),
        )
        return page, True
    if not png.is_file() or png.stat().st_size == 0:
        return _missing_page(job, info).replace(
            "Nothing was rendered.",
            "Nothing was rendered. Blender exited without writing a PNG.",
        ), True
    return _result_page(job, f"photo/{fp}.png", cached=False), True
