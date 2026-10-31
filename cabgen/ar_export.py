"""AR export: a kitchen as .glb (Android Scene Viewer, web viewers) and .usdz (iPhone/iPad
AR Quick Look).

v1 by opencode from briefs/ar-export.md; reviewed and reworked by Grok Bot (2026-10-24).

Geometry is not rebuilt here. It comes from ``client_sheet.job_from`` (which calls
``kitchen.scene_of``, i.e. model3d + parts + counter), the same boxes the client sheet
draws, plus the base filler. Colours are the client sheet's palette, so the AR model
looks like the sheet the client already has.

Coordinates. cabgen works in inches: x left to right, y front (-) to back (+), z up from
the floor. The output is metres, Y up, +Z toward the viewer (glTF and USD both). That is
gl = (x, z, -y) * 0.0254, a proper rotation (no mirror). The model is centred on its
footprint and sits on the floor (y = 0).

No dependencies: the GLB is written with struct/json, the USDZ is an uncompressed zip
with one ASCII .usda layer, every file 64-byte aligned (the USDZ spec). If the Python
running this has OpenUSD (``pxr``), the layer is written as binary .usdc instead.
"""
from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

IN_TO_M = 0.0254
DEFAULT_SHEET = Path(__file__).resolve().parents[1] / "jobs" / "sample-kitchen.csv"


# --------------------------------------------------------------------------- materials
def _hex_rgb(h: str) -> tuple[float, float, float]:
    """#rrggbb (sRGB, as the client sheet uses) -> linear 0..1, which is what glTF
    baseColorFactor and UsdPreviewSurface diffuseColor expect."""
    h = h.lstrip("#")

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return tuple(round(lin(int(h[i:i + 2], 16) / 255.0), 4) for i in (0, 2, 4))


def _materials() -> dict[str, dict]:
    """name -> linear colour, metallic, roughness. The schematic palette, before a finish is named."""
    from .client_sheet import CASE, FRONT, LAMTOP, PULL, SOLID
    return {
        "Case": {"rgb": _hex_rgb(CASE), "metallic": 0.0, "roughness": 0.75},
        "Front": {"rgb": _hex_rgb(FRONT), "metallic": 0.0, "roughness": 0.55},
        "Pull": {"rgb": _hex_rgb(PULL), "metallic": 0.8, "roughness": 0.35},
        "Laminate_top": {"rgb": _hex_rgb(LAMTOP), "metallic": 0.0, "roughness": 0.45},
        "Solid_top": {"rgb": _hex_rgb(SOLID), "metallic": 0.0, "roughness": 0.3},
        "Interior": {"rgb": _hex_rgb("#F4F1EA"), "metallic": 0.0, "roughness": 0.75},
    }


def swatch(box) -> tuple[str, str, float, float]:
    """Material name, sRGB hex, metallic, roughness.

    A named finish keeps the role (Case, Front, Laminate_top, ...) and, when the
    colour is not that role's default, the hex, so two cabinets can differ.
    Hardware stays the pull metal. A blank door or top finish keeps the old palette.
    """
    from .client_sheet import CASE, FRONT, LAMTOP, PULL, SOLID, _color
    from .finishes import WHITE_HEX, part_role

    role = part_role(box.name, box.material)
    if role == "hardware":
        return "Pull", PULL, 0.8, 0.35
    chosen = str(getattr(box, "color", "") or "").strip()
    if role == "kick":
        hex_c = chosen or _color(box)
        return f"Kick {hex_c.upper()}", hex_c, 0.0, 0.55
    if not chosen:
        hex_c = _color(box)
        name = {PULL: "Pull", SOLID: "Solid_top", LAMTOP: "Laminate_top",
                FRONT: "Front", CASE: "Case"}.get(hex_c, "Case")
        metal = 0.8 if name == "Pull" else 0.0
        rough = {"Pull": 0.35, "Solid_top": 0.3, "Laminate_top": 0.45, "Front": 0.55}.get(name, 0.75)
        return name, hex_c, metal, rough
    solid = "solid surface" in (box.material or "").lower()
    canon = {"doors": "Front", "top": "Solid_top" if solid else "Laminate_top",
             "interior": "Interior", "case": "Case"}.get(role, "Case")
    default_hex = {"Front": FRONT, "Solid_top": SOLID, "Laminate_top": LAMTOP,
                   "Interior": WHITE_HEX, "Case": WHITE_HEX}[canon]
    if chosen.lower() == default_hex.lower():
        name = canon
    else:
        name = f"{canon} {chosen.upper()}"
    rough = {"Front": 0.55, "Solid_top": 0.3, "Laminate_top": 0.4,
             "Interior": 0.75, "Case": 0.72}[canon]
    return name, chosen, 0.0, rough


def _material_of(box) -> str:
    """Material name for one solid. Kept for callers that only need the name."""
    return swatch(box)[0]


# --------------------------------------------------------------------------- geometry
def job_boxes(job) -> list:
    """Every visible box of the job (client-sheet set) plus the filler."""
    from .client_sheet import _filler_box
    boxes = list(job.boxes)
    filler = _filler_box(job)
    if filler is not None:
        filler.material = "3/4\" melamine + laminate"   # a finished face, like a front
        from .finishes import paint_filler
        paint_filler(filler, job)
        boxes.append(filler)
    return boxes


def _to_gl(p):
    x, y, z = p
    return (x * IN_TO_M, z * IN_TO_M, -y * IN_TO_M)


def _gl_box(box) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Axis-aligned (min, max) of a cabgen box in output metres."""
    (x, y, z), (sx, sy, sz) = box.pos, box.size
    a, b = _to_gl((x, y, z)), _to_gl((x + sx, y + sy, z + sz))
    return tuple(min(a[i], b[i]) for i in range(3)), tuple(max(a[i], b[i]) for i in range(3))


def _box_faces(lo, hi):
    """24 vertices (4 per face, flat normals) and 12 CCW-outward triangles."""
    verts, norms, tris = [], [], []
    for axis in range(3):
        b, c = (axis + 1) % 3, (axis + 2) % 3
        for side, sign in ((hi, 1.0), (lo, -1.0)):
            quad = []
            for ub, uc in ((0, 0), (1, 0), (1, 1), (0, 1)):   # e_b x e_c = e_axis: CCW for +axis
                v = [0.0, 0.0, 0.0]
                v[axis] = side[axis]
                v[b] = hi[b] if ub else lo[b]
                v[c] = hi[c] if uc else lo[c]
                quad.append(tuple(v))
            if sign < 0:
                quad.reverse()
            n = [0.0, 0.0, 0.0]
            n[axis] = sign
            k = len(verts)
            verts += quad
            norms += [tuple(n)] * 4
            tris += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
    return verts, norms, tris


def build_meshes(boxes) -> tuple[dict[str, dict], tuple[float, float, float]]:
    """Merge the boxes into one mesh per material, centred on the footprint, floor at 0.
    Returns ({material: {points, normals, tris}}, (width, height, depth) in metres)."""
    spans = [_gl_box(b) for b in boxes]
    lo = [min(s[0][i] for s in spans) for i in range(3)]
    hi = [max(s[1][i] for s in spans) for i in range(3)]
    shift = (-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2)
    meshes: dict[str, dict] = {}
    for box, (blo, bhi) in zip(boxes, spans):
        key, hex_c, metal, rough = swatch(box)
        m = meshes.setdefault(key, {"points": [], "normals": [], "tris": [],
                                    "rgb": _hex_rgb(hex_c), "metallic": metal, "roughness": rough})
        blo = tuple(blo[i] + shift[i] for i in range(3))
        bhi = tuple(bhi[i] + shift[i] for i in range(3))
        v, n, t = _box_faces(blo, bhi)
        k = len(m["points"])
        m["points"] += v
        m["normals"] += n
        m["tris"] += [(a + k, b + k, c + k) for a, b, c in t]
    size = tuple(round(hi[i] - lo[i], 6) for i in range(3))
    return meshes, size


# --------------------------------------------------------------------------- GLB
def make_glb(meshes: dict[str, dict], name: str = "Kitchen") -> bytes:
    order = [m for m in meshes if meshes[m]["points"]]
    buf = bytearray()
    views, accessors, prims = [], [], []

    def add_view(data: bytes, target: int) -> int:
        while len(buf) % 4:
            buf.append(0)
        views.append({"buffer": 0, "byteOffset": len(buf), "byteLength": len(data), "target": target})
        buf.extend(data)
        return len(views) - 1

    for mi, key in enumerate(order):
        m = meshes[key]
        pts = m["points"]
        pos = add_view(b"".join(struct.pack("<3f", *p) for p in pts), 34962)
        accessors.append({"bufferView": pos, "componentType": 5126, "count": len(pts), "type": "VEC3",
                          "min": [min(p[i] for p in pts) for i in range(3)],
                          "max": [max(p[i] for p in pts) for i in range(3)]})
        nrm = add_view(b"".join(struct.pack("<3f", *n) for n in m["normals"]), 34962)
        accessors.append({"bufferView": nrm, "componentType": 5126, "count": len(pts), "type": "VEC3"})
        flat = [i for t in m["tris"] for i in t]
        big = len(pts) > 65535
        idx = add_view(struct.pack(f"<{len(flat)}{'I' if big else 'H'}", *flat), 34963)
        accessors.append({"bufferView": idx, "componentType": 5125 if big else 5123,
                          "count": len(flat), "type": "SCALAR"})
        a = len(accessors)
        prims.append({"attributes": {"POSITION": a - 3, "NORMAL": a - 2}, "indices": a - 1,
                      "material": mi, "mode": 4})
    while len(buf) % 4:
        buf.append(0)
    gltf = {
        "asset": {"version": "2.0", "generator": "cabgen ar_export"},
        "scene": 0,
        "scenes": [{"name": name, "nodes": [0]}],
        "nodes": [{"name": name, "mesh": 0}],
        "meshes": [{"name": name, "primitives": prims}],
        "materials": [{"name": k, "pbrMetallicRoughness": {
            "baseColorFactor": [*meshes[k]["rgb"], 1.0],
            "metallicFactor": meshes[k]["metallic"], "roughnessFactor": meshes[k]["roughness"]}}
            for k in order],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(buf)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(buf)
    return (b"glTF" + struct.pack("<II", 2, total)
            + struct.pack("<I", len(js)) + b"JSON" + js
            + struct.pack("<I", len(buf)) + b"BIN\x00" + bytes(buf))


# --------------------------------------------------------------------------- USD
def _usd_name(key: str) -> str:
    """USD prim names are identifiers. Spaces and '#' in a finish name become underscores."""
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in key)


def _f(v: float) -> str:
    return f"{v:.6g}"


def _tup(t) -> str:
    return "(" + ", ".join(_f(x) for x in t) + ")"


def make_usda(meshes: dict[str, dict], name: str = "Kitchen") -> str:
    order = [m for m in meshes if meshes[m]["points"]]
    out = ['#usda 1.0', '(', '    defaultPrim = "Kitchen"', '    metersPerUnit = 1',
           '    upAxis = "Y"', f'    doc = "{name} - cabgen AR export"', ')', '',
           'def Xform "Kitchen" (', '    kind = "component"', ')', '{']
    out += ['    def Scope "Materials"', '    {']
    for k in order:
        m = meshes[k]
        safe = _usd_name(k)
        out += [
            f'        def Material "{safe}"', '        {',
            f'            token outputs:surface.connect = </Kitchen/Materials/{safe}/Surface.outputs:surface>',
            '            def Shader "Surface"', '            {',
            '                uniform token info:id = "UsdPreviewSurface"',
            f'                color3f inputs:diffuseColor = {_tup(m["rgb"])}',
            f'                float inputs:metallic = {_f(m["metallic"])}',
            f'                float inputs:roughness = {_f(m["roughness"])}',
            '                token outputs:surface', '            }', '        }']
    out += ['    }']
    for k in order:
        m = meshes[k]
        pts = m["points"]
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        out += [
            f'    def Mesh "{_usd_name(k)}" (', '        prepend apiSchemas = ["MaterialBindingAPI"]', '    )', '    {',
            f'        float3[] extent = [{_tup(lo)}, {_tup(hi)}]',
            f'        int[] faceVertexCounts = [{", ".join("3" for _ in m["tris"])}]',
            f'        int[] faceVertexIndices = [{", ".join(str(i) for t in m["tris"] for i in t)}]',
            f'        point3f[] points = [{", ".join(_tup(p) for p in pts)}]',
            f'        normal3f[] normals = [{", ".join(_tup(n) for n in m["normals"])}] (',
            '            interpolation = "vertex"', '        )',
            '        uniform token orientation = "rightHanded"',
            '        uniform token subdivisionScheme = "none"',
            '        uniform bool doubleSided = 0',
            f'        rel material:binding = </Kitchen/Materials/{_usd_name(k)}>',
            '    }']
    out += ['}', '']
    return "\n".join(out)


def _usdc_bytes(usda: str) -> bytes | None:
    """Binary crate layer if this Python has OpenUSD; else None (keep the .usda)."""
    try:
        from pxr import Sdf  # type: ignore
    except ImportError:
        return None
    import tempfile
    layer = Sdf.Layer.CreateAnonymous(".usda")
    layer.ImportFromString(usda)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "k.usdc"
        layer.Export(str(path))
        return path.read_bytes()


def write_usdz(path: Path, files: list[tuple[str, bytes]]) -> None:
    """Uncompressed zip, each file's data 64-byte aligned (padding in the extra field)."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as zf:
        for arcname, data in files:
            info = zipfile.ZipInfo(arcname, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            start = zf.fp.tell() + 30 + len(arcname.encode("utf-8"))
            pad = -start % 64
            if pad and pad < 4:
                pad += 64
            if pad:
                info.extra = struct.pack("<HH", 0x1986, pad - 4) + b"\0" * (pad - 4)
            zf.writestr(info, data)


# --------------------------------------------------------------------------- entry point
def export_job(job, out_dir: str | Path, name: str) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    boxes = job_boxes(job)
    meshes, size = build_meshes(boxes)
    title = job.name or name
    glb_path = out_dir / f"{name}.glb"
    glb_path.write_bytes(make_glb(meshes, title))
    usda = make_usda(meshes, title)
    usdc = _usdc_bytes(usda)
    layer = (f"{name}.usdc", usdc) if usdc else (f"{name}.usda", usda.encode("utf-8"))
    usdz_path = out_dir / f"{name}.usdz"
    write_usdz(usdz_path, [layer])
    warnings = list(getattr(job, "finish_warnings", None) or [])
    return {"glb": str(glb_path), "usdz": str(usdz_path), "boxes": len(boxes),
            "size_m": size, "usd_layer": layer[0], "warnings": warnings}


def export_ar(cabs: list | None = None, settings: dict | None = None,
              out_dir: str | Path = "out/ar", name: str = "kitchen",
              sheet_path: str | Path | None = None, title: str | None = None) -> dict:
    """Write <out_dir>/<name>.glb and .usdz. Give a kitchen CSV (sheet_path) or placed
    cabs + settings. With neither, the sample kitchen."""
    from .client_sheet import job_from, load_job
    if cabs is None:
        sheet = Path(sheet_path) if sheet_path is not None else DEFAULT_SHEET
        job = load_job(sheet, title)
        if settings:
            job = job_from(job.cabs, {**job.settings, **settings}, job.name)
    else:
        job = job_from(cabs, settings or {}, title or name)
    return export_job(job, out_dir, name)
