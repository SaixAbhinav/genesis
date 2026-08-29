from genesis import load_settings
from genesis.world.state import Agent, Needs
from genesis.world.needs import tick_needs

S = load_settings("configs/settings.json")
MIDNIGHT = 0


def test_near_warmth_regenerates_warmth_at_night():
    a = Agent(id="a", name="A", x=0, y=0, needs=Needs(warmth=50.0))
    tick_needs(a, MIDNIGHT, S, near_warmth=True)
    assert a.needs.warmth == 50 + S["warmth_regen_near_fire_per_min"]


def test_without_warmth_source_still_decays_at_night():
    a = Agent(id="a", name="A", x=0, y=0, needs=Needs(warmth=50.0))
    tick_needs(a, MIDNIGHT, S, near_warmth=False)
    assert a.needs.warmth == 50 - S["warmth_decay_night_per_min"]
