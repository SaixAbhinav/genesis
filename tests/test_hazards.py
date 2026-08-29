import random
from genesis.world.grid import WorldMap
from genesis.world.hazards import miasma_tick, fall_check
from genesis.world.state import Agent

L1 = {"miasma_damage": 5.0, "miasma_need": "energy"}
L2 = {"cliff_tiles": [[1, 0]], "fall_strain": 40.0}
WM = WorldMap(["GG", "GG"])


def test_miasma_damages_when_not_purified():
    a = Agent(id="a", name="A", x=0, y=0, purified_until=0)
    a.needs.energy = 50.0
    miasma_tick(a, L1, minute=10)
    assert a.needs.energy == 45.0


def test_miasma_blocked_by_purify_buff():
    a = Agent(id="a", name="A", x=0, y=0, purified_until=20)
    a.needs.energy = 50.0
    miasma_tick(a, L1, minute=10)  # 10 < 20 -> purified
    assert a.needs.energy == 50.0


def test_fall_on_cliff_without_wind_adds_strain():
    a = Agent(id="a", name="A", x=1, y=0, negate_fall_until=0)
    evs = fall_check(a, WM, L2, minute=5, rng=random.Random(0))
    assert a.strain == 40.0 and any(e["type"] == "fell" for e in evs)


def test_fall_prevented_by_wind_buff():
    a = Agent(id="a", name="A", x=1, y=0, negate_fall_until=10)
    evs = fall_check(a, WM, L2, minute=5, rng=random.Random(0))
    assert a.strain == 0.0 and evs == []
