"""Finished kick plate: off by default, black or grey, height overridable."""
import json
import struct
from pathlib import Path

from cabgen.ar_export import _hex_rgb, export_ar
from cabgen.client_sheet import load_job, render, render_pages
from cabgen.kickplate import build_kick
from cabgen.kitchen import KitchenError, group_settings, group_sheet, scene_of
from cabgen.omacad_export import scene_payload
from cabgen.params import KICK_PLATE_COLORS, KICK_PLATE_H, KICK_PLATE_THK
from cabgen.web import _run_page, group_view

ROOT = Path(__file__).resolve().parents[1]


def _sheet(tmp_path, extra, rows="Base cabinet 1,3drawer,27,base,,,0,,\nBase cabinet 2,base,30,base,,,27,6,\n"):
    path = tmp_path / "k.csv"
    path.write_text(
        "# upper_bottom=54\n# base_walls=left\n# counter=laminate\n"
        + extra
        + "name,style,width,run,height,depth,x,drawer_front_h,handle\n"
        + rows,
        encoding="utf-8",
    )
    return path


def test_kick_plate_is_off_unless_the_job_asks(tmp_path: Path):
    job = load_job(ROOT / "jobs" / "b3-run.csv")
    assert not any("Kick plate" in b.name for b in job.boxes)
    _boxes, _holes, parts = scene_of(job.cabs, job.settings)
    assert not any("Kick plate" in p.name for p in parts)
    assert "Kick plate" not in render(job, date="October 31, 2026").to_string()


def test_kick_plate_is_one_piece_across_touching_bases(tmp_path: Path):
    path = _sheet(tmp_path, "# kickplate=yes\n# kickplate_color=black\n")
    job = load_job(path)
    plates = [b for b in job.boxes if b.name.endswith("Kick plate")]
    assert len(plates) == 1
    plate = plates[0]
    assert abs(plate.size[0] - 57.0) < 1e-6          # 27 + 30, one length
    assert abs(plate.size[2] - KICK_PLATE_H) < 1e-6
    assert abs(plate.size[1] - KICK_PLATE_THK) < 1e-6
    assert plate.color == KICK_PLATE_COLORS["black"]
    # recessed, on the room side of the structural toe-kick plate, not part of a gable
    recess = job.bases[0].params.toe_kick_recess
    assert abs(plate.pos[1] + plate.size[1] - recess) < 1e-6
    assert plate.pos[1] > 0
    # the kick plate spans the whole run; the gable notch leaves the front of the kick clear
    toe = job.bases[0].params.toe_kick_h
    front_gables = [b for b in job.boxes if "/ Gable " in b.name and "heel" not in b.name
                    and b.pos[1] < recess and b.pos[2] < toe - 1e-6]
    assert front_gables == []
    text = render(job, date="October 31, 2026").to_string()
    assert "Kick plate" in text and "black" in text
    assert KICK_PLATE_COLORS["black"] in text
    _boxes, _holes, parts = scene_of(job.cabs, job.settings)
    cut = [p for p in parts if "Kick plate" in p.name]
    assert len(cut) == 1 and abs(cut[0].length - 57) < 1e-6 and abs(cut[0].width - KICK_PLATE_H) < 1e-6
    # a gap between bases is two plates
    gapped = _sheet(tmp_path, "# kickplate=yes\n",
                    "A,3drawer,27,base,,,0,,\nB,3drawer,18,base,,,40,,\n")
    gap_job = load_job(gapped)
    pieces = build_kick(gap_job.cabs, gap_job.settings)
    assert len(pieces) == 2
    assert abs(pieces[0].length - 27) < 1e-6 and abs(pieces[1].length - 18) < 1e-6


def test_kick_plate_color_and_height_override(tmp_path: Path):
    path = _sheet(tmp_path, "# kickplate=yes\n# kickplate_color=grey\n# kickplate_h=3\n")
    job = load_job(path)
    plate = next(b for b in job.boxes if b.name.endswith("Kick plate"))
    assert plate.color == KICK_PLATE_COLORS["grey"]
    assert abs(plate.size[2] - 3.0) < 1e-6
    text = render_pages(job, date="October 31, 2026")[0].to_string()
    assert "grey" in text and KICK_PLATE_COLORS["grey"] in text
    # the base detail page draws it too
    pages = render_pages(job, date="October 31, 2026")
    detail = next(p.to_string() for p in pages if "kick plate " in p.to_string())
    assert KICK_PLATE_COLORS["grey"] in detail
    # gray is the same as grey
    path.write_text(path.read_text().replace("grey", "gray"), encoding="utf-8")
    again = load_job(path)
    assert next(b for b in again.boxes if "Kick plate" in b.name).color == KICK_PLATE_COLORS["grey"]

    boxes, holes, _parts = scene_of(job.cabs, job.settings)
    payload = scene_payload("K", boxes, holes)
    body = next(b for b in payload["boxes"] if "Kick plate" in b["name"])
    hex_c = KICK_PLATE_COLORS["grey"].lstrip("#")
    assert body["color"][0] == round(int(hex_c[0:2], 16) / 255, 4)

    res = export_ar(out_dir=tmp_path / "ar", name="kick", sheet_path=path)
    # path was rewritten to gray; export from the grey job instead
    grey = tmp_path / "grey.csv"
    grey.write_text(
        "# upper_bottom=54\n# kickplate=yes\n# kickplate_color=grey\n# kickplate_h=3\n"
        "name,style,width,run\nA,3drawer,27,base\n",
        encoding="utf-8",
    )
    res = export_ar(out_dir=tmp_path / "ar", name="kick", sheet_path=grey)
    data = Path(res["glb"]).read_bytes()
    jlen = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20:20 + jlen])
    factors = [m["pbrMetallicRoughness"]["baseColorFactor"][:3] for m in gltf["materials"]]
    assert list(_hex_rgb(KICK_PLATE_COLORS["grey"])) in factors

    too_tall = _sheet(tmp_path, "# kickplate=yes\n# kickplate_h=8\n", "A,3drawer,27,base,,,0,,\n")
    try:
        load_job(too_tall)
    except KitchenError as exc:
        assert "taller" in str(exc)
    else:
        raise AssertionError("an 8 inch kick plate should not fit the toe kick")


def test_form_has_kick_plate_tiles_and_defaults_off():
    page = _run_page(group_view(None))
    assert 'name="kickplate"' in page and 'data-v="yes"' in page and 'data-v="no"' in page
    assert 'name="kickplate_color"' in page
    assert 'name="kickplate_h"' in page and 'value="3.75"' in page
    assert 'data-v="black"' in page and 'data-v="grey"' in page
    assert "wf-counter wf-' + counter" in page
    assert "parseFloat(wfVal('kickplate_h'))" in page
    assert "WIRE.splash_h, 'wf-splash'" not in page
    assert 'value="no"' in page
    on = group_view({"kickplate": "yes", "kickplate_color": "grey", "bw1": "27", "bs1": "3drawer"})
    assert on["kickplate"] == "yes" and on["kickplate_color"] == "grey"
    settings = group_settings({"kickplate": "yes", "kickplate_color": "grey", "walls": "left",
                                "bw1": "27", "bs1": "3drawer"})
    assert settings["kickplate"] == "yes" and settings["kickplate_color"] == "grey"
    text = group_sheet([{"name": "Base cabinet 1", "style": "3drawer", "width": 27, "run": "base",
                         "x": 0, "drawer": None, "handle": ""}], settings)
    assert "# kickplate=yes" in text and "# kickplate_color=grey" in text
    assert "# kickplate_h=3.25" in group_sheet(
        [{"name": "Base cabinet 1", "style": "3drawer", "width": 27, "run": "base",
          "x": 0, "drawer": None, "handle": ""}],
        group_settings({"kickplate": "yes", "kickplate_color": "black", "kickplate_h": "3.25",
                        "walls": "left"}))
    try:
        group_settings({"kickplate": "yes", "kickplate_color": "blue", "walls": "left"})
    except KitchenError as exc:
        assert "black or grey" in str(exc)
    else:
        raise AssertionError("blue is not a kick plate colour")
