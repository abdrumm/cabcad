"""The kitchen sheet changes width and leaves the style's height and depth alone."""
from pathlib import Path

from cabgen.kitchen import (
    KitchenError, apply_discovered_rules, group_settings, group_sheet, layout_text,
    load_kitchen, parse_group, parse_run_widths, place_kitchen, row_labels, run_sheet, scene_of,
)
from cabgen.web import _run_page, group_view


SAMPLE = """\
# upper_bottom=54
name,style,width,run,height,depth,x,gap_after
A,3drawer,27,base,,,
B,base,18,base,,,
C,upper,27,upper,,,
"""


def test_width_changes_and_style_size_stays(tmp_path: Path):
    sheet = tmp_path / "k.csv"
    sheet.write_text(SAMPLE, encoding="utf-8")
    settings, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, settings, sheet.name)
    base, narrow, upper = cabs
    assert base.params.height == 33.5 and base.params.depth == 23.5
    assert base.params.width == 27 and narrow.params.width == 18
    assert narrow.params.height == 33.5 and narrow.params.depth == 23.5
    assert upper.params.height == 30 and upper.params.depth == 12
    assert base.x == 0 and narrow.x == 27
    assert upper.z == 54 and upper.y == 23.5 - 12
    marks = {m["text"]: m for m in row_labels(cabs)}
    assert "Base cabinets" not in marks
    assert marks == {}
    assert base.params.right_side == "wall" and narrow.params.right_side == "open"
    assert upper.params.left_side == "wall" and upper.params.right_side == "open"
    boxes, _holes, parts = scene_of(cabs)
    moved = [b for b in boxes if " B / " in b.name or b.name.startswith("B /")]
    assert moved and min(b.pos[0] for b in moved) >= 27
    assert any(p.name.startswith("Upper /") or p.name.startswith("C /") for p in parts)


def test_a_typed_height_overrides_the_style(tmp_path: Path):
    sheet = tmp_path / "k.csv"
    sheet.write_text(
        "name,style,width,run,height\nTall,3drawer,24,base,42\n",
        encoding="utf-8",
    )
    settings, rows = load_kitchen(sheet)
    cab = place_kitchen(rows, settings)[0]
    assert cab.params.height == 42 and cab.params.depth == 23.5


def test_three_widths_of_the_same_cabinet(tmp_path: Path):
    widths = parse_run_widths({"count": "3", "w1": "18", "w2": "27", "w3": "30", "w4": "36"})
    assert widths == [18, 27, 30]
    sheet = tmp_path / "run.csv"
    sheet.write_text(run_sheet(widths), encoding="utf-8")
    settings, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, settings, sheet.name)
    assert [c.name for c in cabs] == ["Base cabinet 1", "Base cabinet 2", "Base cabinet 3"]
    assert [c.params.width for c in cabs] == [18, 27, 30]
    assert row_labels(cabs) == []
    assert [c.x for c in cabs] == [0, 18, 45]
    assert {c.params.style for c in cabs} == {"base_3drawers"}
    assert {c.params.height for c in cabs} == {33.5}
    assert {c.params.depth for c in cabs} == {23.5}
    try:
        parse_run_widths({"count": "5", "w1": "18"})
    except KitchenError as exc:
        assert "3 or 4" in str(exc)
    else:
        raise AssertionError("expected KitchenError")


def _placed(form: dict, tmp_path: Path):
    cabinets = parse_group(form)
    settings = group_settings(form)
    sheet = tmp_path / "group.csv"
    sheet.write_text(group_sheet(cabinets, settings), encoding="utf-8")
    loaded, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, loaded, sheet.name)
    apply_discovered_rules(cabs, loaded)
    return cabs, loaded


def test_rows_are_independent_and_a_left_wall_is_flush(tmp_path: Path):
    form = {
        "bw1": "27", "bs1": "3drawer",
        "bw2": "18", "bs2": "base",
        "uw1": "30", "us1": "upper",
        "uoff": "4", "boff": "0",
        "walls": "left",
    }
    cabs, settings = _placed(form, tmp_path)
    by_name = {c.name: c for c in cabs}
    assert [c.name for c in cabs if c.run == "base"] == ["Base cabinet 1", "Base cabinet 2"]
    assert by_name["Base cabinet 1"].x == 0 and by_name["Base cabinet 2"].x == 27
    assert by_name["Upper 1"].x == 4
    assert by_name["Upper 1"].params.width == 30
    assert by_name["Upper 1"].params.style == "upper_2doors"
    base = by_name["Base cabinet 1"].params
    assert base.counter_overhang_left == 0 and base.left_side == "wall"
    assert base.counter_overhang_right == 0 and base.right_side == "wall"
    end = by_name["Base cabinet 2"].params
    assert end.counter_overhang_right == 1 and end.right_side == "open"
    assert end.has_spacer is False
    text = layout_text(cabs, settings)
    assert "flush" in text and "1 inch" in text
    assert [m["text"] for m in row_labels(cabs)] == []


def test_two_walls_put_one_filler_on_the_chosen_side(tmp_path: Path):
    right = {
        "bw1": "27", "bs1": "3drawer", "uw1": "27", "us1": "upper",
        "walls": "both", "filler_side": "right", "filler": "1",
    }
    cabs, settings = _placed(right, tmp_path)
    base = next(c for c in cabs if c.run == "base")
    assert base.x == 0
    assert base.params.left_side == "wall" and base.params.right_side == "wall"
    assert base.params.counter_overhang_left == 0
    assert base.params.counter_overhang_right == 0
    assert base.params.has_spacer is True and base.params.spacer_gap == 1
    assert base.params.spacer_side == "right"
    assert base.params.counter_width == 28
    text = layout_text(cabs, settings)
    assert "filler goes on the right" in text
    left = {
        "bw1": "27", "bs1": "3drawer",
        "walls": "both", "filler_side": "left", "filler": "2", "boff": "2",
    }
    cabs, _settings = _placed(left, tmp_path)
    base = next(c for c in cabs if c.run == "base")
    assert base.x == 4
    assert base.params.has_spacer is True and base.params.spacer_gap == 2
    assert base.params.counter_overhang_left == 0
    assert base.params.counter_overhang_right == 0


def test_open_ends_overhang_an_inch_each(tmp_path: Path):
    cabs, _settings = _placed({
        "bw1": "24", "bs1": "3drawer", "walls": "0",
    }, tmp_path)
    base = cabs[0].params
    assert base.left_side == "open" and base.right_side == "open"
    assert base.counter_overhang_left == 1 and base.counter_overhang_right == 1
    assert base.has_spacer is False


def test_group_rejects_a_short_width_and_a_negative_offset(tmp_path: Path):
    try:
        parse_group({"bw1": "10", "bs1": "3drawer", "walls": "left"})
    except KitchenError as exc:
        assert "under 12" in str(exc)
    else:
        raise AssertionError("expected KitchenError")
    try:
        parse_group({"bw1": "18", "bs1": "vanity", "walls": "left"})
    except KitchenError as exc:
        assert "vanity" in str(exc)
    else:
        raise AssertionError("expected KitchenError")
    try:
        group_settings({"walls": "left", "uoff": "-1"})
    except KitchenError as exc:
        assert "past the wall" in str(exc)
    else:
        raise AssertionError("expected KitchenError")


def test_group_page_starts_with_one_base_and_one_upper():
    page = _run_page(group_view(None))
    assert "Add an upper" in page and "Add a base cabinet" in page
    assert 'id="uw1"' in page and 'id="bw1"' in page
    assert 'value="27"' in page
    assert 'id="uw2"' in page and "hidden" in page
    assert 'id="walls-left"' in page and "checked" in page
    assert "Offset from the left wall" in page


def test_unknown_style_names_the_line(tmp_path: Path):
    sheet = tmp_path / "k.csv"
    sheet.write_text("name,style,width\nA,pantry,30\n", encoding="utf-8")
    settings, rows = load_kitchen(sheet)
    try:
        place_kitchen(rows, settings, sheet.name)
    except KitchenError as exc:
        assert "pantry" in str(exc)
    else:
        raise AssertionError("expected KitchenError")


def test_filler_is_one_two_or_three_inches():
    base = {"walls": "both", "filler_side": "left", "uoff": "0", "boff": "0"}
    for w in ("1", "2", "3"):
        assert group_settings({**base, "filler": w})["filler"] == float(w)
    assert group_settings({**base, "filler": ""})["filler"] == 1.0
    for bad in ("0.5", "1.5", "4"):
        try:
            group_settings({**base, "filler": bad})
        except KitchenError:
            continue
        raise AssertionError(f"filler {bad} should be refused")


def test_uppers_never_get_a_filler(tmp_path: Path):
    from cabgen.params import Params
    up = Params(style="upper_2doors", has_spacer=True, spacer_gap=1.0, left_side="wall")
    assert not up.has_filler
    base = Params(style="base_3drawers", has_spacer=True, spacer_gap=2.0, left_side="wall")
    assert base.has_filler
    sheet = tmp_path / "k.csv"
    sheet.write_text("name,style,width,run,gap_after\nU,upper,27,upper,1\n")
    settings, rows = load_kitchen(sheet)
    try:
        place_kitchen(rows, settings)
    except KitchenError as e:
        assert "uppers never get a filler" in str(e)
    else:
        raise AssertionError("upper gap_after should be refused")


def test_one_drawer_style_takes_a_drawer_height(tmp_path: Path):
    form = {"bw1": "27", "bs1": "base", "bd1": "8", "bw2": "18", "bs2": "3drawer",
            "uw1": "27", "us1": "upper", "walls": "left"}
    cabinets = parse_group(form)
    assert [c["drawer"] for c in cabinets] == [8.0, None, None]
    sheet = tmp_path / "g.csv"
    sheet.write_text(group_sheet(cabinets, group_settings(form)))
    settings, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, settings, sheet.name)
    assert cabs[0].params.drawer_front_h == 8.0
    try:
        parse_group({**form, "bd1": "10"})
    except KitchenError:
        pass
    else:
        raise AssertionError("a 10 inch drawer should be refused")
    page = _run_page(group_view(form)) if _run_page.__code__.co_argcount == 1 else None
    if page is not None:
        assert 'id="bd1"' in page and 'value="8" selected' in page


def test_uppers_never_have_drawers(tmp_path: Path):
    sheet = tmp_path / "k.csv"
    sheet.write_text("name,style,width,run\nU,upper_drawer,27,upper\n")
    settings, rows = load_kitchen(sheet)
    try:
        place_kitchen(rows, settings, sheet.name)
    except KitchenError as e:
        assert "never have drawers" in str(e)
    else:
        raise AssertionError("an upper with a drawer should be refused")
    try:
        parse_group({"uw1": "27", "us1": "upper_drawer", "walls": "left"})
    except KitchenError:
        pass
    else:
        raise AssertionError("the form should refuse an upper drawer")

