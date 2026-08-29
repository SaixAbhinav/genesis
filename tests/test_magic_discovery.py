from genesis.world.actions import step_action
from genesis.world.grid import WorldMap
from genesis.world.magic import MagicBook
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GG", "GG"])
SET = {"campfire_warmth_radius": 1, "stone_tools_gather_bonus": 1}
BOOK = MagicBook.from_dict({
    "attributes": ["healing"], "ranks": ["beginner"], "rank_xp": {"beginner": 0},
    "spells": [{"name": "minor_heal", "kind": "spell", "attribute": "healing",
                "requires": ["mana_shard"], "prereqs": {},
                "base_cast_minutes": 2, "mana_cost": 10, "xp_per_cast": 6,
                "effect": {"type": "reduce_strain", "amount": 20}}],
    "params": {}})


def test_experiment_discovers_spell_and_inits_rank():
    a = Agent(id="m", name="M", x=0, y=0, inventory={"mana_shard": 1})
    st = WorldState(0, 1, [a])
    a.current_action = {"action": "experiment_with", "items": ["mana_shard"]}
    ev = step_action(a, st, WM, SET, graph=None, magic=BOOK)
    assert "minor_heal" in a.knowledge
    assert a.attr_rank["healing"] == 0
    assert any(e["type"] == "discovered" for e in ev)


def test_experiment_without_seed_item_finds_nothing():
    a = Agent(id="m", name="M", x=0, y=0, inventory={"wood": 1})
    st = WorldState(0, 1, [a])
    a.current_action = {"action": "experiment_with", "items": ["wood"]}
    ev = step_action(a, st, WM, SET, graph=None, magic=BOOK)
    assert "minor_heal" not in a.knowledge
