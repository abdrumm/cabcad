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
140 passed, 0 failed (pytest 9.2, Python 3.14, 2026-11-07). The Omacad and AR
tests pass here; no pre-existing failures to report.

## Known gaps / open questions
- `docs/CABCAD-SPEC.md` still describes the Oct 30 build; not updated for the
  v0.15 base-run sizes or `base_2doors`.
- README says `cd ~/Work/cabinet-gen`; master is `~/Work/cabcad`.
- Counter depth is one number per run; mixed case depths use the deepest case for
  the counter's back face.
- A toe kick taller than 4" keeps the case top at 32" and shortens the box.
  Confirm Brook wants that rather than a taller finished height (which would
  break the ADA 34" rule).
- `generate --with-omacad` and `kitchen` without `--no-show` need Omacad on the
  machine; they open workspace 3 full screen.

## Where we left off / next steps
1. Cut over: put this tree at `~/Work/cabcad`, keep the `v0.15` tag, push to
   GitHub as the backup.
2. Update `docs/CABCAD-SPEC.md` and `README.md` for v0.15.
3. Ask Brook: does a non-4" toe kick keep 33-1/2" finished (current) or change it?
4. Check `base_2doors` against a real shop cabinet (shelf position, pull height)
   before the first job.

Future revisions and Brook's notes: see docs/PLANS.md.
