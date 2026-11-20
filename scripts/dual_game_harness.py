#!/usr/bin/env python3
"""Boot the package as Borderlands 2 and as The Pre-Sequel, and audit every source line.

Exit 0 only when every check passes. A child process is one game:
    python scripts/dual_game_harness.py --game BL2
    python scripts/dual_game_harness.py --game TPS
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
PACKAGE = SOURCE / "Modern_Movement"
REPORT = ROOT / "reports" / "DUAL_GAME_HARNESS.json"
TEXT_SUFFIXES = {".py", ".md", ".toml", ".json", ".txt"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}


def _install_stubs(game_name: str) -> None:
    import types

    if str(SOURCE) not in sys.path:
        sys.path.insert(0, str(SOURCE))

    mods_base = types.ModuleType("mods_base")
    mods_base.ENGINE = object()
    mods_base.get_pc = lambda *a, **k: None
    mods_base.build_mod = lambda *_a, **_k: types.SimpleNamespace()
    mods_base.NestedOption = object()
    mods_base.GroupedOption = object()

    class _Option:
        def __init__(self, *args, **kwargs):
            self.value = kwargs.get("value", args[1] if len(args) > 1 else True)
            self.key = kwargs.get("key", args[1] if len(args) > 1 else None)

    class _Game:
        BL2 = 1
        TPS = 2

        @staticmethod
        def get_current():
            return SimpleNamespace(name=game_name)

    class _CoopSupport:
        RequiresAllPlayers = "RequiresAllPlayers"
        Optional = "Optional"
        ClientSide = "ClientSide"

    def _hook(*_a, **_k):
        def decorator(fn):
            return fn

        return decorator

    def _keybind(*_a, **_k):
        def decorator(fn):
            fn.key = _a[1] if len(_a) > 1 else None
            return fn

        return decorator

    mods_base.BoolOption = _Option
    mods_base.SliderOption = _Option
    mods_base.Game = _Game
    mods_base.CoopSupport = _CoopSupport
    mods_base.hook = _hook
    mods_base.keybind = _keybind
    sys.modules["mods_base"] = mods_base

    unrealsdk = types.ModuleType("unrealsdk")
    unrealsdk.logging = SimpleNamespace(
        error=lambda *a, **k: None,
        warn=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        info=lambda *a, **k: None,
    )
    unrealsdk.find_class = lambda *_a, **_k: None
    unrealsdk.find_object = lambda *_a, **_k: None
    unrealsdk.make_struct = lambda *_a, **_k: None
    unrealsdk.load_package = lambda *_a, **_k: None
    hooks = types.ModuleType("unrealsdk.hooks")
    hooks.Block = object()
    hooks.Type = SimpleNamespace(PRE=1, POST=2, POST_UNCONDITIONAL=3)
    hooks.add_hook = lambda *_a, **_k: None
    hooks.remove_hook = lambda *_a, **_k: None
    unrealsdk.hooks = hooks
    sys.modules["unrealsdk"] = unrealsdk
    sys.modules["unrealsdk.hooks"] = hooks

    networking = types.ModuleType("networking")
    networking.add_network_functions = lambda *_a, **_k: None
    decorators = types.ModuleType("networking.decorators")

    class _Endpoint:
        def string_message(self, fn=None):
            def wrap(target):
                return target

            return wrap if fn is None else wrap(fn)

        def json_message(self, fn=None):
            def wrap(target):
                return target

            return wrap if fn is None else wrap(fn)

        def message(self, fn=None):
            def wrap(target):
                return target

            return wrap if fn is None else wrap(fn)

        def __call__(self, fn):
            return fn

    decorators.host = _Endpoint()
    decorators.targeted = _Endpoint()
    decorators.broadcast = _Endpoint()
    networking.decorators = decorators
    sys.modules["networking"] = networking
    sys.modules["networking.decorators"] = decorators


def _audit_roots() -> list[Path]:
    """Ship code, tests, docs, and the original BL2 tree. Research dumps are not the package."""
    roots = [
        PACKAGE,
        ROOT / "archive" / "borderlands-2",
        ROOT / "tests",
        ROOT / "scripts",
        ROOT / "docs",
        ROOT / "build",
    ]
    return [path for path in roots if path.exists()]


def _classify_tree(root: Path) -> dict:
    files = []
    failures = []
    targets = _audit_roots() if root == ROOT else [root]
    paths = []
    for target in targets:
        paths.extend(target.rglob("*"))
    for extra in (ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "pyproject.toml"):
        if extra.is_file():
            paths.append(extra)
    for path in sorted(set(paths)):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() not in TEXT_SUFFIXES:
            try:
                size = path.stat().st_size
            except OSError as exc:
                failures.append(f"{rel}: unreadable binary ({exc})")
                continue
            files.append({"path": rel, "kind": "binary", "bytes": size, "lines": 1, "audited": 1})
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            failures.append(f"{rel}: not utf-8 ({exc})")
            continue
        lines = text.splitlines()
        record = {"path": rel, "kind": "text", "lines": len(lines), "audited": len(lines)}
        if path.suffix == ".py":
            try:
                tree = ast.parse(text, filename=str(path))
                compile(tree, str(path), "exec")
                record["python"] = "compiled"
            except SyntaxError as exc:
                failures.append(f"{rel}:{exc.lineno}: {exc.msg}")
                record["python"] = "syntax-error"
        if record["lines"] != record["audited"]:
            failures.append(f"{rel}: audited {record['audited']} of {record['lines']} lines")
        files.append(record)
    return {"files": files, "failures": failures}


def _run_game(game_name: str) -> None:
    _install_stubs(game_name)
    import Modern_Movement as mm

    names = [label for label, _feature, _blurb in mm._FEATURES]
    expected = ["Double Jump", "Dash", "Misc", "Sprint Surge", "Mantle/Vault", "Slide"]
    for label in expected:
        if label not in names:
            raise SystemExit(f"{game_name}: missing feature {label}")
    if game_name == "BL2":
        if "Slam" not in names:
            raise SystemExit("BL2: Slam did not load")
        if not mm._game.is_bl2():
            raise SystemExit("BL2: game.current is not BL2")
    elif game_name == "TPS":
        if "Slam" in names:
            raise SystemExit("TPS: custom Slam loaded beside native Oz slam")
        if not mm._game.is_tps():
            raise SystemExit("TPS: game.current is not TPS")
    else:
        raise SystemExit(f"unknown game {game_name}")
    if not mm._game.supported():
        raise SystemExit(f"{game_name}: supported() is false")

    for label, feature, _blurb in list(mm._FEATURES):
        try:
            feature.on_enable()
            feature.on_disable()
        except Exception:
            traceback.print_exc()
            raise SystemExit(f"{game_name}: {label} enable/disable failed")

    if game_name == "BL2":
        from Modern_Movement import core
        from Modern_Movement.features import slam
        from Modern_Movement.runtime import ExecutionRole, PlayerContext, PlayerKey

        slam.on_enable()
        pawn = SimpleNamespace(
            Physics=core.PHYS_FALLING,
            Velocity=SimpleNamespace(X=180.0, Y=0.0, Z=20.0),
            Location=SimpleNamespace(X=0.0, Y=0.0, Z=1200.0),
            Health=100.0,
            JumpZ=630.0,
            Class=SimpleNamespace(Name="WillowPlayerPawn"),
        )
        pc = SimpleNamespace(bDuck=0, Pawn=pawn, PlayerInput=SimpleNamespace(PressedKeys=[], Bindings=[]))
        ctx = PlayerContext(
            key=PlayerKey(1, 3),
            role=ExecutionRole.LOCAL_STANDALONE,
            controller=pc,
            pawn=pawn,
            clock=5.0,
            pawn_generation=1,
        )

        def start():
            slam._start(pc, pawn)

        core.execute(ctx, start)
        if slam._slam is None or pawn.Velocity.Z >= 0.0:
            raise SystemExit("BL2: slam dive did not start")

        def tick():
            slam._tick(pc, pawn, 1.0 / 60.0)

        core.execute(ctx, tick)
        if slam._slam is None:
            raise SystemExit("BL2: slam dive died on the next tick")
        slam.on_disable()
        if slam._slam is not None:
            raise SystemExit("BL2: slam stayed active after disable")

    print(f"HARNESS_GAME_OK {game_name} features={','.join(names)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=("BL2", "TPS"))
    args = parser.parse_args()
    if args.game:
        _run_game(args.game)
        return 0

    audit = _classify_tree(ROOT)
    if audit["failures"]:
        print("\n".join(audit["failures"]), file=sys.stderr)
        return 1

    games = {}
    for game_name in ("BL2", "TPS"):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--game", game_name],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        games[game_name] = {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        if result.returncode != 0 or f"HARNESS_GAME_OK {game_name}" not in result.stdout:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            return 1

    text_files = [item for item in audit["files"] if item["kind"] == "text"]
    line_total = sum(item["lines"] for item in text_files)
    audited = sum(item["audited"] for item in text_files)
    report = {
        "games": games,
        "text_files": len(text_files),
        "lines": line_total,
        "audited_lines": audited,
        "binary_files": sum(1 for item in audit["files"] if item["kind"] == "binary"),
        "failures": audit["failures"],
        "success": audited == line_total and not audit["failures"],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["success"]:
        return 1
    print(
        f"HARNESS_OK games=BL2,TPS files={report['text_files']} "
        f"lines={line_total} audited={audited}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
