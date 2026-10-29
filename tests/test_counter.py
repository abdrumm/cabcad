"""Countertops: laminate and solid surface builds, seams, nesting, client sheet."""
from pathlib import Path

from cabgen.counter import build_counter, counter_text
from cabgen.kitchen import place_kitchen
from cabgen.nest_project import nest_project

ROOT = Path(__file__).resolve().parent.parent


def _cabs(widths):
    rows = [{"name": f"B{i}", "style": "3drawer", "width": w, "run": "base"}
            for i, w in enumerate(widths, 1)]
    return place_kitchen(rows, {"upper_bottom": 54})


def _labels(ct):
    return {p.label: p for p in ct.pieces}


def test_none_builds_nothing():
    assert build_counter(_cabs([30, 24]), {"counter": "none"}) is None


def test_laminate_build():
    ct = build_counter(_cabs([30, 24]), {"counter": "laminate"})
    p = _labels(ct)
    assert ct.kind == "laminate" and ct.seams == []
    assert "CT1-TOP" in p or "CT1-TOP1" in p
    assert all(x.material == '3/4" plywood' for x in ct.pieces)
    bu = [x for x in ct.pieces if x.label.startswith("CT1-BU")]
    assert bu and all("glued and stapled" in x.notes.lower() for x in bu)
    assert p["CT1-BUJ1"].width == 4.0
    orders = [lp.order for lp in ct.laminate]
    assert min(orders) <= 2 and 3 in orders
    assert "Laminate takeoff" in counter_text(ct)


def test_solid_build():
    ct = build_counter(_cabs([30, 24]), {"counter": "solid"})
    mats = {x.material for x in ct.pieces}
    assert '1/2" solid surface' in mats and '1" plywood' in mats
    assert not ct.laminate and not ct.dogbones


def test_long_laminate_top_is_one_piece_flagged_not_seamed():
    """Brook, Oct 27: no automatic seams. A 181" run is one 181" top, flagged."""
    from cabgen.counter import OVERSIZE_FLAG
    cabs = _cabs([36, 30, 24, 36, 30, 24])          # 181" counter
    ct = build_counter(cabs, {"counter": "laminate"})
    assert ct.seams == [] and ct.dogbones == []
    assert not any("seam" in x.name.lower() for x in ct.pieces)
    tops = [x for x in ct.pieces if "TOP" in x.label]
    assert len(tops) == 1 and tops[0].length == ct.length == 181.0
    assert OVERSIZE_FLAG in tops[0].notes
    assert any("seam TBD" in n for n in ct.notes)
    fronts = [x for x in ct.laminate if x.name.startswith("Front edge")]
    assert len(fronts) == 1 and fronts[0].length == 181.0   # laminate not seamed either
    tops3d = [b for b in ct.boxes if b.name.endswith("Countertop / Top")]
    assert len(tops3d) == 1 and tops3d[0].size[0] == 181.0


def test_long_solid_top_is_one_piece_flagged():
    cabs = _cabs([36, 30, 24, 36, 30, 24, 30])       # 211" > 144"
    ct = build_counter(cabs, {"counter": "solid"})
    assert ct.seams == [] and not ct.dogbones
    assert not any("joint adhesive" in n for n in ct.notes)
    top = next(x for x in ct.pieces if x.material == '1/2" solid surface' and x.length == 211.0)
    assert "seam TBD" in top.notes


def test_short_top_not_flagged():
    ct = build_counter(_cabs([30, 24]), {"counter": "laminate"})
    assert not any("seam TBD" in x.notes for x in ct.pieces)
    assert not any("seam TBD" in n for n in ct.notes)


def test_oversize_top_listed_not_nested():
    from cabgen.nest_project import cutlist_csv, cutlist_text, oversize_pieces
    cabs = _cabs([36, 30, 24, 36, 30, 24])
    ct = build_counter(cabs, {"counter": "laminate"})
    groups = nest_project(cabs, extra=ct.parts())    # no NestError for the 181" top
    big = oversize_pieces(groups)
    assert big and all(p.length > 96 for _k, p in big)
    assert any(p.part.endswith("Top") for _k, p in big)
    assert "seam TBD" in cutlist_text(groups, "T", cabs, 0.125)
    assert "NOT NESTED" in cutlist_csv(groups)
    placed = [p.piece.label for g in groups.values() for p in g.pieces]
    assert not any(lab == p.label for _k, p in big for lab in placed)


def test_nest_includes_ply_not_solid():
    from dataclasses import replace
    cabs = _cabs([30, 24])
    ct = build_counter(cabs, {"counter": "solid"})
    groups = nest_project(cabs, extra=ct.parts())
    names = " ".join(groups)
    assert "solid surface" not in names.lower()
    assert any("1" in g for g in groups)


def test_client_sheet_counter_page(tmp_dir=None):
    from cabgen.client_sheet import load_job, render_pages
    job = load_job(ROOT / "jobs" / "sample-kitchen.csv", "Sample")
    pages = render_pages(job, "Oct 24, 2026")
    text = pages[1].to_string()
    assert "COUNTERTOP - LAMINATE" in text and "TYPICAL LAMINATE SEAM" in text
