from genesis.world.engine import Engine


def test_from_configs_without_minds_has_no_brains():
    eng = Engine.from_configs("configs")
    assert eng.brains == {} and eng.queue is None


def test_from_configs_with_minds_wires_a_brain_per_agent(monkeypatch):
    import json
    from pathlib import Path
    monkeypatch.setenv("GROQ_API_KEY", "test")
    expected_model = json.loads(
        Path("configs/brains.json").read_text(encoding="utf-8")
    )["brains"]["default"]["model"]
    eng = Engine.from_configs("configs", minds=True)
    assert eng.queue is not None
    assert len(eng.brains) == len(eng.state.agents)
    for b in eng.brains.values():
        assert b.model == expected_model


from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState
from genesis.mind.brain import FakeBrain
from genesis.mind.queue import ThreadedThinkQueue


def test_catch_up_submits_no_llm_jobs():
    a = Agent(id="a", name="A", x=0, y=0, brain="fake")
    st = WorldState(0, 7, [a], [])
    S = {"minutes_per_day": 100000, "day_start_minute": 0, "day_end_minute": 100000,
         "hunger_decay_per_min": 0.0, "energy_decay_per_min": 0.0,
         "energy_regen_sleeping_per_min": 0.0, "warmth_decay_night_per_min": 0.0,
         "warmth_decay_night_sleeping_per_min": 0.0, "warmth_regen_day_per_min": 0.0,
         "warmth_regen_near_fire_per_min": 0.0, "campfire_warmth_radius": 1,
         "collapse_duration_min": 5, "collapse_recover_need_value": 50.0,
         "collapse_recover_energy_value": 50.0, "wake_energy_threshold": 80.0,
         "morning_wake_min_energy": 50.0, "strain_decay_per_min": 0.0,
         "strain_lethal_threshold": 60.0, "strain_heal_threshold": 25.0,
         "decision_cooldown_min": 0, "decision_stale_min": 100000}
    q = ThreadedThinkQueue(daily_budget=1000)
    eng = Engine(st, settings=S, maps=[WorldMap(["GG", "GG"])],
                 brains={"a": FakeBrain(lambda c, af: {"choice": "observe", "reason": ""})},
                 queue=q)
    eng.advance(20, live=False)
    assert q.requests_today == 0   # no LLM jobs during catch-up
