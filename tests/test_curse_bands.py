import random
from genesis.world.abyss import action_fails


def test_action_fails_inside_band_when_roll_low():
    cfg = {"curse_band": [20, 50], "curse_fail_chance": 1.0}

    class A:  # minimal stand-in
        strain = 30.0
    assert action_fails(A(), cfg, random.Random(0)) is True


def test_action_ok_outside_band():
    cfg = {"curse_band": [20, 50], "curse_fail_chance": 1.0}

    class A:
        strain = 10.0
    assert action_fails(A(), cfg, random.Random(0)) is False


def test_action_ok_when_roll_high():
    cfg = {"curse_band": [20, 50], "curse_fail_chance": 0.0}

    class A:
        strain = 30.0
    assert action_fails(A(), cfg, random.Random(0)) is False
