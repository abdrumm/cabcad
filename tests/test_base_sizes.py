"""Base-run sizes ported from the old line: case depth, toe kick height and recess,
and countertop depth. The 33-1/2" finished height rule still wins.

Brook, 2026-11-02: the toe kick has two called-out sizes. The recess is measured
from the CASE front, not the door face. The counter's back face stays on the wall.
"""
from pathlib import Path

import pytest

from cabgen.client_sheet import job_from, render_pages
from cabgen.counter import build_counter
from cabgen.kitchen import (
    KitchenError, apply_discovered_rules, group_settings, group_sheet, layout_text,
    load_kitchen, parse_group, place_kitchen,
)
from cabgen.params import (
    BASE_DEPTH, FINISHED_COUNTER_TOP, TOE_KICK_H, TOE_KICK_RECESS, Params,
)
from cabgen.web import _run_page, _wire_data, group_view


def _run(form: dict, tmp_path: Path):
    """The form, through the sheet, and back into placed cabinets."""
    cabinets = parse_group(form)
    settings = group_settings(form)
    sheet = tmp_path / "group.csv"
    sheet.write_text(group_sheet(cabinets, settings), encoding="utf-8")
    loaded, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, loaded, sheet.name)
    apply_discovered_rules(cabs, loaded)
    return cabs, loaded


def test_form_shows_the_base_sizes_and_locks_the_case_height():
    page = _run_page(group_view(None))
    for field in ("height", "depth", "toe_kick_h", "toe_kick_recess", "counter_depth"):
        assert f'id="{field}" name="{field}"' in page, field
    assert "Base sizes" in page
    for text in ("Base case height", "Base case depth", "Toe kick height", "Toe kick depth",
                 "Countertop depth"):
        assert text in page, text
    assert 'id="height" name="height"' in page and "readonly" in page
    assert "33-1/2" in page and "countertop build" in page
    # defaults keep the style's numbers
    view = group_view(None)
    assert view["base_height"] == "32" and view["base_depth"] == "23.5"
    assert view["toe_kick_h"] == "4" and view["toe_kick_recess"] == "3"
    assert view["counter_depth"] == ""            # blank follows the case


def test_case_height_field_follows_the_countertop_choice():
    laminate = _run_page(group_view({"counter": "laminate", "walls": "left"}))
    none = _run_page(group_view({"counter": "none", "walls": "left"}))
    assert 'id="height" name="height"' in laminate
    assert 'value="32"' in laminate
    assert 'value="33.5"' in none
    data = _wire_data()
    assert data["case_height"] == {"laminate": 32.0, "solid": 32.0, "none": 33.5}


def test_base_sizes_round_trip_and_keep_the_33_and_a_half_rule(tmp_path: Path):
    form = {"bw1": "30", "bs1": "base2", "walls": "left",
            "depth": "24", "toe_kick_h": "3.5", "toe_kick_recess": "2.5",
            "counter_depth": "26", "counter": "laminate"}
    cabs, settings = _run(form, tmp_path)
    p = cabs[0].params
    assert p.depth == 24 and p.toe_kick_h == 3.5 and p.toe_kick_recess == 2.5
    assert settings["base_depth"] == 24 and settings["counter_depth"] == 26
    # the rule holds: the case is 33-1/2" minus the countertop build
    assert p.height == 32.0
    counter = build_counter(cabs, settings)
    assert counter.depth == 26 and counter.top_z == FINISHED_COUNTER_TOP == 33.5
    text = layout_text(cabs, settings)
    assert "case depth 24" in text and "toe kick 3 1/2" in text and "counter 26" in text


def test_a_posted_case_height_cannot_break_the_rule(tmp_path: Path):
    form = {"bw1": "30", "bs1": "3drawer", "walls": "left", "height": "40"}
    cabs, _settings = _run(form, tmp_path)
    assert cabs[0].params.height == 32.0       # 33-1/2" finished, not the typed 40


def test_counter_depth_follows_the_case_when_it_is_left_blank(tmp_path: Path):
    cabs, settings = _run({"bw1": "30", "bs1": "3drawer", "walls": "left",
                           "depth": "24"}, tmp_path)
    assert settings.get("counter_depth") is None
    counter = build_counter(cabs, settings)
    assert counter.depth == 24 + 1.5            # case depth + the 1-1/2" front overhang
    assert counter.top_z == 33.5


def test_the_toe_kick_comes_out_of_the_case_not_the_finished_height(tmp_path: Path):
    cabs, settings = _run({"bw1": "30", "bs1": "3drawer", "walls": "left",
                           "toe_kick_h": "3"}, tmp_path)
    p = cabs[0].params
    assert p.height == 32.0 and p.toe_kick_h == 3.0
    assert p.case_bottom_z == 3.0 and p.case_h == 29.0
    assert build_counter(cabs, settings).top_z == 33.5


def test_toe_kick_height_is_capped_at_4_inches(tmp_path: Path):
    """Brook, Nov 9: the kick is never taller than 4". Finished height stays 33-1/2"."""
    page = _run_page(group_view(None))
    assert 'id="toe_kick_h" name="toe_kick_h" min="0" max="4"' in page
    assert "Math.min(4, Math.max(0, toeRaw))" in page
    from cabgen.web import _form_html
    single = _form_html({"style": "base_3drawers", "toe_kick_h": 4})
    assert 'name="toe_kick_h"' in single and 'max="4"' in single
    with pytest.raises(KitchenError, match="4"):
        group_settings({"bw1": "30", "bs1": "3drawer", "walls": "left", "toe_kick_h": "5"})
    cabs, settings = _run({"bw1": "30", "bs1": "3drawer", "walls": "left",
                           "toe_kick_h": "4"}, tmp_path)
    assert cabs[0].params.toe_kick_h == 4.0 and cabs[0].params.height == 32.0
    assert build_counter(cabs, settings).top_z == 33.5
    sheet = tmp_path / "tall.csv"
    sheet.write_text("# toe_kick_h=6\nname,style,width,run\nA,3drawer,30,base\n", encoding="utf-8")
    loaded, rows = load_kitchen(sheet)
    with pytest.raises(KitchenError, match="4"):
        place_kitchen(rows, loaded, sheet.name)


def test_sizes_out_of_range_are_refused():
    base = {"bw1": "30", "bs1": "3drawer", "walls": "left"}
    for key, value in (("depth", "40"), ("toe_kick_h", "5"), ("toe_kick_recess", "13"),
                       ("counter_depth", "50")):
        with pytest.raises(KitchenError):
            group_settings({**base, key: value})
    # a top cannot be shallower than the case it sits on
    with pytest.raises(KitchenError, match="shallower"):
        group_settings({**base, "depth": "24", "counter_depth": "20"})


def test_side_view_calls_out_the_toe_kick_recess(tmp_path: Path):
    cabs, settings = _run({"bw1": "30", "bs1": "base2", "walls": "left",
                           "toe_kick_recess": "2.5"}, tmp_path)
    job = job_from(cabs, settings, "Kick")
    pages = render_pages(job, date="November 7, 2026")
    detail = next(p.to_string() for p in pages if "BASE, 2 DOORS" in p.to_string())
    assert "kick 2 1/2" in detail
    assert "back from the case front" not in detail


def test_front_view_reads_the_toe_kick_and_case_height():
    page = _run_page(group_view(None))
    assert "wfVal('toe_kick_h')" in page and "wfVal('height')" in page
    data = _wire_data()["styles"]
    assert data["base2"]["toe"] == TOE_KICK_H == Params().toe_kick_h
    assert TOE_KICK_RECESS == Params().toe_kick_recess
    assert BASE_DEPTH == Params().depth
    p = Params(style="base_2doors", depth=24)
    assert p.counter_depth == 25.5              # follows the case
    p.counter_depth = 26.0                      # a call-out of its own
    p.set_case_depth(23.0)
    assert p.counter_depth == 26.0              # stays as called out
