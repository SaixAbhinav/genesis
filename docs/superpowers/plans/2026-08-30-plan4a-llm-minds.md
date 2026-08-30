# Plan 4a — LLM Minds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a real LLM asynchronously drive an Agent's grounded choices in the Genesis sim, without disturbing the deterministic engine or its 119 passing tests.

**Architecture:** The engine computes an **affordance menu** of currently-valid options; a **Brain** (LLM) picks one, which becomes a durable **Goal** the engine drives to completion as concrete Actions. Brains run through an async **ThinkQueue** (world never blocks); **Instinct** (today's `choose_action`, unchanged) is the fallback. Everything is opt-in — an Engine built without a brain/queue behaves exactly as today.

**Tech Stack:** Python 3.12, uv, pytest. Groq REST API via stdlib `urllib` (no new dependency). Config in JSON + `.env`.

## Global Constraints

- Never commit directly to `main`; work on `feat/abyss-magic`. Feature branch + PR. (CLAUDE.md)
- No Claude attribution in commits. (CLAUDE.md)
- All 119 existing tests MUST stay green and unchanged; the LLM path is opt-in and injected.
- No test may make a real network call. Groq HTTP is always mocked in tests.
- `agent.goal` is a plain `dict | None` (like `current_action`) so it round-trips through `asdict`/`from_json` with no db.py change.
- Affordance ids are **stable**: `verb + target's own identity` (e.g. `gather:berries@(6,3,0)`), never agent-relative.
- Minds are **sovereign over death**: no survival interrupt. An active Goal runs to completion/invalidity even if fatal. (spec §3; CONTEXT.md)
- Fast-forward / catch-up is **Instinct-only** — never submits LLM jobs. (ADR 0001)
- No new pip dependency without flagging. This plan adds none (stdlib `urllib`).

---

## File Structure & Interfaces (locked)

Exact signatures every task must match:

- `src/genesis/world/state.py` — add `Agent.goal: dict | None = None`
- `src/genesis/world/affordances.py` (new)
  `affordances(agent, state, world_map, settings, graph=None, magic=None) -> list[dict]`
  each item: `{"id": str, "verb": str, "params": dict, "label": str, "dir": str, "dist": int}`
- `src/genesis/world/goal.py` (new)
  `resolve_goal(agent, goal, state, world_map, settings, graph=None, magic=None) -> dict | None`
  (`goal` is an affordance dict; returns an **action** dict or `None` when the goal is satisfied/invalid)
- `src/genesis/mind/brain.py` (new)
  `class InstinctBrain: act(self, agent, state, world_map, settings, rng, graph=None, magic=None) -> dict | None`
  `class FakeBrain: choose(self, context: dict, affordances: list[dict]) -> dict`  (returns `{"choice": id, "reason": str}`)
  `class BrainError(Exception)`
- `src/genesis/mind/llm_brain.py` (new)
  `class LLMBrain: __init__(self, provider, model: str); choose(self, context, affordances) -> dict`
- `src/genesis/mind/groq.py` (new)
  `class GroqAdapter: __init__(self, model: str, api_key: str | None = None); complete(self, prompt: str, schema: dict) -> dict`
- `src/genesis/mind/queue.py` (new)
  `@dataclass DecisionJob: agent_id: str; sim_minute: int; affordances: list[dict]; context: dict`
  `class InlineQueue: submit(job, brain); pending(agent_id) -> bool; pop(agent_id) -> dict | None`
  `class ThreadedThinkQueue: __init__(self, daily_budget: int); submit(job, brain); pending(agent_id) -> bool; pop(agent_id) -> dict | None; requests_today: int`
  (both `pop` return `{"choice": id, "reason": str, "sim_minute": int}` or `None`)
- `src/genesis/world/engine.py` — `Engine.__init__(..., brains=None, queue=None)`; decision flow in `tick`; `from_configs(..., minds=False)`
- `src/genesis/cli.py` — `--minds` flag
- `configs/brains.json`, `.env.example`, `configs/settings.json` (+3 keys)

Tests: `tests/test_affordances.py`, `tests/test_goal.py`, `tests/test_mind_brain.py`, `tests/test_queue.py`, `tests/test_engine_minds.py`, `tests/test_llm_brain.py`, `tests/test_groq.py`, `tests/test_minds_config.py`.

---

### Task 1: `Agent.goal` field

**Files:**
- Modify: `src/genesis/world/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `Agent.goal: dict | None = None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state.py  (add)
def test_agent_goal_round_trips_through_json():
    from genesis.world.state import Agent, WorldState
    a = Agent(id="a", name="A", x=0, y=0, goal={"id": "eat", "verb": "eat"})
    st = WorldState(sim_minutes=0, seed=1, agents=[a])
    back = WorldState.from_json(st.to_json())
    assert back.agents[0].goal == {"id": "eat", "verb": "eat"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py::test_agent_goal_round_trips_through_json -v`
Expected: FAIL — `Agent.__init__() got an unexpected keyword argument 'goal'`

- [ ] **Step 3: Add the field**

In `state.py`, in the `Agent` dataclass, after `current_action: dict | None = None`:

```python
    goal: dict | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/state.py tests/test_state.py
git commit -m "Add Agent.goal field for the mind layer"
```

---

### Task 2: Affordance menu builder

**Files:**
- Create: `src/genesis/world/affordances.py`
- Test: `tests/test_affordances.py`

**Interfaces:**
- Consumes: `validate_action` from `actions.py`, `_nearest_resource` pattern from `instinct.py`.
- Produces: `affordances(agent, state, world_map, settings, graph=None, magic=None) -> list[dict]`

Each affordance: `{"id","verb","params","label","dir","dist"}`. `id` is stable (target identity, not agent position). Include an option only if the resulting action would pass `validate_action` **from a reachable position** (an affordance may require walking there first — that's the Goal's job).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_affordances.py
from genesis.world.affordances import affordances
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState, Resource

WM = WorldMap(["GGGG", "GGGG", "GGGG", "GGGG"])
S = {"campfire_warmth_radius": 2, "strain_heal_threshold": 25.0}


def _agent(**kw):
    return Agent(id="a", name="A", x=0, y=0, **kw)


def test_offers_gather_for_reachable_resource_with_stable_id():
    st = WorldState(0, 1, [_agent()], [Resource(type="berries", x=2, y=1, qty=3, layer=0)])
    opts = affordances(_agent(), st, WM, S)
    berry = [o for o in opts if o["verb"] == "gather" and o["params"].get("resource") == "berries"]
    assert berry, "should offer gathering the berries"
    assert berry[0]["id"] == "gather:berries@(2,1,0)"  # stable: resource identity, not agent-relative


def test_offers_eat_when_holding_berries():
    a = _agent(inventory={"berries": 2})
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, S)
    assert any(o["id"] == "eat" and o["verb"] == "eat" for o in opts)


def test_no_gather_for_resource_on_other_layer():
    a = _agent(layer=0)
    st = WorldState(0, 1, [a], [Resource(type="berries", x=2, y=1, qty=3, layer=1)])
    opts = affordances(a, st, WM, S)
    assert not any(o["verb"] == "gather" for o in opts)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_affordances.py -v`
Expected: FAIL — `ModuleNotFoundError: genesis.world.affordances`

- [ ] **Step 3: Write minimal implementation**

```python
# src/genesis/world/affordances.py
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState


def _dir(dx, dy):
    ns = ("N" if dy < 0 else "S" if dy > 0 else "")
    ew = ("W" if dx < 0 else "E" if dx > 0 else "")
    return (ns + ew) or "here"


def affordances(agent: Agent, state: WorldState, world_map: WorldMap,
                settings: dict, graph=None, magic=None) -> list[dict]:
    opts: list[dict] = []

    # eat / drink from inventory
    if agent.inventory.get("berries", 0) > 0:
        opts.append({"id": "eat", "verb": "eat", "params": {},
                     "label": "eat berries you carry", "dir": "here", "dist": 0})

    # gather any reachable resource on this layer
    for r in state.resources:
        if r.qty > 0 and r.layer == agent.layer:
            dx, dy = r.x - agent.x, r.y - agent.y
            opts.append({
                "id": f"gather:{r.type}@({r.x},{r.y},{r.layer})",
                "verb": "gather", "params": {"resource": r.type, "x": r.x, "y": r.y},
                "label": f"gather {r.type}", "dir": _dir(dx, dy),
                "dist": abs(dx) + abs(dy)})

    # sleep and observe are always available
    opts.append({"id": "sleep", "verb": "sleep", "params": {},
                 "label": "sleep to recover energy", "dir": "here", "dist": 0})
    opts.append({"id": "observe", "verb": "observe", "params": {},
                 "label": "watch and wait", "dir": "here", "dist": 0})
    return opts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_affordances.py -v`
Expected: PASS

- [ ] **Step 5: Add the remaining verbs (one test → one branch each)**

Add tests and branches, in this order, committing after each is green. For each: write the failing test first, run it, then add the branch.

- `experiment_with`: offer `{"id": "experiment", "verb": "experiment_with", "params": {"items": held}}` when `graph is not None` and `held = [k for k,v in agent.inventory.items() if v>0]` is non-empty and `graph.match(held, agent.knowledge)` is not None and not already known.
- `build`: for each of `("campfire","hut")`, offer `{"id": f"build:{s}", "verb":"build","params":{"structure":s}}` when `graph.buildable(s)` exists, its `requires` are all in `agent.knowledge`, and materials are held (`all(agent.inventory.get(m,0)>=n for m,n in spec["materials"].items())`).
- `cast`: for each spell in `agent.knowledge` that `magic.spell(name)` returns with `agent.mana >= spell["mana_cost"]`, offer `{"id": f"cast:{name}", "verb":"cast","params":{"spell":name}}`.
- `descend`/`ascend`: when `settings.get("layers")` has a `link` with that verb tile for `agent.layer`, offer `{"id": verb, "verb": verb, "params": {}, ...}` with the link tile as target for relocation.
- `harvest_relic`: offer for a relic resource (type startswith `relic:`) the same way as gather but `verb="harvest_relic"`.

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/affordances.py tests/test_affordances.py
git commit -m "Add affordance menu builder with stable target-identity ids"
```

---

### Task 3: Goal resolver

**Files:**
- Create: `src/genesis/world/goal.py`
- Test: `tests/test_goal.py`

**Interfaces:**
- Consumes: an affordance dict (Task 2), `validate_action` from `actions.py`, `WorldMap.walkable/neighbors4`.
- Produces: `resolve_goal(agent, goal, state, world_map, settings, graph=None, magic=None) -> dict | None`

Rule: build the concrete action from `goal["verb"] + goal["params"]`. If it validates **here**, return it. Else if the goal has a target tile and the agent isn't adjacent, return a `move_to` toward an adjacent walkable tile. Else return `None` (satisfied/invalid). `move_to` persists across ticks in the engine, so one `move_to` walks the whole path.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_goal.py
from genesis.world.goal import resolve_goal
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState, Resource

WM = WorldMap(["GGGG", "GGGG", "GGGG", "GGGG"])


def test_gather_far_resource_returns_move_toward_it():
    a = Agent(id="a", name="A", x=0, y=0)
    st = WorldState(0, 1, [a], [Resource(type="berries", x=3, y=0, qty=2, layer=0)])
    goal = {"id": "gather:berries@(3,0,0)", "verb": "gather",
            "params": {"resource": "berries", "x": 3, "y": 0}}
    act = resolve_goal(a, goal, st, WM, {})
    assert act["action"] == "move_to"


def test_gather_adjacent_resource_returns_gather():
    a = Agent(id="a", name="A", x=2, y=0)
    st = WorldState(0, 1, [a], [Resource(type="berries", x=3, y=0, qty=2, layer=0)])
    goal = {"id": "gather:berries@(3,0,0)", "verb": "gather",
            "params": {"resource": "berries", "x": 3, "y": 0}}
    act = resolve_goal(a, goal, st, WM, {})
    assert act == {"action": "gather", "resource": "berries"}


def test_gather_depleted_resource_returns_none():
    a = Agent(id="a", name="A", x=2, y=0)
    st = WorldState(0, 1, [a], [Resource(type="berries", x=3, y=0, qty=0, layer=0)])
    goal = {"id": "gather:berries@(3,0,0)", "verb": "gather",
            "params": {"resource": "berries", "x": 3, "y": 0}}
    assert resolve_goal(a, goal, st, WM, {}) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_goal.py -v`
Expected: FAIL — `ModuleNotFoundError: genesis.world.goal`

- [ ] **Step 3: Write minimal implementation**

```python
# src/genesis/world/goal.py
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState


def _adjacent(agent, x, y, world_map):
    tiles = [(agent.x, agent.y)] + world_map.neighbors4(agent.x, agent.y)
    return (x, y) in tiles


def _move_toward(agent, x, y, world_map):
    # walk onto the target if walkable, else onto a walkable neighbor of it
    if world_map.walkable(x, y):
        return {"action": "move_to", "x": x, "y": y}
    for nx, ny in world_map.neighbors4(x, y):
        if world_map.walkable(nx, ny):
            return {"action": "move_to", "x": nx, "y": ny}
    return None


def resolve_goal(agent: Agent, goal: dict, state: WorldState, world_map: WorldMap,
                 settings: dict, graph=None, magic=None) -> dict | None:
    verb = goal["verb"]
    p = goal.get("params", {})

    if verb in ("gather", "harvest_relic"):
        r = next((r for r in state.resources
                  if r.type == p["resource"] and r.x == p["x"] and r.y == p["y"]
                  and r.layer == agent.layer), None)
        if r is None or r.qty <= 0:
            return None
        if _adjacent(agent, r.x, r.y, world_map):
            return {"action": verb, "resource": r.type}
        return _move_toward(agent, r.x, r.y, world_map)

    if verb == "eat":
        return {"action": "eat"} if agent.inventory.get("berries", 0) > 0 else None
    if verb in ("sleep", "observe"):
        return {"action": verb}
    if verb == "experiment_with":
        return {"action": "experiment_with", "items": p["items"]}
    if verb == "build":
        return {"action": "build", "structure": p["structure"]}
    if verb == "cast":
        return {"action": "cast", "spell": p["spell"]}
    if verb in ("descend", "ascend"):
        layers = settings.get("layers", [])
        tile = layers[agent.layer].get("link", {}).get(verb) if layers else None
        if tile is None:
            return None
        if [agent.x, agent.y] == tile:
            return {"action": verb}
        return _move_toward(agent, tile[0], tile[1], world_map)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_goal.py -v`
Expected: PASS

- [ ] **Step 5: Add tests for the remaining verbs** (sleep/observe → returns the action; experiment/build/cast → returns the action; descend far → move_to; descend on-tile → the verb). One test per branch, commit when green.

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/goal.py tests/test_goal.py
git commit -m "Add goal resolver: expand a Goal into the next concrete Action"
```

---

### Task 4: Brain protocol, FakeBrain, InstinctBrain

**Files:**
- Create: `src/genesis/mind/__init__.py` (empty), `src/genesis/mind/brain.py`
- Test: `tests/test_mind_brain.py`

**Interfaces:**
- Consumes: `choose_action` from `instinct.py`.
- Produces: `InstinctBrain.act(...)`, `FakeBrain.choose(context, affordances) -> {"choice","reason"}`, `BrainError`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_mind_brain.py
from genesis.mind.brain import InstinctBrain, FakeBrain
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState
import random

WM = WorldMap(["GG", "GG"])


def test_instinct_brain_matches_choose_action():
    from genesis.world.instinct import choose_action
    a = Agent(id="a", name="A", x=0, y=0)
    st = WorldState(0, 7, [a])
    S = {"minutes_per_day": 1000, "day_start_minute": 0, "day_end_minute": 1000}
    expected = choose_action(a, st, WM, S, random.Random(7))
    got = InstinctBrain().act(a, st, WM, S, random.Random(7))
    assert got == expected


def test_fake_brain_returns_scripted_choice():
    fb = FakeBrain(lambda ctx, affs: {"choice": affs[0]["id"], "reason": "first"})
    out = fb.choose({}, [{"id": "eat"}, {"id": "sleep"}])
    assert out == {"choice": "eat", "reason": "first"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mind_brain.py -v`
Expected: FAIL — `ModuleNotFoundError: genesis.mind.brain`

- [ ] **Step 3: Write minimal implementation**

```python
# src/genesis/mind/brain.py
from genesis.world.instinct import choose_action


class BrainError(Exception):
    pass


class InstinctBrain:
    """The deterministic reflex Mind — today's choose_action, unchanged."""
    def act(self, agent, state, world_map, settings, rng, graph=None, magic=None):
        return choose_action(agent, state, world_map, settings, rng, graph, magic)


class FakeBrain:
    """Scripted LLM Brain for deterministic tests. `chooser(ctx, affs)->dict`."""
    def __init__(self, chooser):
        self._chooser = chooser

    def choose(self, context: dict, affordances: list[dict]) -> dict:
        return self._chooser(context, affordances)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_mind_brain.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/genesis/mind/__init__.py src/genesis/mind/brain.py tests/test_mind_brain.py
git commit -m "Add Mind seam: InstinctBrain (reflex) and FakeBrain (test double)"
```

---

### Task 5: DecisionJob + InlineQueue

**Files:**
- Create: `src/genesis/mind/queue.py`
- Test: `tests/test_queue.py`

**Interfaces:**
- Consumes: a Brain with `.choose(context, affordances)`.
- Produces: `DecisionJob`, `InlineQueue.submit/pending/pop`. `pop` returns `{"choice","reason","sim_minute"} | None`. An invalid choice (not in the submitted affordance ids) yields no result and clears pending.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_queue.py
from genesis.mind.queue import DecisionJob, InlineQueue
from genesis.mind.brain import FakeBrain


def _job(agent_id="a", minute=0):
    return DecisionJob(agent_id=agent_id, sim_minute=minute,
                       affordances=[{"id": "eat"}, {"id": "sleep"}], context={})


def test_inline_queue_resolves_immediately():
    q = InlineQueue()
    q.submit(_job(), FakeBrain(lambda c, a: {"choice": "sleep", "reason": "tired"}))
    out = q.pop("a")
    assert out["choice"] == "sleep" and out["reason"] == "tired" and out["sim_minute"] == 0


def test_inline_queue_drops_invalid_choice():
    q = InlineQueue()
    q.submit(_job(), FakeBrain(lambda c, a: {"choice": "fly", "reason": "nope"}))
    assert q.pop("a") is None
    assert q.pending("a") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_queue.py -v`
Expected: FAIL — `ModuleNotFoundError: genesis.mind.queue`

- [ ] **Step 3: Write minimal implementation**

```python
# src/genesis/mind/queue.py
from dataclasses import dataclass


@dataclass
class DecisionJob:
    agent_id: str
    sim_minute: int
    affordances: list[dict]
    context: dict


def _resolve(job: DecisionJob, brain) -> dict | None:
    ids = {a["id"] for a in job.affordances}
    try:
        out = brain.choose(job.context, job.affordances)
    except Exception:
        return None
    if not isinstance(out, dict) or out.get("choice") not in ids:
        return None
    return {"choice": out["choice"], "reason": out.get("reason", ""),
            "sim_minute": job.sim_minute}


class InlineQueue:
    """Synchronous queue: resolves each job immediately. Deterministic."""
    def __init__(self):
        self._inbox: dict[str, dict] = {}
        self._pending: set[str] = set()

    def submit(self, job: DecisionJob, brain) -> None:
        self._pending.add(job.agent_id)
        result = _resolve(job, brain)
        self._pending.discard(job.agent_id)
        if result is not None:
            self._inbox[job.agent_id] = result

    def pending(self, agent_id: str) -> bool:
        return agent_id in self._pending

    def pop(self, agent_id: str) -> dict | None:
        return self._inbox.pop(agent_id, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_queue.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/genesis/mind/queue.py tests/test_queue.py
git commit -m "Add DecisionJob and synchronous InlineQueue"
```

---

### Task 6: Engine decision flow (the integration)

**Files:**
- Modify: `src/genesis/world/engine.py`
- Test: `tests/test_engine_minds.py`

**Interfaces:**
- Consumes: `affordances` (T2), `resolve_goal` (T3), `InstinctBrain` (T4), `InlineQueue`/`DecisionJob` (T5).
- Produces: `Engine.__init__(..., brains: dict | None = None, queue=None)`; per-agent decision flow; `decided` event `{"type":"decided","agent","choice","reason","model","minute"}`.

The flow inside `tick`, per active/sleeping agent when `current_action is None` (replaces the current single `choose_action` call). Order matters — see the InlineQueue pop-after-submit note (makes InlineQueue drive synchronously; ThreadedThinkQueue stays async).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_minds.py
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
        "decision_cooldown_min": 0, "decision_stale_min": 100000}


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
    eng.advance(10)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_engine_minds.py -v`
Expected: FAIL — `Engine.__init__() got an unexpected keyword argument 'brains'`

- [ ] **Step 3: Write minimal implementation**

In `engine.py`, extend `__init__`:

```python
    def __init__(self, state, world_map=None, settings=None, graph=None,
                 maps=None, magic=None, brains=None, queue=None):
        # ...existing body...
        self.brains = brains or {}
        self.queue = queue
        self.instinct = None  # lazily set to InstinctBrain to avoid import cost
        self._last_submit: dict[str, int] = {}
```

Add imports at top: `from genesis.mind.brain import InstinctBrain`; `from genesis.mind.queue import DecisionJob`; `from genesis.world.affordances import affordances`; `from genesis.world.goal import resolve_goal`. Set `self.instinct = InstinctBrain()` in `__init__`.

Replace the `if agent.current_action is None and ...:` block in `tick` with:

```python
            if agent.current_action is None and agent.status in ("active", "sleeping"):
                action, extra = self._decide(agent, wm)
                agent.current_action = action
                events += extra
```

Add the method:

```python
    def _decide(self, agent, wm):
        minute = self.state.sim_minutes
        extra = []
        # 1. drive an active goal
        if agent.goal is not None:
            act = resolve_goal(agent, agent.goal, self.state, wm,
                               self.settings, self.graph, self.magic)
            if act is not None:
                return act, extra
            agent.goal = None
        # 2/3. LLM path (only if a brain+queue are wired for this agent)
        brain = self.brains.get(agent.id)
        if self.queue is not None and brain is not None:
            menu = affordances(agent, self.state, wm, self.settings,
                               self.graph, self.magic)
            landed = self._consume(agent, menu, minute, extra)
            if landed is not None:
                return landed, extra
            cooldown = self.settings.get("decision_cooldown_min", 0)
            if (not self.queue.pending(agent.id)
                    and minute - self._last_submit.get(agent.id, -10**9) >= cooldown
                    and menu):
                ctx = self._context(agent, menu)
                self.queue.submit(DecisionJob(agent.id, minute, menu, ctx), brain)
                self._last_submit[agent.id] = minute
                landed = self._consume(agent, menu, minute, extra)  # InlineQueue: ready now
                if landed is not None:
                    return landed, extra
        # 4. instinct meanwhile / fallback
        return self.instinct.act(agent, self.state, wm, self.settings,
                                 self.rng, self.graph, self.magic), extra

    def _consume(self, agent, menu, minute, extra):
        d = self.queue.pop(agent.id)
        if d is None:
            return None
        aff = next((o for o in menu if o["id"] == d["choice"]), None)
        stale = self.settings.get("decision_stale_min", 10**9)
        if aff is None or minute - d["sim_minute"] > stale:
            return None  # stale/invalid -> drop, re-decide later
        agent.goal = aff
        model = getattr(self.brains.get(agent.id), "model", "fake")
        extra.append({"type": "decided", "agent": agent.id, "choice": aff["id"],
                      "reason": d["reason"], "model": model, "minute": minute})
        return resolve_goal(agent, aff, self.state, wm=self.map_for(agent),
                            settings=self.settings, graph=self.graph, magic=self.magic)

    def _context(self, agent, menu):
        return {"persona": agent.persona, "needs": vars(agent.needs),
                "strain": agent.strain, "mana": agent.mana, "mana_max": agent.mana_max,
                "layer": agent.layer, "inventory": dict(agent.inventory),
                "known": list(agent.knowledge), "options": menu}
```

Note: `_consume` calls `resolve_goal` with `wm=self.map_for(agent)`; keep the keyword call as written.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_engine_minds.py -v`
Expected: PASS

- [ ] **Step 5: Run the FULL suite (backward-compat gate)**

Run: `uv run pytest -q`
Expected: all previous tests PASS unchanged, plus the new ones. If any pre-existing test changed behavior, the wiring leaked into the default path — fix so `brains`/`queue` default to the pure-instinct path.

- [ ] **Step 6: Add the fatal-sovereignty, in-flight, and staleness tests**

Write these three (failing-first not applicable — they assert behavior the flow already provides; run them and confirm they pass, then keep as regression guards). If any fails, the flow is wrong — fix the flow, not the test.

```python
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
```

- [ ] **Step 7: Commit**

```bash
git add src/genesis/world/engine.py tests/test_engine_minds.py
git commit -m "Wire async decision flow into the engine (affordance->goal, instinct fallback, sovereign goals)"
```

---

### Task 7: LLMBrain (prompt + validation + retry)

**Files:**
- Create: `src/genesis/mind/llm_brain.py`
- Test: `tests/test_llm_brain.py`

**Interfaces:**
- Consumes: a provider with `.complete(prompt: str, schema: dict) -> dict`.
- Produces: `LLMBrain(provider, model).choose(context, affordances) -> {"choice","reason"}`; retries once on invalid, raises `BrainError` if still invalid.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_llm_brain.py
import pytest
from genesis.mind.llm_brain import LLMBrain
from genesis.mind.brain import BrainError


class StubProvider:
    def __init__(self, replies): self.replies = list(replies); self.calls = 0
    def complete(self, prompt, schema):
        r = self.replies[min(self.calls, len(self.replies) - 1)]; self.calls += 1
        return r


AFFS = [{"id": "eat", "label": "eat", "dir": "here", "dist": 0},
        {"id": "sleep", "label": "sleep", "dir": "here", "dist": 0}]


def test_returns_valid_choice():
    b = LLMBrain(StubProvider([{"choice": "sleep", "reason": "tired"}]), "m")
    assert b.choose({"persona": "lazy"}, AFFS) == {"choice": "sleep", "reason": "tired"}


def test_retries_once_then_succeeds():
    p = StubProvider([{"choice": "fly", "reason": "x"}, {"choice": "eat", "reason": "ok"}])
    b = LLMBrain(p, "m")
    assert b.choose({}, AFFS)["choice"] == "eat"
    assert p.calls == 2


def test_raises_after_two_invalid():
    p = StubProvider([{"choice": "fly"}, {"choice": "swim"}])
    with pytest.raises(BrainError):
        LLMBrain(p, "m").choose({}, AFFS)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_llm_brain.py -v`
Expected: FAIL — `ModuleNotFoundError: genesis.mind.llm_brain`

- [ ] **Step 3: Write minimal implementation**

```python
# src/genesis/mind/llm_brain.py
import json
from genesis.mind.brain import BrainError

_SCHEMA = {"type": "object",
           "properties": {"choice": {"type": "string"}, "reason": {"type": "string"}},
           "required": ["choice", "reason"]}


def _prompt(context: dict, affordances: list[dict]) -> str:
    lines = ["You are an agent in a survival world. Pick ONE option by its id.",
             f"State: {json.dumps(context, default=str)}", "Options:"]
    for a in affordances:
        lines.append(f"- {a['id']}: {a.get('label','')} ({a.get('dir','')}, {a.get('dist','')})")
    lines.append('Reply JSON: {"choice": "<id>", "reason": "<one short line>"}')
    return "\n".join(lines)


class LLMBrain:
    def __init__(self, provider, model: str):
        self.provider = provider
        self.model = model

    def choose(self, context: dict, affordances: list[dict]) -> dict:
        ids = {a["id"] for a in affordances}
        prompt = _prompt(context, affordances)
        for _ in range(2):  # one try + one retry
            try:
                out = self.provider.complete(prompt, _SCHEMA)
            except Exception:
                out = None
            if isinstance(out, dict) and out.get("choice") in ids:
                return {"choice": out["choice"], "reason": out.get("reason", "")}
        raise BrainError("no valid choice after retry")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_llm_brain.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/genesis/mind/llm_brain.py tests/test_llm_brain.py
git commit -m "Add LLMBrain: prompt build, choice validation, one retry"
```

---

### Task 8: GroqAdapter (stdlib HTTP, mocked in tests)

**Files:**
- Create: `src/genesis/mind/groq.py`
- Test: `tests/test_groq.py`

**Interfaces:**
- Produces: `GroqAdapter(model, api_key=None).complete(prompt, schema) -> dict`. Reads `GROQ_API_KEY` from env if `api_key` is None. Missing key raises `BrainError`. Uses `urllib.request` to POST to Groq's OpenAI-compatible chat endpoint; parses the JSON content of the first choice. **No test hits the network** — patch `_http_post`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_groq.py
import pytest
from genesis.mind import groq as G
from genesis.mind.brain import BrainError


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(BrainError):
        G.GroqAdapter("llama-3.3-70b-versatile").complete("hi", {})


def test_parses_json_content(monkeypatch):
    # patch the HTTP layer so no network call happens
    monkeypatch.setattr(G, "_http_post",
                        lambda url, headers, body: {
                            "choices": [{"message": {"content": '{"choice":"eat","reason":"hungry"}'}}]})
    out = G.GroqAdapter("m", api_key="k").complete("prompt", {})
    assert out == {"choice": "eat", "reason": "hungry"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_groq.py -v`
Expected: FAIL — `ModuleNotFoundError: genesis.mind.groq`

- [ ] **Step 3: Write minimal implementation**

```python
# src/genesis/mind/groq.py
import json
import os
import urllib.request
from genesis.mind.brain import BrainError

_URL = "https://api.groq.com/openai/v1/chat/completions"


def _http_post(url: str, headers: dict, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


class GroqAdapter:
    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")

    def complete(self, prompt: str, schema: dict) -> dict:
        if not self.api_key:
            raise BrainError("GROQ_API_KEY not set")
        body = {"model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.7, "max_tokens": 120}
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        data = _http_post(_URL, headers, body)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_groq.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/genesis/mind/groq.py tests/test_groq.py
git commit -m "Add GroqAdapter over stdlib urllib (no new dependency)"
```

---

### Task 9: ThreadedThinkQueue + daily-budget guard

**Files:**
- Modify: `src/genesis/mind/queue.py`
- Test: `tests/test_queue.py`

**Interfaces:**
- Produces: `ThreadedThinkQueue(daily_budget: int)` with `submit/pending/pop` and `requests_today: int`. A worker thread pops jobs, calls `brain.choose`, stores results in a thread-safe inbox. At/over `daily_budget`, `submit` is a no-op (agent rides instinct) and increments nothing.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_queue.py  (add)
import threading
from genesis.mind.queue import ThreadedThinkQueue


def test_threaded_queue_delivers_result():
    q = ThreadedThinkQueue(daily_budget=100)
    from genesis.mind.brain import FakeBrain
    q.submit(_job(), FakeBrain(lambda c, a: {"choice": "eat", "reason": "r"}))
    done = q.wait_idle(timeout=2.0)   # test helper: block until worker drains
    assert done
    assert q.pop("a")["choice"] == "eat"


def test_threaded_queue_stops_submitting_at_budget():
    q = ThreadedThinkQueue(daily_budget=0)
    from genesis.mind.brain import FakeBrain
    q.submit(_job(), FakeBrain(lambda c, a: {"choice": "eat", "reason": "r"}))
    q.wait_idle(timeout=1.0)
    assert q.pop("a") is None          # nothing was processed
    assert q.requests_today == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_queue.py::test_threaded_queue_delivers_result -v`
Expected: FAIL — `ImportError: cannot import name 'ThreadedThinkQueue'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/genesis/mind/queue.py  (add)
import queue as _q
import threading


class ThreadedThinkQueue:
    def __init__(self, daily_budget: int):
        self.daily_budget = daily_budget
        self.requests_today = 0
        self._jobs: _q.Queue = _q.Queue()
        self._inbox: dict[str, dict] = {}
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def submit(self, job: DecisionJob, brain) -> None:
        with self._lock:
            if self.requests_today >= self.daily_budget:
                return  # budget spent -> agent rides instinct
            self.requests_today += 1
            self._pending.add(job.agent_id)
        self._jobs.put((job, brain))

    def _run(self):
        while True:
            job, brain = self._jobs.get()
            result = _resolve(job, brain)
            with self._lock:
                self._pending.discard(job.agent_id)
                if result is not None:
                    self._inbox[job.agent_id] = result
            self._jobs.task_done()

    def pending(self, agent_id: str) -> bool:
        with self._lock:
            return agent_id in self._pending

    def pop(self, agent_id: str) -> dict | None:
        with self._lock:
            return self._inbox.pop(agent_id, None)

    def wait_idle(self, timeout: float = 2.0) -> bool:
        # test helper: block until the job queue drains
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._jobs.unfinished_tasks == 0:
                return True
            time.sleep(0.01)
        return False
```

Note: `wait_idle` uses `time.monotonic`, which is allowed (it is not `Date.now`-style non-determinism in Python; it only gates a test timeout and never feeds sim state).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_queue.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/genesis/mind/queue.py tests/test_queue.py
git commit -m "Add ThreadedThinkQueue with a daily-request budget guard"
```

---

### Task 10: Config wiring, `--minds`, and Instinct-only fast-forward

**Files:**
- Create: `configs/brains.json`, `.env.example`
- Modify: `configs/settings.json`, `src/genesis/world/engine.py` (`from_configs`), `src/genesis/cli.py`
- Test: `tests/test_minds_config.py`

**Interfaces:**
- Consumes: `GroqAdapter` (T8), `LLMBrain` (T7), `ThreadedThinkQueue` (T9).
- Produces: `Engine.from_configs(config_dir, seed, sim_minutes, minds=False)`. When `minds=True`, builds `{agent.id: LLMBrain(GroqAdapter(model), model)}` from `brains.json` mapped through `agent.brain`, plus a `ThreadedThinkQueue(daily_budget)`. When `minds=False` (default), no brains/queue — the pure-instinct path (all existing tests, incl. `test_cli.py`, unaffected).

- [ ] **Step 1: Add the three settings keys**

In `configs/settings.json` add (after `mana_regen_sleeping_per_min`):

```json
  "decision_cooldown_min": 30,
  "decision_stale_min": 20,
  "daily_request_budget": 900
```

- [ ] **Step 2: Create config files**

`configs/brains.json`:
```json
{ "brains": { "default": { "provider": "groq", "model": "llama-3.3-70b-versatile" } } }
```

`.env.example`:
```
GROQ_API_KEY=your-key-here
```

Confirm `.env` is gitignored:
Run: `grep -q '^\.env$' .gitignore || echo '.env' >> .gitignore`

- [ ] **Step 3: Write the failing test**

```python
# tests/test_minds_config.py
from genesis.world.engine import Engine


def test_from_configs_without_minds_has_no_brains():
    eng = Engine.from_configs("configs")
    assert eng.brains == {} and eng.queue is None


def test_from_configs_with_minds_wires_a_brain_per_agent(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    eng = Engine.from_configs("configs", minds=True)
    assert eng.queue is not None
    assert len(eng.brains) == len(eng.state.agents)
    for b in eng.brains.values():
        assert b.model == "llama-3.3-70b-versatile"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_minds_config.py -v`
Expected: FAIL — `from_configs() got an unexpected keyword argument 'minds'`

- [ ] **Step 5: Implement `minds=` in `from_configs`**

Add parameter `minds: bool = False`. Before `return cls(...)`, when `minds`:

```python
        brains, queue = {}, None
        if minds:
            from genesis.mind.groq import GroqAdapter
            from genesis.mind.llm_brain import LLMBrain
            from genesis.mind.queue import ThreadedThinkQueue
            cfg = json.loads((config_dir / "brains.json").read_text(encoding="utf-8"))["brains"]
            for ag in state.agents:
                spec = cfg.get(ag.brain) or cfg["default"]
                brains[ag.id] = LLMBrain(GroqAdapter(spec["model"]), spec["model"])
            queue = ThreadedThinkQueue(settings.get("daily_request_budget", 900))
        return cls(state, settings=settings, maps=maps, magic=magic, graph=graph,
                   brains=brains, queue=queue)
```

- [ ] **Step 6: Add `--minds` to the CLI**

In `cli.py`, add an argparse flag `--minds` (store_true) and pass it to `Engine.from_configs(..., minds=args.minds)`.

- [ ] **Step 7: Enforce Instinct-only fast-forward (ADR 0001)**

Fast-forward/catch-up must never submit LLM jobs. Add a guard: `Engine.advance` gets an optional `live: bool = True`; the CLI/catch-up path calls `advance(minutes, live=False)`, and in `_decide` skip the LLM branch when `not self._live` (set `self._live` at the start of `advance`). Write this test first:

```python
# tests/test_minds_config.py  (add)
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
```

Then implement the `live` flag (default `True` so existing `advance` calls are unaffected).

- [ ] **Step 8: Run tests + full suite**

Run: `uv run pytest -q`
Expected: all green (119 existing + all new).

- [ ] **Step 9: Commit**

```bash
git add configs/ .env.example .gitignore src/genesis/world/engine.py src/genesis/cli.py tests/test_minds_config.py
git commit -m "Wire LLM minds config, --minds flag, and Instinct-only catch-up (ADR 0001)"
```

---

## Self-Review

**Spec coverage:**
- §3 affordance→Goal→Action → Tasks 2, 3, 6 ✓
- §3 decision flow (drive/consume/submit/instinct), staleness, dedup → Task 6 ✓
- §3 Goals sovereign / fatal choices → Task 6 Step 6 test ✓
- §4 Brain seam (InstinctBrain/FakeBrain/LLMBrain/GroqAdapter, retry→fallback, no-key→instinct) → Tasks 4, 7, 8 (no-key raises BrainError → engine falls to instinct because `LLMBrain.choose` raising is caught in `_resolve` → returns None → instinct) ✓
- §5 ThinkQueue (Inline + Threaded, budget guard, inbox) → Tasks 5, 9 ✓
- §6 free-tier rules: cooldown (T6/T10), daily budget (T9/T10), Instinct-only fast-forward (T10 Step 7) ✓
- §7 config/enablement, opt-in, backward-compat → Tasks 6, 10 ✓
- §8 `decided` event → Task 6 ✓
- §9 testing incl. network-free → every task mocks/fakes; no real HTTP ✓

**Placeholder scan:** every code step has real code; the only prose-only expansions (T2 Step 5, T3 Step 5) enumerate concrete branches with exact conditions and repeat the shapes. No TBD/TODO. ✓

**Type consistency:** `affordances()` item shape (`id/verb/params/label/dir/dist`) is identical across T2, T3, T6, T7. `pop()` result (`choice/reason/sim_minute`) identical across T5, T6, T9. `brain.choose(context, affordances)` and `InstinctBrain.act(...)` signatures identical across T4, T5, T6, T7. `Engine.__init__(..., brains, queue)` and `from_configs(..., minds)` consistent T6/T10. ✓

---

## Execution note

Tasks 1–6 deliver a fully working, deterministic LLM-driven engine using `FakeBrain` + `InlineQueue` — worth verifying end-to-end before Tasks 7–10 add the real Groq path. The full suite must be green after every task, and no test may hit the network.
