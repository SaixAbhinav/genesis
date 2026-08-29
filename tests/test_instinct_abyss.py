from genesis.world.grid import WorldMap
from genesis.world.instinct import choose_action
from genesis.world.magic import MagicBook
from genesis.world.state import Agent, Resource, WorldState
import random

WM = WorldMap(["CC", "CC"])
BOOK = MagicBook.from_dict({
    "attributes": ["healing"], "ranks": ["beginner"], "rank_xp": {"beginner": 0},
    "spells": [{"name": "minor_heal", "kind": "spell", "attribute": "healing",
                "requires": ["mana_shard"], "prereqs": {}, "base_cast_minutes": 2,
                "mana_cost": 10, "xp_per_cast": 6,
                "effect": {"type": "reduce_strain", "amount": 20}}],
    "params": {}})
SET = {"minutes_per_day": 100, "day_start_minute": 0, "day_end_minute": 100,
       "campfire_warmth_radius": 1, "strain_heal_threshold": 25.0,
       "layers": [{}, {}]}


def test_high_strain_triggers_heal_when_able():
    a = Agent(id="a", name="A", x=0, y=0, strain=40.0, mana=20.0, mana_max=40.0,
              knowledge=["minor_heal"], attr_rank={"healing": 0})
    a.needs.hunger = 100.0; a.needs.energy = 100.0
    act = choose_action(a, WorldState(0, 1, [a]), WM, SET, random.Random(0),
                        None, BOOK)
    assert act == {"action": "cast", "spell": "minor_heal"}


def test_low_strain_does_not_heal():
    a = Agent(id="a", name="A", x=0, y=0, strain=5.0, mana=20.0, mana_max=40.0,
              knowledge=["minor_heal"], attr_rank={"healing": 0})
    a.needs.hunger = 100.0; a.needs.energy = 100.0
    act = choose_action(a, WorldState(0, 1, [a]), WM, SET, random.Random(0),
                        None, BOOK)
    assert act != {"action": "cast", "spell": "minor_heal"}
