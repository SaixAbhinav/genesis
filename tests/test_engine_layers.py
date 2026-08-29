from genesis.world.engine import Engine
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState

M0 = WorldMap(["GG", "GG"])
M1 = WorldMap(["RR", "RR"])
SET = {"minutes_per_day": 100, "day_start_minute": 0, "day_end_minute": 100,
       "hunger_decay_per_min": 0.0, "energy_decay_per_min": 0.0,
       "energy_regen_sleeping_per_min": 0.0, "warmth_decay_night_per_min": 0.0,
       "warmth_decay_night_sleeping_per_min": 0.0, "warmth_regen_day_per_min": 0.0,
       "warmth_regen_near_fire_per_min": 0.0, "campfire_warmth_radius": 1,
       "collapse_duration_min": 1, "collapse_recover_need_value": 50.0,
       "collapse_recover_energy_value": 50.0, "wake_energy_threshold": 80.0,
       "morning_wake_min_energy": 50.0, "strain_decay_per_min": 0.0,
       "strain_lethal_threshold": 60.0}


def test_map_for_returns_agents_layer():
    a0 = Agent(id="a0", name="A", x=0, y=0, layer=0)
    a1 = Agent(id="a1", name="B", x=0, y=0, layer=1)
    ws = WorldState(sim_minutes=0, seed=1, agents=[a0, a1])
    eng = Engine(ws, settings=SET, maps=[M0, M1])
    assert eng.map_for(a0).terrain(0, 0) == "grass"
    assert eng.map_for(a1).terrain(0, 0) == "rock"


def test_single_world_map_still_supported():
    ws = WorldState(sim_minutes=0, seed=1,
                    agents=[Agent(id="a", name="A", x=0, y=0)])
    eng = Engine(ws, world_map=M0, settings=SET)
    assert eng.maps == [M0]
