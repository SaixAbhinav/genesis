# tests/test_integration_dive.py
from genesis.world.engine import Engine
from genesis.world.grid import WorldMap
from genesis.world.magic import MagicBook
from genesis.world.state import Agent, WorldState


def _book():
    return MagicBook.from_dict({
        "attributes": ["healing"], "ranks": ["beginner", "intermediate"],
        "rank_xp": {"beginner": 0, "intermediate": 20},
        "spells": [{"name": "minor_heal", "kind": "spell", "attribute": "healing",
                    "requires": ["mana_shard"], "prereqs": {}, "base_cast_minutes": 1,
                    "mana_cost": 5, "xp_per_cast": 6,
                    "effect": {"type": "reduce_strain", "amount": 40}}],
        "params": {"mana_depletion_frac": 0.15, "mana_growth_step": 5.0}})


BASE = {"minutes_per_day": 1000, "day_start_minute": 0, "day_end_minute": 1000,
        "hunger_decay_per_min": 0.0, "energy_decay_per_min": 0.0,
        "energy_regen_sleeping_per_min": 0.0, "warmth_decay_night_per_min": 0.0,
        "warmth_decay_night_sleeping_per_min": 0.0, "warmth_regen_day_per_min": 0.0,
        "warmth_regen_near_fire_per_min": 0.0, "campfire_warmth_radius": 1,
        "collapse_duration_min": 5, "collapse_recover_need_value": 50.0,
        "collapse_recover_energy_value": 50.0, "wake_energy_threshold": 80.0,
        "morning_wake_min_energy": 50.0, "strain_decay_per_min": 0.0,
        "strain_lethal_threshold": 60.0, "strain_heal_threshold": 20.0}

MAPS = [WorldMap(["CC", "CC"]), WorldMap(["CC", "CC"]), WorldMap(["CC", "CC"])]
LAYERS = [
    {"curse_strain": 5, "link": {"descend": [0, 0], "entry_down": [1, 1], "entry_up": [1, 1]}},
    {"curse_strain": 20, "link": {"descend": [0, 0], "ascend": [1, 1],
                                  "entry_down": [1, 1], "entry_up": [1, 1]}},
    {"curse_strain": 45, "link": {"ascend": [1, 1], "entry_up": [1, 1]}},
]


def test_well_ranked_agent_survives_the_climb():
    # Scripted: an agent ascends from L2, which pushes strain to 65 (>= lethal 60).
    # A heal then reduces strain to 25 (< lethal), so when energy crashes,
    # the agent collapses (survives) rather than dies.
    # If reduce_strain were a no-op, strain would stay 65 and the crash would kill.
    a = Agent(id="hero", name="Reg", x=1, y=1, layer=2, strain=20.0,
              mana=50.0, mana_max=50.0, knowledge=["minor_heal"],
              attr_rank={"healing": 1})
    a.needs.energy = 40.0
    st = WorldState(0, 7, [a])
    settings = {**BASE, "layers": LAYERS, "energy_decay_per_min": 10.0}
    eng = Engine(st, settings=settings, maps=MAPS, layers=LAYERS, magic=_book())

    # Tick 1: Ascend L2->L1, strain 20+45=65 (>= lethal 60)
    a.current_action = {"action": "ascend"}
    eng.advance(1)
    assert a.layer == 1 and a.strain == 65.0 and a.status == "active"

    # Ticks 2-3: Heal (cast takes 2 ticks), strain 65-40=25 (< lethal 60)
    a.current_action = {"action": "cast", "spell": "minor_heal"}
    eng.advance(2)
    assert a.strain == 25.0 and a.status == "active"

    # Tick 4: Energy crashes (40->30->20->10->0 over 4 ticks)
    # With strain 25 < lethal, agent collapses (survives) not dies
    eng.advance(1)

    # Test assertion: agent survived the energy crash
    assert a.status != "dead"


def test_under_ranked_agent_dies_on_the_climb():
    # No heal, energy will be spent: ascending from L2 pushes strain past lethal,
    # and the next need-crash kills instead of collapsing.
    a = Agent(id="fool", name="Nanachi", x=1, y=1, layer=2, strain=20.0)
    a.needs.energy = 20.0  # will decay to 10 after first tick, to 0 after second
    st = WorldState(0, 7, [a])
    settings = {**BASE, "layers": LAYERS, "hunger_decay_per_min": 0.0,
                "energy_decay_per_min": 10.0}
    eng = Engine(st, settings=settings, maps=MAPS, layers=LAYERS, magic=_book())
    a.current_action = {"action": "ascend"}     # +45 strain -> 65 >= lethal
    eng.advance(1)  # tick_needs: energy 20->10 (no crash); step_action: ascend (strain 20->65)
    eng.advance(1)  # tick_needs: energy 10->0 (crash + strain 65 >= lethal -> dead)
    assert a.status == "dead"
