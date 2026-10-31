"""Finish picker MVP: catalog, separate picks, 3D/AR use, custom finishes (Oct 30)."""
import json
import zipfile
from pathlib import Path

import pytest

from cabgen import finishes
from cabgen.ar_export import export_ar
from cabgen.client_sheet import load_job, render
from cabgen.web import _run_page, group_view

SHEET = ("# counter={counter}\n# finish_fronts=lam-walnut\n# finish_box=lam-white\n"
         "# finish_counter={top}\nname,style,width,run\nA,base,30,base\nU,upper,30,upper\n")


@pytest.fixture(autouse=True)
def _custom(tmp_path, monkeypatch):
    monkeypatch.setenv("CABCAD_CUSTOM_FINISHES", str(tmp_path / "custom.json"))


def test_starter_catalog_is_licensed_and_split_by_kind():
    cat = finishes.catalog()
    assert 12 <= len(cat) <= 15
    kinds = {f["kind"] for f in cat}
    assert kinds == {"laminate", "solid_surface"}
    for f in cat:
        assert f["color"].startswith("#") and 0 <= f["roughness"] <= 1
        if f["texture"]:
            assert finishes.texture_path(f) is not None and f["license"] == "CC0-1.0"
            assert "ambientcg.com" in f["source"]
    woods = [f for f in cat if f["family"] == "wood"]
    assert {"Maple look", "White oak look", "Walnut look", "Birch ply look"} <= {f["name"] for f in woods}
    readme = (finishes.DIR / "README.md").read_text()
    assert "CC0" in readme and "Wood027" in readme


def test_picks_change_the_client_sheet_colours(tmp_path):
    sheet = tmp_path / "k.csv"
    sheet.write_text(SHEET.format(counter="solid", top="ss-warm-gray"), encoding="utf-8")
    job = load_job(sheet)
    text = render(job).to_string()
    walnut, white, gray = (finishes.get(i)["color"] for i in ("lam-walnut", "lam-white", "ss-warm-gray"))
    assert walnut in text and gray in text
    assert "Walnut look" in text and "Warm gray" in text          # the notes list the picks


def test_ar_files_carry_the_finishes_and_textures(tmp_path):
    sheet = tmp_path / "k.csv"
    sheet.write_text(SHEET.format(counter="laminate", top="lam-maple"), encoding="utf-8")
    res = export_ar(sheet_path=sheet, out_dir=tmp_path, name="k")
    with zipfile.ZipFile(res["usdz"]) as z:
        names = z.namelist()
        assert names[0].endswith((".usda", ".usdc"))
        assert "textures/walnut.jpg" in names and "textures/maple.jpg" in names
        usda = z.read(names[0]).decode()
        assert "UsdUVTexture" in usda and "primvars:st" in usda and "@textures/walnut.jpg@" in usda
        for info in z.infolist():
            assert (info.header_offset + 30 + len(info.filename) + len(info.extra)) % 64 == 0
    data = Path(res["glb"]).read_bytes()
    jlen = int.from_bytes(data[12:16], "little")
    gltf = json.loads(data[20:20 + jlen])
    assert len(gltf["images"]) == 2 and gltf["textures"]
    assert any("TEXCOORD_0" in p["attributes"] for p in gltf["meshes"][0]["primitives"])
    assert Path(res["usdz"]).stat().st_size < 3_000_000                       # email-friendly


def test_form_has_three_pickers_and_custom_finishes_join_them(tmp_path):
    page = _run_page(group_view(None))
    for name in ("finish_fronts", "finish_box", "finish_counter"):
        assert f'name="{name}"' in page
    assert "Add custom finish" in page and "Walnut look" in page
    f = finishes.add_custom("Kensington Maple", "7972-60", "laminate", "#C8A27A")
    assert f["id"] in {x["id"] for x in finishes.choices("laminate")}
    assert json.loads((tmp_path / "custom.json").read_text())["finishes"][0]["needs_match"]
    assert "Kensington Maple (7972-60) (custom, not yet on an estimate)" in _run_page(group_view(None))
    with pytest.raises(ValueError):
        finishes.add_custom("Bad", "", "laminate", "red")
