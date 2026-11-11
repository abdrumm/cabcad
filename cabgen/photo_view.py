"""Photorealistic still of the current job.

The original Blender kitchen was not in the git repo and was not on the iMac.
This starts the procedural script shipped in ``cabgen/blender/render_kitchen.py``.
It draws the job's real boxes, including the countertop build-up. It does not
call a paid renderer and it does not substitute an AI image.

Blender is not vendored. Set ``CABCAD_BLENDER`` to the absolute path of the
official 5.2.4 LTS binary (it is not on PATH):

    /home/abdrumm/.local/opt/blender-5.2.4-linux-x64/blender

One render runs at a time, in the background. The kitchen form does not wait
and does not start a render when it is only opened. A repeat of the same
design returns the cached PNG.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

from .blender.render_kitchen import SCRIPT_VERSION

# Proven on the shop iMac (i7-2600, no AVX2). Not on PATH. Parent sets the env var.
PROVEN_BLENDER = "/home/abdrumm/.local/opt/blender-5.2.4-linux-x64/blender"
BUNDLED_SCRIPT = Path(__file__).resolve().parent / "blender" / "render_kitchen.py"

_lock = threading.Lock()
_running: dict | None = None


def fingerprint(job) -> str:
    """Stable id of the design plus the script version. A repeat reuses the PNG."""
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
        "v": SCRIPT_VERSION,
        "name": job.name,
        "counter": settings.get("counter"),
        "splash": [settings.get("splash_left"), settings.get("splash_right")],
        "finishes": {k: settings.get(k) for k in
                     ("finish_fronts", "finish_box", "finish_counter")},
        "cabs": cabs,
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def export_boxes(job) -> list[dict]:
    """The boxes the still is built from, including perimeter build-up and the filler."""
    from .client_sheet import _filler_box
    from .finishes import paint_boxes

    boxes = list(job.boxes)
    paint_boxes(boxes, job.settings or {})
    filler = _filler_box(job)
    if filler is not None:
        boxes.append(filler)
    out = []
    for box in boxes:
        sx, sy, sz = (float(v) for v in box.size)
        if sx <= 1e-4 or sy <= 1e-4 or sz <= 1e-4:
            continue
        out.append({
            "name": box.name,
            "material": box.material or "",
            "color": box.color or "",
            "shape": box.shape or "",
            "pos": [float(v) for v in box.pos],
            "size": [sx, sy, sz],
        })
    return out


def job_payload(job) -> dict:
    denoise = os.environ.get("CABCAD_BLENDER_DENOISE", "0").strip() in ("1", "true", "yes")
    return {
        "name": job.name,
        "version": SCRIPT_VERSION,
        "samples": int(os.environ.get("CABCAD_BLENDER_SAMPLES", "32")),
        "width": int(os.environ.get("CABCAD_BLENDER_WIDTH", "960")),
        "height": int(os.environ.get("CABCAD_BLENDER_HEIGHT", "540")),
        "denoise": denoise,
        "boxes": export_boxes(job),
    }


def discover() -> dict:
    """The Blender binary. The scene script ships with CabCAD; no .blend is required."""
    raw = os.environ.get("CABCAD_BLENDER", "").strip()
    binary = Path(raw) if raw else None
    if binary is None or not binary.is_file():
        found = shutil.which("blender")
        binary = Path(found) if found else None
    ready = bool(binary and binary.is_file() and BUNDLED_SCRIPT.is_file())
    return {"ready": ready, "blender": binary, "script": BUNDLED_SCRIPT}


def png_name(fp: str) -> str:
    return f"photo-{fp}.png"


def _png(out_dir: Path, fp: str) -> Path:
    return Path(out_dir) / png_name(fp)


def _status_file(out_dir: Path, fp: str) -> Path:
    folder = Path(out_dir) / "photo"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{fp}.json"


def _write_status(out_dir: Path, fp: str, name: str, state: str, error: str = "") -> None:
    _status_file(out_dir, fp).write_text(json.dumps({
        "fp": fp, "name": name, "state": state, "error": error,
    }), encoding="utf-8")


def _read_status(out_dir: Path, fp: str) -> dict | None:
    path = Path(out_dir) / "photo" / f"{fp}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _page(title: str, body: str, refresh: str = "") -> str:
    meta = ""
    if refresh:
        meta = f'<meta http-equiv="refresh" content="4; url={html.escape(refresh, quote=True)}">'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">{meta}
<title>{html.escape(title)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 1.5rem auto; max-width: 46rem;
         line-height: 1.45; color: #1f2933; }}
  h1 {{ font-size: 1.25rem; }}
  img {{ max-width: 100%; height: auto; background: #fff; }}
  code {{ font-size: .92em; }}
  .warn {{ background: #f59e0b22; border: 1px solid #f59e0b66; padding: .7rem .9rem;
          border-radius: 8px; }}
</style></head><body>
{body}
</body></html>
"""


def _missing_page(job) -> str:
    binary = os.environ.get("CABCAD_BLENDER", "").strip() or "not set"
    return _page("Photorealistic view", f"""
<h1>Photorealistic view needs Blender</h1>
<p class="warn">CabCAD did not draw a picture. The old kitchen <code>.blend</code> was
not found. The new still is built by the script in this repo
(<code>cabgen/blender/render_kitchen.py</code>, version {SCRIPT_VERSION}) from the
current cabinet and countertop boxes. Blender itself is not in git.</p>
<p>Job: {html.escape(job.name)}. Nothing was rendered.</p>
<h2>Install on the iMac</h2>
<p>Official Blender <b>5.2.4 LTS</b>, portable Linux build, already run on this
i7-2600 (no AVX2, official <code>-march=x86-64-v2</code>, SSE4.2). It is not on
<code>PATH</code>. CPU only: no CUDA, OptiX, HIP or oneAPI. Denoise stays off
unless OpenImageDenoise can be set on the CPU; if it cannot, the still is
rendered without it.</p>
<pre>export CABCAD_BLENDER={html.escape(PROVEN_BLENDER)}</pre>
<p>Current <code>CABCAD_BLENDER</code>: <code>{html.escape(binary)}</code></p>
<p>A 64×64, 8-sample smoke frame on that machine was 3.2 seconds. That is not
the time for a kitchen. The demo frame is 960×540, 32 samples, denoise off,
one render at a time. Opening this form does not start it.</p>
""")


def _result_page(name: str, file_name: str, cached: bool) -> str:
    word = ("Cached still. The design did not change, so Blender was not run again."
            if cached else "Rendered from the current design.")
    return _page(name, f"""
<h1>{html.escape(name)}</h1>
<p>{word} Generic room, real cabinet and countertop geometry. Not the lost original scene.</p>
<p><img src="/files/{html.escape(file_name)}" alt="Photorealistic view of {html.escape(name)}"></p>
""")


def _progress_page(name: str, fp: str, busy: bool) -> str:
    href = f"/photo-status?fp={fp}"
    if busy:
        lead = ("A render is already running, so this one was not started. "
                "One still at a time. This page checks the render that is in progress.")
    else:
        lead = ("Rendering one still on the CPU. This tab refreshes. "
                "The kitchen form stays usable; opening it does not start another render.")
    return _page(name, f"""
<h1>{html.escape(name)}</h1>
<p>{lead}</p>
<p><a href="{html.escape(href)}">Check the still</a></p>
""", refresh=href)


def _error_page(name: str, detail: str) -> str:
    return _page(name or "Photorealistic view", f"""
<h1>Photorealistic view failed</h1>
<p class="warn">Blender ran and did not write a still. Nothing was invented in its place.</p>
<pre>{html.escape(detail[:1500])}</pre>
""")


def _idle_page() -> str:
    return _page("Photorealistic view", """
<h1>No render is running</h1>
<p>This page does not start one. Use Photorealistic view on the kitchen form.</p>
""")


def run_blender(binary: Path, script: Path, job_json: Path, png: Path) -> None:
    """One headless CPU render. Tests replace this."""
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(binary), "-b", "--factory-startup", "-P", str(script), "--",
         str(job_json), str(png)],
        check=True, capture_output=True, text=True, timeout=60 * 60,
    )


def _worker(name: str, fp: str, out_dir: Path, info: dict, payload: dict) -> None:
    global _running
    png = _png(out_dir, fp)
    error = ""
    try:
        folder = out_dir / "photo"
        folder.mkdir(parents=True, exist_ok=True)
        job_json = folder / f"{fp}.job.json"
        job_json.write_text(json.dumps(payload), encoding="utf-8")
        run_blender(info["blender"], info["script"], job_json, png)
        if not png.is_file() or png.stat().st_size < 32:
            error = "Blender exited without writing a PNG."
            if png.is_file():
                png.unlink()
    except subprocess.CalledProcessError as exc:
        error = (exc.stderr or exc.stdout or str(exc) or "Blender failed")[:1500]
    except (OSError, subprocess.TimeoutExpired) as exc:
        error = str(exc)
        if png.is_file() and png.stat().st_size < 32:
            png.unlink()
    _write_status(out_dir, fp, name, "error" if error else "done", error)
    with _lock:
        if _running and _running.get("fp") == fp:
            _running = None


def render_photo(job, out_dir: Path, *, block: bool = False) -> tuple[str, bool]:
    """HTML for the new tab, and whether a new render was started.

    ``block=True`` waits (tests). The web form uses the default and returns
    immediately. A cached PNG is returned without calling Blender.
    """
    global _running
    out_dir = Path(out_dir)
    fp = fingerprint(job)
    png = _png(out_dir, fp)
    if png.is_file() and png.stat().st_size > 32:
        return _result_page(job.name, png_name(fp), cached=True), False
    info = discover()
    if not info["ready"]:
        return _missing_page(job), False
    with _lock:
        if _running is not None:
            return _progress_page(job.name, _running["fp"], busy=True), False
        _running = {"fp": fp}
    _write_status(out_dir, fp, job.name, "running")
    thread = threading.Thread(
        target=_worker, args=(job.name, fp, out_dir, info, job_payload(job)), daemon=True)
    thread.start()
    if block:
        thread.join()
        status = _read_status(out_dir, fp) or {}
        if status.get("state") == "error":
            return _error_page(job.name, status.get("error") or "render failed"), True
        if png.is_file():
            return _result_page(job.name, png_name(fp), cached=False), True
        return _error_page(job.name, "Blender finished without a PNG."), True
    return _progress_page(job.name, fp, busy=False), True


def status_page(out_dir: Path, fp: str) -> str:
    """What the refresh link shows. This never starts Blender."""
    fp = (fp or "").strip()
    if not fp or "/" in fp or ".." in fp:
        return _idle_page()
    out_dir = Path(out_dir)
    png = _png(out_dir, fp)
    if png.is_file() and png.stat().st_size > 32:
        status = _read_status(out_dir, fp) or {}
        return _result_page(status.get("name") or "Kitchen", png_name(fp), cached=False)
    status = _read_status(out_dir, fp)
    if status and status.get("state") == "error":
        return _error_page(status.get("name") or "", status.get("error") or "render failed")
    with _lock:
        running = _running.get("fp") if _running else None
    if running == fp or (status and status.get("state") == "running"):
        return _progress_page(status.get("name") if status else "Kitchen", fp, busy=False)
    return _idle_page()
