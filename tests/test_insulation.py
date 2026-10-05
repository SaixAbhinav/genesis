from genesis import load_settings
from genesis.world.state import Agent, WorldState
from genesis.world.needs import tick_needs
from genesis.world.properties import PropertyBook

S = load_settings("configs/settings.json")
P = PropertyBook.from_file("configs/properties.json")
MIDNIGHT = 0


def _warmth_after_night_tick(inventory):
    a = Agent(id="a", name="A", x=0, y=0, inventory=dict(inventory))
    a.needs.warmth = 50.0
    tick_needs(a, MIDNIGHT, S, near_warmth=False, props_of=P.props_of)
    return a.needs.warmth


def test_insulating_item_slows_night_warmth_loss():
    plain = 50.0 - _warmth_after_night_tick({})            # loss with nothing
    insulated = 50.0 - _warmth_after_night_tick({"thick_moss": 1})
    assert insulated < plain
    assert abs(insulated - plain * S["insulation_warmth_factor"]) < 1e-9


def test_no_insulation_without_props_of():
    a = Agent(id="a", name="A", x=0, y=0, inventory={"thick_moss": 1})
    a.needs.warmth = 50.0
    tick_needs(a, MIDNIGHT, S, near_warmth=False)          # props_of defaults None
    assert a.needs.warmth == 50.0 - S["warmth_decay_night_per_min"]
