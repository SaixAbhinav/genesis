# tests/test_affordances.py
from genesis.world.affordances import affordances
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState, Resource

WM = WorldMap(["GGGG", "GGGG", "GGGG", "GGGG"])
S = {"campfire_warmth_radius": 2, "strain_heal_threshold": 25.0}


def _agent(**kw):
    return Agent(id="a", name="A", x=0, y=0, **kw)


def test_offers_gather_for_reachable_resource_with_stable_id():
    st = WorldState(0, 1, [_agent()], [Resource(type="berries", x=2, y=1, qty=3, layer=0)])
    opts = affordances(_agent(), st, WM, S)
    berry = [o for o in opts if o["verb"] == "gather" and o["params"].get("resource") == "berries"]
    assert berry, "should offer gathering the berries"
    assert berry[0]["id"] == "gather:berries@(2,1,0)"  # stable: resource identity, not agent-relative


def test_offers_eat_when_holding_berries():
    a = _agent(inventory={"berries": 2})
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, S)
    assert any(o["id"] == "eat" and o["verb"] == "eat" for o in opts)


def test_no_gather_for_resource_on_other_layer():
    a = _agent(layer=0)
    st = WorldState(0, 1, [a], [Resource(type="berries", x=2, y=1, qty=3, layer=1)])
    opts = affordances(a, st, WM, S)
    assert not any(o["verb"] == "gather" for o in opts)
