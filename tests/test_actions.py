from genesis import load_settings
from genesis.world.state import Agent, Needs, Resource, WorldState
from genesis.world.grid import WorldMap
from genesis.world.actions import validate_action, step_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
NOON = 720


def make_world(agent, resources=None):
    return WorldState(sim_minutes=NOON, seed=1, agents=[agent],
                      resources=resources or [])


def test_validate_rejects_unknown_and_malformed():
    a = Agent(id="t", name="T", x=5, y=5)
    ok, why = validate_action({"action": "fly"}, a, make_world(a), M)
    assert ok is False and "fly" in why
    ok, _ = validate_action({"action": "move_to", "x": 5}, a, make_world(a), M)
    assert ok is False


def test_move_steps_toward_target_and_arrives():
    a = Agent(id="t", name="T", x=5, y=5,
              current_action={"action": "move_to", "x": 7, "y": 5})
    st = make_world(a)
    ev = step_action(a, st, M, S)
    assert (a.x, a.y) == (6, 5) and ev[0]["type"] == "moved"
    ev = step_action(a, st, M, S)
    assert (a.x, a.y) == (7, 5)
    assert any(e["type"] == "arrived" for e in ev)
    assert a.current_action is None


def test_move_does_not_enter_water():
    a = Agent(id="t", name="T", x=5, y=7,
              current_action={"action": "move_to", "x": 5, "y": 10})
    st = make_world(a)
    step_action(a, st, M, S)          # tries (5,8)=water, sidesteps on x
    assert M.walkable(a.x, a.y)


def test_gather_transfers_one_unit():
    r = Resource(type="berries", x=1, y=2, qty=3)
    a = Agent(id="t", name="T", x=1, y=2,
              current_action={"action": "gather", "resource": "berries"})
    st = make_world(a, [r])
    ev = step_action(a, st, M, S)
    assert a.inventory["berries"] == 1 and r.qty == 2
    assert ev[0]["type"] == "gathered" and a.current_action is None


def test_gather_fails_without_resource():
    a = Agent(id="t", name="T", x=5, y=5,
              current_action={"action": "gather", "resource": "berries"})
    ev = step_action(a, make_world(a), M, S)
    assert ev[0]["type"] == "gather_failed" and a.current_action is None


def test_eat_restores_hunger():
    a = Agent(id="t", name="T", x=5, y=5, needs=Needs(hunger=40.0),
              inventory={"berries": 2}, current_action={"action": "eat"})
    step_action(a, make_world(a), M, S)
    assert a.needs.hunger == 40 + S["eat_berries_hunger_restore"]
    assert a.inventory["berries"] == 1


def test_drink_requires_water_adjacency():
    a = Agent(id="t", name="T", x=5, y=7, needs=Needs(energy=50.0),
              current_action={"action": "drink"})   # (5,8) is water
    ev = step_action(a, make_world(a), M, S)
    assert ev[0]["type"] == "drank"
    b = Agent(id="u", name="U", x=1, y=1, current_action={"action": "drink"})
    ev = step_action(b, make_world(b), M, S)
    assert ev[0]["type"] == "drink_failed"


def test_sleep_until_rested():
    a = Agent(id="t", name="T", x=5, y=5, needs=Needs(energy=94.9),
              current_action={"action": "sleep"})
    st = make_world(a)
    step_action(a, st, M, S)
    assert a.status == "sleeping"
    a.needs.energy = 96.0
    ev = step_action(a, st, M, S)
    assert a.status == "active" and ev[0]["type"] == "woke"


def test_observe_sees_nearby_agents():
    a = Agent(id="t", name="T", x=5, y=5, current_action={"action": "observe"})
    b = Agent(id="u", name="U", x=7, y=6)
    st = WorldState(sim_minutes=NOON, seed=1, agents=[a, b])
    ev = step_action(a, st, M, S)
    assert ev[0]["type"] == "observed" and "U" in ev[0]["seen_agents"]
