"""cabgen command line."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .cutlist import to_csv, to_markdown, to_table_saw_sheet
from .draw import cutlist_sheet, nesting_drawing, shop_drawing
from .nesting import nest_by_material, uncuttable
from .params import Params, STYLE_LABELS, STYLE_PRESETS, door_rule_warnings
from .parts import build_parts
from .units import fmt_in


def svg_to_pdf(svg_path: Path) -> Path | None:
    """Convert an SVG to PDF using rsvg-convert (or cairosvg)."""
    pdf_path = svg_path.with_suffix(".pdf")
    rsvg = shutil.which("rsvg-convert")
    if rsvg:
        res = subprocess.run(
            [rsvg, "-f", "pdf", "-o", str(pdf_path), str(svg_path)],
            capture_output=True, text=True,
        )
        if res.returncode == 0:
            return pdf_path
    try:
        import cairosvg  # type: ignore

        cairosvg.svg2pdf(url=str(svg_path), write_to=str(pdf_path))
        return pdf_path
    except Exception:
        return None


def generate(p: Params, out_dir: Path, name: str | None = None,
             with_omacad: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    parts, layout = build_parts(p)
    stem = name or (p.name.lower().replace(" ", "-") or "cabinet")

    written: list[str] = []
    warnings: list[str] = []
    warnings.extend(door_rule_warnings(p))

    drawing, leftover = shop_drawing(p, parts, layout)
    svg_path = out_dir / f"{stem}-drawing.svg"
    drawing.write(str(svg_path))
    written.append(str(svg_path))
    pdf = svg_to_pdf(svg_path)
    if pdf:
        written.append(str(pdf))

    if leftover:
        extra = cutlist_sheet(p, leftover, page=2, pages=2)
        x2 = out_dir / f"{stem}-cutlist-sheet2.svg"
        extra.write(str(x2))
        written.append(str(x2))
        p2 = svg_to_pdf(x2)
        if p2:
            written.append(str(p2))

    (out_dir / f"{stem}-cutlist.csv").write_text(to_csv(parts), encoding="utf-8")
    (out_dir / f"{stem}-cutlist.md").write_text(to_markdown(parts), encoding="utf-8")
    (out_dir / f"{stem}-table-saw.txt").write_text(to_table_saw_sheet(parts), encoding="utf-8")
    written += [
        str(out_dir / f"{stem}-cutlist.csv"),
        str(out_dir / f"{stem}-cutlist.md"),
        str(out_dir / f"{stem}-table-saw.txt"),
    ]

    nests = nest_by_material(parts, p.sheet_w, p.sheet_h, p.kerf)
    for material, sheets in nests.items():
        safe = material.replace('"', "").replace(" ", "-").replace("/", "-")
        if not sheets:
            continue
        for sheet in sheets:
            svg = nesting_drawing(sheets, f"{material} - nesting", p.kerf, p.sheet_w, p.sheet_h)
            np = out_dir / f"{stem}-nest-{safe}-{sheet.index}.svg"
            svg.write(str(np))
            written.append(str(np))
            npdf = svg_to_pdf(np)
            if npdf:
                written.append(str(npdf))

    (out_dir / f"{stem}-params.json").write_text(json.dumps(p.to_dict(), indent=2), encoding="utf-8")
    written.append(str(out_dir / f"{stem}-params.json"))

    if with_omacad:
        from .omacad_export import export_omacad

        ok, msg = export_omacad(p, out_dir / f"{stem}.omacad")
        if ok:
            written.append(str(out_dir / f"{stem}.omacad"))
        else:
            warnings.append(f"omacad export failed: {msg}")

    return {
        "parts": parts,
        "layout": layout,
        "written": written,
        "warnings": warnings,
        "nests": nests,
        "uncuttable": uncuttable(parts, p.sheet_w, p.sheet_h),
    }


def cmd_generate(args: argparse.Namespace) -> int:
    p = Params(
        style=args.style,
        width=args.width,
        height=args.height,
        depth=args.depth,
    )
    if args.counter_depth is not None:
        p.counter_depth = args.counter_depth
    if args.name:
        p.name = args.name
    out = Path(args.out)
    result = generate(p, out, with_omacad=args.with_omacad)
    print(f"{p.name}: {len(result['parts'])} part lines -> {out}")
    for w in result["written"]:
        print(f"  {w}")
    for u in result["uncuttable"]:
        print(f"  ! does not fit a 4x8 sheet: {u}")
    for w in result["warnings"]:
        print(f"  ! {w}")
    if args.with_omacad and not args.no_show:
        stem = p.name.lower().replace(" ", "-") or "cabinet"
        model = out / f"{stem}.omacad"
        if model.exists():
            from .omacad_export import open_in_omacad
            ok, msg = open_in_omacad(model)
            print(msg if ok else f"  ! {msg}")
    return 0


def cmd_omacad(args: argparse.Namespace) -> int:
    from .omacad_export import export_omacad

    p = Params(
        style=args.style,
        width=args.width,
        height=args.height,
        depth=args.depth,
    )
    if args.name:
        p.name = args.name
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = p.name.lower().replace(" ", "-") or "cabinet"
    target = out / f"{stem}.omacad"
    ok, msg = export_omacad(p, target)
    if not ok:
        print(f"omacad export failed: {msg}", file=sys.stderr)
        return 1
    print(msg)
    if not args.no_show:
        from .omacad_export import open_in_omacad
        shown, show_msg = open_in_omacad(target)
        print(show_msg if shown else f"could not open: {show_msg}",
              file=sys.stdout if shown else sys.stderr)
        if not shown:
            return 1
    return 0


def cmd_open(args: argparse.Namespace) -> int:
    """Open the generated model in Omacad (seeds the session, then starts the app)."""
    from .omacad_export import open_in_omacad

    out = Path(args.out)
    stem = args.name.lower().replace(" ", "-") or "cabinet"
    model = out / f"{stem}.omacad"
    if not model.exists():
        print(f"{model} does not exist - run: "
              f"python3 -m cabgen.cli generate --out {args.out} --name \"{args.name}\" --with-omacad",
              file=sys.stderr)
        return 1
    ok, msg = open_in_omacad(model)
    print(msg if ok else f"could not open: {msg}", file=sys.stderr if not ok else sys.stdout)
    return 0 if ok else 1


def cmd_kitchen(args: argparse.Namespace) -> int:
    """Build a run of cabinets from a spreadsheet and show it in Omacad."""
    from .kitchen import KitchenError, write_kitchen

    sheet = Path(args.sheet)
    if not sheet.exists():
        print(f"{sheet} does not exist", file=sys.stderr)
        return 1
    name = args.name or sheet.stem.replace("-", " ").replace("_", " ").title()
    try:
        ok, msg = write_kitchen(sheet, Path(args.out), name, show=not args.no_show,
                                nest={"kerf": args.kerf, "sheet_w": args.sheet_w,
                                      "sheet_l": args.sheet_l})
    except KitchenError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(msg)
    return 0 if ok else 1


def cmd_client(args: argparse.Namespace) -> int:
    from .client_sheet import load_job, write_client_sheet
    from .kitchen import KitchenError

    sheet = Path(args.sheet)
    try:
        job = load_job(sheet, args.name)
        files = write_client_sheet(job, Path(args.out), args.stem or f"{sheet.stem}-client-sheet")
    except KitchenError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"  {files['pdf']}  ({files['pages']} pages)")
    for path in files.get("pngs", []):
        print(f"  {path}")
    return 0


def cmd_styles(args: argparse.Namespace) -> int:
    for key, preset in STYLE_PRESETS.items():
        print(f"{key:<22} {preset['label']}")
    return 0


def cmd_ar(args: argparse.Namespace) -> int:
    from .ar_export import export_job
    from .client_sheet import load_job
    from .kitchen import KitchenError

    sheet = Path(args.sheet)
    try:
        job = load_job(sheet, args.title)
        res = export_job(job, Path(args.out), args.name or sheet.stem)
    except KitchenError as exc:
        print(exc, file=sys.stderr)
        return 1
    w, h, d = res["size_m"]
    print(f"  {res['glb']}\n  {res['usdz']}  ({res['usd_layer']})")
    print(f"  {res['boxes']} parts, {w:.3f} x {h:.3f} x {d:.3f} m (W x H x D)")
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    from .web import serve

    host = "0.0.0.0" if args.lan else args.host
    serve(host=host, port=args.port, out_dir=Path(args.out))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="cabgen", description="Cabinet shop drawing generator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate drawings, cut list and nesting")
    g.add_argument("--style", default="base_1drawer_2doors", choices=list(STYLE_PRESETS))
    g.add_argument("--name", default="Base cabinet")
    g.add_argument("--width", type=float, default=None)
    g.add_argument("--height", type=float, default=None)
    g.add_argument("--depth", type=float, default=None)
    g.add_argument("--counter-depth", type=float, default=None)
    g.add_argument("--out", default="out")
    g.add_argument("--with-omacad", action="store_true",
                   help="also write the Omacad 3D model and show it in the one Omacad window")
    g.add_argument("--no-show", action="store_true",
                   help="with --with-omacad, write the file without updating the Omacad window")
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("styles", help="list cabinet styles")
    s.set_defaults(func=cmd_styles)

    o = sub.add_parser("omacad", help="write an Omacad (.omacad) 3D model")
    o.add_argument("--style", default="base_1drawer_2doors", choices=list(STYLE_PRESETS))
    o.add_argument("--name", default="Base cabinet")
    o.add_argument("--width", type=float, default=None)
    o.add_argument("--height", type=float, default=None)
    o.add_argument("--depth", type=float, default=None)
    o.add_argument("--out", default="out")
    o.add_argument("--no-show", action="store_true",
                   help="write the file without updating the Omacad window")
    o.set_defaults(func=cmd_omacad)

    k = sub.add_parser("kitchen", help="build a run of cabinets from a spreadsheet")
    k.add_argument("sheet", help="CSV: name, style, width, run. Height and depth are optional")
    k.add_argument("--name", default=None, help="job name (default: the file name)")
    k.add_argument("--out", default="out")
    k.add_argument("--no-show", action="store_true",
                   help="write the model without opening the Omacad window")
    k.add_argument("--kerf", type=float, default=None, help='saw kerf, inches (default 3/16")')
    k.add_argument("--sheet-w", type=float, default=None, help="sheet width, inches (default 48)")
    k.add_argument("--sheet-l", type=float, default=None, help="sheet length, inches (default 96)")
    k.set_defaults(func=cmd_kitchen)

    cs = sub.add_parser("client", help="one-page client sheet (PDF + PNG) for a kitchen sheet")
    cs.add_argument("sheet", help="kitchen CSV")
    cs.add_argument("--out", default="out/client-sheet")
    cs.add_argument("--name", default=None, help="job name on the page (default: file name)")
    cs.add_argument("--stem", default=None, help="output file name stem")
    cs.set_defaults(func=cmd_client)

    op = sub.add_parser("open", help="open the generated model in Omacad")
    op.add_argument("--name", default="Base cabinet")
    op.add_argument("--out", default="out")
    op.set_defaults(func=cmd_open)

    ar = sub.add_parser("ar", help="AR files of a kitchen sheet: .glb (Android) and .usdz (iPhone)")
    ar.add_argument("sheet", help="kitchen CSV")
    ar.add_argument("--out", default="out/ar")
    ar.add_argument("--name", default=None, help="file name stem (default: the CSV name)")
    ar.add_argument("--title", default=None, help="job name in the model (default: file name)")
    ar.set_defaults(func=cmd_ar)

    w = sub.add_parser("web", help="local web form for styles and dimensions")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--lan", action="store_true",
                   help="listen on all interfaces (0.0.0.0) so a phone on the same Wi-Fi can "
                        "open the AR pages; the form itself still answers only this laptop")
    w.add_argument("--port", type=int, default=8777)
    w.add_argument("--out", default="out")
    w.set_defaults(func=cmd_web)

    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
