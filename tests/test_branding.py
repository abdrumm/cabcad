"""Coppinger logo small on every client page and image; a minimal title block (Oct 30)."""
import shutil
from pathlib import Path

from cabgen import branding as br
from cabgen.client_sheet import load_job, render_pages
from cabgen.web import _run_page, group_view

ROOT = Path(__file__).resolve().parents[1]
LOGO_VIEWBOX = 'viewBox="0 0 2860 960"'


def _job(tmp_path):
    sheet = tmp_path / "smith.csv"
    sheet.write_text("# client=Jane Smith\n# job_no=26-114\n# rev=B\n# job=Smith Kitchen\n"
                     + (ROOT / "jobs" / "sample-kitchen.csv").read_text(), encoding="utf-8")
    return load_job(sheet)


def test_every_client_page_has_the_logo_and_the_title_block(tmp_path):
    job = _job(tmp_path)
    assert job.name == "Smith Kitchen"
    pages = render_pages(job, date="October 30, 2026")
    for i, page in enumerate(pages, start=1):
        text = page.to_string()
        assert LOGO_VIEWBOX in text, i
        for words in ("Coppinger Exhibits", "9955 Westpoint Dr, Suite 150",
                      "Indianapolis, IN 46256", "(317) 913-1400", "Jane Smith", "No. 26-114",
                      ">B<", f">{i} of {len(pages)}<", "October 30, 2026", br.NAVY):
            assert words in text, (i, words)


def test_render_png_has_the_corner_mark(tmp_path):
    from cabgen.render import render_svg, write_render
    job = _job(tmp_path)
    text = render_svg(job).to_string()
    assert LOGO_VIEWBOX in text and "Smith Kitchen" in text and "Jane Smith" in text
    if shutil.which("rsvg-convert"):
        png = write_render(job, tmp_path)
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_form_carries_job_client_number_and_revision():
    from cabgen.kitchen import group_settings, group_sheet, parse_group
    page = _run_page(group_view(None))
    for name in ("job", "client", "job_no", "rev"):
        assert f'name="{name}"' in page
    form = {"bw1": "18", "bs1": "3drawer", "job": "Lobby desk", "client": "Acme\nCo", "rev": "C"}
    text = group_sheet(parse_group(form), group_settings(form))
    assert "# job=Lobby desk" in text and "# client=Acme Co" in text and "# rev=C" in text


def test_ar_phone_page_shows_the_logo():
    from cabgen.ar_web import phone_page
    assert "data:image/svg+xml;base64," in phone_page("http://x", "1", "Job")
