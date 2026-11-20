"""Pre-Sequel texture layout check, vendored from the installed texloader 1.1.9 fork.

MIT. Copyright (c) 2026. The notice is in native/LICENSE.txt.
Borderlands 2 uses its own native module and does not need this check.

Game check for this fork: texloader on Borderlands 2, The Pre-Sequel and Tiny Tina's Assault on Dragon Keep.

The native module finds every UObject field through the SDK's reflection, and copies the engine's mip-block
vtable from a live texture, so it carries no BL2 addresses. What it does assume is BL2's engine layout of a
texture's mips: `Texture2D.Mips` a StructProperty holding a pointer array, each element a 0x3c-byte
FTexture2DMipMap block with SizeX/SizeY at +0x34/+0x38. Before anything is written on a game other than BL2,
that layout is checked against the game's own live textures (read only); if it doesn't match, no texture is
created and the reason is logged, so the game is never written into the wrong shape.

The Pre-Sequel also needs each texture's render resource built by hand (`update_resource`, below).
"""

from __future__ import annotations

import ctypes
import struct

import unrealsdk
from mods_base import Game
from unrealsdk import logging

BLOCK_SIZE_X = 0x34     # FTexture2DMipMap: SizeX, SizeY after the 0x34-byte FByteBulkData
BLOCK_SIZE_Y = 0x38
WANT_MATCHES = 8        # live textures whose mip 0 must agree before the layout is trusted
LOOK_AT = 4000          # textures looked at, at most

_result: tuple[bool, str] | None = None


def _read(addr: int, fmt: str) -> tuple:
    return struct.unpack(fmt, ctypes.string_at(addr, struct.calcsize(fmt)))


def _probe() -> tuple[bool, str]:
    try:
        game = Game.get_current()
    except Exception as e:  # noqa: BLE001
        return False, f"couldn't tell which game this is ({e!r})"
    if game == Game.BL2:
        return True, "Borderlands 2"
    name = getattr(game, "name", str(game))
    try:
        cls = unrealsdk.find_class("Texture2D")
        prop = cls._find("Mips")
    except Exception as e:  # noqa: BLE001
        return False, f"{name}: Texture2D has no Mips field ({e!r})"
    kind = str(prop.Class.Name)
    if kind != "StructProperty":
        return False, f"{name}: Texture2D.Mips is a {kind}, not BL2's StructProperty"
    offset = int(prop.Offset_Internal)
    matches = mismatches = looked = 0
    for tex in unrealsdk.find_all("Texture2D", exact=False):
        looked += 1
        if looked > LOOK_AT or matches >= WANT_MATCHES:
            break
        try:
            if str(tex.Name).startswith("Default__"):
                continue
            data, count = _read(tex._get_address() + offset, "<Ii")
            if not data or count <= 0 or count > 16:
                continue
            (block,) = _read(data, "<I")
            if not block:
                continue
            sx, sy = _read(block + BLOCK_SIZE_X, "<ii")
            want = (int(tex.SizeX), int(tex.SizeY))
        except Exception:  # noqa: BLE001
            continue
        if want[0] <= 0 or want[1] <= 0:
            continue
        if (sx, sy) == want:
            matches += 1
        else:
            mismatches += 1
            if mismatches >= 3 and matches == 0:
                break
    if matches >= WANT_MATCHES and mismatches == 0:
        return True, f"{name}: texture layout matches Borderlands 2 ({matches} live textures checked)"
    if matches == 0 and mismatches == 0:
        return False, f"{name}: no loaded texture with mips to check the layout against (looked at {looked})"
    return False, (f"{name}: texture layout differs from Borderlands 2 ({matches} textures agreed, "
                   f"{mismatches} didn't): no textures will be created")


def check() -> tuple[bool, str]:
    """(compatible, why), worked out once."""
    global _result
    if _result is None or (not _result[0] and "no loaded texture" in _result[1]):
        try:
            _result = _probe()
        except Exception as e:  # noqa: BLE001
            _result = (False, f"layout check failed ({e!r})")
        if _result[0] or "no loaded texture" in _result[1]:   # (fine, or too early to tell: the log file only)
            logging.dev_warning(f"[texloader] {_result[1]}")
        else:
            logging.warning(f"[texloader] {_result[1]}")
    return _result


def require() -> None:
    ok, why = check()
    if not ok:
        raise RuntimeError(f"texloader is unavailable here: {why}")


# ---- The Pre-Sequel: building a texture's render resource directly
# TPS's build has no PostEditChangeProperty for textures (its slot is an empty stub: no editor code), so the
# native module's call there builds nothing and every texture draws white. The function that does the work,
# UTexture2D::UpdateResource, is in the texture's virtual table at slot 75 on TPS (85 on BL2: TPS's UObject
# has ten fewer virtuals). Found by reading both games' code: the slot is only ever called after its first
# bytes are checked against UPDATE_RESOURCE_HEAD (push esi; mov esi,ecx; cmp byte [esi+0x74],0x1a; je;
# mov eax,[esi]; mov edx,[eax+0x154]), so a different game or version is never called into blind.
UPDATE_RESOURCE_SLOTS = {"TPS": 75}
UPDATE_RESOURCE_HEAD = bytes.fromhex("568bf1807e741a74438b068b9054010000")
_thunk = None


def _call_thiscall(this: int, fn: int) -> None:
    """Call a no-argument __thiscall function (this in ECX) from Python: a three-instruction shim
    (mov ecx,[esp+4]; mov eax,[esp+8]; jmp eax), called as cdecl, so the stack stays balanced."""
    global _thunk
    if _thunk is None:
        k32 = ctypes.windll.kernel32
        k32.VirtualAlloc.restype = ctypes.c_void_p
        k32.VirtualAlloc.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32)
        mem = k32.VirtualAlloc(None, 16, 0x3000, 0x40)    # (MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
        if not mem:
            raise OSError("VirtualAlloc failed")
        code = bytes.fromhex("8b4c24048b442408ffe0")
        ctypes.memmove(mem, code, len(code))
        _thunk = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(mem)
    _thunk(ctypes.c_void_p(this), ctypes.c_void_p(fn))


def update_resource(tex) -> str:
    """(TPS) build the texture's render resource from its mips, as the engine's own UpdateResource does.
    Returns what happened."""
    name = getattr(Game.get_current(), "name", "?")
    slot = UPDATE_RESOURCE_SLOTS.get(name)
    if slot is None:
        return f"no UpdateResource slot known for {name}"
    this = tex._get_address()
    (vt,) = _read(this, "<I")
    (fn,) = _read(vt + 4 * slot, "<I")
    head = ctypes.string_at(fn, len(UPDATE_RESOURCE_HEAD))
    if head != UPDATE_RESOURCE_HEAD:
        return f"slot {slot} isn't UpdateResource on this {name} build ({head.hex()}): not called"
    _call_thiscall(this, fn)
    try:
        res = tex.Class._find("Resource")
        (rp,) = _read(this + int(res.Offset_Internal), "<I")
    except Exception:  # noqa: BLE001
        rp = -1
    return f"UpdateResource called; Resource 0x{rp:08x}"
