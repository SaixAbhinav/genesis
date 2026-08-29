from genesis.world.actions import step_action, _find_resource, _tiles_near
from genesis.world.grid import WorldMap
from genesis.world.instinct import _nearest_resource
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


def test_harvest_relic_excludes_different_layer():
    """Regression: relic on same tile but different layer must be excluded."""
    a = Agent(id="a", name="A", x=0, y=0, layer=1, mana_max=40.0)
    r = Resource(type="relic:artifact", x=0, y=0, qty=1, layer=0)  # layer 0, not layer 1
    st = WorldState(0, 1, [a], resources=[r])
    a.current_action = {"action": "harvest_relic"}
    ev = step_action(a, st, WM, SET, None, None)
    # Should fail because relic is on different layer
    assert any(e["type"] == "harvest_failed" for e in ev)
    # Relic qty must remain unchanged
    assert r.qty == 1


def test_find_resource_excludes_different_layer():
    """Regression: _find_resource must exclude resources on different layers."""
    a = Agent(id="a", name="A", x=0, y=0, layer=1)
    # Resource on layer 0, at agent's location
    r = Resource(type="berries", x=0, y=0, qty=5, layer=0)
    st = WorldState(0, 1, [a], resources=[r])
    tiles = _tiles_near(a, WM)
    # When agent is on layer 1, should not find resource on layer 0
    result = _find_resource(st, "berries", tiles, a)
    assert result is None
    # Verify resource is still there
    assert r.qty == 5


def test_nearest_resource_excludes_different_layer():
    """Regression: _nearest_resource must exclude resources on different layers."""
    a = Agent(id="a", name="A", x=0, y=0, layer=1)
    # Berry resource on layer 0 (only 1 tile away)
    r = Resource(type="berries", x=0, y=0, qty=5, layer=0)
    st = WorldState(0, 1, [a], resources=[r])
    # When agent is on layer 1, should not find resource on layer 0
    result = _nearest_resource(a, st, "berries")
    assert result is None
