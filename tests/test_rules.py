from __future__ import annotations

import pytest

from Modern_Movement.rules import EMPTY_RULES, Ruleset


def test_rules_hash_stable():
    a = EMPTY_RULES.hash
    b = Ruleset.from_payload(EMPTY_RULES.payload()).hash
    assert a == b


def test_rules_schema_rejects_unknown_keys():
    payload = EMPTY_RULES.payload()
    payload["extra"] = {}
    with pytest.raises(ValueError):
        Ruleset.from_payload(payload)