from genesis.world.goal import resolve_goal
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GGGGGGGG"] * 8)
S = {"perception_radius": 6}


def _mk(name, x, y, status="active", layer=0):
    return Agent(id=name, name=name, x=x, y=y, status=status, layer=layer)


def test_approach_moves_toward_live_target_then_ends_on_adjacency():
    a = _mk("A", 1, 1)
    b = _mk("B", 4, 1)
    st = WorldState(0, 1, [a, b])
    goal = {"verb": "approach", "params": {"target": "B"}}
    act = resolve_goal(a, goal, st, WM, S)
    assert act["action"] == "move_to" and (act["x"], act["y"]) != (1, 1)
    a.x, a.y = 3, 1
    assert resolve_goal(a, goal, st, WM, S) is None


def test_avoid_steps_away_then_ends_when_out_of_range():
    a = _mk("A", 4, 4)
    b = _mk("B", 5, 4)
    st = WorldState(0, 1, [a, b])
    goal = {"verb": "avoid", "params": {"target": "B"}}
    act = resolve_goal(a, goal, st, WM, S)
    assert act["action"] == "move_to" and act["x"] <= 4    # moved away from B (east)
    b.x, b.y = 40, 40
    assert resolve_goal(a, goal, st, WM, S) is None


def test_approach_ends_if_target_gone_or_dead():
    a = _mk("A", 1, 1)
    b = _mk("B", 3, 1, status="dead")
    st = WorldState(0, 1, [a, b])
    assert resolve_goal(a, {"verb": "approach", "params": {"target": "B"}},
                        st, WM, S) is None
    assert resolve_goal(a, {"verb": "avoid", "params": {"target": "Ghost"}},
                        st, WM, S) is None
