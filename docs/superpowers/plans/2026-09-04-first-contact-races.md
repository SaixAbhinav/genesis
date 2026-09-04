# First Contact: Perception-Only Race Experiment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give agents a race identity and the ability to perceive one another, spawn two races apart on a dedicated scenario, and make first contact with another race a Brain-driven, observable moment — without any scripted inter-race behavior or new action verbs.

**Architecture:** A pure `perceive_agents` helper surfaces nearby agents (and race) into the Brain context and into `approach`/`avoid` *goal* affordances that resolve to the existing `move_to` action, tracking a moving target each tick. The engine detects first contact in its per-tick loop (so a busy agent is preempted too), clears the agent's goal/action, and forces a fresh Brain decision. A `scenario_dir` loads a self-contained first-contact world (map + agents + races) while reusing the shared rule configs.

**Tech Stack:** Python 3, `uv` for env/test (`uv run pytest`), JSON config. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-04-first-contact-races-design.md`

## Global Constraints

- **No new *action* verbs.** `approach`/`avoid` are goal/affordance verbs that resolve to the existing `move_to` action; `VERBS` in `actions.py` is not touched.
- **Nothing about how races treat each other is scripted.** Instinct never chooses `approach`/`avoid`; the LLM decides freely.
- **Determinism:** same seed + same config ⇒ identical outcomes on the non-LLM path. All iteration over agents is `sorted()` where order is observable; no randomness added.
- **No new dependencies.** Standard library only.
- **Back-compat:** `race` defaults to `""` and `warmth_decay_mult` to `1.0`; agents without a race never trigger contact and behave exactly as today.
- **Style:** match existing code — 4-space indent, `snake_case`, type hints as in neighbouring files, no docstrings unless the surrounding file has them. Minimal diffs.
- **Tests:** `uv run pytest` green after every task. Never weaken a test to pass.
- **Git:** never commit to `main`; feature branch `feat/first-contact-races`. No Claude/Anthropic attribution in any commit message.

---

## Task 1: Agent race identity + warmth trait

**Files:**
- Modify: `src/genesis/world/state.py` (add two `Agent` fields)
- Modify: `src/genesis/world/needs.py` (apply `warmth_decay_mult` in night decay)
- Test: `tests/test_race_trait.py`

**Interfaces:**
- Produces: `Agent.race: str = ""`, `Agent.warmth_decay_mult: float = 1.0`. `tick_needs` night-decay rate is multiplied by `agent.warmth_decay_mult`.

- [ ] **Step 1: Write the failing test** — `tests/test_race_trait.py`

```python
from genesis import load_settings
from genesis.world.state import Agent
from genesis.world.needs import tick_needs

S = load_settings("configs/settings.json")
MIDNIGHT = 0


def _warmth_loss(mult):
    a = Agent(id="a", name="A", x=0, y=0, warmth_decay_mult=mult)
    a.needs.warmth = 50.0
    tick_needs(a, MIDNIGHT, S, near_warmth=False)
    return 50.0 - a.needs.warmth


def test_default_race_and_mult():
    a = Agent(id="a", name="A", x=0, y=0)
    assert a.race == "" and a.warmth_decay_mult == 1.0


def test_warmth_trait_scales_night_decay():
    base = _warmth_loss(1.0)
    hardy = _warmth_loss(0.6)
    assert base > 0
    assert abs(hardy - base * 0.6) < 1e-9
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_race_trait.py -v`
Expected: FAIL (`Agent.__init__` has no `warmth_decay_mult`).

- [ ] **Step 3: Add the fields** — in `src/genesis/world/state.py`, append to the `Agent` dataclass after `negate_fall_until: int = 0`:

```python
    # First-contact races
    race: str = ""
    warmth_decay_mult: float = 1.0
```

- [ ] **Step 4: Apply the multiplier** — in `src/genesis/world/needs.py`, in the final `else:` night-decay branch, multiply the rate. It currently reads (after the Task-7 insulation change from the property plan):

```python
    else:
        rate = (settings["warmth_decay_night_sleeping_per_min"]
                if agent.status == "sleeping"
                else settings["warmth_decay_night_per_min"])
        if props_of is not None and any(
                "insulating" in props_of(it)
                for it, q in agent.inventory.items() if q > 0):
            rate *= settings.get("insulation_warmth_factor", 1.0)
        n.warmth = _clamp(n.warmth - rate)
```

Insert the race multiplier immediately before `n.warmth = _clamp(...)`:

```python
        rate *= agent.warmth_decay_mult
        n.warmth = _clamp(n.warmth - rate)
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_race_trait.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Full suite**

Run: `uv run pytest -q`
Expected: all green (default `1.0` leaves existing warmth tests unchanged).

- [ ] **Step 7: Commit**

```bash
git add src/genesis/world/state.py src/genesis/world/needs.py tests/test_race_trait.py
git commit -m "Add Agent race + warmth_decay_mult trait"
```

---

## Task 2: perceive_agents

**Files:**
- Create: `src/genesis/world/perception.py`
- Test: `tests/test_perception.py`

**Interfaces:**
- Produces: `perceive_agents(agent, state, radius) -> list[dict]` — every OTHER living agent on the same layer within Manhattan `radius`, each `{"name", "race", "dir", "dist"}`, sorted by `(dist, name)`. Excludes self and dead agents.

- [ ] **Step 1: Write the failing test** — `tests/test_perception.py`

```python
from genesis.world.perception import perceive_agents
from genesis.world.state import Agent, WorldState


def _mk(name, x, y, race="", status="active", layer=0):
    return Agent(id=name, name=name, x=x, y=y, race=race, status=status, layer=layer)


def test_perceives_nearby_sorted_by_dist_then_name():
    a = _mk("A", 5, 5, race="ashfolk")
    near = _mk("Near", 6, 5, race="mosskin")
    far = _mk("Far", 5, 9, race="mosskin")
    st = WorldState(0, 1, [a, far, near])
    seen = perceive_agents(a, st, radius=6)
    assert [s["name"] for s in seen] == ["Near", "Far"]
    assert seen[0]["race"] == "mosskin" and seen[0]["dist"] == 1
    assert seen[0]["dir"] == "E"


def test_excludes_self_dead_other_layer_and_out_of_range():
    a = _mk("A", 0, 0)
    dead = _mk("D", 1, 0, status="dead")
    below = _mk("B", 1, 0, layer=1)
    away = _mk("F", 20, 20)
    st = WorldState(0, 1, [a, dead, below, away])
    assert perceive_agents(a, st, radius=6) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_perception.py -v`
Expected: FAIL (`ModuleNotFoundError: genesis.world.perception`).

- [ ] **Step 3: Write `src/genesis/world/perception.py`**

```python
def _bearing(dx: int, dy: int) -> str:
    ns = ("N" if dy < 0 else "S" if dy > 0 else "")
    ew = ("W" if dx < 0 else "E" if dx > 0 else "")
    return (ns + ew) or "here"


def perceive_agents(agent, state, radius: int) -> list[dict]:
    out = []
    for other in state.agents:
        if other.id == agent.id or other.status == "dead" \
                or other.layer != agent.layer:
            continue
        dist = abs(other.x - agent.x) + abs(other.y - agent.y)
        if dist <= radius:
            out.append({"name": other.name, "race": other.race,
                        "dir": _bearing(other.x - agent.x, other.y - agent.y),
                        "dist": dist})
    out.sort(key=lambda o: (o["dist"], o["name"]))
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_perception.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/perception.py tests/test_perception.py
git commit -m "Add perceive_agents helper"
```

---

## Task 3: approach / avoid affordances

**Files:**
- Modify: `src/genesis/world/affordances.py`
- Test: `tests/test_affordances_social.py`

**Interfaces:**
- Consumes: `perceive_agents` (Task 2); `settings["perception_radius"]` (default 6), `settings["perception_affordance_cap"]` (default 3).
- Produces: for the nearest ≤cap perceived agents, two options with `verb` `"approach"`/`"avoid"`, `id` `"approach:<name>"`/`"avoid:<name>"`, `params={"target": "<name>"}`, and a label naming the other's race + direction.

- [ ] **Step 1: Write the failing test** — `tests/test_affordances_social.py`

```python
from genesis.world.affordances import affordances
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GGGGGGGG"] * 8)
S = {"perception_radius": 6, "perception_affordance_cap": 3}


def _mk(name, x, y, race=""):
    return Agent(id=name, name=name, x=x, y=y, race=race)


def test_offers_approach_and_avoid_for_perceived_agent():
    a = _mk("A", 1, 1, race="ashfolk")
    b = _mk("B", 3, 1, race="mosskin")
    opts = affordances(a, WorldState(0, 1, [a, b]), WM, S)
    ids = {o["id"] for o in opts}
    assert "approach:B" in ids and "avoid:B" in ids
    ap = next(o for o in opts if o["id"] == "approach:B")
    assert ap["verb"] == "approach" and ap["params"] == {"target": "B"}
    assert "mosskin" in ap["label"] and "E" in ap["label"]


def test_no_social_options_when_alone():
    a = _mk("A", 1, 1, race="ashfolk")
    opts = affordances(a, WorldState(0, 1, [a]), WM, S)
    assert not any(o["verb"] in ("approach", "avoid") for o in opts)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_affordances_social.py -v`
Expected: FAIL (no approach/avoid options emitted).

- [ ] **Step 3: Edit `src/genesis/world/affordances.py`**

Add the import at the top, next to the existing imports:

```python
from genesis.world.perception import perceive_agents
```

Insert this block just before the final `# sleep and observe are always available` block:

```python
    # social: approach/avoid perceived agents — resolve to move_to (no new action verb)
    radius = settings.get("perception_radius", 6) if settings else 6
    cap = settings.get("perception_affordance_cap", 3) if settings else 3
    for other in perceive_agents(agent, state, radius)[:cap]:
        who = f"the {other['race']} " if other["race"] else ""
        opts.append({"id": f"approach:{other['name']}", "verb": "approach",
                     "params": {"target": other["name"]},
                     "label": f"approach {who}{other['name']} to the {other['dir']}",
                     "dir": other["dir"], "dist": other["dist"]})
        opts.append({"id": f"avoid:{other['name']}", "verb": "avoid",
                     "params": {"target": other["name"]},
                     "label": f"move away from {who}{other['name']} to the {other['dir']}",
                     "dir": other["dir"], "dist": other["dist"]})
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_affordances_social.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Full suite**

Run: `uv run pytest -q`
Expected: all green. Existing `test_affordances*` use single-agent states, so no social options appear and their assertions are unaffected.

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/affordances.py tests/test_affordances_social.py
git commit -m "Offer approach/avoid affordances for perceived agents"
```

---

## Task 4: resolve_goal approach / avoid (moving-target tracking)

**Files:**
- Modify: `src/genesis/world/goal.py`
- Test: `tests/test_goal_social.py`

**Interfaces:**
- Consumes: `settings["perception_radius"]`; `agent.layer`, `state.agents`.
- Produces: `resolve_goal` handles `verb` `"approach"`/`"avoid"` with `params={"target": name}` — returns a `move_to` action toward / one step away from the target's *current* tile, or `None` when the goal is complete (approach: adjacent; avoid: target beyond radius) or the target is gone/dead/on another layer.

- [ ] **Step 1: Write the failing test** — `tests/test_goal_social.py`

```python
from genesis.world.goal import resolve_goal
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GGGGGGGG"] * 8)
S = {"perception_radius": 6}


def _mk(name, x, y, status="active", layer=0):
    return Agent(id=name, name=name, x=x, y=y, status=status, layer=layer)


def test_approach_moves_toward_live_target_then_ends_on_adjacency():
    a = _mk("A", 1, 1)
    b = _mk("B", 4, 1)
    st = WorldState(0, 1, [a, b])
    goal = {"verb": "approach", "params": {"target": "B"}}
    act = resolve_goal(a, goal, st, WM, S)
    assert act["action"] == "move_to" and (act["x"], act["y"]) != (1, 1)
    # target adjacent -> goal complete
    a.x, a.y = 3, 1
    assert resolve_goal(a, goal, st, WM, S) is None


def test_avoid_steps_away_then_ends_when_out_of_range():
    a = _mk("A", 4, 4)
    b = _mk("B", 5, 4)
    st = WorldState(0, 1, [a, b])
    goal = {"verb": "avoid", "params": {"target": "B"}}
    act = resolve_goal(a, goal, st, WM, S)
    assert act["action"] == "move_to" and act["x"] <= 4   # moved away from B (east)
    b.x, b.y = 40, 40                                       # now far
    assert resolve_goal(a, goal, st, WM, S) is None


def test_approach_ends_if_target_gone_or_dead():
    a = _mk("A", 1, 1)
    b = _mk("B", 3, 1, status="dead")
    st = WorldState(0, 1, [a, b])
    assert resolve_goal(a, {"verb": "approach", "params": {"target": "B"}},
                        st, WM, S) is None
    assert resolve_goal(a, {"verb": "avoid", "params": {"target": "Ghost"}},
                        st, WM, S) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_goal_social.py -v`
Expected: FAIL (`resolve_goal` returns `None` for unknown verbs, so the first assertion — expecting a `move_to` — fails).

- [ ] **Step 3: Edit `src/genesis/world/goal.py`**

Add two module-level helpers after `_move_toward`:

```python
def _agent_by_name(state, name):
    return next((a for a in state.agents if a.name == name), None)


def _move_away(agent, x, y, world_map):
    dx = 0 if agent.x == x else (1 if agent.x > x else -1)
    dy = 0 if agent.y == y else (1 if agent.y > y else -1)
    for tx, ty in ((agent.x + dx, agent.y + dy),
                   (agent.x + dx, agent.y), (agent.x, agent.y + dy)):
        if (tx, ty) != (agent.x, agent.y) and world_map.walkable(tx, ty):
            return {"action": "move_to", "x": tx, "y": ty}
    return None
```

Add this branch inside `resolve_goal`, before the final `return None`:

```python
    if verb in ("approach", "avoid"):
        radius = settings.get("perception_radius", 6)
        target = _agent_by_name(state, p["target"])
        if target is None or target.status == "dead" \
                or target.layer != agent.layer:
            return None
        if abs(target.x - agent.x) + abs(target.y - agent.y) > radius:
            return None
        if verb == "approach":
            if _adjacent(agent, target.x, target.y, world_map):
                return None
            return _move_toward(agent, target.x, target.y, world_map)
        return _move_away(agent, target.x, target.y, world_map)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_goal_social.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Full suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/goal.py tests/test_goal_social.py
git commit -m "Resolve approach/avoid goals against a moving target"
```

---

## Task 5: Engine — perception context + first-contact preemption

Detect first contact in the per-tick loop (so an agent mid-action is preempted too), clear its goal/action, emit a `contact` event, and force a fresh Brain decision that bypasses the cooldown. Add `race` + `nearby` to the Brain context.

**Files:**
- Modify: `src/genesis/world/engine.py`
- Test: `tests/test_contact.py`

**Interfaces:**
- Consumes: `perceive_agents` (Task 2); `settings["perception_radius"]`.
- Produces: `Engine._contacted: dict[str, set[str]]`, `Engine._force_decide: set[str]`; a `{"type":"contact","agent","race","other","minute"}` event on first perception of a foreign race; `_context` gains `"race"` and `"nearby"` keys.

- [ ] **Step 1: Write the failing test** — `tests/test_contact.py`

```python
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
    # both always choose to observe; cooldown is huge, so only a forced
    # (contact) decision can produce a 'decided' event on tick 0.
    eng = _engine([a, b], lambda c, affs: {"choice": "observe", "reason": "watch"})
    events = eng.tick()
    contacts = [e for e in events if e["type"] == "contact"]
    assert {c["race"] for c in contacts} == {"ashfolk", "mosskin"}
    assert any(e["type"] == "decided" for e in events)   # cooldown bypassed


def test_contact_context_has_nearby_and_race():
    a = Agent(id="a", name="Ash", x=1, y=1, race="ashfolk", brain="fake")
    b = Agent(id="b", name="Moss", x=3, y=1, race="mosskin", brain="fake")
    seen = {}

    def chooser(ctx, affs):
        seen.update(ctx)
        return {"choice": "observe", "reason": "watch"}

    _engine([a, b], chooser).tick()
    assert seen["race"] == "ashfolk"
    assert any(n["name"] == "Moss" and n["race"] == "mosskin"
               for n in seen["nearby"])


def test_contact_fires_once_per_race():
    a = Agent(id="a", name="Ash", x=1, y=1, race="ashfolk", brain="fake")
    b = Agent(id="b", name="Moss", x=3, y=1, race="mosskin", brain="fake")
    eng = _engine([a, b], lambda c, affs: {"choice": "observe", "reason": "watch"})
    eng.tick()
    later = eng.tick()
    assert not any(e["type"] == "contact" for e in later)


def test_no_contact_between_same_or_raceless_agents():
    a = Agent(id="a", name="A", x=1, y=1, brain="fake")           # race ""
    b = Agent(id="b", name="B", x=3, y=1, brain="fake")           # race ""
    eng = _engine([a, b], lambda c, affs: {"choice": "observe", "reason": "watch"})
    assert not any(e["type"] == "contact" for e in eng.tick())
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_contact.py -v`
Expected: FAIL (no `contact` events; `_context` has no `race`/`nearby`).

- [ ] **Step 3: Initialise state in `Engine.__init__`** — in `src/genesis/world/engine.py`, add after `self._last_submit: dict[str, int] = {}`:

```python
        self._contacted: dict[str, set] = {}
        self._force_decide: set = set()
```

Add the import near the other `genesis.world` imports:

```python
from genesis.world.perception import perceive_agents
```

- [ ] **Step 4: Add the contact check and wire it into `tick`** — add this method to `Engine`:

```python
    def _contact_check(self, agent, minute) -> list[dict]:
        # First perception of a foreign race preempts the agent and marks it for
        # a forced decision. Live sim only (never ADR-0001 catch-up); only raced
        # agents make contact. A Brain is NOT required to EMIT the event (so the
        # deterministic path is testable) — only to react to it (see _decide).
        if not self._live or not agent.race:
            return []
        radius = self.settings.get("perception_radius", 6)
        seen = self._contacted.setdefault(agent.id, set())
        events = []
        for other in perceive_agents(agent, self.state, radius):
            r = other["race"]
            if r and r != agent.race and r not in seen:
                seen.add(r)
                events.append({"type": "contact", "agent": agent.id, "race": r,
                               "other": other["name"], "minute": minute})
        if events:
            agent.goal = None
            agent.current_action = None
            self._force_decide.add(agent.id)
        return events
```

In `tick`, call it before the decision gate. The current loop body is:

```python
            if agent.current_action is None and agent.status in ("active", "sleeping"):
                action, extra = self._decide(agent, wm)
                agent.current_action = action
                events += extra
```

Change it to:

```python
            events += self._contact_check(agent, minute)
            if agent.current_action is None and agent.status in ("active", "sleeping"):
                action, extra = self._decide(agent, wm)
                agent.current_action = action
                events += extra
```

- [ ] **Step 5: Honour the forced decision in `_decide`** — three edits.

**(a)** Pop the `forced` flag at the very top of `_decide`, right after `extra: list[dict] = []`:

```python
        forced = agent.id in self._force_decide
        self._force_decide.discard(agent.id)
```

(This always clears the flag — even on the Instinct-only path where the LLM block below is skipped — so it can't leak to a later tick.)

**(b)** In the LLM block, the stale-pending pop must be ignored when forced. Change:

```python
            landed = self._consume(agent, wm, menu, minute, extra)
            if landed is not None:
                return landed, extra
```

to:

```python
            landed = self._consume(agent, wm, menu, minute, extra)
            if landed is not None and not forced:
                return landed, extra
```

**(c)** The submit gate bypasses pending + cooldown when forced. Change:

```python
            cooldown = self.settings.get("decision_cooldown_min", 0)
            if (not self.queue.pending(agent.id)
                    and minute - self._last_submit.get(agent.id, -10**9) >= cooldown
                    and menu):
```

to:

```python
            cooldown = self.settings.get("decision_cooldown_min", 0)
            ready = (not self.queue.pending(agent.id)
                     and minute - self._last_submit.get(agent.id, -10**9) >= cooldown)
            if (forced or ready) and menu:
```

- [ ] **Step 6: Add `race` + `nearby` to the context** — replace the `_context` return in `src/genesis/world/engine.py`:

```python
    def _context(self, agent, menu):
        radius = self.settings.get("perception_radius", 6)
        return {"persona": agent.persona, "needs": vars(agent.needs),
                "strain": agent.strain, "mana": agent.mana, "mana_max": agent.mana_max,
                "layer": agent.layer, "inventory": dict(agent.inventory),
                "materials": {it: sorted(self.props.props_of(it))
                              for it in agent.inventory if agent.inventory[it] > 0},
                "race": agent.race,
                "nearby": perceive_agents(agent, self.state, radius),
                "known": list(agent.knowledge), "options": menu}
```

- [ ] **Step 7: Run to verify it passes**

Run: `uv run pytest tests/test_contact.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Full suite**

Run: `uv run pytest -q`
Expected: all green. Existing multi-agent engine tests use raceless agents, so `_contact_check` returns `[]` and nothing changes. If `test_engine_minds.py` / `test_cli.py` assert an exact affordance/context shape and now see the additive `race`/`nearby` keys, update those assertions to the enriched shape (behavior intentionally additive) — never delete the new keys.

- [ ] **Step 9: Commit**

```bash
git add src/genesis/world/engine.py tests/test_contact.py
git commit -m "Detect first contact, preempt the agent, and force a Brain decision"
```

---

## Task 6: Scenario loading + race application + `--scenario` flag + scenario configs

Load a self-contained first-contact world (map + agents + races) via `scenario_dir`, reusing the shared rule configs, and apply each race's starting knowledge/inventory/trait/persona.

**Files:**
- Create: `configs/scenarios/first-contact/races.json`
- Create: `configs/scenarios/first-contact/agents.json`
- Create: `configs/scenarios/first-contact/layers.json`
- Create: `configs/scenarios/first-contact/maps/contact.json`
- Modify: `src/genesis/world/engine.py` (`from_configs` gains `scenario_dir`; apply races)
- Modify: `src/genesis/cli.py` (`--scenario` flag through `run_sim`)
- Test: `tests/test_scenario_load.py`

**Interfaces:**
- Consumes: existing `from_configs` loaders; `races.json` schema `{races: {id: {name, blurb, starting_knowledge, starting_inventory, traits}}}`.
- Produces: `Engine.from_configs(config_dir="configs", seed=..., sim_minutes=..., minds=..., threaded=..., scenario_dir=None)`. When `scenario_dir` is set, `layers.json`/maps, `agents.json`, and `races.json` come from it; shared rule configs from `config_dir`; each agent's race config is applied. `run_sim(..., scenario=None)` and a `--scenario` CLI flag.

- [ ] **Step 1: Write `configs/scenarios/first-contact/races.json`**

```json
{
  "races": {
    "ashfolk": {
      "name": "Ashfolk",
      "blurb": "You are of the Ashfolk, people of ember and warmth.",
      "starting_knowledge": ["fire"],
      "starting_inventory": {"flint": 1},
      "traits": {"warmth_decay_mult": 0.6}
    },
    "mosskin": {
      "name": "Mosskin",
      "blurb": "You are of the Mosskin, who dwell among the damp forests.",
      "starting_knowledge": [],
      "starting_inventory": {"thick_moss": 1},
      "traits": {}
    }
  }
}
```

- [ ] **Step 2: Write the map** — `configs/scenarios/first-contact/maps/contact.json`. A 21×9 all-grass field (walkable) so movement and convergence are unobstructed; two Ashfolk spawn west, two Mosskin east, berries in the centre. Terrain kept uniform `G` for v1 (biome flavour is carried by resource placement, not terrain gating).

Note: `WorldMap.from_file` reads the `"rows"` key (a list of equal-length strings), and `walkable` is true for every terrain except `water`; all-`G` (grass) is fully walkable. `water` here is a *resource* at (10,7); the terrain under it stays `G`.

```json
{
  "rows": [
    "GGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGGG"
  ],
  "resources": [
    {"type": "ember_dust", "x": 1, "y": 4, "qty": 10},
    {"type": "flint", "x": 2, "y": 2, "qty": 10},
    {"type": "wood", "x": 1, "y": 6, "qty": 20},
    {"type": "thick_moss", "x": 19, "y": 4, "qty": 10},
    {"type": "arcane_moss", "x": 18, "y": 2, "qty": 10},
    {"type": "wood", "x": 19, "y": 6, "qty": 20},
    {"type": "berries", "x": 10, "y": 3, "qty": 40},
    {"type": "berries", "x": 10, "y": 5, "qty": 40},
    {"type": "water", "x": 10, "y": 7, "qty": 9999}
  ]
}
```

- [ ] **Step 3: Write `configs/scenarios/first-contact/layers.json`** (single layer, no link, mild curse-free surface):

```json
{
  "layers": [
    {"name": "meadow", "map": "maps/contact.json", "link": {}}
  ]
}
```

- [ ] **Step 4: Write `configs/scenarios/first-contact/agents.json`** (2 per race, spawned apart):

```json
{
  "agents": [
    {"id": "ash1", "name": "Ash", "x": 1, "y": 3, "race": "ashfolk", "brain": "default",
     "persona": "curious and cautious"},
    {"id": "ash2", "name": "Ember", "x": 2, "y": 5, "race": "ashfolk", "brain": "default",
     "persona": "bold and forthright"},
    {"id": "moss1", "name": "Fern", "x": 19, "y": 3, "race": "mosskin", "brain": "default",
     "persona": "wary of strangers"},
    {"id": "moss2", "name": "Bram", "x": 18, "y": 5, "race": "mosskin", "brain": "default",
     "persona": "friendly and open"}
  ]
}
```

- [ ] **Step 5: Write the failing test** — `tests/test_scenario_load.py`

```python
from genesis.world.engine import Engine

SC = "configs/scenarios/first-contact"


def test_scenario_loads_races_and_applies_traits():
    eng = Engine.from_configs("configs", scenario_dir=SC, seed=1, sim_minutes=0)
    by_name = {a.name: a for a in eng.state.agents}
    assert len(eng.state.agents) == 4
    ash = by_name["Ash"]
    assert ash.race == "ashfolk"
    assert "fire" in ash.knowledge                     # starting_knowledge
    assert ash.inventory.get("flint", 0) == 1          # starting_inventory
    assert ash.warmth_decay_mult == 0.6                # trait
    assert ash.persona.startswith("You are of the Ashfolk")   # blurb prepended
    fern = by_name["Fern"]
    assert fern.race == "mosskin" and fern.warmth_decay_mult == 1.0
    assert fern.inventory.get("thick_moss", 0) == 1


def test_scenario_is_single_layer_meadow():
    eng = Engine.from_configs("configs", scenario_dir=SC, seed=1, sim_minutes=0)
    assert len(eng.maps) == 1
    assert len(eng.settings["layers"]) == 1
```

- [ ] **Step 6: Run to verify it fails**

Run: `uv run pytest tests/test_scenario_load.py -v`
Expected: FAIL (`from_configs` has no `scenario_dir`).

- [ ] **Step 7: Edit `Engine.from_configs`** — in `src/genesis/world/engine.py`.

Change the signature:

```python
    @classmethod
    def from_configs(cls, config_dir: str | Path = "configs",
                      seed: int = 42, sim_minutes: int = 720,
                      minds: bool = False, threaded: bool = False,
                      scenario_dir: str | Path | None = None) -> "Engine":
```

At the very start of the body, choose where world files come from:

```python
        config_dir = Path(config_dir)
        world_dir = Path(scenario_dir) if scenario_dir is not None else config_dir
```

Then change the three world-file reads to use `world_dir` (leaving the shared rule configs — `settings.json`, `discoveries.json`, `magic.json`, `properties.json`, `brains.json` — reading from `config_dir`):

```python
        layers_cfg = json.loads(
            (world_dir / "layers.json").read_text(encoding="utf-8"))["layers"]
```

```python
            map_path = world_dir / layer["map"]
```

```python
            agents=load_agents(world_dir / "agents.json"),
```

Immediately after `state = WorldState(...)` is built, apply race config:

```python
        races_path = world_dir / "races.json"
        if races_path.exists():
            races = json.loads(races_path.read_text(encoding="utf-8"))["races"]
            for ag in state.agents:
                spec = races.get(ag.race)
                if not spec:
                    continue
                for tech in spec.get("starting_knowledge", []):
                    if tech not in ag.knowledge:
                        ag.knowledge.append(tech)
                for item, n in spec.get("starting_inventory", {}).items():
                    ag.inventory[item] = ag.inventory.get(item, 0) + n
                ag.warmth_decay_mult = spec.get("traits", {}).get(
                    "warmth_decay_mult", 1.0)
                if spec.get("blurb"):
                    ag.persona = (spec["blurb"] + " " + ag.persona).strip()
```

- [ ] **Step 8: Thread the flag through `run_sim` and `main`** — in `src/genesis/cli.py`.

`run_sim` signature + engine build:

```python
def run_sim(days: float, db_path: str | Path, seed: int = 42,
            minds: bool = False, threaded: bool = False,
            scenario: str | None = None) -> dict:
    engine = Engine.from_configs(CONFIG_DIR, seed=seed, minds=minds,
                                 threaded=threaded, scenario_dir=scenario)
```

In `main`, add the arg and pass it:

```python
    p.add_argument("--scenario", default=None,
                   help="Path to a scenario config dir (overrides map/agents/races)")
```

```python
    print(json.dumps(
        run_sim(args.days, args.db, args.seed, args.minds, args.threaded,
                args.scenario),
        indent=2))
```

- [ ] **Step 9: Run to verify it passes**

Run: `uv run pytest tests/test_scenario_load.py -v`
Expected: PASS (2 tests).

- [ ] **Step 10: Full suite**

Run: `uv run pytest -q`
Expected: all green (default `scenario_dir=None`/`scenario=None` leaves the base path unchanged).

- [ ] **Step 11: Commit**

```bash
git add configs/scenarios/first-contact src/genesis/world/engine.py src/genesis/cli.py tests/test_scenario_load.py
git commit -m "Load first-contact scenario with per-race starting state"
```

---

## Task 7: Observer runner + scenario smoke & determinism

A committed observer that summarizes a run, plus a deterministic (Instinct-path) smoke that the scenario runs and that contact fires when races converge.

**Files:**
- Create: `scripts/observe_first_contact.py`
- Test: `tests/test_first_contact_scenario.py`

**Interfaces:**
- Consumes: `Engine.from_configs(..., scenario_dir=...)` (Task 6); the `contact` event (Task 5).

- [ ] **Step 1: Write the failing test** — `tests/test_first_contact_scenario.py`

```python
from genesis.world.engine import Engine

SC = "configs/scenarios/first-contact"


def _run(days):
    eng = Engine.from_configs("configs", scenario_dir=SC, seed=42,
                              sim_minutes=0, minds=False)
    return eng, eng.advance(int(days * eng.settings["minutes_per_day"]))


def test_scenario_runs_clean_instinct_only():
    eng, events = _run(1)
    assert eng.state.sim_minutes >= eng.settings["minutes_per_day"]
    assert all("type" in e for e in events)


def test_contact_event_fires_when_races_converge():
    # The contact EVENT is emitted by _contact_check whenever a raced agent
    # perceives a foreign race in a live tick — no Brain required. Two races
    # within perception range produce a contact on tick 0.
    from genesis.world.grid import WorldMap
    from genesis.world.state import Agent, WorldState
    wm = WorldMap(["GGGGGG"] * 6)
    a = Agent(id="a", name="Ash", x=1, y=1, race="ashfolk")
    b = Agent(id="b", name="Moss", x=2, y=1, race="mosskin")
    st = WorldState(0, 1, [a, b])
    eng = Engine(st, settings={**_MIN, "perception_radius": 6}, maps=[wm])
    events = eng.tick()
    assert any(e["type"] == "contact" and e["race"] == "mosskin"
               and e["agent"] == "a" for e in events)


def test_determinism_same_seed_same_contacts():
    _, e1 = _run(1)
    _, e2 = _run(1)
    key = lambda evs: [(e["type"], e.get("agent"), e["minute"]) for e in evs]
    assert key(e1) == key(e2)


_MIN = {"minutes_per_day": 100000, "day_start_minute": 0, "day_end_minute": 100000,
        "hunger_decay_per_min": 0.0, "energy_decay_per_min": 0.0,
        "energy_regen_sleeping_per_min": 0.0, "warmth_decay_night_per_min": 0.0,
        "warmth_decay_night_sleeping_per_min": 0.0, "warmth_regen_day_per_min": 0.0,
        "warmth_regen_near_fire_per_min": 0.0, "campfire_warmth_radius": 1,
        "decision_cooldown_min": 0, "decision_stale_min": 100000}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_first_contact_scenario.py -v`
Expected: PASS on all three once Tasks 5 and 6 have landed (`_contact_check` emits the event without a Brain; the scenario loads and runs). This task adds no new production code — it is the committed observer script plus these guard tests. If `test_contact_event_fires_when_races_converge` fails, confirm Task 5's `_contact_check` fires on `agent.race` alone (not gated on a wired Brain).

- [ ] **Step 3: Write `scripts/observe_first_contact.py`**

```python
"""Observe first contact between races. Runs the first-contact scenario with
LLM minds and prints a contact timeline + per-race positions. Requires
GROQ_API_KEY in the environment. Usage: uv run python scripts/observe_first_contact.py [days]
"""
import sys
from collections import defaultdict
from genesis.world.engine import Engine

SC = "configs/scenarios/first-contact"


def main(days: float = 2.0) -> None:
    eng = Engine.from_configs("configs", scenario_dir=SC, seed=42,
                              sim_minutes=0, minds=True)
    race_of = {a.id: a.race for a in eng.state.agents}
    events = eng.advance(int(days * eng.settings["minutes_per_day"]))

    decided = {(e["agent"], e["minute"]): e for e in events if e["type"] == "decided"}
    print(f"=== first contact, {days} day(s), {len(eng.state.agents)} agents ===")
    print("\n-- contact timeline --")
    for e in events:
        if e["type"] == "contact":
            d = decided.get((e["agent"], e["minute"]))
            reason = f' -> {d["choice"]}: {d["reason"][:80]}' if d else ""
            print(f"  min {e['minute']:6d}  {e['agent']} ({race_of[e['agent']]}) "
                  f"meets {e['other']} ({e['race']}){reason}")

    approaches = sum(1 for e in events if e["type"] == "decided"
                     and str(e["choice"]).startswith("approach"))
    avoids = sum(1 for e in events if e["type"] == "decided"
                 and str(e["choice"]).startswith("avoid"))
    print(f"\napproach decisions: {approaches}   avoid decisions: {avoids}")
    print("\n-- final positions --")
    byrace = defaultdict(list)
    for a in eng.state.agents:
        byrace[a.race].append(f"{a.name}@({a.x},{a.y})")
    for race, who in sorted(byrace.items()):
        print(f"  {race:10s} {who}")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 2.0)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_first_contact_scenario.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Full suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add scripts/observe_first_contact.py tests/test_first_contact_scenario.py
git commit -m "Add first-contact observer runner and scenario smoke tests"
```

---

## Self-Review

**Spec coverage:**
- §4 race model → Task 6 (`races.json` + application). §5 Agent changes → Task 1 (fields) + Task 6 (application). §6 map/config/central-food → Task 6 (map with central berries + `scenario_dir` mechanism + `--scenario`). §7 perception + approach/avoid affordances → Task 2 (`perceive_agents`) + Task 3 (affordances) + §7 context keys → Task 5. §8a contact preemption → Task 5 (`_contact_check` in the tick loop, forced decision). §8b approach/avoid goals tracking a moving target → Task 4. §9 observer → Task 7. §10 determinism → Task 7 determinism test + `sorted()` in Task 2. §11 back-compat → defaults in Task 1, additive keys in Task 5, `scenario_dir=None` default in Task 6. §12 tests → across Tasks 1–7. §13 non-goals respected (no interaction action verbs; `VERBS` untouched). §14 tuning defaults (radius 6, cap 3) → Tasks 3/5.
- Gap check: the warmth trait (§4) is wired end-to-end (Task 1 mechanic, Task 6 application, Task 6 test). The "food in the middle draws both races" mechanism (§6) is realized by the central berry patches in the Task 6 map + the existing Instinct hunger→berries logic — no code change needed, exercised by Task 7's scenario run.

**Placeholder scan:** No TBD/TODO; every code and test step is literal.

**Type consistency:** `perceive_agents(agent, state, radius) -> list[dict]` with keys `name/race/dir/dist` is identical in Tasks 2, 3, 5. `approach`/`avoid` affordances carry `params={"target": name}` in Task 3 and are consumed with `p["target"]` in Task 4's `resolve_goal`. The `contact` event shape `{type,agent,race,other,minute}` is emitted in Task 5 and read in Task 7's observer. `Engine.from_configs(..., scenario_dir=None)` in Task 6 matches its callers in Task 6 (cli) and Task 7 (tests/observer). `Agent.race`/`warmth_decay_mult` defined in Task 1 are used in Tasks 2/3/5/6.

---

## Execution note

`test_engine_minds.py`, `test_cli.py`, and `test_engine_layers.py` build multi-agent engines. They use **raceless** agents, so `_contact_check` early-returns and the new `race`/`nearby` context keys are additive — they are expected to stay green. If one asserts an exact affordance list or context key-set and trips on the additive keys, update it to the enriched shape (never remove the new keys, never weaken an assertion). Run `uv run pytest -q` after each task to catch this immediately.
