"""Standalone front elevation for the CE pipeline page."""
import shutil
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from cabgen.cli import main
from cabgen.client_sheet import load_job
from cabgen.front_view import pipeline_html, render_front, write_front_view
from cabgen.web import _handle_front_view, _job_card, _make_handler, _run_page, group_view

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "jobs" / "sample-kitchen.csv"
FORM = {"job": "Smith Kitchen", "bw1": "27", "bs1": "3drawer", "uw1": "27", "us1": "upper",
        "walls": "left", "counter": "laminate"}


def test_front_sheet_is_only_the_elevation():
    job = load_job(SAMPLE, "Sample Kitchen")
    text = render_front(job, "November 8, 2026").to_string()
    assert "FRONT ELEVATION" in text
    assert "bases " in text
    assert 'width="17.0in" height="11.0in"' in text
    assert "PLAN (TOP VIEW)" not in text and "END VIEW" not in text
    assert "Coppinger Exhibits" not in text and "viewBox=\"0 0 2860 960\"" not in text
    assert ">1 of 1<" not in text and "SHEET" not in text


def test_placeholder_links_are_marked():
    job = load_job(SAMPLE, "Sample Kitchen")
    svg = render_front(job, "November 8, 2026")
    page = pipeline_html(job, svg, "front", {}, {"render", "usdz", "glb"})
    assert page.count('class="ce-link placeholder"') == 3
    assert "Placeholder — file not produced" in page
    assert 'href="front-render.png"' in page
    assert 'href="front.usdz"' in page and 'href="front.glb"' in page
    assert 'id="ce-front-view"' in page
    assert "FRONT ELEVATION" in page
    ready = pipeline_html(job, svg, "front",
                          {"render": "front-render.png", "usdz": "front.usdz", "glb": "front.glb"},
                          set())
    assert 'class="ce-link placeholder"' not in ready
    assert "Placeholder — file not produced" not in ready
    assert ready.count('class="ce-link"') == 3


def test_write_front_view_links_the_render_and_the_ar_files(tmp_path: Path):
    job = load_job(SAMPLE, "Sample Kitchen")
    res = write_front_view(job, tmp_path, "front", date="November 8, 2026")
    html = res["html"].read_text(encoding="utf-8")
    assert (tmp_path / "front.svg").is_file()
    assert (tmp_path / "front.usdz").is_file() and (tmp_path / "front.glb").is_file()
    assert 'href="front.usdz"' in html and 'href="front.glb"' in html
    assert "usdz" not in res["placeholders"] and "glb" not in res["placeholders"]
    if shutil.which("rsvg-convert"):
        assert res["pdf"] and res["pdf"].is_file()
        assert (tmp_path / "front-render.png").is_file()
        assert 'href="front-render.png"' in html
        assert 'class="ce-link placeholder"' not in html
    else:
        assert "render" in res["placeholders"]
        assert "Placeholder" in html


def test_cli_writes_the_page(tmp_path: Path):
    assert main(["front", str(SAMPLE), "--out", str(tmp_path), "--name", "Sample Kitchen"]) == 0
    assert (tmp_path / "sample-kitchen-front.html").is_file()
    assert "FRONT ELEVATION" in (tmp_path / "sample-kitchen-front.svg").read_text(encoding="utf-8")


def test_front_view_sits_with_the_other_exports(tmp_path: Path):
    page = _run_page(group_view(None))
    assert 'formaction="/front-view"' in page and ">Front view<" in page
    card = _job_card(tmp_path, "base-run")
    assert 'formaction="/front-view"' in card
    assert 'formtarget="_blank"' in card
    assert card.index("Front view") > card.index("Client")


def test_route_serves_the_page_and_its_files(tmp_path: Path):
    body, err = _handle_front_view(dict(FORM), tmp_path)
    assert body and not err
    assert b"FRONT ELEVATION" in body
    assert (tmp_path / "front-view.html").is_file()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(tmp_path))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        data = urllib.parse.urlencode(FORM).encode()
        req = urllib.request.Request(base + "/front-view", data=data)
        page = urllib.request.urlopen(req)
        assert page.geturl().endswith("/files/front-view.html")
        text = page.read().decode()
        assert "Smith Kitchen" in text and "ce-front-view" in text
        usdz = urllib.request.urlopen(base + "/files/front-view.usdz")
        assert usdz.headers["Content-Type"] == "model/vnd.usdz+zip"
        assert usdz.read(2) == b"PK"
        html_type = urllib.request.urlopen(base + "/files/front-view.html")
        assert html_type.headers["Content-Type"].startswith("text/html")
    finally:
        srv.shutdown()
