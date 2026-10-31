"""One set of default widths (CLI = form), and a cut list that follows the typed widths.
Brook, Oct 30."""
from pathlib import Path

from cabgen.kitchen import STYLES
from cabgen.params import DEFAULT_WIDTHS, FORM_STYLE_KEYS, Params, STYLE_PRESETS, default_width
from cabgen.web import _run_page, group_view, live_cutlist


def test_cli_presets_and_form_defaults_are_the_same_numbers():
    for key, width in DEFAULT_WIDTHS.items():
        style = STYLES[key]
        assert FORM_STYLE_KEYS[key] == style
        assert STYLE_PRESETS[style]["width"] == width, key        # CLI: Params(style=...)
        assert Params(style=style).width == width, key
        assert default_width(key) == default_width(style) == width
    page = _run_page(group_view(None))
    assert f'id="bw1" name="bw1" min="12" step="0.0625"' in page
    assert '"3drawer": 18.0' in page and '"upper": 30.0' in page   # JS defaults, same dict


def test_cut_list_follows_the_widths_on_the_form(tmp_path: Path):
    form = {"bw1": "24", "bs1": "base", "bd1": "6", "uw1": "30", "us1": "upper", "walls": "left"}
    first = live_cutlist(form, tmp_path)
    assert "24&quot; wide" in first and "30&quot; wide" in first
    assert "22 1/2&quot;" in first          # 24" base: bottom, stiles at the inside width
    form["bw1"] = "33"
    second = live_cutlist(form, tmp_path)
    assert "33&quot; wide" in second and "31 1/2&quot;" in second and "24&quot; wide" not in second
    assert "under 12" in live_cutlist({"bw1": "8", "bs1": "base"}, tmp_path)
