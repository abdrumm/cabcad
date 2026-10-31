"""Countertops for the base run (Brook, 2026-10-24).

Two builds, both 1-1/2" thick at the front edge:

Laminate (default): 3/4" plywood top. Under it, 3/4" plywood build-up strips at
the front, at each finished (open) side edge, at each counter end, and centred
on every joint where two cabinets meet, so installers screw up into plywood.
Laminate goes on in this order: side edges (when needed), front edge, then the
top. Every exposed backsplash edge gets laminate. 4" backsplash on the wall;
a side splash at a wall end when asked for.

Solid surface (Corian): 1/2" top. A rabbet on the underside at the front and at
finished side edges takes a 1-1/4" solid-surface edge strip, epoxied in; the
1/4" lip that is left plus the 1-1/4" strip gives a 1-1/2" reveal. Under the
sheet, 3/4" plywood build-up strips (SOLID_BUILDUP_THK), 4" wide (STRIP_W),
run the whole perimeter — front, back, and both ends — and one more strip is
centred on every case break. The strips are tight to the underside of the sheet.

Anything Brook did not say is marked TO CONFIRM in ASSUMPTIONS and in
cabinet-shop-standards.md section 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model3d import Box
from .parts import Part
from .units import fmt_in

KINDS = {"laminate": "Laminate", "solid": "Solid surface", "none": "None"}
OPEN_OVERHANG = 1.0       # same as kitchen.OPEN_OVERHANG
STRIP_W = 4.0             # build-up strips, laminate and solid surface (Brook: 4")
# Solid-surface build-up under the 1/2" sheet. 3/4" plywood, same as the laminate
# strips. MDF was the other likely stock; plywood is what the nest already cuts.
# The front edge is still a 1-1/2" solid-surface reveal, so a 3/4" strip tight to
# the sheet starts 1/4" above the case (1" from the case up to the sheet).
SOLID_BUILDUP_THK = 0.75
SPLASH_H = 4.0            # backsplash and side splash height (Brook: both 4")
# Side splash: automatic at every wall end (Brook). The form can still turn one off.
EDGE = 1.5                # finished front / side edge
MAX_LEN = {"laminate": 96.0, "solid": 144.0}   # plywood sheet 96"; solid surface sheet 144" (TO CONFIRM)
LAM_SHEET = 144.0         # longest laminate sheet (5x12)
# Brook, Oct 27: no automatic seams. The top is one piece the length of the run; a
# piece longer than its stock sheet is flagged and Brook decides the seam later.
OVERSIZE_FLAG = "LONGER THAN STOCK SHEET - seam TBD"
SEAM_W = 6.0              # laminate seam strip, 6" centred on the seam (Brook)
DOGBONE_DEPTH = 0.5       # dogbone pockets routed 1/2" deep across the seam (Brook)
DOGBONE_EVERY = 12.0      # one dogbone per ~12" of strip, at least 2 (TO CONFIRM)
LAM_WASTE = 0.10          # laminate takeoff allowance (TO CONFIRM)

MAT = {
    "ply34": '3/4" plywood',
    "ply1": '1" plywood',
    "ss": '1/2" solid surface',
}

ASSUMPTIONS = [
    "Solid-surface build-up is 3/4\" plywood, 4\" wide (SOLID_BUILDUP_THK, STRIP_W). MDF would also do; plywood matches the laminate strips and nests with them.",
    "Those strips are glued tight to the underside of the 1/2\" sheet. The front edge is still a 1-1/2\" solid-surface reveal, so the 3/4\" strip starts 1/4\" above the case.",
    "No laminate backer (balance) sheet on the underside: the top is screwed to the cabinets and the overhang is only 1-1/2\". Guides suggest one for bars, peninsulas and big overhangs.",
    "No automatic seams (Brook, Oct 27): the top, build-up and splash are each one piece the length of the run. A piece longer than its stock sheet (96\" plywood, 144\" solid surface or laminate) is flagged \"longer than stock sheet - seam TBD\".",
    "Laminate seam strip: Brook's 6\" strip is modelled as one 6\" band centred on the seam, cut at the seam so each piece carries 3\" (not a 6\" strip on each side).",
    "Dogbones: one per ~12\" of strip, at least 2 (2 on a 25\" counter).",
    "Solid surface seam: hard seam with the maker's joint adhesive, over the joint stiffener; no dogbones or 6\" strip.",
    "Side splash runs from the front of the counter back to the backsplash (butts it).",
    "Laminate counter: backsplash and side splash are 3/4\" plywood, laminated.",
    "Solid surface counter: backsplash and side splash are 1/2\" solid surface.",
    "Front overhang is 1-1/2\" past the cabinet case (the code's existing value; 3/4\" past the doors), which makes the counter 25\" deep. A Lowe's laminate guide gives 1-1/4\" as standard.",
    "The counter sits on top of the 33-1/2\" case, so the finished top is 35\" off the floor.",
    "A filler end gets one end strip at least 4\" wide (filler + 1-1/2\" when wider) instead of an end strip plus a joint strip.",
    "Laminate counters: no build-up strip along the back wall (Brook named front, edges and joints; JLC suggests front and rear strips).",
    "Solid surface build-up: 4\" strips on the whole perimeter (front, back, both ends) and one centred on every case break, directly under the sheet.",
    "Solid surface rabbet: Brook said 1/2\" x 1/2\", but a 1/4\" lip plus a 1-1/4\" strip = 1-1/2\" means the rabbet is 1/2\" wide x 1/4\" deep in the 1/2\" top. Modelled that way.",
    "Solid surface corners: the front edge strip runs the full length and the side strips butt behind it.",
    "Laminate is listed as a square-foot takeoff (+10% allowance), not nested on sheets.",
    "Solid surface pieces are listed, not nested on 4x8 plywood (sheet size varies by supplier).",
]


def kind_of(settings: dict) -> str:
    kind = str(settings.get("counter") or "laminate").strip().lower()
    kind = {"solid surface": "solid", "corian": "solid", "lam": "laminate", "no": "none"}.get(kind, kind)
    if kind not in KINDS:
        raise ValueError(f"countertop {kind!r} is not laminate, solid, or none")
    return kind


def _yes(value, default=True) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in ("1", "yes", "y", "true", "on")


@dataclass
class Piece:
    label: str
    name: str
    material: str
    thk: float
    width: float           # across (short way)
    length: float          # along (long way)
    notes: str = ""
    boxes: list[Box] = field(default_factory=list)


@dataclass
class LamPiece:
    order: int
    label: str
    name: str
    width: float
    length: float

    @property
    def sqft(self) -> float:
        return self.width * self.length / 144.0


@dataclass
class Counter:
    kind: str
    code: str
    x0: float
    x1: float
    y_front: float
    y_back: float
    z0: float
    left_open: bool
    right_open: bool
    splash_left: bool
    splash_right: bool
    seams: list[float]
    joints: list[float]
    pieces: list[Piece] = field(default_factory=list)
    laminate: list[LamPiece] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    dogbones: list[tuple[float, float]] = field(default_factory=list)   # (x, y) of each pocket

    @property
    def length(self) -> float:
        return self.x1 - self.x0

    @property
    def depth(self) -> float:
        return self.y_back - self.y_front

    @property
    def top_z(self) -> float:
        return self.z0 + EDGE

    @property
    def splash_thk(self) -> float:
        return 0.75 if self.kind == "laminate" else 0.5

    @property
    def boxes(self) -> list[Box]:
        return [b for p in self.pieces for b in p.boxes]

    def parts(self) -> list[tuple[Part, list[str]]]:
        return [(Part(name=p.name, qty=1, material=p.material, thk=p.thk, width=p.width,
                      length=p.length, notes=p.notes), [p.label]) for p in self.pieces]

    @property
    def description(self) -> str:
        if self.kind == "laminate":
            return (f'Laminate on 3/4" plywood, {fmt_in(EDGE)} front edge, '
                    f'{fmt_in(SPLASH_H)} backsplash')
        return (f'Solid surface, 1/2" top with {fmt_in(EDGE)} edge, '
                f'{fmt_in(SPLASH_H)} backsplash')

    def laminate_sqft(self) -> tuple[float, float]:
        net = sum(p.sqft for p in self.laminate)
        return net, net * (1 + LAM_WASTE)


def _filler(cabs, settings) -> tuple[float, float]:
    """(left, right) filler widths on the base run."""
    if "base_walls" not in settings:
        return 0.0, 0.0
    from .kitchen import end_facts
    facts = end_facts(settings)
    if not facts["filler"]:
        return 0.0, 0.0
    return (facts["filler"], 0.0) if facts["filler_side"] == "left" else (0.0, facts["filler"])


def build_counter(cabs, settings: dict) -> Counter | None:
    """The countertop over the base run, or None (no bases, or counter=none)."""
    kind = kind_of(settings)
    bases = sorted((c for c in cabs if c.run == "base"), key=lambda c: c.x)
    if kind == "none" or not bases:
        return None
    first, last = bases[0], bases[-1]
    left_open = first.params.left_side != "wall"
    right_open = last.params.right_side != "wall"
    fl, fr = _filler(cabs, settings)
    cx0, cx1 = first.x, last.x + last.params.width
    x0 = cx0 - fl - (OPEN_OVERHANG if left_open else 0.0)
    x1 = cx1 + fr + (OPEN_OVERHANG if right_open else 0.0)
    y_back = max(c.y + c.params.depth for c in bases)
    y_front = -first.params.counter_front_overhang
    z0 = max(c.z + c.params.height for c in bases)
    joints = []
    for a, b in zip(bases, bases[1:]):
        edge = a.x + a.params.width
        if abs(edge - b.x) < 1e-6:
            joints.append(edge)
    c = Counter(kind, "CT1", x0, x1, y_front, y_back, z0, left_open, right_open,
                splash_left=(not left_open) and _yes(settings.get("splash_left")),
                splash_right=(not right_open) and _yes(settings.get("splash_right")),
                seams=[], joints=joints)
    # One continuous top, always (Brook, Oct 27). c.seams stays empty; the seam
    # machinery below is kept for when Brook sets the seam rules.
    if kind == "laminate":
        _laminate(c, fl, fr)
    else:
        _solid(c, fl, fr)
    _flag_oversize(c, kind)
    return c


def _flag_oversize(c: Counter, kind: str) -> None:
    """Mark every piece longer than its stock sheet. No seam is placed."""
    long_ = []
    for p in c.pieces:
        sheet = MAX_LEN["solid"] if p.material == MAT["ss"] else MAX_LEN["laminate"]
        if p.length > sheet + 1e-6:
            p.notes = (p.notes + " " if p.notes else "") + f"{OVERSIZE_FLAG} ({fmt_in(p.length)} > {sheet:g}\" sheet)."
            long_.append(p.name)
    for lp in c.laminate:
        if lp.length > LAM_SHEET + 1e-6:
            long_.append(f"laminate {lp.name.lower()}")
    if long_:
        c.notes.append(f"Countertop is {fmt_in(c.length)} long, one piece. Longer than stock sheet, "
                       f"seam TBD: {', '.join(long_)}.")


def _seams(c: Counter, max_len: float, what: str = "Top", avoid: tuple = ()) -> list[float]:
    """Seams only when the run is longer than max_len. Each seam goes on a cabinet
    joint (over a strip), picked so the pieces come out about equal. `avoid` keeps a
    laminate seam off the plywood seams."""
    import math
    seams, start = [], c.x0
    while c.x1 - start > max_len + 1e-6:
        left = math.ceil((c.x1 - start) / max_len - 1e-9)
        target = start + (c.x1 - start) / left
        fits = [j for j in c.joints if start + 1e-6 < j <= start + max_len + 1e-6]
        good = [j for j in fits if all(abs(j - a) >= 6 for a in avoid)] or fits
        if good:
            cut = min(good, key=lambda j: abs(j - target))
            c.notes.append(f"{what} is {fmt_in(c.length)} long, more than {fmt_in(max_len)}: seam at "
                           f"{fmt_in(cut - c.x0)} from the left end, on a cabinet joint.")
        else:
            cut = start + max_len
            c.notes.append(f"{what}: no cabinet joint within {fmt_in(max_len)}, so the seam is at "
                           f"{fmt_in(cut - c.x0)} from the left end, off a joint. Add support there.")
        seams.append(cut)
        start = cut
    return seams


def _spans(c: Counter) -> list[tuple[float, float]]:
    edges = [c.x0] + c.seams + [c.x1]
    return list(zip(edges, edges[1:]))


def _num(i: int, n: int) -> str:
    return str(i) if n > 1 else ""


def _add(c: Counter, code: str, name: str, mat: str, thk: float, w: float, l: float,
         boxes: list[tuple], notes: str = "") -> None:
    label = f"{c.code}-{code}"
    bx = [Box(f"{label} Countertop / {name}", pos, size, mat, label if len(boxes) > 1 else "")
          for pos, size in boxes]
    c.pieces.append(Piece(label, name, mat, thk, w, l, notes, bx))


def _cross_strips(c: Counter, thk: float, z: float, y0: float, y1: float, mat: str,
                  fl: float, fr: float, code: str, inset_open: float, word: str,
                  fasten: str = "", joint: str = "Screw down here.") -> None:
    """Front-to-back strips: one at each counter end, one centred on each cabinet joint."""
    length = y1 - y0
    wl = max(STRIP_W, fl + 1.5) if fl else STRIP_W
    wr = max(STRIP_W, fr + 1.5) if fr else STRIP_W
    lx = c.x0 + (inset_open if c.left_open else 0.0)
    rx = c.x1 - (inset_open if c.right_open else 0.0)
    how = (fasten + " ") if fasten else ""

    def end_note(side: str, open_end: bool) -> str:
        if open_end and inset_open > 1e-6:
            return (f"Hold {fmt_in(inset_open)} back from the {side} end of the counter, "
                    f"to clear the {fmt_in(inset_open)} solid-surface edge strip.")
        return f"Flush with the {side} end of the counter."

    _add(c, f"{code}L", f"{word}, left end", mat, thk, wl, length,
         [((lx, y0, z), (wl, length, thk))], how + end_note("left", c.left_open))
    import math
    for i, j in enumerate(c.joints, start=1):
        at = f"{fmt_in(j - c.x0)} from the left end"
        if code == "BU" and any(abs(j - s) < 1e-6 for s in c.seams):
            # Laminate seam (Brook): a 6" strip centred on the seam, split at the seam so
            # each top piece carries 3". Dogbones routed 1/2" deep across the seam.
            n = max(2, math.ceil(length / DOGBONE_EVERY))
            ys = [y0 + length * (k + 0.5) / n for k in range(n)]
            c.dogbones += [(j, y) for y in ys]
            half = SEAM_W / 2
            seam_note = (f"Seam strip: half of the 6\" strip centred on the seam at {at}. Rout {n} "
                         f"dogbone pockets 1/2\" deep across the seam; glue the seam and pull it "
                         "together with dogbone clamps at install.")
            _add(c, f"{code}J{i}A", f"{word}, seam strip {i} left half", mat, thk, half, length,
                 [((j - half, y0, z), (half, length, thk))], how + seam_note)
            _add(c, f"{code}J{i}B", f"{word}, seam strip {i} right half", mat, thk, half, length,
                 [((j, y0, z), (half, length, thk))], how + seam_note)
            c.notes.append(f"Laminate seam at {at}: 6\" strip centred on it (3\" on each piece), {n} "
                           "dogbone pockets routed 1/2\" deep across it, adhesive in the seam, dogbone "
                           "clamps pull it tight at install.")
            continue
        _add(c, f"{code}J{i}", f"{word}, cabinet joint {i}", mat, thk, STRIP_W, length,
             [((j - STRIP_W / 2, y0, z), (STRIP_W, length, thk))],
             how + f"Centred on the joint at {at}. {joint}")
    _add(c, f"{code}R", f"{word}, right end", mat, thk, wr, length,
         [((rx - wr, y0, z), (wr, length, thk))], how + end_note("right", c.right_open))


def _splashes(c: Counter, mat: str, thk: float) -> None:
    z = c.top_z
    spans = _spans(c)
    for i, (a, b) in enumerate(spans, start=1):
        n = _num(i, len(spans))
        _add(c, f"BS{n}", f"Backsplash{(' ' + n) if n else ''}", mat, thk, SPLASH_H, b - a,
             [((a, c.y_back - thk, z), (b - a, thk, SPLASH_H))],
             "Back wall. Runs the full length, including any overhang.")
    side_d = c.depth - thk
    if c.splash_left:
        _add(c, "SSL", "Side splash, left wall", mat, thk, SPLASH_H, side_d,
             [((c.x0, c.y_front, z), (thk, side_d, SPLASH_H))], "Butts the backsplash.")
    if c.splash_right:
        _add(c, "SSR", "Side splash, right wall", mat, thk, SPLASH_H, side_d,
             [((c.x1 - thk, c.y_front, z), (thk, side_d, SPLASH_H))], "Butts the backsplash.")


def _laminate(c: Counter, fl: float, fr: float) -> None:
    ply, t = MAT["ply34"], 0.75
    spans = _spans(c)
    for i, (a, b) in enumerate(spans, start=1):
        n = _num(i, len(spans))
        _add(c, f"TOP{n}", f"Top{(' ' + n) if n else ''}", ply, t, c.depth, b - a,
             [((a, c.y_front, c.z0 + t), (b - a, c.depth, t))],
             "Laminated: side edges, then front edge, then top.")
    for i, (a, b) in enumerate(spans, start=1):
        n = _num(i, len(spans))
        _add(c, f"BUF{n}", f"Build-up, front{(' ' + n) if n else ''}", ply, t, STRIP_W, b - a,
             [((a, c.y_front, c.z0), (b - a, STRIP_W, t))],
             "Glued and stapled under the front edge; with the top makes the 1-1/2\" edge.")
    _cross_strips(c, t, c.z0, c.y_front + STRIP_W, c.y_back, ply, fl, fr, "BU", 0.0, "Build-up",
                  fasten="Glued and stapled to the top.")
    _splashes(c, ply, t)

    # laminate takeoff, in the order it goes on. Laminate sheets run to 144", so the
    # laminate only seams past that, and away from the plywood seams.
    lam_seams: list[float] = []   # no automatic laminate seams (Brook, Oct 27)
    edges = [c.x0] + lam_seams + [c.x1]
    spans = list(zip(edges, edges[1:]))
    lam = c.laminate
    if c.left_open:
        lam.append(LamPiece(1, f"{c.code}-LSL", "Left side edge", EDGE, c.depth))
    if c.right_open:
        lam.append(LamPiece(1, f"{c.code}-LSR", "Right side edge", EDGE, c.depth))
    for i, (a, b) in enumerate(spans, start=1):
        n = _num(i, len(spans))
        lam.append(LamPiece(2, f"{c.code}-LF{n}", f"Front edge{(' ' + n) if n else ''}", EDGE, b - a))
    for i, (a, b) in enumerate(spans, start=1):
        n = _num(i, len(spans))
        lam.append(LamPiece(3, f"{c.code}-LT{n}", f"Top{(' ' + n) if n else ''}", c.depth, b - a))
    st = c.splash_thk
    for i, (a, b) in enumerate(spans, start=1):
        n = _num(i, len(spans))
        lam.append(LamPiece(4, f"{c.code}-LBT{n}", f"Backsplash top edge{(' ' + n) if n else ''}", st, b - a))
    if c.left_open:
        lam.append(LamPiece(4, f"{c.code}-LBEL", "Backsplash left end (exposed)", st, SPLASH_H))
    if c.right_open:
        lam.append(LamPiece(4, f"{c.code}-LBER", "Backsplash right end (exposed)", st, SPLASH_H))
    for side, on in (("L", c.splash_left), ("R", c.splash_right)):
        if on:
            word = "left" if side == "L" else "right"
            lam.append(LamPiece(4, f"{c.code}-LS{side}T", f"Side splash {word}, top edge", st, c.depth - st))
            lam.append(LamPiece(4, f"{c.code}-LS{side}E", f"Side splash {word}, front edge", st, SPLASH_H))
    for i, (a, b) in enumerate(spans, start=1):
        n = _num(i, len(spans))
        lam.append(LamPiece(5, f"{c.code}-LBF{n}", f"Backsplash face{(' ' + n) if n else ''}", SPLASH_H, b - a))
    for side, on in (("L", c.splash_left), ("R", c.splash_right)):
        if on:
            word = "left" if side == "L" else "right"
            lam.append(LamPiece(5, f"{c.code}-LS{side}F", f"Side splash {word}, face", SPLASH_H, c.depth - st))


def _solid(c: Counter, fl: float, fr: float) -> None:
    ss, ply = MAT["ss"], MAT["ply34"]
    rab = 0.5                         # rabbet width = edge strip thickness
    lip = 0.25                        # top left over the rabbet
    strip_h = EDGE - lip              # 1-1/4" edge strip
    sheet = 0.5
    z_top0 = c.z0 + EDGE - sheet      # underside of the 1/2" top; finished top stays 1-1/2"
    z_bu = z_top0 - SOLID_BUILDUP_THK # build-up tight to that underside
    spans = _spans(c)
    for i, (a, b) in enumerate(spans, start=1):
        n = _num(i, len(spans))
        ax = a + (rab if (c.left_open and a == c.x0) else 0.0)
        bx = b - (rab if (c.right_open and b == c.x1) else 0.0)
        boxes = [((ax, c.y_front + rab, z_top0), (bx - ax, c.depth - rab, sheet)),
                 ((a, c.y_front, c.z0 + strip_h), (b - a, rab, lip))]
        if c.left_open and a == c.x0:
            boxes.append(((a, c.y_front + rab, c.z0 + strip_h), (rab, c.depth - rab, lip)))
        if c.right_open and b == c.x1:
            boxes.append(((b - rab, c.y_front + rab, c.z0 + strip_h), (rab, c.depth - rab, lip)))
        _add(c, f"TOP{n}", f"Top{(' ' + n) if n else ''}", ss, sheet, c.depth, b - a, boxes,
             "1/2\" x 1/4\" deep rabbet underneath at the front and finished side edges.")
    for i, (a, b) in enumerate(spans, start=1):
        n = _num(i, len(spans))
        _add(c, f"EF{n}", f"Edge strip, front{(' ' + n) if n else ''}", ss, sheet, strip_h, b - a,
             [((a, c.y_front, c.z0), (b - a, rab, strip_h))],
             "Epoxied into the front rabbet. 1/4\" lip + 1-1/4\" strip = 1-1/2\" reveal.")
    side_d = c.depth - rab
    if c.left_open:
        _add(c, "EL", "Edge strip, left side", ss, sheet, strip_h, side_d,
             [((c.x0, c.y_front + rab, c.z0), (rab, side_d, strip_h))], "Epoxied into the side rabbet.")
    if c.right_open:
        _add(c, "ER", "Edge strip, right side", ss, sheet, strip_h, side_d,
             [((c.x1 - rab, c.y_front + rab, c.z0), (rab, side_d, strip_h))], "Epoxied into the side rabbet.")
    # Perimeter build-up, then the case-break strips between the front and back
    # strips (same places as before). All of them tight to the sheet. Front and
    # back stop short of a solid-surface side edge strip so the two do not collide.
    bu = SOLID_BUILDUP_THK
    glued = ("Glued to the underside of the solid surface. No staples or screws into the sheet. "
             "Directly under the sheet, 4\" wide.")
    fy0 = c.y_front + rab                 # behind the front edge strip
    x_lo = c.x0 + (rab if c.left_open else 0.0)
    x_hi = c.x1 - (rab if c.right_open else 0.0)
    clear = ""
    if c.left_open or c.right_open:
        clear = " Stops short of the solid-surface side edge strip at an open end."
    for i, (a, b) in enumerate(spans, start=1):
        n = _num(i, len(spans))
        lo = max(a, x_lo)
        hi = min(b, x_hi)
        _add(c, f"SBF{n}", f"Build-up, front{(' ' + n) if n else ''}", ply, bu, STRIP_W, hi - lo,
             [((lo, fy0, z_bu), (hi - lo, STRIP_W, bu))], glued + " Front edge, behind the edge strip." + clear)
        _add(c, f"SBB{n}", f"Build-up, back{(' ' + n) if n else ''}", ply, bu, STRIP_W, hi - lo,
             [((lo, c.y_back - STRIP_W, z_bu), (hi - lo, STRIP_W, bu))], glued + " Back edge." + clear)
    _cross_strips(c, bu, z_bu, fy0 + STRIP_W, c.y_back - STRIP_W, ply, fl, fr, "SB", rab, "Build-up",
                  fasten=glued, joint="Screw up from the cabinet into the plywood, not into the solid surface.")
    _splashes(c, ss, 0.5)


def counter_text(c: Counter) -> str:
    """Readable parts list and laminate takeoff for the counter."""
    out = [f"# Countertop {c.code} - {KINDS[c.kind]}", "",
           f"{c.description}. {fmt_in(c.length)} long x {fmt_in(c.depth)} deep, top at "
           f"{fmt_in(c.top_z)} off the floor.",
           f"Left end: {'open, 1\" overhang, finished edge' if c.left_open else 'wall, flush'}"
           f"{', side splash' if c.splash_left else ''}. "
           f"Right end: {'open, 1\" overhang, finished edge' if c.right_open else 'wall, flush'}"
           f"{', side splash' if c.splash_right else ''}.", ""]
    out += [f"- {n}" for n in c.notes]
    out += ["", "## Parts", "", "| Label | Part | Material | Thk | Width | Length | Notes |",
            "|---|---|---|---|---|---|---|"]
    for p in c.pieces:
        out.append(f"| {p.label} | {p.name} | {p.material} | {fmt_in(p.thk)} | {fmt_in(p.width)} | "
                   f"{fmt_in(p.length)} | {p.notes} |")
    if c.laminate:
        net, gross = c.laminate_sqft()
        out += ["", "## Laminate takeoff (in the order it goes on)", "",
                "Order: 1 side edges, 2 front edge, 3 top, then the splash: 4 exposed edges, 5 faces.",
                "", "| Order | Label | Piece | Width | Length | Sq ft |", "|---|---|---|---|---|---|"]
        for lp in sorted(c.laminate, key=lambda q: q.order):
            out.append(f"| {lp.order} | {lp.label} | {lp.name} | {fmt_in(lp.width)} | "
                       f"{fmt_in(lp.length)} | {lp.sqft:.2f} |")
        out += ["", f"Laminate: {net:.1f} sq ft net, {gross:.1f} sq ft with a "
                f"{LAM_WASTE * 100:.0f}% allowance."]
    out += ["", "## Assumptions (to confirm)", ""] + [f"- {a}" for a in ASSUMPTIONS] + [""]
    return "\n".join(out)
