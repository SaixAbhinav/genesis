from genesis.world.engine import Engine

SC = "configs/scenarios/first-contact"


def test_scenario_loads_races_and_applies_traits():
    eng = Engine.from_configs("configs", scenario_dir=SC, seed=1, sim_minutes=0)
    by_name = {a.name: a for a in eng.state.agents}
    assert len(eng.state.agents) == 4
    ash = by_name["Ash"]
    assert ash.race == "ashfolk"
    assert "fire" in ash.knowledge
    assert ash.inventory.get("flint", 0) == 1
    assert ash.warmth_decay_mult == 0.6
    assert ash.persona.startswith("You are of the Ashfolk")
    fern = by_name["Fern"]
    assert fern.race == "mosskin" and fern.warmth_decay_mult == 1.0
    assert fern.inventory.get("thick_moss", 0) == 1


def test_scenario_exposes_race_display_names():
    eng = Engine.from_configs("configs", scenario_dir=SC, seed=1, sim_minutes=0)
    assert eng.settings["race_names"] == {"ashfolk": "Ashfolk", "mosskin": "Mosskin"}


def test_scenario_is_single_layer_meadow():
    eng = Engine.from_configs("configs", scenario_dir=SC, seed=1, sim_minutes=0)
    assert len(eng.maps) == 1
    assert len(eng.settings["layers"]) == 1
