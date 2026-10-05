from genesis.world.engine import Engine

SC = "configs/scenarios/first-contact"

_MIN = {"minutes_per_day": 100000, "day_start_minute": 0, "day_end_minute": 100000,
        "hunger_decay_per_min": 0.0, "energy_decay_per_min": 0.0,
        "energy_regen_sleeping_per_min": 0.0, "warmth_decay_night_per_min": 0.0,
        "warmth_decay_night_sleeping_per_min": 0.0, "warmth_regen_day_per_min": 0.0,
        "warmth_regen_near_fire_per_min": 0.0, "campfire_warmth_radius": 1,
        "decision_cooldown_min": 0, "decision_stale_min": 100000}


def _run(days):
    eng = Engine.from_configs("configs", scenario_dir=SC, seed=42,
                              sim_minutes=0, minds=False)
    return eng, eng.advance(int(days * eng.settings["minutes_per_day"]))


def test_scenario_runs_clean_instinct_only():
    eng, events = _run(1)
    assert eng.state.sim_minutes >= eng.settings["minutes_per_day"]
    assert all("type" in e for e in events)


def test_contact_event_fires_when_races_converge():
    from genesis.world.grid import WorldMap
    from genesis.world.state import Agent, WorldState
    wm = WorldMap(["GGGGGG"] * 6)
    a = Agent(id="a", name="Ash", x=1, y=1, race="ashfolk")
    b = Agent(id="b", name="Moss", x=2, y=1, race="mosskin")
    st = WorldState(0, 1, [a, b])
    eng = Engine(st, settings={**_MIN, "perception_radius": 6}, maps=[wm])
    events = eng.tick()
    assert any(e["type"] == "contact" and e["race"] == "mosskin"
               and e["agent"] == "a" for e in events)


def test_determinism_same_seed_same_contacts():
    _, e1 = _run(1)
    _, e2 = _run(1)
    key = lambda evs: [(e["type"], e.get("agent"), e["minute"]) for e in evs]
    assert key(e1) == key(e2)
