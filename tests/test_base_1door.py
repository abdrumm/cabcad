"""Single-door base: the pull sits on the handle edge, same side rule as a 1-door upper.

The holes stay the base-door distance down from the top. A pair of doors and every
drawer pull stay on the case centerline.
"""
from pathlib import Path

from cabgen.client_sheet import job_from, render_pages, style_groups
from cabgen.kitchen import (
    KitchenError, apply_discovered_rules, group_settings, group_sheet, load_kitchen,
    parse_group, place_kitchen,
)
from cabgen.model3d import build_model
from cabgen.params import UPPER_PULL_EDGE_INSET, Params, door_rule_warnings
from cabgen.parts import build_parts
from cabgen.web import _run_page, _wire_data, group_view


def _build(style, **kw):
    p = Params(style=style, **kw)
    parts, layout = build_parts(p)
    return p, parts, layout, build_model(p, layout)


def _door_pull_holes(model, door):
    x0, x1 = door.pos[0], door.pos[0] + door.size[0]
    return [h for h in model.holes
            if h.normal == (0.0, -1.0, 0.0) and x0 < h.origin[0] < x1]


def test_default_handle_side_is_right_like_an_upper():
    p = Params(style="base_1door")
    assert p.handle_side == "right"
    assert p.hinge_side == "left"
    assert p.doors == 1 and p.drawers == 0
    assert p.has_toe_kick and p.has_shelf
    assert p.width == 18 and p.depth == 23.5
    _assert_pull_on_side("right")


def test_handle_side_left_and_right_move_the_pull_and_the_hinges():
    for handle in ("right", "left"):
        _assert_pull_on_side(handle)


def _assert_pull_on_side(handle):
    p, parts, layout, model = _build("base_1door", width=18.0, handle_side=handle)
    assert p.doors == 1 and p.hinge_side == ("left" if handle == "right" else "right")
    door_part = [x for x in parts if x.name == "Door"]
    assert len(door_part) == 1
    assert f"Handle {handle.upper()}" in door_part[0].notes
    assert f"in from the {handle} edge" in door_part[0].notes
    assert "down from the top of the door" in door_part[0].notes
    assert "Stock wire pull" not in door_part[0].notes
    assert "centerline" not in door_part[0].notes
    door = [b for b in model.boxes if b.name.startswith("Door, handle")][0]
    assert door.name == f"Door, handle {handle[0].upper()}"
    holes = _door_pull_holes(model, door)
    assert len(holes) == 2
    assert all(abs(h.diameter - p.pull_hole_dia) < 1e-9 for h in holes)
    xs = {round(h.origin[0], 4) for h in holes}
    edge = door.pos[0] + (door.size[0] if handle == "right" else 0.0)
    expect = edge - UPPER_PULL_EDGE_INSET if handle == "right" else edge + UPPER_PULL_EDGE_INSET
    assert xs == {round(expect, 4)}
    assert abs(abs(edge - expect) - UPPER_PULL_EDGE_INSET) < 1e-9
    mid = door.pos[0] + door.size[0] / 2
    assert abs(expect - mid) > 1
    zs = sorted(round(h.origin[2], 4) for h in holes)
    d_top = layout.door_top_z
    assert zs == [round(d_top - p.pull_from_top - p.pull_span, 4),
                  round(d_top - p.pull_from_top, 4)]
    # same x as a 1-door upper of this width; the upper's holes are lower on the door
    up = _build("upper_1door", width=18.0, handle_side=handle)[3]
    up_door = [b for b in up.boxes if b.name.startswith("Door")][0]
    up_x = {round(h.origin[0], 4) for h in _door_pull_holes(up, up_door)}
    assert up_x == xs
    cups = [h for h in model.holes if h.diameter > 1.0]
    assert len(cups) == 2
    if handle == "right":
        assert all(h.origin[0] < p.width / 2 for h in cups)
    else:
        assert all(h.origin[0] > p.width / 2 for h in cups)
    assert any(b.name == f"Wire pull, door {handle[0].upper()}" for b in model.boxes)


def test_a_wide_single_door_base_stays_one_door():
    """The 24\" pair rule is for wall uppers. A wide base keeps the one door and the handle."""
    p, parts, layout, model = _build("base_1door", name="Wide base", width=36, handle_side="left")
    assert p.doors == 1 and p.style == "base_1door" and not p.door_count_overridden
    assert door_rule_warnings(p) == []
    assert [x.name for x in parts if x.name.startswith("Door")] == ["Door"]
    door = [b for b in model.boxes if b.name.startswith("Door")][0]
    holes = _door_pull_holes(model, door)
    assert {round(h.origin[0], 4) for h in holes} == {round(door.pos[0] + UPPER_PULL_EDGE_INSET, 4)}


def test_pair_and_drawer_pulls_ignore_handle_side():
    p, parts, layout, model = _build("base_1drawer_2doors", width=30, handle_side="left")
    doors = sorted((b for b in model.boxes if b.name.startswith("Door")), key=lambda b: b.pos[0])
    assert [d.name for d in doors] == ["Door L", "Door R"]
    center = p.width / 2
    for i, door in enumerate(doors):
        expect = center - p.pull_off_center if i == 0 else center + p.pull_off_center
        xs = {round(h.origin[0], 4) for h in _door_pull_holes(model, door)
              if h.origin[2] < layout.door_top_z}
        assert xs == {round(expect, 4)}, door.name
    assert "off the case centerline" in [x for x in parts if x.name == "Door L"][0].notes
    drawer_xs = sorted({round(h.origin[0], 4) for h in model.holes
                        if h.normal == (0.0, -1.0, 0.0) and h.origin[2] > layout.door_top_z})
    assert drawer_xs == [round(center - p.pull_off_center, 4), round(center + p.pull_off_center, 4)]

    drawers = _build("base_3drawers", width=18, handle_side="left")[3]
    center = 9.0
    xs = sorted({round(h.origin[0], 4) for h in drawers.holes if h.normal == (0.0, -1.0, 0.0)})
    assert xs == [round(center - p.pull_off_center, 4), round(center + p.pull_off_center, 4)]
    bar = [b for b in drawers.boxes if b.name.startswith("Wire pull, drawer")][0]
    assert abs((bar.pos[0] + bar.size[0] / 2) - center) < 1e-6


def test_form_exposes_the_handle_side_like_an_upper(tmp_path: Path):
    fresh = _run_page(group_view({"bw1": "18", "bs1": "base1", "walls": "left"}))
    assert 'name="bh1" value="right"' in fresh
    assert 'aria-label="Base 1 handle side"' in fresh
    assert 'class="handle-pick" data-style-for="bs1">' in fresh
    assert 'data-b="1" data-handle="right"' in fresh
    assert 'data-v="base1"' in fresh

    left = _run_page(group_view({
        "bw1": "21", "bs1": "base1", "bh1": "left",
        "uw1": "15", "us1": "upper1", "uh1": "right", "walls": "left",
    }))
    assert 'name="bh1" value="left"' in left
    assert 'name="uh1" value="right"' in left
    assert 'data-b="1" data-handle="left"' in left
    assert '.card[data-handle="left"] .segbtn[data-v="base1"] .ico' in left

    # a pair, a drawer stack and a sink do not offer a handle side
    for style in ("base", "3drawer", "sink"):
        page = _run_page(group_view({"bw1": "30", "bs1": style, "walls": "left"}))
        assert 'class="handle-pick" data-style-for="bs1" hidden>' in page, style

    # wider than 24" an upper hides the toggle; a base keeps it
    wide = _run_page(group_view({
        "bw1": "36", "bs1": "base1", "bh1": "left",
        "uw1": "30", "us1": "upper1", "uh1": "left", "walls": "left",
    }))
    assert 'class="handle-pick" data-style-for="bs1">' in wide
    assert 'class="handle-pick" data-style-for="us1" hidden>' in wide

    wire = _wire_data()["styles"]["base1"]
    assert wire["ndoors"] == 1 and wire["doors"] and wire["toe"] > 0
    assert not wire["false_front"] and not wire.get("by_drawer")
    page = _run_page(group_view(None))
    assert "else if (n === 1)" in page
    assert "WIRE.upper_pull.inset" in page and "WIRE.base_pull.from_top" in page
    assert "WIRE.base_pull.off_center" in page

    cabs = parse_group({"bw1": "18", "bs1": "base1", "walls": "left"})
    assert cabs[0]["style"] == "base1" and cabs[0]["handle"] == "right"
    cabs = parse_group({"bw1": "18", "bs1": "base1", "bh1": "left", "walls": "left"})
    assert cabs[0]["handle"] == "left"
    try:
        parse_group({"bw1": "18", "bs1": "base1", "bh1": "middle", "walls": "left"})
    except KitchenError as exc:
        assert "left or the right" in str(exc)
    else:
        raise AssertionError("a handle that is not left or right should be refused")

    sheet = tmp_path / "base.csv"
    sheet.write_text(group_sheet(cabs, group_settings(
        {"bw1": "18", "bs1": "base1", "bh1": "left", "walls": "left"})))
    settings, rows = load_kitchen(sheet)
    placed = place_kitchen(rows, settings, sheet.name)
    assert placed[0].params.style == "base_1door"
    assert placed[0].params.handle_side == "left"
    assert placed[0].params.doors == 1

    # a blank handle column keeps the same default as an upper
    bare = tmp_path / "bare.csv"
    bare.write_text("name,style,width,run\nDoor,base_1door,18,base\n", encoding="utf-8")
    settings, rows = load_kitchen(bare)
    placed = place_kitchen(rows, settings, bare.name)
    assert placed[0].params.handle_side == "right" and placed[0].params.doors == 1


def test_client_sheet_shows_the_handle_side(tmp_path: Path):
    form = {"bw1": "18", "bs1": "base1", "bh1": "left", "walls": "left"}
    sheet = tmp_path / "base.csv"
    sheet.write_text(group_sheet(parse_group(form), group_settings(form)))
    settings, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, settings, sheet.name)
    apply_discovered_rules(cabs, settings)
    job = job_from(cabs, settings, "One door base")
    styles = [s for s, _ in style_groups(job)]
    assert styles == ["base_1door"]
    pages = render_pages(job, date="November 5, 2026")
    text = {s: pages[i].to_string() for i, s in enumerate(["overview", "counter"] + styles)}
    one = text["base_1door"]
    assert "BASE, 1 DOOR" in one
    assert "handle on the left" in one
    assert "stroke-dasharray" in one
