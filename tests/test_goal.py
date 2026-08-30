from genesis.world.goal import resolve_goal
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState, Resource

WM = WorldMap(["GGGG", "GGGG", "GGGG", "GGGG"])


def test_gather_far_resource_returns_move_toward_it():
    a = Agent(id="a", name="A", x=0, y=0)
    st = WorldState(0, 1, [a], [Resource(type="berries", x=3, y=0, qty=2, layer=0)])
    goal = {"id": "gather:berries@(3,0,0)", "verb": "gather",
            "params": {"resource": "berries", "x": 3, "y": 0}}
    act = resolve_goal(a, goal, st, WM, {})
    assert act["action"] == "move_to"


def test_gather_adjacent_resource_returns_gather():
    a = Agent(id="a", name="A", x=2, y=0)
    st = WorldState(0, 1, [a], [Resource(type="berries", x=3, y=0, qty=2, layer=0)])
    goal = {"id": "gather:berries@(3,0,0)", "verb": "gather",
            "params": {"resource": "berries", "x": 3, "y": 0}}
    act = resolve_goal(a, goal, st, WM, {})
    assert act == {"action": "gather", "resource": "berries"}


def test_gather_depleted_resource_returns_none():
    a = Agent(id="a", name="A", x=2, y=0)
    st = WorldState(0, 1, [a], [Resource(type="berries", x=3, y=0, qty=0, layer=0)])
    goal = {"id": "gather:berries@(3,0,0)", "verb": "gather",
            "params": {"resource": "berries", "x": 3, "y": 0}}
    assert resolve_goal(a, goal, st, WM, {}) is None
