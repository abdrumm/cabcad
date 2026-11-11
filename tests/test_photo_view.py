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
    assert SCRIPT_VERSION == 2


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
