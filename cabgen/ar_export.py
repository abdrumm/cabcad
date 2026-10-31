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


def _materials(settings: dict | None = None) -> dict[str, dict]:
    """name -> linear colour, metallic, roughness, and for a wood or stone finish a texture
    (path, tile size in metres). Colours from the client sheet unless the job picked a
    finish for that role (cabgen.finishes)."""
    from .client_sheet import CASE, FRONT, LAMTOP, PULL, SOLID
    mats = {
        "Case": {"rgb": _hex_rgb(CASE), "metallic": 0.0, "roughness": 0.75},
        "Front": {"rgb": _hex_rgb(FRONT), "metallic": 0.0, "roughness": 0.55},
        "Pull": {"rgb": _hex_rgb(PULL), "metallic": 0.8, "roughness": 0.35},
        "Laminate_top": {"rgb": _hex_rgb(LAMTOP), "metallic": 0.0, "roughness": 0.45},
        "Solid_top": {"rgb": _hex_rgb(SOLID), "metallic": 0.0, "roughness": 0.3},
    }
    if settings:
        from .finishes import roles_of, texture_path
        for role, fin in roles_of(settings).items():
            if not fin:
                continue
            m = mats[role]
            m["rgb"] = _hex_rgb(fin["color"])
            m["roughness"] = float(fin.get("roughness", m["roughness"]))
            m["finish"] = fin["id"]
            tex = texture_path(fin)
            if tex is not None:
                w, h = fin.get("tile_in") or (24, 24)
                m["texture"] = tex
                m["tile_m"] = (w * IN_TO_M, h * IN_TO_M)
    return mats


def _material_of(box) -> str:
    """Same rule as client_sheet.role_of, by material name."""
    from .client_sheet import role_of
    role = role_of(box)
    if role == "kick":
        return "Kick"
    return {"pull": "Pull", "solid_top": "Solid_top", "laminate_top": "Laminate_top",
            "front": "Front", "case": "Case"}[role]


# --------------------------------------------------------------------------- geometry
def job_boxes(job) -> list:
    """Every visible box of the job (client-sheet set) plus the filler."""
    from .client_sheet import _filler_box
    boxes = list(job.boxes)
    filler = _filler_box(job)
    if filler is not None:
        filler.material = "3/4\" melamine + laminate"   # a finished face, like a front
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


def _uv(point, normal) -> tuple[float, float]:
    """Texture coordinates in metres: v runs up on the fronts and sides (wood grain
    vertical on doors, as the textures are stored), along the depth on top faces."""
    x, y, z = point
    if abs(normal[1]) > 0.5:          # top / bottom
        return (x, z)
    if abs(normal[0]) > 0.5:          # left / right ends
        return (z, y)
    return (x, y)                     # front / back


def build_meshes(boxes) -> tuple[dict[str, dict], tuple[float, float, float]]:
    """Merge the boxes into one mesh per material, centred on the footprint, floor at 0.
    Returns ({material: {points, normals, tris}}, (width, height, depth) in metres)."""
    spans = [_gl_box(b) for b in boxes]
    lo = [min(s[0][i] for s in spans) for i in range(3)]
    hi = [max(s[1][i] for s in spans) for i in range(3)]
    shift = (-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2)
    meshes: dict[str, dict] = {}
    for box, (blo, bhi) in zip(boxes, spans):
        m = meshes.setdefault(_material_of(box), {"points": [], "normals": [], "tris": [], "uvs": []})
        blo = tuple(blo[i] + shift[i] for i in range(3))
        bhi = tuple(bhi[i] + shift[i] for i in range(3))
        v, n, t = _box_faces(blo, bhi)
        k = len(m["points"])
        m["points"] += v
        m["normals"] += n
        m.setdefault("uvs", [])
        m["uvs"] += [_uv(p, nn) for p, nn in zip(v, n)]
        m["tris"] += [(a + k, b + k, c + k) for a, b, c in t]
    size = tuple(round(hi[i] - lo[i], 6) for i in range(3))
    return meshes, size


# --------------------------------------------------------------------------- GLB
def _kick_mat(boxes) -> dict:
    """One Kick material, the colour painted on the plate."""
    from .client_sheet import role_of
    kick = next((b for b in boxes if role_of(b) == "kick" and getattr(b, "color", "")), None)
    if not kick:
        return {}
    return {"Kick": {"rgb": _hex_rgb(kick.color), "metallic": 0.0, "roughness": 0.55}}


def make_glb(meshes: dict[str, dict], name: str = "Kitchen", settings: dict | None = None,
             extra_mats: dict | None = None) -> bytes:
    mats = _materials(settings)
    if extra_mats:
        mats.update(extra_mats)
    order = [m for m in mats if m in meshes]
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
        attrs = {"POSITION": a - 3, "NORMAL": a - 2}
        mat = mats[key]
        if mat.get("texture"):
            tw, th = mat["tile_m"]
            uv = add_view(b"".join(struct.pack("<2f", u / tw, 1.0 - v / th) for u, v in m["uvs"]), 34962)
            accessors.append({"bufferView": uv, "componentType": 5126, "count": len(pts), "type": "VEC2"})
            attrs["TEXCOORD_0"] = len(accessors) - 1
        prims.append({"attributes": attrs, "indices": a - 1, "material": mi, "mode": 4})
    images, textures, gl_mats = [], [], []
    for k in order:
        pbr = {"baseColorFactor": [*mats[k]["rgb"], 1.0],
               "metallicFactor": mats[k]["metallic"], "roughnessFactor": mats[k]["roughness"]}
        if mats[k].get("texture") and "TEXCOORD_0" in prims[order.index(k)]["attributes"]:
            data = Path(mats[k]["texture"]).read_bytes()
            while len(buf) % 4:
                buf.append(0)
            views.append({"buffer": 0, "byteOffset": len(buf), "byteLength": len(data)})
            buf.extend(data)
            images.append({"bufferView": len(views) - 1, "mimeType": "image/jpeg"})
            textures.append({"sampler": 0, "source": len(images) - 1})
            pbr["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
            pbr["baseColorTexture"] = {"index": len(textures) - 1}
        gl_mats.append({"name": k, "pbrMetallicRoughness": pbr})
    while len(buf) % 4:
        buf.append(0)
    gltf = {
        "asset": {"version": "2.0", "generator": "cabgen ar_export"},
        "scene": 0,
        "scenes": [{"name": name, "nodes": [0]}],
        "nodes": [{"name": name, "mesh": 0}],
        "meshes": [{"name": name, "primitives": prims}],
        "materials": gl_mats,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(buf)}],
    }
    if images:
        gltf.update(images=images, textures=textures,
                    samplers=[{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}])
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(buf)
    return (b"glTF" + struct.pack("<II", 2, total)
            + struct.pack("<I", len(js)) + b"JSON" + js
            + struct.pack("<I", len(buf)) + b"BIN\x00" + bytes(buf))


# --------------------------------------------------------------------------- USD
def _f(v: float) -> str:
    return f"{v:.6g}"


def _tup(t) -> str:
    return "(" + ", ".join(_f(x) for x in t) + ")"


def usd_textures(settings: dict | None) -> list[tuple[str, bytes]]:
    """(path inside the USDZ, bytes) for each texture the job's finishes use."""
    out, seen = [], set()
    for m in _materials(settings).values():
        tex = m.get("texture")
        if tex and tex.name not in seen:
            seen.add(tex.name)
            out.append((f"textures/{tex.name}", Path(tex).read_bytes()))
    return out


def make_usda(meshes: dict[str, dict], name: str = "Kitchen", settings: dict | None = None,
              extra_mats: dict | None = None) -> str:
    mats = _materials(settings)
    if extra_mats:
        mats.update(extra_mats)
    order = [m for m in mats if m in meshes]
    out = ['#usda 1.0', '(', '    defaultPrim = "Kitchen"', '    metersPerUnit = 1',
           '    upAxis = "Y"', f'    doc = "{name} - cabgen AR export"', ')', '',
           'def Xform "Kitchen" (', '    kind = "component"', ')', '{']
    out += ['    def Scope "Materials"', '    {']
    for k in order:
        m = mats[k]
        base = f"/Kitchen/Materials/{k}"
        tex = m.get("texture")
        diffuse = (f'                color3f inputs:diffuseColor.connect = <{base}/Tex.outputs:rgb>'
                   if tex else f'                color3f inputs:diffuseColor = {_tup(m["rgb"])}')
        out += [
            f'        def Material "{k}"', '        {',
            f'            token outputs:surface.connect = <{base}/Surface.outputs:surface>']
        if tex:
            out += ['            token inputs:frame:stPrimvarName = "st"']
        out += [
            '            def Shader "Surface"', '            {',
            '                uniform token info:id = "UsdPreviewSurface"',
            diffuse,
            f'                float inputs:metallic = {_f(m["metallic"])}',
            f'                float inputs:roughness = {_f(m["roughness"])}',
            '                token outputs:surface', '            }']
        if tex:
            out += [
                '            def Shader "StReader"', '            {',
                '                uniform token info:id = "UsdPrimvarReader_float2"',
                f'                token inputs:varname.connect = <{base}.inputs:frame:stPrimvarName>',
                '                float2 outputs:result', '            }',
                '            def Shader "Tex"', '            {',
                '                uniform token info:id = "UsdUVTexture"',
                f'                asset inputs:file = @textures/{Path(tex).name}@',
                f'                float2 inputs:st.connect = <{base}/StReader.outputs:result>',
                '                token inputs:wrapS = "repeat"', '                token inputs:wrapT = "repeat"',
                '                token inputs:sourceColorSpace = "sRGB"',
                '                float3 outputs:rgb', '            }']
        out += ['        }']
    out += ['    }']
    for k in order:
        m = meshes[k]
        pts = m["points"]
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        out += [
            f'    def Mesh "{k}" (', '        prepend apiSchemas = ["MaterialBindingAPI"]', '    )', '    {',
            f'        float3[] extent = [{_tup(lo)}, {_tup(hi)}]',
            f'        int[] faceVertexCounts = [{", ".join("3" for _ in m["tris"])}]',
            f'        int[] faceVertexIndices = [{", ".join(str(i) for t in m["tris"] for i in t)}]',
            f'        point3f[] points = [{", ".join(_tup(p) for p in pts)}]',
            f'        normal3f[] normals = [{", ".join(_tup(n) for n in m["normals"])}] (',
            '            interpolation = "vertex"', '        )',
            *([f'        texCoord2f[] primvars:st = [{", ".join(_tup((u / mats[k]["tile_m"][0], v / mats[k]["tile_m"][1])) for u, v in m["uvs"])}] (',
               '            interpolation = "vertex"', '        )'] if mats[k].get("texture") else []),
            '        uniform token orientation = "rightHanded"',
            '        uniform token subdivisionScheme = "none"',
            '        uniform bool doubleSided = 0',
            f'        rel material:binding = </Kitchen/Materials/{k}>',
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
    settings = getattr(job, "settings", None) or {}
    extra = _kick_mat(boxes)
    glb_path.write_bytes(make_glb(meshes, title, settings, extra))
    usda = make_usda(meshes, title, settings, extra)
    usdc = _usdc_bytes(usda)
    layer = (f"{name}.usdc", usdc) if usdc else (f"{name}.usda", usda.encode("utf-8"))
    usdz_path = out_dir / f"{name}.usdz"
    write_usdz(usdz_path, [layer] + usd_textures(settings))   # the layer must come first
    return {"glb": str(glb_path), "usdz": str(usdz_path), "boxes": len(boxes),
            "size_m": size, "usd_layer": layer[0]}


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
