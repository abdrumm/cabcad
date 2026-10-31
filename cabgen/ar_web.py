"""CabCad "AR view": build the form's job as .glb/.usdz and show how to open it on a phone.

The phone needs the form server on the LAN (opt-in: `cabgen.cli web --lan` or
`cabcad --lan`). Phones may only GET /ar/... (see web.Handler); the form stays local.
"""
from __future__ import annotations

import html
import shutil
import socket
import subprocess
from pathlib import Path
from urllib.parse import quote

AR_DIR = "ar"           # under the web out dir
AR_STEM = "cabcad"      # out/ar/cabcad.glb, out/ar/cabcad.usdz (each build overwrites)
MIME = {".usdz": "model/vnd.usdz+zip", ".glb": "model/gltf-binary", ".svg": "image/svg+xml"}
PREVIEW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 90" width="240" height="180">
<rect width="120" height="90" fill="#eef1f5"/>
<g fill="#d7e0ea" stroke="#3b3f44" stroke-width="1.2">
<rect x="14" y="12" width="30" height="24"/><rect x="44" y="12" width="30" height="24"/><rect x="74" y="12" width="30" height="24"/>
<rect x="14" y="52" width="46" height="30"/><rect x="60" y="52" width="46" height="30"/></g>
<rect x="10" y="48" width="100" height="4" fill="#d8cfbf" stroke="#3b3f44"/>
<g stroke="#3b3f44" stroke-width="2"><line x1="40" y1="28" x2="40" y2="33"/><line x1="48" y1="28" x2="48" y2="33"/>
<line x1="34" y1="56" x2="40" y2="56"/><line x1="80" y1="56" x2="86" y2="56"/></g>
<text x="60" y="88" font-family="sans-serif" font-size="6" text-anchor="middle" fill="#3b3f44">tap to view in your room</text>
</svg>"""


def is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1") or host.startswith("127.")


def lan_ip() -> str | None:
    """This laptop's address on the default-route network (no packet is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))   # TEST-NET; connect() on UDP only picks a route
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return None if ip.startswith("127.") else ip


def phone_base(host: str, port: int) -> str | None:
    """http://<lan ip>:<port> when the server listens on the LAN, else None."""
    if is_loopback(host):
        return None
    ip = lan_ip() if host in ("0.0.0.0", "", "::") else host
    return f"http://{ip}:{port}" if ip else None


def qr_svg(text: str) -> str | None:
    """Inline SVG QR code via the qrencode CLI (installed on Omarchy); None without it."""
    exe = shutil.which("qrencode")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-t", "SVG", "-m", "2", "-s", "6", "-o", "-", text],
                             capture_output=True, text=True, timeout=10, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    start = out.find("<svg")
    return out[start:] if start >= 0 else None


def scene_viewer_intent(glb_url: str, title: str) -> str:
    """Android Scene Viewer. Officially it wants an https file URL; for an http LAN URL the
    intent must still say scheme=https (Google's documented local-testing behaviour)."""
    return ("intent://arvr.google.com/scene-viewer/1.0?file=" + quote(glb_url, safe="")
            + "&mode=ar_preferred&title=" + quote(title, safe="")
            + "#Intent;scheme=https;package=com.google.android.googlequicksearchbox;"
            "action=android.intent.action.VIEW;S.browser_fallback_url="
            + quote(glb_url, safe="") + ";end;")


def _size_text(size_m) -> str:
    w, h, d = size_m
    inch = lambda m: f'{m / 0.0254:.0f}"'
    return f"{inch(w)} wide x {inch(h)} tall x {inch(d)} deep ({w:.2f} x {h:.2f} x {d:.2f} m)"


def panel_html(result: dict, version: str, base: str | None, port: int) -> str:
    """The AR panel under the form."""
    glb = f"/ar/{AR_STEM}.glb?v={version}"
    usdz = f"/ar/{AR_STEM}.usdz?v={version}"
    rows = [
        '<section class="arpanel" id="ar"><h2>AR view</h2>',
        f'<p class="sub">Built {html.escape(_size_text(result["size_m"]))}, {result["boxes"]} parts. '
        'Files are rebuilt each time you press AR view.</p>',
        f'<p><a href="{usdz}" download>{AR_STEM}.usdz</a> (iPhone / iPad) &nbsp; '
        f'<a href="{glb}" download>{AR_STEM}.glb</a> (Android, 3D viewers)</p>',
    ]
    if base:
        url = f"{base}/ar/view?v={version}"
        qr = qr_svg(url)
        rows.append('<div class="arqr">')
        rows.append(f'<div class="qr">{qr}</div>' if qr else "")
        rows.append(
            '<div><p><b>On the phone</b> (same Wi-Fi): open the camera, scan the code, '
            'tap the link, then tap the picture (iPhone) or "View in your room" (Android).</p>'
            f'<p class="mono">{html.escape(url)}</p></div></div>')
    else:
        rows.append(
            '<p class="warn">Phone access is off: the form only listens on this laptop '
            f'(127.0.0.1). To scan from a phone, start CabCad with <code>cabcad --lan</code> '
            f'and allow the port once: <code>sudo ufw allow from 192.168.0.0/16 to any port {port} proto tcp</code>.</p>')
    rows.append("</section><script>document.getElementById('ar').scrollIntoView();</script>")
    return "".join(rows)


def phone_page(base: str, version: str, title: str) -> str:
    glb_url = f"{base}/ar/{AR_STEM}.glb?v={version}"
    usdz = f"/ar/{AR_STEM}.usdz?v={version}"
    t = html.escape(title)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t} - AR</title>
<style>body{{font-family:system-ui,sans-serif;margin:1.2rem;line-height:1.4;color-scheme:light dark}}
a.btn{{display:block;margin:1rem 0;padding:1rem;border-radius:12px;background:#2563eb;color:#fff;
text-align:center;text-decoration:none;font-weight:600}} img{{width:100%;max-width:360px;border-radius:12px}}
.sub{{opacity:.7;font-size:.9rem}}</style></head><body>
<h1>{t}</h1>
<p><b>iPhone / iPad:</b> tap the picture.</p>
<a rel="ar" href="{usdz}"><img src="/ar/preview.svg" alt="View the cabinets in your room"></a>
<p><b>Android:</b></p>
<a class="btn" href="{html.escape(scene_viewer_intent(glb_url, title))}">View in your room (Android)</a>
<p class="sub">Point the phone at the floor, move it slowly until the cabinets appear, then
drag to place them and twist with two fingers to turn them. They are life size.</p>
<p class="sub">Files: <a href="{usdz}">.usdz</a> · <a href="/ar/{AR_STEM}.glb?v={version}">.glb</a></p>
</body></html>"""
