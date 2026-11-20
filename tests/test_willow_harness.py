"""The installed Willow2 SDK, not a stand-in, has to match what this package calls."""

from scripts.willow_harness import check_installed_helpers, check_package_uses_willow


def test_both_games_have_slammer_helpers():
    problems = check_installed_helpers()
    assert problems == []


def test_movement_calls_the_willow_helpers():
    problems = check_package_uses_willow()
    assert problems == []
