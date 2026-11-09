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
    assert [x.name for x in bu] == ["Build-up, front", "Build-up, left end", "Build-up, right end"]
    assert all("glued and stapled" in x.notes.lower() for x in bu)
    assert all(x.width == 4.0 for x in bu)
    assert not any("joint" in x.name.lower() or "back" in x.name.lower() for x in bu)
    orders = [lp.order for lp in ct.laminate]
    assert min(orders) <= 2 and 3 in orders
    assert "Laminate takeoff" in counter_text(ct)


def test_solid_build():
    ct = build_counter(_cabs([30, 24]), {"counter": "solid"})
    mats = {x.material for x in ct.pieces}
    assert '1/2" solid surface' in mats and '1" plywood' in mats
    assert not ct.laminate and not ct.dogbones


def _buildup(ct):
    return [p for p in ct.pieces if "Build-up" in p.name]


def _on_perimeter(ct, box) -> bool:
    """A strip touches the front, the back, or either end of the underside."""
    x, y, _z = box.pos
    dx, dy, _dz = box.size
    front_y = ct.y_front + (0.5 if ct.kind == "solid" else 0.0)
    on_front = abs(y - front_y) < 1e-6 and dy <= 4.01
    on_back = abs((y + dy) - ct.y_back) < 1e-6 and dy <= 4.01
    on_left = min(abs(x - ct.x0), abs(x - (ct.x0 + 0.5))) < 1e-6 and dx <= 6.01
    on_right = min(abs((x + dx) - ct.x1), abs((x + dx) - (ct.x1 - 0.5))) < 1e-6 and dx <= 6.01
    return on_front or on_back or on_left or on_right


def test_solid_buildup_is_a_perimeter_only():
    """Brook, Nov 7: 4" strips directly under the top, not across cabinet seams."""
    from cabgen.kitchen import scene_of
    from cabgen.omacad_export import scene_payload

    cabs = _cabs([30, 24, 18])
    ct = build_counter(cabs, {"counter": "solid"})
    strips = _buildup(ct)
    assert [p.name for p in strips] == [
        "Build-up, front", "Build-up, back", "Build-up, left end", "Build-up, right end",
    ]
    assert ct.joints, "the run has interior seams to stay clear of"
    for p in strips:
        assert p.width == 4.0 and p.thk == 1.0 and p.material == '1" plywood'
        assert "joint" not in p.name.lower()
        for b in p.boxes:
            assert abs(b.pos[2] - ct.z0) < 1e-6
            assert abs((b.pos[2] + b.size[2]) - (ct.z0 + 1.0)) < 1e-6  # directly under the 1/2" top
            assert _on_perimeter(ct, b), p.name
    text = counter_text(ct)
    assert "perimeter only" in text
    assert "do not run across the seams" in text

    boxes, _holes, parts = scene_of(cabs, {"counter": "solid"})
    names = [p.name for p in parts if p.name.startswith("Countertop")]
    assert any(n.endswith("Build-up, front") for n in names)
    assert not any("joint" in n.lower() for n in names)
    model = [b.name for b in boxes if "Build-up" in b.name]
    assert len(model) == 4 and not any("joint" in n.lower() for n in model)
    payload = scene_payload("Solid", boxes, _holes)
    omacad = [b["name"] for b in payload["boxes"] if "Build-up" in b["name"]]
    assert len(omacad) == 4

    # laminate matches: front and ends only, nothing across a cabinet joint, no back strip
    lam = build_counter(cabs, {"counter": "laminate"})
    assert [p.name for p in _buildup(lam)] == [
        "Build-up, front", "Build-up, left end", "Build-up, right end",
    ]


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
    from cabgen.client_sheet import job_from, load_job, render_pages
    from cabgen.finishes import get
    job = load_job(ROOT / "jobs" / "sample-kitchen.csv", "Sample")
    pages = render_pages(job, "Oct 24, 2026")
    text = pages[1].to_string()
    for words in ("COUNTERTOP - LAMINATE", "FRONT VIEW", "TOP VIEW", "SIDE VIEW", "DETAILS",
                  "TYPICAL LAMINATE SEAM", "BUILD-UP, FROM BELOW", "overhang",
                  "match the countertop", "Coppinger Exhibits"):
        assert words in text, words
    assert 'width="17.0in" height="11.0in"' in text
    maple = get("lam-maple")["color"]
    picked = job_from(job.cabs, {**job.settings, "finish_counter": "lam-maple"}, "Sample")
    picked_page = render_pages(picked, "Oct 24, 2026")[1].to_string()
    assert maple in picked_page          # top and splashes use the countertop colour
    solid = job_from(job.cabs, {**job.settings, "counter": "solid"}, "Sample")
    solid_page = render_pages(solid, "Oct 24, 2026")[1].to_string()
    assert "COUNTERTOP - SOLID SURFACE" in solid_page
    assert "perimeter only" in solid_page
    assert "Not across the seams" in solid_page
    assert "centred where cabinets meet" not in solid_page
