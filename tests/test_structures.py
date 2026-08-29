from genesis import load_settings
from genesis.world.state import Agent, WorldState
from genesis.world.structures import Structure, has_warmth_source

S = load_settings("configs/settings.json")


def test_worldstate_serializes_structures():
    st = WorldState(sim_minutes=5, seed=1,
                    agents=[Agent(id="a", name="A", x=0, y=0)],
                    structures=[Structure(type="campfire", x=3, y=3,
                                          built_by="a", built_minute=4)])
    st2 = WorldState.from_json(st.to_json())
    assert st2.structures[0].type == "campfire"
    assert st2.structures[0].built_by == "a"


def test_from_json_backward_compatible_without_structures():
    legacy = '{"sim_minutes": 1, "seed": 2, "agents": [], "resources": []}'
    st = WorldState.from_json(legacy)
    assert st.structures == []


def test_warmth_from_nearby_campfire():
    a = Agent(id="a", name="A", x=5, y=5)
    st = WorldState(sim_minutes=0, seed=1, agents=[a],
                    structures=[Structure(type="campfire", x=6, y=6,
                                          built_by="a", built_minute=0)])
    assert has_warmth_source(a, st, S) is True
    a.x, a.y = 20, 20
    assert has_warmth_source(a, st, S) is False


def test_warmth_from_held_torch():
    a = Agent(id="a", name="A", x=0, y=0, inventory={"torch": 1})
    st = WorldState(sim_minutes=0, seed=1, agents=[a])
    assert has_warmth_source(a, st, S) is True


def test_hut_only_shelters_when_sleeping_and_adjacent():
    a = Agent(id="a", name="A", x=5, y=5)
    st = WorldState(sim_minutes=0, seed=1, agents=[a],
                    structures=[Structure(type="hut", x=5, y=6,
                                          built_by="a", built_minute=0)])
    assert has_warmth_source(a, st, S) is False     # awake
    a.status = "sleeping"
    assert has_warmth_source(a, st, S) is True
