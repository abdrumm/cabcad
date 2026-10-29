"""Whole-project nesting: kerf, no overlaps, every piece once, backs on their own."""
from collections import Counter
from pathlib import Path

from cabgen.kitchen import (
    apply_discovered_rules, group_settings, group_sheet, load_kitchen, parse_group,
    place_kitchen, scene_of, write_kitchen,
)
from cabgen.nest_project import (
    KERF, NestError, Piece, cutlist_csv, nest_pieces, nest_project, project_pieces,
)

ROOT = Path(__file__).resolve().parents[1]
EPS = 1e-6


def _sample():
    settings, rows = load_kitchen(ROOT / "jobs" / "sample-kitchen.csv")
    cabs = place_kitchen(rows, settings, "sample")
    apply_discovered_rules(cabs, settings)
    return cabs


def _group_form(tmp_path: Path):
    form = {"bw1": "27", "bs1": "3drawer", "bw2": "18", "bs2": "base", "bw3": "30",
            "bs3": "3drawer", "uw1": "27", "us1": "upper", "uw2": "18", "us2": "upper",
            "uw3": "30", "us3": "upper", "walls": "both", "filler_side": "right", "filler": "1"}
    sheet = tmp_path / "group.csv"
    sheet.write_text(group_sheet(parse_group(form), group_settings(form)), encoding="utf-8")
    return sheet


def _check_layout(groups, kerf=KERF):
    for g in groups.values():
        for sh in g.sheets:
            placed = sh.placed
            for p in placed:
                assert p.x >= -EPS and p.y >= -EPS
                assert p.x + p.dx <= sh.sheet_l + EPS and p.y + p.dy <= sh.sheet_w + EPS
                assert {round(p.dx, 4), round(p.dy, 4)} == {round(p.piece.width, 4), round(p.piece.length, 4)}
            for i, a in enumerate(placed):
                for b in placed[i + 1:]:
                    apart = (a.x + a.dx + kerf <= b.x + EPS or b.x + b.dx + kerf <= a.x + EPS
                             or a.y + a.dy + kerf <= b.y + EPS or b.y + b.dy + kerf <= a.y + EPS)
                    assert apart, f"{a.piece.label} and {b.piece.label} are closer than the kerf"


def test_sample_kitchen_every_piece_once_no_overlap():
    cabs = _sample()
    pieces = project_pieces(cabs)
    groups = nest_project(cabs)
    _check_layout(groups)
    placed = Counter(p.piece.label for g in groups.values() for p in g.pieces)
    wanted = Counter(p.label for p in pieces)
    assert placed == wanted
    assert max(wanted.values()) == 1, "labels must be unique"


def test_backs_are_their_own_nest_and_first_cabinet_starts_sheet_one():
    groups = nest_project(_sample())
    backs = [k for k in groups if "back panels" in k]
    assert len(backs) == 1
    for key, g in groups.items():
        for p in g.pieces:
            assert (p.piece.part == "Back panel") == (key in backs)
            assert (key in backs) <= (abs(p.piece.thk - 0.5) < EPS)
    first = groups['3/4" melamine'].sheets[0]
    assert "B1-GL" in {p.piece.label for p in first.placed}


def test_kerf_is_respected_with_a_wide_blade():
    cabs = _sample()
    groups = nest_project(cabs, kerf=0.5)
    _check_layout(groups, kerf=0.5)


def test_part_bigger_than_a_sheet_is_a_clear_error():
    big = Piece("X1-GL", "X", "Gable", '3/4" melamine', 0.75, 50.0, 100.0)
    try:
        nest_pieces([big])
    except NestError as exc:
        assert "X1-GL" in str(exc) and "48 x 96" in str(exc)
    else:
        raise AssertionError("expected NestError")
    # fits only turned, so a grain material refuses it
    long = Piece("X1-SH", "X", "Shelf", "3/4\" birch plywood", 0.75, 90.0, 30.0, grain=True)
    try:
        nest_pieces([long])
    except NestError as exc:
        assert "grain" in str(exc)
    else:
        raise AssertionError("expected NestError")


def test_grain_material_never_turns():
    pieces = [Piece(f"B1-P{i}", "B1", "Panel", '3/4" birch plywood', 0.75, 30.0, 20.0, grain=True)
              for i in range(5)]
    groups = nest_pieces(pieces)
    assert all(not p.turned for g in groups.values() for p in g.pieces)
    free = [Piece(f"B1-P{i}", "B1", "Panel", '3/4" melamine', 0.75, 30.0, 20.0) for i in range(5)]
    _check_layout(nest_pieces(free))


def test_same_width_parts_share_a_strip():
    pieces = [Piece(f"B{i}-TSF", f"B{i}", "Top stile, front", '3/4" melamine', 0.75, 4.0, 25.5)
              for i in range(1, 4)]
    sheet = nest_pieces(pieces)['3/4" melamine'].sheets[0]
    assert len(sheet.strips) == 1 and len(sheet.strips[0].blocks) == 3


def test_cad_boxes_carry_the_cut_sheet_labels():
    cabs = _sample()
    boxes, _holes, _parts = scene_of(cabs)
    names = [b.name for b in boxes]
    assert any(n.startswith("B1-GL Base cabinet 27 / Gable L") for n in names)
    assert any(n.startswith("U1-DR ") for n in names)
    labels = {p.label for p in project_pieces(cabs)}
    on_cad = {n.split(" ", 1)[0] for n in names}
    assert labels <= on_cad, sorted(labels - on_cad)


def test_group_form_build_writes_pdf_and_cutlists(tmp_path: Path):
    sheet = _group_form(tmp_path)
    ok, msg = write_kitchen(sheet, tmp_path, "Base run", show=False)
    assert ok, msg
    for suffix in ("-nest-cutlist.csv", "-nest-cutlist.md"):
        assert (tmp_path / f"base-run{suffix}").is_file()
    import shutil
    if shutil.which("rsvg-convert"):
        assert (tmp_path / "base-run-nest.pdf").stat().st_size > 1000
    settings, rows = load_kitchen(sheet)
    cabs = place_kitchen(rows, settings, "g")
    apply_discovered_rules(cabs, settings)
    groups = nest_project(cabs)
    rows_out = cutlist_csv(groups).strip().splitlines()
    assert len(rows_out) - 1 == len(project_pieces(cabs))
    assert "SP" in " ".join(rows_out), "the 1 inch filler is in the cut list"
