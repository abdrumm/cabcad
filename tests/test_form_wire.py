"""Run form: drag-to-reorder tiles, the live front-view wireframe, default widths."""
import json
import re

from cabgen.counter import EDGE, SPLASH_H
from cabgen.kitchen import BASE_CHOICES, DRAWER_HEIGHTS, UPPER_BOTTOM, UPPER_CHOICES
from cabgen.params import (DEFAULT_WIDTHS, MW_OPENING_H, UPPER_PULL_CC, UPPER_PULL_EDGE_INSET,
                           UPPER_PULL_FROM_BOTTOM, Params)
from cabgen.web import _run_page, _wire_data, group_view


def _page():
    return _run_page(group_view(None))


def test_page_has_wireframe_and_drag_handles():
    page = _page()
    assert '<svg id="wire"' in page
    assert "function drawWire()" in page and "function moveCabinet(" in page
    assert page.count('title="Drag to move this cabinet along the row"') >= 2
    assert "pointerdown" in page and "touch-action: none" in page


def test_wire_data_is_injected_and_comes_from_params():
    page = _page()
    m = re.search(r"const WIRE = (\{.*?\});</script>", page)
    assert m
    data = json.loads(m.group(1))
    assert data == json.loads(json.dumps(_wire_data()))
    assert data["upper_bottom"] == UPPER_BOTTOM
    assert data["counter_edge"] == EDGE and data["splash_h"] == SPLASH_H
    assert data["upper_pull"] == {"cc": UPPER_PULL_CC, "from_bottom": UPPER_PULL_FROM_BOTTOM,
                                  "inset": UPPER_PULL_EDGE_INSET}
    s = data["styles"]
    assert set(s) >= {"3drawer", "base", "sink", "upper", "upper1", "open", "microwave"}
    assert s["sink"]["false_front"] and not s["base"]["false_front"]
    assert s["3drawer"]["height"] == Params().height and len(s["3drawer"]["drawers"]) == 3
    assert s["base"]["toe"] == Params().toe_kick_h
    assert set(s["base"]["by_drawer"]) == {str(h) for h in DRAWER_HEIGHTS}
    assert s["upper1"]["ndoors"] == 1 and s["upper"]["ndoors"] == 2
    assert s["open"]["open"] and len(s["open"]["shelves"]) >= 1 and s["open"]["doors"] is None
    mw = s["microwave"]
    assert mw["depth"] == 12 and abs(mw["mw"][1] - mw["mw"][0] - MW_OPENING_H) < 0.01


def test_drawer_height_changes_the_drawn_drawer():
    by = _wire_data()["styles"]["base"]["by_drawer"]
    for h in DRAWER_HEIGHTS:
        z0, z1 = by[str(h)]["drawers"][0]
        assert abs((z1 - z0) - h) < 1e-6


def test_every_style_has_a_stock_default_width_in_the_form():
    keys = {k for k, _ in BASE_CHOICES + UPPER_CHOICES}
    assert set(DEFAULT_WIDTHS) == keys
    assert all(w % 3 == 0 for w in DEFAULT_WIDTHS.values())
    assert DEFAULT_WIDTHS == {"upper": 30, "upper1": 18, "open": 24, "microwave": 30,
                              "3drawer": 18, "base": 30, "sink": 30}
    page = _page()
    m = re.search(r"const DEFAULT_W = (\{.*?\});", page)
    assert m and json.loads(m.group(1)) == DEFAULT_WIDTHS
    assert "width.value = DEFAULT_W[styleValue]" in page
