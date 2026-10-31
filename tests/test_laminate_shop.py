"""Laminate dropdown, edge banding, finished ends, and the laminate cut list."""
from pathlib import Path

from cabgen.cutlist import to_csv
from cabgen.draw import shop_drawing
from cabgen.edgeband import EDGE_TABLE, band_inches, rule_for
from cabgen.finishes import (
    LIBRARY_PATH, RAW_CASE_HEX, drawing_label, dropdown_groups, library, lookup,
    option_value, posted_finish, resolved_finished_ends,
)
from cabgen.kitchen import (
    apply_discovered_rules, group_settings, group_sheet, load_kitchen, parse_group,
    place_kitchen,
)
from cabgen.laminate_cut import (
    BALANCE_FRONTS, OVERAGE, build_takeoff, sheet_count, to_laminate_csv,
)
from cabgen.nest_project import nest_project, sheet_page
from cabgen.params import Params
from cabgen.parts import build_parts
from cabgen.web import _form_html, _run_page, defaults, group_view

ROOT = Path(__file__).resolve().parents[1]


def _part(params, start):
    parts, _layout = build_parts(params)
    hit = next(p for p in parts if p.name.lower().startswith(start))
    return hit


def test_library_merges_archie_and_keeps_the_old_list():
    rows = library()
    numbers = [r.number for r in rows]
    assert numbers[:4] == ["TBD-WHITE", "TBD-BLACK", "TBD-WOOD", "TBD-GREY"]
    assert numbers[4:7] == ["949-58", "909-58", "8844-WR"]
    assert lookup("5786-NG").name == "Ashwood Oak"
    assert lookup("white").name == "White melamine"
    assert lookup("SparkleLam Light Aqua").name == "Light Aqua"
    assert lookup("949-58").display == "Formica 949-58 White (matte)"
    assert lookup("909-58").display == "Formica 909-58 Black (matte)"
    assert lookup("8844-WR").display == "Formica 8844-WR Aged Ash (woodbrook)"
    assert lookup("8844-WR").staple and lookup("8844-WR").group == "woodgrain"
    assert lookup("SB006").display == "Pionite SB006 Indigo Blue (suede)"
    assert lookup("912").name == "Storm" and lookup("912-58").number == "912-58"
    assert lookup("7924K-07").name == "Biltmore Cherry"
    for fin in rows:
        assert fin.approximate and fin.texture == ""
        assert fin.hex.startswith("#") and len(fin.hex) == 7
        assert fin.group in ("white", "black", "grey", "woodgrain", "pattern", "color")
    text = LIBRARY_PATH.read_text(encoding="utf-8")
    assert "texture" in text.splitlines()[0]
    assert "not a manufacturer swatch" in text
    assert lookup("TBD-WHITE").tbd and lookup("White (TBD)").number == "TBD-WHITE"
    assert drawing_label("TBD-WHITE") == "color TBD"
    assert drawing_label("TBD-WOOD") == "color TBD"
    assert lookup("NO-SUCH-99").fallback
    groups = [title for title, _items in dropdown_groups()]
    assert groups[:2] == ["Not picked yet", "Shop staples"]
    assert "White" in groups and "Woodgrain" in groups


def test_forms_offer_the_dropdown_and_a_custom_number():
    page = _run_page(group_view(None))
    assert 'name="doors"' in page and 'name="case"' in page
    assert 'name="interior"' in page and 'name="top"' in page
    assert "Formica 949-58 White (matte)" in page
    assert "White (TBD)" in page and "Woodgrain (TBD)" in page
    assert 'name="doors_custom"' in page and "Type a number" in page
    assert 'name="bfe1"' in page and "Finished end" in page
    one = _form_html(defaults())
    assert "Formica 909-58 Black (matte)" in one
    assert 'name="finished_ends"' in one
    assert posted_finish({"doors": "949-58", "doors_custom": "NOPE"}, "doors") == "949-58"
    assert posted_finish({"doors": "__custom__", "doors_custom": "NO-SUCH-99"}, "doors") == "NO-SUCH-99"
    form = {"walls": "left", "bw1": "30", "bs1": "base", "doors": "949-58", "case": "TBD-WHITE"}
    settings = group_settings(form)
    assert settings["finish_doors"] == "949-58"
    assert settings["finish_case"] == "TBD-WHITE"
    text = group_sheet(parse_group(form), settings)
    assert "# doors=949-58" in text and "# case=TBD-WHITE" in text
    assert option_value(lookup("949-58")) == "949-58"


def test_edge_banding_codes_follow_the_one_table():
    assert EDGE_TABLE[0].match == "gable"
    base = Params(style="base_1drawer_2doors", width=30)
    gable = _part(base, "gable")
    assert gable.eb_mask == "0010"
    assert gable.eb == "W1 N1"
    assert gable.notch == (base.toe_kick_recess, base.toe_kick_h)
    assert "notch" in gable.banding.lower()
    assert "not a solid rectangle" in gable.banding.lower()
    door = _part(base, "door")
    assert door.eb == "L1 L2 W1 W2" and door.eb_mask == "1111"
    assert _part(base, "back panel").eb == ""
    assert _part(base, "bottom plate").eb == "W1"
    assert _part(base, "drawer front").eb == "L1 L2 W1 W2"
    upper = Params(style="upper_2doors", width=30)
    ug = _part(upper, "gable")
    assert ug.notch is None and ug.eb == "L1 L2 W1"
    assert rule_for("Shelf", "base").mask == "0010"
    # The front band is the height above the notch, plus the top of the notch.
    per_side = (gable.width - base.toe_kick_h) + base.toe_kick_recess
    assert abs(band_inches(gable) - per_side * gable.qty) < 1e-6
    csv = to_csv([gable, door])
    assert csv.splitlines()[0].split(",")[6] == "EB"
    assert "W1 N1" in csv and "L1 L2 W1 W2" in csv
    drawing, _left = shop_drawing(base, build_parts(base)[0], build_parts(base)[1])
    svg = drawing.to_string()
    assert "W1 N1" in svg or "N1" in svg
    assert 'stroke="#222"' in svg or "stroke-linecap" in svg


def test_nest_draws_the_band_and_the_notch():
    from cabgen.kitchen import group_settings as gs
    form = {"walls": "left", "bw1": "30", "bs1": "base", "case": "909-58"}
    sheet_text = group_sheet(parse_group(form), gs(form))
    tmp = Path("/tmp/lam-nest-test.csv")
    tmp.write_text(sheet_text, encoding="utf-8")
    settings, rows = load_kitchen(tmp)
    cabs = place_kitchen(rows, settings, tmp.name)
    apply_discovered_rules(cabs, settings)
    groups = nest_project(cabs)
    page = None
    for group in groups.values():
        for sh in group.sheets:
            if any(p.piece.notch for p in sh.placed):
                page = sheet_page(sh, group, "Test", 2, 3)
                break
    assert page is not None
    text = page.to_string()
    assert "PVC edge band" in text
    assert "toe-kick notch" in text
    assert "stroke-linecap" in text
    assert "stroke-dasharray" in text


def test_finished_ends_follow_the_walls_unless_the_row_says():
    form = {"walls": "left", "bw1": "30", "bs1": "base", "bw2": "18", "bs2": "3drawer",
            "uw1": "30", "us1": "upper"}
    settings = group_settings(form)
    text = group_sheet(parse_group(form), settings)
    _settings, rows = load_kitchen_text(text)
    cabs = place_kitchen(rows, _settings, "job")
    apply_discovered_rules(cabs, _settings)
    bases = [c for c in cabs if c.run == "base"]
    uppers = [c for c in cabs if c.run == "upper"]
    assert resolved_finished_ends(bases[0].params) == "none"
    assert resolved_finished_ends(bases[1].params) == "right"
    assert resolved_finished_ends(uppers[0].params) == "right"
    # an explicit none on the open end wins
    form["bfe2"] = "none"
    text = group_sheet(parse_group(form), group_settings(form))
    base_rows = [ln for ln in text.splitlines() if ln.startswith("Base")]
    assert any(ln.endswith(",none") for ln in base_rows)
    _settings, rows = load_kitchen_text(text)
    cabs = place_kitchen(rows, _settings, "job")
    apply_discovered_rules(cabs, _settings)
    last = [c for c in cabs if c.run == "base"][-1]
    assert last.params.finished_ends == "none"
    assert resolved_finished_ends(last.params) == "none"
    parts, layout = build_parts(last.params)
    from cabgen.model3d import build_model
    from cabgen.finishes import paint_boxes
    boxes = build_model(last.params, layout).boxes
    paint_boxes(boxes, last.params)
    left = next(b for b in boxes if b.name == "Gable L")
    right = next(b for b in boxes if b.name == "Gable R")
    assert left.color == RAW_CASE_HEX and right.color == RAW_CASE_HEX


def test_finished_end_draws_fe_and_uses_the_case_laminate():
    from cabgen.client_sheet import job_from, render
    from cabgen.finishes import lookup
    form = {"walls": "0", "bw1": "30", "bs1": "base", "case": "949-58", "doors": "TBD-WOOD"}
    settings = group_settings(form)
    text = group_sheet(parse_group(form), settings)
    tmp = Path("/tmp/lam-fe.csv")
    tmp.write_text(text, encoding="utf-8")
    loaded, rows = load_kitchen(tmp)
    cabs = place_kitchen(rows, loaded, tmp.name)
    apply_discovered_rules(cabs, loaded)
    cab = cabs[0]
    assert resolved_finished_ends(cab.params) == "both"
    parts, layout = build_parts(cab.params)
    from cabgen.model3d import build_model
    from cabgen.finishes import paint_boxes
    boxes = build_model(cab.params, layout).boxes
    paint_boxes(boxes, cab.params)
    white = lookup("949-58").hex
    assert next(b for b in boxes if b.name == "Gable L").color == white
    assert next(b for b in boxes if b.name == "Gable R").color == white
    job = job_from(cabs, loaded, "FE kitchen")
    page = render(job, date="October 31, 2026").to_string()
    assert ">FE<" in page
    assert "color TBD" in page
    assert "finished end" in page.lower()


def test_laminate_cut_list_overage_faces_sheets_and_banding():
    form = {
        "walls": "left", "counter": "laminate", "bw1": "30", "bs1": "base",
        "doors": "8844-WR", "case": "949-58", "top": "909-58",
    }
    settings = group_settings(form)
    text = group_sheet(parse_group(form), settings)
    tmp = Path("/tmp/lam-cut.csv")
    tmp.write_text(text, encoding="utf-8")
    loaded, rows = load_kitchen(tmp)
    cabs = place_kitchen(rows, loaded, tmp.name)
    apply_discovered_rules(cabs, loaded)
    takeoff = build_takeoff(cabs, loaded)
    doors = [r for r in takeoff.rows if r.part.startswith("Door")]
    assert BALANCE_FRONTS
    assert len(doors) == 4  # two doors, both faces
    assert all(r.spec == "8844-WR" for r in doors)
    assert all(abs(r.cut_w - (r.finished_w + 2 * OVERAGE)) < 1e-9 for r in doors)
    assert all(r.grain == "along the length" for r in doors)
    skins = [r for r in takeoff.rows if r.part.startswith("Finished end")]
    assert len(skins) == 1 and skins[0].qty == 1 and skins[0].spec == "949-58"
    assert "notch" in skins[0].note.lower() and "not a solid rectangle" in skins[0].note.lower()
    assert skins[0].grain == ""  # 949-58 is a solid white, so the skin may turn
    tops = [r for r in takeoff.rows if r.cabinet == "Countertop"]
    assert any("Front edge" in r.part for r in tops)
    assert any(r.part == "Top" for r in tops)
    assert any("Backsplash" in r.part for r in tops)
    assert all(r.spec == "909-58" for r in tops)
    # edge banding is footage, not a sheet row
    assert not any("edge band" in r.part.lower() for r in takeoff.rows)
    n4, n5 = takeoff.sheets("8844-WR")
    assert n4 >= 1 and n5 >= 1 and n5 <= n4
    csv = to_laminate_csv(takeoff)
    assert "CUT WIDTH" in csv and "EDGE BAND LF +10%" in csv
    assert "8844-WR" in csv and "color TBD" not in csv
    band = next(b for b in takeoff.bands if b.spec == "949-58")
    assert band.feet_with_waste == band.feet * 1.10
    # a piece that only fits a 5x12 still counts as one 4x8 sheet (oversize)
    assert sheet_count([(50, 100, "")], 48, 96) == 1
    assert sheet_count([(50, 100, "")], 60, 144) == 1
    assert sheet_count([(40, 40, ""), (40, 40, "")], 48, 96) == 1
    pages = __import__("cabgen.laminate_cut", fromlist=["laminate_pages"]).laminate_pages(takeoff, "Job")
    drawn = "\n".join(p.to_string() for p in pages)
    assert "LAMINATE CUT LIST" in drawn
    assert "1/2" in drawn
    # TBD placeholder is labeled color TBD and still gets a skin
    cab = cabs[0]
    cab.params.finish_doors = "TBD-WHITE"
    cab.params.finish_case = ""
    bare = build_takeoff([cab], {"counter": "none", "base_walls": "left"})
    assert any(r.display == "color TBD" and r.spec == "TBD-WHITE" for r in bare.rows)
    assert not any(r.part.startswith("Finished end") for r in bare.rows)


def load_kitchen_text(text: str):
    path = Path("/tmp/lam-sheet.csv")
    path.write_text(text, encoding="utf-8")
    return load_kitchen(path)
