# CabCAD repo notes

Read [`HANDOFF.md`](HANDOFF.md) first: what CabCAD is, how to run it, where the
master lives, what is in v0.15, test status, and next steps.

Rules for this repo:
- Master is `~/Work/cabcad` on the iMac; GitHub `abdrumm/cabcad` is the backup.
- Keep the 33-1/2" finished height rule (base case = 33.5 minus the countertop
  build) unless Brook changes it. Mark guesses "(inferred)".
- QuickBase is read-only. Never send email or messages for Brook; draft only.
- Tests: `.venv/bin/python -m pytest -q` (or `python3 -m pytest`).
- Version lives in one place: `cabgen/__init__.py`.
