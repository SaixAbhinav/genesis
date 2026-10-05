from genesis.world.magic import MagicBook
from genesis.world.properties import PropertyBook
from genesis.world.state import Agent

PROPS = PropertyBook({"mana_shard": ["mana_rich", "luminous"],
                      "ember_dust": ["ether_fire", "flammable"],
                      "wood": ["flammable"]})
BOOK = MagicBook.from_dict({
    "attributes": ["healing", "fire"], "ranks": ["beginner"],
    "rank_xp": {"beginner": 0},
    "spells": [
        {"name": "minor_heal", "attribute": "healing", "requires": ["mana_rich"],
         "prereqs": {}, "base_cast_minutes": 2, "mana_cost": 8, "xp_per_cast": 6,
         "effect": {"type": "reduce_strain", "amount": 20}},
        {"name": "kindle", "attribute": "fire", "requires": ["ether_fire"],
         "prereqs": {}, "base_cast_minutes": 3, "mana_cost": 5, "xp_per_cast": 4,
         "effect": {"type": "warmth", "amount": 25}},
    ], "params": {}}, props=PROPS)


def _agent(inv, know=None):
    return Agent(id="m", name="M", x=0, y=0, inventory=dict(inv),
                 knowledge=list(know or []))


def test_resolve_spell_from_reagent_property():
    r, cover = BOOK.resolve(["mana_shard"], _agent({"mana_shard": 1}))
    assert r["name"] == "minor_heal" and cover == ["mana_shard"]


def test_resolve_skips_known_spell():
    assert BOOK.resolve(["mana_shard"], _agent({"mana_shard": 1},
                        know=["minor_heal"])) == (None, None)


def test_resolve_none_without_matching_property():
    assert BOOK.resolve(["wood"], _agent({"wood": 1})) == (None, None)
