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
    for label in ("Show in Omacad", "Carpenter 2D", "Countertop 2D", "Front view",
                  "AR view", "Email AR to me", "Photorealistic view"):
        assert label in actions
    assert "Draft client email" not in actions
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
    assert SCRIPT_VERSION == 1


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
