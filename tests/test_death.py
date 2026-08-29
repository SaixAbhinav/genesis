from genesis.world.needs import tick_needs
from genesis.world.state import Agent

BASE = {"minutes_per_day": 100, "day_start_minute": 0, "day_end_minute": 100,
        "hunger_decay_per_min": 100.0, "energy_decay_per_min": 0.0,
        "energy_regen_sleeping_per_min": 0.0, "warmth_decay_night_per_min": 0.0,
        "warmth_decay_night_sleeping_per_min": 0.0, "warmth_regen_day_per_min": 0.0,
        "warmth_regen_near_fire_per_min": 0.0, "collapse_duration_min": 5,
        "collapse_recover_need_value": 50.0, "collapse_recover_energy_value": 50.0,
        "strain_decay_per_min": 0.0, "strain_lethal_threshold": 60.0}


def test_collapse_recovers_when_strain_low():
    a = Agent(id="a", name="A", x=0, y=0, strain=10.0)  # below lethal
    evs = tick_needs(a, 0, BASE)  # hunger crashes to 0
    assert a.status == "collapsed"
    assert any(e["type"] == "collapsed" for e in evs)


def test_dies_when_collapsing_with_high_strain():
    a = Agent(id="a", name="A", x=0, y=0, strain=70.0)  # above lethal
    evs = tick_needs(a, 0, BASE)
    assert a.status == "dead"
    assert any(e["type"] == "died" for e in evs)
