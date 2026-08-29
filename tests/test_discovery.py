from genesis.world.discovery import DiscoveryGraph

G = DiscoveryGraph.from_file("configs/discoveries.json")


def test_match_simple_recipe():
    assert G.match(["flint", "wood"], []) == "fire"
    assert G.match(["wood", "flint"], []) == "fire"     # order independent


def test_match_ignores_extra_items():
    assert G.match(["flint", "wood", "berries"], []) == "fire"


def test_match_requires_knowledge():
    assert G.match(["berries"], []) is None             # needs fire known
    assert G.match(["berries"], ["fire"]) == "cooked_food"


def test_match_returns_none_when_nothing_fits():
    assert G.match(["berries", "water"], []) is None
    assert G.match([], []) is None


def test_buildable_lookup():
    camp = G.buildable("campfire")
    assert camp["materials"] == {"wood": 2} and camp["requires"] == ["fire"]
    assert G.buildable("nonsense") is None
    assert "hut" in G.buildable_names()
