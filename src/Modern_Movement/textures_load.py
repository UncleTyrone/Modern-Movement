"""Load this mod's HUD images with the texture loader that matches the game.

Borderlands 2 and The Pre-Sequel ship different native loaders. Both are in
this package. If that game already has texloader installed, that copy is used.
Otherwise the matching loader in native/ is extracted beside the sdkmod and
used, so a player does not install a second mod. A missing loader leaves the
HUD on its line drawings.
"""

from __future__ import annotations

import importlib.util
import os
import zipfile

_ready = False
_noted = False
_retry_names: tuple[str, ...] = ()
_RETRY_ON = "Engine.GameViewportClient:PostRender"
_RETRY_ID = "mm_texloader_retry"


def _which() -> str | None:
    from . import game

    if game.is_bl2():
        return "bl2"
    if game.is_tps():
        return "tps"
    return None


def _package_file(rel: str) -> bytes | None:
    here = os.path.dirname(os.path.abspath(__file__))
    loose = os.path.join(here, *rel.split("/"))
    if os.path.isfile(loose):
        with open(loose, "rb") as handle:
            return handle.read()
    parts = here.replace("\\", "/").split("/")
    for index, part in enumerate(parts):
        if not part.lower().endswith(".sdkmod"):
            continue
        zpath = os.path.sep.join(parts[: index + 1])
        inner = "/".join(parts[index + 1 :])
        key = f"{inner}/{rel}" if inner else rel
        try:
            with zipfile.ZipFile(zpath) as bundle:
                return bundle.read(key)
        except Exception:  # noqa: BLE001
            return None
    return None


def _native():
    which = _which()
    if which is None:
        return None
    data = _package_file(f"native/{which}/_texloader.pyd")
    if not data:
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    parts = here.replace("\\", "/").split("/")
    root = os.path.dirname(here)
    for index, part in enumerate(parts):
        if part.lower().endswith(".sdkmod"):
            zpath = "/".join(parts[: index + 1])
            root = os.path.dirname(zpath)
            break
    folder = os.path.join(root, ".mm_texloader", which)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "_texloader.pyd")
    try:
        with open(path, "rb") as handle:
            current = handle.read()
    except OSError:
        current = b""
    if current != data:
        with open(path, "wb") as handle:
            handle.write(data)
    spec = importlib.util.spec_from_file_location(f"mm_texloader_{which}", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _loader():
    """(callable load_bytes, needs the Pre-Sequel resource build)."""
    try:
        from texloader.api import load_bytes

        return load_bytes, False
    except Exception:  # noqa: BLE001
        native = _native()
        if native is None:
            return None, False

        def load_bytes(data: bytes, name: str, **_kw) -> str:
            if _which() == "tps":
                from . import texcompat

                texcompat.require()
            path = native.load_image_bytes(
                data, name, None, True, True, False, False, "clamp", "clamp", "linear", "ui", "none",
            )
            if _which() == "tps":
                import unrealsdk

                from . import texcompat

                texcompat.update_resource(unrealsdk.find_object("Texture2D", path))
            return path

        return load_bytes, True


def _png(name: str) -> bytes | None:
    return _package_file(f"textures/{name}.png")


def _exists(name: str) -> bool:
    try:
        import unrealsdk

        return unrealsdk.find_object("Texture2D", "Transient." + name) is not None
    except Exception:  # noqa: BLE001
        return False


def _create(names: tuple[str, ...]) -> None:
    global _ready
    load_bytes, _bundled = _loader()
    if load_bytes is None:
        return
    for name in names:
        if _exists(name):
            continue
        data = _png(name)
        if not data:
            continue
        load_bytes(data, name, lod_group="ui")
    _ready = True


def _retry(*_args) -> None:
    from unrealsdk.hooks import Type, remove_hook

    from . import texcompat

    ok, why = texcompat.check()
    if ok or "no loaded texture" not in why:
        remove_hook(_RETRY_ON, Type.POST, _RETRY_ID)
        if ok and _retry_names:
            _create(_retry_names)


def load_packaged(names: tuple[str, ...]) -> None:
    """Create the HUD textures for this game. Never raises."""
    global _noted, _retry_names
    if not names or _which() is None:
        return
    try:
        _create(names)
    except Exception as exc:  # noqa: BLE001
        text = repr(exc)
        if "no loaded texture" in text:
            _retry_names = names
            try:
                from unrealsdk.hooks import Type, add_hook

                add_hook(_RETRY_ON, Type.POST, _RETRY_ID, _retry)
            except Exception:  # noqa: BLE001
                pass
            return
        if not _noted:
            _noted = True
            try:
                from unrealsdk import logging

                logging.warning(f"[Modern Movement] HUD images stayed on line drawings ({exc!r})")
            except Exception:  # noqa: BLE001
                pass
