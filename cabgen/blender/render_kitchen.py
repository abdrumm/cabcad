"""Procedural kitchen still for CabCAD. Script version 5.

There is no .blend file. Blender builds the room from the job's real boxes
(inches: x to the right, y toward the wall, z up), including the countertop
and the 4" perimeter build-up. Cabinet sizes are not scaled.

    blender -b --factory-startup -P cabgen/blender/render_kitchen.py -- job.json out.png

CPU only. CUDA, OptiX, HIP and oneAPI are not selected. The still is
1920x1080, 20 samples, OpenImageDenoise on the CPU when the job asks for it.
"""

from __future__ import annotations

import json
import sys

SCRIPT_VERSION = 5
INCH = 0.0254
SAMPLES = 20
WIDTH = 1920
HEIGHT = 1080
# Warm greige, clearly not the cabinet white. Floor is a mid oak.
WALL_COLOR = (0.76, 0.69, 0.60)
FLOOR_COLOR = (0.36, 0.24, 0.15)
# From the subject toward the camera: in front of the run, a little to the
# left, slightly above. Image-right is then +X, matching the drawings.
FRONT_VIEW = (-0.16, 1.0, 0.20)


def _norm(v):
    import math
    m = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / m, v[1] / m, v[2] / m)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def camera_fit(bounds_min, bounds_max, view_dir, lens_mm=32.0, aspect=WIDTH / HEIGHT,
               margin=1.14, sensor_mm=36.0):
    """Place a camera so every corner of the box is inside the frame.

    ``view_dir`` points from the subject toward the camera. ``margin`` shrinks
    the field of view, so 1.14 leaves a comfortable gap around the stack.
    Blender's default sensor is 36 mm wide and, for a landscape frame, the
    vertical field is that divided by the aspect. A 36 mm lens on 960x540
    sees only about 31 degrees vertically, which is why a camera parked a
    fixed multiple of the run width cropped the uppers and the toe kicks.
    """
    cx = (bounds_min[0] + bounds_max[0]) / 2.0
    cy = (bounds_min[1] + bounds_max[1]) / 2.0
    cz = (bounds_min[2] + bounds_max[2]) / 2.0
    center = (cx, cy, cz)
    back = _norm(view_dir)
    look = (-back[0], -back[1], -back[2])
    right = _norm(_cross((0.0, 0.0, 1.0), look))
    if abs(right[0]) + abs(right[1]) + abs(right[2]) < 1e-8:
        right = (1.0, 0.0, 0.0)
    up = _norm(_cross(look, right))
    tan_h = (sensor_mm / 2.0) / lens_mm / margin
    tan_v = (sensor_mm / aspect / 2.0) / lens_mm / margin
    dist = 0.05
    for ix in (bounds_min[0] - cx, bounds_max[0] - cx):
        for iy in (bounds_min[1] - cy, bounds_max[1] - cy):
            for iz in (bounds_min[2] - cz, bounds_max[2] - cz):
                p = (ix, iy, iz)
                need = _dot(p, back) + max(abs(_dot(p, right)) / tan_h, abs(_dot(p, up)) / tan_v)
                if need > dist:
                    dist = need
    cam = (center[0] + back[0] * dist, center[1] + back[1] * dist, center[2] + back[2] * dist)
    return cam, center, dist


def box_center_m(pos, size):
    """CabCAD inches (x right, y toward the wall, z up) to a Blender centre, metres."""
    x, y, z = pos
    sx, sy, sz = size
    return ((x + sx / 2.0) * INCH, -(y + sy / 2.0) * INCH, (z + sz / 2.0) * INCH)


def camera_axes(cam, target):
    """Camera basis. ``right`` is +X on the picture, ``look`` points at the target.

    Track-To with up = Y flipped the picture: the microwave, which is on the
    right in the drawings, landed on the left. This basis keeps world +X on
    the right when the camera looks from the front toward the wall.
    """
    look = _norm((target[0] - cam[0], target[1] - cam[1], target[2] - cam[2]))
    right = _norm(_cross((0.0, 0.0, 1.0), look))
    if abs(right[0]) + abs(right[1]) + abs(right[2]) < 1e-8:
        right = (1.0, 0.0, 0.0)
    up = _norm(_cross(look, right))
    return right, up, look


def image_x(point, cam, target):
    """Horizontal position on the picture. Larger means further right."""
    right, _up, _look = camera_axes(cam, target)
    rel = (point[0] - cam[0], point[1] - cam[1], point[2] - cam[2])
    return _dot(rel, right)


def back_wall_interval(cabinet_back_y, thickness=0.06):
    """Wall just behind the cabinets. The room-facing face is ``cabinet_back_y``."""
    return cabinet_back_y - thickness, cabinet_back_y


def denoise_should_try(requested, has_attr, enum_ids):
    """Whether to assign OpenImageDenoise.

    Blender 5.2 in background mode reported ``scene.cycles.denoiser`` with an
    empty ``enum_items``, and the old check treated that as "no denoiser".
    An empty list means the choices were not filled in, not that OIDN is absent.
    """
    if not requested or not has_attr:
        return False
    if not enum_ids:
        return True
    return "OPENIMAGEDENOISE" in enum_ids


def _enum_ids(scene, attr):
    try:
        return [item.identifier for item in scene.cycles.bl_rna.properties[attr].enum_items]
    except Exception:
        return []


def _enable_cpu_denoise(scene, bpy, requested):
    """Turn on CPU OpenImageDenoise. Returns the log line. Never raises."""
    if not requested:
        return "off; job asked to skip"
    attr = next((name for name in ("denoiser", "denoising_denoiser")
                 if hasattr(scene.cycles, name)), None)
    enum_ids = _enum_ids(scene, attr) if attr else []
    if not denoise_should_try(True, attr is not None, enum_ids):
        return "off; no denoiser attribute"
    try:
        scene.cycles.use_denoising = True
        setattr(scene.cycles, attr, "OPENIMAGEDENOISE")
    except Exception as exc:
        scene.cycles.use_denoising = False
        return f"off; OIDN assignment failed ({exc})"
    notes = [f"cycles.{attr}=OPENIMAGEDENOISE"]
    if hasattr(scene.cycles, "denoising_use_gpu"):
        try:
            scene.cycles.denoising_use_gpu = False
            notes.append("denoising_use_gpu=False")
        except Exception as exc:
            notes.append(f"denoising_use_gpu failed ({exc})")
    for name, value in (("denoising_device", "CPU"), ("denoising_prefilter", "FAST"),
                        ("denoising_input_passes", "RGB_ALBEDO_NORMAL")):
        if hasattr(scene.cycles, name):
            try:
                setattr(scene.cycles, name, value)
                notes.append(f"{name}={value}")
            except Exception:
                pass
    for layer in getattr(scene, "view_layers", []):
        cycles = getattr(layer, "cycles", None)
        if cycles is not None and hasattr(cycles, "use_denoising"):
            try:
                cycles.use_denoising = True
                notes.append(f"view-layer {layer.name}")
            except Exception:
                pass
    if not getattr(scene.cycles, "use_denoising", False):
        comp = _try_compositor_denoise(scene, bpy)
        if comp:
            return "compositor Denoise node (Cycles denoiser did not stick)"
        return "off; use_denoising did not stick"
    return "OIDN CPU (" + ", ".join(notes) + ")"


def _try_compositor_denoise(scene, bpy):
    try:
        if hasattr(scene, "use_nodes"):
            scene.use_nodes = True
        if hasattr(scene.render, "use_compositing"):
            scene.render.use_compositing = True
        tree = getattr(scene, "node_tree", None)
        if tree is None:
            return False
        nodes, links = tree.nodes, tree.links
        render = next((n for n in nodes if n.bl_idname == "CompositorNodeRLayers"), None)
        out = next((n for n in nodes if n.bl_idname == "CompositorNodeComposite"), None)
        if render is None or out is None or "Image" not in render.outputs:
            return False
        den = nodes.new("CompositorNodeDenoise")
        links.new(render.outputs["Image"], den.inputs["Image"])
        if "Image" in den.outputs and "Image" in out.inputs:
            links.new(den.outputs["Image"], out.inputs["Image"])
            return True
    except Exception as exc:
        print(f"cabcad-denoise compositor failed ({exc})", flush=True)
    return False


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
    """Neutral materials. A finish colour wins; otherwise a role.

    A countertop is matte laminate. Its albedo is capped so a pale finish
    cannot blow out to the same white as the doors.
    """
    text = f"{name} {material}".lower()
    if "pull" in text or "hardware" in text or "hinge" in text:
        return (0.72, 0.72, 0.70), 0.25, 0.9
    if "plywood" in text or "build-up" in text or "buildup" in text:
        return _hex(color, (0.55, 0.40, 0.28)), 0.62, 0.0
    if "counter" in text or "solid surface" in text or "corian" in text:
        rgb = _hex(color, (0.74, 0.68, 0.58))
        rgb = tuple(min(0.78, channel) for channel in rgb)
        rough = 0.45 if ("solid surface" in text or "corian" in text) else 0.62
        return rgb, rough, 0.0
    if any(word in text for word in ("laminate", "door", "drawer", "front")):
        return _hex(color, (0.90, 0.89, 0.86)), 0.38, 0.0
    if "filler" in text:
        return _hex(color, (0.88, 0.87, 0.84)), 0.45, 0.0
    return _hex(color, (0.84, 0.83, 0.80)), 0.55, 0.0


def raking_sun(minx, maxx, miny, maxy, minz, maxz):
    """Warm morning sun from the upper front-left, aimed across the fronts.

    Blender +Y is toward the camera. The sun sits left of centre, in front of
    the run and above it, so shadows fall down and to the right: door reveals,
    the wall under the uppers, and the toe kick.
    """
    origin = (minx + (maxx - minx) * 0.12, maxy + 2.6, maxz + 1.45)
    aim = (minx + (maxx - minx) * 0.70, (miny + maxy) * 0.5, minz + (maxz - minz) * 0.28)
    return origin, aim


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


def _aim_camera(cam, cam_loc, target):
    """Point the camera with image-right = world +X. No Track-To constraint."""
    import mathutils
    right, up, look = camera_axes(cam_loc, target)
    cam.matrix_world = mathutils.Matrix((
        (right[0], up[0], -look[0], cam_loc[0]),
        (right[1], up[1], -look[1], cam_loc[1]),
        (right[2], up[2], -look[2], cam_loc[2]),
        (0.0, 0.0, 0.0, 1.0),
    ))


def _track(obj, target):
    con = obj.constraints.new(type="TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"


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
        if hasattr(scene.cycles, "adaptive_min_samples"):
            scene.cycles.adaptive_min_samples = 8
    scene.cycles.use_denoising = False
    denoise_log = _enable_cpu_denoise(scene, bpy, want_denoise)
    print(f"cabcad-denoise {denoise_log}", flush=True)
    for name, value in (("max_bounces", 4), ("diffuse_bounces", 2), ("glossy_bounces", 2)):
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
        looks = {item.identifier for item in
                 scene.view_settings.bl_rna.properties["look"].enum_items}
        for name in ("AgX - Medium High Contrast", "Medium High Contrast",
                     "AgX - Medium Contrast", "Medium Contrast"):
            if name in looks:
                scene.view_settings.look = name
                break
        scene.view_settings.exposure = -0.20
    except Exception:
        pass
    if hasattr(scene.cycles, "use_light_tree"):
        scene.cycles.use_light_tree = True

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
            spec = 0.4 if metal > 0.5 else 0.12
            _set_input(bsdf, ("Specular IOR Level", "Specular"), spec)
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
    floor = material("floor", FLOOR_COLOR, 0.72, 0.0)
    wall = material("wall", WALL_COLOR, 0.92, 0.0)
    pad = max(1.4, span * 0.9)
    cube_m(minx - pad, miny - 0.2, -0.02, maxx + pad, maxy + pad * 1.8, 0.0, floor)
    wall_top = max(maxz + 1.2, 2.8)
    # Flush to the cabinet backs. Wide enough that the frame is wall, not void.
    wall_y0, wall_y1 = back_wall_interval(miny)
    cube_m(minx - pad, wall_y0, 0.0, maxx + pad, wall_y1, wall_top, wall)

    cam_loc, target, _dist = camera_fit(
        (minx, miny, minz), (maxx, maxy, maxz), FRONT_VIEW,
        lens_mm=32.0, aspect=width / float(height), margin=1.12)
    bpy.ops.object.camera_add(location=cam_loc)
    cam = bpy.context.active_object
    cam.data.lens = 32
    cam.data.sensor_width = 36
    if hasattr(cam.data, "sensor_fit"):
        cam.data.sensor_fit = "HORIZONTAL"
    cam.data.clip_start = 0.02
    cam.data.clip_end = 200.0
    _aim_camera(cam, cam_loc, target)
    scene.camera = cam

    # Raking morning sun from the upper front-left. A small warm window
    # light keeps the fronts bright. The fill is only enough to open the
    # shadows, not to erase them.
    sun_from, aim_at = raking_sun(minx, maxx, miny, maxy, minz, maxz)
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=aim_at)
    aim = bpy.context.active_object
    bpy.ops.object.light_add(type="SUN", location=sun_from)
    sun = bpy.context.active_object
    sun.data.energy = 2.2
    sun.data.color = (1.0, 0.78, 0.48)
    if hasattr(sun.data, "angle"):
        sun.data.angle = 0.045
    _track(sun, aim)

    bpy.ops.object.light_add(type="AREA", location=(minx + (maxx - minx) * 0.28,
                                                    maxy + 2.2, maxz + 0.55))
    window = bpy.context.active_object
    window.data.energy = 28
    window.data.size = max(0.9, (maxx - minx) * 0.45)
    window.data.color = (1.0, 0.82, 0.58)
    if hasattr(window.data, "shape"):
        window.data.shape = "RECTANGLE"
        window.data.size_y = max(0.7, (maxz - minz) * 0.45)
    _track(window, aim)

    bpy.ops.object.light_add(type="AREA", location=((minx + maxx) / 2.0, maxy + 1.8,
                                                    minz + (maxz - minz) * 0.2))
    fill = bpy.context.active_object
    fill.data.energy = 6
    fill.data.size = max(1.6, (maxx - minx) * 0.7)
    fill.data.color = (1.0, 0.94, 0.86)
    _track(fill, aim)

    world = bpy.data.worlds.new("Kitchen")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.95, 0.88, 0.76, 1.0)
        bg.inputs[1].default_value = 0.035
    if hasattr(scene.cycles, "use_fast_gi"):
        scene.cycles.use_fast_gi = True
        if hasattr(scene.cycles, "fast_gi_method"):
            try:
                scene.cycles.fast_gi_method = "ADD"
            except Exception:
                pass
        lighting = getattr(world, "light_settings", None)
        if lighting is not None and hasattr(lighting, "distance"):
            lighting.distance = 0.10
    if hasattr(scene.cycles, "sample_clamp_indirect"):
        scene.cycles.sample_clamp_indirect = 0.0
    if hasattr(scene.cycles, "blur_glossy"):
        scene.cycles.blur_glossy = 0.0

    print(f"cabcad-render version {SCRIPT_VERSION} samples {samples} {width}x{height} cpu",
          flush=True)
    bpy.ops.render.render(write_still=True)
    print(f"cabcad-render wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
