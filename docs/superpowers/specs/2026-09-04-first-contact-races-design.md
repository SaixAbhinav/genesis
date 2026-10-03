# Genesis — First Contact: a perception-only race experiment (Design Spec)

**Date:** 2026-09-04
**Status:** Approved & grilled (brainstormed and stress-tested 2026-09-04); ready for
implementation plan. §7–§9 reflect decisions forced by the goal/decision loop during the grill.
**Branch target:** `feat/first-contact-races` (off `feat/property-grounded-materials`, the current tip)

---

## 1. Context & problem

The engine has depth, needs/Curse, magic, and property-grounded discovery, plus an LLM
Brain seam. Live `--minds` runs (memory `minds-behavior-observations`) showed discovery is
largely **Instinct-driven** and the Brain rarely engages the world's *vertical* depth —
nobody descended in 3 sim-days, so the abyss went unobserved. The vertical axis is also
**hard to watch**: "did the Brain choose to descend" is a binary buried in a decision log.

**This experiment pivots to a lateral, social axis that is easy to observe:** multiple
**races** of people, spawned apart, who **meet** as their ranges grow. We watch — from
positions and the Brain's own logged reasoning — what agents do on first contact with a
member of another race.

The blocking reality: **agents currently cannot perceive one another.** `Agent` has a
`persona` string but no group identity; neither the affordance menu nor the Brain context
mentions other agents; there is no inter-agent verb, and the goal/decision loop assumes an
agent acts alone. Adding **perception** (and integrating it with that loop) is the
foundational work and the smallest experiment that answers the question.

## 2. Goals & non-goals

**Goals**
1. Agents carry a **race** identity from config, with per-race persona, starting
   knowledge/inventory, a home spawn region, and one minimal mechanical trait.
2. Two races spawn **apart** in distinct home biomes with characteristic materials; shared
   **food** sits in neutral ground so ordinary foraging draws both races together (§6).
3. Agents **perceive** all nearby agents and their race; this is surfaced to the Brain
   (context) and as **movement affordances** (`approach`/`avoid`) that resolve to the existing
   `move_to` **action** — **no new action verbs**.
4. **First contact with a new race preempts** whatever the agent is doing and forces a Brain
   decision, emitting a `contact` event, so the LLM (not Instinct) reacts at the salient moment.
5. Nothing about how races treat each other is scripted; Instinct stays race-neutral.
6. Runs as its **own scenario** (its own map + agents + races), reusing the shared
   rule/property/magic configs, leaving the abyss experiment untouched.
7. Determinism holds on the deterministic (non-LLM) path and for Brain *inputs*; the existing
   suite stays green; new behavior is covered by new tests.

**Non-goals (this spec)**
- Any interaction *action*: trade, give, talk/signal, attack, conflict resolution.
- Relationships, reputation, or encounter memory beyond a per-agent first-contact flag.
- More than 2 races in the shipped scenario (the model allows N; the scenario uses 2).
- The abyss/layers inside this scenario (single layer only).
- Instinct-side social behavior (Instinct ignores other agents).

## 3. Design overview

```
two races spawn apart ──▶ hunger drives both toward the shared food in the middle
        │                              │
        │                        an agent perceives a member of ANOTHER race in range
        ▼                              │
  perceive_agents(radius)        first time for that race?
   → nearby[] in context               │
   → approach/avoid affordances   yes ─▶ preempt goal+action, emit {type:"contact"},
     (resolve to move_to)                force a Brain decision THIS tick
                                        │
                                        ▼
                             Brain picks approach/avoid/observe/… ; approach & avoid
                             track the live target each tick via resolve_goal;
                             positions + logged reasons = the observation
```

## 4. Race model — `races.json` (new, scenario-scoped)

```jsonc
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

- `starting_knowledge` / `starting_inventory` are applied to each agent of that race at load.
- `traits.warmth_decay_mult` (optional, default 1.0) multiplies that race's night warmth
  decay — the one minimal mechanical difference, reusing the existing decay pattern. Ashfolk
  are warmth-hardy; Mosskin instead carry insulating `thick_moss` (an existing mechanic), so
  the two are mechanically distinct without a new system. Future traits follow the same shape.
- `blurb` is prepended to the agent's Brain persona so the model knows its people.

## 5. Agent changes

Add two fields to the `Agent` dataclass, both defaulted so existing scenarios/tests are
unaffected:
- `race: str = ""`
- `warmth_decay_mult: float = 1.0`

`load_agents` stays dumb (`Agent(**a)` from `agents.json`, which now may carry `race`).
**Race application happens in `Engine.from_configs`** after loading agents: for each agent,
look up its race in `races.json` and (a) extend `knowledge` with `starting_knowledge`,
(b) merge `starting_inventory` into `inventory`, (c) set `warmth_decay_mult` from
`traits`, (d) prepend the race `blurb` to `persona`.

## 6. First-contact scenario — map & config

- A dedicated **single-layer** map, wider than tall, three bands:
  - **West (warm) home:** `rock`/`sand`, with `ember_dust`, `flint`, `stone`, `wood`. Ashfolk
    spawn here.
  - **East (forest/marsh) home:** `forest`/`marsh`, with `thick_moss`, `arcane_moss`, `wood`,
    `water`. Mosskin spawn here.
  - **Neutral middle:** `grass`, holding the **berry (food) patches** — the shared draw.
- **Why food is central:** Instinct already seeks the nearest `berries` when `hunger < 40`
  ([instinct.py](src/genesis/world/instinct.py)). Putting food in the middle makes ordinary
  hunger-foraging pull *both* races toward each other → organic first contact, with **zero**
  scripting of the social reaction. Home halves hold only race-specific *materials*, so agents
  start out of perception range and converge on the food over the first day or two.
- **Config mechanism.** `Engine.from_configs(config_dir="configs", scenario_dir=None, …)`.
  When `scenario_dir` is given, `layers.json` (+ the maps it references, resolved relative to
  `scenario_dir`), `agents.json`, and `races.json` load from `scenario_dir`; the shared
  `settings.json`, `discoveries.json`, `magic.json`, `properties.json`, `brains.json` load
  from `config_dir`. `races.json` is loaded only if present (no-op otherwise). A `--scenario
  <dir>` CLI flag threads through `run_sim`. Abyss configs are untouched; nothing is duplicated.

## 7. Perception & movement affordances

New helper (module-level; in a new `perception.py`, or `affordances.py` if it stays small):

```
perceive_agents(agent, state, radius) -> list[dict]
    # all OTHER living agents on the same layer within Manhattan `radius`,
    # each {"name", "race", "dir", "dist"}, sorted by (dist, name). Excludes self and dead.
    # Includes kin and strangers alike, so clustering is observable too.
```

- `settings["perception_radius"]` (default 6).
- **Brain context** (`Engine._context`): add `"race": agent.race` and
  `"nearby": perceive_agents(...)`.
- **Affordances:** for the nearest `settings["perception_affordance_cap"]` (default 3)
  perceived agents, emit two options **whose `verb` is `approach` / `avoid`** and whose params
  are `{"target": "<name>"}` (a name, not a fixed tile — the target moves):
  - `approach:<name>` — label e.g. `approach the Mosskin to the NE`.
  - `avoid:<name>`   — label e.g. `move away from the Mosskin to the NE`.
  These are **goal/affordance verbs**, not action verbs; they resolve to `move_to` actions
  (§8). `move_to` validation/behavior is unchanged, and `VERBS` (the action allow-list) is not
  touched. Instinct never emits them (race-neutral).

## 8. Goal/decision-loop integration (the load-bearing part)

The grill surfaced that `Engine._decide` returns at the goal-drive step before ever reaching
the Brain path, and that `resolve_goal` has no `move_to` handling. Both must change.

**8a. Contact preemption.** At the top of `_decide`, during **live** sim only (never ADR-0001
catch-up), compute perception. If the agent perceives a member of a race **not** in
`self._contacted[agent.id]`:
  - emit `{type: "contact", agent, race, other, minute}` (once per (agent, race) pair),
  - add the race to the contacted set,
  - **clear `agent.goal` and `agent.current_action`**, and fall through past the goal-drive
    step, **bypassing the decision cooldown** so a Brain job is submitted and (Inline queue)
    resolved this tick.
  If no Brain/queue is wired, the `contact` event still fires and Instinct proceeds
  (race-neutral) — keeping the deterministic path testable without an LLM.

**8b. `approach` / `avoid` as goals.** `resolve_goal` gains two branches. Both find the target
agent by `name` in `state.agents`; if it is missing, dead, on another layer, or beyond
`perception_radius`, return `None` (goal ends):
  - `approach`: if already `_adjacent` to the target, return `None` (arrived → goal clears →
    the Brain re-engages next decision); else `_move_toward` the target's **current** tile.
  - `avoid`: return a `move_to` one step directly away from the target's current tile (onto a
    walkable neighbor); if the target is already outside `perception_radius`, return `None`
    (escaped).
  Because the executed action is `move_to` (never equal to the goal verb `approach`/`avoid`),
  `_drive`'s terminal check won't prematurely clear the goal — the `None` returns above are the
  explicit terminations. Targets are recomputed every tick, so pursuit/flight tracks a moving
  agent.

## 9. Observability

A **committed** observer runner, `scripts/observe_first_contact.py`, builds the scenario
engine with minds, advances N days, and reports:
- the **contact timeline** — each `contact` event with the reacting Brain's `decided` reason,
- **positions by race** over periodic snapshots — do races hold home ranges, drift, cluster,
  interleave?
- the **approach/avoid choices** actually taken and their reasons.
The deliverable is a human-readable answer to "what did they do when they met?" Context cost
is small (prior measurement ≈1–1.5k tokens; `nearby` adds a few dozen).

## 10. Determinism

- `perceive_agents` sorts by `(dist, name)`; affordance emission iterates that sorted list and
  a fixed cap; move-target math is pure integer arithmetic; the contacted-set trigger is
  deterministic given identical perception order. No new randomness is introduced.
- Guarantee scope: on the **deterministic (Instinct / no-LLM) path**, same seed + same
  scenario ⇒ identical `contact`/`decided`/`moved` sequence. On the Brain path, the *inputs*
  (perception order, prompts) are deterministic, but the model's decisions are not — the
  determinism tests exercise the non-LLM path (as the existing suite does).

## 11. Migration & back-compat

- `Agent.race` (`""`) and `Agent.warmth_decay_mult` (`1.0`) are additive; `perceive_agents`
  and the new context keys are additive. Scenarios/tests that never set a race and never read
  `nearby` behave exactly as today.
- `tick_needs`'s night branch multiplies the decay rate by `agent.warmth_decay_mult` (default
  1.0 ⇒ no change), stacking with the existing insulation factor. Signature unchanged.
- `from_configs` gains an optional `scenario_dir`; the default (no scenario) path is unchanged.
- No existing config is edited destructively; the scenario is entirely additive.

## 12. Testing plan (new tests)

1. **Perception:** returns the right neighbours within radius on the same layer, sorted by
   `(dist, name)`, excluding self and dead; empty when alone.
2. **Context:** `_context` includes `race` and a `nearby` list matching perception.
3. **Approach/avoid affordances:** offered for nearest perceived agents up to the cap, verb
   `approach`/`avoid`, params `{target}`, with race + direction in the label.
4. **`resolve_goal` tracking:** an `approach` goal moves toward the target's *current* tile and
   returns `None` on adjacency; an `avoid` goal steps away and returns `None` once the target
   leaves radius or is gone/dead.
5. **Contact preemption:** first perception of a new race emits exactly one `contact` per
   (agent, race), clears an in-progress goal/action, and forces a decision that tick; a second
   sighting of the same race neither re-emits nor re-preempts. (Uses a fake brain/queue, as
   `test_engine_minds` does.)
6. **Race load:** agents receive their race's `starting_knowledge`/`starting_inventory`, the
   blurb reaches the persona, and `warmth_decay_mult` is set.
7. **Warmth trait:** an Ashfolk agent loses night warmth at `warmth_decay_mult ×` the base
   rate; a race without the trait uses the base rate.
8. **Back-compat:** a no-race, no-scenario run behaves exactly as today (no `contact`, `nearby`
   absent-or-empty, decisions unchanged).
9. **Determinism (non-LLM):** same seed + scenario ⇒ identical `contact`/`moved` sequence on
   the Instinct path.

Run with `uv run pytest`.

## 13. Deferred / explicitly out of scope
- Interaction *actions* (give/trade/talk/signal/attack) and conflict resolution — the
  deliberate v2 once perception-only first contact is observed.
- Encounter memory, relationships, reputation, alliances.
- More than 2 races in the shipped scenario; procedurally generated peoples.
- The abyss/layers inside this scenario.
- Instinct-side social behavior.

## 14. Open questions (tuning only — mechanics are resolved above)
- **Perception radius** (start 6), **approach/avoid cap** (start 3), and **spawn separation /
  map size** — tune after a live run so first contact lands in the first day or two.
- **Is the preemption trigger enough** to keep contact Brain-driven, or does the scenario also
  want a lower `decision_cooldown_min`? Decide from the first run (not by scripting Instinct).
- **One warmth trait** vs. more per-race traits later.
- **`perception.py` vs folding into `affordances.py`** — decide by size during implementation.
