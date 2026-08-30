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


def test_sleep_returns_the_action():
    a = Agent(id="a", name="A", x=0, y=0)
    st = WorldState(0, 1, [a])
    goal = {"id": "sleep", "verb": "sleep", "params": {}}
    assert resolve_goal(a, goal, st, WM, {}) == {"action": "sleep"}


def test_observe_returns_the_action():
    a = Agent(id="a", name="A", x=0, y=0)
    st = WorldState(0, 1, [a])
    goal = {"id": "observe", "verb": "observe", "params": {}}
    assert resolve_goal(a, goal, st, WM, {}) == {"action": "observe"}


def test_experiment_with_returns_the_action():
    a = Agent(id="a", name="A", x=0, y=0)
    st = WorldState(0, 1, [a])
    goal = {"id": "experiment", "verb": "experiment_with",
            "params": {"items": ["stick", "stone"]}}
    act = resolve_goal(a, goal, st, WM, {})
    assert act == {"action": "experiment_with", "items": ["stick", "stone"]}


def test_build_returns_the_action():
    a = Agent(id="a", name="A", x=0, y=0)
    st = WorldState(0, 1, [a])
    goal = {"id": "build:campfire", "verb": "build",
            "params": {"structure": "campfire"}}
    act = resolve_goal(a, goal, st, WM, {})
    assert act == {"action": "build", "structure": "campfire"}


def test_cast_returns_the_action():
    a = Agent(id="a", name="A", x=0, y=0)
    st = WorldState(0, 1, [a])
    goal = {"id": "cast:spark", "verb": "cast", "params": {"spell": "spark"}}
    act = resolve_goal(a, goal, st, WM, {})
    assert act == {"action": "cast", "spell": "spark"}


def test_descend_far_from_link_tile_returns_move_to():
    a = Agent(id="a", name="A", x=0, y=0)
    st = WorldState(0, 1, [a])
    layers = [{"link": {"descend": [2, 1]}}, {"link": {}}]
    settings = {"layers": layers}
    goal = {"id": "descend", "verb": "descend", "params": {}}
    act = resolve_goal(a, goal, st, WM, settings)
    assert act["action"] == "move_to"


def test_descend_on_link_tile_returns_the_verb():
    a = Agent(id="a", name="A", x=2, y=1)
    st = WorldState(0, 1, [a])
    layers = [{"link": {"descend": [2, 1]}}, {"link": {}}]
    settings = {"layers": layers}
    goal = {"id": "descend", "verb": "descend", "params": {}}
    act = resolve_goal(a, goal, st, WM, settings)
    assert act == {"action": "descend"}
