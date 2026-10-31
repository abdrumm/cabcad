"""One cabinet gets the same labelled nest sheets as a whole kitchen (Oct 31).

Before this the single-cabinet path used the old plain nester: shapes with a name
and a size, but no strip letters, no offcut callouts and no cut order.
"""
from pathlib import Path

from cabgen.cli import generate
from cabgen.params import Params


def _one(tmp_path: Path, style: str = "base_1drawer_2doors") -> Path:
    p = Params(style=style, name="Base cabinet", width=27)
    generate(p, tmp_path)
    return tmp_path


def test_single_cabinet_writes_the_project_nest_files(tmp_path):
    _one(tmp_path)
    for name in ("base-cabinet-nest.pdf", "base-cabinet-nest-cutlist.md",
                 "base-cabinet-nest-cutlist.csv"):
        assert (tmp_path / name).is_file(), name
    assert (tmp_path / "base-cabinet-nest.pdf").stat().st_size > 2000
    assert (tmp_path / "base-cabinet-nest-pages" / "p01-summary.svg").is_file()


def test_sheet_has_labels_offcuts_and_cut_order(tmp_path):
    _one(tmp_path)
    pages = sorted((tmp_path / "base-cabinet-nest-pages").glob("*.svg"))
    sheet = next(p for p in pages if "summary" not in p.name).read_text()
    assert "CUT ORDER" in sheet
    assert "B1-GL" in sheet and "offcut" in sheet
    assert "LEGEND" in sheet and "part: label, width x length" in sheet


def test_nest_cutlist_matches_the_cut_list(tmp_path):
    _one(tmp_path)
    md = (tmp_path / "base-cabinet-nest-cutlist.md").read_text()
    assert "## Part codes" in md and "B1-GL" in md
    assert "Offcuts to keep" in md
    plain = (tmp_path / "base-cabinet-cutlist.csv").read_text()
    assert "Gable" in plain, "the saw cut list is still written"


def test_an_upper_is_labelled_u1(tmp_path):
    _one(tmp_path, "upper_2doors")
    md = (tmp_path / "base-cabinet-nest-cutlist.md").read_text()
    assert "U1-" in md and "B1-" not in md
