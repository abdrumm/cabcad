"""Which edges of a part get color-matched PVC edge banding.

Brook: change the table below. The first row that matches the part name wins.
A more specific row has to sit above a general one.

The code is four characters, ``L1 L2 W1 W2``:

- Lay the part on the bench the way the nest draws it when it is not turned:
  the cut-list LENGTH runs left to right, the WIDTH runs up and down.
- L1 is the top edge of that rectangle (one edge that runs with the length).
- L2 is the bottom edge.
- W1 is the left end.
- W2 is the right end.
- A ``1`` gets PVC. A ``0`` does not.

On a base gable the rectangle is the blank. The toe-kick notch is then cut
out of that one piece (it is not a solid panel, and it is not a second
board). ``N1`` is the top of that notch, the edge you see inside the kick.
The drawing stops the front band where the notch starts.

Banding is 0.5–2 mm and does not change the stated size of the part.
Edges that get a laminate skin over them (counter edges, splash edges) do
not get PVC. The back edge, and any edge buried against the next cabinet or
the wall, do not get PVC.
"""

from __future__ import annotations

from dataclasses import dataclass

from .finishes import lookup


@dataclass(frozen=True)
class EdgeRule:
    match: str          # start of the part name, lower case
    run: str            # "" any, "base", or "upper"
    mask: str           # L1 L2 W1 W2, each 0 or 1
    words: str          # carpenter words
    notch: bool = False # base gable: also band the top of the toe-kick notch


# First match wins. Put the specific row above the general one.
EDGE_TABLE: tuple[EdgeRule, ...] = (
    EdgeRule(
        "gable", "upper", "1110",
        "Upper side: front (W1), top (L1) and bottom (L2). The back (W2) is against the wall.",
    ),
    EdgeRule(
        "gable", "base", "0010",
        "Base side, one piece with the toe-kick notch cut out: front edge above the notch (W1) "
        "and the top of the notch (N1). The back, the floor edge, and the back of the notch "
        "(behind the kick plate) are not banded. This is not a solid rectangle.",
        notch=True,
    ),
    EdgeRule("gable", "", "0010", "Front edge (W1)."),
    EdgeRule(
        "microwave shelf", "", "0010",
        "Front edge (W1), including the two rounded front corners.",
    ),
    EdgeRule("bottom plate", "", "0010", "Front edge (W1). The ends are captured in the sides."),
    EdgeRule("top plate", "", "0010", "Front edge (W1)."),
    EdgeRule("microwave divider", "", "0010", "Front edge (W1)."),
    EdgeRule(
        "sink front board", "", "0010",
        "Bottom edge (W1), the one that shows under the false front. The ends die into the sides.",
    ),
    EdgeRule("top stile, front", "", "0010", "Front edge (W1)."),
    EdgeRule("top stile, back", "", "0000", "None. It sits against the back."),
    EdgeRule("drawer stile", "", "0010", "Front edge (W1)."),
    EdgeRule("back panel", "", "0000", "None. The back is hidden."),
    EdgeRule(
        "toe kick plate", "", "1110",
        "Top edge (W1) and both ends (L1 L2). The bottom edge is on the floor.",
    ),
    EdgeRule("toe kick stile, back", "", "0000", "None. It is hidden at the back."),
    EdgeRule(
        "spacer board", "", "1010",
        "Top edge (L1) and the exposed edge (W1).",
    ),
    EdgeRule("false front", "", "1111", "All four edges (L1 L2 W1 W2)."),
    EdgeRule("drawer front", "", "1111", "All four edges (L1 L2 W1 W2)."),
    EdgeRule("door", "", "1111", "All four edges (L1 L2 W1 W2)."),
    EdgeRule(
        "drawer box side", "", "1010",
        "Top edge (L1) and front edge (W1). The bottom and the back stay raw.",
    ),
    EdgeRule("drawer box front", "", "1000", "Top edge only (L1)."),
    EdgeRule("drawer box bottom", "", "0000", "None. It sits in the groove."),
    EdgeRule("open shelf", "", "0010", "Front edge (W1). It shows."),
    EdgeRule("shelf", "", "0010", "Front edge (W1)."),
    EdgeRule("kick plate", "", "0000", "None. The kick plate is a finished face, not PVC on the carcass."),
    EdgeRule("counter", "", "0000", "No PVC. Laminate or solid surface covers this edge."),
    EdgeRule("backsplash", "", "0000", "No PVC. Laminate or solid surface covers this edge."),
    EdgeRule("build-up", "", "0000", "None. The strip is hidden under the top."),
    EdgeRule("stiffener", "", "0000", "None. Hidden."),
    EdgeRule("edge strip", "", "0000", "No PVC. The solid-surface edge is the finish."),
)

DEFAULT_RULE = EdgeRule("", "", "0000", "None.")

# Paper mark. Light laminates get a dark hairline as well so white still shows.
MARK_SW = 0.035


def rule_for(name: str, run: str) -> EdgeRule:
    part = (name or "").lower().split("/")[-1].strip()
    for rule in EDGE_TABLE:
        if rule.run and rule.run != run:
            continue
        if part.startswith(rule.match):
            return rule
    return DEFAULT_RULE


def codes_from_mask(mask: str) -> list[str]:
    out = []
    for bit, name in zip((mask or "0000").ljust(4, "0"), ("L1", "L2", "W1", "W2")):
        if bit == "1":
            out.append(name)
    return out


def stamp_parts(parts, params) -> None:
    """Fill ``eb``, ``eb_mask`` and ``notch`` from the table. One place Brook edits."""
    run = "base" if getattr(params, "has_toe_kick", False) else "upper"
    for part in parts:
        rule = rule_for(part.name, run)
        mask = (rule.mask or "0000").ljust(4, "0")[:4]
        part.eb_mask = mask
        codes = codes_from_mask(mask)
        part.notch = None
        if rule.notch and run == "base":
            recess = float(getattr(params, "toe_kick_recess", 0) or 0)
            kick = float(getattr(params, "toe_kick_h", 0) or 0)
            if recess > 0 and kick > 0:
                part.notch = (recess, kick)
                codes.append("N1")
        part.eb = " ".join(codes)
        if part.eb:
            part.banding = f"{part.eb} — {rule.words}"
        else:
            part.banding = rule.words
        part.eb_spec = _band_spec(part.name, params)


def _band_spec(name: str, params) -> str:
    """Which laminate the PVC matches. Blank doors stay unnamed."""
    from .finishes import part_role
    role = part_role(name, "")
    if role == "doors":
        return str(getattr(params, "finish_doors", "") or "").strip()
    if role == "interior":
        return str(getattr(params, "finish_interior", "") or "").strip() or "white"
    if role in ("case", "kick"):
        return str(getattr(params, "finish_case", "") or "").strip() or "white"
    if role == "top":
        return str(getattr(params, "finish_top", "") or "").strip()
    return ""


def band_inches(part) -> float:
    """Inches of PVC on this line of the cut list (qty included).

    L1 and L2 are as long as the length. W1 and W2 are as long as the width.
    On a notched base gable the front band loses the kick height, and N1
    (the top of the notch) is added. The notch is a cut in the one piece.
    """
    mask = (getattr(part, "eb_mask", "") or "0000").ljust(4, "0")
    inches = 0.0
    if mask[0] == "1":
        inches += part.length
    if mask[1] == "1":
        inches += part.length
    if mask[2] == "1":
        inches += part.width
    if mask[3] == "1":
        inches += part.width
    notch = getattr(part, "notch", None)
    if notch and "N1" in str(getattr(part, "eb", "") or "").split():
        recess, kick = notch
        if mask[2] == "1":
            inches -= kick
        inches += recess
    if inches < 0:
        inches = 0.0
    return inches * max(1, int(part.qty))


def band_color(spec: str) -> str:
    text = str(spec or "").strip()
    if not text:
        return "#2F6F8F"
    return lookup(text).hex


def _luma(hex_color: str) -> float:
    h = (hex_color or "#000000").lstrip("#")
    if len(h) < 6:
        return 0.0
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def edge_segments(length: float, width: float, mask: str, notch=None):
    """Banded edges in part inches. u runs along the length, v along the width, floor at v=0.

    A notch ``(recess along the length, kick along the width)`` is the
    toe-kick cut at the front-bottom corner. The front band stops above it.
    """
    L1, L2, W1, W2 = [c == "1" for c in (mask or "0000").ljust(4, "0")[:4]]
    segs = []
    recess = kick = 0.0
    if notch:
        recess, kick = float(notch[0]), float(notch[1])
    if L1 and width > 0 and length > 0:
        segs.append((0.0, width, length, width))
    if L2 and length > recess:
        segs.append((recess if notch else 0.0, 0.0, length, 0.0))
    if W1 and width > kick:
        segs.append((0.0, kick if notch else 0.0, 0.0, width))
    if W2 and width > 0:
        segs.append((length, 0.0, length, width))
    if notch and recess > 0 and kick > 0:
        segs.append((0.0, kick, recess, kick))
    return segs


def notch_cut_segments(notch):
    """The two new edges of the toe-kick cut, so the blank is not read as a solid panel."""
    if not notch:
        return []
    recess, kick = float(notch[0]), float(notch[1])
    if recess <= 0 or kick <= 0:
        return []
    return [(recess, 0.0, recess, kick), (0.0, kick, recess, kick)]


def _map(u, v, x, y, w, h, length, width, along_x: bool):
    if length <= 1e-9 or width <= 1e-9:
        return x, y
    if along_x:
        # length to the right, width up the page (v=0 at the bottom)
        return (x + (u / length) * w, y + h - (v / width) * h)
    # turned 90° clockwise: length runs down the page, width runs to the right
    return (x + (v / width) * w, y + (u / length) * h)


def draw_edge_marks(svg, x, y, w, h, *, length, width, mask, notch=None,
                    along_x: bool = True, color: str = "#2F6F8F", sw: float = MARK_SW,
                    show_notch: bool = True) -> None:
    """Thick line on each banded edge. A light colour also gets a dark hairline.

    ``along_x`` is false when the nest has turned the part 90° clockwise.
    """
    if w <= 0 or h <= 0 or length <= 0 or width <= 0:
        return

    def line(u1, v1, u2, v2, stroke, width_stroke, dash=None):
        x1, y1 = _map(u1, v1, x, y, w, h, length, width, along_x)
        x2, y2 = _map(u2, v2, x, y, w, h, length, width, along_x)
        svg.line(x1, y1, x2, y2, stroke=stroke, sw=width_stroke, cap="square", dash=dash)

    if show_notch and notch:
        for u1, v1, u2, v2 in notch_cut_segments(notch):
            line(u1, v1, u2, v2, "#333333", max(0.008, sw * 0.35), dash="0.04,0.03")
    for u1, v1, u2, v2 in edge_segments(length, width, mask, notch):
        line(u1, v1, u2, v2, color, sw)
        if _luma(color) > 0.82:
            line(u1, v1, u2, v2, "#333333", max(0.008, sw * 0.35))


def draw_part_marks(svg, x, y, w, h, part, *, along_x: bool = True, sw: float = MARK_SW) -> None:
    """Marks for a cut-list part. No-ops when nothing is banded and there is no notch."""
    mask = getattr(part, "eb_mask", "") or ""
    notch = getattr(part, "notch", None)
    if not any(c == "1" for c in mask) and not notch:
        return
    color = band_color(getattr(part, "eb_spec", "") or "")
    draw_edge_marks(
        svg, x, y, w, h,
        length=part.length, width=part.width, mask=mask or "0000", notch=notch,
        along_x=along_x, color=color, sw=sw,
    )


LEGEND = (
    "Thick line = PVC edge band, color-matched to that part's laminate. "
    "A light colour is drawn with a dark hairline so it shows on the paper. "
    "L1 and L2 run with the length (top and bottom of the rectangle when the length "
    "goes left to right). W1 and W2 are the ends (left and right). "
    "N1 is the top of the toe-kick notch. The dashed line is that notch cut out of "
    "the one-piece side — the side is not a solid rectangle. "
    "T on the nest means the part was turned 90° clockwise; the band stays on the same edge of the wood."
)
