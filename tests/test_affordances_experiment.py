from genesis.world.affordances import affordances
from genesis.world.discovery import DiscoveryGraph
from genesis.world.properties import PropertyBook
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GGGG", "GGGG", "GGGG", "GGGG"])
S = {"campfire_warmth_radius": 2, "experiment_max_items": 6,
     "experiment_affordance_cap": 10}
P = PropertyBook({"wood": ["flammable"], "flint": ["sparks"], "stone": ["hard"]})
G = DiscoveryGraph(recipes=[], buildables={}, props=P)


def _a(**kw):
    return Agent(id="a", name="A", x=0, y=0, **kw)


def test_offers_pairs_without_success_precheck():
    a = _a(inventory={"wood": 1, "flint": 1, "stone": 1})
    opts = affordances(a, WorldState(0, 1, [a]), WM, S, graph=G)
    exp = {o["id"] for o in opts if o["verb"] == "experiment_with"}
    # C(3,2) pairs + the full set, even though no recipe exists (fallible)
    assert "experiment:flint+wood" in exp
    assert "experiment:flint+stone" in exp
    assert "experiment:stone+wood" in exp
    assert any(id.count("+") == 2 for id in exp)   # combine-all option


def test_label_includes_properties():
    a = _a(inventory={"wood": 1, "flint": 1})
    opts = affordances(a, WorldState(0, 1, [a]), WM, S, graph=G)
    exp = next(o for o in opts if o["verb"] == "experiment_with")
    assert "flammable" in exp["label"] and "sparks" in exp["label"]


def test_lone_item_still_offered():
    a = _a(inventory={"mana_shard": 1})
    g = DiscoveryGraph(recipes=[], buildables={},
                       props=PropertyBook({"mana_shard": ["mana_rich"]}))
    opts = affordances(a, WorldState(0, 1, [a]), WM, S, graph=g)
    assert any(o["id"] == "experiment:mana_shard" for o in opts)
