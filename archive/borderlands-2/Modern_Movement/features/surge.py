"""Sprint Surge: press sprint again while sprinting to holster your weapon and get a speed boost
(30%, building to 70% over "Sprint Surge Speed Ramp Up").
Press it again while surging to end it (the weapon is drawn and the boost stops).

This module only owns the Sprint Surge options. The behaviour itself (detecting the second
sprint press, stowing the weapon, the GroundSpeed boost and drawing the weapon again) lives in
holster.py, because it shares the holster state and the sprint detection with the holster.
holster.py imports these options; the "Sprint Surge" key binding is listed there too.
"""

from mods_base import BoolOption, SliderOption
from .. import core

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
    description="Adjust the time you have to surge for the full boost.",
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


def on_enable() -> None:
    pass


def on_disable() -> None:
    pass


# Camera Tilt (80) is fixed: not in the menu.
OPTIONS = [enabled_option, *core.settings([indicator_option, ramp_slider], "Fine-tune Sprint Surge.")]
KEYBINDS = []
HOOKS = []
