"""A kitchen is a spreadsheet of cabinets.

Each row is one cabinet. Width is the size you type. Height and depth stay at
the style (the current base is 33.5 high and 23.5 deep; a wall upper is 30 by
12) unless that cell is filled in.

Rows in the same run sit side by side, left to right. A `base` run stands on
the floor. An `upper` run hangs with its bottom at `upper_bottom` (54 inches
unless the sheet says otherwise) and its back on the same wall as the bases.

    python3 -m cabgen.cli kitchen jobs/one-cabinet.csv
    python3 -m cabgen.cli kitchen jobs/sample-kitchen.csv --out out/sample-kitchen
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, replace
from pathlib import Path

from .cutlist import to_csv
from .finishes import JOB_KEYS, job_top_spec, paint_boxes, paint_counter_boxes, row_finish
from .model3d import Box, HoleSpec, build_model
from .params import STYLE_PRESETS, Params, min_width
from .parts import build_parts
from .units import fmt_in

UPPER_BOTTOM = 54.0

# The words on the two rows. A base run sits on the floor. An upper run is the wall cabinets.
RUN_LABEL = {"base": "Base cabinets", "upper": "Uppers"}

STYLES = {
    "base": "base_1drawer_2doors",
    "base_1drawer_2doors": "base_1drawer_2doors",
    "1d2d": "base_1drawer_2doors",
    "1drawer": "base_1drawer_2doors",
    "3drawer": "base_3drawers",
    "3drawers": "base_3drawers",
    "base_3drawers": "base_3drawers",
    "sink": "base_sink",
    "base_sink": "base_sink",
    "sink_base": "base_sink",
    "upper": "upper_2doors",
    "upper_2doors": "upper_2doors",
    "2door": "upper_2doors",
    "upper1": "upper_1door",
    "upper_1door": "upper_1door",
    "1door": "upper_1door",
    "open": "upper_open",
    "upper_open": "upper_open",
    "shelves": "upper_open",
    "microwave": "upper_microwave",
    "upper_microwave": "upper_microwave",
    "mw": "upper_microwave",
}

RUNS = {
    "base": "base",
    "lower": "base",
    "floor": "base",
    "upper": "upper",
    "wall": "upper",
}


class KitchenError(ValueError):
    pass


@dataclass
class Cab:
    name: str
    params: Params
    run: str
    x: float
    y: float
    z: float
    gap_after: float


def load_kitchen(path: Path) -> tuple[dict, list[dict]]:
    """Settings from `# key=value` lines, then one dict per cabinet row."""
    text = path.read_text(encoding="utf-8")
    settings = {"upper_bottom": UPPER_BOTTOM}
    body: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            bit = line[1:].strip()
            if "=" in bit:
                key, value = bit.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key in ("upper_bottom", "upper_offset", "base_offset", "filler",
                           "sheet_w", "sheet_l", "kerf"):
                    settings[key] = _float(value, f"{path.name} {key}")
                elif key in ("base_walls", "filler_side", "counter", "splash_left", "splash_right"):
                    settings[key] = value
                elif key in JOB_KEYS:
                    settings[JOB_KEYS[key]] = value
            continue
        body.append(raw)
    if not body:
        raise KitchenError(f"{path} has no cabinet rows")
    rows = list(csv.DictReader(body))
    if not rows:
        raise KitchenError(f"{path} has a header but no cabinets")
    missing = {"name", "style", "width"} - set(rows[0])
    if missing:
        raise KitchenError(f"{path} is missing columns: {', '.join(sorted(missing))}")
    return settings, rows


def place_kitchen(rows: list[dict], settings: dict, source: str = "kitchen") -> list[Cab]:
    """Resolve defaults and pack each run left to right."""
    draft: list[dict] = []
    seen: dict[str, int] = {}
    for number, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            raise KitchenError(f"{source} line {number}: a cabinet needs a name")
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            name = f"{name}-{seen[name]}"
        style = _style((row.get("style") or "").strip(), source, number)
        run = _run((row.get("run") or "base").strip(), source, number)
        width = _float(row.get("width"), f"{source} line {number} width")
        if width < min_width(style):
            raise KitchenError(f"{source} line {number}: width {width} is under "
                               f"{min_width(style):g} inches")
        handle = (row.get("handle") or "").strip().lower() or "right"
        if handle in ("l", "r"):
            handle = {"l": "left", "r": "right"}[handle]
        if handle not in ("left", "right"):
            raise KitchenError(f"{source} line {number}: handle is left or right, not {handle!r}")
        height = _optional(row.get("height"), f"{source} line {number} height")
        depth = _optional(row.get("depth"), f"{source} line {number} depth")
        z = _optional(row.get("z"), f"{source} line {number} z")
        x = _optional(row.get("x"), f"{source} line {number} x")
        gap = _optional(row.get("gap_after"), f"{source} line {number} gap_after") or 0.0
        if run == "upper" and gap:
            raise KitchenError(f"{source} line {number}: uppers never get a filler, so leave gap_after blank")
        drawer_h = _optional(row.get("drawer_front_h"), f"{source} line {number} drawer_front_h")
        params = Params(style=style, name=name, width=width, height=height, depth=depth,
                        drawer_front_h=drawer_h, handle_side=handle,
                        finish_case=row_finish(row, "finish_case", settings.get("finish_case", "")),
                        finish_doors=row_finish(row, "finish_doors", settings.get("finish_doors", "")),
                        finish_top=row_finish(row, "finish_top", settings.get("finish_top", "")),
                        finish_interior=row_finish(row, "finish_interior", settings.get("finish_interior", "")))
        draft.append({
            "name": name, "params": params, "run": run,
            "x": x, "z": z, "gap_after": gap,
            "left": (row.get("left") or "").strip(),
            "right": (row.get("right") or "").strip(),
        })

    by_run: dict[str, list[dict]] = {"base": [], "upper": []}
    for item in draft:
        by_run[item["run"]].append(item)
    for run, items in by_run.items():
        _ends(items)
        cursor = 0.0
        for item in items:
            if item["x"] is None:
                item["x"] = cursor
            cursor = item["x"] + item["params"].width + item["gap_after"]
            if item["z"] is None:
                item["z"] = 0.0 if run == "base" else float(settings["upper_bottom"])

    wall = max((item["params"].depth for item in by_run["base"]), default=0.0)
    placed: list[Cab] = []
    for item in draft:
        depth = item["params"].depth
        y = (wall - depth) if item["run"] == "upper" and wall else 0.0
        placed.append(Cab(
            name=item["name"], params=item["params"], run=item["run"],
            x=item["x"], y=y, z=item["z"], gap_after=item["gap_after"],
        ))
    return placed


def scene_of(cabs: list[Cab], settings: dict | None = None) -> tuple[list[Box], list[HoleSpec], list]:
    """Every cabinet's solids, moved into kitchen coordinates, and one cut list."""
    boxes: list[Box] = []
    holes: list[HoleSpec] = []
    parts = []
    warnings: list[str] = []
    from .nest_project import box_labels, cabinet_codes, part_labels

    codes = cabinet_codes(cabs)
    for cab in cabs:
        built, layout = build_parts(cab.params)
        model = build_model(cab.params, layout)
        warnings.extend(paint_boxes(model.boxes, cab.params))
        # The cut-sheet label (B1-GL ...) leads each name so CAD matches the nest PDF.
        labels = box_labels([b.name for b in model.boxes], part_labels(codes[cab.name], built))
        for box, label in zip(model.boxes, labels):
            tag = f"{label} " if label else ""
            join = f"{tag}{cab.name} / {box.join}" if box.join else ""
            boxes.append(Box(
                f"{tag}{cab.name} / {box.name}",
                (box.pos[0] + cab.x, box.pos[1] + cab.y, box.pos[2] + cab.z),
                box.size, box.material, join, box.shape, box.color,
            ))
        for hole in model.holes:
            ox, oy, oz = hole.origin
            holes.append(HoleSpec(
                hole.diameter, hole.depth,
                (ox + cab.x, oy + cab.y, oz + cab.z),
                hole.normal,
            ))
        for part in built:
            parts.append(replace(part, name=f"{cab.name} / {part.name}"))
    if settings is not None:
        from .counter import build_counter
        counter = build_counter(cabs, settings)
        if counter:
            warnings.extend(paint_counter_boxes(counter.boxes, job_top_spec(cabs, settings)))
            boxes += counter.boxes
            for part, _labels in counter.parts():
                parts.append(replace(part, name=f"Countertop / {part.name}"))
    if settings is not None:
        seen: list[str] = []
        for warning in warnings:
            if warning not in seen:
                seen.append(warning)
        settings["finish_warnings"] = seen
    return boxes, holes, parts


def row_labels(cabs: list[Cab]) -> list[dict]:
    """One title in front of each row, in inches. The words sit just above that row."""
    labels = []
    for run, text in RUN_LABEL.items():
        continue  # Brook: no row titles in the model, bases or uppers (2026-10-23)
        row = [cab for cab in cabs if cab.run == run]
        if not row:
            continue
        left = min(cab.x for cab in row)
        right = max(cab.x + cab.params.width for cab in row)
        top = max(cab.z + cab.params.height for cab in row)
        front = min(cab.y for cab in row)
        span = right - left
        letter_h = 4.0
        labels.append({
            "text": text,
            "x": (left + right) / 2,
            "y": front - 1.0,
            "z": top + 6.0 + letter_h / 2,
            "height": letter_h,
            "depth": 0.35,
            # The words fill this box, so the title spans the row instead of sitting on one cabinet.
            "box": (span * 0.9, letter_h),
        })
    return labels


def layout_text(cabs: list[Cab], settings: dict) -> str:
    lines = [
        "# Kitchen layout",
        "",
        f"Wall-cabinet bottoms are at {fmt_in(settings['upper_bottom'])}.",
        "A blank height or depth kept the style's size. Backs of the uppers",
        "sit on the same wall as the deepest base.",
        "",
    ]
    if "base_walls" in settings:
        facts = end_facts(settings)
        lines.append(facts["text"])
        reach = _counter_reach(cabs, facts)
        if reach:
            lines.append(reach)
        lines.append("")
    lines += [
        "| Name | Run | Style | Width | Height | Depth | X | Y | Z |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    # Uppers on top, base cabinets below, like the form and the wall (Brook, 2026-10-24).
    for cab in sorted(cabs, key=lambda c: (c.run != "upper", c.x)):
        p = cab.params
        lines.append(
            f"| {cab.name} | {RUN_LABEL[cab.run]} | {STYLE_PRESETS[p.style]['label']} "
            f"| {fmt_in(p.width)} | {fmt_in(p.height)} | {fmt_in(p.depth)} "
            f"| {fmt_in(cab.x)} | {fmt_in(cab.y)} | {fmt_in(cab.z)} |"
        )
    lines.append("")
    return "\n".join(lines)


# The run form starts with one base and one upper. A plus on a row adds a
# cabinet to that row only. End rules for the base run are the ones discovered
# so far. More rules get added as they show up. See cabinet-shop-standards.md.
def posted_indexes(form, prefix: str) -> list[int]:
    """The column numbers posted for one row (bw1, bw2, ...), sorted. No upper limit
    (Brook, Oct 27: the old 8-cabinet cap is gone)."""
    if not form:
        return []
    pat = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    found = []
    for key in form:
        m = pat.match(str(key))
        if m and form.get(key) is not None and int(m.group(1)) >= 1:
            found.append(int(m.group(1)))
    return sorted(set(found))
OPEN_OVERHANG = 1.0
BASE_CHOICES = (
    ("3drawer", "3 drawers"),
    ("base", "1 drawer over 2 doors"),
    ("sink", "Sink: false drawer front over 2 doors"),
)
UPPER_CHOICES = (
    ("upper", "2 doors"),
    ("upper1", "1 door"),
    ("open", "Open shelves"),
    ("microwave", "Microwave shelf, 2 doors above"),
)
HANDLE_STYLES = {"upper1"}  # 1 door: pick the handle side; the hinges go on the other side
DRAWER_STYLES = {"base", "sink"}  # 1 drawer (or false front) over 2 doors; uppers never have drawers
DRAWER_HEIGHTS = (4, 5, 6, 7, 8)  # inches; 6 is typical
DRAWER_DEFAULT = 6
WALL_CHOICES = (
    ("0", "No wall"),
    ("left", "Left wall"),
    ("right", "Right wall"),
    ("both", "Both walls"),
)


FILLER_WIDTHS = (1.0, 2.0, 3.0)  # inches; 1 is typical, 3 is the most


def end_rule_text(walls: str, filler_side: str, filler: float) -> str:
    """The counter and filler sentence for one base run. This is the rule so far."""
    if walls == "0":
        return "Both ends are open. The counter overhangs 1 inch on each end."
    if walls == "left":
        return (
            "The left end is a wall, so the counter is flush there. "
            "The open right end overhangs 1 inch."
        )
    if walls == "right":
        return (
            "The right end is a wall, so the counter is flush there. "
            "The open left end overhangs 1 inch."
        )
    side = "left" if filler_side == "left" else "right"
    return (
        "Both ends are walls, so the counter is flush on both. "
        f"A {filler:g} inch filler goes on the {side}. "
        "The two walls are fixed, and the filler takes up the slack."
    )


def end_facts(settings: dict) -> dict:
    """Walls, filler, and the counter overhang at each end of the base run."""
    walls = str(settings.get("base_walls") or "left")
    if walls not in {key for key, _label in WALL_CHOICES}:
        raise KitchenError(f"wall choice {walls!r} is not one of the run ends")
    left_wall = walls in ("left", "both")
    right_wall = walls in ("right", "both")
    filler_side = str(settings.get("filler_side") or "")
    filler = float(settings.get("filler") or 0)
    if walls == "both":
        if filler_side not in ("left", "right"):
            filler_side = "right"
        if filler <= 0:
            filler = OPEN_OVERHANG
    else:
        filler_side = ""
        filler = 0.0
    return {
        "left_wall": left_wall,
        "right_wall": right_wall,
        "filler_side": filler_side,
        "filler": filler,
        "overhang_left": 0.0 if left_wall else OPEN_OVERHANG,
        "overhang_right": 0.0 if right_wall else OPEN_OVERHANG,
        "text": end_rule_text(walls, filler_side or "right", filler or OPEN_OVERHANG),
    }


def _counter_reach(cabs: list[Cab], facts: dict) -> str:
    bases = [cab for cab in cabs if cab.run == "base"]
    if not bases:
        return ""
    left = min(cab.x for cab in bases)
    right = max(cab.x + cab.params.width for cab in bases)
    if facts["filler_side"] == "left":
        start = left - facts["filler"]
    else:
        start = left - facts["overhang_left"]
    if facts["filler_side"] == "right":
        end = right + facts["filler"]
    else:
        end = right + facts["overhang_right"]
    return (
        f"Counter across the bases runs from {fmt_in(start)} to {fmt_in(end)} "
        f"({fmt_in(end - start)} overall)."
    )


def apply_discovered_rules(cabs: list[Cab], settings: dict) -> None:
    """Put the known end rules on the base run. Sheets without them stay as they were."""
    if "base_walls" not in settings:
        return
    facts = end_facts(settings)
    bases = [cab for cab in cabs if cab.run == "base"]
    last = len(bases) - 1
    for i, cab in enumerate(bases):
        params = cab.params
        params.left_side = "wall" if i > 0 or facts["left_wall"] else "open"
        params.right_side = "wall" if i < last or facts["right_wall"] else "open"
        params.counter_overhang_left = 0.0 if params.left_side == "wall" else OPEN_OVERHANG
        params.counter_overhang_right = 0.0 if params.right_side == "wall" else OPEN_OVERHANG
        params.has_spacer = False
        params.spacer_side = ""
        params.laminate_right_side = params.right_side != "wall"
    if facts["filler"] and bases:
        end = bases[0] if facts["filler_side"] == "left" else bases[last]
        end.params.has_spacer = True
        end.params.spacer_gap = facts["filler"]
        end.params.spacer_side = facts["filler_side"]


def group_sheet(cabinets: list[dict], settings: dict | None = None) -> str:
    """CSV for one group. Each row keeps its own x, measured from the left."""
    lines = ["# upper_bottom=54"]
    if settings:
        lines.append(f"# upper_offset={settings['upper_offset']:g}")
        lines.append(f"# base_offset={settings['base_offset']:g}")
        lines.append(f"# base_walls={settings['base_walls']}")
        if settings["base_walls"] == "both":
            lines.append(f"# filler_side={settings['filler_side']}")
            lines.append(f"# filler={settings['filler']:g}")
        if settings.get("counter"):
            lines.append(f"# counter={settings['counter']}")
            lines.append(f"# splash_left={settings.get('splash_left', 'yes')}")
            lines.append(f"# splash_right={settings.get('splash_right', 'yes')}")
        for key, label in (("finish_case", "case"), ("finish_doors", "doors"),
                           ("finish_top", "top"), ("finish_interior", "interior")):
            if settings.get(key):
                lines.append(f"# {label}={settings[key]}")
    lines.append("# Blank height and depth keep the style. x is the left edge of that cabinet.")
    lines.append("name,style,width,run,height,depth,x,drawer_front_h,handle")
    for cab in cabinets:
        drawer = cab.get("drawer")
        drawer_text = f"{drawer:g}" if drawer else ""
        lines.append(
            f"{cab['name']},{cab['style']},{cab['width']:g},{cab['run']},,,{cab['x']:g},"
            f"{drawer_text},{cab.get('handle') or ''}"
        )
    lines.append("")
    return "\n".join(lines)


def group_settings(form: dict) -> dict:
    """Offset of each row, and how the base run meets the walls."""
    walls = str(form.get("walls") or "left").strip()
    if walls not in {key for key, _label in WALL_CHOICES}:
        raise KitchenError(f"wall choice {walls!r} is not one of the run ends")
    filler_side = str(form.get("filler_side") or "right").strip()
    filler = 0.0
    if walls == "both":
        if filler_side not in ("left", "right"):
            raise KitchenError("the filler goes on the left or the right")
        raw = form.get("filler")
        filler = 1.0 if raw is None or str(raw).strip() == "" else _float(raw, "filler")
        if filler not in FILLER_WIDTHS:
            raise KitchenError("a filler is 1, 2, or 3 inches")
    else:
        filler_side = ""
    counter = str(form.get("counter") or "laminate").strip().lower()
    if counter not in ("laminate", "solid", "none"):
        raise KitchenError("the countertop is laminate, solid surface, or none")
    splash = {}
    for side in ("left", "right"):
        raw = str(form.get(f"splash_{side}") or "yes").strip().lower()
        if raw not in ("yes", "no"):
            raise KitchenError(f"side splash on the {side} is yes or no")
        splash[f"splash_{side}"] = raw
    finishes = {}
    for form_key, field in JOB_KEYS.items():
        raw = form.get(form_key)
        if field not in finishes and raw is not None and str(raw).strip():
            finishes[field] = str(raw).strip()
    return {
        "counter": counter,
        **splash,
        "upper_offset": _offset(form.get("uoff"), "upper offset from the wall"),
        "base_offset": _offset(form.get("boff"), "base offset from the wall"),
        "base_walls": walls,
        "filler_side": filler_side,
        "filler": filler,
        **finishes,
    }


def parse_group(form: dict) -> list[dict]:
    """Uppers and bases from the run form. The rows are separate."""
    settings = group_settings(form)
    bases = _members(form, "bw", "bs", "base cabinet", BASE_CHOICES, "3drawer", "bd")
    uppers = _members(form, "uw", "us", "upper", UPPER_CHOICES, "upper", "ud", "uh")
    if not bases and not uppers:
        raise KitchenError("add at least one cabinet")
    facts = end_facts(settings)
    x = settings["base_offset"]
    if facts["filler_side"] == "left":
        x += facts["filler"]
    cabinets: list[dict] = []
    for i, item in enumerate(bases, start=1):
        item["name"] = f"Base cabinet {i}"
        item["run"] = "base"
        item["x"] = x
        x += item["width"]
        cabinets.append(item)
    x = settings["upper_offset"]
    for i, item in enumerate(uppers, start=1):
        item["name"] = f"Upper {i}"
        item["run"] = "upper"
        item["x"] = x
        x += item["width"]
        cabinets.append(item)
    return cabinets


def _members(form, width_prefix, style_prefix, label, choices, default_style, drawer_prefix=None,
             handle_prefix=None) -> list[dict]:
    present = posted_indexes(form, width_prefix)
    if present and present != list(range(1, present[-1] + 1)):
        raise KitchenError(f"{label}s have a gap")
    allowed = {key for key, _name in choices}
    found = []
    for i in present:
        raw = form.get(f"{width_prefix}{i}")
        if str(raw).strip() == "":
            raise KitchenError(f"{label} {i} width is empty")
        width = _float(raw, f"{label} {i} width")
        style = str(form.get(f"{style_prefix}{i}") or default_style).strip()
        if style not in allowed:
            raise KitchenError(f"{label} {i}: unknown style {style!r}")
        least = min_width(STYLES.get(style, style))
        if width < least:
            raise KitchenError(f"{label} {i} width {width:g} is under {least:g} inches")
        handle = ""
        if style in HANDLE_STYLES:
            raw_h = form.get(f"{handle_prefix}{i}") if handle_prefix else None
            handle = str(raw_h or "right").strip().lower()
            if handle not in ("left", "right"):
                raise KitchenError(f"{label} {i}: the handle goes on the left or the right")
        drawer = None
        if style in DRAWER_STYLES:
            raw_d = form.get(f"{drawer_prefix}{i}") if drawer_prefix else None
            drawer = float(DRAWER_DEFAULT) if raw_d is None or str(raw_d).strip() == "" else _float(raw_d, f"{label} {i} drawer")
            if drawer not in DRAWER_HEIGHTS:
                raise KitchenError(f"{label} {i}: the drawer is 4 to 8 inches tall")
        found.append({"style": style, "width": width, "drawer": drawer, "handle": handle})
    return found


def _offset(cell, label: str) -> float:
    if cell is None or str(cell).strip() == "":
        return 0.0
    value = _float(cell, label)
    if value < 0:
        raise KitchenError(f"{label} can't start past the wall")
    return value


def run_sheet(widths: list[float]) -> str:
    """CSV for copies of the current 3-drawer base. Height and depth stay blank."""
    lines = [
        "# Copies of the current cabinet: base, 3 drawers.",
        "# Leave height and depth blank. The style stays 33.5 high and 23.5 deep.",
        "name,style,width,run,height,depth",
    ]
    for i, width in enumerate(widths, start=1):
        lines.append(f"Base cabinet {i},3drawer,{width:g},base,,")
    lines.append("")
    return "\n".join(lines)


def parse_run_widths(form: dict) -> list[float]:
    """Three or four widths from a form. Keys are count, w1, w2, w3, and w4."""
    raw_count = str(form.get("count") or "3").strip()
    try:
        count = int(raw_count)
    except ValueError:
        raise KitchenError(f"cabinet count {raw_count!r} is not 3 or 4") from None
    if count not in (3, 4):
        raise KitchenError("choose 3 or 4 cabinets")
    widths: list[float] = []
    for i in range(1, count + 1):
        cell = form.get(f"w{i}")
        label = f"cabinet {i} width"
        if cell is None or str(cell).strip() == "":
            raise KitchenError(f"{label} is empty")
        width = _float(cell, label)
        if width < 12:
            raise KitchenError(f"{label} {width:g} is under 12 inches")
        widths.append(width)
    return widths


def write_kitchen(sheet: Path, out_dir: Path, name: str, show: bool,
                  nest: dict | None = None) -> tuple[bool, str]:
    """Write the combined model, the cut list, and the layout. Open Omacad when `show`."""
    settings, rows = load_kitchen(sheet)
    settings.update({k: v for k, v in (nest or {}).items() if v is not None})
    cabs = place_kitchen(rows, settings, sheet.name)
    apply_discovered_rules(cabs, settings)
    boxes, holes, parts = scene_of(cabs, settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    from .counter import build_counter, counter_text
    counter = build_counter(cabs, settings)
    stem = name.lower().replace(" ", "-") or "kitchen"
    from .nest_project import KERF, SHEET_L, SHEET_W, NestError, nest_project, write_project_nest
    kerf = float(settings.get("kerf", KERF))
    try:
        groups = nest_project(cabs, float(settings.get("sheet_w", SHEET_W)),
                              float(settings.get("sheet_l", SHEET_L)), kerf,
                              extra=counter.parts() if counter else None)
    except NestError as exc:
        return False, f"nesting: {exc}"
    nest_files = write_project_nest(groups, out_dir, stem, name, cabs, kerf)
    counter_path = out_dir / f"{stem}-counter.md"
    if counter:
        counter_path.write_text(counter_text(counter), encoding="utf-8")
        nest_files.append(counter_path)
    elif counter_path.exists():
        counter_path.unlink()
    (out_dir / f"{stem}-layout.md").write_text(layout_text(cabs, settings), encoding="utf-8")
    (out_dir / f"{stem}-cutlist.csv").write_text(to_csv(parts), encoding="utf-8")
    model = out_dir / f"{stem}.omacad"
    from .omacad_export import export_scene
    ok, msg = export_scene(name, boxes, holes, model, row_labels(cabs))
    if not ok:
        return False, msg
    summary = [
        f"{name}: {len(cabs)} cabinets -> {out_dir}",
        f"  {out_dir / f'{stem}-layout.md'}",
        f"  {out_dir / f'{stem}-cutlist.csv'}",
        *[f"  {path}" for path in nest_files],
        "  sheets: " + ", ".join(f"{g.key} {len(g.sheets)}" for g in groups.values()),
        f"  {msg}",
        *[f"warning: {w}" for w in settings.get("finish_warnings") or []],
    ]
    if show:
        from .omacad_export import open_in_omacad
        opened, note = open_in_omacad(model)
        summary.append(note if opened else f"could not open: {note}")
        if not opened:
            return False, "\n".join(summary)
    return True, "\n".join(summary)


def _style(cell: str, source: str, line: int) -> str:
    key = cell.strip().lower().replace(" ", "_").replace("-", "_")
    if key in ("upper_drawer", "upper_1drawer_2doors"):
        raise KitchenError(f"{source} line {line}: uppers never have drawers. Use style upper (2 doors).")
    if key not in STYLES:
        known = ", ".join(sorted(set(STYLES)))
        raise KitchenError(f"{source} line {line}: unknown style {cell!r}. Use one of: {known}")
    return STYLES[key]


def _run(cell: str, source: str, line: int) -> str:
    key = cell.strip().lower()
    if key not in RUNS:
        raise KitchenError(f"{source} line {line}: run must be base or upper, not {cell!r}")
    return RUNS[key]


def _ends(items: list[dict]) -> None:
    """Buried sides stay plain. The two ends of a run match a lone cabinet: wall, then open."""
    last = len(items) - 1
    for i, item in enumerate(items):
        left = item["left"] or "wall"
        right = item["right"] or ("open" if i == last else "wall")
        item["params"].left_side = left
        item["params"].right_side = right
        item["params"].laminate_right_side = right != "wall"


def _optional(cell: str | None, label: str) -> float | None:
    if cell is None or str(cell).strip() == "":
        return None
    return _float(cell, label)


def _float(cell, label: str) -> float:
    try:
        return float(str(cell).strip())
    except (TypeError, ValueError):
        raise KitchenError(f"{label}: {cell!r} is not a number") from None
