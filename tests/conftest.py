from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Pre Sequel Port" / "Source"
PACKAGE_DIR = SOURCE_ROOT / "Modern_Movement"

_SUBMODULES = (
    "game",
    "protocol",
    "diagnostics",
    "runtime",
    "rules",
    "input_state",
    "gravity",
    "authority",
)


def _install_stubs() -> None:
    if str(SOURCE_ROOT) not in sys.path:
        sys.path.insert(0, str(SOURCE_ROOT))

    if "mods_base" not in sys.modules:
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
            TPS = 1

            @staticmethod
            def get_current():
                return types.SimpleNamespace(name="TPS")

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

    if "unrealsdk" not in sys.modules:
        unrealsdk = types.ModuleType("unrealsdk")
        unrealsdk.logging = types.SimpleNamespace(
            error=lambda *a, **k: None,
            warn=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            info=lambda *a, **k: None,
        )
        unrealsdk.find_class = lambda *_a, **_k: None
        unrealsdk.find_object = lambda *_a, **_k: None
        unrealsdk.make_struct = lambda *_a, **_k: None
        hooks = types.ModuleType("unrealsdk.hooks")
        hooks.Block = object()
        hooks.Type = types.SimpleNamespace(PRE=1, POST=2, POST_UNCONDITIONAL=3)
        hooks.add_hook = lambda *_a, **_k: None
        hooks.remove_hook = lambda *_a, **_k: None
        unrealsdk.hooks = hooks
        sys.modules["unrealsdk"] = unrealsdk
        sys.modules["unrealsdk.hooks"] = hooks

    if "networking" not in sys.modules:
        networking = types.ModuleType("networking")

        def add_network_functions(_ids):  # noqa: ANN001
            return None

        networking.add_network_functions = add_network_functions
        decorators = types.ModuleType("networking.decorators")

        class _Endpoint:
            def string_message(self, fn=None):  # noqa: ANN001
                def wrap(target):
                    return target

                return wrap if fn is None else wrap(fn)

            def json_message(self, fn=None):  # noqa: ANN001
                def wrap(target):
                    return target

                return wrap if fn is None else wrap(fn)

            def message(self, fn=None):  # noqa: ANN001
                def wrap(target):
                    return target

                return wrap if fn is None else wrap(fn)

            def __call__(self, fn):  # noqa: ANN001
                return fn

        decorators.host = _Endpoint()
        decorators.targeted = _Endpoint()
        decorators.broadcast = _Endpoint()
        networking.decorators = decorators
        sys.modules["networking"] = networking
        sys.modules["networking.decorators"] = decorators


def _load_submodule(name: str) -> None:
    qualified = f"Modern_Movement.{name}"
    if qualified in sys.modules:
        return
    path = PACKAGE_DIR / f"{name.replace('.', '/')}.py"
    spec = importlib.util.spec_from_file_location(qualified, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {qualified} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)


def _bootstrap_package() -> None:
    pkg_name = "Modern_Movement"
    if pkg_name not in sys.modules:
        package = types.ModuleType(pkg_name)
        package.__path__ = [str(PACKAGE_DIR)]
        package.__package__ = pkg_name
        sys.modules[pkg_name] = package
    for name in _SUBMODULES:
        _load_submodule(name)


_install_stubs()
_bootstrap_package()


@pytest.fixture(autouse=True)
def _reset_authority_globals():
    import Modern_Movement.authority as authority
    import Modern_Movement.diagnostics as diagnostics

    authority._features.clear()
    authority._send = None
    diagnostics.reset()
    yield
    authority._features.clear()
    authority._send = None
    diagnostics.reset()