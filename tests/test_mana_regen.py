from genesis import load_settings
from genesis.world.state import Agent, Needs
from genesis.world.needs import tick_needs

S = load_settings("configs/settings.json")
NOON = 720


def make_agent(**kw):
    return Agent(id="t", name="T", x=0, y=0, **kw)


def test_mana_regenerates_while_active():
    a = make_agent(mana=10.0, mana_max=50.0)
    tick_needs(a, NOON, S)
    assert a.mana == 10.0 + S["mana_regen_per_min"]


def test_mana_regenerates_faster_while_sleeping():
    a = make_agent(status="sleeping", mana=10.0, mana_max=50.0)
    tick_needs(a, NOON, S)
    assert a.mana == 10.0 + S["mana_regen_sleeping_per_min"]


def test_mana_never_exceeds_max():
    a = make_agent(status="sleeping", mana=49.9, mana_max=50.0)
    tick_needs(a, NOON, S)
    assert a.mana == 50.0


def test_no_regen_for_non_casters():
    a = make_agent(mana=0.0, mana_max=0.0)
    tick_needs(a, NOON, S)
    assert a.mana == 0.0


def test_no_mana_regen_while_collapsed():
    a = make_agent(status="collapsed", mana=10.0, mana_max=50.0,
                   collapse_until=NOON + 60)
    tick_needs(a, NOON, S)
    assert a.mana == 10.0
