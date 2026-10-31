"""The owner's run: one countertop, one-piece base gables, one splash colour.

The job is the one that showed a hole over the last base, a toe-kick split on
every base side, and a side splash darker than the backsplash.
"""
import math
from pathlib import Path

from cabgen.client_sheet import (
    _deck_z, _iso_faces, counter_paint_rank, load_job, render,
)
from cabgen.finishes import lookup
from cabgen.model3d import build_model, expand_round, qdisc_center
from cabgen.omacad_export import scene_payload
from cabgen.params import MICROWAVE_SHELF_CORNER_R
from cabgen.parts import build_parts

ROOT = Path(__file__).resolve().parents[1]
JOB = ROOT / "jobs" / "b3-run.csv"


def test_counter_is_one_slab_and_it_paints_above_the_bases():
    job = load_job(JOB)
    tops = [b for b in job.boxes if b.name.endswith("Countertop / Top")]
    assert len(tops) == 1
    top = tops[0]
    assert abs(top.pos[0] - job.counter.x0) < 1e-6
    assert abs(top.size[0] - job.counter.length) < 1e-6
    assert job.counter.length == 100.0 and job.counter.seams == []
    # the same single slab is what AR and Omacad are given
    from cabgen.kitchen import scene_of
    scene, _holes, _parts = scene_of(job.cabs, job.settings)
    scene_tops = [b for b in scene if b.name.endswith("Countertop / Top")]
    assert len(scene_tops) == 1 and scene_tops[0].size[0] == top.size[0]

    deck = _deck_z(job.boxes)
    bottom = next(b for b in job.boxes if "Base cabinet 3 / Bottom" in b.name)
    front = next(b for b in job.boxes if "Build-up, front" in b.name)
    back = next(b for b in job.boxes if b.name.endswith("Countertop / Backsplash"))
    side = next(b for b in job.boxes if "Side splash" in b.name)
    assert counter_paint_rank(bottom, deck) < counter_paint_rank(front, deck) < counter_paint_rank(top, deck)
    assert counter_paint_rank(top, deck) < counter_paint_rank(back, deck) == counter_paint_rank(side, deck)
    # nothing under the deck is allowed to paint after it
    for b in job.boxes:
        if b.pos[2] + b.size[2] <= deck + 1e-4 and "Countertop /" not in b.name:
            assert counter_paint_rank(b, deck) < counter_paint_rank(top, deck)


def test_base_gables_are_one_piece_with_the_toe_kick_notch():
    job = load_job(JOB)
    for cab in job.bases:
        parts, layout = build_parts(cab.params)
        gables = [p for p in parts if p.name.startswith("Gable")]
        assert len(gables) == 1
        assert gables[0].qty == 2
        assert abs(gables[0].width - cab.params.height) < 1e-6  # blank is full height
        assert "One piece" in gables[0].notes and "Notch" in gables[0].notes
        model = build_model(cab.params, layout)
        left = [b for b in model.boxes if b.name.startswith("Gable L")]
        assert len(left) == 2 and len({b.join for b in left}) == 1
        upper = min(left, key=lambda b: b.pos[1])
        heel = max(left, key=lambda b: b.pos[1])
        assert upper.pos[2] == cab.params.toe_kick_h
        assert abs(upper.pos[2] + upper.size[2] - cab.params.case_top_z) < 1e-6
        assert heel.pos[2] == 0.0 and heel.pos[1] == cab.params.toe_kick_recess
        # the notch itself is empty: nothing of this gable in front of the recess, below the kick
        assert not any(b.pos[1] < cab.params.toe_kick_recess - 1e-6 and b.pos[2] < cab.params.toe_kick_h - 1e-6
                       for b in left)


def test_splashes_share_the_countertop_finish(tmp_path: Path):
    sheet = tmp_path / "splashes.csv"
    sheet.write_text(
        "# upper_bottom=54\n"
        "# base_walls=both\n"
        "# filler_side=right\n"
        "# filler=1\n"
        "# counter=laminate\n"
        "# splash_left=yes\n"
        "# splash_right=yes\n"
        "# top=3450-58\n"
        "name,style,width,run,height,depth,x,drawer_front_h,handle\n"
        "Base cabinet 1,3drawer,27,base,,,0,,\n"
        "Base cabinet 2,base,30,base,,,27,6,\n",
        encoding="utf-8",
    )
    job = load_job(sheet)
    jet = lookup("3450-58").hex
    back = next(b for b in job.boxes if b.name.endswith("Countertop / Backsplash"))
    sides = [b for b in job.boxes if "Side splash" in b.name]
    assert len(sides) == 2
    assert back.color == jet
    assert {b.color for b in sides} == {jet}
    assert _iso_faces(back) == (jet, jet, jet)
    assert all(_iso_faces(b) == (jet, jet, jet) for b in sides)

    from cabgen.kitchen import scene_of
    boxes, holes, _parts = scene_of(job.cabs, job.settings)
    payload = scene_payload("Splashes", boxes, holes)
    def rgba(fragment):
        hit = next(b for b in payload["boxes"] if fragment in b["name"])
        return hit["color"]
    assert rgba("Backsplash") == rgba("Side splash, left") == rgba("Side splash, right")

    from cabgen.ar_export import _hex_rgb, export_ar, swatch
    assert swatch(back)[1] == swatch(sides[0])[1] == jet
    res = export_ar(out_dir=tmp_path / "ar", name="splashes", sheet_path=sheet)
    data = Path(res["glb"]).read_bytes()
    import json
    import struct
    jlen = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20:20 + jlen])
    factors = [m["pbrMetallicRoughness"]["baseColorFactor"][:3] for m in gltf["materials"]]
    assert list(_hex_rgb(jet)) in factors
    # one material carries that colour; the two splashes are not two shades of it
    assert factors.count(list(_hex_rgb(jet))) == 1


def test_microwave_shelf_stays_inside_the_case_and_inside_the_radius():
    """The shelf does project forward of the 12\" box (that is the spec). It does not
    project past the sides of the case, and the corner steps stay inside the 2\" radius.
    Page-1 pixels of this shelf were identical at ce84eef, 84c4596 and c0934c9; the
    steps used to be as wide as the circle at their middle, so each band bulged past
    the radius."""
    job = load_job(JOB)
    cab = next(c for c in job.cabs if c.params.is_microwave)
    shelf = [b for b in job.boxes if "Upper 4" in b.name and "Microwave shelf" in b.name]
    assert shelf
    left = cab.x + cab.params.carcass_thk
    right = cab.x + cab.params.width - cab.params.carcass_thk
    for b in shelf:
        assert b.pos[0] >= left - 1e-6
        assert b.pos[0] + b.size[0] <= right + 1e-6
    front = min(b.pos[1] for b in shelf)
    # 16" from the face of the back, so 4-1/2" past the 11-1/2" gable
    assert abs((cab.y + cab.params.gable_depth) - (front + 16.0)) < 1e-6
    R = MICROWAVE_SHELF_CORNER_R
    # rebuild the corner squares from the model, before the slices
    _parts, layout = build_parts(cab.params)
    model = build_model(cab.params, layout)
    rounds = [b for b in model.boxes if b.shape.startswith("qdisc")]
    assert len(rounds) == 2
    for b in expand_round(model.boxes):
        if b.shape != "slice":
            continue
        for rb in rounds:
            cx, cy = qdisc_center(rb)
            if not (rb.pos[0] - 1e-6 <= b.pos[0] <= rb.pos[0] + R + 1e-6):
                continue
            if not (rb.pos[1] - 1e-6 <= b.pos[1] <= rb.pos[1] + R + 1e-6):
                continue
            for xx in (b.pos[0], b.pos[0] + b.size[0]):
                for yy in (b.pos[1], b.pos[1] + b.size[1]):
                    assert math.hypot(xx - cx, yy - cy) <= R + 1e-4
