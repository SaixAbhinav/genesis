from genesis.world.affordances import affordances
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GGGGGGGG"] * 8)
S = {"perception_radius": 6, "perception_affordance_cap": 3}


def _mk(name, x, y, race=""):
    return Agent(id=name, name=name, x=x, y=y, race=race)


def test_offers_approach_and_avoid_for_perceived_agent():
    a = _mk("A", 1, 1, race="ashfolk")
    b = _mk("B", 3, 1, race="mosskin")
    opts = affordances(a, WorldState(0, 1, [a, b]), WM, S)
    ids = {o["id"] for o in opts}
    assert "approach:B" in ids and "avoid:B" in ids
    ap = next(o for o in opts if o["id"] == "approach:B")
    assert ap["verb"] == "approach" and ap["params"] == {"target": "B"}
    assert "mosskin" in ap["label"] and "E" in ap["label"]


def test_no_social_options_when_alone():
    a = _mk("A", 1, 1, race="ashfolk")
    opts = affordances(a, WorldState(0, 1, [a]), WM, S)
    assert not any(o["verb"] in ("approach", "avoid") for o in opts)
