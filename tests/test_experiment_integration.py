from genesis.world.engine import Engine


def test_experiment_resolves_through_real_tick_loop():
    engine = Engine.from_configs("configs", seed=42, sim_minutes=720)
    a = engine.state.agents[0]
    a.layer = 0                     # surface: no curse band, no action_fail rolls
    a.knowledge = []
    a.inventory = {"flint": 1, "wood": 1}
    a.goal = None
    a.current_action = {"action": "experiment_with", "items": ["flint", "wood"]}
    engine.tick()                   # start tick: sets experiment_until, still chanting
    assert "fire" not in a.knowledge
    for _ in range(engine.settings["experiment_minutes"]):
        engine.tick()
    assert "fire" in a.knowledge     # resolved through the real engine tick loop
