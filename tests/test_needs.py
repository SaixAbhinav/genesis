from genesis import load_settings
from genesis.world.state import Agent, Needs
from genesis.world.needs import tick_needs, is_daytime

S = load_settings("configs/settings.json")
NOON = 720
MIDNIGHT = 0


def make_agent(**kw):
    return Agent(id="t", name="T", x=0, y=0, **kw)


def test_is_daytime():
    assert is_daytime(NOON, S) is True
    assert is_daytime(MIDNIGHT, S) is False
    assert is_daytime(1440 + NOON, S) is True   # day 2


def test_hunger_and_energy_decay_active_day():
    a = make_agent()
    tick_needs(a, NOON, S)
    assert a.needs.hunger == 100 - S["hunger_decay_per_min"]
    assert a.needs.energy == 100 - S["energy_decay_per_min"]
    assert a.needs.warmth == 100.0    # clamped, regens by day


def test_warmth_decays_at_night():
    a = make_agent()
    tick_needs(a, MIDNIGHT, S)
    assert a.needs.warmth == 100 - S["warmth_decay_night_per_min"]


def test_sleeping_regenerates_energy():
    a = make_agent(status="sleeping", needs=Needs(energy=50.0))
    tick_needs(a, NOON, S)
    assert a.needs.energy == 50 + S["energy_regen_sleeping_per_min"]


def test_collapse_and_recovery():
    a = make_agent(needs=Needs(hunger=0.05))
    events = tick_needs(a, NOON, S)
    assert a.status == "collapsed"
    assert events[0]["type"] == "collapsed"
    assert a.collapse_until == NOON + S["collapse_duration_min"]
    events = tick_needs(a, a.collapse_until, S)
    assert a.status == "active"
    assert a.needs.hunger == S["collapse_recover_need_value"]
    assert a.needs.energy >= S["collapse_recover_energy_value"]
    assert events[0]["type"] == "recovered"
