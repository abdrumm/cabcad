"""Flat finish colours in the Omacad export (Oct 31, from CabCAD PR #2).

Only the Omacad piece is taken from that PR: the local finish catalog stays the
source of the colours, so the picks match the sheet, the front view and AR.
"""
from pathlib import Path

from cabgen import finishes
from cabgen.model3d import build_model
from cabgen.omacad_export import BUILDER, scene_payload
from cabgen.params import Params
from cabgen.parts import build_parts

SETTINGS = {"finish_fronts": "lam-walnut", "finish_box": "lam-white",
            "finish_counter": "lam-maple", "counter": "laminate"}


def _boxes(style: str = "base_1drawer_2doors") -> list:
    p = Params(style=style, name="Test", width=27)
    _parts, layout = build_parts(p)
    return build_model(p, layout).boxes


def test_paint_boxes_uses_the_picked_finish_per_role():
    boxes = _boxes()
    finishes.paint_boxes(boxes, SETTINGS)
    pal = finishes.palette_of(SETTINGS)

    fronts = [b for b in boxes if b.material.startswith("3/4\" melamine") and "door" in b.name.lower()]
    pulls = [b for b in boxes if "pull" in b.material or "hardware" in b.material]
    assert fronts, "the base cabinet has a door"
    assert all(b.color == pal["front"] for b in fronts)
    assert all(b.color == "" for b in pulls), "hardware keeps its metal"

    case = [b for b in boxes if b.material.startswith("3/4\" melamine") and "gable" in b.name.lower()]
    assert case and all(b.color == pal["case"] for b in case)


def test_blank_picks_leave_the_boxes_unpainted():
    boxes = _boxes()
    finishes.paint_boxes(boxes, {})
    assert all(b.color == "" for b in boxes), "no pick means the drawing palette, not a flat colour"


def test_countertop_takes_the_counter_finish():
    from cabgen.model3d import Box

    boxes = [Box("Countertop / top", (0.0, 0.0, 0.0), (24.0, 25.0, 1.5), "solid surface")]
    finishes.paint_boxes(boxes, SETTINGS)
    assert boxes[0].color == finishes.palette_of(SETTINGS)["solid_top"]


def test_scene_payload_carries_the_colour_only_when_set():
    boxes = _boxes()
    finishes.paint_boxes(boxes, SETTINGS)
    payload = scene_payload("Test", boxes, [])
    painted = [b for b in payload["boxes"] if "color" in b]
    assert painted, "the picked finishes reach the Omacad payload"
    for b in painted:
        assert len(b["color"]) == 4 and all(0.0 <= c <= 1.0 for c in b["color"])
        assert b["color"][3] == 1.0

    bright = {tuple(b["color"][:3]) for b in painted}
    assert tuple(round(int(finishes.get("lam-walnut")["color"][i:i + 2], 16) / 255.0, 4)
                 for i in (1, 3, 5)) in bright

    plain = scene_payload("Test", _boxes(), [])
    assert all("color" not in b for b in plain["boxes"]), "an unpainted job keeps Omacad's own colour"


def test_builder_paints_joined_parts_and_free_bodies():
    assert "def paint(body_id, color)" in BUILDER
    assert 'doc.body_colors[body_id] = rgba' in BUILDER
    # A joined part takes the colour of its first painted piece, after the join.
    assert "color = next((item[1] for item in items if item[1]), None)" in BUILDER
    assert "paint(ids[0], color)" in BUILDER
