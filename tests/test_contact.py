from genesis.world.engine import Engine
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState
from genesis.mind.brain import FakeBrain
from genesis.mind.queue import InlineQueue

WM = WorldMap(["GGGGGGGG"] * 8)
BASE = {"minutes_per_day": 100000, "day_start_minute": 0, "day_end_minute": 100000,
        "hunger_decay_per_min": 0.0, "energy_decay_per_min": 0.0,
        "energy_regen_sleeping_per_min": 0.0, "warmth_decay_night_per_min": 0.0,
        "warmth_decay_night_sleeping_per_min": 0.0, "warmth_regen_day_per_min": 0.0,
        "warmth_regen_near_fire_per_min": 0.0, "campfire_warmth_radius": 1,
        "decision_cooldown_min": 100000, "decision_stale_min": 100000,
        "perception_radius": 6, "perception_affordance_cap": 3}


def _engine(agents, chooser):
    st = WorldState(0, 7, agents)
    brains = {a.id: FakeBrain(chooser) for a in agents}
    return Engine(st, settings=BASE, maps=[WM], brains=brains, queue=InlineQueue())


def test_first_contact_emits_event_and_forces_decision():
    a = Agent(id="a", name="Ash", x=1, y=1, race="ashfolk", brain="fake")
    b = Agent(id="b", name="Moss", x=3, y=1, race="mosskin", brain="fake")
    eng = _engine([a, b], lambda c, affs: {"choice": "observe", "reason": "watch"})
    events = eng.tick()
    contacts = [e for e in events if e["type"] == "contact"]
    assert {c["race"] for c in contacts} == {"ashfolk", "mosskin"}
    assert any(e["type"] == "decided" for e in events)


def test_contact_context_has_nearby_and_race():
    a = Agent(id="a", name="Ash", x=1, y=1, race="ashfolk", brain="fake")
    b = Agent(id="b", name="Moss", x=3, y=1, race="mosskin", brain="fake")
    seen = []

    def chooser(ctx, affs):
        seen.append(dict(ctx))
        return {"choice": "observe", "reason": "watch"}

    _engine([a, b], chooser).tick()
    ash_ctx = next(c for c in seen if c["race"] == "ashfolk")
    assert any(n["name"] == "Moss" and n["race"] == "mosskin"
               for n in ash_ctx["nearby"])


def test_contact_fires_once_per_race():
    a = Agent(id="a", name="Ash", x=1, y=1, race="ashfolk", brain="fake")
    b = Agent(id="b", name="Moss", x=3, y=1, race="mosskin", brain="fake")
    eng = _engine([a, b], lambda c, affs: {"choice": "observe", "reason": "watch"})
    eng.tick()
    later = eng.tick()
    assert not any(e["type"] == "contact" for e in later)


def test_forced_contact_decision_carries_notice_only_once():
    a = Agent(id="a", name="Ash", x=1, y=1, race="ashfolk", brain="fake")
    b = Agent(id="b", name="Moss", x=3, y=1, race="mosskin", brain="fake")
    ash_ctxs = []

    def chooser(ctx, affs):
        if ctx["race"] == "ashfolk":
            ash_ctxs.append(dict(ctx))
        return {"choice": "observe", "reason": "watch"}

    st = WorldState(0, 7, [a, b])
    settings = {**BASE, "decision_cooldown_min": 0,
                "race_names": {"ashfolk": "Ashfolk", "mosskin": "Mosskin"}}
    eng = Engine(st, settings=settings, maps=[WM],
                 brains={x.id: FakeBrain(chooser) for x in (a, b)},
                 queue=InlineQueue())
    for _ in range(3):
        eng.tick()
    assert len(ash_ctxs) >= 2
    first, later = ash_ctxs[0], ash_ctxs[1:]
    assert len(first["notice"]) == 1
    assert "Moss" in first["notice"][0] and "Mosskin" in first["notice"][0]
    assert all("notice" not in c for c in later)


def test_no_contact_between_same_or_raceless_agents():
    a = Agent(id="a", name="A", x=1, y=1, brain="fake")
    b = Agent(id="b", name="B", x=3, y=1, brain="fake")
    eng = _engine([a, b], lambda c, affs: {"choice": "observe", "reason": "watch"})
    assert not any(e["type"] == "contact" for e in eng.tick())
