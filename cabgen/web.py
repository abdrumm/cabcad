"""A tiny local web form for the cabinet generator.

No dependencies: http.server + a form built from params.FORM_FIELDS.
Open http://127.0.0.1:8777/ , pick a style, set the dimensions, generate.
"""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .cli import generate
from .kitchen import (
    BASE_CHOICES, HANDLE_STYLES, KitchenError, STYLES, UPPER_CHOICES, posted_indexes, WALL_CHOICES,
    group_settings, parse_group, group_sheet, write_kitchen,
)
from .params import (
    DEFAULT_WIDTHS, FORM_FIELDS, Params, STYLE_PRESETS, UPPER_1DOOR_MAX_WIDTH, _coerce,
    door_rule_warnings,
)

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CabCad - cabinet shop drawings</title>
<style>
  :root {{ color-scheme: light dark; }}
  *, *::before, *::after {{ box-sizing: border-box; }}
  html {{ height: 100%; }}
  body {{ font-family: system-ui, sans-serif;
         font-size: clamp(14.5px, 0.15vw + 14px, 17px); line-height: 1.45;
         margin: 0 auto; padding: clamp(0.75rem, 2.2vw, 1.75rem);
         max-width: min(68rem, 100%); min-height: 100%; }}
  h1 {{ font-size: clamp(1.2rem, 1.1vw + 1rem, 1.7rem); margin: 0 0 .2rem;
       overflow-wrap: break-word; }}
  h2 {{ font-size: clamp(1.05rem, 0.5vw + 0.95rem, 1.35rem); overflow-wrap: break-word; }}
  p.sub {{ margin: 0 0 1.4rem; opacity: .7; max-width: 68rem; }}
  fieldset {{ border: 1px solid #8884; border-radius: 8px; margin: 0 0 1.2rem;
              padding: clamp(.6rem, 1.5vw, .9rem) clamp(.7rem, 2vw, 1rem) clamp(.7rem, 1.6vw, 1.1rem);
              min-width: 0; max-width: 100%; }}
  legend {{ font-weight: 600; padding: 0 .4rem; }}
  form {{ min-width: 0; max-width: 100%; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr));
           gap: clamp(.4rem, 1vw, .6rem) clamp(.6rem, 2vw, 1.2rem); }}
  .rowhead {{ display: flex; flex-wrap: wrap; gap: .4rem 1.4rem; align-items: end;
              justify-content: space-between; margin-bottom: .7rem; }}
  .rowname {{ font-weight: 650; font-size: clamp(.95rem, 0.4vw + .9rem, 1.15rem); }}
  .offset {{ width: min(9rem, 100%); }}
  .cards {{ display: flex; flex-wrap: wrap; gap: .8rem; align-items: end; min-width: 0; max-width: 100%; }}
  .card {{ width: min(11rem, 100%); max-width: 100%; }}
  button.plus {{ width: 2.7rem; height: 2.7rem; padding: 0; font-size: 1.5rem;
                 line-height: 1; }}
  button.quiet {{ background: transparent; color: inherit; }}
  button.del {{ margin-top: .4rem; padding: .25rem .7rem; font-size: .8rem; font-weight: 500; }}
  button:disabled {{ opacity: .45; cursor: default; }}
  .total {{ font-weight: 600; }}
  .ends {{ display: flex; flex-wrap: wrap; gap: .4rem 1.2rem; }}
  #end-rule {{ margin: .8rem 0 0; max-width: 68rem; }}
  label {{ display: block; font-size: .82rem; opacity: .85; margin-bottom: .15rem; }}
  input, select, textarea {{ width: 100%; max-width: 100%; padding: .35rem .5rem; border-radius: 5px;
                   border: 1px solid #8886; font: inherit; background: transparent;
                   color: inherit; }}
  input[type=checkbox], input[type=radio] {{ width: auto; }}
  .check {{ display: flex; align-items: center; gap: .45rem; margin-top: 1.1rem; flex-wrap: wrap; }}
  .check label {{ margin: 0; }}
  button {{ font: inherit; font-weight: 600; padding: .55rem 1.4rem; border-radius: 6px;
            border: 1px solid #8886; background: #3b82f6; color: #fff; cursor: pointer;
            max-width: 100%; }}
  .table-scroll {{ overflow-x: auto; max-width: 100%; margin-bottom: 1.2rem; }}
  .table-scroll table {{ margin-bottom: 0; width: max-content; min-width: 100%; max-width: none; }}
  .table-scroll th, .table-scroll td {{ white-space: nowrap; }}
  table {{ border-collapse: collapse; width: 100%; max-width: 100%; font-size: .86rem; margin-bottom: 1.2rem; }}
  th, td {{ text-align: left; padding: .3rem .5rem; border-bottom: 1px solid #8883; }}
  th {{ font-size: .76rem; text-transform: uppercase; letter-spacing: .04em; opacity: .7; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .files a {{ display: inline-block; margin: .2rem .5rem .2rem 0; max-width: 100%; overflow-wrap: anywhere; }}
  img {{ max-width: 100%; height: auto; }}
  img.preview {{ width: 100%; border: 1px solid #8884; border-radius: 6px; }}
  .warn {{ background: #f59e0b22; border: 1px solid #f59e0b66; padding: .5rem .7rem;
           border-radius: 6px; font-size: .85rem; max-width: 100%; overflow-wrap: break-word; }}
  ul {{ max-width: 100%; padding-left: 1.2rem; }}
  li {{ overflow-wrap: anywhere; }}
  @media (max-width: 40rem) {{
    h1 {{ font-size: clamp(1.15rem, 4.5vw, 1.45rem); }}
    button {{ padding: .5rem 1rem; }}
    .grid {{ gap: .45rem .65rem; }}
  }}
  @media (max-height: 800px) {{
    body {{ padding-block: clamp(0.45rem, 1.6dvh, 1rem); }}
    p.sub {{ margin-bottom: clamp(0.4rem, 1.6dvh, 1rem); }}
    fieldset {{ margin-bottom: clamp(0.45rem, 1.4dvh, 1rem); }}
  }}
  @media (min-width: 90rem) {{
    body {{ font-size: clamp(16px, 0.2vw + 15px, 18px); }}
  }}
</style>
</head>
<body>
{body}
<script>
const PRESETS = {presets};
const STYLE_KEYS = {style_keys};

function applyStyle(sel) {{
  const p = PRESETS[sel.value];
  if (!p) return;
  for (const [field, value] of Object.entries(p.dims)) {{
    const el = document.querySelector(`[name="${{field}}"]`);
    if (el) el.value = value;
  }}
  const counter = document.querySelector('[name="counter_depth"]');
  if (counter) counter.disabled = !p.has_counter;
}}

document.addEventListener('DOMContentLoaded', () => {{
  const sel = document.querySelector('[name="style"]');
  if (sel) {{ applyStyle(sel); sel.addEventListener('change', () => applyStyle(sel)); }}
}});
</script>
</body>
</html>
"""


def _field_html(field: dict, values: dict) -> str:
    name = field["name"]
    label = field["label"]
    kind = field["type"]
    val = values.get(name, "")
    if kind == "select":
        opts = "".join(
            '<option value="{v}"{sel}>{t}</option>'.format(
                v=html.escape(str(o["value"])),
                t=html.escape(str(o["label"])),
                sel=" selected" if str(o["value"]) == str(val) else "",
            )
            for o in field.get("options", [])
        )
        return f'<div><label for="f-{name}">{html.escape(label)}</label>' \
               f'<select id="f-{name}" name="{name}">{opts}</select></div>'
    if kind == "checkbox":
        checked = " checked" if val in (True, "on", "True", "true") else ""
        return (f'<div class="check"><input type="checkbox" id="f-{name}" '
                f'name="{name}"{checked}><label for="f-{name}">{html.escape(label)}</label></div>')
    step = ' step="0.0625"'
    return (f'<div><label for="f-{name}">{html.escape(label)}</label>'
            f'<input type="number" id="f-{name}" name="{name}" '
            f'value="{html.escape(str(val))}"{step}></div>')


def _form_html(values: dict) -> str:
    groups = [
        ("Job", [f for f in FORM_FIELDS if f["name"] in ("style", "name")]),
        ("Dimensions", [f for f in FORM_FIELDS
                        if f["type"] == "number" and f["name"] not in ("name",)]),
        ("Sides and construction", [f for f in FORM_FIELDS
                                    if f["type"] == "select" and f["name"] != "style"]),
        ("Finish", [f for f in FORM_FIELDS if f["type"] == "checkbox"]),
    ]
    out = ["<h1>cabgen</h1>",
           '<p class="sub">Cabinet shop drawings, cut list and nesting - '
           'local only, nothing leaves this machine. '
           '<a href="/run">Build a group of cabinets</a>.</p>',
           '<form method="post" action="/generate">']
    for legend, fields in groups:
        if not fields:
            continue
        out.append(f"<fieldset><legend>{legend}</legend><div class=\"grid\">")
        for f in fields:
            out.append(_field_html(f, values))
        out.append("</div></fieldset>")
    out.append('<button type="submit">Generate drawings</button>')
    out.append("</form>")
    return "".join(out)


def _result_html(p: Params, files: list[str], warnings: list[str], out_dir: Path) -> str:
    parts_rows = ""
    for f in files:
        parts_rows += (
            f'<tr><td><a href="/files/{html.escape(Path(f).name)}">'
            f'{html.escape(Path(f).name)}</a></td>'
            f'<td class="num">{html.escape(str(Path(f).stat().st_size))} B</td></tr>'
        )
    warn = ""
    if warnings:
        warn = ('<p class="warn"><strong>Check these:</strong><br>'
                + "<br>".join(html.escape(w) for w in warnings) + "</p>")
    preview = ""
    for f in files:
        if f.endswith("-drawing.svg"):
            preview = (f'<h2>Preview</h2><img class="preview" '
                       f'src="/files/{html.escape(Path(f).name)}" alt="drawing">')
    return "".join([
        "<h1>Generated</h1>",
        f'<p class="sub">{html.escape(p.name)} - {p.width:g}" x {p.height:g}" '
        f'({p.doors} door(s), {p.drawers} drawer(s))</p>',
        warn,
        preview,
        "<h2>Files</h2>",
        '<div class="table-scroll"><table><tr><th>File</th><th>Size</th></tr>'
        + parts_rows + "</table></div>",
        '<p><a href="/">&larr; back to the form</a></p>',
    ])


def _choice(name: str, selected: str, choices: tuple[tuple[str, str], ...], disabled: bool) -> str:
    opts = []
    for value, label in choices:
        sel = " selected" if value == selected else ""
        opts.append(
            f'<option value="{html.escape(value)}"{sel}>{html.escape(label)}</option>'
        )
    off = " disabled" if disabled else ""
    return f'<select id="{name}" name="{name}"{off}>{"".join(opts)}</select>'


def _width_input(name: str, label: str, value: str, disabled: bool) -> str:
    off = " disabled" if disabled else ""
    return (
        f'<label for="{name}">Width</label>'
        f'<input type="number" id="{name}" name="{name}" min="12" step="0.0625" '
        f'aria-label="{html.escape(label)}" value="{html.escape(value)}"{off}>'
        f'<span class="sub">inches</span>'
    )


# Tiles drawn ready on the page. Not a limit: the + button adds more past this.
SHOWN_COLUMNS = 8


def _at(values, i: int, default: str) -> str:
    """values[i-1], or the default when the list is short or missing."""
    return values[i - 1] if values and 0 < i <= len(values) else default


def _row_state(form, width_name, style_name, default_style, default_width, start, drawer_name="") -> dict:
    posted = posted_indexes(form, width_name) if form is not None else []
    n = max([SHOWN_COLUMNS] + posted)
    widths = [""] * n
    styles = [default_style] * n
    drawers = ["6"] * n
    count = start
    if form is None:
        widths[0] = default_width
        return {"count": count, "widths": widths, "styles": styles, "drawers": drawers}
    count = max(posted) if posted else 0
    for i in range(1, n + 1):
        if form.get(f"{width_name}{i}") is not None:
            widths[i - 1] = str(form.get(f"{width_name}{i}")).strip()
        if form.get(f"{style_name}{i}") is not None:
            styles[i - 1] = str(form.get(f"{style_name}{i}")).strip()
        if drawer_name and form.get(f"{drawer_name}{i}"):
            drawers[i - 1] = str(form.get(f"{drawer_name}{i}")).strip()
    return {"count": count, "widths": widths, "styles": styles, "drawers": drawers}


def group_view(form: dict | None) -> dict:
    """What the run form should show. A fresh page is one base and one upper."""
    view = {
        "bases": _row_state(form, "bw", "bs", "3drawer", "27", 1, "bd"),
        "uppers": _row_state(form, "uw", "us", "upper", "27", 1, "ud"),
        "walls": "left",
        "uoff": "0",
        "boff": "0",
        "filler_side": "right",
        "filler": "1",
        "counter": "laminate",
        "splash_left": "yes",
        "splash_right": "yes",
    }
    n = len(view["uppers"]["widths"])
    handles = ["right"] * n
    for i in range(1, n + 1):
        raw = str((form or {}).get(f"uh{i}") or "").strip().lower()
        if raw in ("left", "right"):
            handles[i - 1] = raw
    view["uppers"]["handles"] = handles
    if form:
        if form.get("walls"):
            view["walls"] = str(form.get("walls")).strip()
        if form.get("uoff") is not None:
            view["uoff"] = str(form.get("uoff")).strip()
        if form.get("boff") is not None:
            view["boff"] = str(form.get("boff")).strip()
        if form.get("filler_side"):
            view["filler_side"] = str(form.get("filler_side")).strip()
        if form.get("filler") is not None and str(form.get("filler")).strip() != "":
            view["filler"] = str(form.get("filler")).strip()
        for key in ("counter", "splash_left", "splash_right"):
            if form.get(key):
                view[key] = str(form.get(key)).strip()
    return view


COUNTER_CHOICES = (("laminate", "Laminate"), ("solid", "Solid surface"), ("none", "None"))

# Short face labels for the style buttons on a cabinet tile (the full name is the tooltip).
STYLE_SHORT = {"3drawer": "3 drawers", "base": "Drawer + doors", "sink": "Sink", "upper": "2 doors",
               "upper1": "1 door", "open": "Open", "microwave": "Microwave"}
_SVG = ('<svg class="ico" viewBox="0 0 24 30" aria-hidden="true" fill="none" '
        'stroke="currentColor" stroke-width="1.6" stroke-linecap="round">'
        '<rect x="1.5" y="1.5" width="21" height="27" rx="1.5"/>{}</svg>')
STYLE_ICONS = {
    "3drawer": _SVG.format('<path d="M1.5 10.5h21M1.5 19.5h21M9 6h6M9 15h6M9 24h6"/>'),
    "base": _SVG.format('<path d="M1.5 9h21M12 9v19.5M9 5.2h6M10 13v5M14 13v5"/>'),
    # sink: the same face with no pull on the false front
    "sink": _SVG.format('<path d="M1.5 9h21M12 9v19.5M10 13v5M14 13v5"/>'),
    "upper": _SVG.format('<path d="M12 1.5v27M10 21v4M14 21v4"/>'),
    # drawn handle RIGHT: pull by the right edge, dashed V pointing at the hinges (left).
    # The tile flips it (CSS) when its Handle toggle is L.
    "upper1": _SVG.format('<path d="M18.5 18.5v6.5" stroke-width="2.6"/><path d="M20 4L4 15l16 11" '
                          'stroke-dasharray="2 1.6" stroke-width="1"/>'),
    "open": _SVG.format('<path d="M1.5 10.5h21M1.5 19.5h21"/>'),
    "microwave": _SVG.format('<path d="M1.5 12h21M12 1.5V12M10 7v3M14 7v3"/>'
                             '<rect x="4.5" y="16" width="15" height="9" rx="1" stroke-width="1.2"/>'
                             '<path d="M16.5 18.5v4" stroke-width="1.2"/>'),
}


def _seg(name: str, current: str, choices, disabled: bool = False,
         icons: dict | None = None, label: str = "") -> str:
    """Segmented buttons in place of a dropdown. The value rides in a hidden
    input with the same name and id, so the posted form is unchanged."""
    off = " disabled" if disabled else ""
    btns = []
    for value, text in choices:
        on = value == current
        face = (icons or {}).get(value, "")
        short = STYLE_SHORT.get(value, text) if icons else text
        btns.append(
            f'<button type="button" class="segbtn{" on" if on else ""}" '
            f'data-v="{html.escape(value)}" title="{html.escape(text)}" '
            f'aria-pressed="{"true" if on else "false"}"{off}>'
            f'{face}<span>{html.escape(short)}</span></button>'
        )
    return (
        f'<input type="hidden" id="{name}" name="{name}" value="{html.escape(current)}"{off}>'
        f'<div class="seg{" many" if len(btns) > 3 else ""}" role="group" '
        f'aria-label="{html.escape(label or name)}" '
        f'data-for="{name}">{"".join(btns)}</div>'
    )


def _counter_fields(view: dict) -> str:
    """Countertop type, and a side splash at each wall end."""
    yes_no = (("yes", "Splash"), ("no", "None"))
    walls = view["walls"]
    left_hidden = "" if walls in ("left", "both") else " hidden"
    right_hidden = "" if walls in ("right", "both") else " hidden"
    return (
        '<div class="opt" id="counter-box"><span class="optlabel">Countertop</span>'
        f'{_seg("counter", view["counter"], COUNTER_CHOICES, label="Countertop")}</div>'
        f'<div class="opt" id="splash-left-box"{left_hidden}><span class="optlabel">Left wall side splash</span>'
        f'{_seg("splash_left", view["splash_left"], yes_no, label="Left wall side splash")}</div>'
        f'<div class="opt" id="splash-right-box"{right_hidden}><span class="optlabel">Right wall side splash</span>'
        f'{_seg("splash_right", view["splash_right"], yes_no, label="Right wall side splash")}</div>'
        '<script>(function () {'
        "function syncSplash() {"
        "  const w = (document.querySelector('input[name=\"walls\"]:checked') || {}).value || 'left';"
        "  const none = document.getElementById('counter').value === 'none';"
        "  document.getElementById('splash-left-box').hidden = none || !(w === 'left' || w === 'both');"
        "  document.getElementById('splash-right-box').hidden = none || !(w === 'right' || w === 'both');"
        "}"
        "document.querySelectorAll('input[name=\"walls\"]').forEach((el) => el.addEventListener('change', syncSplash));"
        "document.getElementById('counter').addEventListener('change', syncSplash);"
        "syncSplash();"
        '})();</script>'
    )


def _card(style_name, width_name, row, choices, noun, data_name, i, on, num=None) -> str:
    """One cabinet tile. `i` reads the row lists; `num` (default i) goes in the names,
    so the page template can be drawn with num="__N__"."""
    tag = "U" if data_name == "u" else "B"
    n = i if num is None else num
    hidden = "" if on else " hidden"
    off = "" if on else " disabled"
    wname = f"{width_name}{n}"
    return (
        f'<div class="card" data-{data_name}="{n}"{_handle_attr(row, i, data_name)}{hidden}>'
        f'<div class="cardhead" title="Drag to move this cabinet along the row">'
        f'<span class="tag"><span class="grip" aria-hidden="true">&#x2807;&#x2807;</span>{tag}{n}</span>'
        f'<button type="button" class="del" data-del-kind="{data_name}" data-del-index="{n}" '
        f'aria-label="Delete {html.escape(noun)} {n}" title="Delete {html.escape(noun.lower())} {n}">&times;</button></div>'
        f'{_seg(f"{style_name}{n}", row["styles"][i - 1], choices, not on, STYLE_ICONS, f"{noun} {n} style")}'
        f'<div class="w"><input type="number" id="{wname}" name="{wname}" '
        f'min="{9 if data_name == "u" else 12}" step="0.0625" '
        f'aria-label="{html.escape(f"{noun} {n} width, inches")}" '
        f'value="{html.escape(row["widths"][i - 1])}"{off}><span>in wide</span></div>'
        f'{_drawer_pick(style_name, i, row, not on, n)}'
        f'{_handle_pick(style_name, i, row, not on, n) if data_name == "u" else ""}'
        f'</div>'
    )


def _cards(style_name, width_name, row, choices, noun, data_name) -> str:
    """One tile per cabinet, left to right, plus a template the + button copies when
    the row grows past the tiles already on the page (no limit on cabinets)."""
    bits = [_card(style_name, width_name, row, choices, noun, data_name, i, i <= row["count"])
            for i in range(1, len(row["widths"]) + 1)]
    blank = {"styles": [row["styles"][-1]], "widths": [""], "drawers": ["6"], "handles": ["right"]}
    bits.append(f'<template id="{data_name}tpl">'
                + _card(style_name, width_name, blank, choices, noun, data_name, 1, False, "__N__")
                + "</template>")
    return "".join(bits)


def _wall_radios(selected: str) -> str:
    bits = []
    for value, label in WALL_CHOICES:
        checked = " checked" if value == selected else ""
        v = html.escape(value)
        bits.append(
            f'<input type="radio" id="walls-{v}" name="walls" value="{v}"{checked}>'
            f'<label for="walls-{v}">{html.escape(label)}</label>'
        )
    return '<div class="pills" role="radiogroup" aria-label="Run ends">' + "".join(bits) + "</div>"


RUN_CSS = """
<style>
  /* Group builder uses the monitor width, capped so a large iMac does not
     stretch the sentences across the whole panel. clamp(), min(), and dvh
     follow the window; nothing here is tuned to one machine. */
  body { max-width: min(140rem, 100%); margin-inline: auto;
         padding: clamp(.55rem, 1.4dvh, 1rem) clamp(.7rem, 1.8vw, 1.6rem) clamp(1rem, 2.4dvh, 2rem); }
  .cc { --line: #8885; --tile: #8881; --accent: #3b82f6; min-width: 0; }
  [hidden] { display: none !important; }
  .bar { display: flex; align-items: center; justify-content: space-between; gap: clamp(.5rem, 2vw, 1rem);
         flex-wrap: wrap; margin-bottom: .2rem; }
  .brand { font-size: clamp(1.2rem, 0.6vw + 1rem, 1.55rem); font-weight: 750; letter-spacing: .01em; }
  .brand .muted { font-size: clamp(.85rem, 0.3vw + .75rem, 1rem); font-weight: 500; opacity: .6; margin-left: .4rem; }
  .actions { display: flex; flex-wrap: wrap; gap: .5rem; }
  .actions button { padding: .45rem 1.1rem; }
  .actions button.ghost { background: transparent; color: inherit; }
  .arpanel { border: 1px solid var(--line, #8885); border-radius: 12px;
             padding: clamp(.5rem, 1.5vw, 1rem); margin: .9rem 0; min-width: 0; max-width: 100%; }
  .arpanel h2 { margin: .2rem 0 .4rem; }
  .arqr { display: flex; flex-wrap: wrap; gap: clamp(.6rem, 2vw, 1.2rem); align-items: center; }
  .arqr .qr { max-width: 100%; }
  .arqr .qr svg { width: min(180px, 42vw); height: auto; aspect-ratio: 1; background: #fff; border-radius: 8px; }
  .mono, .arpanel code { font-family: ui-monospace, monospace; font-size: .85rem; overflow-wrap: anywhere; }
  .lead, .foot, #end-rule { max-width: 68rem; }
  .lead { margin: .1rem 0 1rem; opacity: .65; font-size: .88rem; }
  .row { display: grid; grid-template-columns: minmax(9rem, 11.5rem) minmax(0, 1fr);
         gap: clamp(.6rem, 1.5vw, 1rem); align-items: stretch; min-width: 0;
         border: 1px solid var(--line); border-radius: 12px;
         padding: clamp(.5rem, 1.2vw, .8rem) clamp(.6rem, 1.5vw, 1rem); margin-bottom: .9rem; }
  .rowside { display: flex; flex-direction: column; gap: .35rem; border-right: 1px solid var(--line);
             padding-right: 1rem; min-width: 0; }
  .rowname { font-weight: 700; font-size: clamp(.95rem, 0.4vw + .9rem, 1.15rem); }
  .total { font-size: .86rem; font-weight: 600; opacity: .85; }
  .rowside label { font-size: .75rem; opacity: .7; margin: .3rem 0 0; }
  .rowside .link { margin-top: auto; }
  button.link { background: transparent; color: inherit; border: 0; padding: .1rem 0; font-size: .78rem;
                font-weight: 500; opacity: .6; text-align: left; text-decoration: underline; }
  button.link:hover { opacity: 1; }
  .cards { display: flex; flex-wrap: nowrap; gap: .6rem; align-items: stretch; overflow-x: auto;
           min-width: 0; max-width: 100%; padding-bottom: .35rem; }
  .card { flex: 1 1 0; min-width: min(8.6rem, 100%); max-width: 15rem; display: flex; flex-direction: column;
          gap: .45rem; border: 1px solid var(--line); border-radius: 10px; padding: .45rem .55rem .6rem;
          background: var(--tile); }
  .cardhead { display: flex; justify-content: space-between; align-items: center; gap: .3rem; }
  .tag { font-weight: 700; font-size: .8rem; opacity: .7; }
  .card button.del { background: transparent; color: inherit; border: 0; padding: 0 .3rem; margin: 0;
                     font-size: 1.1rem; line-height: 1; font-weight: 400; opacity: .45; }
  .card button.del:hover { opacity: 1; color: #ef4444; }
  button.plus { flex: 0 0 3.2rem; min-height: 6rem; height: auto; padding: 0; font-size: 1.7rem;
                font-weight: 300; background: transparent; color: inherit; border: 2px dashed var(--line);
                border-radius: 10px; }
  button.plus:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .seg { display: flex; flex-wrap: wrap; border: 1px solid var(--line); border-radius: 7px; overflow: hidden;
         width: max-content; max-width: 100%; }
  .card .seg { width: 100%; }
  .segbtn { flex: 1 1 0; display: flex; flex-direction: column; align-items: center; gap: .15rem;
            background: transparent; color: inherit; border: 0; border-right: 1px solid var(--line);
            border-radius: 0; padding: .28rem .6rem; font-size: .78rem; font-weight: 500; white-space: nowrap;
            min-width: 0; }
  .segbtn:last-child { border-right: 0; }
  .segbtn:hover:not(:disabled):not(.on) { background: #8882; }
  .segbtn.on { background: var(--accent); color: #fff; }
  .card .segbtn { padding: .3rem .2rem; font-size: .72rem; white-space: normal; text-align: center; line-height: 1.15; }
  .ico { width: 17px; height: 21px; flex: 0 0 auto; }
  .card .seg.many { display: grid; grid-template-columns: 1fr 1fr; }
  .card .seg.many .segbtn { border-bottom: 1px solid var(--line); }
  .card .seg.many .segbtn:nth-child(2n) { border-right: 0; }
  .card .seg.many .segbtn:nth-last-child(-n+2) { border-bottom: 0; }
  .handle-pick { display: flex; align-items: center; flex-wrap: wrap; gap: .4rem; max-width: 100%; }
  .ico { transition: transform .15s; }
  .card[data-handle="left"] .segbtn[data-v="upper1"] .ico { transform: scaleX(-1); }
  .handle-pick .optlabel { font-size: .75rem; }
  .card .handle-pick .seg { width: auto; }
  .card .handle-pick .segbtn { padding: .15rem .55rem; }
  .w { display: flex; align-items: center; gap: .35rem; max-width: 100%; }
  .w input { width: min(5rem, 100%); text-align: right; font-weight: 650; font-variant-numeric: tabular-nums; padding: .25rem .4rem; }
  .w span { font-size: .78rem; opacity: .6; white-space: nowrap; }
  .drawer-pick { display: flex; align-items: center; gap: .35rem; flex-wrap: wrap; }
  .drawer-pick label { margin: 0; font-size: .75rem; }
  .drawer-pick select { width: auto; max-width: 100%; padding: .15rem .3rem; font-size: .8rem; }
  .opts { display: flex; flex-wrap: wrap; align-items: center; gap: clamp(.5rem, 1.5vw, .7rem) clamp(.8rem, 2vw, 1.6rem);
          border: 1px solid var(--line); border-radius: 12px;
          padding: clamp(.55rem, 1.4vw, .75rem) clamp(.7rem, 1.6vw, 1rem); min-width: 0; }
  .opt { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; max-width: 100%; min-width: 0; }
  .optlabel { font-size: .8rem; opacity: .75; }
  .pills { display: inline-flex; flex-wrap: wrap; max-width: 100%; border: 1px solid var(--line); border-radius: 7px; overflow: hidden; }
  .pills input { position: absolute; opacity: 0; width: 1px; height: 1px; pointer-events: none; }
  .pills label { margin: 0; padding: .28rem .7rem; font-size: .8rem; opacity: 1; cursor: pointer;
                 border-right: 1px solid var(--line); }
  .pills label:last-child { border-right: 0; }
  .pills input:checked + label { background: var(--accent); color: #fff; }
  .pills input:focus-visible + label, .segbtn:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .cardhead { cursor: grab; touch-action: none; user-select: none; }
  .grip { opacity: .4; margin-right: .3rem; letter-spacing: -.2em; }
  .card.dragging { position: relative; z-index: 5; cursor: grabbing; background: Canvas;
                   box-shadow: 0 6px 18px #0004; transition: none; }
  .card.dragging .cardhead { cursor: grabbing; }
  .card.drop-before { box-shadow: -4px 0 0 0 var(--accent); }
  .card.drop-after { box-shadow: 4px 0 0 0 var(--accent); }
  .wire { border: 1px solid var(--line); border-radius: 12px;
          padding: clamp(.4rem, 1.2vw, .6rem) clamp(.6rem, 1.6vw, 1rem) .4rem;
          margin: .9rem 0; min-width: 0; max-width: 100%; }
  .wirehead { display: flex; flex-wrap: wrap; gap: .35rem .8rem; align-items: baseline; }
  /* Front view fills the width it is given and a slice of the window height.
     60vh up to 640px on a normal desktop. Short windows (the ~800-900px laptop)
     use the smaller slice in the max-height query so the form and the drawing
     share the screen. A wide short window puts the drawing beside the form.
     Vector art stays sharp; preserveAspectRatio meet keeps the aspect. */
  #wire { display: block; width: 100%; max-width: 100%;
          height: clamp(320px, 60vh, 640px);
          height: clamp(320px, min(60vh, 60dvh), 640px);
          max-height: min(80dvh, 900px); }
  #wire .wf-floor { stroke: currentColor; stroke-width: .6; }
  #wire .wf-wall { fill: #8884; stroke: currentColor; stroke-width: .35; }
  #wire .wf-case { fill: #8881; stroke: currentColor; stroke-width: .35; }
  #wire .wf-kick { fill: #8884; stroke: none; }
  #wire .wf-inside { fill: #8883; stroke: none; }
  #wire .wf-shelf { fill: #8886; stroke: currentColor; stroke-width: .2; }
  #wire .wf-front { fill: #3b82f61f; stroke: currentColor; stroke-width: .3; }
  #wire .wf-pull { stroke: currentColor; stroke-width: .55; stroke-linecap: round; }
  #wire .wf-swing { fill: none; stroke: currentColor; stroke-width: .18; stroke-dasharray: 1 .8; opacity: .7; }
  #wire .wf-mw { fill: #8885; stroke: currentColor; stroke-width: .25; }
  #wire .wf-mwwin { fill: #0003; stroke: currentColor; stroke-width: .15; }
  #wire .wf-filler { fill: #e6dccb88; stroke: currentColor; stroke-width: .3; }
  #wire .wf-counter { stroke: currentColor; stroke-width: .3; }
  #wire .wf-laminate { fill: #c9b48f; }
  #wire .wf-solid { fill: #e4e0d8; }
  #wire .wf-splash { fill: #8882; stroke: currentColor; stroke-width: .2; stroke-dasharray: 1 .6; }
  #wire .wf-tag { font: 700 3px system-ui, sans-serif; fill: currentColor; text-anchor: middle; }
  #wire .wf-dim { stroke: currentColor; stroke-width: .2; opacity: .7; }
  #wire .wf-dimtext { font: 2.6px system-ui, sans-serif; fill: currentColor; text-anchor: middle; opacity: .8; }
  .foot { margin: .6rem 0 0; font-size: .82rem; opacity: .65; }
  #end-rule { margin: .7rem 0 0; font-size: .85rem; }
  @media (max-width: 52rem) {
    .row { grid-template-columns: minmax(0, 1fr); }
    .rowside { border-right: 0; border-bottom: 1px solid var(--line); padding-right: 0; padding-bottom: .55rem; }
    .actions button { padding: .4rem .8rem; }
  }
  /* Owner's short-laptop slice, for a stacked page: smaller than 60vh so the
     drawing does not push the form into a long scroll. Wide short windows
     override this and park the drawing in the side column instead. */
  @media (max-height: 900px) {
    .lead { margin-bottom: .45rem; }
    .row { margin-bottom: .55rem; }
    .wire { margin: .55rem 0; }
    button.plus { min-height: 4.5rem; }
    #wire { height: clamp(240px, 45vh, 480px);
            height: clamp(240px, min(45vh, 45dvh), 480px); }
  }
  /* Wide and short (13-15" laptop, short desktop): the drawing sits beside the
     rows and uses the leftover height, instead of stacking under them. */
  .stage { min-width: 0; max-width: 100%; }
  .stage-main, .stage-notes { min-width: 0; max-width: 100%; }
  /* Up through a 1080p desktop: the drawing stays beside the rows so a 640px
     front view does not sit below the form and force a long scroll. Taller
     monitors (a 1440p iMac) keep the drawing full width under the form. */
  @media (min-width: 68rem) and (max-height: 1100px) {
    .stage { display: grid;
             grid-template-columns: minmax(0, 1.15fr) minmax(min(100%, 18rem), 0.95fr);
             grid-template-areas: "main wire" "notes notes";
             column-gap: clamp(.6rem, 1.4vw, 1.1rem); align-items: start; }
    .stage-main { grid-area: main; }
    .stage > .wire { grid-area: wire; position: sticky; top: .4rem; margin: 0;
                     align-self: start; max-height: calc(100dvh - .8rem); }
    .stage-notes { grid-area: notes; }
    .stage > .wire #wire { height: clamp(240px, min(68vh, 68dvh), 640px);
                           max-height: calc(100dvh - 8rem); }
  }
</style>
"""


WIRE_JS = r"""<script>
/* ---- live front view (wireframe), drawn from the form. Sizes come from WIRE (server). ---- */
const SVGNS = 'http://www.w3.org/2000/svg';
function wfVal(id) { const el = document.getElementById(id); return el ? el.value : ''; }
function wfRow(kind) {
  const out = [];
  document.querySelectorAll('.card[data-' + kind + ']').forEach((el) => {
    if (el.hidden) return;
    const i = el.dataset[kind];
    out.push({ tag: (kind === 'u' ? 'U' : 'B') + i, style: wfVal(kind + 's' + i),
               w: parseFloat(wfVal(kind + 'w' + i)) || 0, drawer: wfVal(kind + 'd' + i),
               handle: wfVal('uh' + i) === 'left' ? 'left' : 'right' });
  });
  return out;
}
function drawWire() {
  const svg = document.getElementById('wire');
  if (!svg || typeof WIRE === 'undefined') return;
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  const S = WIRE.styles;
  const el = (tag, attrs, parent) => {
    const n = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    (parent || svg).appendChild(n);
    return n;
  };
  const Y = (z) => -z;
  const rect = (x, z0, w, h, cls, parent) => el('rect', { x, y: Y(z0 + h), width: Math.max(w, 0), height: Math.max(h, 0), class: cls }, parent);
  const line = (x1, z1, x2, z2, cls) => el('line', { x1, y1: Y(z1), x2, y2: Y(z2), class: cls });
  const text = (x, z, s, cls) => { const t = el('text', { x, y: Y(z), class: cls }); t.textContent = s; return t; };

  const walls = (document.querySelector('input[name="walls"]:checked') || {}).value || 'left';
  const both = walls === 'both';
  const filler = both ? (parseFloat(wfVal('filler')) || 0) : 0;
  const fillerLeft = both && wfVal('filler_side') === 'left';
  const counter = wfVal('counter') || 'laminate';
  const uoff = parseFloat(wfVal('uoff')) || 0;
  const bases = wfRow('b'), uppers = wfRow('u');

  let x = fillerLeft ? filler : 0;
  bases.forEach((c) => { c.x = x; x += c.w; });
  const baseEnd = x + (both && !fillerLeft ? filler : 0);
  x = uoff;
  uppers.forEach((c) => { c.x = x; x += c.w; });
  const upperEnd = x;
  const baseTop = Math.max(0, ...bases.map((c) => (S[c.style] || {}).height || 0));
  const upperTop = Math.max(0, ...uppers.map((c) => WIRE.upper_bottom + ((S[c.style] || {}).height || 0)));
  const runR = Math.max(baseEnd, upperEnd, 12);
  const top = Math.max(upperTop, baseTop + 20) + 14;
  const leftWall = walls === 'left' || both, rightWall = walls === 'right' || both;
  const wallR = bases.length ? baseEnd : runR;
  svg.setAttribute('viewBox', `${-14} ${-top} ${runR + 28} ${top + 24}`);

  // floor and walls
  line(-10, 0, runR + 10, 0, 'wf-floor');
  if (leftWall) rect(-3, 0, 3, top - 6, 'wf-wall');
  if (rightWall) rect(wallR, 0, 3, top - 6, 'wf-wall');

  function pull(xc, z0, len, vertical) {
    if (vertical) line(xc, z0, xc, z0 + len, 'wf-pull');
    else line(xc - len / 2, z0, xc + len / 2, z0, 'wf-pull');
  }
  function cabinet(c, zBase, isUpper) {
    const s = S[c.style];
    if (!s || c.w <= 0) return;
    const g = el('g', { class: 'wf-cab' });
    const r = s.reveal, fw = c.w - 2 * r;
    rect(c.x, zBase + s.toe, c.w, s.height - s.toe, 'wf-case', g);
    if (s.toe) rect(c.x + s.t, zBase, c.w - 2 * s.t, s.toe, 'wf-kick', g);
    const f = (s.by_drawer && s.by_drawer[c.drawer]) || s;
    if (s.open) {
      rect(c.x + s.t, zBase + s.t, c.w - 2 * s.t, s.height - 2 * s.t, 'wf-inside', g);
      s.shelves.forEach((z) => rect(c.x + s.t, zBase + z, c.w - 2 * s.t, s.t, 'wf-shelf', g));
    }
    if (s.mw) {
      rect(c.x + s.t, zBase + s.mw[0], c.w - 2 * s.t, s.mw[1] - s.mw[0], 'wf-inside', g);
      const mw = Math.min(c.w - 4, 24), mh = Math.min(s.mw[1] - s.mw[0] - 3, 14);
      rect(c.x + (c.w - mw) / 2, zBase + s.mw[0], mw, mh, 'wf-mw', g);
      rect(c.x + (c.w - mw) / 2 + 1.5, zBase + s.mw[0] + 2, mw * 0.62, mh - 4, 'wf-mwwin', g);
      rect(c.x + s.t, zBase + s.mw[1], c.w - 2 * s.t, s.t, 'wf-shelf', g);
    }
    (f.drawers || []).forEach(([z0, z1]) => {
      rect(c.x + r, zBase + z0, fw, z1 - z0, 'wf-front', g);
      if (!s.false_front) pull(c.x + c.w / 2, zBase + (z0 + z1) / 2, WIRE.base_pull.span, false);
    });
    if (f.doors) {
      const [d0, d1] = f.doors;
      // Brook, 2026-10-30: a single-door upper wider than upper_1door_max is a pair.
      let n = s.ndoors;
      if (isUpper && n === 1 && c.w > WIRE.upper_1door_max) n = 2;
      const dw = (fw - s.gap * (n - 1)) / n;
      for (let k = 0; k < n; k += 1) {
        const dx = c.x + r + k * (dw + s.gap);
        rect(dx, zBase + d0, dw, d1 - d0, 'wf-front', g);
        if (isUpper) {
          const handleRight = n === 2 ? k === 0 : c.handle === 'right';
          const px = handleRight ? dx + dw - WIRE.upper_pull.inset : dx + WIRE.upper_pull.inset;
          pull(px, zBase + d0 + WIRE.upper_pull.from_bottom, WIRE.upper_pull.cc, true);
          if (n === 1) {
            const xh = handleRight ? dx + dw : dx, xg = handleRight ? dx : dx + dw;
            el('polyline', { points: `${xh},${Y(zBase + d1)} ${xg},${Y(zBase + (d0 + d1) / 2)} ${xh},${Y(zBase + d0)}`, class: 'wf-swing' }, g);
          }
        } else {
          const px = n === 2 ? c.x + c.w / 2 + (k === 0 ? -1 : 1) * WIRE.base_pull.off_center : dx + dw / 2;
          pull(px, zBase + d1 - WIRE.base_pull.from_top - WIRE.base_pull.span, WIRE.base_pull.span, true);
        }
      }
    }
    text(c.x + c.w / 2, isUpper ? zBase + s.height + 2.2 : -5.5, c.tag, 'wf-tag');
  }
  bases.forEach((c) => cabinet(c, 0, false));
  if (filler) rect(fillerLeft ? 0 : baseEnd - filler, 0, filler, baseTop, 'wf-filler');

  // countertop over the base run (and the filler), splashes
  if (counter !== 'none' && bases.length) {
    const L = (leftWall ? 0 : bases[0].x - WIRE.open_overhang);
    const R = (rightWall ? baseEnd : baseEnd + WIRE.open_overhang);
    const thk = WIRE.splash_thk[counter] || 0.75;
    rect(L, baseTop + WIRE.counter_edge, R - L, WIRE.splash_h, 'wf-splash');
    rect(L, baseTop, R - L, WIRE.counter_edge, 'wf-counter wf-' + counter);
    if (leftWall && wfVal('splash_left') !== 'no') rect(L, baseTop + WIRE.counter_edge, thk, WIRE.splash_h, 'wf-counter wf-' + counter);
    if (rightWall && wfVal('splash_right') !== 'no') rect(R - thk, baseTop + WIRE.counter_edge, thk, WIRE.splash_h, 'wf-counter wf-' + counter);
  }
  uppers.forEach((c) => cabinet(c, WIRE.upper_bottom, true));

  // overall widths
  function dim(x0, x1, z, label) {
    if (x1 <= x0) return;
    line(x0, z, x1, z, 'wf-dim');
    line(x0, z - 1.2, x0, z + 1.2, 'wf-dim');
    line(x1, z - 1.2, x1, z + 1.2, 'wf-dim');
    text((x0 + x1) / 2, z + 1.1, label, 'wf-dimtext');
  }
  if (uppers.length) dim(uppers[0].x, upperEnd, upperTop + 7, 'uppers ' + fmtIn(upperEnd - uppers[0].x));
  if (bases.length) dim(fillerLeft ? 0 : bases[0].x, baseEnd, -11, 'bases ' + fmtIn(baseEnd - (fillerLeft ? 0 : bases[0].x)));

  if (typeof syncDrawers === 'function') syncDrawers();
  const rule = document.getElementById('door-rule');
  if (rule) {
    const max = WIRE.upper_1door_max;
    const inches = (x) => fmtIn(x).split(' (')[0];
    const notes = [];
    uppers.forEach((c) => {
      const st = S[c.style];
      if (st && st.ndoors === 1 && c.w > max)
        notes.push('Warning: ' + c.tag + ' is ' + inches(c.w) + ' wide. A single-door upper is ' +
          inches(max) + ' at most (Brook). Asked for as one door; drawn as two doors.');
    });
    rule.hidden = notes.length === 0;
    rule.style.whiteSpace = 'pre-line';
    rule.textContent = notes.join('\n');
  }
}

/* ---- drag a tile by its header to move it along its own row ---- */
let DRAG = null;
function rowCards(kind) { return [...document.querySelectorAll('.card[data-' + kind + ']')].filter((c) => !c.hidden); }
function clearDrop() { document.querySelectorAll('.drop-before, .drop-after').forEach((c) => c.classList.remove('drop-before', 'drop-after')); }
function moveCabinet(kind, from, to) {
  const n = rowCards(kind).length;
  if (from < 1 || from > n || to < 1 || to > n || from === to) return;
  FIELDS[kind].forEach((prefix) => {
    const vals = [];
    for (let j = 1; j <= n; j += 1) { const e = document.getElementById(prefix + j); vals.push(e ? e.value : ''); }
    const [moved] = vals.splice(from - 1, 1);
    vals.splice(to - 1, 0, moved);
    for (let j = 1; j <= n; j += 1) { const e = document.getElementById(prefix + j); if (e) e.value = vals[j - 1]; }
  });
  setRow(kind, n);
}
function dragTarget(x) {
  const others = DRAG.mids.filter((m) => m.i !== DRAG.from);
  let k = 0;
  others.forEach((m) => { if (m.mid < x) k += 1; });
  clearDrop();
  if (others.length) {
    if (k < others.length) others[k].card.classList.add('drop-before');
    else others[others.length - 1].card.classList.add('drop-after');
  }
  return k + 1;
}
// Delegated, so tiles added past the drawn ones drag too.
document.addEventListener('pointerdown', (e) => {
    const head = e.target.closest('.card .cardhead');
    if (!head) return;
    if (e.button > 0 || e.target.closest('button')) return;
    const card = head.closest('.card');
    const kind = card.dataset.u ? 'u' : 'b';
    DRAG = { card, kind, from: Number(card.dataset[kind]), x0: e.clientX, to: null,
             mids: rowCards(kind).map((c) => { const b = c.getBoundingClientRect(); return { i: Number(c.dataset[kind]), mid: b.left + b.width / 2, card: c }; }) };
    try { head.setPointerCapture(e.pointerId); } catch (_) { /* synthetic pointer */ }
    card.classList.add('dragging');
    e.preventDefault();
});
document.addEventListener('pointermove', (e) => {
    if (!DRAG) return;
    DRAG.card.style.transform = 'translateX(' + (e.clientX - DRAG.x0) + 'px)';
    DRAG.to = dragTarget(e.clientX);
  });
  const end = () => {
    if (!DRAG) return;
    const d = DRAG;
    DRAG = null;
    d.card.classList.remove('dragging');
    d.card.style.transform = '';
    clearDrop();
    if (d.to && d.to !== d.from) moveCabinet(d.kind, d.from, d.to);
  };
document.addEventListener('pointerup', end);
document.addEventListener('pointercancel', end);
RUN_FORM.addEventListener('change', drawWire);
RUN_FORM.addEventListener('input', drawWire);
drawWire();
</script>
"""


RUN_JS = """
<script>
function syncSegs() {
  document.querySelectorAll('.seg').forEach((seg) => {
    const inp = document.getElementById(seg.dataset.for);
    if (!inp) return;
    seg.querySelectorAll('button').forEach((b) => {
      const on = b.dataset.v === inp.value;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.disabled = inp.disabled;
    });
  });
}
document.addEventListener('click', (ev) => {
  const b = ev.target.closest('.seg button');
  if (!b) return;
  const inp = document.getElementById(b.closest('.seg').dataset.for);
  if (!inp || inp.disabled) return;
  const old = inp.value;
  inp.value = b.dataset.v;
  const sm = /^([ub])s(\\d+)$/.exec(inp.id);
  if (sm && old !== inp.value) {
    // new style: fill its stock width, unless a width was typed (not empty, not the old default)
    const w = document.getElementById(sm[1] + 'w' + sm[2]);
    if (w && (w.value.trim() === '' || parseFloat(w.value) === DEFAULT_W[old])) w.value = DEFAULT_W[inp.value] || w.value;
  }
  syncSegs();
  inp.dispatchEvent(new Event('change', { bubbles: true }));
});
function setRow(kind, n) {
  n = Math.max(0, n);
  ensureCards(kind, n);
  document.querySelectorAll('[data-' + kind + ']').forEach((el) => {
    const on = Number(el.dataset[kind]) <= n;
    el.hidden = !on;
    el.querySelectorAll('input, select').forEach((inp) => { inp.disabled = !on; });
  });
  if (typeof syncDrawers === 'function') syncDrawers();
  document.getElementById(kind + 'drop').disabled = n <= 0;
  if (typeof syncTotals === 'function') syncTotals();
  syncSegs();
  if (typeof drawWire === 'function') drawWire();
}
const DEFAULT_W = DEFAULTW;
function ensureCards(kind, n) {
  // Tiles past the ones drawn on the page come from the row's template. No cap.
  const tpl = document.getElementById(kind + 'tpl');
  if (!tpl) return;
  let have = document.querySelectorAll('.card[data-' + kind + ']').length;
  while (have < n) {
    have += 1;
    const wrap = document.createElement('div');
    wrap.innerHTML = tpl.innerHTML.replace(/__N__/g, String(have));
    tpl.parentNode.insertBefore(wrap.firstElementChild, tpl);
  }
}
function addCabinet(kind, styleId, widthId, styleValue) {
  const cards = document.querySelectorAll('[data-' + kind + ']');
  let n = 0;
  cards.forEach((el) => { if (!el.hidden) n += 1; });
  const next = n + 1;
  ensureCards(kind, next);
  const style = document.getElementById(styleId + next);
  const width = document.getElementById(widthId + next);
  if (style) style.value = styleValue;
  if (width) width.value = DEFAULT_W[styleValue] || '';   // stock width for the style
  const handle = document.getElementById('uh' + next);
  if (kind === 'u' && handle) handle.value = 'right';   // a new tile starts with the handle right
  setRow(kind, next);
  if (width) { width.focus(); width.select(); }
}
function singleDoorUpperTooWide(styleEl) {
  // Same limit as UPPER_1DOOR_MAX_WIDTH, injected as WIRE.upper_1door_max.
  if (typeof WIRE === 'undefined' || WIRE.upper_1door_max == null) return false;
  if (!styleEl || styleEl.value !== 'upper1') return false;
  const m = /^us(\\d+)$/.exec(styleEl.id);
  if (!m) return false;
  const w = document.getElementById('uw' + m[1]);
  const width = w ? parseFloat(w.value) : NaN;
  return width > WIRE.upper_1door_max;
}
function syncDrawers() {
  document.querySelectorAll('.drawer-pick').forEach((box) => {
    const style = document.getElementById(box.dataset.styleFor);
    const card = box.closest('.card');
    const show = !!style && (style.value === 'base' || style.value === 'sink');
    box.hidden = !show;
    box.querySelectorAll('select').forEach((el) => { el.disabled = !show || (card && card.hidden); });
  });
  document.querySelectorAll('.handle-pick').forEach((box) => {
    const style = document.getElementById(box.dataset.styleFor);
    const card = box.closest('.card');
    let show = !!style && style.value === 'upper1';
    if (show && typeof singleDoorUpperTooWide === 'function' && singleDoorUpperTooWide(style)) show = false;
    box.hidden = !show;
    const inp = box.querySelector('input');
    if (card) card.dataset.handle = (inp && inp.value === 'left') ? 'left' : 'right';
    box.querySelectorAll('input').forEach((el) => { el.disabled = !show || (card && card.hidden); });
  });
  if (typeof syncSegs === 'function') syncSegs();
}
const FIELDS = { u: ['us', 'uw', 'ud', 'uh'], b: ['bs', 'bw', 'bd'] };
function deleteCabinet(kind, index) {
  let n = 0;
  document.querySelectorAll('[data-' + kind + ']').forEach((el) => { if (!el.hidden) n += 1; });
  if (index < 1 || index > n) return;
  for (let j = index; j < n; j += 1) {
    FIELDS[kind].forEach((prefix) => {
      const here = document.getElementById(prefix + j);
      const next = document.getElementById(prefix + (j + 1));
      if (here && next) here.value = next.value;
    });
  }
  setRow(kind, n - 1);
}
function dropCabinet(kind) {
  let n = 0;
  document.querySelectorAll('[data-' + kind + ']').forEach((el) => { if (!el.hidden) n += 1; });
  setRow(kind, n - 1);
}
function fmtIn(x) {
  const r = Math.round(x * 16) / 16;
  const whole = Math.floor(r);
  const frac = Math.round((r - whole) * 16);
  let f = '';
  if (frac) { let a = frac, b = 16; while (a % 2 === 0) { a /= 2; b /= 2; } f = ' ' + a + '/' + b; }
  let s = whole + f + '"';
  if (r >= 12) { const ft = Math.floor(r / 12); const rest = r - ft * 12; s += ' (' + ft + "' " + (Math.round(rest * 16) / 16) + '")'; }
  return s;
}
function rowSum(kind, widthId) {
  let sum = 0, n = 0;
  document.querySelectorAll('[data-' + kind + ']').forEach((el) => {
    if (el.hidden) return;
    const w = document.getElementById(widthId + el.dataset[kind]);
    const v = w ? parseFloat(w.value) : NaN;
    if (!isNaN(v)) { sum += v; n += 1; }
  });
  return { sum, n };
}
function syncTotals() {
  const u = rowSum('u', 'uw');
  const b = rowSum('b', 'bw');
  const both = document.getElementById('walls-both') && document.getElementById('walls-both').checked;
  const filler = both ? (parseFloat(document.getElementById('filler').value) || 0) : 0;
  document.getElementById('utotal').textContent = 'Uppers total: ' + fmtIn(u.sum);
  document.getElementById('btotal').textContent = 'Bases total: ' + fmtIn(b.sum + filler) + (filler ? ' (includes the ' + filler + '" filler)' : '');
}
function ruleText() {
  const walls = document.querySelector('input[name="walls"]:checked').value;
  const side = document.getElementById('filler_side').value === 'left' ? 'left' : 'right';
  const filler = document.getElementById('filler').value || '1';
  if (walls === '0') return 'Both ends are open. The counter overhangs 1 inch on each end.';
  if (walls === 'left') return 'The left end is a wall, so the counter is flush there. The open right end overhangs 1 inch.';
  if (walls === 'right') return 'The right end is a wall, so the counter is flush there. The open left end overhangs 1 inch.';
  return 'Both ends are walls, so the counter is flush on both. A ' + filler + ' inch filler goes on the ' + side + '. The two walls are fixed, and the filler takes up the slack.';
}
function syncEnds() {
  const both = document.getElementById('walls-both').checked;
  const box = document.getElementById('filler-box');
  box.hidden = !both;
  box.querySelectorAll('input, select').forEach((el) => { el.disabled = !both; });
  document.getElementById('end-rule').textContent = ruleText();
  syncSegs();
}
document.addEventListener('click', (ev) => {
  const b = ev.target.closest('button.del');
  if (b) deleteCabinet(b.dataset.delKind, Number(b.dataset.delIndex));
});
document.getElementById('uadd').addEventListener('click', () => addCabinet('u', 'us', 'uw', 'upper'));
document.getElementById('badd').addEventListener('click', () => addCabinet('b', 'bs', 'bw', '3drawer'));
document.getElementById('udrop').addEventListener('click', () => dropCabinet('u'));
document.getElementById('bdrop').addEventListener('click', () => dropCabinet('b'));
document.querySelectorAll('input[name="walls"]').forEach((el) => el.addEventListener('change', syncEnds));
document.getElementById('filler_side').addEventListener('change', syncEnds);
document.getElementById('filler').addEventListener('change', syncEnds);
const RUN_FORM = document.querySelector('form[action="/run"]');
RUN_FORM.addEventListener('input', syncTotals);
RUN_FORM.addEventListener('change', () => { syncDrawers(); syncTotals(); });
setRow('u', UCOUNT);
setRow('b', BCOUNT);
syncEnds();
syncTotals();
</script>
"""


def _filler_value(current) -> str:
    try:
        w = float(current)
    except (TypeError, ValueError):
        return "1"
    return str(int(w)) if w in (1.0, 2.0, 3.0) else "1"


def _run_fields(view: dict) -> str:
    """One base and one upper to start. A plus adds a cabinet to the right of that row."""
    uppers = _cards("us", "uw", view["uppers"], UPPER_CHOICES, "Upper", "u")
    bases = _cards("bs", "bw", view["bases"], BASE_CHOICES, "Base cabinet", "b")
    both = view["walls"] == "both"
    filler_hidden = "" if both else " hidden"
    side = "left" if view["filler_side"] == "left" else "right"
    filler_seg = _seg("filler", _filler_value(view["filler"]),
                      (("1", '1"'), ("2", '2"'), ("3", '3"')), not both, label="Filler width")
    side_seg = _seg("filler_side", side, (("left", "Left"), ("right", "Right")), not both,
                    label="Filler side")
    wire_data = "<script>const WIRE = " + json.dumps(_wire_data()) + ";</script>"
    js = (RUN_JS.replace("DEFAULTW", json.dumps(DEFAULT_WIDTHS))
          .replace("UCOUNT", str(view["uppers"]["count"]))
          .replace("BCOUNT", str(view["bases"]["count"])))
    door_notes = _upper_door_form_warnings(view)
    if door_notes:
        door_rule = ('<p class="warn" id="door-rule">'
                     + "<br>".join(html.escape(n) for n in door_notes) + "</p>")
    else:
        door_rule = '<p class="warn" id="door-rule" hidden></p>'
    return f"""{RUN_CSS}
<form method="post" action="/run" class="cc">
<header class="bar">
<div class="brand">CabCad<span class="muted">cabinet group</span></div>
<div class="actions">
<button type="submit">Show in Omacad</button>
<button type="submit" class="ghost" formaction="/client-sheet" formtarget="_blank">Client sheet (PDF)</button>
<button type="submit" class="ghost" formaction="/ar" title="Build the job for AR on a phone (iPhone and Android)">AR view</button>
</div>
</header>
<p class="lead">Each row builds left to right. The + adds a cabinet on the right end of that row.
Drag a cabinet by its label (U1, B1 ...) to move it along its row. Height and depth stay with the style.</p>
<div class="stage">
<div class="stage-main">
<section class="row" aria-label="Uppers">
<div class="rowside">
<div class="rowname">Uppers</div>
<div class="total" id="utotal"></div>
<label for="uoff">Offset from the left wall</label>
<div class="w"><input type="number" id="uoff" name="uoff" min="0" step="0.0625" value="{html.escape(view["uoff"])}"><span>in</span></div>
<button type="button" class="link" id="udrop">Remove last upper</button>
</div>
<div class="cards">{uppers}
<button type="button" class="plus" id="uadd" aria-label="Add an upper" title="Add an upper">+</button>
</div>
</section>
<section class="row" aria-label="Base cabinets">
<div class="rowside">
<div class="rowname">Base cabinets</div>
<div class="total" id="btotal"></div>
<input type="hidden" id="boff" name="boff" value="0">
<button type="button" class="link" id="bdrop">Remove last base</button>
</div>
<div class="cards">{bases}
<button type="button" class="plus" id="badd" aria-label="Add a base cabinet" title="Add a base cabinet">+</button>
</div>
</section>
<section class="opts" aria-label="Run ends and countertop">
<div class="opt"><span class="optlabel">Base run ends</span>{_wall_radios(view["walls"])}</div>
<div class="opt" id="filler-box"{filler_hidden}><span class="optlabel">Filler width</span>{filler_seg}<span class="optlabel">on the</span>{side_seg}</div>
{_counter_fields(view)}
</section>
</div>
<section class="wire" aria-label="Front view">
<div class="wirehead"><span class="rowname">Front view</span><span class="optlabel">simple wireframe, to scale, updates as you change the form</span></div>
<svg id="wire" role="img" aria-label="Front view of the cabinets" preserveAspectRatio="xMidYMid meet"></svg>
</section>
<div class="stage-notes">
{door_rule}
<p class="sub" id="end-rule">The left end is a wall, so the counter is flush there. The open right end overhangs 1 inch.</p>
<p class="foot">4" backsplash on the wall; open ends get a finished edge with a 1" overhang. The countertop and splashes are drawn, and their parts go in the cut list and nest.
Building takes about a minute; the model opens full screen on workspace 3.</p>
</div>
</div>
</form>
{wire_data}{js}{WIRE_JS}"""


def _layout_table(text: str) -> str:
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and all(set(c) <= set("-: ") and c for c in cells):
            continue
        rows.append(cells)
    if not rows:
        return ""
    head = "".join(f"<th>{html.escape(c)}</th>" for c in rows[0])
    body = ""
    for cells in rows[1:]:
        body += "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells) + "</tr>"
    return f'<div class="table-scroll"><table><tr>{head}</tr>{body}</table></div>'


NEST_LINKS = (
    ("-nest.pdf", "Nested cut sheets (PDF, print 11x17 at 100%)"),
    ("-nest-cutlist.md", "Nested cut list, cut order (text)"),
    ("-nest-cutlist.csv", "Nested cut list (CSV)"),
    ("-cutlist.csv", "Parts cut list (CSV)"),
)


def _nest_links(out_dir: Path, stem: str) -> str:
    """Links to the whole-group nest files that exist."""
    items = []
    for suffix, text in NEST_LINKS:
        if (out_dir / f"{stem}{suffix}").is_file():
            name = html.escape(f"{stem}{suffix}")
            items.append(f'<li><a href="/files/{name}" target="_blank">{html.escape(text)}</a></li>')
    return "<h2>Cut sheets</h2><ul>" + "".join(items) + "</ul>" if items else ""


def _run_page(view: dict, note: str = "", error: str = "", layout: str = "",
              links: str = "", ar: str = "") -> str:
    parts = [_run_fields(view)]
    if ar:
        parts.append(ar)
    if error:
        parts.append(f'<p class="warn">{html.escape(error)}</p>')
    if note:
        parts.append(f'<p class="sub">{html.escape(note)}</p>')
    if links:
        parts.append(links)
    if layout:
        parts.append("<h2>This run</h2>")
        parts.append(_layout_table(layout))
    parts.append('<p><a href="/">Single cabinet drawings</a></p>')
    return "".join(parts)


def _handle_run(form: dict, out_dir: Path) -> str:
    view = group_view(form)
    try:
        settings = group_settings(form)
        cabinets = parse_group(form)
    except KitchenError as exc:
        return _run_page(view, error=str(exc))
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet = out_dir / "base-run.csv"
    sheet.write_text(group_sheet(cabinets, settings), encoding="utf-8")
    ok, msg = write_kitchen(sheet, out_dir, "Base run", show=True)
    layout = ""
    layout_path = out_dir / "base-run-layout.md"
    if layout_path.is_file():
        layout = layout_path.read_text(encoding="utf-8")
    links = _nest_links(out_dir, "base-run")
    if not ok:
        return _run_page(view, error=msg, layout=layout, links=links)
    return _run_page(view, note=msg, layout=layout, links=links)


def _handle_client_sheet(form: dict, out_dir: Path) -> tuple[bytes | None, str]:
    """One-page client PDF for the group on the form. Omacad is not touched."""
    from .client_sheet import load_job, write_client_sheet

    view = group_view(form)
    try:
        settings = group_settings(form)
        cabinets = parse_group(form)
    except KitchenError as exc:
        return None, _run_page(view, error=str(exc))
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet = out_dir / "client-sheet.csv"
    sheet.write_text(group_sheet(cabinets, settings), encoding="utf-8")
    try:
        job = load_job(sheet, name=str(form.get("job") or "Cabinet group"))
        files = write_client_sheet(job, out_dir, "client-sheet", png=False)
    except (KitchenError, RuntimeError, OSError) as exc:
        return None, _run_page(view, error=f"client sheet: {exc}")
    return files["pdf"].read_bytes(), ""


def _handle_ar(form: dict, out_dir: Path, host: str, port: int) -> str:
    """Build the form's job as out/ar/cabcad.glb + .usdz and show the AR panel.
    Omacad is not touched."""
    from . import ar_web
    from .ar_export import export_job
    from .client_sheet import load_job

    view = group_view(form)
    try:
        settings = group_settings(form)
        cabinets = parse_group(form)
    except KitchenError as exc:
        return _run_page(view, error=str(exc))
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet = out_dir / "ar-view.csv"
    sheet.write_text(group_sheet(cabinets, settings), encoding="utf-8")
    title = str(form.get("job") or "Cabinet group")
    try:
        job = load_job(sheet, name=title)
        result = export_job(job, out_dir / ar_web.AR_DIR, ar_web.AR_STEM)
    except (KitchenError, RuntimeError, OSError, ValueError) as exc:
        return _run_page(view, error=f"AR view: {exc}")
    version = str(int(Path(result["usdz"]).stat().st_mtime))
    (out_dir / ar_web.AR_DIR / f"{ar_web.AR_STEM}.json").write_text(json.dumps(
        {"title": title, "version": version, "size_m": result["size_m"]}), encoding="utf-8")
    panel = ar_web.panel_html(result, version, ar_web.phone_base(host, port), port)
    return _run_page(view, ar=panel)


def _make_handler(out_dir: Path, host: str = "127.0.0.1", port: int = 8777):
    out_dir.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        server_version = "cabgen"

        def log_message(self, fmt: str, *args) -> None:  # quieter output
            print(f"  {self.address_string()} {fmt % args}")

        # -- helpers --------------------------------------------------------
        def _send(self, body: bytes, ctype: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            # Never let the browser reuse an old page or script: after a code update a
            # plain reload must show the new form (Brook, Oct 27: sink button missing).
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _html(self, body: str, status: int = 200) -> None:
            self._send(body.encode("utf-8"), "text/html; charset=utf-8", status)

        def _page(self, body: str) -> None:
            presets = {
                k: {
                    "has_counter": v["has_counter"],
                    "dims": {f: v[f] for f in ("width", "height", "depth", "drawer_front_h")
                             if f in v},
                }
                for k, v in STYLE_PRESETS.items()
            }
            self._html(PAGE.format(body=body, presets=json.dumps(presets),
                                   style_keys=json.dumps(list(STYLE_PRESETS))))

        def _local(self) -> bool:
            """Only this laptop may use the form. A phone on the LAN (--lan) gets /ar/ only."""
            from .ar_web import is_loopback
            return is_loopback(self.client_address[0])

        def _ar_get(self, path: str) -> None:
            from . import ar_web
            ar_dir = out_dir / ar_web.AR_DIR
            name = path[len("/ar/"):]
            if name == "preview.svg":
                self._send(ar_web.PREVIEW_SVG.encode("utf-8"), "image/svg+xml")
                return
            if name == "view":
                meta_path = ar_dir / f"{ar_web.AR_STEM}.json"
                if not meta_path.is_file():
                    self._html("<h1>No AR model yet</h1><p>Press AR view in CabCad first.</p>", 404)
                    return
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                base = f"http://{self.headers.get('Host') or f'{host}:{port}'}"
                self._html(ar_web.phone_page(base, meta["version"], meta["title"]))
                return
            target = (ar_dir / Path(name).name).resolve()
            if target.suffix not in (".glb", ".usdz") or not target.is_file():
                self._html("<h1>Not found</h1>", 404)
                return
            self._send(target.read_bytes(), ar_web.MIME[target.suffix])

        def do_HEAD(self) -> None:
            """Some phone viewers check a model with HEAD before fetching it."""
            from . import ar_web
            path = urlparse(self.path).path
            target = (out_dir / ar_web.AR_DIR / Path(path[len("/ar/"):]).name)
            if not path.startswith("/ar/") or target.suffix not in (".glb", ".usdz") or not target.is_file():
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", ar_web.MIME[target.suffix])
            self.send_header("Content-Length", str(target.stat().st_size))
            self.end_headers()

        # -- routes ---------------------------------------------------------
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path.startswith("/ar/"):
                self._ar_get(path)
                return
            if not self._local():
                self._html("<h1>Forbidden</h1><p>Only the AR pages are shared on the network.</p>", 403)
                return
            if path in ("/", "/index.html"):
                self._page(_form_html(defaults()))
                return
            if path == "/run":
                self._page(_run_page(group_view(None)))
                return
            if path.startswith("/files/"):
                name = Path(path[len("/files/"):]).name
                target = (out_dir / name).resolve()
                if not str(target).startswith(str(out_dir.resolve())) or not target.is_file():
                    self._html("<h1>Not found</h1>", 404)
                    return
                ctype = {
                    ".svg": "image/svg+xml",
                    ".pdf": "application/pdf",
                    ".csv": "text/csv; charset=utf-8",
                    ".md": "text/markdown; charset=utf-8",
                    ".txt": "text/plain; charset=utf-8",
                    ".json": "application/json",
                }.get(target.suffix, "application/octet-stream")
                self._send(target.read_bytes(), ctype)
                return
            self._html("<h1>Not found</h1>", 404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if not self._local():
                self._html("<h1>Forbidden</h1>", 403)
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8")
            form = {k: v[0] for k, v in parse_qs(raw).items()}
            if path == "/run":
                self._page(_handle_run(form, out_dir))
                return
            if path == "/ar":
                self._page(_handle_ar(form, out_dir, host, port))
                return
            if path == "/client-sheet":
                pdf, page = _handle_client_sheet(form, out_dir)
                if pdf is None:
                    self._page(page)
                else:
                    self._send(pdf, "application/pdf")
                return
            if path != "/generate":
                self._html("<h1>Not found</h1>", 404)
                return
            p = params_from_form(form)
            result = generate(p, out_dir, with_omacad=True)
            warnings = [str(u) for u in result["uncuttable"]]
            warnings += list(result.get("warnings", []))
            warnings += list(getattr(result["layout"], "assumptions", []))
            deduped: list[str] = []
            for w in warnings:
                if w not in deduped:
                    deduped.append(w)
            self._page(_result_html(p, result["written"], deduped, out_dir))

    return Handler


def defaults() -> dict:
    p = Params()
    vals = {f["name"]: getattr(p, f["name"]) for f in FORM_FIELDS}
    vals["style"] = p.style
    return vals


def params_from_form(form: dict) -> Params:
    """Turn posted form values into a Params object."""
    style = form.get("style") or Params().style
    if style not in STYLE_PRESETS:
        style = Params().style
    base = Params(style=style)
    data = {"style": style}
    for f in FORM_FIELDS:
        name = f["name"]
        if name == "style":
            continue
        if f["type"] == "checkbox":
            data[name] = name in form
        elif name in form and form[name] != "":
            data[name] = _coerce(form[name])
    p = Params.from_dict({**base.to_dict(), **data})
    p.apply_style(style, only_missing=True)
    return p


def serve(host: str = "127.0.0.1", port: int = 8777, out_dir: Path | None = None) -> None:
    out_dir = out_dir or Path("out")
    # Threaded, so an idle browser connection (Chromium preconnect) can't freeze the form.
    handler = _make_handler(out_dir, host, port)
    handler.timeout = 30  # drop sockets that send nothing
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    print(f"cabgen on http://{host}:{port}/  (files -> {out_dir.resolve()})")
    from .ar_web import phone_base
    if phone_base(host, port):
        print(f"LAN: phones can open {phone_base(host, port)}/ar/view (AR pages only)")
    print("Ctrl-C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        httpd.server_close()


def _filler_options(current) -> str:
    """Filler widths for a base run: 1, 2, or 3 inches. 1 is typical."""
    try:
        cur = float(current)
    except (TypeError, ValueError):
        cur = 1.0
    out = []
    for w in (1, 2, 3):
        sel = " selected" if cur == w else ""
        out.append(f'<option value="{w}"{sel}>{w} inch</option>')
    return "".join(out)


DRAWER_FIELD = {"bs": "bd", "us": "ud"}
DRAWER_STYLE_VALUES = ("base", "sink")


def _drawer_pick(style_name: str, i: int, row: dict, card_off: bool, num=None) -> str:
    """Drawer height for the 1 drawer over 2 doors styles. 6 inches is typical."""
    n = i if num is None else num
    field = f"{DRAWER_FIELD[style_name]}{n}"
    shown = row["styles"][i - 1] in DRAWER_STYLE_VALUES
    hidden = "" if shown else " hidden"
    off = " disabled" if card_off or not shown else ""
    current = _at(row.get("drawers"), i, "6")
    opts = "".join(
        f'<option value="{h}"{" selected" if str(h) == str(current).rstrip("0").rstrip(".") or (str(h) == current) else ""}>{h}&quot;</option>'
        for h in (4, 5, 6, 7, 8)
    )
    return (
        f'<div class="drawer-pick" data-style-for="{style_name}{n}"{hidden}>'
        f'<label for="{field}">Drawer</label>'
        f'<select id="{field}" name="{field}"{off}>{opts}</select></div>'
    )


def _upper_door_form_warnings(view: dict) -> list[str]:
    """Warnings for 1-door uppers the form is about to build wider than 24\"."""
    notes: list[str] = []
    row = view["uppers"]
    for i in range(1, int(row["count"]) + 1):
        raw = _at(row["widths"], i, "")
        if str(raw).strip() == "":
            continue
        try:
            width = float(raw)
        except ValueError:
            continue
        style = str(_at(row["styles"], i, "upper")).strip().lower().replace(" ", "_").replace("-", "_")
        resolved = STYLES.get(style)
        if not resolved:
            continue
        p = Params(style=resolved, name=f"Upper {i}", width=width)
        notes.extend(door_rule_warnings(p))
    return notes


def _handle_pick(style_name: str, i: int, row: dict, card_off: bool, num=None) -> str:
    """1-door upper: which side the handle goes on. The hinges go on the other side."""
    n = i if num is None else num
    field = f"uh{n}"
    shown = row["styles"][i - 1] in HANDLE_STYLES
    if shown:
        raw_w = _at(row.get("widths"), i, "")
        try:
            if float(raw_w) > UPPER_1DOOR_MAX_WIDTH:
                shown = False   # over 24" it is a pair; the handle side does not apply
        except (TypeError, ValueError):
            pass
    hidden = "" if shown else " hidden"
    current = _at(row.get("handles"), i, "right") or "right"
    return (
        f'<div class="handle-pick" data-style-for="{style_name}{n}"{hidden}>'
        f'<span class="optlabel">Handle</span>'
        f'{_seg(field, current, (("left", "L"), ("right", "R")), card_off or not shown, label=f"Upper {n} handle side")}'
        f'</div>'
    )


def _handle_attr(row: dict, i: int, data_name: str) -> str:
    """data-handle on an upper tile, so the 1-door icon shows the handle on that side."""
    if data_name != "u":
        return ""
    side = _at(row.get("handles"), i, "right") or "right"
    return f' data-handle="{"left" if side == "left" else "right"}"'


def _wire_data() -> dict:
    """Sizes the front-view wireframe needs, taken from the same code that builds the
    cabinets, so the page does not keep its own copy of the numbers."""
    from .counter import EDGE, OPEN_OVERHANG as CT_OVERHANG, SPLASH_H
    from .kitchen import DRAWER_HEIGHTS, DRAWER_STYLES, STYLES, UPPER_BOTTOM
    from .params import (Params, UPPER_1DOOR_MAX_WIDTH, UPPER_PULL_CC, UPPER_PULL_EDGE_INSET,
                         UPPER_PULL_FROM_BOTTOM)
    from .parts import build_parts, open_shelf_z

    def fronts(p: Params) -> dict:
        _parts, lay = build_parts(p)
        return {
            "drawers": [[round(a, 4), round(b, 4)] for a, b in lay.drawer_bands],
            "doors": [lay.door_bottom_z, lay.door_top_z] if lay.door_heights else None,
        }

    styles = {}
    for key, _label in BASE_CHOICES + UPPER_CHOICES:
        p = Params(style=STYLES[key])
        info = {
            "height": p.height, "depth": p.depth, "t": p.carcass_thk,
            "toe": p.toe_kick_h if p.has_toe_kick else 0.0,
            "reveal": p.edge_reveal, "gap": p.door_gap, "ndoors": p.doors,
            "open": p.open_shelves > 0, "shelves": open_shelf_z(p),
            "mw": [p.case_bottom_z + p.carcass_thk, p.mw_divider_z] if p.is_microwave else None,
            "false_front": bool(p.sink),
            **fronts(p),
        }
        if key in DRAWER_STYLES:
            info["by_drawer"] = {
                str(h): fronts(Params(style=STYLES[key], drawer_front_h=float(h)))
                for h in DRAWER_HEIGHTS
            }
        styles[key] = info
    ref = Params()
    return {
        "styles": styles,
        "upper_bottom": UPPER_BOTTOM,
        "upper_1door_max": UPPER_1DOOR_MAX_WIDTH,
        "counter_edge": EDGE,
        "splash_h": SPLASH_H,
        "splash_thk": {"laminate": 0.75, "solid": 0.5},   # as counter.Counter.splash_thk
        "open_overhang": CT_OVERHANG,
        "upper_pull": {"cc": UPPER_PULL_CC, "from_bottom": UPPER_PULL_FROM_BOTTOM,
                       "inset": UPPER_PULL_EDGE_INSET},
        "base_pull": {"span": ref.pull_span, "from_top": ref.pull_from_top,
                      "off_center": ref.pull_off_center},
    }
