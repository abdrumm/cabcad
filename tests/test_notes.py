"""Condensed, context-aware shop and client notes (Brook, Oct 30)."""
from pathlib import Path

from cabgen.client_sheet import load_job, render
from cabgen.draw import shop_drawing
from cabgen.notes import NOTES, Facts, facts_from_job, facts_from_params, select
from cabgen.params import Params
from cabgen.parts import build_parts


def _ids(f, audience="shop"):
    return {n.id for n in NOTES if n.audience == audience and n.when(f)}


def test_every_note_is_short_and_has_a_condition():
    for n in NOTES:
        assert n.audience in ("shop", "client") and callable(n.when)
        assert len(n.render(Facts(filler=1, filler_side="right"))) <= 110, n.id


def test_laminate_job_has_no_solid_surface_notes_and_vice_versa():
    lam = _ids(Facts(bases=1, counter="laminate"))
    assert "counter-lam" in lam and "counter-solid" not in lam
    solid = _ids(Facts(bases=1, counter="solid"))
    assert "counter-solid" in solid and "counter-lam" not in solid
    assert not {"counter-lam", "counter-solid", "height"} & _ids(Facts(bases=1, counter="none"))


def test_no_drawers_no_drawer_note_no_sink_no_sink_note():
    f = Facts(uppers=2, doors=4)
    ids = _ids(f)
    assert "drawers" not in ids and "sink" not in ids and "microwave" not in ids
    assert "uppers" in ids and "fronts" in ids
    assert {"drawers", "sink"} <= _ids(Facts(bases=2, drawers=3, sink=True))


def test_facts_come_from_the_design(tmp_path: Path):
    sheet = tmp_path / "k.csv"
    sheet.write_text("# counter=solid\n# base_walls=both\n# filler=2\n# filler_side=left\n"
                     "name,style,width,run\nA,sink,30,base\nU,upper,30,upper\n", encoding="utf-8")
    job = load_job(sheet)
    f = facts_from_job(job)
    assert f.sink and f.drawers == 0 and f.counter == "solid" and f.filler == 2 and f.uppers == 1
    page = render(job).to_string()
    assert "Solid surface, 1-1/2" not in page and "Sink base: false drawer front" not in page
    assert "NOTES" not in page
    assert "filler closes the gap at the left wall" not in page


def test_single_cabinet_drawing_notes_only_what_applies():
    p = Params(style="upper_2doors", width=30)
    parts, layout = build_parts(p)
    svg, _ = shop_drawing(p, parts, layout)
    text = svg.to_string()
    assert "SITE" in text and "UPPERS" in text
    for absent in ("Corian", "DRAWERS -", "SINK -", "COUNTERTOP -"):
        assert absent not in text, absent
    assert facts_from_params(Params(style="base_3drawers")).drawers == 3
    assert "DRAWERS" in [t for t, _ in select(Facts(drawers=1), "shop")]
