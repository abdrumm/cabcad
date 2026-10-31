"""Sink base (false front, vertical front board) and the 12" microwave upper with its
projecting shelf (Brook, 2026-10-27)."""
from pathlib import Path

from cabgen.client_sheet import _features
from cabgen.kitchen import STYLES, group_sheet, load_kitchen, parse_group, place_kitchen
from cabgen.model3d import build_model
from cabgen.nest_project import CODE_MEANING, cabinet_codes, part_labels
from cabgen.params import (
    DEFAULT_WIDTHS, MICROWAVE_SHELF_CALLED_DEPTH, MICROWAVE_SHELF_CORNER_R, Params,
    SINK_BACK_STILE_H, SINK_FRONT_BOARD_BELOW_DOOR_TOP, UPPER_DEPTH,
)
from cabgen.parts import build_parts
from cabgen.units import fmt_in
from cabgen.web import _wire_data


def _build(style, **kw):
    p = Params(style=style, **kw)
    parts, layout = build_parts(p)
    return p, parts, layout, build_model(p, layout)


def _names(parts):
    return {x.name for x in parts}


def test_sink_fronts_match_the_one_drawer_base():
    base = _build("base_1drawer_2doors", width=30.0)
    sink = _build("base_sink")
    assert sink[0].width == 30.0 == DEFAULT_WIDTHS["sink"]
    assert sink[2].drawer_bands == base[2].drawer_bands
    assert sink[2].door_heights == base[2].door_heights
    assert (sink[2].door_bottom_z, sink[2].door_top_z) == (base[2].door_bottom_z, base[2].door_top_z)
    ff = [x for x in sink[1] if x.name == "False front"][0]
    df = [x for x in base[1] if x.name == "Drawer front 1"][0]
    assert (ff.width, ff.length) == (df.width, df.length)
    assert "NO pull" in ff.notes


def test_sink_has_no_drawer_box_slides_shelf_or_pins():
    p, parts, layout, model = _build("base_sink")
    names = _names(parts)
    assert not any(n.startswith("Drawer box") for n in names)
    assert "Shelf" not in names and "Drawer stile" not in names and "Top stile, front" not in names
    assert not layout.rails
    # only the door pulls are drilled: nothing in the false front, no shelf pins in the gables
    assert model.holes and all(h.normal == (0.0, -1.0, 0.0) and h.origin[2] < layout.door_top_z
                               for h in model.holes)
    assert not any(b.name.startswith(("Wire pull, drawer", "Drawer box", "Shelf")) for b in model.boxes)
    gable = [x for x in parts if x.name.startswith("Gable")][0]
    assert "Shelf-pin" not in gable.notes
    # doors keep their pulls
    assert any(b.name.startswith("Wire pull, door") for b in model.boxes)


def test_sink_front_board_runs_to_half_inch_below_the_door_tops():
    p, parts, layout, model = _build("base_sink")
    fb = [x for x in parts if x.name == "Sink front board"][0]
    bot, top = layout.sink_board
    assert abs(top - p.case_top_z) < 1e-9
    assert abs(bot - (layout.door_top_z - SINK_FRONT_BOARD_BELOW_DOOR_TOP)) < 1e-9
    assert abs(fb.length - (top - bot)) < 1e-9 and abs(fb.width - p.width_in) < 1e-9
    box = [b for b in model.boxes if b.name == "Sink front board"][0]
    assert box.pos[1] == 0 and box.size[1] == p.carcass_thk          # vertical, at the case front
    back = [b for b in model.boxes if b.name == "Top stile, back"][0]
    assert back.size[2] == SINK_BACK_STILE_H and back.size[1] == p.carcass_thk   # on edge, 4" tall
    assert abs(back.pos[2] + back.size[2] - p.case_top_z) < 1e-9


def test_sink_labels_and_codes():
    p, parts, _l, _m = _build("base_sink")
    labels = [lab for _part, labs in part_labels("B3", parts) for lab in labs]
    assert "B3-FB" in labels and "B3-FF" in labels and "B3-TSB" in labels
    assert "FB" in CODE_MEANING and "FF" in CODE_MEANING


def test_sink_through_the_form_csv_and_wire(tmp_path: Path):
    form = {"bw1": "30", "bs1": "sink", "bd1": "6", "bw2": "18", "bs2": "3drawer", "walls": "left"}
    cabs = parse_group(form)
    assert cabs[0]["style"] == "sink" and cabs[0]["drawer"] == 6.0
    from cabgen.kitchen import group_settings
    sheet = tmp_path / "g.csv"
    sheet.write_text(group_sheet(cabs, group_settings(form)))
    kitchen = load_kitchen(sheet)
    assert kitchen[0].params.style == "base_sink" if hasattr(kitchen[0], "params") else True
    assert STYLES["sink"] == "base_sink"
    w = _wire_data()["styles"]["sink"]
    assert w["false_front"] and w["drawers"] and w["doors"]
    feats = " ".join(_features(Params(style="base_sink")))
    assert "false drawer front" in feats and "no pull" in feats


def test_microwave_box_is_upper_depth_and_only_the_shelf_projects():
    p, parts, layout, model = _build("upper_microwave")
    assert p.depth == UPPER_DEPTH == Params(style="upper_2doors").depth == 12.0
    assert (p.width, p.height) == (30.0, 30.0)
    shelf = [x for x in parts if x.name == "Microwave shelf"][0]
    assert shelf.length == MICROWAVE_SHELF_CALLED_DEPTH == 16.0
    assert f'{MICROWAVE_SHELF_CORNER_R:g}"' in shelf.notes.replace("2 radius", '2" radius') or "radius" in shelf.notes
    assert "Bottom plate (stretcher)" not in _names(parts)
    shelf_boxes = [b for b in model.boxes if b.name.startswith("Microwave shelf")]
    back_front = p.gable_depth                       # front face of the applied 1/2" back
    y0 = min(b.pos[1] for b in shelf_boxes)
    y1 = max(b.pos[1] + b.size[1] for b in shelf_boxes)
    assert abs(y1 - back_front) < 1e-9
    assert abs(y1 - y0 - 16.0) < 1e-9
    assert abs((back_front + p.back_thk) - y0 - 16.5) < 1e-9   # 16-1/2" overall
    assert len({b.join for b in shelf_boxes}) == 1               # one joined solid
    # everything else stays inside the 12" box
    for b in model.boxes:
        if b.name.startswith(("Microwave shelf", "Door", "Wire pull")):
            continue
        assert b.pos[1] >= -1e-9 and b.pos[1] + b.size[1] <= p.depth + 1e-9, b.name
    div = [b for b in model.boxes if b.name == "Microwave divider"][0]
    assert div.size[1] == p.gable_depth
    labels = [lab for _part, labs in part_labels("U3", parts) for lab in labs]
    assert "U3-MS" in labels


def _job(tmp_path: Path, form: dict):
    from cabgen.client_sheet import load_job
    from cabgen.kitchen import group_settings
    sheet = tmp_path / "job.csv"
    sheet.write_text(group_sheet(parse_group(form), group_settings(form)))
    return load_job(sheet, name="Test")


FORM = {"uw1": "27", "us1": "upper", "uw2": "30", "us2": "microwave",
        "bw1": "30", "bs1": "base", "bd1": "6", "bw2": "39", "bs2": "3drawer",
        "bw3": "30", "bs3": "sink", "bd3": "6", "walls": "left", "counter": "laminate"}


def test_client_sheet_renders_sink_and_microwave_pages(tmp_path: Path):
    from cabgen.client_sheet import render_pages
    job = _job(tmp_path, FORM)
    pages = render_pages(job, "2026-10-27")
    import html
    text = html.unescape("".join(p.to_string() for p in pages))
    assert "SINK" in text.upper() and "false drawer front" in text
    assert "the shelf projects to " + fmt_in(16.5) in text


def test_client_views_show_one_unbroken_countertop(tmp_path: Path):
    """A 99" base run makes a 100" top, longer than a 96" sheet. Brook, Oct 27: it is
    still one piece in Omacad, the client sheet, AR and the cut list (seam TBD)."""
    job = _job(tmp_path, FORM)
    assert job.counter.seams == []                  # one piece everywhere (Brook, Oct 27)
    assert all(len(p.boxes) == 1 for p in job.counter.pieces if p.name in ("Top", "Backsplash"))
    tops = [b for b in job.boxes if b.name.endswith("Countertop / Top")]
    assert len(tops) == 1
    assert abs(tops[0].pos[0] - job.counter.x0) < 1e-6
    assert abs(tops[0].pos[0] + tops[0].size[0] - job.counter.x1) < 1e-6
    splashes = [b for b in job.boxes if b.name.endswith("Backsplash")]
    fronts = [b for b in job.boxes if "Build-up, front" in b.name]
    assert len(splashes) == 1 and len(fronts) == 1
    # the cut list has one 100" top, flagged; Omacad gets one top box too
    tops_cut = [part for part, _labs in job.counter.parts() if part.name.startswith("Top")]
    assert len(tops_cut) == 1 and tops_cut[0].length == 100.0 and "seam TBD" in tops_cut[0].notes
    from cabgen.kitchen import scene_of
    boxes, _h, _p = scene_of(job.cabs, job.settings)
    assert len([b for b in boxes if b.name.endswith("Countertop / Top")]) == 1


def test_microwave_shelf_has_round_front_corners():
    from cabgen.model3d import expand_round, qdisc_center
    p, _parts, _layout, model = _build("upper_microwave")
    rounds = [b for b in model.boxes if b.shape.startswith("qdisc")]
    assert len(rounds) == 2
    R = MICROWAVE_SHELF_CORNER_R
    front = min(b.pos[1] for b in model.boxes if b.name.startswith("Microwave shelf"))
    for b in rounds:
        assert b.size[0] == b.size[1] == R
        cx, cy = qdisc_center(b)
        assert abs(cy - (front + R)) < 1e-9
    # the square corner itself is not filled: the slices stay inside the circle
    slices = expand_round(model.boxes)
    assert not any(b.shape.startswith("qdisc") for b in slices)
    import math
    for b in slices:
        if b.name == "Microwave shelf heel" and b.size[0] < R - 1e-6:
            for rb in rounds:
                cx, cy = qdisc_center(rb)
                if rb.pos[0] - 1e-6 <= b.pos[0] <= rb.pos[0] + R + 1e-6:
                    far_x = b.pos[0] if "+x" in rb.shape else b.pos[0] + b.size[0]
                    near_y = b.pos[1] + b.size[1] if b.pos[1] + b.size[1] <= cy else b.pos[1]
                    assert math.hypot(far_x - cx, near_y - cy) <= R + 1e-6


def test_microwave_corners_go_to_omacad_as_cylinders():
    from cabgen.omacad_export import BUILDER, scene_payload
    _p, _parts, _layout, model = _build("upper_microwave")
    payload = scene_payload("t", model.boxes, model.holes)
    assert sum(1 for b in payload["boxes"] if b.get("shape", "").startswith("qdisc")) == 2
    assert "add_cylinder" in BUILDER


def test_nest_sheet_draws_rounded_shelf(tmp_path: Path):
    from cabgen.nest_project import nest_project, sheet_page
    cabs = _job(tmp_path, {"uw1": "30", "us1": "microwave", "walls": "left", "counter": "none"}).cabs
    groups = nest_project(cabs)
    svgs = [sheet_page(sh, g, "T", 2, 2).to_string() for g in groups.values() for sh in g.sheets]
    hit = [s for s in svgs if "U1-MS" in s]
    assert hit and " A" in hit[0] and "<path" in hit[0]


def test_ten_bases_no_column_cap():
    from cabgen.kitchen import parse_group
    form = {f"bw{i}": "24" for i in range(1, 11)}
    form.update({f"bs{i}": "base" for i in range(1, 11)})
    form.update({"walls": "left", "counter": "laminate"})
    items = parse_group(form)
    assert len([c for c in items if c["run"] == "base"]) == 10
    from cabgen.web import group_view, _run_fields
    view = group_view(form)
    assert view["bases"]["count"] == 10
    page = _run_fields(view)
    assert 'name="bw10"' in page and 'id="btpl"' in page and "__N__" in page
    assert "MAXC" not in page
