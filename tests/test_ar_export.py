"""AR export (.glb + .usdz). v1 tests by opencode; extended by Grok Bot in review."""
import json
import struct
import zipfile
from pathlib import Path

from cabgen.ar_export import IN_TO_M, export_ar
from cabgen.client_sheet import load_job

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "jobs" / "sample-kitchen.csv"
UPPERS = ROOT / "jobs" / "upper-styles.csv"


def _glb(path):
    data = Path(path).read_bytes()
    magic, version, total = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF" and version == 2 and total == len(data)
    jlen, jtype = struct.unpack("<I4s", data[12:20])
    assert jtype == b"JSON" and jlen % 4 == 0
    gltf = json.loads(data[20:20 + jlen])
    blen, btype = struct.unpack("<I4s", data[20 + jlen:28 + jlen])
    assert btype == b"BIN\x00" and blen == gltf["buffers"][0]["byteLength"]
    return gltf, data[28 + jlen:28 + jlen + blen]


def _read(gltf, binary, acc_i):
    acc = gltf["accessors"][acc_i]
    view = gltf["bufferViews"][acc["bufferView"]]
    fmt = {5126: "f", 5123: "H", 5125: "I"}[acc["componentType"]]
    n = {"VEC3": 3, "SCALAR": 1}[acc["type"]]
    raw = struct.unpack_from(f"<{acc['count'] * n}{fmt}", binary, view["byteOffset"])
    return [raw[i:i + n] for i in range(0, len(raw), n)] if n > 1 else list(raw)


def _bounds(gltf):
    pos = [gltf["accessors"][p["attributes"]["POSITION"]] for p in gltf["meshes"][0]["primitives"]]
    lo = [min(a["min"][i] for a in pos) for i in range(3)]
    hi = [max(a["max"][i] for a in pos) for i in range(3)]
    return lo, hi


def test_ar_export_creates_files(tmp_path: Path):
    res = export_ar(out_dir=tmp_path / "ar", name="sample-kitchen", sheet_path=SAMPLE)
    for key in ("glb", "usdz"):
        assert Path(res[key]).is_file() and Path(res[key]).stat().st_size > 0
    _glb(res["glb"])


def test_ar_export_bounding_box_is_the_kitchen_in_metres_on_the_floor(tmp_path: Path):
    res = export_ar(out_dir=tmp_path, name="k", sheet_path=SAMPLE)
    job = load_job(SAMPLE)
    xs = [b.pos[0] for b in job.boxes] + [b.pos[0] + b.size[0] for b in job.boxes]
    ys = [b.pos[1] for b in job.boxes] + [b.pos[1] + b.size[1] for b in job.boxes]
    zs = [b.pos[2] + b.size[2] for b in job.boxes]
    lo, hi = _bounds(_glb(res["glb"])[0])
    assert abs((hi[0] - lo[0]) - (max(xs) - min(xs)) * IN_TO_M) < 0.001      # run length
    assert abs((hi[1] - lo[1]) - max(zs) * IN_TO_M) < 0.001                  # floor to top
    assert abs((hi[2] - lo[2]) - (max(ys) - min(ys)) * IN_TO_M) < 0.001      # depth
    assert abs(lo[1]) < 1e-6                                                 # floor at y = 0
    assert abs(lo[0] + hi[0]) < 1e-6 and abs(lo[2] + hi[2]) < 1e-6          # centred footprint
    assert abs(hi[0] - lo[0] - 76 * IN_TO_M) < 0.001 and abs(hi[1] - 84 * IN_TO_M) < 0.001


def test_triangles_face_out_and_the_model_is_not_mirrored(tmp_path: Path):
    res = export_ar(out_dir=tmp_path, name="u", sheet_path=UPPERS)
    gltf, binary = _glb(res["glb"])
    for prim in gltf["meshes"][0]["primitives"]:
        pts = _read(gltf, binary, prim["attributes"]["POSITION"])
        nrm = _read(gltf, binary, prim["attributes"]["NORMAL"])
        idx = _read(gltf, binary, prim["indices"])
        for k in range(0, len(idx), 3):
            a, b, c = (pts[i] for i in idx[k:k + 3])
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            assert sum(cross[i] * nrm[idx[k]][i] for i in range(3)) > 0      # CCW = outward
    # Upper 1 (x 0..15) is a 1-door with the handle LEFT, Upper 5 (x 102..117) handle RIGHT.
    # Not mirrored: the pull of Upper 1 is near the left of the model, and fronts face +Z.
    mats = [m["name"] for m in gltf["materials"]]
    pull = gltf["meshes"][0]["primitives"][mats.index("Pull")]
    pts = _read(gltf, binary, pull["attributes"]["POSITION"])
    lo, hi = _bounds(gltf)
    upper = [p for p in pts if p[1] > 54 * IN_TO_M]

    def front_most(ps):   # the pull, not the hinge plate inside the same cabinet
        return [p for p in ps if p[2] > max(q[2] for q in ps) - 0.5 * IN_TO_M]

    left = front_most([p for p in upper if p[0] < lo[0] + 15 * IN_TO_M])
    right = front_most([p for p in upper if p[0] > lo[0] + 102 * IN_TO_M])
    assert left and right
    assert max(p[0] for p in left) - lo[0] < 4 * IN_TO_M                    # 2" from the left edge
    assert (lo[0] + 117 * IN_TO_M) - min(p[0] for p in right) < 4 * IN_TO_M
    assert max(p[2] for p in pts) > hi[2] - 0.05                            # pulls at the front (+Z)


def test_all_styles_counter_and_filler_are_in_the_model(tmp_path: Path):
    res = export_ar(out_dir=tmp_path, name="u", sheet_path=UPPERS)
    gltf, _ = _glb(res["glb"])
    assert {m["name"] for m in gltf["materials"]} >= {"Case", "Front", "Pull", "Laminate_top"}
    job = load_job(UPPERS)
    assert job.filler and res["boxes"] == len(job.boxes) + 1               # + the filler
    names = " ".join(b.name for b in job.boxes)
    for part in ("Open shelf 1", "Microwave divider", "Door, handle L", "Door, handle R",
                 "Backsplash", "Side splash, left wall", "Side splash, right wall"):
        assert part in names


def test_usdz_is_stored_64_byte_aligned_and_y_up_metres(tmp_path: Path):
    res = export_ar(out_dir=tmp_path, name="k", sheet_path=SAMPLE)
    with zipfile.ZipFile(res["usdz"]) as zf:
        infos = zf.infolist()
        assert infos and infos[0].filename.endswith((".usda", ".usdc"))
        raw = Path(res["usdz"]).read_bytes()
        for info in infos:
            assert info.compress_type == zipfile.ZIP_STORED
            fn_len, extra_len = struct.unpack("<HH", raw[info.header_offset + 26:info.header_offset + 30])
            assert (info.header_offset + 30 + fn_len + extra_len) % 64 == 0
        if infos[0].filename.endswith(".usda"):
            text = zf.read(infos[0]).decode("utf-8")
            assert text.startswith("#usda 1.0")
            assert "metersPerUnit = 1" in text and 'upAxis = "Y"' in text
            assert 'defaultPrim = "Kitchen"' in text and "UsdPreviewSurface" in text
            assert text.count("{") == text.count("}")
