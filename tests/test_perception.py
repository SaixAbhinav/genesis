from genesis.world.perception import perceive_agents
from genesis.world.state import Agent, WorldState


def _mk(name, x, y, race="", status="active", layer=0):
    return Agent(id=name, name=name, x=x, y=y, race=race, status=status, layer=layer)


def test_perceives_nearby_sorted_by_dist_then_name():
    a = _mk("A", 5, 5, race="ashfolk")
    near = _mk("Near", 6, 5, race="mosskin")
    far = _mk("Far", 5, 9, race="mosskin")
    st = WorldState(0, 1, [a, far, near])
    seen = perceive_agents(a, st, radius=6)
    assert [s["name"] for s in seen] == ["Near", "Far"]
    assert seen[0]["race"] == "mosskin" and seen[0]["dist"] == 1
    assert seen[0]["dir"] == "E"


def test_excludes_self_dead_other_layer_and_out_of_range():
    a = _mk("A", 0, 0)
    dead = _mk("D", 1, 0, status="dead")
    below = _mk("B", 1, 0, layer=1)
    away = _mk("F", 20, 20)
    st = WorldState(0, 1, [a, dead, below, away])
    assert perceive_agents(a, st, radius=6) == []
