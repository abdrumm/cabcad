"""11x17 sheets: one title line on top, a thin rail on the right, drawings in the rest."""
import re
from pathlib import Path

from cabgen.client_sheet import PAGE_H, PAGE_W, RAIL_W, load_job, render, render_pages
from cabgen.draw import shop_drawing
from cabgen.front_view import render_front
from cabgen.params import Params
from cabgen.parts import build_parts

ROOT = Path(__file__).resolve().parents[1]


def _texts(svg: str):
    return re.findall(
        r'<text x="([\d.]+)" y="([\d.]+)"[^>]*font-size="([\d.]+)"[^>]*>([^<]*)</text>',
        svg,
    )


def _rail(svg: str):
    """A tall narrow rectangle on the right is the identity rail."""
    rects = re.findall(
        r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"',
        svg,
    )
    hits = []
    for x, y, w, h in rects:
        x, y, w, h = map(float, (x, y, w, h))
        if x > 14 and 1.2 <= w <= 2.0 and h > 8:
            hits.append((x, y, w, h))
    return hits


def test_client_pages_keep_11x17_and_use_the_right_rail():
    job = load_job(ROOT / "jobs" / "sample-kitchen.csv", "Sample Kitchen")
    pages = render_pages(job, date="November 11, 2026")
    for i, page in enumerate(pages, start=1):
        text = page.to_string()
        assert 'width="17.0in" height="11.0in"' in text
        assert _rail(text), i
        # the job name sits in the top band, not in a tall block
        title = [t for t in _texts(text) if "Sample Kitchen" in t[3]]
        assert title, i
        y = float(title[0][1])
        size = float(title[0][2])
        assert y < 0.8 and size <= 0.17, (i, y, size)
        for x, y, size, body in _texts(text):
            assert float(x) < PAGE_W - 0.02, (i, body)
            assert 0 < float(y) < PAGE_H - 0.02, (i, body)


def test_a_long_job_name_stays_on_one_line():
    job = load_job(ROOT / "jobs" / "sample-kitchen.csv")
    job.name = "Westfield Corporate Campus " * 40
    text = render(job, date="November 11, 2026").to_string()
    assert 'height="11.0in"' in text
    titles = [t for t in _texts(text) if "Westfield" in t[3]]
    assert len(titles) == 1
    assert float(titles[0][1]) < 0.8
    assert float(titles[0][2]) <= 0.16
    assert titles[0][3].endswith("\u2026")
    assert len(titles[0][3]) < len(job.name)


def test_front_sheet_uses_the_same_rail_and_a_larger_elevation():
    job = load_job(ROOT / "jobs" / "sample-kitchen.csv", "Sample Kitchen")
    text = render_front(job, "November 11, 2026").to_string()
    assert _rail(text)
    assert "FRONT ELEVATION" in text and "PLAN (TOP VIEW)" not in text
    # the elevation box is the whole drawing area: its heading sits under the title line
    head = [t for t in _texts(text) if t[3] == "FRONT ELEVATION"][0]
    assert float(head[1]) < 1.3
    assert RAIL_W < 2


def test_shop_drawing_uses_a_thin_rail_too():
    p = Params(style="base_3drawers", name="Base cabinet", width=30)
    parts, layout = build_parts(p)
    svg, _rest = shop_drawing(p, parts, layout)
    text = svg.to_string()
    assert 'width="17.0in" height="11.0in"' in text
    assert _rail(text)
    assert "SHOP DRAWING" in text
