"""Brook, Oct 30: every job finishes at 33-1/2" floor to countertop top (ADA-safe, <= 34").
The base case is 33-1/2" minus the countertop build; the 4" toe kick stays.
3-drawer boxes in 3D follow the cut-list rule (front - 2")."""
from pathlib import Path

from cabgen.ar_export import export_ar
from cabgen.client_sheet import load_job
from cabgen.params import FINISHED_COUNTER_TOP, Params, base_case_height
from cabgen.model3d import build_model
from cabgen.parts import build_parts

SHEET = "# counter={kind}\nname,style,width,run\nA,3drawer,18,base\nB,base,30,base\nU,upper,30,upper\n"


def _job(tmp_path: Path, kind: str):
    path = tmp_path / f"{kind}.csv"
    path.write_text(SHEET.format(kind=kind), encoding="utf-8")
    return load_job(path)


def test_finished_height_is_33_and_a_half_for_every_countertop(tmp_path: Path):
    assert FINISHED_COUNTER_TOP == 33.5 <= 34.0
    for kind in ("laminate", "solid"):
        job = _job(tmp_path, kind)
        assert job.counter.top_z == 33.5, kind
        for c in job.bases:
            assert c.params.height == base_case_height(kind) == 32.0
            assert c.params.toe_kick_h == 4.0
        parts = {pt.name: pt for pt in build_parts(job.bases[1].params)[0]}
        assert parts["Gable (side panel)"].width == 32.0      # cut list follows the case
    none = _job(tmp_path, "none")
    assert none.counter is None and {c.params.height for c in none.bases} == {33.5}


def test_ar_model_tops_out_at_33_and_a_half_plus_the_splash(tmp_path: Path):
    path = tmp_path / "b.csv"
    path.write_text("# counter=laminate\nname,style,width,run\nA,base,30,base\n", encoding="utf-8")
    res = export_ar(sheet_path=path, out_dir=tmp_path, name="b")
    assert abs(res["size_m"][1] - (33.5 + 4.0) * 0.0254) < 1e-4


def test_three_drawer_boxes_in_3d_match_the_cut_list():
    p = Params(style="base_3drawers", width=18)
    parts, layout = build_parts(p)
    side = next(pt for pt in parts if pt.name.startswith("Drawer box side"))
    model = build_model(p, layout)
    sides = [b for b in model.boxes if b.name.startswith("Drawer box side")]
    assert sides and all(abs(b.size[2] - side.width) < 1e-6 for b in sides)
    front = layout.drawer_heights[0]
    assert abs(side.width - (front - 2.0)) < 1e-6
