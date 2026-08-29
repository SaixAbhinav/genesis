import random
from genesis.world.grid import WorldMap
from genesis.world.hazards import miasma_tick, fall_check
from genesis.world.state import Agent, WorldState
from genesis.world.engine import Engine

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


def test_engine_fires_hazard_events_on_tick():
    """Integration test: Engine tier hazards (miasma + creature) fire and damage agent."""
    agent = Agent(id="a1", name="Agent1", x=0, y=0, layer=0)
    agent.needs.energy = 100.0
    state = WorldState(sim_minutes=0, seed=42, agents=[agent])

    # Layer 0 has hazards: miasma (5 dmg to energy) and creatures (3 dmg to energy)
    hazard_layer = {
        "miasma_damage": 5.0,
        "miasma_need": "energy",
        "creature_damage": 3.0,
    }
    # Minimal complete settings dict
    settings = {
        "layers": [hazard_layer],
        "campfire_warmth_radius": 2,
        "day_start_minute": 360,
        "day_end_minute": 1200,
        "minutes_per_day": 1440,
        "hunger_decay_per_min": 0.07,
        "energy_decay_per_min": 0.06,
        "energy_regen_sleeping_per_min": 0.35,
        "warmth_decay_night_per_min": 0.25,
        "warmth_decay_night_sleeping_per_min": 0.12,
        "warmth_regen_day_per_min": 0.5,
        "warmth_regen_near_fire_per_min": 0.4,
        "eat_berries_hunger_restore": 30.0,
        "stone_tools_gather_bonus": 1,
        "eat_cooked_hunger_bonus": 15.0,
        "drink_energy_restore": 5.0,
        "collapse_duration_min": 60,
        "collapse_recover_need_value": 25.0,
        "collapse_recover_energy_value": 40.0,
        "wake_energy_threshold": 95.0,
        "morning_wake_min_energy": 50.0,
    }

    engine = Engine(state, world_map=WM, settings=settings)
    events = engine.tick()

    # Verify both hazard events fired
    miasma_events = [e for e in events if e["type"] == "miasma"]
    creature_events = [e for e in events if e["type"] == "creature_attack"]

    assert len(miasma_events) > 0, "miasma event should fire"
    assert len(creature_events) > 0, "creature_attack event should fire"

    # Verify energy was damaged: 100 - 5 (miasma) - 3 (creature) - 0.06 (decay) ≈ 91.94
    assert agent.needs.energy < 100.0, f"Energy should be depleted, got {agent.needs.energy}"
    assert 91.0 < agent.needs.energy < 92.5, f"Expected energy ~91.94, got {agent.needs.energy}"
