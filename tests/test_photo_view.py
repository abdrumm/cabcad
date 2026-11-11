"""Photorealistic view: the button is there, and it does not invent a Blender still."""
from pathlib import Path

from cabgen.client_sheet import load_job
from cabgen.photo_view import discover, fingerprint, render_photo
from cabgen.web import _run_page, group_view

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "jobs" / "sample-kitchen.csv"


def test_button_is_last_and_the_others_stay():
    page = _run_page(group_view(None))
    actions = page.split('class="actions"', 1)[1].split("</div>", 1)[0]
    for label in ("Show in Omacad", "Client sheet (PDF)", "Front view", "AR view",
                  "Email AR to me", "Draft client email", "Photorealistic view"):
        assert label in actions
    assert actions.rindex("Photorealistic view") > actions.rindex("Draft client email")
    assert 'formaction="/photo"' in actions and 'formtarget="_blank"' in actions
    # Opening the form does not embed a photorealistic image.
    assert "/files/photo/" not in page


def test_missing_pipeline_is_reported_and_not_faked(tmp_path, monkeypatch):
    monkeypatch.setenv("CABCAD_BLENDER_DIR", str(tmp_path / "no-such-stage"))
    monkeypatch.delenv("CABCAD_BLENDER", raising=False)
    monkeypatch.delenv("CABCAD_BLENDER_SCENE", raising=False)
    monkeypatch.delenv("CABCAD_BLENDER_SCRIPT", raising=False)
    info = discover()
    assert info["ready"] is False
    job = load_job(SAMPLE, "Sample Kitchen")
    page, ran = render_photo(job, tmp_path)
    assert ran is False
    assert "No Blender scene or render script is in the git repository" in page
    assert "did not" in page and "invent" in page
    assert "cabcad-blender" in page or "CABCAD_BLENDER_SCENE" in page
    assert not page.startswith("\x89PNG")
    assert not list((tmp_path / "photo").glob("*.png")) if (tmp_path / "photo").is_dir() else True


def test_same_design_is_not_rendered_twice(tmp_path, monkeypatch):
    scene = tmp_path / "stage"
    scene.mkdir()
    blend = scene / "scene.blend"
    script = scene / "render_job.py"
    blend.write_bytes(b"BLEND")
    script.write_text("print('stage')\n", encoding="utf-8")
    binary = tmp_path / "blender"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("CABCAD_BLENDER_DIR", str(scene))
    monkeypatch.setenv("CABCAD_BLENDER", str(binary))
    monkeypatch.setenv("CABCAD_BLENDER_SCENE", str(blend))
    monkeypatch.setenv("CABCAD_BLENDER_SCRIPT", str(script))
    calls = []

    def fake_run(binary, scene, script, job_json, png):
        calls.append(job_json.name)
        png.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    monkeypatch.setattr("cabgen.photo_view.run_blender", fake_run)
    job = load_job(SAMPLE, "Sample Kitchen")
    first, ran = render_photo(job, tmp_path)
    assert ran is True and "Rendered from the current design" in first
    second, ran2 = render_photo(job, tmp_path)
    assert ran2 is False and "Cached still" in second
    assert calls == [fingerprint(job) + ".json"]
    # a different width is a different design
    job.cabs[0].params.width = 40
    third, ran3 = render_photo(job, tmp_path)
    assert ran3 is True and len(calls) == 2
