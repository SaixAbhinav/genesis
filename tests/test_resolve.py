from genesis.world.discovery import DiscoveryGraph, covering_subset
from genesis.world.properties import PropertyBook
from genesis.world.state import Agent

PROPS = PropertyBook({
    "wood": ["flammable", "fibrous"], "flint": ["sharp", "sparks"],
    "dry_grass": ["flammable", "light"], "berries": ["edible"],
    "ore": ["metallic", "hard"], "charcoal": ["hot_burning", "flammable"],
})
RECIPES = [
    {"name": "fire", "requires": ["flammable", "sparks"], "prereqs": {},
     "kind": "knowledge", "min_items": 2},
    {"name": "cooked_food", "requires": ["edible"],
     "prereqs": {"knowledge": ["fire"]}, "kind": "knowledge", "min_items": 1},
    {"name": "metal_ingot", "requires": ["metallic", "hot_burning"], "prereqs": {},
     "kind": "item", "produces": "metal_ingot", "min_items": 2},
]
G = DiscoveryGraph(RECIPES, {}, props=PROPS)


def _agent(inv, know=None):
    return Agent(id="a", name="A", x=0, y=0, inventory=dict(inv),
                 knowledge=list(know or []))


def test_covering_subset_minimal_and_sorted():
    assert covering_subset({"wood", "flint"}, ["flammable", "sparks"],
                           PROPS.props_of) == ["flint", "wood"]
    assert covering_subset({"berries"}, ["flammable"], PROPS.props_of) is None


def test_resolve_fire_from_two_item_sets():
    r, cover = G.resolve(["wood", "flint"], _agent({"wood": 1, "flint": 1}))
    assert r["name"] == "fire" and cover == ["flint", "wood"]
    r2, _ = G.resolve(["dry_grass", "flint"], _agent({"dry_grass": 1, "flint": 1}))
    assert r2["name"] == "fire"


def test_resolve_ignores_extra_and_respects_min_items():
    # flint alone would cover nothing for fire; single item can't meet min_items 2
    r, _ = G.resolve(["flint"], _agent({"flint": 1}))
    assert r is None


def test_resolve_prereq_and_known_skip():
    a = _agent({"berries": 1})
    assert G.resolve(["berries"], a) == (None, None)          # needs fire
    a.knowledge.append("fire")
    r, cover = G.resolve(["berries"], a)
    assert r["name"] == "cooked_food" and cover == ["berries"]
    a.knowledge.append("cooked_food")
    assert G.resolve(["berries"], a) == (None, None)          # already known


def test_resolve_item_recipe_repeatable_when_known():
    a = _agent({"ore": 1, "charcoal": 1}, know=["metal_ingot"])
    r, cover = G.resolve(["ore", "charcoal"], a)
    assert r["name"] == "metal_ingot" and cover == ["charcoal", "ore"]  # item: not skipped
