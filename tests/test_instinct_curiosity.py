import random
from genesis import load_settings
from genesis.world.state import Agent, Resource, WorldState
from genesis.world.grid import WorldMap
from genesis.world.discovery import DiscoveryGraph
from genesis.world.properties import PropertyBook
from genesis.world.instinct import choose_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
P = PropertyBook.from_file("configs/properties.json")
G = DiscoveryGraph.from_file("configs/discoveries.json", P)
NOON = 720


def world(agent, resources=None):
    return WorldState(sim_minutes=NOON, seed=1, agents=[agent],
                      resources=resources or [])


def test_experiments_with_held_materials():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1})
    act = choose_action(a, world(a), M, S, random.Random(1), G)
    assert act["action"] == "experiment_with"
    assert set(act["items"]) == {"flint", "wood"}


def test_builds_campfire_when_fire_known_and_wood_available():
    # charcoal is a known item recipe so curiosity won't divert to discovering it;
    # the agent's best move with wood in hand is to build a campfire.
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire", "charcoal"],
              inventory={"wood": 2})
    act = choose_action(a, world(a), M, S, random.Random(1), G)
    assert act == {"action": "build", "structure": "campfire"}


def test_gathers_raw_material_underfoot():
    r = Resource(type="wood", x=5, y=5, qty=5)
    a = Agent(id="a", name="A", x=5, y=5)   # no inventory, knows nothing
    act = choose_action(a, world(a, [r]), M, S, random.Random(1), G)
    assert act == {"action": "gather", "resource": "wood"}


def test_without_graph_matches_plan1_wander():
    a = Agent(id="a", name="A", x=5, y=5)
    act = choose_action(a, world(a), M, S, random.Random(1))   # graph=None
    assert act["action"] in ("move_to", "observe")


def test_does_not_re_experiment_when_nothing_new():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"],
              inventory={"stone": 1})     # stone alone yields no new discovery
    act = choose_action(a, world(a), M, S, random.Random(1), G)
    assert act["action"] != "experiment_with"
