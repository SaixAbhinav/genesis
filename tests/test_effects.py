from genesis.world.effects import apply_effect
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GG", "GG"])
SET = {"campfire_warmth_radius": 1}


def _agent(**kw):
    return Agent(id="a", name="A", x=0, y=0, **kw)


def test_reduce_strain_lowers_strain_and_gives_bonus_energy():
    a = _agent(strain=30.0)
    a.needs.energy = 40.0
    apply_effect({"type": "reduce_strain", "amount": 20, "bonus": {"energy": 10}},
                 a, WorldState(0, 1, [a]), WM, SET, minute=5)
    assert a.strain == 10.0 and a.needs.energy == 50.0


def test_reduce_strain_clamps_at_zero():
    a = _agent(strain=5.0)
    apply_effect({"type": "reduce_strain", "amount": 20}, a,
                 WorldState(0, 1, [a]), WM, SET, minute=0)
    assert a.strain == 0.0


def test_clear_miasma_sets_buff_window():
    a = _agent()
    apply_effect({"type": "clear_miasma", "duration": 30}, a,
                 WorldState(0, 1, [a]), WM, SET, minute=10)
    assert a.purified_until == 40


def test_negate_fall_sets_buff_window():
    a = _agent()
    apply_effect({"type": "negate_fall", "duration": 15}, a,
                 WorldState(0, 1, [a]), WM, SET, minute=10)
    assert a.negate_fall_until == 25


def test_unknown_effect_is_noop_event():
    a = _agent()
    evs = apply_effect({"type": "teleport"}, a, WorldState(0, 1, [a]), WM, SET, 0)
    assert evs and evs[0]["type"] == "effect_noop"
