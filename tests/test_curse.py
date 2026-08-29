# tests/test_curse.py
from genesis.world.actions import step_action, validate_action
from genesis.world.grid import WorldMap
from genesis.world.needs import tick_needs
from genesis.world.state import Agent, WorldState

WM = WorldMap(["CC", "CC"])  # all cave tiles, walkable
LAYERS = [
    {"curse_strain": 5, "link": {"descend": [0, 0], "entry_down": [1, 1], "entry_up": [0, 0]}},
    {"curse_strain": 20, "link": {"descend": [1, 0], "entry_down": [1, 1], "ascend": [1, 1], "entry_up": [0, 0]}},
]
SET = {"layers": LAYERS, "strain_decay_per_min": 0.5, "minutes_per_day": 100,
       "day_start_minute": 0, "day_end_minute": 100, "hunger_decay_per_min": 0.0,
       "energy_decay_per_min": 0.0, "energy_regen_sleeping_per_min": 0.0,
       "warmth_decay_night_per_min": 0.0, "warmth_decay_night_sleeping_per_min": 0.0,
       "warmth_regen_day_per_min": 0.0, "warmth_regen_near_fire_per_min": 0.0,
       "collapse_duration_min": 1, "collapse_recover_need_value": 50.0,
       "collapse_recover_energy_value": 50.0, "strain_lethal_threshold": 60.0}


def test_descend_requires_link_tile():
    a = Agent(id="a", name="A", x=1, y=0, layer=0)  # not on descend tile
    ok, why = validate_action({"action": "descend"}, a, WorldState(0, 1, [a]),
                              WM, settings=SET)
    assert not ok


def test_descend_moves_to_next_layer_no_strain():
    a = Agent(id="a", name="A", x=0, y=0, layer=0)
    st = WorldState(0, 1, [a]); a.current_action = {"action": "descend"}
    step_action(a, st, WM, SET, None, None)
    assert a.layer == 1 and (a.x, a.y) == (1, 1) and a.strain == 0.0


def test_ascend_adds_curse_strain_of_layer_left():
    a = Agent(id="a", name="A", x=1, y=1, layer=1)
    st = WorldState(0, 1, [a]); a.current_action = {"action": "ascend"}
    step_action(a, st, WM, SET, None, None)
    assert a.layer == 0 and (a.x, a.y) == (0, 0) and a.strain == 20.0


def test_strain_decays_each_minute():
    a = Agent(id="a", name="A", x=0, y=0, strain=10.0)
    tick_needs(a, 0, SET)
    assert a.strain == 9.5
