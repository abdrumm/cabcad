"""Procedural kitchen still for CabCAD. Script version 1.

There is no .blend file. Blender builds the room from the job's real boxes
(inches: x to the right, y toward the wall, z up), including the countertop
and the 4" perimeter build-up.

    blender -b --factory-startup -P cabgen/blender/render_kitchen.py -- job.json out.png

CPU only. CUDA, OptiX, HIP and oneAPI are not selected. Denoise stays off
unless the job asks for it and OpenImageDenoise can be set on the CPU. If
that setup fails, the still is rendered without a denoiser. OIDN is not
required, and no GPU denoiser is used.

The iMac binary that has been run (parent, Nov 11) is official Blender 5.2.4
LTS, portable, not on PATH:

    /home/abdrumm/.local/opt/blender-5.2.4-linux-x64/blender

Point CabCAD at it with CABCAD_BLENDER set to that absolute path. It is an
official -march=x86-64-v2 build (SSE4.2). The i7-2600 has SSE4.2 and AVX, not
AVX2, and has no GPU. A 64x64 / 8-sample smoke frame took 3.2s there. That
timing is not a kitchen still. This script's demo frame is 960x540, 32
samples, denoise off.
"""

from __future__ import annotations

import json
import sys

SCRIPT_VERSION = 1
INCH = 0.0254
SAMPLES = 32
WIDTH = 960
HEIGHT = 540


def denoise_plan(requested: bool, has_oidn: bool, accelerator: str) -> dict:
    """How to denoise a CPU still.

    A GPU accelerator is never used. If OIDN cannot be set, denoise stays off
    and the render still runs.
    """
    if str(accelerator or "CPU").upper() not in ("", "NONE", "CPU"):
        return {"denoise": False, "reason": "no GPU denoiser; CPU fallback"}
    if not requested:
        return {"denoise": False, "reason": "off; OIDN not required"}
    if not has_oidn:
        return {"denoise": False, "reason": "OIDN unavailable; rendered without denoise"}
    return {"denoise": True, "reason": "OIDN on the CPU"}


def _args():
    argv = sys.argv
    if "--" not in argv or len(argv[argv.index("--") + 1:]) < 2:
        raise SystemExit("usage: blender -b -P render_kitchen.py -- job.json out.png")
    job_path, out_path = argv[argv.index("--") + 1:][:2]
    return job_path, out_path


def _hex(color: str, fallback):
    color = (color or "").strip()
    if len(color) == 7 and color.startswith("#"):
        try:
            return tuple(int(color[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        except ValueError:
            pass
    return fallback


def _look(name: str, material: str, color: str):
    """Neutral materials. A finish colour wins; otherwise a role."""
    text = f"{name} {material}".lower()
    if "pull" in text or "hardware" in text or "hinge" in text:
        return (0.72, 0.72, 0.70), 0.25, 0.9
    if "solid surface" in text or "corian" in text:
        return _hex(color, (0.90, 0.89, 0.86)), 0.18, 0.0
    if "plywood" in text or "build-up" in text or "buildup" in text:
        return _hex(color, (0.62, 0.48, 0.34)), 0.55, 0.0
    if any(word in text for word in ("laminate", "door", "drawer", "front")):
        return _hex(color, (0.90, 0.90, 0.88)), 0.38, 0.0
    if "filler" in text:
        return _hex(color, (0.86, 0.86, 0.84)), 0.45, 0.0
    return _hex(color, (0.93, 0.92, 0.90)), 0.5, 0.0


def _set_input(node, names, value):
    for name in names:
        sock = node.inputs.get(name) if hasattr(node.inputs, "get") else None
        if sock is None:
            try:
                sock = node.inputs[name]
            except (KeyError, TypeError, IndexError):
                sock = None
        if sock is not None:
            sock.default_value = value
            return


def main():
    import bpy

    job_path, out_path = _args()
    with open(job_path, encoding="utf-8") as fh:
        job = json.load(fh)
    samples = int(job.get("samples") or SAMPLES)
    width = int(job.get("width") or WIDTH)
    height = int(job.get("height") or HEIGHT)
    want_denoise = bool(job.get("denoise"))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        import addon_utils
        addon_utils.enable("cycles", default_set=True)
    except Exception as exc:
        print(f"cabcad-cycles enable: {exc}", flush=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        if hasattr(prefs, "compute_device_type"):
            prefs.compute_device_type = "NONE"
    except Exception as exc:
        print(f"cabcad-cycles cpu: {exc}", flush=True)
    scene.cycles.samples = max(1, samples)
    if hasattr(scene.cycles, "use_adaptive_sampling"):
        scene.cycles.use_adaptive_sampling = True
        if hasattr(scene.cycles, "adaptive_threshold"):
            scene.cycles.adaptive_threshold = 0.05
    scene.cycles.use_denoising = False
    has_oidn = False
    denoiser_attr = None
    for attr in ("denoiser", "denoising_denoiser"):
        if hasattr(scene.cycles, attr):
            denoiser_attr = attr
            try:
                items = scene.cycles.bl_rna.properties[attr].enum_items
                has_oidn = any(item.identifier == "OPENIMAGEDENOISE" for item in items)
            except Exception:
                has_oidn = True
            break
    plan = denoise_plan(want_denoise, has_oidn, "CPU")
    if plan["denoise"] and denoiser_attr:
        try:
            setattr(scene.cycles, denoiser_attr, "OPENIMAGEDENOISE")
            if hasattr(scene.cycles, "denoising_use_gpu"):
                scene.cycles.denoising_use_gpu = False
            scene.cycles.use_denoising = True
        except Exception as exc:
            scene.cycles.use_denoising = False
            plan = {"denoise": False, "reason": f"OIDN setup failed ({exc}); rendered without denoise"}
    print(f"cabcad-denoise {plan['reason']}", flush=True)
    for name, value in (("max_bounces", 6), ("diffuse_bounces", 3), ("glossy_bounces", 3)):
        if hasattr(scene.cycles, name):
            setattr(scene.cycles, name, value)
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = out_path
    scene.render.film_transparent = False
    try:
        transforms = {item.identifier for item in
                      scene.view_settings.bl_rna.properties["view_transform"].enum_items}
        if "AgX" in transforms:
            scene.view_settings.view_transform = "AgX"
        elif "Filmic" in transforms:
            scene.view_settings.view_transform = "Filmic"
    except Exception:
        pass

    mats = {}

    def material(key, rgba, rough, metal):
        if key in mats:
            return mats[key]
        mat = bpy.data.materials.new(key)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            _set_input(bsdf, ("Base Color", "Color"), (*rgba, 1.0))
            _set_input(bsdf, ("Roughness",), rough)
            _set_input(bsdf, ("Metallic", "Metalness"), metal)
        mats[key] = mat
        return mat

    def cube_in(x, y, z, sx, sy, sz, mat):
        if sx <= 1e-4 or sy <= 1e-4 or sz <= 1e-4:
            return None
        cx = (x + sx / 2.0) * INCH
        cy = -(y + sy / 2.0) * INCH
        cz = (z + sz / 2.0) * INCH
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
        ob = bpy.context.active_object
        ob.scale = (sx * INCH, sy * INCH, sz * INCH)
        ob.data.materials.append(mat)
        return ob

    def cube_m(x0, y0, z0, x1, y1, z1, mat):
        sx, sy, sz = abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)
        if sx < 1e-4 or sy < 1e-4 or sz < 1e-4:
            return None
        bpy.ops.mesh.primitive_cube_add(
            size=1.0, location=((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0))
        ob = bpy.context.active_object
        ob.scale = (sx, sy, sz)
        ob.data.materials.append(mat)
        return ob

    xs, ys, zs = [], [], []
    for box in job.get("boxes") or []:
        pos, size = box["pos"], box["size"]
        rgb, rough, metal = _look(box.get("name") or "", box.get("material") or "",
                                  box.get("color") or "")
        key = f"{rgb[0]:.3f}-{rgb[1]:.3f}-{rgb[2]:.3f}-{rough:.2f}-{metal:.2f}"
        ob = cube_in(pos[0], pos[1], pos[2], size[0], size[1], size[2],
                     material(key, rgb, rough, metal))
        if ob is None:
            continue
        xs += [ob.location.x - ob.scale.x / 2.0, ob.location.x + ob.scale.x / 2.0]
        ys += [ob.location.y - ob.scale.y / 2.0, ob.location.y + ob.scale.y / 2.0]
        zs += [ob.location.z - ob.scale.z / 2.0, ob.location.z + ob.scale.z / 2.0]
    if not xs:
        raise SystemExit("job has no boxes to render")

    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    minz, maxz = min(zs), max(zs)
    span = max(maxx - minx, maxz - minz, 0.5)
    floor = material("floor", (0.45, 0.32, 0.22), 0.62, 0.0)
    wall = material("wall", (0.94, 0.93, 0.91), 0.75, 0.0)
    pad = max(0.55, span * 0.45)
    cube_m(minx - pad, miny - pad * 0.4, -0.02, maxx + pad, maxy + pad * 1.5, 0.0, floor)
    wall_top = max(maxz + span * 0.35, 2.45)
    cube_m(minx - pad * 0.3, miny - 0.10, 0.0, maxx + pad * 0.3, miny - 0.02, wall_top, wall)
    cube_m(minx - pad * 0.35, miny - 0.02, 0.0, minx - pad * 0.35 + 0.08, maxy + pad * 0.4,
           wall_top, wall)

    target = ((minx + maxx) / 2.0, (miny + maxy) / 2.0, minz * 0.25 + maxz * 0.45)
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=target)
    aim = bpy.context.active_object
    cam_loc = (target[0] - span * 0.22, maxy + span * 0.95, target[2] + span * 0.28)
    bpy.ops.object.camera_add(location=cam_loc)
    cam = bpy.context.active_object
    cam.data.lens = 36
    con = cam.constraints.new(type="TRACK_TO")
    con.target = aim
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    scene.camera = cam

    bpy.ops.object.light_add(type="AREA", location=(target[0], maxy + span * 0.25, maxz + span * 0.7))
    key = bpy.context.active_object
    key.data.energy = 220
    key.data.size = max(1.4, span * 1.5)
    key.data.color = (1.0, 0.94, 0.86)
    if hasattr(key.data, "shape"):
        key.data.shape = "RECTANGLE"
        key.data.size_y = key.data.size * 0.55
    bpy.ops.object.light_add(type="SUN", location=(target[0], maxy, maxz + 3))
    sun = bpy.context.active_object
    sun.data.energy = 2.4
    if hasattr(sun.data, "angle"):
        sun.data.angle = 0.12
    sun.rotation_euler = (0.9, 0.1, -0.55)

    world = bpy.data.worlds.new("Kitchen")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.75, 0.82, 0.90, 1.0)
        bg.inputs[1].default_value = 0.35

    print(f"cabcad-render version {SCRIPT_VERSION} samples {samples} {width}x{height} cpu",
          flush=True)
    bpy.ops.render.render(write_still=True)
    print(f"cabcad-render wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
