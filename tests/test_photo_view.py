"""Photorealistic view: procedural Blender still, cache, one at a time."""
import threading
from pathlib import Path

from cabgen.blender.render_kitchen import SCRIPT_VERSION, denoise_plan
from cabgen.client_sheet import load_job
from cabgen.photo_view import (
    PROVEN_BLENDER, discover, export_boxes, fingerprint, render_photo, status_page,
)
from cabgen.web import _run_page, group_view

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "jobs" / "sample-kitchen.csv"


def test_button_is_last_and_the_others_stay():
    page = _run_page(group_view(None))
    actions = page.split('class="actions"', 1)[1].split("</div>", 1)[0]
    for label in ("Omacad", "Carpenter 2D", "Countertop 2D", "Front view",
                  "AR view", "Email AR to me", "Photorealistic view"):
        assert label in actions
    assert "Draft client email" not in actions
    assert "Show in Omacad" not in actions
    assert actions.rindex("Photorealistic view") > actions.rindex("Email AR to me")
    assert 'formaction="/photo"' in actions and 'formtarget="_blank"' in actions
    assert 'formaction="/carpenter-2d"' in actions and 'formaction="/counter-2d"' in actions
    assert "/files/photo-" not in page


def test_missing_blender_is_reported_and_not_faked(tmp_path, monkeypatch):
    monkeypatch.delenv("CABCAD_BLENDER", raising=False)
    monkeypatch.setattr("cabgen.photo_view.shutil.which", lambda name: None)
    info = discover()
    assert info["ready"] is False
    assert info["script"].is_file()
    job = load_job(SAMPLE, "Sample Kitchen")
    page, ran = render_photo(job, tmp_path)
    assert ran is False
    assert "5.2.4" in page and PROVEN_BLENDER in page
    assert "Nothing was rendered" in page
    assert "did not draw a picture" in page
    assert not list(tmp_path.glob("photo-*.png"))


def test_export_includes_the_perimeter_build_up():
    job = load_job(SAMPLE, "Sample Kitchen")
    names = [box["name"] for box in export_boxes(job)]
    assert any("Build-up, front" in name for name in names)
    assert any("Build-up, back" in name for name in names)
    assert SCRIPT_VERSION == 9


def test_still_is_1920_by_1080(monkeypatch):
    monkeypatch.delenv("CABCAD_BLENDER_WIDTH", raising=False)
    monkeypatch.delenv("CABCAD_BLENDER_HEIGHT", raising=False)
    monkeypatch.delenv("CABCAD_BLENDER_DENOISE", raising=False)
    from cabgen.photo_view import job_payload
    job = load_job(SAMPLE, "Sample Kitchen")
    payload = job_payload(job)
    assert payload["width"] == 1920 and payload["height"] == 1080
    assert payload["version"] == 9 and payload["samples"] == 80
    assert payload["walls"] == "0"
    assert payload["denoise"] is True


def test_camera_fits_the_whole_stack_including_a_wide_run():
    """960x540 at 32 mm cropped the uppers and the toe kicks when the camera
    sat a fixed distance off the run width. Every corner has to land inside
    the frame, for a tall stack and for a long one."""
    from cabgen.blender.render_kitchen import _cross, _dot, _norm, camera_fit
    tan_h = (36.0 / 2.0) / 32.0
    tan_v = (36.0 / (960 / 540) / 2.0) / 32.0
    cases = (
        ((0.0, -0.7, 0.0), (3.4, 0.05, 2.2)),    # wide, full height
        ((0.0, -0.6, 0.0), (0.8, 0.0, 2.3)),     # narrow and tall
    )
    view = (0.38, 1.0, 0.16)
    for bmin, bmax in cases:
        cam, _center, dist = camera_fit(bmin, bmax, view, lens_mm=32.0, aspect=960 / 540, margin=1.16)
        assert dist > 1.0
        back = _norm(view)
        look = (-back[0], -back[1], -back[2])
        right = _norm(_cross((0.0, 0.0, 1.0), look))
        up = _norm(_cross(look, right))
        for x in (bmin[0], bmax[0]):
            for y in (bmin[1], bmax[1]):
                for z in (bmin[2], bmax[2]):
                    p = (x - cam[0], y - cam[1], z - cam[2])
                    depth = _dot(p, look)
                    assert depth > 0.2
                    assert abs(_dot(p, right)) / depth <= tan_h / 1.16 + 1e-6
                    assert abs(_dot(p, up)) / depth <= tan_v / 1.16 + 1e-6


def test_counter_laminate_stays_a_surface_and_the_sun_rakes():
    from cabgen.blender.render_kitchen import SIDE_WALL_COLOR, WALL_COLOR, _look, raking_sun
    top, rough, _metal = _look("Countertop / top", "laminate", "#d8cfbf")
    door, door_rough, _metal = _look("door", "laminate", "#f7f4ee")
    assert rough > door_rough and max(top) <= 0.78
    assert max(top) < max(door)
    # The wall is a warm grey, not the same white as a door. The side wall
    # is darker than the back wall so the corner reads.
    assert max(WALL_COLOR) < 0.85 and WALL_COLOR[0] > WALL_COLOR[2]
    assert max(SIDE_WALL_COLOR) < min(WALL_COLOR)
    origin, aim = raking_sun(0.0, 3.0, -0.6, 0.1, 0.0, 2.2)
    assert origin[0] > 3.0
    rise = origin[2] - aim[2]
    reach = origin[0] - aim[0]
    assert rise > 0 and rise < reach * 0.45


def test_the_right_hand_cabinet_stays_on_the_right():
    """U4, the microwave, is the rightmost upper. The picture must not mirror it."""
    from cabgen.blender.render_kitchen import box_center_m, camera_for_run, image_x
    left = box_center_m((0.0, 0.0, 54.0), (24.0, 12.0, 30.0))
    micro = box_center_m((72.0, 0.0, 54.0), (30.0, 12.0, 30.0))
    assert micro[0] > left[0]
    bmin = (left[0] - 0.3, min(left[1], micro[1]) - 0.4, 0.0)
    bmax = (micro[0] + 0.3, max(left[1], micro[1]) + 0.2, 2.2)
    cam, target, _dist, _view = camera_for_run(bmin, bmax, "left", aspect=16 / 9)
    assert image_x(micro, cam, target) > image_x(left, cam, target)


def test_side_wall_sits_on_the_end_the_job_names():
    from cabgen.blender.render_kitchen import side_wall_spans
    left, right = side_wall_spans("left", 0.0, 3.2)
    assert left is not None and right is None
    assert left[0] < 0.0 and 0.0 <= left[1] <= 0.004
    left, right = side_wall_spans("right", 0.0, 3.2)
    assert left is None and right is not None and 3.196 <= right[0] <= 3.2
    left, right = side_wall_spans("both", 0.0, 3.2)
    assert left is not None and right is not None
    assert side_wall_spans("0", 0.0, 3.2) == (None, None)


def test_camera_shows_the_finished_end_and_keeps_the_stack():
    """A left wall's finished end is the right one. The view is 35 degrees
    off square, the left wall's face is inside the frame, and the wall runs
    past the camera so the picture cannot see around it."""
    from cabgen.blender.render_kitchen import (
        EYE_CLEARANCE, FRAME_MARGIN, camera_for_run, in_frame, side_wall_forward,
        view_angle,
    )
    # The renderer frames the cabinets plus a short strip of wall in front.
    bmin, bmax = (0.0, -0.7, 0.0), (3.4, 0.05 + 0.22, 2.2)
    cam, target, dist, _view = camera_for_run(
        bmin, bmax, "left", aspect=16 / 9, margin=FRAME_MARGIN)
    assert dist > 1.0
    assert abs(view_angle(cam, target) - 35.0) < 1.0
    assert abs((bmax[2] - cam[2]) - EYE_CLEARANCE) < 1e-6
    assert cam[2] < bmax[2]
    assert cam[0] > bmax[0]
    assert cam[1] > bmax[1]
    for x in (bmin[0], bmax[0]):
        for y in (bmin[1], bmax[1]):
            for z in (bmin[2], bmax[2]):
                assert in_frame((x, y, z), cam, target, aspect=16 / 9)
    # The left wall face beside the run, from the floor to above the uppers.
    for point in ((0.0, -0.7, 0.05), (0.0, -0.7, 2.1), (0.0, 0.2, 0.05), (0.0, 0.2, 2.1)):
        assert in_frame(point, cam, target, aspect=16 / 9)
    _back, forward = side_wall_forward(-0.76, cam[1])
    assert forward > cam[1]
    other, _t, _d, _v = camera_for_run(bmin, bmax, "right", aspect=16 / 9)
    assert other[0] < bmin[0]
    assert abs(view_angle(other, _t) - 35.0) < 1.0


def test_back_wall_sits_on_the_cabinet_backs():
    from cabgen.blender.render_kitchen import back_wall_interval
    back = -1.4
    y0, y1 = back_wall_interval(back)
    assert y0 < y1 and abs(y1 - back) < 1e-9


def test_empty_denoiser_enum_still_tries_oidn():
    from cabgen.blender.render_kitchen import denoise_should_try
    assert denoise_should_try(True, True, []) is True
    assert denoise_should_try(True, True, ["OPENIMAGEDENOISE"]) is True
    assert denoise_should_try(False, True, []) is False
    assert denoise_should_try(True, False, []) is False


def test_photo_page_does_not_crop_the_still(tmp_path, monkeypatch):
    binary = tmp_path / "blender"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("CABCAD_BLENDER", str(binary))

    def fake_run(binary, script, job_json, png):
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 40)

    monkeypatch.setattr("cabgen.photo_view.run_blender", fake_run)
    job = load_job(SAMPLE, "Sample Kitchen")
    page, _ran = render_photo(job, tmp_path, block=True)
    assert "object-fit: contain" in page
    assert "object-fit: cover" not in page


def test_denoise_falls_back_without_a_gpu_or_oidn():
    assert denoise_plan(False, True, "CPU")["denoise"] is False
    assert denoise_plan(True, False, "CPU")["denoise"] is False
    assert denoise_plan(True, True, "OPTIX")["denoise"] is False
    assert denoise_plan(True, True, "CPU") == {"denoise": True, "reason": "OIDN on the CPU"}


def test_same_design_is_not_rendered_twice(tmp_path, monkeypatch):
    binary = tmp_path / "blender"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("CABCAD_BLENDER", str(binary))
    calls = []

    def fake_run(binary, script, job_json, png):
        calls.append(job_json.name)
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 40)

    monkeypatch.setattr("cabgen.photo_view.run_blender", fake_run)
    job = load_job(SAMPLE, "Sample Kitchen")
    first, ran = render_photo(job, tmp_path, block=True)
    assert ran is True and "Rendered from the current design" in first
    second, ran2 = render_photo(job, tmp_path, block=True)
    assert ran2 is False and "Cached still" in second
    assert len(calls) == 1
    job.cabs[0].params.width = 40
    third, ran3 = render_photo(job, tmp_path, block=True)
    assert ran3 is True and len(calls) == 2
    assert "photo-" in third


def test_omacad_starts_one_render_without_waiting(tmp_path, monkeypatch):
    """A successful Omacad build enqueues the still and returns at once.
    The photo button joins that work. A bad form and GET /run do not render.
    A Blender failure stays on the photo status page."""
    import time
    import urllib.request
    from http.server import ThreadingHTTPServer

    from cabgen.photo_view import fingerprint, status_page
    from cabgen.web import _handle_photo, _handle_run, _make_handler

    binary = tmp_path / "blender"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("CABCAD_BLENDER", str(binary))
    monkeypatch.setattr("cabgen.web.write_kitchen", lambda *a, **k: (True, "opened"))
    started = threading.Event()
    release = threading.Event()
    calls = []

    def fake_run(binary, script, job_json, png):
        calls.append(job_json.name)
        started.set()
        release.wait(5)
        raise OSError("Blender failed on purpose")

    monkeypatch.setattr("cabgen.photo_view.run_blender", fake_run)
    form = {"job": "Smith Kitchen", "bw1": "27", "bs1": "3drawer", "uw1": "27",
            "us1": "upper", "walls": "left", "counter": "laminate"}
    t0 = time.perf_counter()
    page = _handle_run(form, tmp_path)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0
    assert "opened" in page and "Blender failed" not in page
    assert started.wait(2)
    assert len(calls) == 1
    photo, err = _handle_photo(form, tmp_path)
    assert err == "" and b"already running" in photo
    assert len(calls) == 1
    bad = _handle_run({"bw1": "8"}, tmp_path)
    assert "under 12" in bad and len(calls) == 1
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(tmp_path))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        port = srv.server_address[1]
        got = urllib.request.urlopen(f"http://127.0.0.1:{port}/run", timeout=3)
        body = got.read().decode()
        assert ">Omacad<" in body and len(calls) == 1
    finally:
        srv.shutdown()
    release.set()
    try:
        from cabgen.client_sheet import load_job
        job = load_job(tmp_path / "base-run.csv", "Smith Kitchen")
        fp = fingerprint(job)
        for _ in range(50):
            if "Blender failed" in status_page(tmp_path, fp):
                break
            threading.Event().wait(0.05)
        assert "Blender failed" in status_page(tmp_path, fp)
        assert "Blender failed" not in page
    finally:
        import cabgen.photo_view as pv
        pv._running = None
        pv._pending = None


def test_only_one_render_runs_and_status_does_not_start_one(tmp_path, monkeypatch):
    binary = tmp_path / "blender"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("CABCAD_BLENDER", str(binary))
    started = threading.Event()
    release = threading.Event()
    calls = []

    def fake_run(binary, script, job_json, png):
        calls.append(1)
        started.set()
        assert release.wait(5)
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 40)

    monkeypatch.setattr("cabgen.photo_view.run_blender", fake_run)
    import cabgen.photo_view as pv
    pv._running = None
    pv._pending = None
    job = load_job(SAMPLE, "Sample Kitchen")
    page, ran = render_photo(job, tmp_path, block=False)
    assert ran is True and "Rendering one still" in page
    assert started.wait(2)
    fp = fingerprint(job)
    assert "does not start" in status_page(tmp_path, "no-such-design")
    again, ran2 = render_photo(job, tmp_path, block=False)
    assert ran2 is False and "already running" in again
    assert calls == [1]
    release.set()
    for _ in range(50):
        if (tmp_path / f"photo-{fp}.png").is_file():
            break
        threading.Event().wait(0.05)


def test_script_asks_for_cpu_and_a_denoise_fallback():
    text = (ROOT / "cabgen" / "blender" / "render_kitchen.py").read_text(encoding="utf-8")
    assert 'scene.cycles.device = "CPU"' in text
    assert 'compute_device_type = "NONE"' in text
    assert "use_denoising = False" in text
    assert "denoise_plan" in text
    assert "no .blend" in text
