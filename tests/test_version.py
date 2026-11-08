"""One obvious version number: cabgen.__version__, shown in the web UI title and footer."""
from cabgen import __version__
from cabgen.web import PAGE


def test_version_lives_in_cabgen_init():
    assert __version__ == "0.15"


def test_version_shows_in_the_page_title_and_footer():
    page = PAGE.format(body="<p>home</p>", presets="{}", style_keys="[]", version=__version__)
    assert "<title>CabCad v0.15 - cabinet shop drawings</title>" in page
    assert '<footer class="version"><p class="sub">CabCad v0.15</p></footer>' in page
