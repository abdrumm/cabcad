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
170 passed, 2 failed (pytest, Python 3.12, 2026-11-11, this checkout). The two
failures are pre-existing and only happen when `~/Work/omacad` is not installed:

- `tests/test_nest_project.py::test_group_form_build_writes_pdf_and_cutlists`
- `tests/test_uppers.py::test_labels_nest_and_cut_list`

Both call `write_kitchen`, which shells out to Omacad to write the model. On
the iMac (2026-11-07) the same suite was 140 passed, 0 failed. The tests added
since then pass. AR export does not need Omacad and passes here.

## Known gaps / open questions
- `docs/CABCAD-SPEC.md` still describes the Oct 30 build, except the solid-surface
  build-up bullets, which now match the Nov 7 perimeter rule. It is not updated
  for the v0.15 base-run sizes or `base_2doors`.
- README says `cd ~/Work/cabinet-gen`; master is `~/Work/cabcad`.
- Counter depth is one number per run; mixed case depths use the deepest case for
  the counter's back face.
- Toe kick height is 4" at most (Brook, Nov 9). The form and a sheet both
  refuse a taller kick. The kick still comes out of the case, and the finished
  height stays 33-1/2".
- `generate --with-omacad` and `kitchen` without `--no-show` need Omacad on the
  machine; they open workspace 3 full screen.
- Build-up on every countertop (laminate and solid surface) is 4" strips under
  the countertop around the whole perimeter, including a continuous strip along
  the full back edge (Brook, Nov 11). The Oct 24 "no back strip on laminate"
  note is superseded. No strip crosses a cabinet joint. Corners are butted, not
  stacked. The strips are in the cut list, the nest, the drawings and the
  Omacad boxes.
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
- Draft client email is off the form (Brook, Nov 11). `POST /client-email` is
  not a route. Email AR to me is unchanged and still does not send mail.
  `drafts.draft_client_email` is unused.
- Photorealistic view is the last button on the kitchen form. It does not run
  when the form is only opened. The original `.blend` was not found. The still
  is a new generic room around the current boxes, including the perimeter
  build-up (`cabgen/blender/render_kitchen.py`, version 9). No `.blend` file
  is required and none is in git. Blender is not vendored.
  Set `CABCAD_BLENDER` to the absolute path. The binary that has been run on
  the iMac is official Blender 5.2.4 LTS, portable, not on PATH:
  `/home/abdrumm/.local/opt/blender-5.2.4-linux-x64/blender`
  It is `-march=x86-64-v2` (SSE4.2). The i7-2600 has SSE4.2 and AVX, not AVX2,
  and no GPU. Cycles is CPU only: no CUDA, OptiX, HIP, or oneAPI.
  4 cores / 8 threads, 31 GiB RAM. Measured on that machine: a 64×64,
  8-sample smoke frame was 3.2 seconds, and a 4-base 4-upper kitchen at
  960×540 and 64 samples, no denoise, was 28.7 seconds for a 4-base 4-upper
  kitchen (fingerprint `16b10cbb085ede1a` on commit `6250615`). Version 3
  (`f6fe180`) was 1920×1080, 64 samples, no denoise, 89.8 seconds. Brook's
  review: the run was mirrored (microwave on the left), a blue window slab
  sat in the corner, the cabinets stood off the wall, and the fronts were
  dark and grainy. Version 4 points the camera so world +X is picture-right,
  sets the back wall flush with the cabinet backs, removes that side window,
  and lights the fronts from in front. It asks for CPU OpenImageDenoise even
  when Blender's denoiser enum comes back empty. Measured on the iMac at
  `acb6c2c`: version 4, 1920×1080, 36 samples, OIDN on, 120.4 seconds. The
  orientation, the wall, and the grain were right, and the picture was blown
  out. Version 5 keeps that camera and that denoiser, drops the light power,
  rakes the sun from the upper front-left, and renders 20 samples. Measured
  on the iMac at `391c369`: version 5, 1920×1080, 20 samples, OIDN FAST,
  58.0 seconds. Brook called it much better, and still too bright and flat,
  with no left wall and the finished right end hidden. Version 6
  (`ea16437`) measured 55.7 seconds. The left wall was in the scene, but it
  stopped half a metre past the cabinet front, so the frame looked past it
  into a black void, and it was the same colour as the back wall. Version 7
  runs that wall from the back wall to past the camera and makes it darker
  than the back wall. The light is one stop under version 6, a low amber sun.
  Version 8 brings the camera back to 35 degrees off the front, still on the
  right so the finished end shows, and frames the run tighter. Version 9
  raises that camera to just under the upper tops. Same low amber
  sun, 80 samples, bounces, and OIDN on the ACCURATE prefilter.
  Estimate about 240 seconds, four times the 55.7 second frame. Not measured.
  One render at a time, in the background, cached by design. A repeat of the same
  design on that machine was 0.015 seconds, and an ordinary page was 0.044
  seconds. `GET /photo-status` only checks; it does not start a render.
  This checkout did not run Blender, so there is no new kitchen PNG from here.
  `cabgen.render` is still the flat shaded still. Cabinet sizes are unchanged.

## Where we left off / next steps
Done 2026-11-08, from docs/PLANS.md items 3, 4 and 5. Items 1 and 2 were left
alone. The finished height is still 33-1/2".

- Build-up does not cross a cabinet joint on any countertop (Brook, Nov 9).
  Solid surface: 4" strips of 1" plywood directly under the top, at the front
  (behind the edge strip), the back wall, and both ends. Laminate: 4" strips
  of 3/4" plywood under the top on that same perimeter, including the back
  edge (Brook, Nov 11). The cut list, the nest, the counter takeoff, the
  drawings and the Omacad boxes follow those strips.
- Carpenter 2D is the old client-sheet PDF, renamed (Brook, Nov 11). The form
  button is Carpenter 2D (`POST /carpenter-2d`). `POST /client-sheet` still
  returns the same PDF. Page 1 is the kitchen. The countertop page is included
  once. Then one drawing page per style. Cabinet detail pages are drawings
  and dimensions only: no "WHAT IT IS" list, no "THIS STYLE IN …" table, and
  no "drawn on this page" line. Shop drawings and cut lists still carry the
  manufacturing notes.
- Countertop 2D (`POST /counter-2d`, `python3 -m cabgen.cli counter`) is that
  same countertop sheet alone, one 11x17 page, laminate or solid surface.
  Front, top, side, and the build-up detail. No cabinet elevations. The 4"
  strips go around the perimeter, including the back edge, and do not cross
  cabinet joints.
- Standalone front elevation: `python3 -m cabgen.cli front <sheet.csv> --out
  <dir>` writes SVG, PDF and an HTML page for the CE pipeline. The sheet is
  the elevation only: no logo and no title block, so the drawing can use the
  page. The HTML links the render PNG and the AR files written next to it.
  The kitchen form has a Front view button. The live wireframe under the form
  uses the page width (`#wire` is `width: 100%; height: auto`).
- Toe kick height is at most 4" (Brook, Nov 9). The kitchen form, the single
  cabinet form, and a `# toe_kick_h=` line all refuse a taller kick. The live
  front view will not draw one. The kick still comes out of the case. Finished
  height stays 33-1/2".
- On Carpenter 2D, the countertop page, the cabinet detail pages, and the
  shop drawing, the identity block is a small box at the bottom right: half
  the old 5.2 in width, and about a quarter of that block's area (2.6 by
  1.83 inches). The cabinets table sits just to its left on the overview.
  The standalone front
  elevation has no block. Nest sheets are unchanged.

Still to do:
1. Cut over: put this tree at `~/Work/cabcad`, keep the `v0.15` tag, push to
   GitHub as the backup.
2. Update `docs/CABCAD-SPEC.md` and `README.md` for v0.15 (the solid-surface
   build-up lines are already current).
3. Check `base_2doors` against a real shop cabinet (shelf position, pull height)
   before the first job.

Future revisions and Brook's notes: see docs/PLANS.md.
