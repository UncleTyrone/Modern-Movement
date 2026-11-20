"""Check the installed Willow2 v3.8 Slammer helpers on both games.

Reads the sdkmods that are actually in each game folder. Movement RPCs in this package
are matched against those modules: every host function is a Networking decorator, and
the crouch hold uses the same InputKey event the keybinds module uses.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "Modern_Movement"

GAMES = {
    "Borderlands 2": Path(r"D:\SteamLibrary\steamapps\common\Borderlands 2\sdk_mods"),
    "Pre-Sequel": Path(r"D:\SteamLibrary\steamapps\common\BorderlandsPreSequel\sdk_mods"),
}

# Willow2 Mod Manager v3.8 Slammer.
EXPECTED = {
    "mods_base.sdkmod": ("mods_base/__init__.py", (1, 12)),
    "networking.sdkmod": ("networking/__init__.py", (1, 2)),
    "keybinds.sdkmod": ("keybinds/__init__.py", (1, 2)),
    "ui_utils.sdkmod": ("ui_utils/__init__.py", (1, 5)),
}

_VERSION = re.compile(r"__version_info__:\s*tuple\[int,\s*int\]\s*=\s*\((\d+),\s*(\d+)\)")


def _version(sdkmod: Path, member: str) -> tuple[int, int]:
    with zipfile.ZipFile(sdkmod) as zf:
        text = zf.read(member).decode("utf-8")
    match = _VERSION.search(text)
    if match is None:
        raise RuntimeError(f"no version in {sdkmod.name}:{member}")
    return int(match.group(1)), int(match.group(2))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def check_installed_helpers() -> list[str]:
    """Return a list of problems. An empty list means both games match Slammer."""
    problems: list[str] = []
    hashes: dict[str, dict[str, str]] = {}
    for game, folder in GAMES.items():
        hashes[game] = {}
        if not folder.is_dir():
            problems.append(f"{game}: sdk_mods folder is missing ({folder})")
            continue
        for name, (member, need) in EXPECTED.items():
            path = folder / name
            if not path.is_file():
                problems.append(f"{game}: {name} is not installed")
                continue
            hashes[game][name] = _sha256(path)
            try:
                found = _version(path, member)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{game}: {name} version unreadable ({exc})")
                continue
            if found != need:
                problems.append(
                    f"{game}: {name} is {found[0]}.{found[1]}, Slammer wants {need[0]}.{need[1]}"
                )
    games = list(GAMES)
    if len(games) == 2 and all(hashes.get(game) for game in games):
        left, right = games
        for name in EXPECTED:
            if hashes[left].get(name) != hashes[right].get(name):
                problems.append(f"{name} differs between {left} and {right}")
    return problems


def check_package_uses_willow() -> list[str]:
    """The movement package has to call the real helpers, not a private copy of them."""
    problems: list[str] = []
    coop = (PACKAGE / "coop_rpc.py").read_text(encoding="utf-8")
    network = (PACKAGE / "network.py").read_text(encoding="utf-8")
    core = (PACKAGE / "core.py").read_text(encoding="utf-8")
    init = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
    if "from networking.decorators import host" not in coop:
        problems.append("coop_rpc does not import networking.decorators.host")
    if "add_network_functions" not in network:
        problems.append("network functions are not attached with add_network_functions")
    if "attach_mod" not in init:
        problems.append("the mod does not attach Networking on startup")
    if "WillowGame.WillowUIInteraction:InputKey" not in core:
        problems.append("crouch hold does not use the Willow2 InputKey event")
    for name in (
        "server_dash",
        "server_double_jump",
        "server_slide_enter",
        "server_slide_exit",
        "server_slide_jump",
        "server_speed_mult",
        "server_holster",
        "server_mantle_start",
        "server_mantle_end",
        "server_slam_begin",
        "server_slam_end",
        "server_slam_impact",
    ):
        if f"def {name}" not in coop:
            problems.append(f"missing host RPC {name}")
    if coop.count("@host.") < 12:
        problems.append("expected every movement RPC to use a @host decorator")
    if "@host.string_message" not in network or "@targeted.string_message" not in network:
        problems.append("the handshake is not on Networking host/targeted endpoints")
    return problems


def main() -> int:
    problems = check_installed_helpers() + check_package_uses_willow()
    if problems:
        print("willow harness failed:")
        for problem in problems:
            print(" -", problem)
        return 1
    print("willow harness ok: both games have Slammer helpers, and movement uses them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
