# Cabinet Shop Standards — Context & Rules

Saved: 2026-10-21
Status: **Living document.** The user said "there will be more" — append new rules here.
Owner: abdrumm (custom casework / cabinet shop). Design tool: Omacad + `cabgen`.

Units: **inches**, fractions to the nearest 1/16 where it matters. Nothing in this shop
gets complicated for the sake of it — **keep cut-list dimensions in the simplest fractions.**

---

## 0. Project at hand (first instance)

Base cabinet, one drawer over two doors, with solid-surface top:

| Item | Value |
|---|---|
| Case outer width | 27" |
| Overall height (floor to top of counter) | 33.5" |
| Countertop depth | 25" |
| Base casework depth | 24" (always countertop depth − 1") |
| Drawer | one, 6" tall front |
| Doors | two, below the drawer |
| Carcass material | 3/4" melamine, light oak formica laminate on reveal faces |
| Top | 1/2" Corian solid surface, 1" MDF backer, rabbit-jointed |
| Kick plate | 4" |

---

## 1. Materials

| Material | Thickness | Notes |
|---|---|---|
| Melamine (carcass) | 3/4" | standard carcass stock |
| Melamine (back panel) | 1/2" | applied or dadoed into the sides |
| Laminate (formica) | light oak | applied to **reveal faces only**; right side of this cabinet is a reveal |
| Solid surface (Corian) | 1/2" | countertop top piece |
| MDF backer | 1" | under the Corian, screw medium + edge build-up |
| Edge banding | 0.5–2 mm | **never** alters stated part dimensions |

### Finish numbers (display colour, 2026-10-30)

A job names four finishes by catalogue number. The lines sit with the other
`# key=value` settings. A cabinet row can override with the same column name.
Blank `case` and `interior` mean white melamine. Blank `doors` keeps the plain
front colour. Blank `top` keeps the counter's laminate or solid-surface colour.

| Line | Surface |
|---|---|
| `# case=` | box exterior (gables, toe kick, visible stiles) |
| `# doors=` | doors and drawer fronts |
| `# top=` | countertop show faces (deck, front edge, splashes) |
| `# interior=` | shelves, back, drawer boxes. Default white melamine |

The list is `cabgen/laminates.csv`: manufacturer, number, name, an approximate
hex (not a manufacturer swatch), and a `texture` column left blank for a later
image. An unknown number is a neutral gray plus a warning. It does not stop the job.
`jobs/sample-kitchen.csv` uses Formica 5786-NG Ashwood Oak doors, white interior,
and Formica 3450-58 Mineral Jet tops.

### Laminating rules (the "spray" method)
- Take the **final dimension** of the piece and **add 1"** (1/2" per side) so there is
  wiggle room for overspray when the laminate and the melamine are sprayed with
  contact adhesive.
- Trim the overspray back with the **palm router**.
- Sand the unfinished edges; **hand-file the exposed edges**.

### Waterfall pattern (laminate face order)
Apply laminate in this order so the pattern sheds like water:
1. **Bottom** (when applicable — e.g. door fronts)
2. **Sides**
3. **Top**

Exceptions happen, but they are few and deliberate. Note any exception on the drawing.

---

## 2. Casework anatomy

- **Bottom plate** ("stretcher" that is the floor of the cabinet).
- **Top stretchers: two, 4" wide** — one at the back, one at the front — length = the
  **inside** dimension width.
- **Toe-kick stretcher**: a stretcher at the face of the toe kick, butting up to the floor.
- **Drawer stretchers**: when there is a drawer, the stretcher **lies horizontally — flat**,
  so the drawer has a **3/4" board** to face-edge and overlap.
- **If there is a drawer or a door below the drawer, another stretcher is placed for that
  drawer** (i.e. an extra stretcher for the lower element).
- **Uppers:** sides (gables) run full height; the **top and bottom are each one full-depth
  piece cut to the inside width**, captured between the sides. (Brook, 2026-10-23)
- **Base gables are one piece.** Each side runs full height from the floor to the top
  of the case, and that includes the toe-kick zone. The toe-kick notch (the recess,
  3" deep by the 4" kick height) is cut into that one panel. The structural toe-kick
  plate is a separate board, set back from the front. The gable is never a second
  piece stacked under the case for the bottom 4". (Brook, 2026-10-31)
- **Finished kick plate (optional).** Off unless the job says `# kickplate=yes`.
  Black or grey (`# kickplate_color=black` or `grey`; `gray` is grey). Height is
  **3.75"** (`KICK_PLATE_H` in `cabgen/params.py`), overridable with `# kickplate_h=`.
  It has to stay inside the 4" toe kick. One piece covers each stretch of bases that
  touch, filler included on the end. A gap between bases starts another piece. It is
  a 1/4" skin on the room side of the structural toe-kick plate. The gables stay one
  piece. Sample jobs leave it off. (Brook, 2026-10-31)
- Drawer sizes vary; door sizes vary. **The generator must accept these as inputs** and
  adjust the schedule of stretchers, not hard-code them.

### Doors and drawers
- Doors are **overlay**: **1/2" overhang** (default; expose as a field).
- **Gap between the two doors: 1/8"** (expose as a field — see TBD #3 about 1/8" per door).
- Drawer fronts overlay the case the same way.

### Front build (how the fronts stack) — implemented in `cabgen`
Top down, at the **case front**:

1. **Top stretcher, 4"** — visible band above the top front.
2. **Front opening** = the rest of the case height (28" case − 4" stretcher = 24").
3. **Drawer stack** (if any): drawer fronts separated by a **1/8" reveal**; the height of a
   single drawer front is an input, several fronts split what is left evenly.
4. **Drawer rail, 4"**, flat at the case front under the drawer front(s) — the front
   butts the rail **face to edge**, the rail carries the front and squares the case.
5. **1/8" reveal**, then the **doors** fill the rest of the opening.

Consequence for the first instance (27" case, 33.5" overall, 6" drawer):
6" drawer front + 4" rail + 13 7/8" doors inside a 24" opening.
The rail and the top stretcher are **visible** at the case front (they show through the
reveals). If the drawer front is supposed to **cover** the top stretcher instead, the
front has to be 4" + opening tall — that is TBD #11.

---

### Upper styles (2026-10-24), placeholders to confirm with Brook's shop plans
Brook asked for 1-door, open-shelf and microwave uppers and will bring plans and CAD
files from work. Until then everything below is a **placeholder, to confirm with
Brook's shop plans**. The numbers live at the top of `cabgen/params.py`.
- **2 doors** (`upper`): unchanged. 30" tall, 12" deep, no shelf (as built so far).
- **1 door** (`upper1`): one door over the full opening. Default 18" wide; typical
  9"-24", and the form and CSV accept down to 9" (other cabinets stay 12" minimum).
  Wider than 24" is not built as one door; see the rule below.
  The tile has a **Handle L/R** toggle (CSV column `handle`): the pull goes on that
  side, 1-1/2" in from the edge; the **hinges go on the other side**: two 35 mm cups,
  1/2" deep, 22.5 mm from the hinge edge, 3" from the top and the bottom. The model
  names the door `Door, handle L|R` and shows hinge plates; the client sheet draws
  the dashed swing V (point = hinge side) and lists the handle side. Label `U#-D`.
  To confirm: hinge brand/overlay, hinge count on tall doors, pull position.
- **Single-door upper, 24" maximum (Brook, 2026-10-30).** A wall upper with one
  door is never wider than 24". Exactly 24" is still one door. Any upper wider
  than 24" that would have been one door is built as a pair (two doors). If the
  form, the CSV (`upper1` / `1door` / `upper_1door`), or a style pick asks for
  one door on an upper over 24", CabCAD does not build that single door: it
  switches the cabinet to two doors and writes a warning on the layout, the
  shop-drawing notes, the generator output, and the client-sheet detail.
  Open shelves and the microwave upper are not single-door cabinets, so this
  does not add doors to them. Base cabinets are not covered; a base keeps its
  own door count. Constant `UPPER_1DOOR_MAX_WIDTH` in `cabgen/params.py`.
  Enforced when the style is applied and again when parts, the 3D model, and
  the kitchen layout are built. The live front view uses the same limit
  (`WIRE.upper_1door_max`).
- **Open shelves** (`open`): no doors, 30" wide default, 2 adjustable 3/4" shelves
  spaced evenly in the clear height, 1/8" side gap, 1/4" set back, on 1/4" pins
  (rows at each shelf and 2" either side, columns 2" from the front and the back).
  Finished interior: the inside faces show, front edges banded. Label `U#-OS1..`.
  To confirm: shelf count, fixed vs adjustable, interior finish (melamine vs laminate).
- **Microwave** (`microwave`): 30" wide x 30" tall (tops line up with the other
  uppers). **Depth CONFIRMED (Brook, 2026-10-27): the box is 12" deep like every other
  upper** (`UPPER_DEPTH` in `cabgen/params.py`; was a 15" placeholder).
  **17-1/4" clear opening** above the bottom, then a fixed 3/4" divider (label `U#-MD`),
  then a small 2-door cabinet: 12" overall above the opening (doors about 11-1/2"
  tall, lapping the divider like any other front). Opening interior is finished.
  - **Microwave shelf (bottom board) CONFIRMED (Brook, 2026-10-27):** the only part that
    leaves the 12" box. It measures **16" from the front face of the 1/2" back to the
    front of the shelf** (`MICROWAVE_SHELF_CALLED_DEPTH = 16`), so **16-1/2" overall**
    and it projects 4-1/2" past the gables. **Front corners rounded to a 2" radius**
    (`MICROWAVE_SHELF_CORNER_R`). Captured between the gables (inside width), fixed,
    glued and screwed. Label `U#-MS`. **The 2" R corners are modelled (2026-10-27):**
    true round corners in Omacad (cylinders joined into the shelf), fine steps following
    the radius in the client views and AR, and the nest sheet draws the rounded outline
    over the dashed rectangle it is packed and cut from, marked `2" R front corners`.
  - To confirm: shelf width (inside the gables, or full width with the gables sitting on
    it), opening height for Brook's microwaves, venting, trim kit or not, whether it
    ever drops lower than the other uppers.
- The client sheet's cabinet table goes to two columns (W x H x D) on long jobs.
- **Upper door pulls (Brook, 2026-10-24): stock pull: wire pull, 4" c-c, screws from
  the back.** Vertical on every upper door (2 doors, 1 door, the microwave's 2 doors).
  All dimensions are to **hole centres**: bottom hole 1-1/2" up from the bottom edge of
  the door, top hole 5-1/2" up (4" c-c), both 2" from the door's handle (opening) edge;
  a pair opens at the meeting edges, a 1-door at its handle side. Holes drilled through
  at 3/16" (screw size is a placeholder). Constants `UPPER_PULL_*` in `cabgen/params.py`.
  "For now" positions; base door pulls are unchanged (2" and 6" down from the top,
  2" off the case centreline).

### Sink base (Brook, 2026-10-27) — style `sink`, label "Base, sink"
Built like the 1 drawer over 2 doors base (`base`), with these differences. Constants
`SINK_*` at the top of `cabgen/params.py`.
- **False drawer front** — CONFIRMED: same size, reveals and gaps as the real drawer
  front of the 1-drawer base (the form's drawer-height pick works the same, 6" default).
  **No pull, no holes.** Label `B#-FF`.
- **No drawer box, no slides, no shelf, no shelf-pin holes** — CONFIRMED.
- **Front board** replaces the flat front top stile (and the drawer stile under the
  front): a vertical 3/4" board between the gables, flush with their front edges,
  right behind the false front, which screws to it from behind. It runs **from the
  top of the case down to 1/2" below the top edge of the doors** — **TO CONFIRM**
  (Brook said "I think"; `SINK_FRONT_BOARD_BELOW_DOOR_TOP = 0.5`). The doors close
  against it. Label `B#-FB`, in the cut list and nesting.
- **Back stile stands vertical, 4" tall** — CONFIRMED (`SINK_BACK_STILE_H = 4`),
  flush with the top of the sides. Label `B#-TSB`.
- Normal bottom; doors and gaps the same as `base` — CONFIRMED.
- Default width 30", the same as `base` — CONFIRMED "for now". Common sink bases run
  30"-36" (33"/36" for a double bowl); revisit when Brook has job history.
- To confirm: the 1/2" below the door tops; whether the back stile needs notching for
  plumbing; whether the bottom gets a finished/sealed face for leaks.

## 3. Countertops (Brook, 2026-10-24) — implemented in `cabgen/counter.py`

Pick one per job on the group form or in the CSV (`# counter=laminate|solid|none`).
**Laminate is the default.** The two builds are kept separate here, in the code and in the
cut list. Both are **1-1/2" at the front edge**. Items marked **(to confirm)** are my
assumptions, not Brook's words.

Common to both:
- **Backsplash 4"** tall along the wall. **Side splash 4"** at every wall end, put on
  automatically (Brook); the form can turn one off.
- **Open end** (no wall): 1" overhang with a finished edge. **Wall end**: flush.
- Front overhang 1-1/2" past the case, so the counter is 25" deep (existing value; Lowe's
  gives 1-1/4" as standard) **(to confirm)**.
- The counter sits on the 33-1/2" case, top at 35" **(to confirm)**.
- Side splash runs from the front back to the backsplash and butts it **(to confirm)**.

### 3a. Laminate counter
- **3/4" plywood top.**
- **3/4" plywood build-up strips, 4" wide** (Brook), **glued and stapled** to the underside:
  under the front edge, under each finished side edge, at each counter end, and **centred on
  every place two cabinets meet**. Installers screw up through the cabinets into the strips.
  Front edge = 3/4" + 3/4" = **1-1/2"**.
- **Laminate order: side edges (when needed), front edge, then the top.** Every exposed
  splash edge gets laminate.
- Backsplash and side splash: 3/4" plywood, laminated **(to confirm)**.
- No build-up strip along the back wall **(to confirm)**; no backer (balance) sheet underneath,
  since it is screwed down and the overhang is small; guides want one for bars and big
  overhangs **(to confirm)**.
- Laminate is listed as a **takeoff in sq ft** (+10% waste, to confirm), not nested. Plywood
  top and strips go in the whole-project nest.

### 3b. Solid surface counter (Corian)
- **1/2" solid surface top.** Underside rabbet at the front and finished edges takes a
  **1-1/4" solid surface edge strip, epoxied**. 1/4" lip + 1-1/4" strip = **1-1/2" reveal**.
  - Brook said a 1/2" x 1/2" rabbet; to get a 1/4" lip it is modelled **1/2" wide x 1/4" deep**
    **(to confirm)**. Ease revealed edges with a 1/8" round-over; sand flat.
- **Build-up strips directly under the sheet.** 4" wide (`STRIP_W`), **3/4" plywood**
  (`SOLID_BUILDUP_THK` in `cabgen/counter.py`). MDF is the other stock that would fit;
  plywood matches the laminate strips and goes in the nest. The strips are glued tight
  to the underside of the 1/2" sheet. Because the front edge is still a 1-1/2" reveal,
  a 3/4" strip starts 1/4" above the case.
  - **Perimeter:** front (behind the edge strip), back, and both ends.
  - **Case breaks:** one strip centred on every place two base cabinets meet, running
    front-to-back between the front and back strips (same places as before).
- Backsplash / side splash: 1/2" solid surface **(to confirm)**.
- Solid surface pieces are **listed, not nested** on 4x8 plywood. Build-up strips are nested.
- Front strip runs full length; side strips butt behind it **(to confirm)**.

### 3c. Seams: none automatic (Brook, 2026-10-27)
- **One continuous countertop, everywhere.** The program no longer splits the top at 96"
  (or 144"). The top, the front build-up and the backsplash are each **one piece the length
  of the run** in Omacad, the client sheet, AR, the front view, the cut list and the nesting.
- A piece longer than its stock sheet (96" plywood; 144" solid surface or laminate) is
  **flagged "LONGER THAN STOCK SHEET - seam TBD"** in its cut-list note, listed under
  "Not nested" in the nested cut list (.md and .csv) and on the nest PDF summary page, and
  **not drawn on any sheet**. Brook decides where it seams.
- Seam rules are a later topic Brook will define. The notes below are the earlier research
  and the old rule, kept for that discussion; **the program does not apply them now.**
- **No cabinet limit (2026-10-27):** the old 8-cabinets-per-row cap is gone. The form
  draws 8 tiles ready and the + button keeps adding past that; the server reads any number.

Earlier rule (not applied now). Brook: "the counter seams at convenient places." Rule the program uses:
1. **Only seam when the run is longer than one piece can be**: plywood top **96"** (4x8 sheet);
   solid surface **144"** (common sheet length, to confirm with our supplier).
2. **Put the seam on a cabinet joint**, so it sits over a strip and cabinet sides hold it up.
   When more than one joint fits, pick the one that makes the pieces **about equal**.
   If no joint is close enough, it seams at the max length and says "add support there".
3. **Laminate seam — Brook's method (this is how we do it):** "we always add another 6 inch
   strip of material on the seam, then router out the dogbone shape on both sides .5 inch deep
   to use dogbone clamps to firmly pull the two sides together into one continuous countertop.
   Adhesive is used." In the program: a **6" strip of 3/4" plywood centred on the seam**, cut
   at the seam so **each piece carries 3"** (glued and stapled), labels `CT1-BUJnA` / `CT1-BUJnB`;
   **dogbone pockets routed 1/2" deep** across the seam; adhesive in the seam; dogbone clamps
   pull it tight at install.
   - One 6" band split 3"/3" vs. a full 6" strip on each side **(to confirm)**.
   - Dogbone count: one per ~12" of strip, at least 2 (2 on a 25" counter) **(to confirm)**.
   - Laminate sheets run to 144", so the **laminate itself only seams past 144"**, and then
     at least 6" away from the plywood seam (WOODWEB) **(to confirm)**.
4. **Solid surface seam (manufacturer practice, to confirm with Brook)**: on a joint, over the
   1" ply joint stiffener (supported), hard seam with the maker's joint adhesive. Corian says a
   reinforcing strip under the seam is not needed in normal dry kitchens. **No dogbones or 6"
   strip** — that is Brook's laminate method only.
5. Not automated yet (no sinks or cooktops in the model): keep seams **off sink, cooktop and
   dishwasher** openings (Corian: at least 2-3" from a cutout, never over a dishwasher or heat
   source), and **away from inside corners** (Corian: at least 1-1/2"). Check these by hand.

Sources (quick check, 2026-10-24):
- WOODWEB, "Installing seamed countertops" — laminate seam at least 6" off the substrate seam
  (their cleat method is replaced by Brook's 6" strip + dogbones).
  https://woodweb.com/knowledge_base/Installing_seamed_countertops.html
- Customcraft laminate install guide — build-up strips each side of where cabinets meet;
  dual-action (tite-joint) fasteners at field joints, snug not over-tight.
  https://www.customcraftcountertops.com/CountertopsWebsite/web/cms/docs/LaminateInstallGuide2022V4.pdf
- Corian "Positioning of seams" (K-25288) — seams over support, not over a dishwasher or heat
  source; offset from inside corners. https://www.corian.com/sites/corian.com/IMG/pdf/k-25288-positioning-of-seams.pdf
- Corian "Requirements" (K-25705) / food service (K-30223) — reinforcement strip not required in
  dry residential use with Corian Joint Adhesive; seams 2" from cutout edges, over support.
  https://www.corian.com/sites/corian.com/IMG/pdf/k-25705-corian-solid-surface-requirements-102019.pdf
- Earlier light check on laminate practice (overhang, back strips, backer sheet): Lowe's laminate
  countertop guide and JLC; see ASSUMPTIONS in `cabgen/counter.py`.

---

## 4. Installation & site rules

- **Always measure the real-world space** the cabinet goes into. Rough framing is
  routinely out of square, so **revisit the space to sanity-check the opening** before
  committing to a cut.
- **1" spacer board** on the right or left of the cabinet (whichever is appropriate).
- If the counter butts against a wall on one side, **also add that 1" on the other side**
  when one side is open.
- Worked example: a **44" opening → a 43" cabinet case**, a **44" countertop**, and a
  **front spacer board** bridging the gap between the case side and the wall.
  - The spacer is nuanced and handled differently job to job — call it out on the drawing
    rather than assuming.
- The spacer piece sits at the **front** of the case and closes the gap to the wall.
- **Cabinets in a run sit tight side by side** (no gap, no joining hardware) and each is
  **screwed to the wall**. The generator places them touching. (Brook, 2026-10-23)

---

## 5. Deliverables for the carpenter

1. **2D drawings** (shop drawings) with the dimensions a carpenter needs, relevant to
   carpentry — not CAD ornament.
2. **Edge banding** called out per part and per edge.
3. **Cut list** for the table saw.
4. **Nesting plan (suggestion)** to preserve maximum material.

### Nesting
- Sheet stock is **4' x 8'** (48 x 96) for every material: melamine, MDF, birch plywood
  and others. Sheet size is a setting (`# sheet_w=48`, `# sheet_l=96` in a kitchen sheet,
  or `--sheet-w/--sheet-l`).
- **Kerf = 3/16"** (saw blade). Every cut eats 3/16" — the nesting plan must account for it
  (`# kerf=` / `--kerf`). The factory edge is used as is (no trim cut, for now).
- **Whole project, in cabinet order** (Brook, 2026-10-23): the first base cabinet's parts go
  on sheet 1, the next cabinet's parts fill the space left, and a new sheet opens only when
  nothing fits. Bases left to right, then uppers. Each material + thickness is its own nest.
- **Back panels are always 1/2"** and are nested across the whole project in their own
  separate nest and pages.
- **Shop workflow, guillotine only:** panel saw rips the 4x8 into full-length strips, each
  strip is crosscut into blocks, then the table saw rips a block to its part widths.
- **Fewest cuts beats least waste** when they disagree: same-width parts share one strip,
  same-length parts share one block, few rip widths.
- **Rotation:** melamine and MDF have no grain, so parts may turn 90 degrees (marked T).
  Grain materials (birch plywood, veneers) keep the part length along the 96" direction.
- **Offcuts are kept:** leftovers at least 4" each way are drawn and labeled "offcut W x L"
  on the sheet; smaller slivers are hatched as scrap. Offcut inventory/reuse: not yet.
- **Labels:** every part has a short unique label, cabinet + part code, e.g. B1-GL = base
  cabinet 1, gable left; U2-DR = upper 2, door right. The same label is on the nest PDF,
  the text cut list, and the part in the CAD model (Omacad).
- **Deliverables:** `<job>-nest.pdf` (summary page, then one 11x17 landscape page per sheet
  drawn at 1-1/2" = 1'-0", print at 100%), `<job>-nest-cutlist.md` (cut order per sheet:
  strips, then crosscuts, then table-saw rips) and `<job>-nest-cutlist.csv`.

---

## 6. Tooling & repo

- **Omacad** (`~/Work/omacad`) — native parametric 3D CAD for Omarchy; the 3D model home.
  `cabgen` writes a `.omacad` project with one named body per part (mm), so the 3D model
  and the cut list are the same cabinet.
- **cabgen** (`~/Work/cabinet-gen`) — CLI-first generator that emits the 2D shop drawings,
  cut list, nesting plan and the Omacad model. A local web form gives the dropdowns and
  dimension fields.
- Print target: **11x17 ANSI B landscape**. Carpenters get paper prints; PDF is required.
- Match the shop's existing print look — do not "modernize" it.
- See `cabinet-generator-context.md` for the wider project context and data plan.

---

## 7. Open questions / TBD (feed these back in)

1. **Is the 27" the case width or the overall width including the door overhang?**
   Assumption so far: 27" = case outer width; doors overlay 1/2" per side → 28" overall
   with doors, 28" countertop.
2. **Is 33.5" the overall height including the toe kick and the countertop?**
   Assumption so far: yes — 4" kick + 28" case + 1.5" counter build = 33.5".
3. **Is the 1/8" door gap total between the doors, or 1/8" per door (1/4" total)?**
   Literal reading (1/8" total) makes 13 15/16" doors; 1/4" total makes 13 7/8" doors,
   which is a simpler fraction for the cut list.
4. **Do the doors overlay the case bottom / top stretcher too**, or only the sides?
   Assumption so far: 1/2" side overhang only; doors stop at the case bottom and
   below the drawer with a 1/8" reveal.
5. **Is the back panel dadoed into the sides (sides 23.5" deep, back 26" wide) or
   applied on the back (sides 24" deep, back 27" wide)?**
   Assumption so far: dadoed (captured), which keeps the outer dimension exact.
6. ~~Backsplash height~~ — answered 2026-10-24: 4" backsplash, 4" side splash at wall ends (section 3).
7. **Drawer box material and construction** — 1/2" melamine boxes? Scribe/fit or
   adjustable slides? Default: 1/2" melamine, bottom-fit.
8. **Countertop MDF backer: strips or solid?** Default solid 1" MDF, and the top of the
   case is rabbeted to receive the Corian tongue.
9. **Toe-kick recess** from the case front (typical 3")? Default 3".
10. **Is there a left/right reveal-side laminate assignment rule per cabinet**, or is it
    chosen per job? Right side of this cabinet = laminate (reveal); left side = wall.
11. **Should the drawer front cover the 4" top stretcher?** The generator now shows the
    stretcher as a visible band above the drawer front (front 6" + rail 4" + doors
    13 7/8" inside a 24" opening). If the front must hide the stretcher, the front is
    4" + opening tall and the drawer opening gets shorter — say which and it is a
    one-line change.
12. **How many drawer rails?** Now one rail under the whole drawer stack. The shop rule
    "if there is a drawer or a door below the drawer, another stretcher is placed" is
    read as that one extra rail. Confirm.

---

## 8. Run ends, as discovered

This list is the rules named so far for a row of cabinets. It is not finished.
New ones get appended when they show up in a real kitchen. Do not invent the
next rule to fill a gap. Ask, or leave it unnamed.

The group form (`http://127.0.0.1:8777/run`) starts with one base and one upper.
A plus on a row adds one cabinet to that row only, with its own style and width.
Uppers and bases do not have to line up. Each row has its own offset from the
left wall, in inches, and that offset cannot go negative.

Base run, where it meets a wall:

- No wall. Both ends are open. The counter overhangs 1 inch on each end.
- One wall, on the left. The counter is flush with that wall. The open end
  overhangs 1 inch. A wall on the right is the mirror.
- Both walls. The two walls are fixed. Always add a filler on one side only,
  left or right, so the case is not pinched between them. The counter is flush
  with both walls, and it crosses the filler to reach the wall. The filler
  is 1, 2, or 3 inches. One inch is typical; three is the most.
- The filler is one board on that one end. It is not added to both ends, and
  it is not added on an open end.
- Uppers never get a filler. Fillers are for base runs only, on one side,
  left or right. (Brook, 2026-10-23)

Not decided yet, so the tool does not guess:

- How an upper run meets a wall (other than: no filler, ever).
- The counter as one solid across the whole base run. The numbers are stored
  and written in the layout. The Corian body is still off.
- Vanity, ADA vanity, sink, trash, and a 1-drawer 1-door base. They are not
  styles until a real model exists.

### Form default widths (Brook, 2026-10-24)
When a tile is added in CabCad, or its style is switched while the width box is empty
or still holds the old style's default, the width fills in with the style's stock size.
A width Brook typed is never overwritten. Constants `DEFAULT_WIDTH_*` / `DEFAULT_WIDTHS`
in `cabgen/params.py`. Common stock sizes, 3" steps:

| Style | Form key | Default | Why |
|---|---|---|---|
| Upper, 2 doors | `upper` | 30" | W3030 is the most common wall cabinet |
| Upper, 1 door | `upper1` | 18" | single doors are stock 9"-21"; 24" is the most. Wider is built as 2 doors, with a warning |
| Upper, open shelves | `open` | 24" | mid-size open shelf |
| Upper, microwave | `microwave` | 30" | fits a countertop microwave plus clearance; 12" box, shelf projects to 16-1/2" |
| Base, 3 drawers | `3drawer` | 18" | drawer bases are stock 12"-24"; 18" is the usual |
| Base, 1 drawer over 2 doors | `base` | 30" | always 2 doors here; 2-door bases are stock 24"-36" (24" doors only ~11-3/4") |
| Base, sink | `sink` | 30" | same as `base` for now (sink bases are commonly 30"-36") |

(The CLI/CSV still requires a width on every cabinet; these are form defaults only.)
