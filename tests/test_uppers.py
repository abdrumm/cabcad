"""Upper styles: 1 door (handle side), open shelves, microwave shelf with 2 doors above."""
from pathlib import Path

from cabgen.client_sheet import job_from, render_pages, style_groups
from cabgen.kitchen import (
    KitchenError, apply_discovered_rules, group_settings, group_sheet, load_kitchen,
    parse_group, place_kitchen, scene_of, write_kitchen,
)
from cabgen.model3d import build_model
from cabgen.nest_project import cabinet_codes, part_labels
from cabgen.params import MW_OPENING_H, Params
from cabgen.parts import build_parts, open_shelf_z
from cabgen.web import _run_page, group_view

FORM = {
    "uw1": "15", "us1": "upper1", "uh1": "left",
    "uw2": "30", "us2": "open",
    "uw3": "30", "us3": "microwave",
    "uw4": "27", "us4": "upper",
    "uw5": "12", "us5": "upper1", "uh5": "right",
    "bw1": "30", "bs1": "3drawer", "walls": "left",
}


def _build(style, **kw):
    p = Params(style=style, **kw)
    parts, layout = build_parts(p)
    return p, parts, layout, build_model(p, layout)


def test_one_door_handle_side_moves_the_pull_and_the_hinges():
    for handle in ("right", "left"):
        p, parts, layout, model = _build("upper_1door", width=18.0, handle_side=handle)
        assert p.doors == 1 and p.hinge_side == ("left" if handle == "right" else "right")
        door = [x for x in parts if x.name == "Door"]
        assert len(door) == 1 and abs(door[0].width - 17.5) < 1e-6
        assert f"Handle {handle.upper()}" in door[0].notes
        box = [b for b in model.boxes if b.name.startswith("Door, handle")][0]
        assert box.name == f"Door, handle {handle[0].upper()}"
        pulls = [h for h in model.holes if abs(h.diameter - 0.1875) < 1e-6]
        cups = [h for h in model.holes if h.diameter > 1.0]
        assert len(pulls) == 2 and len(cups) == 2
        if handle == "right":
            assert all(h.origin[0] > 9 for h in pulls) and all(h.origin[0] < 9 for h in cups)
        else:
            assert all(h.origin[0] < 9 for h in pulls) and all(h.origin[0] > 9 for h in cups)


def test_open_upper_has_no_doors_and_even_shelves():
    p, parts, layout, model = _build("upper_open")
    assert p.doors == 0 and not layout.door_heights and p.finished_interior
    shelf = [x for x in parts if x.name == "Open shelf"][0]
    assert shelf.qty == 2
    z = open_shelf_z(p)
    gaps = [z[0] - 0.75, z[1] - (z[0] + 0.75), (30 - 0.75) - (z[1] + 0.75)]
    assert max(gaps) - min(gaps) < 1e-3
    assert [b.name for b in model.boxes if b.name.startswith("Open shelf")] == ["Open shelf 1", "Open shelf 2"]
    assert len(model.holes) == 2 * 2 * 6          # 2 gables x 2 columns x 6 rows
    assert not any(b.name.startswith("Door") for b in model.boxes)


def test_microwave_upper_opening_divider_and_short_doors():
    p, parts, layout, model = _build("upper_microwave")
    assert (p.width, p.height, p.depth) == (30.0, 30.0, 12.0)
    assert p.mw_opening_h == MW_OPENING_H
    div = [b for b in model.boxes if b.name == "Microwave divider"][0]
    assert abs(div.pos[2] - (0.75 + MW_OPENING_H)) < 1e-6
    assert len(layout.door_heights) == 2
    assert abs(layout.door_bottom_z - (div.pos[2] + 0.25)) < 1e-6
    assert abs(layout.door_heights[0] - (29.75 - div.pos[2] - 0.25)) < 1e-6
    assert any(x.name == "Microwave divider" for x in parts)


def test_form_carries_the_new_styles_and_the_handle_through_the_csv(tmp_path: Path):
    cabs = parse_group(FORM)
    uppers = [c for c in cabs if c["run"] == "upper"]
    assert [c["style"] for c in uppers] == ["upper1", "open", "microwave", "upper", "upper1"]
    assert [c["handle"] for c in uppers] == ["left", "", "", "", "right"]
    sheet = tmp_path / "g.csv"
    sheet.write_text(group_sheet(cabs, group_settings(FORM)))
    settings, rows = load_kitchen(sheet)
    placed = place_kitchen(rows, settings, sheet.name)
    styles = {c.name: (c.params.style, c.params.handle_side) for c in placed}
    assert styles["Upper 1"] == ("upper_1door", "left")
    assert styles["Upper 5"] == ("upper_1door", "right")
    assert styles["Upper 3"][0] == "upper_microwave"
    # a 1-door may be 9" wide, a 2-door may not
    parse_group({"uw1": "9", "us1": "upper1", "walls": "left"})
    try:
        parse_group({"uw1": "9", "us1": "upper", "walls": "left"})
    except KitchenError as exc:
        assert "under 12" in str(exc)
    else:
        raise AssertionError("a 9 inch 2-door upper should be refused")
    try:
        parse_group({"uw1": "15", "us1": "upper1", "uh1": "up", "walls": "left"})
    except KitchenError:
        pass
    else:
        raise AssertionError("a handle that is not left or right should be refused")


def test_labels_nest_and_cut_list(tmp_path: Path):
    sheet = tmp_path / "g.csv"
    sheet.write_text(group_sheet(parse_group(FORM), group_settings(FORM)))
    settings, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, settings, sheet.name)
    codes = cabinet_codes(cabs)
    labels = {}
    for c in cabs:
        for part, labs in part_labels(codes[c.name], build_parts(c.params)[0]):
            labels.setdefault(c.name, []).extend(labs)
    assert "U1-D" in labels["Upper 1"]
    assert "U2-OS1" in labels["Upper 2"] and "U2-OS2" in labels["Upper 2"]
    assert "U3-MD" in labels["Upper 3"]
    boxes, holes, parts = scene_of(cabs, settings)
    names = [b.name for b in boxes]
    assert any(n.startswith("U1-D Upper 1 / Door, handle L") for n in names)
    assert any(n.startswith("U3-MD Upper 3 / Microwave divider") for n in names)
    ok, msg = write_kitchen(sheet, tmp_path, "Uppers", show=False)
    assert ok, msg
    cut = (tmp_path / "uppers-cutlist.csv").read_text()
    assert "Open shelf" in cut and "Microwave divider" in cut and "Upper 1 / Door" in cut
    nest = (tmp_path / "uppers-nest-cutlist.csv").read_text()
    for lab in ("U1-D", "U2-OS1", "U3-MD"):
        assert lab in nest, lab


def test_client_sheet_has_a_detail_page_for_each_new_style(tmp_path: Path):
    sheet = tmp_path / "g.csv"
    sheet.write_text(group_sheet(parse_group(FORM), group_settings(FORM)))
    settings, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, settings, sheet.name)
    apply_discovered_rules(cabs, settings)
    job = job_from(cabs, settings, "Uppers")
    styles = [s for s, _ in style_groups(job)]
    for s in ("upper_1door", "upper_open", "upper_microwave", "upper_2doors"):
        assert s in styles
    pages = render_pages(job, date="October 24, 2026")
    text = {s: pages[i].to_string() for i, s in enumerate(["overview", "counter"] + styles)}
    one = text["upper_1door"]
    assert "WALL UPPER, 1 DOOR" in one and "handle on the left" in one
    assert ">left<" in one and ">right<" in one and "stroke-dasharray" in one
    assert "OPEN SHELVES" in text["upper_open"] and "2 adjustable shelves" in text["upper_open"]
    mw = text["upper_microwave"]
    assert "MICROWAVE" in mw and "opening 17 1/4" in mw
    assert "stroke-dasharray" in text["overview"]       # swing marks on the elevation


def test_form_tile_shows_the_handle_toggle_and_style_icons():
    page = _run_page(group_view(FORM))
    assert 'id="uh1"' in page and 'name="uh1" value="left"' in page
    for short in ("1 door", "Open", "Microwave", "2 doors"):
        assert f"<span>{short}</span>" in page
    assert 'class="seg many"' in page
    assert 'min="9"' in page


def test_upper_pulls_are_stock_wire_pulls_measured_to_hole_centres():
    from cabgen.params import (UPPER_PULL_CC, UPPER_PULL_EDGE_INSET, UPPER_PULL_FROM_BOTTOM,
                               UPPER_PULL_HOLE_DIA)
    cases = [("upper_2doors", {}), ("upper_microwave", {}),
             ("upper_1door", {"handle_side": "left"}), ("upper_1door", {"handle_side": "right"})]
    for style, kw in cases:
        p, parts, layout, model = _build(style, **kw)
        doors = sorted((b for b in model.boxes if b.name.startswith("Door")), key=lambda b: b.pos[0])
        holes = [h for h in model.holes if h.normal == (0.0, -1.0, 0.0)]
        assert len(holes) == 2 * len(doors), style
        assert all(abs(h.diameter - UPPER_PULL_HOLE_DIA) < 1e-9 and h.depth == p.carcass_thk
                   for h in holes)                                # through the door
        for i, d in enumerate(doors):
            x0, x1, bot = d.pos[0], d.pos[0] + d.size[0], d.pos[2]
            mine = sorted((h for h in holes if x0 < h.origin[0] < x1), key=lambda h: h.origin[2])
            assert len(mine) == 2, (style, d.name)
            zs = [round(h.origin[2] - bot, 4) for h in mine]
            assert zs == [UPPER_PULL_FROM_BOTTOM, UPPER_PULL_FROM_BOTTOM + UPPER_PULL_CC], (style, zs)
            if p.doors == 2:
                handle_right = i == 0                             # pairs open at the meeting edges
            else:
                handle_right = p.handle_side == "right"
            edge = x1 if handle_right else x0
            assert abs(abs(edge - mine[0].origin[0]) - UPPER_PULL_EDGE_INSET) < 1e-9, (style, d.name)
        assert sum(1 for b in model.boxes if b.name.startswith("Wire pull")) == 3 * len(doors)


def test_base_door_pulls_did_not_change():
    p, parts, layout, model = _build("base_1drawer_2doors")
    d_top = layout.door_top_z
    door_holes = sorted({round(h.origin[2], 4) for h in model.holes
                         if h.normal == (0.0, -1.0, 0.0) and h.origin[2] < d_top})
    assert door_holes == [round(d_top - p.pull_from_top - p.pull_span, 4), round(d_top - p.pull_from_top, 4)]
    assert all(abs(h.diameter - p.pull_hole_dia) < 1e-9 for h in model.holes if h.normal == (0.0, -1.0, 0.0))


def test_summary_tables_list_uppers_before_bases(tmp_path: Path):
    from cabgen.kitchen import layout_text
    sheet = tmp_path / "g.csv"
    sheet.write_text(group_sheet(parse_group(FORM), group_settings(FORM)))
    settings, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, settings, sheet.name)
    table = [ln for ln in layout_text(cabs, settings).splitlines() if ln.startswith("| ") and "Name" not in ln]
    runs = [ln.split("|")[2].strip() for ln in table]
    assert runs == ["Uppers"] * 5 + ["Base cabinets"]
    apply_discovered_rules(cabs, settings)
    page = render_pages(job_from(cabs, settings, "Uppers"), date="October 24, 2026")[0].to_string()
    assert page.index(">U1<") < page.index(">B1<", page.index("CABINETS"))


def test_one_door_icon_follows_the_handle_toggle():
    page = _run_page(group_view(FORM))
    assert 'data-u="1" data-handle="left"' in page
    assert 'data-u="5" data-handle="right"' in page
    assert '.card[data-handle="left"] .segbtn[data-v="upper1"] .ico' in page
    assert "card.dataset.handle" in page
