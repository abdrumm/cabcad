"""Local pages declare a viewport and fluid CSS for short laptops and large monitors."""
from pathlib import Path

from cabgen.params import Params
from cabgen.web import PAGE, _layout_table, _result_html, _run_page, group_view


def _full(body: str) -> str:
    from cabgen import __version__
    return PAGE.format(body=body, presets="{}", style_keys="[]", version=__version__)


def test_viewport_meta_and_responsive_css_are_present():
    home = _full("<p>home</p>")
    run = _full(_run_page(group_view(None)))
    for page in (home, run):
        assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in page
        assert "clamp(" in page
        assert "dvh" in page
        assert "minmax(" in page
        assert "@media (max-width:" in page
        assert "@media (max-height:" in page
        assert ".table-scroll" in page
    assert "#wire { display: block; width: 100%; max-width: 100%; height: auto; }" in run
    assert 'grid-template-areas: "main wire"' not in run
    assert 'preserveAspectRatio="xMidYMid meet"' in run
    assert "@media (max-height: 900px)" in run
    assert "flex-wrap: wrap" in run
    assert 'class="stage"' in run


def test_tables_scroll_inside_their_own_container(tmp_path: Path):
    drawing = tmp_path / "job-drawing.svg"
    drawing.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    result = _result_html(Params(), [str(drawing)], [], tmp_path)
    assert '<div class="table-scroll"><table>' in result
    layout = _layout_table(
        "| Name | Run | Style |\n|---|---|---|\n| B1 | Base | 3 drawers |\n"
    )
    assert layout.startswith('<div class="table-scroll"><table>')
    assert layout.endswith("</table></div>")
