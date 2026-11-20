"""Host-authoritative gameplay rules separate from local presentation options."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .protocol import digest


@dataclass(frozen=True)
class Ruleset:
    revision: int = 1
    double_jump: dict[str, Any] = field(default_factory=dict)
    dash: dict[str, Any] = field(default_factory=dict)
    holster: dict[str, Any] = field(default_factory=dict)
    surge: dict[str, Any] = field(default_factory=dict)
    mantle: dict[str, Any] = field(default_factory=dict)
    slide: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def hash(self) -> str:
        return digest(self.payload())

    def with_revision(self, revision: int) -> "Ruleset":
        data = self.payload()
        data["revision"] = revision
        return Ruleset(**data)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "Ruleset":
        expected = {"revision", "double_jump", "dash", "holster", "surge", "mantle", "slide"}
        if set(payload) != expected:
            raise ValueError("invalid rules schema")
        if isinstance(payload["revision"], bool) or not isinstance(payload["revision"], int):
            raise ValueError("invalid rules revision")
        for key in expected - {"revision"}:
            if not isinstance(payload[key], dict):
                raise ValueError(f"invalid rules section: {key}")
        return cls(**payload)


def canonical_json(rules: Ruleset) -> str:
    return json.dumps(rules.payload(), allow_nan=False, separators=(",", ":"), sort_keys=True)


EMPTY_RULES = Ruleset(
    double_jump={"enabled": False, "strength": 100, "extra_jumps": 1, "only_rising": False},
    dash={
        "enabled": False,
        "air_only": False,
        "cooldown": 2,
        "dodge": False,
        "perfect_window_ms": 150,
    },
    holster={"enabled": False, "while_sprinting": False},
    surge={"enabled": False, "ramp_seconds": 3.0, "boost_min": 0.30, "boost_max": 0.70},
    mantle={"enabled": False, "vault": False, "max_height": 200.0},
    slide={"enabled": False, "distance_percent": 80},
)


def collect_live_rules(revision: int = 1) -> Ruleset:
    """Snapshot host gameplay options into an immutable ruleset (presentation stays local)."""
    from .features import dash, double_jump, holster, mantle, slide, surge

    return Ruleset(
        revision=revision,
        double_jump={
            "enabled": bool(double_jump.enabled_option.value),
            "strength": int(double_jump.strength_slider.value),
            "extra_jumps": int(double_jump.extra_jumps_slider.value),
            "only_rising": bool(double_jump.only_rising_option.value),
        },
        dash={
            "enabled": bool(dash.enabled_option.value),
            "air_only": bool(dash.air_only_option.value),
            "cooldown": int(dash.cooldown_slider.value),
            "dodge": bool(dash.dodge_option.value),
            "perfect_window_ms": int(dash.perfect_slider.value),
        },
        holster={
            "enabled": bool(holster.enabled_option.value),
            "while_sprinting": bool(holster.holster_sprinting_option.value),
        },
        surge={
            "enabled": bool(surge.enabled_option.value),
            "ramp_seconds": float(surge.ramp_slider.value),
            "boost_min": float(surge.BOOST_START) / 100.0,
            "boost_max": float(surge.BOOST_FULL) / 100.0,
        },
        mantle={
            "enabled": bool(mantle.enabled_option.value),
            "vault": bool(mantle.vault_option.value),
            "max_height": float(mantle.max_height_slider.value),
        },
        slide={
            "enabled": bool(slide.enabled_option.value),
            "distance_percent": int(slide.distance_slider.value),
        },
    )
