# cabgen

Parametric cabinet shop drawings, cut list and nesting plan.

Built for the rules in [`../cabinet-shop-standards.md`](../cabinet-shop-standards.md).
3D models live in Omacad (`../omacad`); this tool makes the 2D paper the carpenter
actually works from.

## Quick start

```bash
cd ~/Work/cabinet-gen

# list the styles
python3 -m cabgen.cli styles

# generate a set of drawings for the first job
python3 -m cabgen.cli generate --out out --name "Base-27"

# ... and the 3D model in Omacad
python3 -m cabgen.cli generate --out out --name "Base-27" --with-omacad
python3 -m cabgen.cli omacad --out out --name "Base-27"      # 3D only
python3 -m cabgen.cli open --out out --name "Base-27"        # open it in Omacad

# or the local web form (style dropdown + dimension fields)
python3 -m cabgen.cli web --port 8777
# then open http://127.0.0.1:8777/run
# one base and one upper; a plus adds to either row

# one cabinet, or a run of bases and uppers, from a spreadsheet
python3 -m cabgen.cli kitchen jobs/one-cabinet.csv
python3 -m cabgen.cli kitchen jobs/sample-kitchen.csv --out out/sample-kitchen
```

`open` (and `generate --with-omacad`) shows the model in the one Omacad window.
cabgen seeds Omacad's session file with a camera that frames the model and starts
`run.sh --resume`. A window that is already open reloads that model and stays the
only window. `--no-show` writes the file and leaves the window alone.

## What comes out (in `--out`)

| File | What it is |
|---|---|
| `<name>-drawing.svg` / `.pdf` | 11x17 sheet: front + side elevation, numbered key, notes, cut list, title block |
| `<name>-cutlist-sheet2.*` | only if the cut list runs past sheet 1 |
| `<name>-cutlist.csv` | cut list for the saw (qty, part, material, thk, width, length, banding, laminate, notes) |
| `<name>-cutlist.md` | the same, readable |
| `<name>-table-saw.txt` | one line per piece, the way it is read off the list |
| `<name>-nest-<material>-<n>.svg/.pdf` | nesting sheets, 4x8, 3/16" kerf, grain along the length |
| `<name>-params.json` | every parameter, so a job can be replayed |
| `<name>.omacad` | the 3D model: one named body per part, in mm, opens in Omacad |

PDF conversion uses `rsvg-convert` if it is installed, otherwise `cairosvg`.

## A kitchen from a spreadsheet

`jobs/one-cabinet.csv` is the current 3-drawer base. Change the width cell.
Leave height and depth blank and they stay 33.5 and 23.5.

`jobs/sample-kitchen.csv` is a run: bases side by side on the floor, uppers
above them. Each row is one cabinet, left to right. `run` is `base` or `upper`.
An upper's bottom is at 54 inches (`# upper_bottom=54` at the top of the file)
and its back sits on the same wall as the bases. `gap_after` is a filler, in
inches, before the next cabinet in that row.

Styles you can type: `3drawer`, `base` (1 drawer over 2 doors), `upper` (2 doors;
uppers never have drawers). A filled height or depth replaces the style for that one cabinet.

The command writes one Omacad model of the whole run, a layout table, and one
cut list. It opens the model full screen on workspace 3. `--no-show` skips that.

`http://127.0.0.1:8777/run` (from `cabgen.cli web`) starts with one base and one
upper. A plus on a row adds a cabinet to that row only. Each row has its own
offset from the left wall. The base run can meet no wall, the left wall, the
right wall, or both. Both walls add a filler on one side. An open end overhangs
the counter 1 inch. A wall end is flush. The end rules named so far are in
`cabinet-shop-standards.md` section 8. That list grows as rules show up.

## The model

`cabgen/params.py` holds everything that can change on a job: outer dimensions, the
style, material thicknesses, counter build, front reveals, side conditions, laminate
and sheet goods. Styles (`base_1drawer_2doors`, `base_3drawers`, `upper_2doors`) set the case type and give the dimensions a default; anything
left `None` in `Params` is filled from the style.

The front build (top down): top stretcher, drawer fronts with a reveal between them, a
flat drawer rail under the fronts, a 1/8" reveal, then the doors. The rails are visible
at the case front. See the standards file, section 2, and TBD #11/#12.

## Layout

```
cabgen/params.py     parameters, style presets, the web form fields
cabgen/parts.py      the part schedule and the vertical layout of the fronts
cabgen/model3d.py    where every part sits in space (X width, Y depth, Z height)
cabgen/omacad_export.py  writes the .omacad project (uses the Omacad venv)
cabgen/draw.py       the 11x17 shop drawing and the nesting sheets
cabgen/cutlist.py    csv / markdown / table-saw output
cabgen/nesting.py    kerf-aware nesting, grain constrained
cabgen/svg.py        small SVG writer (text, hatch, clipping)
cabgen/units.py      inch formatting in the simplest fractions
cabgen/web.py        the local web form (stdlib only)
tools/check_svg.py   layout checker: off-page elements and overlapping text
```

## The 3D model

`model3d.py` places every part in the cabinet's own coordinates (X = width from the
left face, Y = depth from the case front, Z = height from the floor) and
`omacad_export.py` writes one named Omacad body per part, in millimetres, into a
`.omacad` project. The exporter runs the Omacad venv
(`~/Work/omacad/.venv/bin/python`) as a subprocess, so nothing from Omacad is
imported here.

Open `out/<name>.omacad` in Omacad: the timeline has one box feature per part, named
after the cut list, so a part can be traced back to its cut list row.

## Checking the drawings

There is no way to look at a PDF in this environment, so the drawings are checked
structurally:

```bash
python3 tools/check_svg.py out/base-27-drawing.svg
```

It reports any element off the page and any pair of text labels that overlap.
Run it after every change to `draw.py`.

## Whole-project nesting

`python3 -m cabgen.cli kitchen <sheet.csv> --out DIR` (and "Show in Omacad" on the group
form) also writes `<job>-nest.pdf`, `<job>-nest-cutlist.md` and `<job>-nest-cutlist.csv`.
Code: `cabgen/nest_project.py`; rules: `cabinet-shop-standards.md` section 5, Nesting.
Options: `--kerf`, `--sheet-w`, `--sheet-l`. Tests: `tests/test_nest_project.py`.

## Client sheet

`python3 -m cabgen.cli client <sheet.csv> --out out/client-sheet` writes `<sheet>-client-sheet.pdf`
(11x17 landscape): page 1 is the whole kitchen (front elevation, plan, end view, 3D view,
cabinet schedule, title block), then one detail page per cabinet style (front, side, top, 3D of
one cabinet, plus the widths of that style in the job). PNG previews of every page come too.
The group form's "Client sheet (PDF)" button builds the same PDF without touching Omacad.
Code: `cabgen/client_sheet.py`. Tests: `tests/test_client_sheet.py`.

## Countertop

Pick it on the group form or in the CSV: `# counter=laminate` (default), `solid`, or `none`;
`# splash_left=yes|no`, `# splash_right=yes|no` (side splashes are on by default at wall ends).
Rules and assumptions: `~/Work/cabinet-shop-standards.md` section 3. Code: `cabgen/counter.py`.

- Laminate: 3/4" ply top + 4" ply build-up strips (glued and stapled) at the front, ends and
  every cabinet joint; laminate takeoff in sq ft, in order (sides, front, top).
- Solid surface: 1/2" top, 1-1/4" edge strip in a rabbet, 1" ply stiffeners. Solid surface is
  listed, not nested; the plywood is nested with the rest of the project.
- Seams: only when the run is longer than 96" (plywood) / 144" (solid surface), always on a
  cabinet joint, pieces about equal. Laminate seams use Brook's method: 6" strip centred on the
  seam (3" per piece), dogbone pockets 1/2" deep, adhesive, dogbone clamps at install.
- Out: `<job>-counter.md` (parts, takeoff, seams, assumptions), counter parts in the cut list and
  nest (labels `CT1-...`), and a countertop page (page 2) in the client sheet.
