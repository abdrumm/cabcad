"""Email drafts: 'Email AR to me' and 'Draft client email' (Brook, Oct 30).

Draft only. Nothing here talks to a mail server: each button writes a folder with the
files and a ready-to-open .eml (marked X-Unsent so mail apps open it as a draft), plus a
mailto: link and a copy-paste body, then opens the folder in the file manager.

    out/email-ar/<job>/       cabcad.usdz, cabcad.glb, email.eml, mailto.txt
    out/client-email/<job>/   <job>-client-sheet.pdf, <job>-render.png, <job>.usdz,
                              <job>.glb, email.txt, email.eml

Recipients come from config/email.json; only enabled entries are used. Rick
(ricks@cexhibits.com) is listed there but disabled until Brook says so.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path
from urllib.parse import quote

from . import branding as br

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "email.json"
MIME = {".usdz": ("model", "vnd.usdz+zip"), ".glb": ("model", "gltf-binary"),
        ".pdf": ("application", "pdf"), ".png": ("image", "png")}


def config() -> dict:
    path = Path(os.environ.get("CABCAD_EMAIL_CONFIG") or CONFIG)
    return json.loads(path.read_text(encoding="utf-8"))


def ar_recipients(cfg: dict | None = None) -> list[str]:
    """Enabled AR recipients only (Brook for now)."""
    cfg = cfg or config()
    return [r["email"] for r in cfg.get("ar_recipients", []) if r.get("enabled")]


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60] or "job"


def build_eml(to: list[str], subject: str, body: str, files: list[Path]) -> bytes:
    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["X-Unsent"] = "1"                      # open as a draft, never as a sent mail
    msg.set_content(body)
    for f in files:
        main, sub = MIME.get(f.suffix, tuple((mimetypes.guess_type(f.name)[0]
                                              or "application/octet-stream").split("/")))
        msg.add_attachment(f.read_bytes(), maintype=main, subtype=sub, filename=f.name)
    return bytes(msg)


def mailto(to: list[str], subject: str, body: str) -> str:
    """mailto: cannot carry attachments; the folder opens alongside it."""
    return (f"mailto:{','.join(to)}?subject={quote(subject)}&body={quote(body)}")


def open_folder(path: Path) -> bool:
    """Open the folder in the file manager, detached. CABCAD_NO_OPEN=1 skips it (tests)."""
    if os.environ.get("CABCAD_NO_OPEN") or not shutil.which("xdg-open"):
        return False
    subprocess.Popen(["setsid", "xdg-open", str(path)], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    return True


def _fresh(folder: Path) -> Path:
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    return folder


def draft_ar_email(job, out_dir: Path, open_it: bool = True) -> dict:
    """'Email AR to me': AR files (USDZ for iPhone, GLB for Android) in a draft to Brook."""
    from .ar_export import export_job
    folder = _fresh(Path(out_dir) / "email-ar" / slug(job.name))
    res = export_job(job, folder, "cabcad")
    files = [Path(res["usdz"]), Path(res["glb"])]
    to = ar_recipients()
    subject = f"AR: {job.name}"
    body = (f"AR model for {job.name}.\n\n"
            "iPhone / iPad: tap cabcad.usdz, then the AR button.\n"
            "Android: open cabcad.glb in Google's Scene Viewer or any 3D viewer.\n\n"
            f"Made by CabCad, {date.today():%b %d, %Y}.\n")
    (folder / "email.eml").write_bytes(build_eml(to, subject, body, files))
    link = mailto(to, subject, body)
    (folder / "mailto.txt").write_text(link + "\n", encoding="utf-8")
    opened = open_folder(folder) if open_it else False
    return {"folder": folder, "to": to, "subject": subject, "body": body, "files": files,
            "eml": folder / "email.eml", "mailto": link, "opened": opened}
