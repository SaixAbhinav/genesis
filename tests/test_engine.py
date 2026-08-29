from genesis import load_settings
from genesis.world.state import WorldState, load_agents
from genesis.world.grid import WorldMap
from genesis.world.engine import Engine

S = load_settings("configs/settings.json")


def fresh_state(seed=42):
    return WorldState(sim_minutes=720, seed=seed,
                      agents=load_agents("configs/agents.json"))


def make_engine(seed=42):
    return Engine(fresh_state(seed), WorldMap.from_file("configs/map.json"), S)


def test_tick_advances_time_and_decays_needs():
    e = make_engine()
    e.tick()
    assert e.state.sim_minutes == 721
    assert e.state.agents[0].needs.hunger < 100


def test_agents_get_instinct_actions_and_move():
    e = make_engine()
    before = [(a.x, a.y) for a in e.state.agents]
    e.advance(30)
    after = [(a.x, a.y) for a in e.state.agents]
    assert before != after             # somebody actually moved


def test_events_carry_minute():
    e = make_engine()
    events = e.advance(10)
    assert events and all("minute" in ev for ev in events)


def test_fast_forward_is_deterministic():
    e1, e2 = make_engine(seed=7), make_engine(seed=7)
    ev1, ev2 = e1.advance(600), e2.advance(600)
    assert e1.state.to_json() == e2.state.to_json()
    assert ev1 == ev2


def test_different_seeds_diverge():
    e1, e2 = make_engine(seed=1), make_engine(seed=2)
    e1.advance(600); e2.advance(600)
    assert e1.state.to_json() != e2.state.to_json()
