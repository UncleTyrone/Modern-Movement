"""Sprint Surge: press sprint again while sprinting to holster your weapon and get a speed boost
(30%, building to 70% over "Sprint Surge Speed Ramp Up").
Press it again while surging to end it (the weapon is drawn and the boost stops).

This module only owns the Sprint Surge options. The behaviour itself (detecting the second
sprint press, stowing the weapon, the GroundSpeed boost and drawing the weapon again) lives in
holster.py, because it shares the holster state and the sprint detection with the holster.
holster.py imports these options; the "Sprint Surge" key binding is listed there too.
"""

from mods_base import BoolOption, SliderOption

from .. import authority, core, hudfx, network

enabled_option = BoolOption(
    "Sprint Surge Enabled",
    True,
    "On",
    "Off",
    description="Turn sprint surge on or off.",
)

BOOST_START = 30.0   # % speed boost when a surge starts...
BOOST_FULL = 70.0    # ...ramping up to this over "Sprint Surge Speed Ramp Up"

ramp_slider = SliderOption(
    "Sprint Surge Speed Ramp Up",
    value=3.0,
    min_value=0.0,
    max_value=10.0,
    step=0.5,
    is_integer=False,
    description=(
        "Seconds to climb from +30% to +70% of the run you already have. "
        "0 is instant. 10 is the longest climb. This is not a 10x multiplier. "
        "Each player keeps their own value."
    ),
)

indicator_option = BoolOption(
    "Sprint Surge Indicator",
    True,
    "On",
    "Off",
    description="Arcs either side of the crosshair show while you surge, pushing outward as the boost builds "
                "and sweeping away once you reach full boost.",
)


def ramp(surging_for: float) -> float:
    """0 (just started) .. 1 (full boost)."""
    secs = float(ramp_slider.value)
    if secs <= 0.0:
        return 1.0
    return max(0.0, min(1.0, surging_for / secs))


def boost(surging_for: float) -> float:
    """The speed boost in %, surging_for seconds into a surge."""
    return BOOST_START + (BOOST_FULL - BOOST_START) * ramp(surging_for)


tilt_slider = SliderOption(
    "Sprint Surge Camera Tilt (%)",
    value=80,
    min_value=0,
    max_value=200,
    step=10,
    is_integer=True,
    description="The view leans forward while Sprint Surge is active and eases back when it ends. Your aim moves with it and returns exactly. 0 = off.",
)


def _snapshot(ctx) -> dict:
    from . import holster

    return holster.surge_snapshot(ctx)


def _presentation(event: str, payload: dict) -> None:
    if event == "desync":
        hudfx.surge_state(False, 0.0)
        return
    state_payload = payload.get("state", payload)
    if not isinstance(state_payload, dict):
        return
    features = state_payload.get("features")
    surge_payload = features.get("surge") if isinstance(features, dict) else state_payload
    if not isinstance(surge_payload, dict):
        surge_payload = state_payload
    active = bool(surge_payload.get("active"))
    elapsed = float(surge_payload.get("elapsed", 0.0))
    if active and indicator_option.value:
        hudfx.surge_state(True, ramp(elapsed))
    elif event in ("state", "accept", "end"):
        hudfx.surge_state(False, 0.0)


def on_enable() -> None:
    authority.register_feature(
        "surge",
        authority.FeatureController(snapshot=_snapshot),
    )
    network.register_presentation("surge", _presentation)


def on_disable() -> None:
    authority.unregister_feature("surge")
    network.unregister_presentation("surge")
    hudfx.surge_state(False, 0.0)


OPTIONS = [
    enabled_option,
    *core.settings([indicator_option, ramp_slider, tilt_slider], "Fine-tune Sprint Surge."),
]
KEYBINDS = []
HOOKS = []