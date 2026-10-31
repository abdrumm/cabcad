# CabCad finishes

- `catalog.json`: the starter finishes (13): laminate solids (white, black, gray, navy, sage),
  laminate wood looks (maple, white oak, walnut, birch ply) and solid-surface looks
  (solid white, warm gray, gray-veined quartz look, concrete gray look).
  Names are generic. `close_to` stays empty unless a finish is a real match to a brand
  colour (e.g. "close to Wilsonart 7972-60"). No brand images or files are shipped.
- `custom.json`: finishes added with "Add custom finish" on the form (name, code, colour).
  Flagged `custom: true` and `on_estimate: false`; the assistant researches and matches a
  CC0 look-alike later.
- Each entry: id, name, kind (`laminate` | `solid_surface`), family, color (sRGB hex; for a
  texture it is the texture's average), roughness (0-1), texture (path or null),
  tile_in ([w, h] inches one tile covers), source, license, close_to, on_estimate.

## Texture sources (all CC0 1.0, public domain; https://docs.ambientcg.com/license/)

Downloaded Oct 30, 2026 as the 1K-JPG pack, colour map only, resized to 512 px and
re-saved at JPEG quality 82 (woods rotated 90 degrees so the grain runs vertically on doors).

| File | ambientCG asset | Used for |
|---|---|---|
| textures/maple.jpg | Wood048 https://ambientcg.com/a/Wood048 | Maple look |
| textures/white-oak.jpg | Wood049 https://ambientcg.com/a/Wood049 | White oak look |
| textures/walnut.jpg | Wood027 https://ambientcg.com/a/Wood027 | Walnut look |
| textures/birch-ply.jpg | Wood090A https://ambientcg.com/a/Wood090A | Birch ply look |
| textures/white-quartz.jpg | Marble012 https://ambientcg.com/a/Marble012 | Gray-veined quartz look |
| textures/concrete-gray.jpg | Concrete034 https://ambientcg.com/a/Concrete034 | Concrete gray look |

Total 236 KB, so the USDZ stays email-friendly.
