from genesis import load_settings
from genesis.world.state import Agent, WorldState
from genesis.world.grid import WorldMap
from genesis.world.discovery import DiscoveryGraph
from genesis.world.actions import validate_action, step_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
G = DiscoveryGraph.from_file("configs/discoveries.json")


def world(agent):
    return WorldState(sim_minutes=0, seed=1, agents=[agent])


def test_experiment_discovers_fire_and_keeps_items():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1},
              current_action={"action": "experiment_with", "items": ["flint", "wood"]})
    ev = step_action(a, world(a), M, S, G)
    assert "fire" in a.knowledge
    assert ev[0]["type"] == "discovered" and ev[0]["discovery"] == "fire"
    assert a.inventory == {"flint": 1, "wood": 1}     # not consumed
    assert a.current_action is None


def test_experiment_known_when_already_discovered():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1},
              knowledge=["fire"],
              current_action={"action": "experiment_with", "items": ["flint", "wood"]})
    ev = step_action(a, world(a), M, S, G)
    assert ev[0]["type"] == "experiment_known"


def test_experiment_failed_when_no_recipe():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"berries": 1},
              current_action={"action": "experiment_with", "items": ["berries"]})
    ev = step_action(a, world(a), M, S, G)
    assert ev[0]["type"] == "experiment_failed"


def test_validate_rejects_experiment_without_held_items():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1})
    ok, why = validate_action(
        {"action": "experiment_with", "items": ["flint", "wood"]}, a, world(a), M, G)
    assert ok is False and "wood" in why


def test_validate_rejects_experiment_without_graph():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1})
    ok, _ = validate_action(
        {"action": "experiment_with", "items": ["flint", "wood"]}, a, world(a), M, None)
    assert ok is False
