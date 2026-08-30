# Plan 4a — LLM Minds (Brain seam + one live mind)

**Date:** 2026-08-30
**Status:** Design (post-grill); pending user review before writing the plan
**Repo:** `projects/genesis/`
**Depends on:** Plans 1–3 (built; `feat/abyss-magic`, 119 tests green)
**Glossary:** see `CONTEXT.md`. **Decision record:** see `docs/adr/0001-fast-forward-is-instinct-only.md`.

---

## 1. Goal of this slice

Make a **real LLM drive an Agent's choices** — asynchronously, grounded, and
watchable — without disturbing the deterministic engine. 4a is the first slice of
Plan 4 (LLM minds). It delivers the **Brain seam**, one working provider (Groq),
the **async ThinkQueue**, the **affordance → Goal** decision model, and a
`decided` event stream that makes each choice (and its one-line reason) observable
before the Phaser viewer exists.

**Explicitly out of scope** (later slices): memory stream + retrieval (4b);
reflection + morning day-planning (4c); conversations + knowledge transfer (4d);
the mixed-brain "who's smarter" scoreboard (4e); the Phaser viewer.

A **side effect worth noting:** because the affordance menu includes
`experiment_with`, `descend`/`ascend`, and `cast`, an LLM Agent can autonomously
dive and discover magic — the behaviour Instinct cannot produce (Plan 3
fast-follow #2). 4a partially closes that follow-up as a consequence, not a goal.

## 2. The golden rule (unchanged)

The engine owns **facts** (positions, inventory, needs, discoveries, validity).
A Mind owns only **choices and words**. A Brain never computes coordinates, never
mutates state, and never bookkeeps. It picks one **Affordance** from a menu the
engine computed, and the engine does the rest.

## 3. Core model: Affordance → Goal → Action

Three domain terms (see `CONTEXT.md`), in a strict hierarchy:

- **Affordance** — a currently-valid, world-grounded option the engine offers.
  Shape: `{id, verb, params, label, dir, dist}`.
  - `id` is **stable**: `verb + target's own identity`, e.g.
    `gather:berries@(6,3,0)`, `cast:minor_heal`, `descend`. **Never**
    agent-relative — position-encoded ids would change every step and break
    staleness matching. `label`/`dir`/`dist` carry the human "3 tiles E" for the
    prompt only.
- **Goal** — the single Affordance an Agent is currently pursuing
  (`agent.goal: dict | None`, mirroring `current_action` so it serializes through
  `asdict`/`from_json` with no db.py change).
- **Action** — one engine step. One Goal expands into one or more Actions via the
  Goal resolver.

### Decision flow (inside `Engine.tick`, per active Agent)

When `agent.current_action is None`:

0. **Survival interrupt.** If a need is survival-critical or strain is dangerous
   (the same thresholds Instinct reacts to), clear any active `agent.goal`. A Mind
   is never locked into a Goal while dying — the Agent gets a fresh Decision (or,
   until it lands, Instinct's heal/eat/flee reflex). This is what lets a *smart*
   model visibly react to danger; a Goal that ignored starvation would only make
   every model look equally reckless.
1. **Drive the active Goal.** If `agent.goal` is set, call
   `resolve_goal(agent, goal, …) → action | None`.
   - non-None → set `current_action`, done for this tick.
   - None → the Goal is satisfied or invalid; clear it and fall through.
2. **Consume a landed Decision.** If the Agent's inbox holds a Decision **and**
   its chosen affordance id is still in the freshly-computed menu **and** it is not
   older than `decision_stale_min` → set it as the new `agent.goal`, emit
   `decided`, clear the pending flag. Then go to step 1. (No cooldown gate here —
   the request was already spent; discarding a landed Decision would waste budget.
   The cooldown gates *submission* only, in step 3.)
3. **Submit a Decision job** (if none pending for this Agent and the cooldown has
   elapsed): build the affordance menu + compact context, enqueue
   `DecisionJob{agent_id, sim_minute, affordances, context}`, mark pending.
4. **Stay lively.** If the Agent still has no action this tick, fall through to
   **Instinct** (`choose_action`) so it keeps moving while its thought is in flight.

**Staleness** (ADR-adjacent, phase-1 "stale jobs dropped"): a landed Decision is
re-validated against the *current* world in step 2. Vanished target or too-old job
→ dropped, pending cleared, re-submitted next chance. A slow/outdated thought can
never force an invalid action.

**Dedup:** at most one in-flight job per Agent.

## 4. The Brain seam

```
Mind
 ├─ InstinctBrain   — wraps today's choose_action UNCHANGED (fallback + no-key mode)
 ├─ LLMBrain        — menu + context → prompt → validated {choice, reason}
 └─ FakeBrain       — scripted choices, for deterministic tests
```

- `InstinctBrain` is literally today's `instinct.choose_action`; the 119 existing
  tests are untouched. It is the fallback whenever a Brain is absent, thinking, or
  returns something invalid.
- `affordances(agent, state, map, settings, graph, magic) → [Affordance]` is **new**
  code and the single source of Brain-offered options. Instinct is allowed to
  differ from the menu; unifying them is a later refactor, not 4a.
- `GroqBrain.complete(prompt, schema) → dict` — one ~30-line adapter.
  `GROQ_API_KEY` via `.env` (never committed). JSON structured output. Reply schema
  `{choice: <affordance_id>, reason: <one line>}`, validated against the submitted
  ids → invalid → **one retry → Instinct fallback**. Missing key → degrade to
  Instinct with one log line (the sim always runs).

### Prompt context (stateless in 4a; no memory stream yet)

Compact JSON: `persona` (curious/cautious/social/lazy), `needs`, `strain`,
`mana`/`mana_max`, `layer`, `inventory`, `known` discoveries, `recent` (last 1–2
actions, to stop dithering), and `options` (the menu with labels + dir/dist).
Kept small on purpose — see §6.

## 5. The ThinkQueue (async)

```
ThinkQueue
 ├─ InlineQueue        — resolves each job immediately via the injected Brain
 │                       (deterministic; used by ALL behavioral tests)
 └─ ThreadedThinkQueue — worker thread; per-provider rate limiter; daily-request
                         budget guard; result inbox per Agent (production)
```

- The world **never blocks** on the queue. Results land in a per-Agent inbox and
  are consumed at the next decision point (§3 step 2).
- `ThreadedThinkQueue` enforces a **daily-request budget** (default sized to the
  free-tier ~1,000 RPD, configurable). Near the cap it stops submitting — Agents
  ride Instinct and it logs — rather than throwing 429s.

## 6. The free-tier ceiling (the constraint that shapes 4a)

Groq free tier for the target models is **~30 RPM / ~1,000 RPD**, shared across all
Agents (sources: eesel AI; TokenMix; Price Per Token, Aug 2026). **RPD is the
binding constraint: ~1,000 Decisions per wall-clock day, total.** Three rules:

1. **Fast-forward is Instinct-only** (see ADR 0001). Catch-up `advance_world`
   submits no jobs; Brains engage only for live watching.
2. **Daily-request budget guard** lives in `ThreadedThinkQueue` (§5).
3. **Decisions/agent/sim-day bounded to ~30–50** by the Goal layer plus
   `decision_cooldown_min` (~30 sim-min floor — an Agent won't submit a new job
   more often than this; between, it rides Instinct). Sleep-goals collapse whole
   nights into one Decision.

Model choice is quality-only (budget is identical across models) → default
**`groq/llama-3.3-70b-versatile`**. Budget expansion later = mixing providers
(Gemini's separate pool); the `brains.json` seam makes it drop-in.

## 7. Config & enablement

- `agents.json` / a small `brains.json` maps `Agent.brain` (field already exists)
  → `{provider, model}` and carries each Agent's `persona`.
- LLM minds are **opt-in**. An Engine built without a brain/queue keeps today's
  pure-Instinct path (all 119 tests literally unchanged). A `--minds` CLI flag (or
  presence of `brains.json`) wires `ThreadedThinkQueue` + `GroqBrain`.

## 8. Observability

Every Decision emits a `decided` event: `{agent, choice, reason, model, minute}`,
appended to the existing event stream / SQLite `events` table. This makes the
"who's smarter" signal and each Agent's reasoning watchable now, before the viewer.

## 9. Testing (TDD; suite stays deterministic, never hits the network)

- **Existing 119 tests:** unchanged (no brain/queue → pure Instinct).
- `affordances()` returns the right menu for scripted scenarios (incl. stable ids).
- `resolve_goal` expands a Goal into the correct Action sequence and returns None
  when satisfied/invalid.
- Decision flow with `InlineQueue` + `FakeBrain`: Agent adopts and pursues the
  chosen affordance as a Goal to completion.
- Staleness: a Decision whose affordance vanished is dropped → Instinct fallback.
- In-flight: while pending, the Agent acts on Instinct.
- Cooldown: an Agent does not submit more than once per `decision_cooldown_min`.
- Budget guard: at the daily cap, `ThreadedThinkQueue` stops submitting and the
  Agent rides Instinct.
- `GroqBrain`: schema-validate + one retry + fallback, **HTTP mocked**; missing key
  → Instinct.
- `ThreadedThinkQueue`: one narrow plumbing test — submit a job (FakeBrain), block
  on a completion signal, assert the result lands in the inbox. No sim-determinism
  depends on threads.

## 10. New/changed files (anticipated)

- `src/genesis/world/affordances.py` — the menu builder (new)
- `src/genesis/world/goal.py` — `resolve_goal` (new)
- `src/genesis/mind/brain.py` — `Mind`/`Brain` protocol, `InstinctBrain`,
  `FakeBrain` (new package)
- `src/genesis/mind/llm_brain.py`, `src/genesis/mind/groq.py` — LLM Brain + adapter
- `src/genesis/mind/queue.py` — `InlineQueue`, `ThreadedThinkQueue`
- `src/genesis/world/engine.py` — decision flow in `tick`; optional brain/queue
- `src/genesis/world/state.py` — `Agent.goal: dict | None`
- `configs/brains.json`, `.env.example` — config + key template
- `configs/settings.json` — `decision_cooldown_min`, `decision_stale_min`,
  `daily_request_budget`

## 11. Success criteria

- With `--minds`, a live run shows Agents adopting LLM-chosen Goals, pursuing them
  to completion, and re-deciding — visible in the `decided` event stream with
  reasons — while never blocking the world.
- With no key / no `--minds`, the sim runs exactly as today.
- The full suite is green and deterministic; no test makes a network call.
- A catch-up fast-forward makes zero LLM requests (ADR 0001).
