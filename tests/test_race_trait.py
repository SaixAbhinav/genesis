from genesis import load_settings
from genesis.world.state import Agent
from genesis.world.needs import tick_needs

S = load_settings("configs/settings.json")
MIDNIGHT = 0


def _warmth_loss(mult):
    a = Agent(id="a", name="A", x=0, y=0, warmth_decay_mult=mult)
    a.needs.warmth = 50.0
    tick_needs(a, MIDNIGHT, S, near_warmth=False)
    return 50.0 - a.needs.warmth


def test_default_race_and_mult():
    a = Agent(id="a", name="A", x=0, y=0)
    assert a.race == "" and a.warmth_decay_mult == 1.0


def test_warmth_trait_scales_night_decay():
    base = _warmth_loss(1.0)
    hardy = _warmth_loss(0.6)
    assert base > 0
    assert abs(hardy - base * 0.6) < 1e-9
