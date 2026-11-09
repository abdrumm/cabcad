# CabCAD plans and future revisions

Brook's notes for upcoming work. Newest first. Build only what is listed; Brook will trim to bare minimums later.

## Nov 7, 2026 (after v0.15)

1. **Email draft window is unreadable.** The draft window background is white and so is the text. Change the text to black.
2. **Carpenter build drawings: overview page (11x17).** An experiment: a page for the carpenters with a big, readable front view of the full cabinet run with clear dimensions, plus a side view. It also needs details. Bare minimums to be decided later.
3. **Countertop page.** A dedicated page for the countertop with front view, top view, side view, and details. **Done** (2026-11-08): page 2 of the client sheet. Splashes are drawn in the countertop colour. Build-up, overhangs and dimensions are on the sheet.
4. **Standalone front-view page.** Make the front overview of the cabinets its own standalone page so it can be added to the CE pipeline page, with links to the render and the AR files. (For fun; Rick, Randy, and Andrew would enjoy it.) **Done** (2026-11-08): `cabgen.cli front` and the kitchen form's Front view button write an SVG, a PDF and an HTML page. The HTML links the render PNG and the AR files (USDZ and GLB) written beside it. A file that could not be written is a dashed placeholder link.
5. **Countertop buildup fix.** The buildup should not run over the interior cabinet seams. Run the buildup only around the perimeter of the countertop's underside, not across the seams between cabinets. **Done** (2026-11-08): solid-surface counters get 4" build-up strips of 1" plywood directly under the top, front, back and both ends only. **Nov 9:** laminate matches — front and end strips only, no strip on interior joints. Still no strip along the back wall (Oct 24).
