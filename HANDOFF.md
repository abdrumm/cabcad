# CabCAD — handoff

## What it is
CabCad is Brook's rules-based cabinet configurator for Coppinger Exhibits. Pick
styles and widths for a base row and an upper row; it writes carpenter shop
drawings, a cut list, 4x8 nest sheets, a client PDF, a 3D model for Omacad, and
phone AR files (USDZ/GLB). Python 3.11+, no third-party runtime deps. Tests use
pytest.

## Where the master lives
- Master: this iMac, `~/Work/cabcad` (after the cutover from
  `~/Work/cabinet-gen`, which the README still names - that path is stale).
- Backup/remote: GitHub `abdrumm/cabcad`.
- This working copy: `~/Work/cabcad-v015`, branch `v0.15`, tagged `v0.15`.
- No other folder is master.

## How to run
```bash
cd ~/Work/cabcad
python3 -m cabgen.cli web --port 8777
# open http://127.0.0.1:8777/  (kitchen run); /single is one cabinet

python3 -m cabgen.cli styles
python3 -m cabgen.cli generate --out out --name "Base-27"
python3 -m cabgen.cli kitchen jobs/sample-kitchen.csv --out out/sample-kitchen
python3 -m cabgen.cli client jobs/sample-kitchen.csv --out out/client-sheet
python3 -m cabgen.cli front jobs/sample-kitchen.csv --out out/front
```
Tests (pytest is the only dev dependency; a local venv works):
```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

## What's in v0.15
- Base-run sizes from the old line (Brook, 2026-11-02): base case depth, toe
  kick height, toe kick recess (case front to kick face), countertop depth.
  Set once for the whole base run in the form, or as `# base_depth=`,
  `# toe_kick_h=`, `# toe_kick_recess=`, `# counter_depth=` lines in a sheet.
  Blank keeps the style/default.
- New base style `base_2doors` (form key `base2`, "2 doors"): a pair of doors,
  no drawer, one adjustable shelf, toe kick.
- The 33-1/2" finished-height rule is kept: the base case is 33-1/2" minus the
  countertop build (32" laminate or solid surface, 33-1/2" with none). The form
  shows "Base case height" read-only; a typed height is ignored. Toe kick comes
  out of the case, never off the finished height.
- Countertop depth follows the case (case + 1-1/2" front overhang) unless it is
  called out, so the back of the top stays on the wall. Side views dimension the
  toe kick recess.
- Version 0.15 in `cabgen/__init__.py`; shown in the page title and footer.
- PR #7 single-door base (Handle L/R) is in, as on main.

## Test status
145 passed, 2 failed (pytest, Python 3.12, 2026-11-08, this checkout). The two
failures are pre-existing and only happen when `~/Work/omacad` is not installed:

- `tests/test_nest_project.py::test_group_form_build_writes_pdf_and_cutlists`
- `tests/test_uppers.py::test_labels_nest_and_cut_list`

Both call `write_kitchen`, which shells out to Omacad to write the model. On
the iMac (2026-11-07) the same suite was 140 passed, 0 failed. The seven tests
added since then pass. AR export does not need Omacad and passes here.

## Known gaps / open questions
- `docs/CABCAD-SPEC.md` still describes the Oct 30 build, except the solid-surface
  build-up bullets, which now match the Nov 7 perimeter rule. It is not updated
  for the v0.15 base-run sizes or `base_2doors`.
- README says `cd ~/Work/cabinet-gen`; master is `~/Work/cabcad`.
- Counter depth is one number per run; mixed case depths use the deepest case for
  the counter's back face.
- A toe kick taller than 4" keeps the case top at 32" and shortens the box.
  Confirm Brook wants that rather than a taller finished height (which would
  break the ADA 34" rule).
- `generate --with-omacad` and `kitchen` without `--no-show` need Omacad on the
  machine; they open workspace 3 full screen.
- Laminate build-up is unchanged from Oct 24: 4" strips under the front edge, at
  each end, and centred on every cabinet joint, and no strip along the back wall.
  The Nov 7 perimeter rule was applied to solid surface only. Ask Brook whether
  laminate should drop the joint strips too.
- On a solid-surface top the 4" is the strip width. The strips are still 1"
  plywood, directly under the 1/2" top, so the edge stays 1-1/2" and the base
  case stays 32" (finished height 33-1/2"). That reading matches the laminate
  strips, which Brook already calls 4" wide.
- Back and side splashes were already the same material as the top (laminate on
  plywood, or solid surface). The countertop page now draws them in the
  countertop colour. No new shop rule.
- The front-view HTML is a file to drop into the CE pipeline. CabCad does not
  publish it to the company site. The render PNG and the AR files (USDZ and GLB)
  are written beside that page and linked from it. If a writer fails, that link
  is drawn dashed and marked "Placeholder — file not produced".

## Where we left off / next steps
Done 2026-11-08, from docs/PLANS.md items 3, 4 and 5. Items 1 and 2 were left
alone. The finished height is still 33-1/2".

- Solid-surface build-up is 4" strips of 1" plywood directly under the top,
  around the perimeter only (front, behind the edge strip; back wall; both
  ends). No strip runs across the seams between cabinets. The cut list, the
  nest, the counter takeoff, the drawings and the Omacad boxes all use those
  strips. Laminate build-up is unchanged.
- The client-sheet countertop page (page 2) has a front view, a top view, a
  side view and a details block: build-up strips, splashes in the countertop
  colour, overhangs and dimensions. Same border and title block as the other
  sheets.
- Standalone front elevation: `python3 -m cabgen.cli front <sheet.csv> --out
  <dir>` writes SVG, PDF and an HTML page for the CE pipeline. The HTML links
  the render PNG and the AR files written next to it. The kitchen form has a
  Front view button beside the client sheet (it also lives on the job card).

Still to do:
1. Cut over: put this tree at `~/Work/cabcad`, keep the `v0.15` tag, push to
   GitHub as the backup.
2. Update `docs/CABCAD-SPEC.md` and `README.md` for v0.15 (the solid-surface
   build-up lines are already current).
3. Ask Brook: does a non-4" toe kick keep 33-1/2" finished (current) or change it?
4. Check `base_2doors` against a real shop cabinet (shelf position, pull height)
   before the first job.
5. Ask Brook whether laminate build-up should also stay off the cabinet joints.
   It still has a strip on every joint, and none along the back wall.

Future revisions and Brook's notes: see docs/PLANS.md.
