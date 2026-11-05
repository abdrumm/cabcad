# CABCAD-SPEC.md: complete rebuild specification for CabCad

Version: 2026-10-30, 10:15 PM EDT (Oct 30 build: 33-1/2" height, branding, notes, finishes, email drafts, plans page). Owner: Brook (abdrumm), casework PM at Coppinger Exhibits.
Sources: the code on the iMac (`~/Work/cabinet-gen`, `~/Work/omacad`), `~/Work/cabinet-shop-standards.md`, `CABCAD-PLAN.md`, `CABCAD-IDEAS.md`, `cabinet-generator-context.md` and `cabinet-generator-state.md`, plus Brook's decisions saved in assistant memory (Oct 19 to Oct 30, 2026).
Status tags: **BUILT** (in code and working), **DECIDED-NOT-BUILT** (Brook decided it, but the code doesn't do it yet), **PLANNED** (on the roadmap, details not final), **OPEN** (a question still waiting for Brook's answer). **UNKNOWN** means the sources don't say.

---

## 0. How to rebuild with an AI (read this first)

This is the single source of truth for CabCad, Brook's cabinet configurator. Here is how to rebuild it from this file alone. Build a stdlib-only Python 3.12+ package called `cabgen`, using the module layout in section 3. Use every number in sections 5 to 9 exactly as written. They are real values from the working code, not suggestions. Inches are the internal unit everywhere, and fractions are printed to the nearest 1/16". Build in this order: params, parts, model3d, kitchen/run layout, counter, nest_project, cut lists, shop drawing, client sheet, web form plus front-view wireframe, AR export, then the Omacad export and the launcher. Write the tests listed in section 12 as you go, and check them against the worked numbers in section 6.9. Don't "improve" or modernize shop rules. Items tagged DECIDED-NOT-BUILT, PLANNED or OPEN are not in the current app. Rebuild only the BUILT items unless Brook says go. When a rule is missing, ask Brook rather than inventing one. That is a standing rule: "Do not invent the next rule to fill a gap. Ask, or leave it unnamed."

---

## 1. Purpose and users

- **What it is.** CabCad is a rules-based cabinet configurator. It does not try to be a general CAD app. You pick cabinet styles and widths for an upper row and a base row. It then produces carpenter shop drawings, a cut list, whole-project 4x8 nested cut sheets, a client presentation PDF, a 3D model in Omacad, and an AR file for phones.
- **Why.** Brook went from carpenter to running the Coppinger cabinet shop after the experienced person left, and the crew is new. CabCad captures the shop's tribal knowledge as rules, so work keeps moving through staff turnover. Shop drawings for the carpenters matter most.
- **Business goal (Oct 30).** One design gets sold and built. It removes the gates between the simple estimate, waiting for approval, redrawing in CAD, and releasing to the shop. What Rick sells is exactly what the carpenters build. The real end goal is an **automatic estimator** that turns potential sales into a yes.
- **Status of the work.** It's a work-crossover project, done on personal time. The aim is an MVP that wins Coppinger IT and admin buy-in for doing it on work time.
- **Name.** "CabCad" is kept as the internal name (Brook, Oct 30). The Python package is `cabgen`.
- **Users and what each gets:**
  - **Brook** (casework PM; took over from Archie, the previous casework PM, who quit). Brook gets approved estimates and drawings to hand to the carpenters, shop drawings, cut sheets, a purchase list, and a one-page estimate summary for the paper billing folder.
  - **Rick** (sales). Rick gets finish picks, renders, AR, client drawings for approval, a cost estimate, and a "Draft client email" button. He carries a **phone** and has a **Windows** work computer, and probably a laptop too.
  - **Randy and Andrew** (carpenters). They get shop drawings, cut sheets and labels on **paper**, printed 11x17. They like it simple, but get annoyed when any dimension is missing.
  - **Eddie** (purchasing). Eddie gets a clean purchase list with every line flagged **IN STOCK** or **ORDER**. Long-lead items (custom laminate, solid surface, hardware) are ordered at release, so they arrive while the boxes are being built.
  - Others named for future team views: Tully, Eric, Chad, Sue (QuickBooks), Mike (view-only; marketing logo), and Matt (the other PM, who works only in AutoCAD).
- **UI principle.** Keep the UI clean and minimal, with no feature bloat. Occasional options stay hidden or compact until they're needed.

---

## 2. Architecture and how to run it

- **Machines.** The iMac `imacomarchy` (Omarchy Linux, Hyprland) holds the **working copy and the git master**. The laptop `brook-mbp15` ("omarchy") is the mirror. Both use `~/Work/...`.
- **Repos.**
  - `~/Work/cabinet-gen`: package `cabgen`, the generator plus the web form. It's pure Python stdlib, with **no venv** and no pip dependencies, and runs on the system `python3` (Python 3.14.8 on the iMac). External CLIs: `rsvg-convert` (SVG to PDF/PNG; required for the client sheet and the nest PDF) and `qrencode` (optional QR code on the AR panel). If `rsvg-convert` is missing, the single-cabinet drawing falls back to `cairosvg`.
  - `~/Work/omacad`: Omacad, a native parametric 3D CAD app for Omarchy, modelled on Fusion 360. It's a separate project (bjornkindstrom/omacad, version 0.9.9.x). It uses Python 3.14, PySide6 6.12 (Qt6 + OpenGL), manifold3d 3.5.4, shapely 2.2 and python-solvespace 3.0.8 (sketch constraints). It runs from its own **uv venv** at `~/Work/omacad/.venv`, and its launcher is `~/Work/omacad/run.sh`.
  - **Omacad build quirk.** `python-solvespace` has no wheel for Python 3.14, so build it with:
    `CFLAGS="-std=gnu17" CXXFLAGS="-std=gnu++17" uv pip install --python .venv/bin/python python-solvespace`
  - **Omacad repo rules** (`~/Work/omacad/AGENTS.md`):
    - Never push, build or publish without being asked.
    - Stage only source and test files, never `.omacad`, `.pdf` or `video/` files.
    - Every change needs a test plus `CHANGELOG.md` and `SOLUTIONS_LOG.md` entries.
    - Its README is in Swedish; code and the changelog are in English.
- **How CabCad uses Omacad.** cabgen never imports Omacad. `omacad_export.py` writes a JSON payload and runs a builder script under `~/Work/omacad/.venv/bin/python`. The script uses `omacad.model.document.Document` and `omacad.io.exporter.Exporter` to write a `.omacad` project with **one named box body per part, in millimetres** (×25.4). Rounded corners (`shape="qdisc:..."`) become real cylinders joined into the part. `OMACAD_DIR` can be overridden by an environment variable.
  - **Opening a model.** Omacad has no file argument. cabgen does three things:
    1. It seeds `~/.local/share/omacad/session.json` with the model and a camera framed on it.
    2. It adds the model to `recent_files` in `~/.local/share/omacad/settings.json` (max 10).
    3. It starts `run.sh --resume` detached, logging to `~/.local/share/omacad/cabgen-launch.log`.

    If a window is already open, the new process hands `resume` to `~/.local/share/omacad/live.sock` and exits, and the open window reloads. The result is **only ever one Omacad window**. After that, cabgen moves the window to **workspace 3, full screen**, and focuses it.
  - **Gotchas:**
    - Never `pkill -f` or `pgrep -f omacad|app.py|cabgen.cli web`, because the pattern matches the shell that runs it.
    - Don't launch with `WAYLAND_DISPLAY=wayland-0` or `QT_QPA_PLATFORM=xcb` (the iMac session is wayland-1).
    - Detach GUI launches with `setsid nohup ... </dev/null &`.
    - Tkinter is broken on the machine (libtk missing). That's why the UI is a stdlib web form.
- **Web server** (`cabgen/web.py`). It's stdlib `http.server.ThreadingHTTPServer`, with daemon threads and a 30 s socket timeout so idle Chromium preconnects can't freeze it. Every response sends `Cache-Control: no-store`.
  - Start it with `cd ~/Work/cabinet-gen && python3 -m cabgen.cli web --port 8777`. The default host is `127.0.0.1` and the default port is **8777**. `--lan` listens on `0.0.0.0`, and output goes to `--out` (default `out`).
  - **Routes:**
    - `GET /` is the single-cabinet form.
    - `GET /run` is the **CabCad group form** (the main page).
    - `POST /generate` builds a single cabinet.
    - `POST /run` handles "Show in Omacad".
    - `POST /client-sheet` returns the PDF inline.
    - `POST /ar` builds the AR files and shows the AR panel.
    - `POST /cutlist` returns the live cut-list table (HTML) and writes `out/cutlist-live.csv`.
    - `POST /finishes` saves a custom finish (name, code, kind, colour) and returns it as JSON.
    - `POST /email-ar` writes the "Email AR to me" draft folder; `POST /client-email` writes the "Draft client email" folder. Neither sends anything.
    - `GET /files/<name>` serves output files, locked to the out dir.
    - `GET|HEAD /ar/<file>` serves `.glb` and `.usdz`, plus `/ar/view` (phone page) and `/ar/preview.svg`.
  - **Security.** Only loopback clients may use the form and the POST routes. LAN clients get only `/ar/...`, and anything else returns 403 "Only the AR pages are shared on the network."
- **`cabcad` command** (`~/.local/bin/cabcad`, bash, safe to re-run):
  1. It starts the form server if nothing is listening on 8777. It runs detached with `setsid nohup python3 -m cabgen.cli web --port 8777 [--lan]` and logs to `/tmp/gb/cabgen-web.log`. If the server doesn't come up, it sends a `notify-send` error.
  2. If no Omacad window exists, it opens `out/base-run.omacad` (or the newest `out/*.omacad`) through `cabgen.cli open`, or else launches plain Omacad.
  3. It opens the form as a Chromium app window with `omarchy-launch-webapp http://127.0.0.1:8777/run`. The window class `^chrome-127\.0\.0\.1__.*-Default$` has a Hyprland rule that puts it on **workspace 5**.
  4. With two or more monitors, it moves workspace 3 to the first monitor and workspace 5 to the second.
  5. It ends with focus on the form.

  The window rules live in `~/.config/hypr/hyprland.lua` (Omacad: class `^omacad$` goes to workspace 3, full screen). The command tries the Lua-style `hl.dsp.*` dispatchers first, then the classic ones.
- **`cabcad --lan`.** It restarts a local-only server so it listens on the LAN, which lets a phone on the same Wi-Fi open the AR pages. It needs the port opened once: `sudo ufw allow from 192.168.0.0/16 to any port 8777 proto tcp`.
- **`omacad` command.** `~/.local/bin/omacad` runs `exec ~/Work/omacad/run.sh "$@"`. `run.sh` uses `.venv/bin/python app.py` if the venv exists, otherwise `python3`.
- **Menu entries.** `~/.local/share/applications/cabcad.desktop` (Name=CabCad, Exec=`~/.local/bin/cabcad`, Path=`~/Work/cabinet-gen`, Icon=cabcad) and `omacad.desktop`. Brook launches CabCad from the Omarchy menu.
- **CLI** (`python3 -m cabgen.cli ...`, run from `~/Work/cabinet-gen`):
  - `styles` lists the styles.
  - `generate --style --name --width --height --depth --counter-depth --out [--with-omacad] [--no-show]` builds single-cabinet drawings.
  - `omacad ...` writes the 3D model only. `open --name --out` shows a model in Omacad.
  - `kitchen <sheet.csv> [--name] [--out] [--no-show] [--kerf] [--sheet-w] [--sheet-l]` builds a whole job from a CSV.
  - `client <sheet.csv> [--out out/client-sheet] [--name] [--stem]` builds the client sheet.
  - `ar <sheet.csv> [--out out/ar] [--name] [--title]` builds the AR files.
  - `render <sheet.csv> [--out out/render] [--name] [--stem]` writes the client render (PNG 1800×1200, 150 dpi).
  - `web [--host] [--lan] [--port 8777] [--out]` starts the form server.
- **Tests.** Run `cd ~/Work/cabinet-gen && ~/Work/omacad/.venv/bin/python -m pytest -q` (about 35 s). There are **97 tests in 16 files**:
  - `test_ar_export` 5, `test_ar_web` 7, `test_base_height` 3, `test_branding` 4, `test_client_sheet` 3, `test_counter` 9, `test_defaults_and_cutlist` 2, `test_drafts` 4, `test_finishes` 4, `test_form_wire` 4, `test_kitchen` 14, `test_nest_project` 8, `test_notes` 5, `test_plans_page` 2, `test_sink_and_microwave` 12, `test_uppers` 11.
  - Oct 30 (late) run on the iMac: **97 passed**.
  - pytest is installed in the Omacad venv (Oct 30, `cd ~/Work/omacad && uv pip install --python .venv/bin/python pytest`; the venv has no pip). The system `python3` still has no pytest.
- **Layout checker.** `python3 tools/check_svg.py out/<name>-drawing.svg` reports elements off the page and overlapping text labels. Run it after every `draw.py` change.

---

## 3. Module layout (`~/Work/cabinet-gen`)

- `cabgen/params.py`: the `Params` dataclass (one cabinet, inches), style presets, shop constants, default widths and the single-form field list.
- `cabgen/parts.py`: `build_parts(Params) -> (list[Part], Layout)`. It produces the part schedule plus the vertical front layout (drawer bands, rails, door zone, sink board). `Part` has: name, qty, material, thk, width (across the grain), length (along the grain), banding, laminate, notes.
- `cabgen/model3d.py`: places every part as a `Box(name, pos, size, material, join, shape)` and every drilled hole as a `HoleSpec(diameter, depth, origin, normal)`. Coordinates are **X = width from the case's left face, Y = depth from the case front (+Y toward the wall), Z = up from the floor**.
- `cabgen/kitchen.py`: CSV jobs, row layout, run-end and filler rules, the group-form parser, and `write_kitchen`.
- `cabgen/counter.py`: the countertop over the base run (laminate or solid surface).
- `cabgen/nest_project.py`: whole-project guillotine nesting, labels, the nest PDF and the cut lists. `cabgen/nesting.py` is the older single-cabinet nest.
- `cabgen/cutlist.py`: CSV, markdown and table-saw text.
- `cabgen/draw.py`: the 11x17 single-cabinet shop drawing and cut-list overflow sheet. `cabgen/svg.py` is a tiny SVG writer.
- `cabgen/units.py`: `fmt_in` (for example `27"`, `13 15/16"`, `3/4"`, rounded to 1/16) and `parse_in`.
- `cabgen/client_sheet.py`: the client presentation PDF, its title block (`title_block`) and the finish palette (`palette_for`, `pal`, `role_of`).
- `cabgen/branding.py`: Coppinger name, address, phone, navy `#263460`, and the logo as SVG (`logo_svg`, `corner_mark`) or a data URI (`logo_data_uri`).
- `cabgen/notes.py`: the condensed, context-aware notes: a data list of `Note(id, audience, title, text, when)`; `select(facts, "shop"|"client")`.
- `cabgen/finishes.py`: the finish catalog (`assets/finishes/catalog.json`), custom finishes (`assets/finishes/custom.json`), picks, palette and AR material roles.
- `cabgen/render.py`: the client render still (PNG).
- `cabgen/drafts.py`: "Email AR to me" and "Draft client email" draft folders (.eml, mailto, copy-paste text). Never sends. Recipients in `config/email.json`.
- `cabgen/ar_export.py`: GLB and USDZ writer. `cabgen/ar_web.py`: AR panel, phone page and QR code.
- `cabgen/omacad_export.py`: the `.omacad` writer and the window control.
- `cabgen/web.py`: the web form, the front-view wireframe and the routes. `cabgen/cli.py`: argparse.
- `jobs/one-cabinet.csv`, `jobs/sample-kitchen.csv`, `jobs/upper-styles.csv`: example jobs. `briefs/ar-export.md` is the AR spec. `tools/check_svg.py`. `tools/cabcad-sync-check` and `tools/systemd/` (section 13). `assets/branding/coppinger/` (placeholder logo, roadmap step 5). `assets/finishes/` (catalog, custom list, CC0 textures, README). `config/email.json` (draft recipients). `tools/plans-page` and `tools/cabcad-plans` (plans dashboard, 9.10). `docs/CABCAD-SPEC.md` (this file).
- `.gitignore`: `out/ __pycache__/ *.pyc .venv/ .pytest_cache/ *.bak*`.
- Docs that live **outside** the repo, in `~/Work/`: `cabinet-shop-standards.md` (the live rules), `CABCAD-PLAN.md`, `CABCAD-IDEAS.md`, `CABCAD-SPEC.md` (this file), `cabinet-generator-context.md`, `cabinet-generator-state.md`.

---

## 4. Inputs: every field, default and unit (all inches)

### 4.1 CabCad group form (`/run`, the main page). BUILT
- **Header bar** with the brand "CabCad · cabinet group" and five buttons:
  - **Show in Omacad** (POST /run): writes everything and opens the model.
  - **Client sheet (PDF)** (POST /client-sheet, new tab).
  - **AR view** (POST /ar).
  - **Email AR to me** (POST /email-ar) and **Draft client email** (POST /client-email). Draft only; see 9.9.
- **Job line** (Oct 30): Job, Client, Job no., Rev (default "A"). They go on the client title block, the render and the email drafts (`job`, `client`, `job_no`, `rev`; whitespace collapsed, max 80 characters).
- **Uppers row** (top) and **Base cabinets row** (below), matching how they sit on the wall.
  - Each row starts with **1 cabinet**. 8 tiles are pre-drawn (`SHOWN_COLUMNS = 8`), and **+** adds more past 8 with **no limit** (the old 8-cabinet cap was removed Oct 27). "Remove last upper/base" and a per-tile delete are there too.
  - First tile on a fresh page: the base is style `3drawer`, width **18**; the upper is style `upper`, width **30** (from `DEFAULT_WIDTHS`; the old 27/27 is gone, Oct 30). Form field names: `bw#`/`bs#`/`bd#`/`bh#` for base width, style, drawer and handle; `uw#`/`us#`/`uh#` for upper width, style and handle.
  - **Upper offset from the left wall** (`uoff`): default 0, step 1/16, can't be negative. The base offset `boff` is hidden and fixed at 0, because the base filler replaced the old base offset.
  - **Row totals** are read-only. The base total includes the filler but not the offset.
  - **Drag and drop.** Drag a tile by its header label (U1, B1 ...) to reorder it within its own row. It uses pointer events and works on tiles added past the 8 drawn ones. The goal is that clients can rearrange cabinets.
- **Each tile** has:
  - **Style** as segmented icon buttons, not a dropdown:
    - Bases: `3drawer` ("3 drawers"), `base1` ("1 door"), `base` ("1 drawer over 2 doors"), `sink` ("Sink: false drawer front over 2 doors").
    - Uppers: `upper` ("2 doors"), `upper1` ("1 door"), `open` ("Open shelves"), `microwave` ("Microwave shelf, 2 doors above").
  - **Width** (in).
  - **Drawer height** for `base` and `sink` only: choices **4, 5, 6, 7, 8**, default **6**. The 4 to 8 range is a placeholder (OPEN: check historical jobs); 6 is confirmed.
  - **Handle L/R** for `upper1` and `base1`, default R. The handle goes on the picked side and the hinges on the other. The tile icon mirrors when L is picked. On an upper wider than 24" the control hides, because that cabinet is built as a pair. A 1-door base keeps the control at any width.
- **Default width when a tile is added, or its style is switched while the width box is empty or still holds the old style's default** (a typed width is never overwritten): upper 30, upper1 18, open 24, microwave 30, 3drawer 18, base1 18, base 30, sink 30. **One place:** `params.DEFAULT_WIDTHS`; the CLI style presets take their width from it too (`FORM_STYLE_KEYS`, `default_width(style)`), so the CLI and the form always agree (CONFIRMED Brook, Oct 30; `test_defaults_and_cutlist`).
- **Minimum widths:** 12 for everything, 9 for the 1-door upper.
- **Base run ends** (`walls`, radios): `0` (No wall), `left` (default), `right`, `both`.
  - With **both**: **filler width** `1`, `2` or `3` (default 1; 1 is typical, 3 is the most) and **filler side** left or right (default right).
- **Countertop** (`counter`): `laminate` (default), `solid` (solid surface) or `none`.
  - **Left wall side splash** and **Right wall side splash**: yes (default) or no. They only show at wall ends and are hidden when the counter is none.
- **Finishes** (Oct 30): three pickers, **Doors and fronts**, **Box** (laminate finishes) and **Countertop** (laminate or solid surface, filtered by the countertop choice; off when the counter is none), each with a colour swatch. "Drawing colours" (blank) keeps the old palette. **Add custom finish** (name, code, laminate/solid surface, colour) saves to `assets/finishes/custom.json` and joins the dropdowns at once (see 9.8).
- **Front view**: a live wireframe below the options (see section 9.6). It is painted in the picked finish colours.
- **Cut list** (Oct 30): a collapsible section that rebuilds live (debounced POST /cutlist) from the same parts code as the shop output, grouped by cabinet ("B1 · name · 24" wide"). It always shows the widths typed on the form.
- **Info lines** show the end-rule sentence and the footer note about the 4" backsplash and the 1" open-end overhang.
- **Validation errors** are shown in plain words: a row with a gap; an empty width; under the minimum width; an unknown style; a drawer outside 4 to 8; a filler other than 1, 2 or 3; an offset past the wall; "add at least one cabinet".

### 4.2 Kitchen CSV (`kitchen`, `client`, `ar` commands). BUILT
- **Settings** are `# key=value` lines:
  - Numbers: `upper_bottom` (default **54**), `upper_offset`, `base_offset`, `filler`, `sheet_w` (48), `sheet_l` (96), `kerf` (0.1875).
  - Text: `base_walls` (0/left/right/both), `filler_side`, `counter` (laminate/solid/none; also accepts "solid surface", "corian", "lam", "no"), `splash_left`, `splash_right`.
  - Job text (Oct 30, `kitchen.JOB_TEXT_KEYS`): `job`, `client`, `job_no`, `rev`, `finish_fronts`, `finish_box`, `finish_counter` (finish ids from the catalog).
- **Columns:**
  - Required: `name`, `style`, `width`.
  - Optional: `run` (base/lower/floor or upper/wall; default base), `height`, `depth`, `x`, `z`, `gap_after` (base filler only; an error on uppers), `drawer_front_h`, `handle` (l/r/left/right; default right), `left`, `right` (wall/open/reveal).
- **Style aliases:**
  - base / base_1drawer_2doors / 1d2d / 1drawer
  - base1 / base_1door
  - 3drawer / 3drawers / base_3drawers
  - sink / base_sink / sink_base
  - upper / upper_2doors / 2door
  - upper1 / upper_1door / 1door
  - open / upper_open / shelves
  - microwave / upper_microwave / mw

  `upper_drawer` is rejected with "uppers never have drawers".
- Blank height and depth keep the style's values. A blank base height becomes `base_case_height(counter)`: 32 under a laminate or solid top, 33.5 with none. Duplicate names get `-2`, `-3` added.

### 4.3 Single-cabinet form (`/`) and `Params` fields. BUILT (legacy page; the group form is the main UI)
- **Identity:** `style`, `name`.
- **Outer size:** `width` (case outer width), `height` (overall height, floor to top of case; see 6.1), `depth` (finished case depth, front of the sides to the back face of the back). These take the style preset when left blank.
- **Materials:** `carcass_thk` 0.75, `back_thk` 0.5, `drawer_box_thk` 0.75, `drawer_box_bottom_thk` 0.25, `edge_banding` "0.5 mm".
- **Per-cabinet counter (legacy; the job counter in counter.py replaces it):**
  - `has_counter` False ("countertop removed for now").
  - `counter_depth` 25, `counter_thk` 0.5, `counter_backer_thk` 1.0.
  - `counter_overhang_left/right` 1.0, `counter_front_overhang` 1.5.
  - `backsplash_h` 4.0, `backsplash_left` True, `backsplash_back` True.
  - `counter_build_style` "edge_strips" (or "mdf_deck").
- **Fronts:** `door_overhang` 0.5, `door_gap` 0.125 (total gap between doors), `door_overhang_bottom` 0, `drawer_front_h` (from the style; 6), `drawer_gap` 0.125.
- **Anatomy:** `stretcher_w` 4.0, `toe_kick_h` 4.0, `toe_kick_recess` 3.0, `back_style` "applied" (or "dado").
- **Drawer box:**
  - `slide_clearance` 0.5 per side.
  - `drawer_box_h` 4.0 (used by the 3D model) and `drawer_box_short` 2.0 (the cut list uses front minus 2, min 2).
  - `drawer_box_above_rail` 0.25.
  - `drawer_groove` 0.25, `drawer_bottom_up` 0.5, `drawer_dado_w` 0.25, `drawer_dado_d` 0.25.
- **Shelf (current code):**
  - `shelf_z` 16, `shelf_side_gap` 0.125, `shelf_setback` 0.25.
  - `shelf_pin_dia` 0.25, `shelf_pin_depth` 0.375.
  - `shelf_pin_rows` (10, 12, 14, 16, 18, 20) off the floor; `shelf_pin_y` (4.5, 18) from the front.
- **Pulls:** `has_pulls` True, `pull_span` 4.0, `pull_hole_dia` 0.2, `pull_from_top` 2.0, `pull_off_center` 2.0.
- **Site:** `left_side` "wall", `right_side` "open" (wall/open/reveal), `spacer_gap` 1.0, `has_spacer` False, `spacer_side` "".
- **Laminate:** `laminate` True, `laminate_right_side` True.
- **Sheet goods:** `sheet_w` 48, `sheet_h` 96, `kerf` 0.1875.
- **Style-driven fields:** `has_counter`, `has_toe_kick`, `drawers`, `doors`, `has_shelf`, `open_shelves`, `finished_interior`, `mw_opening_h`, `sink`, `handle_side` (default "right").
- **Form coercion.** "true/on/yes" become True, and "false/off/no/''" become False. Numbers are parsed as int, then float.

---

## 5. Styles (presets in `params.py`). BUILT

| Key (code) | Form key | Label | Default W (CLI = form) | H (case) | D | Drawers | Doors | Other |
|---|---|---|---|---|---|---|---|---|
| base_1drawer_2doors | base | Base, 1 drawer over 2 doors | 30 | 32 | 23.5 | 1 (6" front) | 2 | toe kick, adjustable shelf |
| base_1door | base1 | Base, 1 door | 18 | 32 | 23.5 | 0 | 1 | toe kick, adjustable shelf, handle L/R (default R) |
| base_3drawers | 3drawer | Base, 3 drawers | 18 | 32 | 23.5 | 3 (split evenly) | 0 | toe kick |
| base_sink | sink | Base, sink | 30 | 32 | 23.5 | 1 FALSE front (6") | 2 | toe kick, no shelf, `sink=True` |
| upper_2doors | upper | Wall upper, 2 doors | 30 | 30 | 12 | 0 | 2 | no shelf (as built) |
| upper_1door | upper1 | Wall upper, 1 door | 18 | 30 | 12 | 0 | 1 | handle L/R, min width 9 |
| upper_open | open | Wall upper, open shelves | 24 | 30 | 12 | 0 | 0 | 2 adjustable shelves, finished interior |
| upper_microwave | microwave | Wall upper, microwave shelf, 2 doors above | 30 | 30 | 12 | 0 | 2 | 17-1/4" opening, finished interior |

Base H is the case under a 1-1/2" countertop (33.5 with no countertop); see 6.1. Widths are unified in `DEFAULT_WIDTHS` (Oct 30; the old CLI presets 27/27/27/30 are gone).

- `STYLE_UPPER_1D2D = "upper_1drawer_2doors"` still exists as a constant, but uppers **never have drawers** (Brook, Oct 23). It has no preset and the CSV rejects it.
- **Upper dimensions** were placeholders until Brook brings shop plans and CAD from work. The 12" upper depth and everything about the microwave are CONFIRMED.
- **Not styles yet** (they need a real model first): vanity, ADA vanity, trash, the 1-drawer 1-door base, pantry and drawer bank. PLANNED/OPEN.

---

## 6. Construction rules and shop standards

### 6.1 Heights and depths. BUILT
- **Base (CONFIRMED Brook, Oct 30; supersedes the 35" top and the ADA option):** the **total finished height including the countertop is 33-1/2" on every job**. The case = 33.5 − the countertop thickness, and the toe kick stays 4".
  - `params.FINISHED_COUNTER_TOP = 33.5`, `COUNTER_THICKNESS = {laminate: 1.5, solid: 1.5, none: 0}`, `base_case_height(kind)`, `BASE_CASE_H = 32`.
  - Laminate or solid surface (both 1-1/2" builds): **case 32"** (4" kick + 28" box), top at 33-1/2". No countertop: case 33-1/2".
  - 33-1/2" is under the ADA 34" maximum (2010 ADA 902.3 / 606.3), so no separate ADA option is needed (it was dropped).
  - Applies to the cut lists, 3D, AR, client sheet, front view (`_wire_data` carries an `info["none"]` height for the no-counter case) and the standards doc (`cabinet-shop-standards.md`, overall height row and line 177; backup `cabinet-shop-standards.md.bak-20261030-height`).
- **Base depth:** 23-1/2" finished. That's the gables at 23" plus the 1/2" applied back. Counter depth is **25"** (1-1/2" front overhang past the case).
  - An older standards note says "base depth is always counter depth minus 1"" (24"). Superseded by the code's 23.5. OPEN only if Brook objects.
- **Uppers:** **30" tall, 12" deep** (11-1/2" gables + 1/2" back). Bottoms hang at **54"** off the floor (`upper_bottom`).
- **Upper back placement:** uppers' backs sit on the same wall as the deepest base, so `upper.y = deepest base depth − upper depth`.
- **Runs:** cabinets in a run sit **tight side by side**, with no gap and no joining hardware, and each is screwed to the wall. The generator packs them touching, left to right, starting at the row offset.

### 6.2 Materials. BUILT
- **Carcass:** 3/4" melamine. **Back:** 1/2" melamine.
- **Fronts** (doors, drawer fronts, false front): 3/4" melamine.
- **Drawer boxes:** 3/4" melamine sides, fronts and backs, with a **1/4" bottom labelled `1/4" melamine`** (`parts.MAT_1_4`; label fixed Oct 30, CONFIRMED Brook).
- **Laminate (Formica), light oak in the first job:** on **reveal faces only** (the visible, open side). Doors and fronts get laminate on both faces and all edges.
  - **Spray method:** cut the laminate to the final size **+1"** (1/2" per side), contact-adhesive both surfaces, trim with a palm router, sand the unfinished edges, and hand-file the exposed edges.
  - **Waterfall order:** bottom face, then sides/edges, then top. Exceptions are rare and must be noted on the drawing.
- **Edge banding:** 0.5 to 2 mm, and it **never changes any stated part dimension**.
- **Units and formatting:** keep cut-list dimensions in the simplest fractions (1/16").

### 6.3 Case anatomy. BUILT
- **Gables (sides):** run to the floor and are **notched at the front bottom for the toe kick**, 3" deep × 4" tall on bases.
  - Size: width = case top height, length = gable depth.
  - Banding: front edge and bottom edge (toe-kick side).
- **Back:** default **applied**, meaning it sits behind the sides at full case width, from the floor to the top of the sides. The `dado` option makes it inside width × (case height − 3/4).
- **Bottom plate:** captured between the gables, flush front and back, with the front edge banded. On bases it sits on the toe-kick stiles.
- **Base top:** two **flat stiles, 4" front to back**, at inside width.
  - **Top stile, front:** flush with the top and front.
  - **Top stile, back:** flush with the top and back.
  - "Stretchers lie flat; the 4" is not a face height."
- **Toe kick:**
  - **Toe kick plate:** inside width × 4", recessed **3"** from the case front. Banding: top edge and ends.
  - **Toe kick stile, back:** at the back, under the bottom.
- **Uppers:** gables run full height. The **top plate and bottom plate are each one full-depth piece cut to the inside width**, captured between the sides. Front edges are banded.
- **Construction:** captured, so the stated outer dimensions are the finished outside dimensions.

### 6.4 Fronts: overlay, reveals, gaps. BUILT
- **Overlay:** fronts cover **1/2"** of each 3/4" edge. That leaves a **1/4" reveal** around the case perimeter, and the fronts stay inside the case outline.
  - Front width = case width − 2 × 1/4.
  - Door width (pair) = (front width − 1/8) / 2.
- **Gaps:** **1/8"** between the two doors (total), and **1/8"** between drawer fronts and between a drawer and the doors.
- **Opening:** from (case bottom + 1/4) to (case top − 1/4). The case bottom is the top of the toe kick on bases, or 0 on uppers.
- **Front stack (top down):** drawer front(s) start at the top of the opening. Then a 1/8" gap, with a **flat 3/4" drawer stile (rail) centred on that gap**, so each front laps the stile's 3/4" edge by 5/16". Then the doors fill the rest of the opening.
  - **3-drawer base:** the 3 fronts split the opening evenly, with 1/8" gaps, and get 2 stiles.
  - **1-drawer base:** drawer height comes from the form (default 6).
- **Drawer stile:** inside width × 4" deep, flat, front edge banded, one per rail.
- **Doors and fronts:** all four edges banded (both faces).

### 6.5 Hardware and holes. BUILT (positions are "for now" unless marked confirmed)
- **Base door pulls:** 4" wire pull, vertical. Holes are **2" and 6" down from the top of the door**, **2" off the case centreline** on each door of a pair. Hole diameter 0.2. A single door keeps that height and moves the holes to **2" in from the handle edge** (the same side rule as a 1-door upper; `handle_side`, default right). The hinges go on the other side.
- **Drawer pulls:** 4" wire pull, centred on the case, holes ±2" off the centre at the front's mid-height.
- **Upper door pulls** (Brook, Oct 24; stock wire pull, two screws from the back, **4" c-c**, vertical):
  - Every number is to a hole centre: bottom hole **1-1/2" up** from the door bottom, top hole **5-1/2" up**, both **2" from the handle (opening) edge**.
  - A pair opens at the meeting edges. A 1-door opens at its handle side.
  - Drill **3/16" through**; the screw size is a placeholder.
  - Applies to the 2-door, 1-door and microwave uppers.
- **1-door hinges:** two **35 mm cup** holes, **1/2" deep**, cup centre **22.5 mm** from the hinge edge, **3" from the top and the bottom**, on the side opposite the handle. The model shows a hinge block on the gable. Hinge brand, overlay and the count on tall doors are OPEN.
- **Shelf pins (current code):**
  - Base `has_shelf`: 1/4" holes, 3/8" deep, inside face only, columns 4-1/2" and 18" from the front, rows at 10, 12, 14, 16, 18 and 20" off the floor. The shelf sits on the 16" row.
  - Open upper: columns 2" from the front and 2" from the back of the gable, with rows at each shelf position and 2" above and below it.
  - These are **to be replaced by the new standard** in 6.10.
- **Carpenters use a jig for door hinges.** Brook may build jigs for pulls. Long-term: model hinges, pulls and slides exactly to get hole locations, and eventually **CNC code** so assemblers never need a tape measure. PLANNED.

### 6.6 Drawer boxes. BUILT (assumptions OPEN)
- **Outer width** = inside width − 2 × 1/2 slide clearance (min 8). **Depth** = gable depth − 1 (22" in a 23" side, which leaves 1" for the slide; min 8).
- **Height:** box height = **front height − 2** (min 2), in the cut list **and the 3D model** (`p.drawer_box_height(...)`; the 3D model followed the fixed 4" until Oct 30, so 3-drawer bases now match the cut list). `drawer_box_h` 4.0 is legacy. Brook will give more drawer-box size rules later; the 3-drawer box height rule itself is kept as is pending his explanation.
- **Box:** sides 3/4", front and back captured between the sides, bottom 1/4" in a 1/4" groove, 1/2" up from the bottom of the sides. The bottom is inside size + 2 × groove. The box sits 1/4" above the stile below it.

### 6.7 Style-specific rules
- **1 drawer over 2 doors base.** BUILT. A 6" drawer front is typical. It has one adjustable shelf: inside width − 2 × 1/8 wide, gable depth − 1/4 deep, front edge banded.
- **1-door base.** BUILT. One full-height door, no drawer, toe kick, one adjustable shelf. Default 18" wide. Door label `B#-D`, name "Door, handle L|R". The pull is the base door pull (2" and 6" down from the top) set 2" in from the handle edge. The client sheet and the front-view wireframe draw a dashed swing V, point on the hinge side. The 24" single-door limit is for wall uppers only.
- **3-drawer base.** BUILT. Equal fronts, 2 drawer stiles, no doors, no shelf.
- **Sink base** (Brook, Oct 27). BUILT. Built like the 1-drawer base, with these differences:
  - **False drawer front:** same size, reveals and gaps as the real one, **no pull, no holes**. Label `B#-FF`.
  - **No drawer box, no slides, no shelf, no shelf-pin holes.**
  - **Sink front board:** a vertical 3/4" board between the gables, flush with their fronts, behind the false front. The false front screws to it from behind. It runs **from the case top down to 1/2" below the top edge of the doors** (`SINK_FRONT_BOARD_BELOW_DOOR_TOP = 0.5`, **OPEN: Brook said "I think"**). The doors close against it. It replaces the front top stile and the drawer stile. Bottom edge banded. Label `B#-FB`.
  - **Back top stile stands vertical, 4" tall** (`SINK_BACK_STILE_H = 4`), flush with the top of the sides. Label `B#-TSB`.
  - Normal bottom; doors and gaps the same as `base`. Default width 30 "for now" (sink bases are commonly 30" to 36"; 33"/36" for a double bowl).
  - OPEN: whether the back stile needs a **plumbing notch**, and whether the bottom gets a finished or sealed face for leaks.
- **1-door upper.** BUILT. Default 18" wide, typical 9" to 24", accepted down to 9". Door label `U#-D`, with the name "Door, handle L|R". The client sheet draws a dashed swing V, with the point on the hinge side.
- **Open-shelf upper.** BUILT (placeholder):
  - No doors, 2 adjustable 3/4" shelves spaced evenly in the clear height.
  - Shelves: 1/8" side gap, 1/4" setback, on 1/4" pins.
  - Finished interior: the inside faces show and front edges are banded. Labels `U#-OS1..`.
  - OPEN: shelf count, fixed vs adjustable, interior finish (melamine vs laminate).
- **Microwave upper** (CONFIRMED Oct 27). BUILT:
  - **30" wide × 30" tall × 12" deep**, so the tops line up with the other uppers.
  - **17-1/4" clear opening** above the bottom. Then a **fixed 3/4" divider** (`U#-MD`), the floor of a small 2-door cabinet: 12" overall above the opening, doors about 11-1/2" tall, lapping the divider.
  - The opening interior is finished.
  - **Microwave shelf** (the bottom board, `U#-MS`) is the only part that leaves the 12" box. It measures **16" from the front face of the 1/2" back to its front edge** (`MICROWAVE_SHELF_CALLED_DEPTH = 16`), so it's **16-1/2" overall** and **projects 4-1/2"** past the gables.
  - **Front corners rounded to a 2" radius** (`MICROWAVE_SHELF_CORNER_R = 2`). The shelf is captured between the gables, fixed, glued and screwed, with the front edge and corners banded.
  - The rounded corners are modelled as true cylinders in Omacad, as fine steps in the client views and AR, and as a rounded outline over a dashed packing rectangle on the nest sheet, marked `2" R front corners`.
  - OPEN: shelf width (between the gables, or full width with the gables sitting on it), the opening height for Brook's microwaves, venting, a trim kit, and whether it ever drops lower than the other uppers.
- **Over-sink 2-door upper** can be shorter (about 6", may vary), with its top flush to the other uppers. DECIDED-NOT-BUILT. It should stay hidden or compact in the UI.

### 6.8 Run ends, fillers and site rules. BUILT
- **No wall:** both ends open, and the counter overhangs **1"** at each end.
- **Left (or right) wall:** the counter is flush at the wall, and the open end overhangs 1".
- **Both walls:** the walls are fixed. **Always add a filler on ONE side only**, left or right (default right), so the case isn't pinched. Filler options are **1, 2 or 3"** (1 typical). The counter is flush at both walls and crosses the filler to reach the wall.
- **Filler details:** one board on that end only, never on both ends and never on an open end. **Uppers never get a filler** (the CSV rejects `gap_after` on uppers).
- **Filler parts:** "Spacer board (wall side)", 3/4" × filler width × toe-kick height, label `SP`. Brook wants to type the filler width directly and has asked for expert best-practice recommendations (OPEN).
- **Side assignment.** Inside a run, the buried sides are "wall". The ends follow the walls setting. `laminate_right_side` is True only when the right end isn't a wall.
- **Site rules (from the standards):**
  - Always measure the real space and revisit to sanity-check the opening, since framing is out of square.
  - Use a 1" spacer at the wall side, or both sides when one is open.
  - Worked example: a **44" opening becomes a 43" case** with a 44" counter and a front spacer board. The spacer is nuanced, so call it out on the drawing.
- **Not decided** (the tool doesn't guess): how an upper run meets a wall (other than "no filler ever"), and edge cases for fillers between two out-of-spec walls. OPEN.

### 6.9 Worked numbers (the code's output; use these to verify a rebuild)
Bases are under a countertop (32" case, Oct 30).
- **Base, 1 drawer over 2 doors, 30 wide:**
  - Gables 2× 32 × 23; bottom 28-1/2 × 23.
  - Back 30 × 32 × 1/2.
  - Top stile front, top stile back, drawer stile, toe-kick plate and toe-kick back: each 28-1/2 × 4.
  - Doors 2× 14-11/16 × 21-3/8 (z 4.25 to 25.625); drawer front 29-1/2 × 6.
  - Drawer box: sides 2× 4 × 22, front/back 2× 4 × 26, bottom 26-1/2 × 21 × 1/4 (`1/4" melamine`).
  - Shelf 28-1/4 × 22-3/4. Opening z 4.25 to 31.75 (27-1/2).
- **Base, 3 drawers, 18 wide:** 3 fronts 17-1/2 × 9-1/16, 2 drawer stiles, box sides 6× 7-1/16 × 22, front/back 6× 7-1/16 × 14, bottoms 3× 14-1/2 × 21. The 3D boxes are 7-1/16 tall too.
- **Sink base, 30 wide:** sink front board 28-1/2 × 6-7/8 (z 25.125 to 32), back stile 28-1/2 × 4, false front 29-1/2 × 6, doors 14-11/16 × 21-3/8, no drawer box, no shelf, no drawer stile.
- With **no countertop** the bases are 33-1/2 (the pre-Oct 30 numbers: gables 33-1/2 × 23, doors 22-7/8, 3-drawer fronts 9-9/16).
- **Upper, 2 doors, 30 wide:** gables 30 × 11-1/2; top and bottom 28-1/2 × 11-1/2; back 30 × 30; doors 2× 14-11/16 × 29-1/2.
- **Upper, 1 door, 18 wide:** door 17-1/2 × 29-1/2.
- **Open upper, 24 wide:** 2 shelves 22-1/4 × 11-1/4.
- **Microwave, 30 wide:** shelf 28-1/2 × 16; divider 28-1/2 × 11-1/2; doors 2× 14-11/16 × 11-1/2.
- The first teaching job ("base-27": 27" case, 6" drawer over 2 doors, 1/2" Corian on a 1" backer, light-oak laminate on the reveal faces) is historical. It came from Brook's Fusion STEP file `27 in 1 Drawer 2 doors.step`.

### 6.10 Shelf-pin standard (Brook, Oct 28 to 30). DECIDED-NOT-BUILT
- **1/4" pins** (1/4" holes), **3" on centre** vertically.
- Two rows per gable: **1-1/2" from the front** and **1-1/2" from the back** edge.
- The band runs from **8" above the bottom** to **8" below the top** of the interior.
- Drill on the inside faces of both gables, mirrored so the shelves sit level.
- It replaces the current rows (10" to 20" at 2", columns 4-1/2" and 18") and the open-upper "2" either side" layout.
- **Which styles get it:** OPEN. Not the sink base (confirmed).
- It needs Brook's go to build in the code and the drawings.

### 6.11 Countertops (`counter.py`; Brook, Oct 24 to 27). BUILT
- **Scope.** One counter (`CT1`) per job over the base run. None if there are no bases or the counter is `none`.
- **Extent:** from the first base's left edge minus the left filler (minus 1" if that end is open) to the last base's right edge plus the right filler (plus 1" if open).
- **Depth:** from the front (−1-1/2" overhang) to the back of the deepest base. The bottom of the counter is at the top of the tallest base.
- **Common to both kinds:**
  - **Front edge 1-1/2"**. **Backsplash 4"** for the full length, including overhangs.
  - **Side splash 4"** at every wall end, on automatically; the form can turn one off. The side splash runs from the counter front back to the backsplash and butts it (to confirm).
  - Open end: 1" overhang with a finished edge. Wall end: flush.
- **Laminate (default):**
  - **3/4" plywood top**.
  - **3/4" plywood build-up strips, 4" wide**, glued and stapled underneath: at the front (full length), at each end, and **centred on every cabinet joint** so installers screw up into them. Front edge = 3/4 + 3/4 = 1-1/2.
  - A filler end gets one end strip at least 4" wide (filler + 1-1/2 when wider).
  - **No strip along the back wall** and **no backer (balance) sheet** (both to confirm).
  - **Laminate order:** side edges, front edge, top, then the splash's exposed edges, then the splash faces. Every exposed splash edge gets laminate.
  - Splashes are 3/4" plywood, laminated.
  - The laminate is a **sq-ft takeoff +10%** (to confirm), not nested. Laminate sheets run to 144" (5×12).
- **Solid surface (Corian):**
  - **1/2" top**. An underside rabbet, **1/2" wide × 1/4" deep** (Brook said 1/2 × 1/2; modelled 1/2 × 1/4 to leave a 1/4" lip; to confirm), at the front and finished sides takes a **1-1/4" solid-surface edge strip, epoxied**. 1/4 lip + 1-1/4 strip = 1-1/2" reveal.
  - Ease the revealed edges with a 1/8" round-over and sand flat. The front strip runs the full length, and the side strips butt behind it.
  - **1" plywood stiffener strips, 4" wide** (width to confirm): at the front (behind the edge strip), along the back wall, at the ends, and centred on cabinet joints. Overall 1-1/2". (An older note said a 1" MDF backer; Brook now says 1" plywood.)
  - Splashes are 1/2" solid surface. Solid surface is **listed, not nested**; the plywood stiffeners are nested.
  - Also a shop rule (Oct 26): **1/2" solid-surface tops get a 1" MDF or wood substrate siliconed underneath**, for 1-1/2" height and something to screw into.
- **Seams (Brook, Oct 27): none automatic.** The top, the front build-up and the backsplash are each **one piece the length of the run** everywhere (Omacad, client sheet, AR, front view, cut list, nest).
  - A piece longer than its stock sheet (96" plywood; 144" solid surface or laminate) is flagged **"LONGER THAN STOCK SHEET - seam TBD"** in its note. It's listed under "Not nested" in the nested cut list and on the nest summary page, in red, and isn't drawn on any sheet. Brook decides the seam.
- **Seam rules, kept for later (code exists but is off):**
  - Seam only when the run is too long. Put the seam on a cabinet joint, with pieces about equal.
  - **Brook's laminate seam:** a 6" strip of 3/4" ply centred on the seam (3" per piece, labels `CT1-BUJnA/B`), dogbone pockets **1/2" deep** across the seam (one per ~12", at least 2), adhesive, and dogbone clamps at install. Laminate itself seams only past 144", at least 6" from the ply seam.
  - **Solid surface:** a hard seam with the maker's adhesive over the joint stiffener; no dogbones.
  - Keep seams off sink, cooktop and dishwasher openings (2" to 3" from a cutout) and away from inside corners (1-1/2"). Sources: WOODWEB, Customcraft, Corian K-25288 and K-25705.
- **Output:** `<job>-counter.md` (parts table, laminate takeoff by order, assumptions list), counter parts in the cut list and the nest (labels `CT1-TOP`, `CT1-BUF`, `CT1-BUL/R/Jn`, `CT1-STF/STB/STL/STR/STJn`, `CT1-EF/EL/ER`, `CT1-BS`, `CT1-SSL/SSR`, laminate `CT1-LSL/LSR/LF/LT/LBT/LBEL/LBER/LSxT/LSxE/LBF/LSxF`), and the countertop page in the client sheet.
- **Seam default rule (older, from memory):** seam only when longer than one piece, over a cabinet joint with a strip underneath, away from cutouts. Superseded by "no automatic seams; Brook decides".

---

## 7. Labels (the same on the nest PDF, the cut lists and the Omacad bodies). BUILT
- **Cabinet codes:** `B1, B2...` for bases left to right, then `U1, U2...` for uppers left to right. The countertop is `CT1`.
- **Part codes:**
  - `GL`/`GR` gable left/right.
  - `BP` bottom plate, `TP` top plate, `BK` back.
  - `TSF`/`TSB` top stile front/back, `DS` drawer stile.
  - `FB` sink front board, `FF` false front.
  - `TK` toe-kick plate, `TKB` toe-kick back.
  - `DF` drawer front, `DL`/`DR` door left/right, `D` single door.
  - `OS` open shelf, `MD` microwave divider, `MS` microwave shelf.
  - `DBS`/`DBF`/`DBB` drawer box side, front/back, bottom.
  - `SH` shelf, `SP` spacer (filler).
- **Numbering:** numbered parts carry their number (`DF1`). Multiple pieces get suffixes (`DBS1`, `DBS2`, or `DF1.1`). Collisions get `-2`.
- **Omacad box names:** `"<label> <cabinet name> / <part name>"`, for example `B1-GL Base cabinet 1 / Gable left`.

---

## 8. Nesting and cut lists (`nest_project.py`). BUILT
- **Stock:** **4' × 8'** (48 × 96) for every material: melamine, MDF, birch ply. Configurable with `sheet_w`/`sheet_l`.
- **Kerf:** **3/16"**, charged between every two neighbours. The factory edge is used as is (no trim cut).
- **Whole project, in cabinet order.** Bases left to right, then uppers, then the countertop plywood. The first cabinet fills sheet 1, the next fills what's left, and a new sheet opens only when nothing fits.
- **Grouping:** each **material + thickness** is its own nest. **1/2" back panels always get their own separate nest** ("- back panels").
- **Guillotine, 3 stages, matching the shop:**
  1. Panel saw rips the sheet into full-length strips.
  2. Crosscut each strip into blocks.
  3. Table saw rips a block into part widths.
- **Fewest cuts beats least waste.** Same-width parts share a strip, and same-length parts share a block. Strips are named A, B, C... (skipping I and O).
- **Grain.** Melamine and MDF have no grain, so parts may turn 90° (marked "turned"/T). Grain materials (any name containing birch, plywood, ply, oak, maple, walnut, cherry or veneer) keep their length along the 96" direction.
- **Offcuts:** leftovers at least **4"** each way are drawn and labelled "offcut W x L" and kept. Smaller slivers are hatched as scrap. Offcut inventory and reuse are PLANNED, not built.
- **Errors:** a part that doesn't fit a sheet raises an error, except oversize countertop pieces (see 6.11).
- **Outputs:**
  - `<job>-nest.pdf`: page 1 is a summary (per material: sheets, pieces, yield %, offcuts kept in sq ft, waste in sq ft, cuts, grain; then totals, oversize pieces in red, the cabinet code list and the part-code legend). Then one **11×17 landscape page per sheet**, drawn at **1-1/2" = 1'-0" (1:8), print at 100%**. Built with `rsvg-convert`.
  - `<job>-nest-cutlist.md`: cut order per sheet (strip rips, crosscuts, table-saw rips), a table per sheet, and the offcuts to keep.
  - `<job>-nest-cutlist.csv` with columns MATERIAL, SHEET, STRIP, RIP WIDTH, BLOCK, CROSSCUT, ORDER, LABEL, CABINET, PART, THICKNESS, WIDTH, LENGTH, TURNED, X ON SHEET, Y ON SHEET. Oversize rows read "NOT NESTED".
- **Yield** = part area / sheet area. The sample kitchen gave 9 sheets at about 70% yield (Oct 23).
- **Parts cut list** `<job>-cutlist.csv` (all parts, prefixed with "<cabinet> / ") and `<job>-layout.md` (wall-cabinet height, end-rule sentence, counter reach, and a table with uppers on top and bases below: Name, Run, Style, W, H, D, X, Y, Z).
- **Single-cabinet outputs** (`generate`):
  - `<name>-drawing.svg/.pdf` and `<name>-cutlist-sheet2.*` when it overflows.
  - `<name>-cutlist.csv` (qty, part, material, thk, width, length, banding, laminate, notes), `.md` and `-table-saw.txt` (one line per piece).
  - `<name>-nest-<material>-<n>.svg/.pdf`, `<name>-params.json` (for replay) and `<name>.omacad`.
- **OPEN nesting assumptions to confirm:** no edge trim, 96" rips, 4" minimum offcut, plywood grain direction, drawer-bottom details.

---

## 9. Outputs

### 9.1 Single-cabinet shop drawing (`draw.py`). BUILT
- **11×17 ANSI B landscape**, 0.4" margin, border.
- **Header:** "CABINET SHOP DRAWING" and the name with W x H.
- **Layout:** front elevation (left, 6.2 × 6.4), side elevation, a numbered key block, a notes block (assumptions), a cut-list table (bottom left) and a title block (bottom right). The title block shows STYLE, CASE, OVERALL, COUNTER, FRONTS, MATERIAL, KERF, DATE and "SHEET n OF m".
- **Dimensions:** overall dimensions sit outside the views. The scale is computed to fit and never hard-coded. Match the shop's existing print look; don't modernize it.

### 9.2 Omacad 3D model. BUILT
- One combined `.omacad` per job (`out/base-run.omacad` from the form), with one named body per part plus drilled holes (pulls, hinge cups, shelf pins), the countertop pieces, and simple wire-pull bodies.
- **No row titles** in the model (Brook, Oct 23; the `row_labels` code is disabled).
- "Show in Omacad" opens it full screen on workspace 3 and focuses it. Building takes about a minute.

### 9.3 Client sheet (`client_sheet.py`, "Client sheet (PDF)" button). BUILT
- **11×17 landscape, multi-page PDF.**
  - **Page 1, the whole kitchen:** title, front elevation (uppers over bases, doors, drawers, filler), isometric shaded 3D, plan view, end view, the cabinet schedule (it goes to 2 columns of W×H×D on long jobs), and a title block.
  - **Page 2, the countertop** (if any): sections, plus seam and dogbone details.
  - **Then one detail page per cabinet style:** front, side, top and 3D of one cabinet, one set of dimensions, a feature list, and a table of the other widths of that style used in the job.
- **Title block (Oct 30, on every page):** white box, hairline frame, a thin navy `#263460` top rule; the Coppinger logo (0.34" tall) top left and "Coppinger Exhibits / 9955 Westpoint Dr, Suite 150 / Indianapolis, IN 46256 · (317) 913-1400" right-aligned; then the job name (+ "· No. <job_no>") in bold; then two quiet columns: Client, Date (for example "October 30, 2026"), Revision, Sheet "n of N" | Drawing, Cabinets ("N (b base, u upper)"), Countertop, Prepared by. Long text is trimmed to fit. Footer: "Preliminary, for discussion. Not for construction."
- **Notes on page 1** (Oct 30): up to 5 short client notes from `notes.py` (picked finishes first, then only the notes that apply: height, counter kind, uppers, filler, sink, microwave, site check), under a shorter iso view.
- **Scales:** chosen from 1-1/2", 1", 3/4", 1/2", 3/8", 1/4", 3/16" and 1/8" = 1'-0".
- **Palette:** INK `#1f2933`, SOFT `#6b7785`, DIM `#3d4b5c`, fronts `#d7e0ea`, case `#f5f3ee`, filler `#e6dccb`, pull `#3b3f44`, wall `#9aa3ad`, laminate top `#d8cfbf`, solid top `#ebe8e2`. Picked finishes replace the front, case, filler and top colours (`palette_for(job)`); blank picks keep these.
- **Content rules:** a 1-door upper shows a dashed swing V (point = hinge side). Sparse, with overall widths; no manufacturing detail.
- The CLI also writes PNG previews (110 dpi). The form button returns the PDF inline and doesn't touch Omacad.

### 9.4 AR (`ar_export.py`, `ar_web.py`, "AR view" button). BUILT
- **Writes** `out/ar/cabcad.glb` (Android Scene Viewer and 3D viewers) and `out/ar/cabcad.usdz` (iPhone and iPad AR Quick Look), plus `cabcad.json` (title, version = USDZ mtime, size). Every build overwrites them.
- **No dependencies.** The GLB is written with struct and JSON. The USDZ is an **uncompressed zip with one ASCII `.usda` layer, every file 64-byte aligned** (binary `.usdc` is used if OpenUSD `pxr` is available).
- **Coordinates:** metres, Y up, +Z toward the viewer: `gl = (x, z, -y) × 0.0254`. The model is centred on its footprint and sits on the floor. Life size.
- **Geometry:** the same boxes as the client sheet (model3d + parts + counter + filler); rounded corners are stepped.
- **Materials:** the client-sheet colours (or the picked finishes) converted to linear RGB. Wood, marble and concrete finishes carry their 512 px CC0 JPEG texture (Oct 30): GLB uses `images`/`textures`/a repeat sampler and `TEXCOORD_0`; the USDZ uses `UsdUVTexture` + `UsdPrimvarReader_float2` with `primvars:st` and the JPEGs stored after the layer in `textures/`. Texture scale comes from the finish's `tile_in`. Not yet tried on a real iPhone with textures.
  - Case: roughness 0.75. Front: 0.55. Pull: metallic 0.8, roughness 0.35. Laminate top: 0.45. Solid top: 0.3.
- **MIME types:** `.usdz` is **`model/vnd.usdz+zip`**, `.glb` is `model/gltf-binary`. Some phone viewers send a HEAD request first, which is supported.
- **AR panel on the form:** size in inches and metres, the part count, and download links. With `--lan` it also shows a **QR code** (via `qrencode`) for `http://<lan-ip>:8777/ar/view?v=<version>`. Without `--lan` it shows a warning explaining `cabcad --lan` and the ufw command.
- **Phone page `/ar/view`:** the Coppinger logo in a small white pill at the top, navy button.
  - iPhone: tap the preview image (`<a rel="ar" href=...usdz>`).
  - Android: a Scene Viewer intent button (`intent://arvr.google.com/scene-viewer/1.0?file=...&mode=ar_preferred`, `scheme=https`).
  - Instructions: point at the floor, drag to place, twist to turn.
- **By email:** the **USDZ emailed to an iPhone opens from iPhone Mail in AR Quick Look**. That was demoed, and coworkers were amazed. The file stays email-friendly.
- **Wanted later:** a QR code on printed client and shop sheets that opens the full-size AR view from anywhere. That needs hosting. PLANNED.

### 9.5 Files served to the form
- After "Show in Omacad", links appear for: the nested cut sheets (PDF; "print 11x17 at 100%"), the nested cut list (text and CSV), and the parts cut list (CSV). The "This run" layout table and the build summary (sheet counts per material) are shown too.

### 9.6 Front-view wireframe (on `/run`). BUILT
- An SVG `#wire`, to scale, updated live as the form changes, **below the cabinet tiles and above the info lines**. It's "the star of the show for sales".
- **Draws:** floor, walls, cases, toe kick, interior, open shelves, fronts (drawers and doors), pulls, the 1-door swing V (uppers and 1-door bases), the microwave opening, the countertop over the bases and the filler, splashes, and overall width dimensions. A 1-door base pull sits on the handle side, 2" in from that edge, still 2" and 6" down from the top of the door. A pair of base doors stays 2" off the case centreline. Drawer pulls stay centred.
- **Its numbers come from the server** (`_wire_data()`, built from the same code as the cabinets), so the page never keeps its own copy of the dimensions.
- **Sizing for small screens (Oct 30 fit):**
  - `#wire { display:block; width:100%; max-width:100%; height: clamp(320px, 60vh, 640px); }`
  - `@media (max-height: 900px) { #wire { height: clamp(240px, 45vh, 480px); } }`
  - Full card width, twice the old 320px on a big screen, shrinking on short windows. `preserveAspectRatio="xMidYMid meet"`.
- **Totals table:** uppers listed on top, bases below.
- **Finish colours** (Oct 30): fronts, case, filler and countertop shapes (`.wf-front`, `.wf-case`, `.wf-filler`, `.wf-laminate`/`.wf-solid`) are filled with the picked finish colours. There is no separate 3D view inside the form; the 3D colour shows on the client sheet iso view, the render and AR.

### 9.7 Branding on client output (Oct 30). BUILT
- Logo: `assets/branding/coppinger/coppinger-logo-traced.svg` (PLACEHOLDER), embedded as a nested SVG (about 125 KB each). Used small: client sheet title block on every page, the render corner mark (bottom right), the AR phone page. Shop drawings (`draw.py`) keep their existing look, with no branding.
- Render (`render.py`, `cli render`, and the client email): 12×8 in on `#f3f3f1`, the shaded iso view only, a hairline, the job name and client bottom left, the logo corner mark bottom right; 1800×1200 PNG. One angle; studio lighting waits for a real renderer.

### 9.8 Finishes (Oct 30). BUILT (MVP)
- **Catalog** `assets/finishes/catalog.json`, 13 starter finishes, generic names (no brand names; "close to <brand code>" only once a real match is known):
  - Laminate solids: White, Black, Gray, Navy, Sage.
  - Laminate wood looks (CC0 textures from ambientCG, 512 px, rotated for vertical grain): Maple look (Wood048), White oak look (Wood049), Walnut look (Wood027), Birch ply look (Wood090A), tile 24×24".
  - Solid surface: White, Warm gray, Veined quartz look (Marble012, 30×30"), Concrete look (Concrete034, 48×24").
  - Each entry: id, kind (`laminate`/`solid_surface`), family, name, brand/code/close_to (blank), color, roughness, texture, tile_in, source, license, on_estimate.
  - Sources and licence in `assets/finishes/README.md` (CC0 1.0; textures about 236 KB total).
- **Custom finish stub:** `finishes.add_custom(name, code, kind, color)` → id `custom-<slug>`, saved to `assets/finishes/custom.json` (override path: env `CABCAD_CUSTOM_FINISHES`), flagged `needs_match` and "custom, not yet on an estimate". The assistant matches a CC0 look-alike later.
- **Where picks apply:** client sheet colours + notes, front-view wireframe, render, AR (GLB + USDZ). Box finish = case and interior; fronts = doors, drawer fronts and filler; countertop = laminate or solid top.
- OPEN: Rick's most-sold list from QuickBase/Archie's estimates; who may add finishes.

### 9.9 Email drafts (Oct 30). BUILT (draft only, never sends)
- **Email AR to me** (`POST /email-ar`, `drafts.draft_ar_email`): writes `out/email-ar/<job-slug>/` with `cabcad.usdz` (iPhone), `cabcad.glb` (Android), `email.eml` (To brook@printrbot.com, `X-Unsent: 1`, both files attached) and `mailto.txt`, then opens the folder (`xdg-open`, detached).
  - Recipients in `config/email.json`, enabled entries only: **brook@printrbot.com**. **Rick, ricks@cexhibits.com, is listed but `enabled: false`** (future recipient; do not include until Brook says so).
- **Draft client email** (`POST /client-email`, test mode): writes `out/client-email/<job-slug>/` with `<job>-client-sheet.pdf`, `<job>-render.png`, `<job>.usdz`, `<job>.glb`, `email.txt` (subject + copy-paste body) and `email.eml` (no To: address; all four files attached), opens the folder, and shows the body with a **Copy email text** button.
- Neither route contains any mail-sending code; the tests replace `smtplib.SMTP` to prove nothing tries to send.

### 9.10 Plans dashboard (Oct 30). BUILT
- `tools/plans-page` (stdlib Python) reads `~/Work/CABCAD-PLAN.md` and `~/Work/CABCAD-IDEAS.md` and writes **`~/Work/CABCAD-PLANS.html`**: counts, **Open questions** (highlighted, navy rule), the build order with a **Status** column, next steps, and the features/ideas table with status badges (BUILT / NEXT / LATER / OPEN QUESTION) and a **How to test** line for each built item.
  - Markdown conventions: `- STATUS — text` (DONE→BUILT, NOW→NEXT) and an indented `  - Test: ...` line; a `Status` column in the PLAN build-order table; bullets under "Open items"/"Open questions" are open questions.
- `tools/cabcad-plans` (linked as `~/.local/bin/cabcad-plans`): rebuilds the page and (re)opens it as a Chromium app window (`omarchy-launch-webapp file://...`), then goes to workspace 9. `--login` opens it quietly.
- Hyprland: `~/.config/hypr/hyprland.lua` rule `o.window("^chrome-__home_.*_CABCAD-PLANS\\.html-Default$", { workspace = "9 silent" })`; `~/.config/hypr/autostart.lua` runs `cabcad-plans --login` at start. Backups: `*.bak-20261030-plans` next to both files.

### 9.11 Notes (Oct 30). BUILT
- `cabgen/notes.py` holds every standard note once, each with an audience (shop/client) and an applies-when condition on the design's facts (counter kind, drawers, sink, microwave, uppers, filler, laminate, open ends ...). The shop drawing notes block and the client sheet use `select()`, so a laminate job never shows solid-surface notes and a door-only job never shows drawer notes. Assumption lines already covered by a note are dropped (`extra_checks`). The shop title block only says "Corian top" when the cabinet has a counter.

---

## 10. Status summary of features beyond section 9

- BUILT: everything in sections 2 to 9 not tagged otherwise, including the Oct 30 work: finished height 33-1/2", drawer bottom label, unified widths + live cut list, 3D drawer boxes = front − 2, branding/title block, render, context notes, finish picker MVP, Email AR to me, Draft client email (test mode), plans dashboard.
- CONFIRMED Oct 30 (Brook): drawer bottom 1/4" (label fixed); one set of default widths (upper 30, upper1 18, open 24, microwave 30, 3drawer 18, base 30, sink 30); total finished height 33-1/2" on all jobs with the case = 33.5 − counter; 3D drawer boxes follow the cut list; AR email to Brook only, Rick disabled.
- DECIDED-NOT-BUILT:
  - Shelf-pin standard (6.10).
  - Over-sink short upper (6.7).
  - Carpenter shop-drawing set for whole jobs. Brook, Oct 27, wants it tighter than the client sheets, with:
    - every door and drawer dimension, matching the cut list;
    - pull and hinge locations;
    - edge banding per part and per edge;
    - door and drawer gaps and reveals shown as **close-up picture details**, not text;
    - plus **one picture-based shop-standards reminder page** (the "ONE shop way").
  - Drawing set order: whole-kitchen overview first, then one detail page per style. Already done on the client sheet; to mirror on the shop set.
- PLANNED:
  - "Working model" Easter egg: click a door in the front view (and ideally 3D/AR) to pop it open and show the shelves.
  - Exact hinge, pull and slide models for hole locations.
  - Assembly drawings.
  - CNC code output.
  - Offcut inventory.
  - Real counter assembly bodies and real hardware in 3D.
- OPEN QUESTIONS (waiting on Brook):
  1. Carpenter-drawing questions (unanswered from Oct 27): the hinge jig (stock hinge brand, overlay, drill locations, count on tall doors), pull placement and handle jigs, the edge-banding rule (which edges), door and drawer gaps (confirm 1/8" and the 1/4" reveal), the **3-drawer box height**, and part labels on the parts themselves. The exact wording of all 7 is **unknown**; these are the topics recorded.
  2. Sink front board 1/2" drop below the door tops. Sink plumbing notch in the back stile. Sealed sink bottom.
  3. Microwave shelf between the gables vs full width; opening height, venting, trim kit, drop height.
  4. Nesting assumptions (no edge trim, 96" rips, 4" minimum offcut, plywood grain).
  5. Drawer-height range (4 to 8) vs historical jobs.
  6. Filler best practice; fillers between out-of-spec walls; how an upper run meets a wall.
  7. Older standards TBDs, mostly settled by the code but never formally confirmed:
     - #1, the case width excludes the overlay;
     - #3, the 1/8" total door gap;
     - #4, doors overlay the sides only;
     - #5, applied vs dadoed back (the code uses applied);
     - #7, drawer box material (the code uses 3/4" melamine);
     - #8, counter backer strips vs solid (the code uses strips);
     - #9, the 3" toe-kick recess;
     - #10, the reveal-side laminate rule per cabinet;
     - #11, whether the drawer front covers the top stile (the code: fronts start 1/4" below the case top, with the flat stile behind);
     - #12, one rail per drawer gap (the code does that).
  8. Counter items marked "to confirm" in 6.11: the 25" depth (the top height is settled: 33-1/2" finished, Oct 30), side-splash butt, no back strip, no backer sheet, +10% laminate, 4" stiffeners, the rabbet depth, splash materials.
  9. Open-shelf upper: shelf count, fixed vs adjustable, interior finish.

---

## 11. Roadmap (Oct 30 plan; build order)

1. **Local git and sync.** BUILT on the iMac: bare repos, plus `cabcad-sync-check` running at login, after resume and every 30 min. PENDING on the laptop: clone, sync-check install and SSH/Tailscale. Done when both machines sit on the same commit and the check is green on both (see section 13).
2. **Finish catalog (laminate and solid surface).** MVP BUILT Oct 30 (9.8): 13 generic starter finishes, CC0 textures, three picks, AR. Still PLANNED: the real list from QuickBase/Archie, "close to" labels, Rick's top sellers first.
   - The list comes from finishes on the **real QuickBase job records and historical purchases / Archie's estimates**. It's not in QuickBooks; Sue has that.
   - Every finish is labelled **"close to <brand> <code> <name>"**. Never ship brand images or files (they're copyrighted).
   - Each one gets a close **CC0 look-alike** (ambientCG, Poly Haven) or a solid colour plus roughness/gloss.
   - **Separate picks** for doors/fronts, box/interior and countertop. Rick's most-sold finishes go at the top.
   - Stored as a data file (JSON or YAML) in the repo, one entry per finish: type, brand, code, name, look-alike source + licence, colour, roughness, texture path, scale, and an "on a real estimate" flag.
   - Starter set: about 12 to 15 finishes (solids: white, black, grey, navy, sage; woods: maple, white oak, walnut, birch ply; 3 or 4 solid-surface or quartz looks) until the real list arrives.
   - Finishes apply to the 3D view, the renders and the AR file (textures make the USDZ a little bigger; keep it email-friendly).
3. **Custom finish.** STUB BUILT Oct 30 (name, code, colour → custom.json, in the dropdown, flagged). The research/match step is still manual (the assistant).
   - The user types a name and code (laminate or solid surface). The **assistant researches it and matches the closest CC0 look-alike**, and it's added to the dropdown permanently.
   - Flag it "custom, not yet on an estimate" until it appears on one.
   - Later: turn a phone photo of a sample chip into a tileable texture.
   - OPEN: who can add finishes, Brook only or Rick too.
4. **Render feature.** FIRST STILL BUILT Oct 30 (9.7: one angle, flat shading, logo corner mark). PLANNED: stills with soft studio light, a neutral background, 1 to 3 angles and a small logo watermark.
5. **Branding and title block on client output.** BUILT Oct 30 (9.3, 9.7), except the approval box and revision change notes.
   - Minimal Coppinger Exhibits branding, but fully professional ("as if a whole team were behind it"). The shop prints keep their existing look.
   - **Title block on every client sheet:** logo, job name and number, client, date, revision, sheet number, and "Prepared by".
   - **Colours:** accent navy **`#263460`**; greens **`#037c39`** (wordmark), **`#93bc3c`** and **`#5fa549`** (sphere), used sparingly. Clean sans-serif, white space, thin rules.
   - **Client approval box:** signature and date.
   - **Address:** **9955 Westpoint Dr, Suite 150, Indianapolis, IN 46256 · (317) 913-1400**. Verified on Google Maps and the Coppinger site; it's near 96th St on the Indianapolis side of the Fishers line.
   - **Logo:** a PLACEHOLDER vector traced from the website's 286×96 PNG. It's committed in the repo at `assets/branding/coppinger/coppinger-logo-traced.svg`, along with:
  - the original PNGs (`coppinger-logo.png` 286×96, `coppinger-logo-1.png` 200×67);
  - a 2860w render;
  - the legacy 2012 CE vector (`old-ce-logo-2012.svg`, from the site's `requirements.pdf`);
  - a `README.md` with sources and colours;
  - `src/` and `web/` captures of the site.

  Brook approved it as a placeholder. Ask Mike or marketing for the official AI/EPS/SVG master.
   - Later: revision tracking (Rev A/B/C with change notes).
6. **Sales package plus a "Draft client email" button.** TEST MODE BUILT Oct 30 (9.9): folder + copy-paste body + .eml, nothing sent; plus "Email AR to me".
   - One button loads the client PDF, the render(s) and the AR USDZ into an email draft that Rick edits and sends.
   - For testing first: a copy-paste version we send to ourselves to see exactly what the client sees.
   - **Approval stays manual.** Client approvals usually come with changes; they're not a yes/no. Automated approval (client clicks or signs, the job is marked approved in QuickBase) is LATER and on hold.
7. **Estimate database plus the estimator (the real goal).** PLANNED.
   - **Source: Archie's Excel estimates**, on the work drive under **Projects → each job → Estimate folder → exactly one `.xlsx`** (the naming convention is unknown). Sheet 1 is the client one-pager; the other sheets have the detail.
   - Build a historical database: job, cases (type, size, count), materials, finishes, prices, **shop man-hours per case**, install.
   - Decode Archie's shorthand for upper and base cases, and ask Brook about anything unclear.
   - **Estimator math:** materials (sheets, laminate, solid surface per sq ft, banding, hardware) + labour (hours per box, door, drawer, countertop and install × rate) + markup. It produces a client price; the margin is visible only to Brook and Rick.
   - Match Archie's method first, then improve it with actual vs estimated hours (carpenter hours from the dashboard; material costs from Eddie's purchase orders).
   - **Custom item line** with a manual price and hours, so one-offs don't block the flow.
   - Output the same **one-page summary** as Archie's sheet 1, printable for Brook's billing folder.
   - Later: good/better/best options (for example laminate vs solid surface), and creating the QuickBase estimate automatically on approval.
   - Done when CabCad's price is within an agreed tolerance of Archie's on past jobs.
   - **Access:** WKS058 (work PC, read-only, Brook approves each access) may see Projects. Fallback: Brook copies 10 to 20 `.xlsx` files to the laptop's `~/Work/estimates/`. Long-term: IT-approved access.
8. **Web app for Rick.** PLANNED.
   - Runs in a browser on his Windows laptop and his phone. Brook prefers a simple **PWA** (Add to Home Screen) over native apps, with the Omarchy iMac doing the work and serving phones, tablets and Windows browsers.
   - Hosted so salespeople can set up a job and get live links to the drawings and the AR view to email or print. `cabcad --lan` is the first step.
   - Later: team access with personalized views (Rick, Tully, Brook, Eric, Chad, Randy, Andrew, Sue, Eddie; Mike view-only).
9. **Shop handoff plus the purchase list.** PLANNED.
   - An approved job goes straight to shop drawings and cut sheets for Randy and Andrew (the design that's sold is the one that's built; no CAD redraw).
   - At the same moment, the purchase list goes to Eddie: detailed and clean, each line **IN STOCK** or **ORDER**. Base materials are mostly stocked. Custom laminate, solid surface and hardware are long-lead and ordered at release, arriving while the casework is built.
   - Later: drawings carpenters build from with zero redraw ("close, not there yet").

Ideas backlog: `~/Work/CABCAD-IDEAS.md` (BUILT/NEXT/LATER/OPEN QUESTION, with "Test:" lines; shown on the plans page, 9.10). Feed new ideas to Brook as they come up.

---

## 12. Tests to recreate (97; names from `~/Work/cabinet-gen/tests`)
- **Added Oct 30:**
  - `test_base_height` (3): 33-1/2" finished on every counter kind; case = 33.5 − counter; 3D drawer boxes = front − 2.
  - `test_branding` (4): the logo and address on every client page; the title block fields; the render has the corner mark; form job fields reach the sheet.
  - `test_defaults_and_cutlist` (2): CLI and form default widths are the same table; the live cut list follows the typed widths.
  - `test_notes` (5): laminate jobs show no solid-surface notes; door-only jobs show no drawer notes; sink/microwave notes only when present; client notes short; duplicate assumptions dropped.
  - `test_finishes` (4): catalog licensed and split by kind; picks change the client sheet colours and notes; AR carries finishes and textures (aligned USDZ, GLB TEXCOORD_0); the form has three pickers and custom finishes join them.
  - `test_drafts` (4): config has Brook only and Rick disabled; the buttons are on the form; Email AR writes a USDZ+GLB draft to Brook; the client email collects PDF, render and AR.
  - `test_plans_page` (2): status badges, test lines and open questions; the real docs build.
  - `test_kitchen` gained the drawer-bottom label test (14).
- **`test_ar_export` (5):**
  - creates the files;
  - the bounding box is the kitchen in metres, on the floor;
  - triangles face out and the model is not mirrored;
  - all styles, the counter and the filler are in the model;
  - the USDZ is stored 64-byte aligned, Y-up, in metres.
- **`test_ar_web` (7):**
  - the CLI writes both files;
  - `--lan` is opt-in;
  - the local-only panel explains LAN;
  - the LAN panel has a QR code and the phone URL;
  - phone page links;
  - the server serves models with AR MIME types;
  - LAN clients only get the AR pages.
- **`test_client_sheet` (3):**
  - the sample page has every view and the schedule;
  - the form button returns a PDF and shows the filler;
  - one detail page per style, about one cabinet only.
- **`test_counter` (9):**
  - `none` builds nothing;
  - laminate build; solid build;
  - a long laminate top is one piece, flagged, not seamed;
  - a long solid top is flagged; a short top is not flagged;
  - an oversize top is listed, not nested;
  - the nest includes the plywood, not the solid surface;
  - the client-sheet counter page.
- **`test_form_wire` (4):**
  - the page has the wireframe and drag handles;
  - the wire data is injected and comes from params;
  - the drawer height changes the drawn drawer;
  - every style has a stock default width in the form.
- **`test_kitchen` (13):**
  - a width change keeps the style's size; a typed height overrides the style;
  - three widths of the same cabinet;
  - rows are independent and a left wall is flush;
  - two walls put one filler on the chosen side;
  - open ends overhang an inch each;
  - the group form rejects a short width and a negative offset;
  - the group page starts with one base and one upper;
  - an unknown style names the line;
  - the filler is 1, 2 or 3 inches;
  - uppers never get a filler;
  - the 1-drawer style takes a drawer height;
  - uppers never have drawers.
- **`test_nest_project` (8):**
  - every piece of the sample kitchen appears once, with no overlap;
  - backs are their own nest, and the first cabinet starts sheet one;
  - kerf is respected with a wide blade;
  - a part bigger than a sheet gives a clear error;
  - a grain material never turns;
  - same-width parts share a strip;
  - CAD boxes carry the cut-sheet labels;
  - the group-form build writes the PDF and cut lists (needs Omacad and rsvg).
- **`test_sink_and_microwave` (12):**
  - sink fronts match the 1-drawer base;
  - the sink has no drawer box, slides, shelf or pins;
  - the sink front board runs to 1/2" below the door tops;
  - sink labels and codes; the sink goes through the form, the CSV and the wireframe;
  - the microwave box is upper depth and only the shelf projects;
  - the client sheet renders the sink and microwave pages;
  - the client views show one unbroken countertop;
  - the microwave shelf has round front corners, which go to Omacad as cylinders;
  - the nest sheet draws the rounded shelf;
  - ten bases, no column cap.
- **`test_uppers` (11):**
  - the 1-door handle side moves the pull and the hinges;
  - the open upper has no doors and even shelves;
  - the microwave upper's opening, divider and short doors;
  - the form carries the new styles and the handle through the CSV;
  - labels, nest and cut list (needs Omacad);
  - the client sheet has a detail page for each new style;
  - the form tile shows the handle toggle and style icons;
  - upper pulls are stock wire pulls measured to hole centres;
  - base door pulls did not change;
  - summary tables list uppers before bases;
  - the 1-door icon follows the handle toggle.

---

## 13. Backups (after losing a laptop)
- **Local-only git, no GitHub** (Brook: "If git is local, yes. But both machines.").
- **Master bare repos on the iMac:** `~/Work/git/cabinet-gen.git` and `~/Work/git/omacad.git`.
  - `~/Work/cabinet-gen` pushes and pulls through remote **`origin`** (the bare repo).
  - `~/Work/omacad` uses remote **`imac`** (its own `origin` is still the upstream Omacad project).
  - Branch: `main`.
- **cabinet-gen history:**
  - `0edde35` initial snapshot
  - `b0ca402` sync-check script and systemd units
  - `b7b009d` this spec as `docs/CABCAD-SPEC.md`
  - `3e62520` branding assets
  - Oct 30 features: `0a8dbf9` drawer bottom label, `e559e6b` unified widths + live cut list, `d8d3489` 33-1/2" finished height, `4b4108f` branding + title block + render, `e3ade5d` context notes, `8ae4c91` finish picker, `a7e008e` Email AR to me, `6a6856f` Draft client email, `712860e` plans dashboard, then this spec update
- **Laptop.** It clones and mirrors over the LAN or Tailscale. The iMac is `imaco` on the LAN and `imaco-ts` / 100.66.33.81 on Tailscale. The laptop's remotes use the same names with SSH URLs, like `ssh://abdrumm@100.66.33.81/home/abdrumm/Work/git/cabinet-gen.git`. It needs key-based SSH from the laptop to the iMac. Status: **PENDING**, since the laptop has been offline.
- **Sync check (`cabcad-sync-check`).** BUILT on the iMac; PENDING on the laptop.
  - **Script:** `~/.local/bin/cabcad-sync-check` (bash). The repo copy is `tools/cabcad-sync-check`.
  - **Config:** the `REPOS` array holds `"<working tree>|<remote>|<branch>"`:
    - `~/Work/cabinet-gen|origin|main`
    - `~/Work/omacad|imac|main`
  - **What it does for each repo:** fetch, with a 30 s timeout and SSH in BatchMode with a 10 s connect timeout, and no prompts. Then:
    - **behind:** fast-forward pull;
    - **ahead:** plain push;
    - **diverged:** report only;
    - **dirty working tree:** report;
    - **remote unreachable:** report ("can't reach iMac").
  - It **never auto-commits** and never force-pushes or merges.
  - **Notices:** `notify-send`, green when in sync and red on any problem. With `--quiet`, nothing shows when everything's in sync.
  - **Log:** `~/.local/state/cabcad-sync.log`.
  - **Modes:**
    - plain run: one check;
    - `--quiet`: the timer mode;
    - `--watch-resume`: blocks on `gdbus monitor` of logind `PrepareForSleep(false)` (no root needed), then runs a check 20 s after each resume from sleep.
  - **systemd user units** (repo `tools/systemd/`, installed and enabled on the iMac; install steps in `tools/systemd/INSTALL-sync-check.md`):
    - `cabcad-sync-check.service`: at login (after `graphical-session.target` and `network-online.target`), with `ExecStartPre=/bin/sleep 20`, so it runs **20 s after login**.
    - `cabcad-sync-resume.service`: the long-running `--watch-resume` watcher, after `graphical-session.target`.
    - `cabcad-sync-check.timer`: `OnBootSec=5min`, `OnUnitActiveSec=30min`. It triggers `cabcad-sync-check-timer.service`, which runs `--quiet` **every 30 minutes**.
  - **Laptop install (PENDING):**
    1. Clone both repos from the iMac with SSH remotes (`origin` for cabinet-gen, `imac` for omacad).
    2. Copy the script to `~/.local/bin/` and the units to `~/.config/systemd/user/`.
    3. Run `systemctl --user daemon-reload`.
    4. Enable `cabcad-sync-check.service`, `cabcad-sync-resume.service` and `cabcad-sync-check.timer`.
    5. Confirm a green notice.
- **After every work session:** commit, then let the sync check push and pull (or run `cabcad-sync-check` by hand), and confirm a green notice on both machines (same commit, clean status).
- **Docs:** `CABCAD-PLAN.md`, `CABCAD-IDEAS.md`, `CABCAD-SPEC.md` and `cabinet-shop-standards.md` are kept identical in `~/Work/` on both machines. The spec is also in the repo as `docs/CABCAD-SPEC.md`, so it travels with git. The others are outside git (LATER: move them into `docs/`).
- **Branding assets** are in the repo at `assets/branding/coppinger/` (see the roadmap, step 5).
- **Older safety copies:** `*.bak-YYYYMMDD-*` files next to the sources (git-ignored) and `~/Work/cabinet-gen.bak-20261028` on the laptop.
- **LATER:** an off-site backup that isn't public GitHub (an encrypted drive or a private remote). That's Brook's call.
- Note: the GitHub repo `abdrumm/cabcad` exists and was **public**. Brook chose local-only git, and nothing has been pushed to GitHub.
