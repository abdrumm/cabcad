"""tools/plans-page: plan + ideas markdown -> one HTML dashboard (Brook, Oct 30)."""
import importlib.machinery
import importlib.util
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "tools" / "plans-page"
loader = importlib.machinery.SourceFileLoader("plans_page", str(TOOL))
spec = importlib.util.spec_from_loader("plans_page", loader)
pp = importlib.util.module_from_spec(spec)
loader.exec_module(pp)

PLAN = """# CabCad Plan

Updated 2026-10-30 (ET).

## Build order
| # | Step | Done when | Status |
|---|---|---|---|
| 1 | Finish picker | dropdowns change AR | BUILT |
| 2 | Estimator | price within tolerance | NEXT |

## Open questions
- **3-drawer box height**: why 2" under the front?
"""
IDEAS = """# Ideas

## Finishes
- BUILT — Finish picker with `13` finishes.
  - Test: open the form, pick Walnut look, press AR view.
- DONE — iPhone AR.
- LATER — Photo swatch to texture.
- OPEN QUESTION — Who can add finishes?
"""


def test_status_column_tests_and_open_questions(tmp_path):
    (tmp_path / "p.md").write_text(PLAN)
    (tmp_path / "i.md").write_text(IDEAS)
    out = pp.build(tmp_path / "p.md", tmp_path / "i.md", tmp_path / "x.html")
    page = out.read_text()
    assert page.startswith("<!doctype html>") and "#263460" in page
    assert '<span class="st built">Built</span>' in page and '<span class="st next">Next</span>' in page
    assert 'class="test">open the form, pick Walnut look, press AR view.' in page
    assert '<ul class="questions">' in page and "<b>3-drawer box height</b>" in page
    assert "Who can add finishes?" in page.split('<ul class="questions">')[1].split("</ul>")[0]
    assert "<code>13</code>" in page
    items = pp.parse_ideas(IDEAS)
    assert [i["status"] for i in items] == ["BUILT", "BUILT", "LATER", "OPEN QUESTION"]


def test_real_docs_build(tmp_path):
    work = Path.home() / "Work"
    if (work / "CABCAD-PLAN.md").is_file():
        page = pp.build(work / "CABCAD-PLAN.md", work / "CABCAD-IDEAS.md", tmp_path / "r.html").read_text()
        assert "Build order" in page
