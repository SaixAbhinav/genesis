from genesis import load_settings
from genesis.world.actions import step_action
from genesis.world.grid import WorldMap
from genesis.world.magic import MagicBook
from genesis.world.properties import PropertyBook
from genesis.world.state import Agent, WorldState

S = load_settings("configs/settings.json")
WM = WorldMap(["GG", "GG"])
P = PropertyBook({"mana_shard": ["mana_rich", "luminous"],
                  "ember_dust": ["ether_fire", "flammable"], "wood": ["flammable"]})
BOOK = MagicBook.from_dict({
    "attributes": ["healing", "fire"], "ranks": ["beginner"],
    "rank_xp": {"beginner": 0},
    "spells": [
        {"name": "minor_heal", "attribute": "healing", "requires": ["mana_rich"],
         "prereqs": {}, "base_cast_minutes": 2, "mana_cost": 10, "xp_per_cast": 6,
         "effect": {"type": "reduce_strain", "amount": 20}},
        {"name": "kindle", "attribute": "fire", "requires": ["ether_fire"],
         "prereqs": {}, "base_cast_minutes": 3, "mana_cost": 5, "xp_per_cast": 4,
         "effect": {"type": "warmth", "amount": 25}},
    ], "params": {}}, props=P)


def _run(a, st, items):
    a.current_action = {"action": "experiment_with", "items": items}
    step_action(a, st, WM, S, graph=None, magic=BOOK)
    st.sim_minutes += S["experiment_minutes"]
    return step_action(a, st, WM, S, graph=None, magic=BOOK)


def test_experiment_discovers_spell_and_inits_rank():
    a = Agent(id="m", name="M", x=0, y=0, inventory={"mana_shard": 1})
    ev = _run(a, WorldState(0, 1, [a]), ["mana_shard"])
    assert "minor_heal" in a.knowledge and a.attr_rank["healing"] == 0
    assert any(e["type"] == "discovered" for e in ev)
    assert a.inventory.get("mana_shard", 0) == 0        # reagent consumed


def test_substitution_discovers_kindle_from_ether_fire():
    a = Agent(id="m", name="M", x=0, y=0, inventory={"ember_dust": 1})
    _run(a, WorldState(0, 1, [a]), ["ember_dust"])
    assert "kindle" in a.knowledge


def test_experiment_without_matching_property_finds_nothing():
    a = Agent(id="m", name="M", x=0, y=0, inventory={"wood": 1})
    _run(a, WorldState(0, 1, [a]), ["wood"])
    assert "minor_heal" not in a.knowledge
