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


def test_single_door_upper_stops_at_24_inches(tmp_path: Path):
    """Brook: a 1-door wall upper is 24\" at most. Wider is a pair, and an explicit
    single-door request is converted and called out. Bases are not part of this rule."""
    from cabgen.cli import generate
    from cabgen.client_sheet import _features, job_from, render_pages
    from cabgen.cutlist import to_csv
    from cabgen.draw import shop_drawing
    from cabgen.kitchen import layout_text
    from cabgen.nest_project import part_labels
    from cabgen.params import UPPER_1DOOR_MAX_WIDTH, door_rule_warnings
    from cabgen.web import params_from_form

    assert UPPER_1DOOR_MAX_WIDTH == 24

    legal = Params(style="upper_1door", name="Legal", width=24, handle_side="left")
    assert legal.doors == 1 and legal.style == "upper_1door"
    assert door_rule_warnings(legal) == []
    parts, layout, model = _build("upper_1door", name="Legal", width=24, handle_side="left")[1:]
    assert [x.name for x in parts if x.name.startswith("Door")] == ["Door"]
    assert [b.name for b in model.boxes if b.name.startswith("Door")] == ["Door, handle L"]
    assert not any("single-door upper" in a for a in layout.assumptions)

    # 9" is still a legal single door (the old minimum). A 2-door style stays a pair
    # even when it is narrow: this rule does not take doors away.
    assert Params(style="upper_1door", width=9).doors == 1
    assert Params(style="upper_2doors", width=18).doors == 2
    assert Params(style="upper_2doors", name="Already a pair", width=36).doors == 2
    assert door_rule_warnings(Params(style="upper_2doors", width=36)) == []

    for width in (24.5, 27, 30, 36):
        p, parts, layout, model = _build("upper_1door", name=f"Upper {width:g}", width=width,
                                         handle_side="left")
        assert p.doors == 2 and p.style == "upper_2doors", width
        assert p.door_count_overridden
        warning = door_rule_warnings(p)
        assert len(warning) == 1, width
        assert warning[0].startswith(f"Warning: Upper {width:g} is ")
        assert "single-door upper" in warning[0] and '24"' in warning[0]
        assert "Asked for as one door; built as two doors." in warning[0]
        if width == 24.5:
            assert '24 1/2"' in warning[0]
        doors = [x for x in parts if x.name.startswith("Door")]
        assert [d.name for d in doors] == ["Door L", "Door R"], width
        assert abs(doors[0].width - doors[1].width) < 1e-6
        assert doors[0].width < width / 2
        assert layout.door_heights and len(layout.door_heights) == 2
        assert warning[0] in layout.assumptions
        boxes = [b.name for b in model.boxes if b.name.startswith("Door")]
        assert boxes == ["Door L", "Door R"], width
        assert not any(h.diameter > 1 for h in model.holes), width   # hinge cups are the 1-door
        labels = [lab for _part, labs in part_labels("U9", parts) for lab in labs]
        assert "U9-DL" in labels and "U9-DR" in labels and "U9-D" not in labels

    # The same conversion when the single-cabinet form posts the 1-door style.
    posted = params_from_form({"style": "upper_1door", "width": "30", "name": "Spec"})
    assert posted.doors == 2 and posted.style == "upper_2doors"
    assert "Spec" in door_rule_warnings(posted)[0]
    base_posted = params_from_form({"style": "base_1drawer_2doors", "width": "36", "name": "Base spec"})
    assert base_posted.doors == 2 and base_posted.style == "base_1drawer_2doors"
    assert door_rule_warnings(base_posted) == []

    # A job that asks for one door on a 30" upper, plus the other widths and the bases.
    sheet = """\
name,style,width,run,handle
Wide,upper1,30,upper,left
Legal,upper1,24,upper,right
Half,1door,24.5,upper,left
Pair,upper,27,upper,
Tall,upper,36,upper,
Open,open,36,upper,
Micro,microwave,30,upper,
Base wide,base,36,base,
Drawers,3drawer,36,base,
Sink,sink,36,base,
"""
    from io import StringIO
    import csv
    rows = list(csv.DictReader(StringIO(sheet)))
    settings = {"upper_bottom": 54.0, "counter": "none"}
    cabs = place_kitchen(rows, settings, "wide-upper.csv")
    by = {c.name: c for c in cabs}
    assert by["Legal"].params.doors == 1 and by["Legal"].params.style == "upper_1door"
    assert by["Legal"].params.handle_side == "right"
    for name in ("Wide", "Half", "Pair", "Tall"):
        assert by[name].params.doors == 2, name
    assert by["Wide"].params.style == "upper_2doors"
    assert by["Half"].params.style == "upper_2doors"
    assert by["Open"].params.doors == 0 and by["Open"].params.style == "upper_open"
    assert by["Micro"].params.doors == 2 and by["Micro"].params.style == "upper_microwave"
    assert not by["Micro"].params.door_count_overridden
    assert not by["Pair"].params.door_count_overridden
    for name, doors in (("Base wide", 2), ("Drawers", 0), ("Sink", 2)):
        cab = by[name]
        assert cab.params.doors == doors and not cab.params.door_count_overridden, name
        assert not str(cab.params.style).startswith("upper")
    text = layout_text(cabs, settings)
    assert "Shop-standard warnings:" in text
    assert "Warning: Wide is 30\" wide." in text
    assert "Warning: Half is 24 1/2\" wide." in text
    assert "Base wide" not in text.split("Shop-standard warnings:")[1].split("|")[0]
    assert "Legal" not in text.split("Shop-standard warnings:")[1].split("|")[0]

    wide = by["Wide"].params
    assert any("built as two doors" in line for line in _features(wide))
    assert any(line == "2 doors" for line in _features(wide))
    assert not any(line.startswith("1 door") for line in _features(wide))
    assert any(line.startswith("1 door, handle on the right") for line in _features(by["Legal"].params))
    assert _features(by["Base wide"].params)  # still describes a base, not the upper rule
    assert not any("single-door upper" in line for line in _features(by["Base wide"].params))

    job = job_from(cabs, settings, "Wide upper")
    pages = "\n".join(page.to_string() for page in render_pages(job, date="October 30, 2026"))
    assert "Asked for as one door; built as two doors." in pages
    assert "Warning: Wide is" in pages

    _p, parts, layout, model = _build("upper_1door", name="Wide", width=30)
    drawing, _leftover = shop_drawing(_p, parts, layout)
    drawn = drawing.to_string()
    assert "Warning:" in drawn and "single-door" in drawn
    cut = to_csv(parts)
    assert "Door L" in cut and "Door R" in cut

    # Generator output carries the same warning the shop drawing does.
    # (generate writes the drawing files; the warning is on the result, not only the SVG.)
    result = generate(Params(style="upper_1door", name="Wide", width=30), tmp_path)
    assert any("Warning: Wide is 30\" wide." in w for w in result["warnings"])
    assert result["layout"].params.doors == 2
    base_result = generate(Params(style="base_1drawer_2doors", name="Base wide", width=36), tmp_path)
    assert base_result["layout"].params.doors == 2
    assert not any("single-door upper" in w for w in base_result["warnings"])


def test_base_doors_are_unchanged_at_widths_over_24():
    for width in (24, 30, 36):
        p, parts, layout, model = _build("base_1drawer_2doors", width=width)
        assert p.doors == 2 and p.style == "base_1drawer_2doors"
        assert not p.door_count_overridden
        assert [x.name for x in parts if x.name.startswith("Door")] == ["Door L", "Door R"]
        d_top = layout.door_top_z
        door_holes = sorted({round(h.origin[2], 4) for h in model.holes
                             if h.normal == (0.0, -1.0, 0.0) and h.origin[2] < d_top})
        assert door_holes == [round(d_top - p.pull_from_top - p.pull_span, 4),
                              round(d_top - p.pull_from_top, 4)]
    p, parts, layout, model = _build("base_3drawers", width=36)
    assert p.doors == 0 and not layout.door_heights
    p, parts, layout, model = _build("base_sink", width=36)
    assert p.doors == 2 and [x.name for x in parts if x.name.startswith("Door")] == ["Door L", "Door R"]
    assert not p.door_count_overridden


def test_one_door_icon_follows_the_handle_toggle():
    page = _run_page(group_view(FORM))
    assert 'data-u="1" data-handle="left"' in page
    assert 'data-u="5" data-handle="right"' in page
    assert '.card[data-handle="left"] .segbtn[data-v="upper1"] .ico' in page
    assert "card.dataset.handle" in page
