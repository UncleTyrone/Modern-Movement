"""Fail if dash/slide co-op source text diverges from locked contracts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "Modern_Movement"


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "OK" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        raise SystemExit(1)


def main() -> None:
    dash = (SRC / "features" / "dash.py").read_text(encoding="utf-8")
    slide = (SRC / "features" / "slide.py").read_text(encoding="utf-8")
    rpc = (SRC / "coop_rpc.py").read_text(encoding="utf-8")

    check("dash hold 0.15s", "_HOST_DASH_S = 0.15" in dash)
    check("host dash dict", "_HOST_DASHES" in dash)
    check("client dash predict", "_CLIENT_DASH" in dash)
    check("dash soft stop 200", "200.0" in dash and "-10.0" in dash)
    check("dash RPC", "ModernMovement:Dash" in rpc)
    # Joiner path must dual-write (local hold + call_host), not host-only.
    req_match = re.search(r"def _dash_request\(\).*?(?=\nOPTIONS|\ndef )", dash, re.S)
    check("found _dash_request", req_match is not None)
    req = req_match.group(0) if req_match else ""
    check("joiner calls server_dash", "server_dash" in req)
    check("joiner starts _CLIENT_DASH", "_CLIENT_DASH" in req)
    check("joiner set_velocity predict", "set_velocity" in req)
    check("joiner ground skim", "PHYS_FALLING" in req)

    check(
        "juso pct enter/exit + flat decay",
        "_JUSO_SLIDE_PCT =" in slide
        and "_JUSO_CROUCH_PCT = 0.5" in slide
        and "_JUSO_DECAY =" in slide,
    )
    check("slide FP arms pose", "_ARMS_SLIDE" in slide and "_begin_slide_pose" in slide)

    check("host slides dict", "_HOST_SLIDES" in slide)
    check("slide latches bDuck", "bDuck = 1" in slide)
    check("slide enter RPC", "ModernMovement:SlideEnter" in rpc)
    # Timed block must not write Velocity.
    timed = re.search(r"if timed:.*?(?=\n    if s\[)", slide, re.S)
    check("found timed slide block", timed is not None)
    block = timed.group(0) if timed else ""
    check("timed has no set_velocity", "set_velocity" not in block)
    check("timed writes CrouchedPct", "CrouchedPct" in block)
    check("tick services host slides", "_service_host_slides" in slide)
    move = re.search(r"def _post_player_move\(.*?(?=\ndef )", slide, re.S)
    check("PlayerMove no double decay", move is not None and "_service_host_slides" not in move.group(0))
    print("parity checks passed")


if __name__ == "__main__":
    main()
