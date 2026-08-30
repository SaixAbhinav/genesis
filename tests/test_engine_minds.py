from genesis.world.engine import Engine
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState, Resource
from genesis.mind.brain import InstinctBrain, FakeBrain
from genesis.mind.queue import InlineQueue

WM = WorldMap(["GGGG", "GGGG", "GGGG", "GGGG"])
BASE = {"minutes_per_day": 100000, "day_start_minute": 0, "day_end_minute": 100000,
        "hunger_decay_per_min": 0.0, "energy_decay_per_min": 0.0,
        "energy_regen_sleeping_per_min": 0.0, "warmth_decay_night_per_min": 0.0,
        "warmth_decay_night_sleeping_per_min": 0.0, "warmth_regen_day_per_min": 0.0,
        "warmth_regen_near_fire_per_min": 0.0, "campfire_warmth_radius": 1,
        "collapse_duration_min": 5, "collapse_recover_need_value": 50.0,
        "collapse_recover_energy_value": 50.0, "wake_energy_threshold": 80.0,
        "morning_wake_min_energy": 50.0, "strain_decay_per_min": 0.0,
        "strain_lethal_threshold": 60.0, "strain_heal_threshold": 25.0,
        "decision_cooldown_min": 0, "decision_stale_min": 100000,
        # test-data addition: the brief's BASE omitted this, but actions.py's
        # 'eat' verb reads it unconditionally -- needed once tests actually
        # let the 'eat' action execute (e.g. the anti-loop and instinct-
        # fallback tests below).
        "eat_berries_hunger_restore": 10.0}


def _engine(agent, resources=None, chooser=None):
    st = WorldState(0, 7, [agent], resources or [])
    brain = FakeBrain(chooser) if chooser else InstinctBrain()
    q = InlineQueue()
    return Engine(st, settings=BASE, maps=[WM], brains={agent.id: brain}, queue=q)


def test_agent_adopts_and_pursues_llm_chosen_goal():
    a = Agent(id="a", name="A", x=0, y=0, brain="fake")
    berries = Resource(type="berries", x=3, y=0, qty=2, layer=0)
    # always pick the gather affordance
    eng = _engine(a, [berries], lambda c, affs:
                  {"choice": next(o["id"] for o in affs if o["verb"] == "gather"),
                   "reason": "hungry"})
    # NOTE (test-data adjustment): the brief's original version used
    # eng.advance(10). The resource sits at distance 3, so with 10 ticks the
    # agent arrives, gathers (a one-shot verb), and -- per the Task 6
    # augmentation -- the goal is correctly cleared the moment the terminal
    # 'gather' action is issued (same tick, since the agent is adjacent).
    # That collapse-and-clear is the *intended*, tested-elsewhere behavior
    # (see test_terminal_goal_clears_after_issue_so_agent_redecides), so
    # asserting "goal still set" after 10 ticks is a timing-fragile artifact
    # of the original test data, not the feature under test here ("the agent
    # adopts an LLM-chosen goal and walks toward it"). Advancing only 2 ticks
    # (< the distance of 3) keeps the assertion inside the walking phase,
    # where the goal is guaranteed to still be alive, deterministically.
    eng.advance(2)
    assert a.goal is not None and a.goal["verb"] == "gather"
    assert (a.x, a.y) != (0, 0)  # it walked toward the berries


def test_decided_event_carries_reason():
    a = Agent(id="a", name="A", x=0, y=0, brain="fake")
    r = Resource(type="berries", x=2, y=0, qty=2, layer=0)
    eng = _engine(a, [r], lambda c, affs:
                  {"choice": next(o["id"] for o in affs if o["verb"] == "gather"),
                   "reason": "berries look good"})
    events = eng.advance(3)
    decided = [e for e in events if e["type"] == "decided"]
    assert decided and decided[0]["reason"] == "berries look good"


def test_no_brain_no_queue_is_pure_instinct():
    # backward-compat: an Engine with neither brains nor queue must not error
    a = Agent(id="a", name="A", x=0, y=0)
    st = WorldState(0, 7, [a])
    eng = Engine(st, settings=BASE, maps=[WM])
    eng.advance(5)  # no exception, agent acts on instinct
    assert a.status != "dead"


def test_terminal_goal_clears_after_issue_so_agent_redecides():
    # Anti-loop regression: resolve_goal never returns None for a one-shot
    # verb like 'eat' while berries remain -- it keeps returning the same
    # action forever. Without goal-clearing, the goal would stay adopted and
    # this would spam 'eat' every tick without ever letting the agent
    # re-decide. Written RED-FIRST: fails without the _drive() clearing
    # logic (a.goal would still be the adopted 'eat' affordance dict after
    # one tick), passes with it.
    a = Agent(id="a", name="A", x=0, y=0, brain="fake", inventory={"berries": 3})
    eng = _engine(a, [], lambda c, affs: {"choice": "eat", "reason": "hungry"})
    eng.advance(1)
    assert a.goal is None  # 'eat' is terminal; the goal is cleared after being issued


def test_fatal_goal_is_not_interrupted_by_hunger():
    # Brain always picks 'observe'; with InlineQueue the goal is re-adopted every
    # decision, so Instinct's eat-reflex never runs. Hunger decays to death.
    a = Agent(id="a", name="A", x=0, y=0, brain="fake",
              inventory={"berries": 5})   # food on hand, but the mind won't eat
    a.needs.hunger = 3.0
    st = WorldState(0, 7, [a], [])
    settings = {**BASE, "hunger_decay_per_min": 1.0, "strain_lethal_threshold": -1.0}
    eng = Engine(st, settings=settings, maps=[WM],
                 brains={"a": FakeBrain(lambda c, affs: {"choice": "observe", "reason": "gaze"})},
                 queue=InlineQueue())
    eng.advance(10)
    assert a.status in ("collapsed", "dead")  # never rescued mid-goal


def test_instinct_acts_while_no_brain_result_available():
    # A queue that never returns a result -> agent must still act (instinct).
    class DeadQueue:
        def submit(self, job, brain): pass
        def pending(self, aid): return False
        def pop(self, aid): return None
    a = Agent(id="a", name="A", x=0, y=0, brain="fake")
    st = WorldState(0, 7, [a], [Resource(type="berries", x=1, y=0, qty=9, layer=0)])
    a.needs.hunger = 10.0
    settings = {**BASE, "hunger_decay_per_min": 0.0}
    eng = Engine(st, settings=settings, maps=[WM],
                 brains={"a": FakeBrain(lambda c, affs: {"choice": "observe", "reason": ""})},
                 queue=DeadQueue())
    eng.advance(3)
    assert a.current_action is not None or a.goal is None  # it kept acting via instinct
