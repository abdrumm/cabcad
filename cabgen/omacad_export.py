"""Write the cabinet to an Omacad project file (.omacad).

Omacad lives in ~/Work/omacad and runs on its own venv (PySide6, manifold3d), so
this module shells out to that interpreter instead of importing it here.

    python3 -m cabgen.cli omacad --out out --name "Base-27"
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from .model3d import build_model
from .params import Params
from .parts import build_parts

OMACAD_DIR = Path(os.environ.get("OMACAD_DIR", Path.home() / "Work" / "omacad"))
MM = 25.4   # Omacad works in mm

BUILDER = '''
import json
import sys
sys.path.insert(0, {omacad!r})
from omacad.model.document import Document
from omacad.io.exporter import Exporter

payload = json.load(open({payload!r}))
doc = Document(payload["name"])
groups = {{}}
for b in payload["boxes"]:
    dx, dy, dz = b["size"]
    shape = b.get("shape") or ""
    if shape.startswith("qdisc"):
        # a rounded corner: a cylinder on the round's centre, joined into its part
        x, y, z = b["pos"]
        cx = x + dx if "+x" in shape else x
        cy = y + dy if "+y" in shape else y
        body = doc.add_cylinder(dx, dz, name=b["name"], translation=[cx, cy, z])
    else:
        body = doc.add_box(dx, dy, dz, name=b["name"], translation=b["pos"])
    key = b.get("join") or ""
    if key:
        groups.setdefault(key, []).append(body.body_id)
for key, ids in groups.items():
    if len(ids) < 2:
        continue
    doc.join_bodies(ids)
    if ids[0] in doc.bodies:
        doc.bodies[ids[0]].name = key
for hole in payload.get("hole_groups", []):
    doc.add_hole(hole["points"], diameter=hole["diameter"], depth=hole["depth"], through=False)
import numpy as np
from omacad.model.sketch_entities import SketchPlane
for lab in payload.get("labels") or []:
    plane = SketchPlane(
        name="label",
        origin=np.array(lab["origin"], dtype=np.float32),
        u_axis=np.array([1.0, 0.0, 0.0], dtype=np.float32),
        v_axis=np.array([0.0, 0.0, 1.0], dtype=np.float32),
        normal=np.array([0.0, -1.0, 0.0], dtype=np.float32),
    )
    sk = doc.start_sketch_on_plane(plane)
    sk.name = lab["text"]
    text_box = lab.get("box")
    sk.add_text(
        lab["text"], (0.0, 0.0), height=lab["height"], h_align="center", v_align="middle", bold=True,
        box=tuple(text_box) if text_box else None,
    )
    doc.finish_sketch()
    idxs = sk.text_profile_indices()
    if idxs:
        doc.extrude_profile(
            sk.sketch_id, idxs[0], lab["depth"], name=lab["text"], extra_profiles=idxs[1:],
        )
Exporter.save_project(doc, {out!r})
print("wrote", {out!r}, "with", len(doc.bodies), "bodies")
'''

SESSION_SCRIPT = '''
import numpy as np
import sys
sys.path.insert(0, {omacad!r})
from omacad.io.exporter import Exporter
from omacad import session

path = {path!r}
doc = Exporter.load_project(path)
pts = []
for b in doc.bodies.values():
    mesh = b.manifold.to_mesh()
    for v in mesh.vert_properties:
        pts.append(v[:3])
if pts:
    pts = np.array(pts)
    bmin, bmax = pts.min(axis=0), pts.max(axis=0)
    cam = {{
        "azimuth": 45.0,
        "elevation": 25.0,
        "distance": float(max(40.0, float(np.linalg.norm(bmax - bmin)) * 1.8)),
        "target": [float(x) for x in (bmin + bmax) / 2],
    }}
else:
    cam = {{}}
session.save(doc, path, cam)
print("session seeded for", path, "with", len(doc.bodies), "bodies")
'''


def omacad_python() -> Path:
    """The interpreter that has Omacad's dependencies."""
    venv = OMACAD_DIR / ".venv" / "bin" / "python"
    if venv.exists():
        return venv
    return Path("python3")


def seed_session(omad_path: Path) -> tuple[bool, str]:
    """Put the model into Omacad's session file, with a camera that frames it.

    Omacad has no command line file argument, so this is how a model gets
    opened: seed the session, then start the app with --resume.
    """
    omad_path = omad_path.resolve()
    if not omad_path.exists():
        return False, f"{omad_path} does not exist"
    script = SESSION_SCRIPT.format(omacad=str(OMACAD_DIR), path=str(omad_path))
    with tempfile.TemporaryDirectory(prefix="cabgen-omacad-") as tmpdir:
        script_path = Path(tmpdir) / "seed.py"
        script_path.write_text(script, encoding="utf-8")
        res = subprocess.run(
            [str(omacad_python()), str(script_path)],
            capture_output=True, text=True, cwd=str(OMACAD_DIR),
        )
    if res.returncode != 0:
        lines = (res.stderr or res.stdout).strip().splitlines()
        return False, lines[-1] if lines else "unknown error"
    return True, res.stdout.strip()


def add_recent(omad_path: Path) -> None:
    """Best effort: put the model in Omacad's recent-files list."""
    omad_path = omad_path.resolve()
    settings = Path.home() / ".local" / "share" / "omacad" / "settings.json"
    try:
        data = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}
    except (OSError, ValueError):
        data = {}
    files = [str(omad_path)] + [p for p in data.get("recent_files", []) if p != str(omad_path)]
    data["recent_files"] = files[:10]
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps(data, indent=2), encoding="utf-8")


CAD_WORKSPACE = "3"


def place_omacad_fullscreen(workspace: str = CAD_WORKSPACE, attempts: int = 12) -> bool:
    """Put the Omacad window on its own workspace, full screen.

    The Hyprland rule does this for a new window. This repeats it for the
    window that is already open, and it is safe to run when that window is
    already full screen.
    """
    win = "class:^omacad$"
    move = f'hl.dsp.window.move({{ workspace = "{workspace}", window = "{win}" }})'
    full = f'hl.dsp.window.fullscreen({{ mode = "fullscreen", action = "set", window = "{win}" }})'
    for _ in range(attempts):
        moved = subprocess.run(["hyprctl", "dispatch", move], capture_output=True, text=True)
        if moved.returncode == 0 and "ok" in (moved.stdout or "").lower():
            subprocess.run(["hyprctl", "dispatch", full], capture_output=True, text=True)
            return True
        time.sleep(0.25)
    return False


def focus_omacad(workspace: str = CAD_WORKSPACE) -> bool:
    """Switch the screen to the Omacad window (best effort, never raises).

    Tries the Lua-config dispatcher on the window, then on its workspace, then
    the classic dispatchers. Returns True if one of them said ok.
    """
    tries = [
        ["hyprctl", "dispatch", 'hl.dsp.focus({ window = "class:^omacad$" })'],
        ["hyprctl", "dispatch", f'hl.dsp.focus({{ workspace = "{workspace}" }})'],
        ["hyprctl", "dispatch", "focuswindow", "class:^omacad$"],
        ["hyprctl", "dispatch", "workspace", workspace],
    ]
    for cmd in tries:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        except Exception:  # hyprctl missing, no Hyprland session, timeout
            return False
        if r.returncode == 0 and "ok" in (r.stdout or "").lower():
            return True
    return False


def open_in_omacad(omad_path: Path, log: Path | None = None) -> tuple[bool, str]:
    """Show this model in the one Omacad window.

    The session is seeded (camera framed on the model) and `run.sh --resume` is
    started. If a window is already up, that process hands the model over and
    exits; the open window reloads. Do not pkill or pgrep for omacad: a pattern
    that contains the word matches the shell that ran it.
    """
    ok, msg = seed_session(omad_path)
    if not ok:
        return False, msg
    add_recent(omad_path)
    runner = OMACAD_DIR / "run.sh"
    if not runner.exists():
        return False, f"{runner} not found"
    log = log or (Path.home() / ".local" / "share" / "omacad" / "cabgen-launch.log")
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as fh:
        subprocess.Popen(
            [str(runner), "--resume"],
            cwd=str(OMACAD_DIR),
            stdout=fh, stderr=fh, stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    placed = place_omacad_fullscreen()
    focus_omacad()
    where = f"workspace {CAD_WORKSPACE}, full screen" if placed else "its window"
    return True, f"Omacad is showing {omad_path.name} on {where} (log: {log})"


def scene_payload(name: str, boxes, holes, labels=None) -> dict:
    """Boxes and holes are in inches. Omacad stores millimetres."""
    groups: dict[tuple[float, float], list[dict]] = {}
    for hole in holes:
        key = (round(hole.diameter, 4), round(hole.depth, 4))
        groups.setdefault(key, []).append({
            "origin": [round(v * MM, 3) for v in hole.origin],
            "normal": list(hole.normal),
        })
    return {
        "name": name,
        "boxes": [
            {
                "name": b.name,
                "pos": [round(v * MM, 3) for v in b.pos],
                "size": [round(max(v, 0.01) * MM, 3) for v in b.size],
                "join": b.join,
                **({"shape": b.shape} if getattr(b, "shape", "") else {}),
            }
            for b in boxes
        ],
        "hole_groups": [
            {
                "diameter": round(dia * MM, 3),
                "depth": round(depth * MM, 3),
                "points": points,
            }
            for (dia, depth), points in groups.items()
        ],
        "labels": [
            {
                "text": lab["text"],
                "origin": [round(lab["x"] * MM, 3), round(lab["y"] * MM, 3), round(lab["z"] * MM, 3)],
                "height": round(lab["height"] * MM, 3),
                "depth": round(lab["depth"] * MM, 3),
                **({"box": [round(v * MM, 3) for v in lab["box"]]} if lab.get("box") else {}),
            }
            for lab in (labels or [])
        ],
    }


def write_project(payload: dict, out_path: Path) -> tuple[bool, str]:
    """Run the Omacad venv to save a project. Returns (ok, message)."""
    out_path = out_path.resolve()
    with tempfile.TemporaryDirectory(prefix="cabgen-omacad-") as tmpdir:
        payload_path = Path(tmpdir) / "payload.json"
        payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        script = BUILDER.format(
            omacad=str(OMACAD_DIR),
            payload=str(payload_path),
            out=str(out_path),
        )
        script_path = Path(tmpdir) / "build.py"
        script_path.write_text(script, encoding="utf-8")
        res = subprocess.run(
            [str(omacad_python()), str(script_path)],
            capture_output=True, text=True, cwd=str(OMACAD_DIR),
        )
    if res.returncode != 0:
        lines = (res.stderr or res.stdout).strip().splitlines()
        return False, lines[-1] if lines else "unknown error"
    return True, res.stdout.strip()


def export_omacad(p: Params, out_path: Path, name: str | None = None) -> tuple[bool, str]:
    """Build the Omacad project for one cabinet. Returns (ok, message)."""
    _parts, layout = build_parts(p)
    model = build_model(p, layout)
    return write_project(scene_payload(name or p.name, model.boxes, model.holes), out_path)


def export_scene(name: str, boxes, holes, out_path: Path, labels=None) -> tuple[bool, str]:
    """Build one Omacad project from several cabinets already placed in inches."""
    return write_project(scene_payload(name, boxes, holes, labels), out_path)
