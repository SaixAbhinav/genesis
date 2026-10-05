from genesis import load_settings
from genesis.world.state import Agent, WorldState
from genesis.world.grid import WorldMap
from genesis.world.discovery import DiscoveryGraph
from genesis.world.properties import PropertyBook
from genesis.world.actions import validate_action, step_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
P = PropertyBook.from_file("configs/properties.json")
G = DiscoveryGraph.from_file("configs/discoveries.json", P)


def world(agent):
    return WorldState(sim_minutes=0, seed=1, agents=[agent])


def _run(a, st, items):
    a.current_action = {"action": "experiment_with", "items": items}
    step_action(a, st, M, S, G)                 # tick 1: starts the experiment
    st.sim_minutes += S["experiment_minutes"]
    return step_action(a, st, M, S, G)          # resolves


def test_experiment_takes_time_before_resolving():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1},
              current_action={"action": "experiment_with", "items": ["flint", "wood"]})
    ev = step_action(a, world(a), M, S, G)
    assert ev == [] and "fire" not in a.knowledge   # still chanting


def test_experiment_discovers_fire_and_consumes_cover():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1})
    ev = _run(a, world(a), ["flint", "wood"])
    assert "fire" in a.knowledge
    assert ev[0]["type"] == "discovered" and ev[0]["discovery"] == "fire"
    assert a.inventory.get("wood", 0) == 0 and a.inventory.get("flint", 0) == 0


def test_substitution_ember_dust_also_makes_fire():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "ember_dust": 1})
    _run(a, world(a), ["flint", "ember_dust"])
    assert "fire" in a.knowledge


def test_experiment_failed_consumes_nothing():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"berries": 1})
    ev = _run(a, world(a), ["berries"])
    assert ev[0]["type"] == "experiment_failed"
    assert a.inventory == {"berries": 1}


def test_item_recipe_chain_charcoal_then_ingot():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"],
              inventory={"wood": 1, "ore": 1})
    ev = _run(a, world(a), ["wood"])
    assert ev[0]["type"] == "crafted" and a.inventory.get("charcoal", 0) == 1
    assert a.inventory.get("wood", 0) == 0
    ev2 = _run(a, world(a), ["ore", "charcoal"])
    assert ev2[0]["type"] == "crafted" and a.inventory.get("metal_ingot", 0) == 1


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
