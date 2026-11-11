"""11x17 sheets: drawings use the top of the page; identity is a short bottom-right block."""
import re
from pathlib import Path

from cabgen.client_sheet import BLOCK_H, BLOCK_W, PAGE_H, PAGE_W, SCHED_W, load_job, render, render_pages
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


def _block(svg: str):
    """The identity block: a small bottom-right box, about a quarter of the old rail."""
    rects = re.findall(
        r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"',
        svg,
    )
    hits = []
    for x, y, w, h in rects:
        x, y, w, h = map(float, (x, y, w, h))
        if x > 12 and 2.4 <= w <= 4.0 and 1.2 <= h <= 2.0 and y > 8:
            hits.append((x, y, w, h))
    return hits


def test_client_pages_use_a_short_bottom_right_block():
    job = load_job(ROOT / "jobs" / "sample-kitchen.csv", "Sample Kitchen")
    pages = render_pages(job, date="November 11, 2026")
    for i, page in enumerate(pages, start=1):
        text = page.to_string()
        assert 'width="17.0in" height="11.0in"' in text
        block = _block(text)
        assert block, i
        _x, y, _w, h = block[0]
        assert abs(h - BLOCK_H) < 0.05
        assert abs(_w - BLOCK_W) < 0.05
        old = 5.2 * round(11.0 / 3.0, 3)
        assert 0.22 * old <= BLOCK_W * BLOCK_H <= 0.28 * old
        assert y + h > PAGE_H - 0.6
        title = [t for t in _texts(text) if "Sample Kitchen" in t[3]]
        assert title, i
        ty = float(title[0][1])
        assert ty > 6.5, (i, ty)
        assert float(title[0][2]) <= 0.16
        for tx, yy, _size, body in _texts(text):
            assert float(tx) < PAGE_W - 0.02, (i, body)
            assert 0 < float(yy) < PAGE_H - 0.02, (i, body)


def test_cabinets_table_sits_left_of_the_block():
    job = load_job(ROOT / "jobs" / "sample-kitchen.csv", "Sample Kitchen")
    text = render(job, date="November 11, 2026").to_string()
    block = _block(text)[0]
    heads = [t for t in _texts(text) if t[3] == "CABINETS"]
    assert len(heads) == 1
    hx, hy = float(heads[0][0]), float(heads[0][1])
    assert hy > 8
    assert hx + 0.2 < block[0]
    assert abs((block[0] - SCHED_W) - hx) < 0.4
    assert "NOTES" not in text


def test_a_long_job_name_stays_on_one_line():
    job = load_job(ROOT / "jobs" / "sample-kitchen.csv")
    job.name = "Westfield Corporate Campus " * 40
    text = render(job, date="November 11, 2026").to_string()
    assert 'height="11.0in"' in text
    titles = [t for t in _texts(text) if "Westfield" in t[3]]
    assert len(titles) == 1
    assert float(titles[0][1]) > 6.5
    assert float(titles[0][2]) <= 0.12
    assert titles[0][3].endswith("\u2026")
    assert len(titles[0][3]) < len(job.name)


def test_front_sheet_is_only_the_elevation():
    job = load_job(ROOT / "jobs" / "sample-kitchen.csv", "Sample Kitchen")
    text = render_front(job, "November 11, 2026").to_string()
    assert not _block(text)
    assert "FRONT ELEVATION" in text and "PLAN (TOP VIEW)" not in text
    assert "Coppinger Exhibits" not in text
    head = [t for t in _texts(text) if t[3] == "FRONT ELEVATION"][0]
    assert float(head[1]) < 1.0


def test_shop_drawing_uses_the_same_bottom_right_block():
    p = Params(style="base_3drawers", name="Base cabinet", width=30)
    parts, layout = build_parts(p)
    svg, _rest = shop_drawing(p, parts, layout)
    text = svg.to_string()
    assert 'width="17.0in" height="11.0in"' in text
    assert _block(text)
    assert "SHOP DRAWING" in text
