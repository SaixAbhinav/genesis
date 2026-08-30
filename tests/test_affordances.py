# tests/test_affordances.py
from genesis.world.affordances import affordances
from genesis.world.discovery import DiscoveryGraph
from genesis.world.grid import WorldMap
from genesis.world.magic import MagicBook
from genesis.world.state import Agent, WorldState, Resource

WM = WorldMap(["GGGG", "GGGG", "GGGG", "GGGG"])
S = {"campfire_warmth_radius": 2, "strain_heal_threshold": 25.0}


def _agent(**kw):
    return Agent(id="a", name="A", x=0, y=0, **kw)


def test_offers_gather_for_reachable_resource_with_stable_id():
    st = WorldState(0, 1, [_agent()], [Resource(type="berries", x=2, y=1, qty=3, layer=0)])
    opts = affordances(_agent(), st, WM, S)
    berry = [o for o in opts if o["verb"] == "gather" and o["params"].get("resource") == "berries"]
    assert berry, "should offer gathering the berries"
    assert berry[0]["id"] == "gather:berries@(2,1,0)"  # stable: resource identity, not agent-relative


def test_offers_eat_when_holding_berries():
    a = _agent(inventory={"berries": 2})
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, S)
    assert any(o["id"] == "eat" and o["verb"] == "eat" for o in opts)


def test_no_gather_for_resource_on_other_layer():
    a = _agent(layer=0)
    st = WorldState(0, 1, [a], [Resource(type="berries", x=2, y=1, qty=3, layer=1)])
    opts = affordances(a, st, WM, S)
    assert not any(o["verb"] == "gather" for o in opts)


def test_offers_experiment_when_recipe_matches_and_result_unknown():
    g = DiscoveryGraph(
        recipes=[{"items": ["wood", "flint"], "requires": [], "result": "fire"}],
        buildables={},
    )
    a = _agent(inventory={"wood": 1, "flint": 1})
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, S, graph=g)
    exp = [o for o in opts if o["verb"] == "experiment_with"]
    assert exp and exp[0]["id"] == "experiment"
    assert set(exp[0]["params"]["items"]) == {"wood", "flint"}


def test_no_experiment_when_result_already_known():
    g = DiscoveryGraph(
        recipes=[{"items": ["wood", "flint"], "requires": [], "result": "fire"}],
        buildables={},
    )
    a = _agent(inventory={"wood": 1, "flint": 1}, knowledge=["fire"])
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, S, graph=g)
    assert not any(o["verb"] == "experiment_with" for o in opts)


def test_offers_build_campfire_when_known_and_materials_held():
    g = DiscoveryGraph(
        recipes=[],
        buildables={"campfire": {"materials": {"wood": 2}, "requires": ["fire"],
                                 "terrain": ["grass"]}},
    )
    a = _agent(inventory={"wood": 2}, knowledge=["fire"])
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, S, graph=g)
    assert any(o["id"] == "build:campfire" and o["verb"] == "build"
              and o["params"]["structure"] == "campfire" for o in opts)


def test_no_build_when_missing_materials_or_knowledge():
    g = DiscoveryGraph(
        recipes=[],
        buildables={"campfire": {"materials": {"wood": 2}, "requires": ["fire"],
                                 "terrain": ["grass"]}},
    )
    a = _agent(inventory={"wood": 1}, knowledge=["fire"])  # not enough wood
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, S, graph=g)
    assert not any(o["verb"] == "build" for o in opts)


def _magic():
    return MagicBook.from_dict({
        "attributes": ["fire"], "ranks": ["novice"], "rank_xp": {"novice": 0},
        "spells": [{"name": "spark", "attribute": "fire", "mana_cost": 5.0,
                   "effect": {"type": "noop"}, "base_cast_minutes": 1,
                   "xp_per_cast": 1, "prereqs": {}}],
        "params": {},
    })


def test_offers_cast_for_known_spell_with_enough_mana():
    m = _magic()
    a = _agent(knowledge=["spark"], mana=10.0)
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, S, magic=m)
    assert any(o["id"] == "cast:spark" and o["verb"] == "cast"
              and o["params"]["spell"] == "spark" for o in opts)


def test_no_cast_when_not_enough_mana():
    m = _magic()
    a = _agent(knowledge=["spark"], mana=1.0)
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, S, magic=m)
    assert not any(o["verb"] == "cast" for o in opts)


def test_offers_descend_toward_link_tile_even_when_not_standing_on_it():
    a = _agent(layer=0)
    st = WorldState(0, 1, [a])
    layers = [{"link": {"descend": [2, 1]}}, {"link": {}}]
    settings = {**S, "layers": layers}
    opts = affordances(a, st, WM, settings)
    desc = [o for o in opts if o["verb"] == "descend"]
    assert desc and desc[0]["id"] == "descend"
    assert desc[0]["dist"] == 3  # (2,1) is 3 tiles from (0,0)


def test_no_ascend_from_top_layer():
    a = _agent(layer=0)
    st = WorldState(0, 1, [a])
    layers = [{"link": {"ascend": [0, 0]}}]
    settings = {**S, "layers": layers}
    opts = affordances(a, st, WM, settings)
    assert not any(o["verb"] == "ascend" for o in opts)
