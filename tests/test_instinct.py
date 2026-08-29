import random
from genesis import load_settings
from genesis.world.state import Agent, Needs, Resource, WorldState
from genesis.world.grid import WorldMap
from genesis.world.instinct import choose_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
NOON, MIDNIGHT = 720, 0


def world(agent, minutes=NOON, resources=None):
    return WorldState(sim_minutes=minutes, seed=1, agents=[agent],
                      resources=resources or [])


def test_sleeps_at_night():
    a = Agent(id="t", name="T", x=5, y=5)
    assert choose_action(a, world(a, MIDNIGHT), M, S, random.Random(1)) == {"action": "sleep"}


def test_eats_carried_food_when_hungry():
    a = Agent(id="t", name="T", x=5, y=5, needs=Needs(hunger=30.0),
              inventory={"berries": 1})
    assert choose_action(a, world(a), M, S, random.Random(1)) == {"action": "eat"}


def test_moves_to_food_when_hungry_and_empty_handed():
    a = Agent(id="t", name="T", x=5, y=5, needs=Needs(hunger=30.0))
    r = Resource(type="berries", x=1, y=2, qty=10)
    act = choose_action(a, world(a, resources=[r]), M, S, random.Random(1))
    assert act["action"] == "move_to"


def test_gathers_when_on_food():
    a = Agent(id="t", name="T", x=1, y=2, needs=Needs(hunger=30.0))
    r = Resource(type="berries", x=1, y=2, qty=10)
    act = choose_action(a, world(a, resources=[r]), M, S, random.Random(1))
    assert act == {"action": "gather", "resource": "berries"}


def test_wanders_by_default_to_walkable_tile():
    a = Agent(id="t", name="T", x=5, y=5)
    act = choose_action(a, world(a), M, S, random.Random(1))
    assert act["action"] == "move_to" and M.walkable(act["x"], act["y"])


def test_none_when_collapsed():
    a = Agent(id="t", name="T", x=5, y=5, status="collapsed")
    assert choose_action(a, world(a), M, S, random.Random(1)) is None
