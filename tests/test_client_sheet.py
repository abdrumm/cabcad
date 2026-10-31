"""Client sheet: one page, all four views, no Omacad."""
import shutil
from pathlib import Path

from cabgen.client_sheet import ft_in, load_job, render, render_pages, style_groups, write_client_sheet
from cabgen.web import _handle_client_sheet

ROOT = Path(__file__).resolve().parents[1]


def test_sample_page_has_every_view_and_the_schedule():
    job = load_job(ROOT / "jobs" / "sample-kitchen.csv")
    text = render(job, date="October 23, 2026").to_string()
    for words in ("FRONT ELEVATION", "PLAN (TOP VIEW)", "END VIEW", "3D VIEW", "CABINETS",
                  "Sample Kitchen", "October 23, 2026", "6 (3 base, 3 upper)",
                  "bases 75"):
        assert words in text, words
    for tag in ("B1", "B2", "B3", "U1", "U2", "U3"):
        assert f">{tag}<" in text
    assert 'width="17.0in" height="11.0in"' in text
    assert ft_in(84) == "84\" (7'-0\")" and ft_in(10) == '10"'


def test_form_button_returns_a_pdf_and_shows_the_filler(tmp_path: Path):
    form = {"bw1": "27", "bs1": "3drawer", "bw2": "18", "bs2": "base", "uw1": "27",
            "us1": "upper", "walls": "both", "filler_side": "right", "filler": "2", "boff": "0"}
    if not shutil.which("rsvg-convert"):
        return
    pdf, page = _handle_client_sheet(form, tmp_path)
    assert pdf is not None, page
    assert pdf[:5] == b"%PDF-"
    assert (tmp_path / "client-sheet.pdf").is_file()
    svg = (tmp_path / "client-sheet.svg").read_text(encoding="utf-8")
    assert "Filler, right end of the bases" in svg
    bad, page = _handle_client_sheet({"bw1": "8"}, tmp_path)
    assert bad is None and "under 12" in page


def test_one_detail_page_per_style_about_one_cabinet_only():
    job = load_job(ROOT / "jobs" / "sample-kitchen.csv")
    groups = style_groups(job)
    assert [s for s, _ in groups] == ["base_3drawers", "base_1drawer_2doors", "upper_2doors"]
    assert [[job.codes[c.name] for c in cabs] for _s, cabs in groups] == [["B1", "B3"], ["B2"], ["U1", "U2", "U3"]]
    pages = render_pages(job, date="October 23, 2026")
    assert len(pages) == 5                      # overview, countertop, 3 styles
    assert "COUNTERTOP" in pages[1].to_string()
    three = pages[2].to_string()
    assert "BASE, 3 DRAWERS" in three and "W = 27&quot;" in three
    assert "drawn on this page" in three and ">B3<" in three
    assert ">B2<" not in three and ">U1<" not in three   # nothing from the neighbours
    assert "Page 3 of 5" in three
