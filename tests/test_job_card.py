"""The result page as a job card: outputs grouped by who they are for (Oct 31).

Shop floor files link straight to /files; Client and Model buttons live outside
the run form and reach it with form="runform".
"""
from pathlib import Path

from cabgen.params import Params
from cabgen.web import (
    _form_html, _job_card, _nest_summary, _result_html, _run_page, group_view,
)

NEST_MD = """# Base run - nested cut list

## Summary

| Material | Sheets | Pieces | Yield | Offcuts kept (sq ft) | Waste (sq ft) | Cuts |
|---|---|---|---|---|---|---|
| 3/4" melamine | 2 | 24 | 63% | 12.4 | 5.1 | 31 |

## Part codes
"""


def _out(tmp_path: Path, *names: str) -> Path:
    for name in names:
        (tmp_path / name).write_text("x", encoding="utf-8")
    return tmp_path


def test_card_groups_shop_client_and_model(tmp_path):
    _out(tmp_path, "base-run-nest.pdf", "base-run-nest-cutlist.md", "base-run.omacad")
    card = _job_card(tmp_path, "base-run")
    assert "Shop floor" in card and "Client" in card and "Model" in card
    assert 'href="/files/base-run-nest.pdf"' in card
    assert 'formaction="/client-sheet"' in card and 'formaction="/ar"' in card
    assert 'form="runform"' in card


def test_card_only_shows_files_that_exist(tmp_path):
    _out(tmp_path, "base-run-nest.pdf")
    card = _job_card(tmp_path, "base-run")
    assert "base-run-nest.pdf" in card
    assert "base-run-nest-cutlist.md" not in card
    assert "base-run.omacad" not in card
    assert _job_card(tmp_path, "nothing-here", form_id="") == ""
    # With the run form behind it the buttons still make sense on an empty job.
    assert "Client sheet (PDF)" in _job_card(tmp_path, "nothing-here")


def test_card_without_a_form_has_no_buttons(tmp_path):
    _out(tmp_path, "cab-nest.pdf", "cab.omacad")
    card = _job_card(tmp_path, "cab", form_id="")
    assert 'href="/files/cab-nest.pdf"' in card
    assert "<button" not in card, "the single-cabinet page has no run form to submit"


def test_nest_summary_is_one_line_per_material(tmp_path):
    (tmp_path / "job-nest-cutlist.md").write_text(NEST_MD, encoding="utf-8")
    line = _nest_summary(tmp_path, "job")
    assert line == '3/4" melamine: 2 sheets, 63% yield, 12.4 sq ft of offcuts kept'
    assert _nest_summary(tmp_path, "missing") == ""


def test_run_page_puts_the_card_above_the_layout(tmp_path):
    _out(tmp_path, "base-run-nest.pdf")
    page = _run_page(group_view(None), card=_job_card(tmp_path, "base-run"),
                     layout="| Name | Run |\n|---|---|\n| B1 | Base |")
    assert page.index("This job") < page.index("This run")
    assert 'id="runform"' in page, "the card's buttons need the form to point at"


def test_single_cabinet_result_gets_the_same_card(tmp_path):
    (tmp_path / "base-cabinet-nest.pdf").write_text("x", encoding="utf-8")
    html = _result_html(Params(name="Base cabinet"), [str(tmp_path / "base-cabinet-nest.pdf")],
                        [], tmp_path)
    assert "This job" in html and "Shop floor" in html
    assert '<details class="jmore"><summary>All files</summary>' in html


def test_the_kitchen_form_is_the_front_door(tmp_path):
    page = _form_html({})
    assert '<a href="/">' in page, "the single-cabinet page points back to the kitchen form"
    assert 'action="/generate"' in page
