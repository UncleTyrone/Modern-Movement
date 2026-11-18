#!/usr/bin/env python3
"""AST static policies for the TPS Modern Movement co-op package."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Pre Sequel Port" / "Source" / "Modern_Movement"
FEATURE_DIR = SOURCE / "features"

# Feature modules must not call mods_base.get_pc directly. core.get_pc_pawn is allowed only as a
# thin local fallback outside authority mutation blocks (reported, not hard-failed).
BANNED_GET_PC = {"get_pc"}
AUTHORITY_WRITE_ATTRS = {
    "Velocity",
    "Acceleration",
    "Physics",
    "GroundSpeed",
    "CrouchedPct",
    "bDuck",
}


def _calls_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def check_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rel = path.relative_to(SOURCE).as_posix()
    issues: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # mods_base.get_pc(...) or bare get_pc(...) imported from mods_base
            if isinstance(func, ast.Name) and func.id in BANNED_GET_PC and path.parent == FEATURE_DIR:
                issues.append(f"{rel}:{node.lineno}: feature calls get_pc()")
            if isinstance(func, ast.Attribute) and func.attr in BANNED_GET_PC:
                if path.parent == FEATURE_DIR:
                    issues.append(f"{rel}:{node.lineno}: feature calls get_pc()")
    return issues


def main() -> int:
    issues: list[str] = []
    for path in sorted(SOURCE.rglob("*.py")):
        issues.extend(check_file(path))
    # Hard fail only on feature-internal get_pc (plan static policy).
    hard = [item for item in issues if "feature calls get_pc()" in item]
    for item in hard:
        print(item, file=sys.stderr)
    if hard:
        print(f"static_policy: {len(hard)} hard failure(s)", file=sys.stderr)
        return 1
    print("static_policy: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
