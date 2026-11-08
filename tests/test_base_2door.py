"""The 2-door base (Brook, 2026-11-02): a pair of doors, no drawer, a shelf,
on the same 33-1/2" finished height rule as the other bases.
"""
from pathlib import Path

from cabgen.client_sheet import job_from, render_pages, style_groups
from cabgen.kitchen import (
    BASE_CHOICES, apply_discovered_rules, group_settings, group_sheet, load_kitchen,
    parse_group, place_kitchen,
)
from cabgen.model3d import build_model
from cabgen.params import DEFAULT_WIDTHS, STYLE_PRESETS, Params, base_case_height
from cabgen.parts import build_parts
from cabgen.web import _wire_data


def _run(form: dict, tmp_path: Path):
    cabinets = parse_group(form)
    settings = group_settings(form)
    sheet = tmp_path / "group.csv"
    sheet.write_text(group_sheet(cabinets, settings), encoding="utf-8")
    loaded, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, loaded, sheet.name)
    apply_discovered_rules(cabs, loaded)
    return cabs, loaded


def test_two_door_base_is_a_stock_style_with_a_shelf():
    assert "base_2doors" in STYLE_PRESETS and ("base2", "2 doors") in BASE_CHOICES
    assert DEFAULT_WIDTHS["base2"] == 30
    p = Params(style="base_2doors")
    assert p.doors == 2 and p.drawers == 0 and p.has_shelf
    assert p.has_toe_kick and p.has_counter is False
    assert p.height == base_case_height("laminate") == 32.0     # 33-1/2" rule
    assert p.depth == 23.5


def test_two_door_base_parts_and_model():
    p = Params(style="base_2doors", width=30)
    parts, layout = build_parts(p)
    names = [x.name for x in parts]
    assert names.count("Door L") == 1 and names.count("Door R") == 1
    assert "Toe kick plate" in names and "Shelf" in names
    assert layout.drawer_heights == []
    assert len(layout.door_heights) == 2
    model = build_model(p, layout)
    assert len([b for b in model.boxes if b.name.startswith("Door")]) == 2
    # the pair's pulls sit either side of the case centerline, as on a drawer base
    xs = sorted({round(h.origin[0], 4) for h in model.holes if h.normal == (0.0, -1.0, 0.0)})
    assert xs == [round(15 - 2.0, 4), round(15 + 2.0, 4)]


def test_two_door_base_flows_through_the_sheet(tmp_path: Path):
    cabs, _settings = _run({"bw1": "30", "bs1": "base2", "walls": "left"}, tmp_path)
    assert cabs[0].params.style == "base_2doors"
    assert cabs[0].params.doors == 2 and cabs[0].params.drawers == 0
    assert cabs[0].params.height == 32.0


def test_two_door_base_gets_a_client_sheet_page(tmp_path: Path):
    cabs, settings = _run({"bw1": "30", "bs1": "base2", "walls": "left"}, tmp_path)
    job = job_from(cabs, settings, "Two door base")
    assert [s for s, _c in style_groups(job)] == ["base_2doors"]
    pages = render_pages(job, date="November 7, 2026")
    assert any("BASE, 2 DOORS" in pg.to_string() for pg in pages)


def test_two_door_base_is_in_the_front_view():
    data = _wire_data()["styles"]
    assert data["base2"]["ndoors"] == 2 and not data["base2"]["false_front"]
    assert data["base2"]["drawers"] == [] and data["base2"]["toe"] > 0
    assert "base2" in data and "base2" not in data["base1"]
