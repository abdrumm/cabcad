"""Finishes: separate picks for doors/fronts, box and countertop (Brook, Oct 30).

Laminate and solid surface. The starter catalog is assets/finishes/catalog.json; custom
finishes added on the form go to assets/finishes/custom.json (in git, so it is backed up).
A finish is a colour plus roughness, and for a wood or stone look a CC0 texture.

A job picks finishes with three settings (CSV "# key=value" lines, or the form):
    finish_fronts   doors, drawer fronts, filler, laminated reveal faces
    finish_box      the case (gables, bottom, top, back)
    finish_counter  the countertop (a laminate or solid-surface finish to match the top)
Blank means the drawing palette, which is what CabCad always drew.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "assets" / "finishes"
CATALOG = DIR / "catalog.json"
KINDS = {"laminate": "Laminate", "solid_surface": "Solid surface"}
USES = ("fronts", "box", "counter")


def custom_path() -> Path:
    return Path(os.environ.get("CABCAD_CUSTOM_FINISHES") or DIR / "custom.json")


def _read(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("finishes", []))


def catalog() -> list[dict]:
    """Every finish: the starter catalog, then the custom ones."""
    return _read(CATALOG) + [{**f, "custom": True} for f in _read(custom_path())]


def get(fid: str | None) -> dict | None:
    if not fid:
        return None
    return next((f for f in catalog() if f["id"] == fid), None)


def choices(kind: str | None = None) -> list[dict]:
    return [f for f in catalog() if kind is None or f["kind"] == kind]


def texture_path(f: dict) -> Path | None:
    tex = f.get("texture")
    if not tex:
        return None
    p = (DIR / tex).resolve()
    return p if p.is_file() else None


def _hex(value: str) -> str:
    v = str(value or "").strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        raise ValueError(f"colour {value!r} is not #rrggbb")
    return v.lower()


def add_custom(name: str, code: str, kind: str, color: str, close_to: str = "") -> dict:
    """Save a custom finish (name, code, colour) so it shows in the dropdowns from now on.
    The assistant matches a CC0 look-alike texture later."""
    name = " ".join(str(name or "").split())[:60]
    code = " ".join(str(code or "").split())[:30]
    if not name:
        raise ValueError("a custom finish needs a name")
    if kind not in KINDS:
        raise ValueError("a custom finish is laminate or solid surface")
    slug = re.sub(r"[^a-z0-9]+", "-", f"{name} {code}".lower()).strip("-")[:40] or "finish"
    fid = f"custom-{slug}"
    path = custom_path()
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"version": 1, "finishes": []}
    data["finishes"] = [f for f in data.get("finishes", []) if f["id"] != fid]
    entry = {"id": fid, "name": name + (f" ({code})" if code else ""), "code": code, "kind": kind,
             "family": "solid", "color": _hex(color), "roughness": 0.5 if kind == "laminate" else 0.35,
             "texture": None, "tile_in": None, "source": "custom colour, entered on the form",
             "license": "n/a", "close_to": " ".join(str(close_to or "").split())[:80] or None,
             "on_estimate": False, "needs_match": True}
    data["finishes"].append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return {**entry, "custom": True}


def label(f: dict) -> str:
    text = f["name"]
    if f.get("close_to"):
        text += f", close to {f['close_to']}"
    if f.get("custom"):
        text += " (custom, not yet on an estimate)"
    return text


def picks(settings: dict) -> dict[str, dict | None]:
    """{"fronts": finish|None, "box": ..., "counter": ...} for a job's settings."""
    return {use: get((settings or {}).get(f"finish_{use}")) for use in USES}


def palette_of(settings: dict) -> dict:
    """Drawing colours for a job: the defaults with its finish picks swapped in."""
    from .client_sheet import DEFAULT_PALETTE
    pal = dict(DEFAULT_PALETTE)
    p = picks(settings)
    if p["fronts"]:
        pal["front"] = p["fronts"]["color"]
    if p["box"]:
        pal["case"] = p["box"]["color"]
    if p["counter"]:
        pal["laminate_top"] = pal["solid_top"] = p["counter"]["color"]
    return pal


def roles_of(settings: dict) -> dict[str, dict | None]:
    """AR material role -> finish (or None for the default look)."""
    p = picks(settings)
    return {"Front": p["fronts"], "Case": p["box"], "Laminate_top": p["counter"],
            "Solid_top": p["counter"], "Pull": None}


def summary(settings: dict) -> list[tuple[str, str]]:
    """("Doors and fronts", "Walnut look") ... for the picks that are set."""
    names = {"fronts": "Doors and fronts", "box": "Box", "counter": "Countertop"}
    return [(names[u], label(f)) for u, f in picks(settings).items() if f]


def paint_boxes(boxes, settings: dict) -> list[str]:
    """Give each box the colour of the finish its role picked (box.color, #rrggbb).

    Hardware keeps its own metal and stays blank, so the exporter leaves it alone.
    Blank picks are left blank too: the drawing palette is the default look.
    Returns the labels of the finishes that were applied, for a warning line.
    """
    from .client_sheet import role_of

    pal = palette_of(settings)
    picked = picks(settings)
    for box in boxes:
        role = role_of(box)
        if role in ("pull", "kick"):
            continue
        finish = picked.get("fronts" if role == "front" else
                            "counter" if role in ("laminate_top", "solid_top") else "box")
        if finish:
            box.color = pal[role]
    return [label(f) for f in picked.values() if f]
