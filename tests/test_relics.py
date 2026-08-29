from genesis.world.actions import step_action
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, Resource, WorldState

WM = WorldMap(["GG", "GG"])
SET = {"campfire_warmth_radius": 1,
       "relics": {"relic:artifact": {"value": 50, "mana_max": 10}}}


def test_harvest_relic_adds_value_and_mana_max():
    a = Agent(id="a", name="A", x=0, y=0, layer=1, mana_max=40.0)
    r = Resource(type="relic:artifact", x=0, y=0, qty=1, layer=1)
    st = WorldState(0, 1, [a], resources=[r])
    a.current_action = {"action": "harvest_relic"}
    ev = step_action(a, st, WM, SET, None, None)
    assert a.inventory.get("relic_value") == 50
    assert a.mana_max == 50.0
    assert r.qty == 0 and any(e["type"] == "relic_taken" for e in ev)


def test_harvest_relic_fails_when_none_here():
    a = Agent(id="a", name="A", x=0, y=0, layer=1)
    st = WorldState(0, 1, [a], resources=[])
    a.current_action = {"action": "harvest_relic"}
    ev = step_action(a, st, WM, SET, None, None)
    assert any(e["type"] == "harvest_failed" for e in ev)
