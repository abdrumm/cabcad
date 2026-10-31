"""CabCad AR view: CLI, the panel, the phone page, and LAN access limits."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from cabgen import ar_web
from cabgen.cli import main
from cabgen.web import _handle_ar, _make_handler

FORM = {"uw1": "18", "us1": "upper1", "uh1": "left", "uw2": "30", "us2": "microwave",
        "bw1": "30", "bs1": "base", "bd1": "6", "bw2": "18", "bs2": "3drawer", "walls": "left",
        "counter": "laminate"}


def test_cli_ar_writes_both_files(tmp_path: Path):
    sheet = Path(__file__).resolve().parents[1] / "jobs" / "sample-kitchen.csv"
    assert main(["ar", str(sheet), "--out", str(tmp_path), "--name", "s"]) == 0
    assert (tmp_path / "s.glb").stat().st_size > 0 and (tmp_path / "s.usdz").stat().st_size > 0


def test_web_lan_flag_is_opt_in():
    from cabgen.cli import build_parser
    assert build_parser().parse_args(["web"]).host == "127.0.0.1"
    assert build_parser().parse_args(["web"]).lan is False
    assert build_parser().parse_args(["web", "--lan"]).lan is True


def test_panel_local_only_explains_lan(tmp_path: Path):
    page = _handle_ar(dict(FORM), tmp_path, "127.0.0.1", 8777)
    assert 'id="ar"' in page and "cabcad --lan" in page and "ufw allow" in page
    assert (tmp_path / "ar" / "cabcad.glb").is_file() and (tmp_path / "ar" / "cabcad.usdz").is_file()
    meta = json.loads((tmp_path / "ar" / "cabcad.json").read_text())
    assert meta["version"] and meta["size_m"][0] > 1.2


def test_panel_on_lan_has_qr_and_phone_url(tmp_path: Path, ):
    page = _handle_ar(dict(FORM), tmp_path, "0.0.0.0", 8777)
    ip = ar_web.lan_ip()
    if ip:
        assert f"http://{ip}:8777/ar/view?v=" in page
        if ar_web.qr_svg("x"):
            assert "<svg" in page.split('id="ar"')[1]


def test_phone_page_links():
    page = ar_web.phone_page("http://192.168.1.5:8777", "123", "Smith kitchen")
    assert '<a rel="ar" href="/ar/cabcad.usdz?v=123"><img' in page
    assert "intent://arvr.google.com/scene-viewer/1.0?file=http%3A%2F%2F192.168.1.5%3A8777%2Far%2Fcabcad.glb" in page
    assert "scheme=https;package=com.google.android.googlequicksearchbox" in page


def test_server_serves_models_with_ar_mime_types(tmp_path: Path):
    _handle_ar(dict(FORM), tmp_path, "127.0.0.1", 8777)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(tmp_path, "127.0.0.1", 0))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        r = urllib.request.urlopen(f"{base}/ar/cabcad.usdz")
        assert r.headers["Content-Type"] == "model/vnd.usdz+zip" and r.read(2) == b"PK"
        r = urllib.request.urlopen(f"{base}/ar/cabcad.glb")
        assert r.headers["Content-Type"] == "model/gltf-binary" and r.read(4) == b"glTF"
        r = urllib.request.urlopen(urllib.request.Request(f"{base}/ar/cabcad.glb", method="HEAD"))
        assert int(r.headers["Content-Length"]) > 0
        assert 'rel="ar"' in urllib.request.urlopen(f"{base}/ar/view").read().decode()
        try:
            urllib.request.urlopen(f"{base}/ar/../ar-view.csv")
            raise AssertionError("served a non-model file")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        srv.shutdown()


def test_lan_clients_only_get_ar_pages(tmp_path: Path):
    handler = _make_handler(tmp_path, "0.0.0.0", 8777)
    calls = []

    class Fake(handler):
        def __init__(self, path, client):   # no socket: drive do_GET/do_POST directly
            self.path, self.client_address = path, (client, 5555)
            self.headers = {"Host": "192.168.1.121:8777", "Content-Length": "0"}

        def _html(self, body, status=200):
            calls.append((self.path, status))

        def _page(self, body):
            calls.append((self.path, 200))

        def _send(self, body, ctype, status=200):
            calls.append((self.path, status))

    Fake("/run", "192.168.1.50").do_GET()
    Fake("/files/base-run.csv", "192.168.1.50").do_GET()
    Fake("/run", "192.168.1.50").do_POST()
    Fake("/ar/preview.svg", "192.168.1.50").do_GET()
    Fake("/run", "127.0.0.1").do_GET()
    assert calls == [("/run", 403), ("/files/base-run.csv", 403), ("/run", 403),
                     ("/ar/preview.svg", 200), ("/run", 200)]
