"""Laminate numbers: the library, the job sheet, the AR colours, the Omacad payload."""
import json
import struct
from pathlib import Path

from cabgen.ar_export import _hex_rgb, export_ar
from cabgen.finishes import (
    FALLBACK_HEX, LIBRARY_PATH, WHITE_HEX, library, lookup, part_role,
)
from cabgen.kitchen import load_kitchen, place_kitchen, scene_of
from cabgen.omacad_export import BUILDER, scene_payload
from cabgen.params import Params
from cabgen.parts import build_parts

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "jobs" / "sample-kitchen.csv"

REQUIRED = (
    ("Formica", "5786-NG", "Ashwood Oak"),
    ("Formica", "912", "Storm"),
    ("Formica", "3450-58", "Mineral Jet"),
    ("Formica", "9529", "Seasalt"),
    ("Formica", "JO718", "Fenix Grigio Londra"),
    ("Formica", "5789", "Clove Spice Cherry"),
    ("Wilsonart", "7995-38", "Sterling Ash"),
    ("Wilsonart", "7909-60", "Fusion Maple"),
    ("Wilsonart", "7924K-07", "Biltmore Cherry"),
    ("SparkleLam", "", "Light Aqua"),
    ("", "white", "White melamine"),
    ("Corian", "Glacier White", "Glacier White"),
    ("Corian", "Dove", "Dove"),
    ("Corian", "Cloud White", "Cloud White"),
    ("Meganite", "Jet Black", "Jet Black"),
    ("HI-MACS", "Black Pearl", "Black Pearl"),
)


def test_library_lists_the_shop_finishes_as_approximate_colours():
    rows = {(r.manufacturer, r.number, r.name): r for r in library()}
    assert set(REQUIRED) <= set(rows)
    for fin in rows.values():
        assert fin.approximate
        assert fin.texture == ""
        assert fin.hex.startswith("#") and len(fin.hex) == 7
    text = LIBRARY_PATH.read_text(encoding="utf-8")
    assert "texture" in text.splitlines()[0]
    oak = lookup("5786-NG")
    assert oak.name == "Ashwood Oak" and oak.hex == lookup("Formica 5786-NG").hex
    assert lookup("Ashwood Oak").hex == oak.hex
    assert lookup("5786").number == "5786-NG"
    assert lookup("JO718").name == "Fenix Grigio Londra"
    assert lookup("Grigio Londra").number == "JO718"
    assert lookup("SparkleLam Light Aqua").name == "Light Aqua"
    assert lookup("white").name == "White melamine" and lookup("white").hex == WHITE_HEX
    assert lookup("Corian Glacier White").kind == "solid"
    assert lookup("HI-MACS Black Pearl").hex == lookup("HIMACS Black Pearl").hex
    assert lookup("3450-58").name == "Mineral Jet"
    assert lookup("7995-38").name == "Sterling Ash"


def test_unknown_number_is_a_neutral_gray_and_a_warning():
    fin = lookup("NO-SUCH-99")
    assert fin.fallback and fin.hex == FALLBACK_HEX and "NO-SUCH-99" in fin.warning
    assert lookup("  ") .hex == WHITE_HEX and not lookup("").fallback


def test_blank_means_white_melamine_and_a_row_can_override(tmp_path: Path):
    sheet = tmp_path / "k.csv"
    sheet.write_text(
        "# doors=5786-NG\n"
        "# top=3450-58\n"
        "name,style,width,run,doors,case\n"
        "Oak,3drawer,27,base,,\n"
        "Storm,3drawer,18,base,912,9529\n",
        encoding="utf-8",
    )
    settings, rows = load_kitchen(sheet)
    oak, storm = place_kitchen(rows, settings, sheet.name)
    assert oak.params.finish_doors == "5786-NG"
    assert oak.params.finish_case == ""
    assert oak.params.finish_interior == ""
    assert oak.params.finish_top == "3450-58"
    assert storm.params.finish_doors == "912"
    assert storm.params.finish_case == "9529"
    boxes, _holes, parts = scene_of([oak, storm], settings)
    def color(fragment):
        hit = [b for b in boxes if fragment in b.name]
        assert hit, fragment
        return hit[0].color
    assert color("Oak / Gable L") == WHITE_HEX
    assert color("Oak / Drawer front 1") == lookup("5786-NG").hex
    assert color("Oak / Back panel") == WHITE_HEX
    assert color("Storm / Drawer front 1") == lookup("912").hex
    assert color("Storm / Gable L") == lookup("9529").hex
    assert color("Countertop / Top") == lookup("3450-58").hex
    assert any("Formica 5786-NG Ashwood Oak" in p.laminate for p in parts)
    assert "finish_warnings" not in settings or settings["finish_warnings"] == []
    # a number the library does not know is still a cabinet, and it is reported
    bad = tmp_path / "bad.csv"
    bad.write_text("name,style,width,run,doors\nA,3drawer,27,base,NO-SUCH-99\n", encoding="utf-8")
    settings, rows = load_kitchen(bad)
    cabs = place_kitchen(rows, settings, bad.name)
    scene_of(cabs, settings)
    assert settings["finish_warnings"] and "NO-SUCH-99" in settings["finish_warnings"][0]
    assert color_of(cabs, settings) == FALLBACK_HEX


def color_of(cabs, settings):
    boxes, _h, _p = scene_of(cabs, settings)
    door = next(b for b in boxes if "Drawer front" in b.name)
    return door.color


def test_a_saved_number_stays_text():
    p = Params.from_dict({"style": "base_3drawers", "finish_doors": "912", "finish_case": ""})
    assert p.finish_doors == "912" and p.finish_case == ""
    _parts, _layout = build_parts(p)


def test_roles():
    assert part_role("Gable L") == "case"
    assert part_role("Top stile, front") == "case"
    assert part_role("Door, handle L", '3/4" melamine + laminate') == "doors"
    assert part_role("False front") == "doors"
    assert part_role("Drawer front 1") == "doors"
    assert part_role("Drawer box side 1") == "interior"
    assert part_role("Open shelf 1") == "interior"
    assert part_role("Microwave shelf heel") == "interior"
    assert part_role("Back panel") == "interior"
    assert part_role("Wire pull, door L", "wire pull") == "hardware"
    assert part_role("CT1-TOP Countertop / Top", '3/4" plywood') == "top"
    assert part_role("CT1-BUF Countertop / Build-up, front", '3/4" plywood') == "top"
    assert part_role("CT1-BS Countertop / Backsplash", '3/4" plywood') == "top"
    assert part_role("CT1-BUL Countertop / Build-up, left end", '3/4" plywood') == "substrate"
    assert part_role("CT1-STF Countertop / Stiffener, front", '1" plywood') == "substrate"


def _glb(path):
    data = Path(path).read_bytes()
    jlen = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + jlen])


def test_ar_view_uses_the_finish_colours(tmp_path: Path):
    res = export_ar(out_dir=tmp_path, name="sample", sheet_path=SAMPLE)
    assert res["warnings"] == []
    gltf = _glb(res["glb"])
    by_name = {m["name"]: m for m in gltf["materials"]}
    oak = lookup("5786-NG").hex
    jet = lookup("3450-58").hex
    assert f"Front {oak.upper()}" in by_name
    assert f"Laminate_top {jet.upper()}" in by_name
    assert "Case" in by_name and "Pull" in by_name and "Interior" in by_name

    def factor(name):
        return by_name[name]["pbrMetallicRoughness"]["baseColorFactor"][:3]

    assert factor(f"Front {oak.upper()}") == list(_hex_rgb(oak))
    assert factor(f"Laminate_top {jet.upper()}") == list(_hex_rgb(jet))
    assert factor("Case") == list(_hex_rgb(WHITE_HEX))
    assert factor("Interior") == list(_hex_rgb(WHITE_HEX))
    # the old schematic names are still there for a job that names nothing
    plain = export_ar(out_dir=tmp_path / "plain", name="plain",
                      sheet_path=ROOT / "jobs" / "upper-styles.csv")
    names = {m["name"] for m in _glb(plain["glb"])["materials"]}
    assert {"Case", "Front", "Pull", "Laminate_top"} <= names


def test_unknown_finish_still_exports_ar(tmp_path: Path):
    sheet = tmp_path / "bad.csv"
    sheet.write_text(
        "# doors=NOT-A-LAMINATE\nname,style,width,run\nA,base,30,base\n",
        encoding="utf-8",
    )
    res = export_ar(out_dir=tmp_path, name="bad", sheet_path=sheet)
    assert any("NOT-A-LAMINATE" in w for w in res["warnings"])
    gltf = _glb(res["glb"])
    colors = [m["pbrMetallicRoughness"]["baseColorFactor"][:3] for m in gltf["materials"]]
    assert list(_hex_rgb(FALLBACK_HEX)) in colors


def test_omacad_payload_carries_body_colours():
    settings, rows = load_kitchen(SAMPLE)
    cabs = place_kitchen(rows, settings, SAMPLE.name)
    boxes, holes, _parts = scene_of(cabs, settings)
    payload = scene_payload("Sample", boxes, holes)
    painted = [b for b in payload["boxes"] if b.get("color")]
    assert painted
    door = next(b for b in payload["boxes"] if "Drawer front" in b["name"] or "/ Door" in b["name"])
    oak = lookup("5786-NG").hex.lstrip("#")
    assert door["color"][0] == round(int(oak[0:2], 16) / 255, 4)
    assert door["color"][3] == 1.0
    gable = next(b for b in payload["boxes"] if "Gable L" in b["name"])
    white = WHITE_HEX.lstrip("#")
    assert gable["color"][0] == round(int(white[0:2], 16) / 255, 4)
    assert "body_colors" in BUILDER and "def paint" in BUILDER
