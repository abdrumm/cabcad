"""Email AR to me / Draft client email: draft only, never sent (Brook, Oct 30)."""
import email
import json
from email import policy
from pathlib import Path

import pytest

from cabgen import drafts
from cabgen.web import _handle_draft, _run_page, group_view

FORM = {"job": "Smith Kitchen", "client": "Ann Smith", "rev": "B", "counter": "laminate",
        "bs1": "3drawer", "bw1": "18", "us1": "upper", "uw1": "30"}


@pytest.fixture(autouse=True)
def _no_open(monkeypatch):
    monkeypatch.setenv("CABCAD_NO_OPEN", "1")
    import smtplib
    monkeypatch.setattr(smtplib, "SMTP", None)        # any attempt to send would blow up


def _eml(path):
    return email.message_from_bytes(Path(path).read_bytes(), policy=policy.default)


def test_config_has_brook_only_and_rick_disabled():
    cfg = drafts.config()
    assert drafts.ar_recipients(cfg) == ["brook@printrbot.com"]
    rick = [r for r in cfg["ar_recipients"] if r["email"] == "ricks@cexhibits.com"]
    assert rick and rick[0]["enabled"] is False


def test_buttons_are_on_the_form():
    page = _run_page(group_view(None))
    assert 'formaction="/email-ar"' in page and ">Email AR to me<" in page


def test_email_ar_writes_a_draft_with_usdz_and_glb(tmp_path):
    page = _handle_draft(dict(FORM), tmp_path, "ar")
    folder = tmp_path / "email-ar" / "smith-kitchen"
    assert "Draft only, nothing was sent" in page
    msg = _eml(folder / "email.eml")
    assert msg["To"] == "brook@printrbot.com" and "ricks@" not in msg.as_string()
    assert msg["X-Unsent"] == "1"
    names = sorted(p.get_filename() for p in msg.iter_attachments())
    assert names == ["cabcad.glb", "cabcad.usdz"]
    assert (folder / "mailto.txt").read_text().startswith("mailto:brook@printrbot.com?subject=AR%3A")
