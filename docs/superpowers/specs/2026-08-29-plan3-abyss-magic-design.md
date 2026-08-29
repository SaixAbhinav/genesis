# Genesis — Plan 3 ("The Abyss & Magic") Design Spec

**Date:** 2026-08-29
**Status:** Approved by user (brainstorming session)
**Repo:** `projects/genesis/`
**Depends on:** Plans 1–2 (world engine, discovery/crafting/building). Still **rule-driven**
(`instinct`); LLM minds are Plan 4.
**Roadmap context:** `docs/superpowers/specs/2026-08-29-genesis-roadmap.md`

---

## 1. Vision & scope

Turn the flat survival world into a **vertical, layered Abyss** (Made in Abyss) where
**descending is cheap but ascending inflicts an escalating Curse**, and give agents a
**Mushoku Tensei magic system** — the tool that lets them survive deeper strata. The
danger curve is deliberately tied to the magic curve: each layer demands a higher magic
rank than the last.

Plan 3 builds the deterministic **stage** and validates it with the existing rule-driven
`instinct` agents. Success = seeded runs in which a well-ranked agent descends to Layer 3
and returns alive, and an under-ranked agent dies on the climb — both reproducible from
the event log.

**In scope:** depth/layers, the Curse (strain), curse-only permadeath, the magic system
(mana, attributes, ranks, spells as typed effect records), 3 layers with hazards + relics
+ scarcity, new actions, an extended instinct policy, tests.

**Out of scope (later plans):** LLM minds (4), reproduction/lineage (5), romance (6),
farming (7), the self-building discovery engine (8), the Phaser viewer.

## 2. Guiding decision — discoveries are typed effect records

**Every discovery — crafting recipes and magic spells alike — is a typed record the
engine *interprets*, not a bare string with behaviour hard-coded in `actions.py`.**

```json
{
  "name": "minor_heal",
  "kind": "spell",
  "requires": [],
  "prereqs": { "attribute_rank": { "healing": "beginner" } },
  "effect": { "type": "reduce_strain", "amount": 20, "bonus": { "energy": 10 } }
}
```

- `name` — canonical id, added to `agent.knowledge` on discovery (unchanged mechanism).
- `requires` — prior knowledge needed to *discover* it (as today).
- `prereqs` — runtime gate to *use* it (e.g. minimum attribute rank).
- `effect` — a **typed, data-driven descriptor** the engine executes via a small
  dispatch table (`effect.type → handler`).

This is the forward-compat guardrail for Plan 8: the future generative engine coins new
records in this **same schema**, so it becomes additive rather than a rewrite. Plan 2's
existing recipes (`fire`, `stone_tools`, `cooked_food`) keep working; migrating their
hard-coded effects into `effect` records is a **non-blocking follow-up**, not required by
Plan 3. New Plan 3 content (spells) uses the schema from day one and proves the pattern.

## 3. World representation — the depth axis

- **Each layer is its own `WorldMap`.** `Engine` holds `maps: list[WorldMap]` and resolves
  the map per agent as `maps[agent.layer]`. `actions`, `needs`, `instinct` receive the
  agent's current map (minimal signature change: pass `maps[agent.layer]` where a single
  `world_map` is passed today).
- **`Agent` gains `layer: int = 0`** alongside `x, y`.
- **`Resource` and `Structure` each gain `layer: int = 0`.** Every resource/structure
  query filters to the acting agent's layer. (Least-invasive choice vs. nesting.)
- **Layer transitions are link tiles.** A layer's map has a `descend` tile (cave `C`) that
  drops to the next layer's paired `ascend` entry tile, and vice-versa. Moving between
  layers is *only* via the `descend`/`ascend` actions on those tiles — never free movement.
- **Depth in meters is layer config** (`depth_m: [top, bottom]`); the Curse reads the
  layer index, not per-tile depth. Keeps the model discrete and testable.

All layer content lives in **`configs/layers.json`** so Layers 4–7 are data, not code.

## 4. The Curse of the Abyss (signature mechanic)

- **New field `Agent.strain: float = 0.0`** — a stat that *only rises on ascent*.
- On a successful `ascend` from layer `L`, add `layers[L].curse_strain` to `strain`.
  Multi-layer climbs **stack** (each ascent adds its layer's value).
- `strain` **decays slowly** every tick (`strain_decay_per_min`) while not ascending.
- **Healing magic burns strain down fast** (the `reduce_strain` effect) — the primary
  counter and the first hard tie-in to the magic system.
- **Curse side-effects by band** (deterministic via the seeded `engine.rng`). Engine
  layers are 0-indexed (`agent.layer`), so `L1` = Forest of Temptation, `L2` = Great
  Fault:
  - Forest of Temptation (`L1`) — numbness: while `strain` is in a mid band, an agent
    action has a configured chance to fail (`action_fail` event).
  - Great Fault (`L2`) — hallucination: in a high band, `observe` may report a **phantom**
    threat, and movement may fail.

### Death model (curse-only permadeath)

- **New status `"dead"`.** Dead agents are skipped in `tick()` and excluded from all
  queries; a single `died` event is logged.
- An agent dies **only** if it would `collapse` (a need hits 0) **while
  `strain >= strain_lethal_threshold`** — i.e. the curse got them mid-climb. Ordinary
  surface need-collapse still recovers exactly as in Plan 1/2.
- Death is **permanent**. This is what makes every descent a genuine gamble.

## 5. Magic system (Mushoku Tensei)

New per-agent fields on `Agent`:

- `mana: float`, `mana_max: float`
- `attr_rank: dict[str, int]` — attribute → rank index (0 = none / unlearned)
- `attr_xp: dict[str, float]` — accumulated use-XP per attribute
- discovered spells live in the existing `knowledge` list

**Five attributes:** `fire`, `water`, `wind`, `earth`, `healing`. (Detoxification folds
into Water — "route A": Water clears *environmental* miasma, Healing offsets bodily curse.)

**Ranks (config-ordered, Plan 3 caps at King):**
`beginner → intermediate → advanced → saint → king`. Each has a `use_xp` threshold.

**Three deterministic MT mechanics:**

1. **Mana pool grows by depletion.** Casting that drives `mana` below
   `mana_depletion_frac × mana_max` raises `mana_max` by `mana_growth_step` on next
   recovery. No RNG.
2. **Rank up by use.** Each successful cast adds `attr_xp[attribute]`; crossing the next
   rank's threshold raises `attr_rank[attribute]`, unlocking stronger spells and reducing
   their `mana_cost` and `cast_minutes`.
3. **Chant → chantless.** A spell's `cast_minutes` is `base_cast_minutes` scaled down by
   the caster's rank in that attribute (higher rank = faster/near-instant) — matters when
   a predator is on you.

**Spells as typed effect records** (`configs/magic.json`), effects are survival verbs:

| Spell (example) | Attribute | Effect type | What it does |
|---|---|---|---|
| `minor_heal` | healing | `reduce_strain` (+energy) | Primary curse counter |
| `purify` | water | `clear_miasma` (buff w/ duration) | Neutralise Layer-2 spores |
| `kindle` | fire | `warmth` / `attack` | Warmth, cook, weapon vs. creatures |
| `stone_shape` | earth | `build_shelter` / `block` | Instant shelter, carve ledge |
| `updraft` | wind | `negate_fall` (buff) | Safe traverse on the Great Fault |

Magic is **discovered** through the existing `experiment_with` flow: experimenting with
the right items near a **`mana_crystal`** resource yields the agent's first spell
(a spell record whose `requires`/conditions are met), after which it grows by use.

## 6. Layers & the escalation wall

Three layers, each demanding a higher rank than the last (the "match the power" curve).

| | **L0 — Edge** (0–1350m) | **L1 — Forest of Temptation** (1350–2600m) | **L2 — Great Fault** (2600–7000m) |
|---|---|---|---|
| `curse_strain` on ascent | low | moderate (numbness band) | high (hallucination band) |
| Signature hazard | Cold nights; weak *Silkfang* | **Miasma spores** (poison tick) + *Corpse-Weeper* | **Fall-death** cliff traverse, aerial *Splitjaw*, bitter cold |
| Magic gate to thrive | none — **discover** magic here (mana crystals) | Water Intermediate (purify) · Healing Beginner+ · Fire | Wind Advanced (falls) · Earth Advanced (ledges) · Healing Saint (ascent curse) · Fire Advanced |
| Relic reward | trinket + **mana shard** (seeds first spell) | mid relic (value) + spell material | top relic (value) + **artifact: +mana_max** |
| Scarcity pull | thin surface food | rich food locked behind miasma | unique materials + best relics only here |

**Emergent death spiral:** an agent that dives to L2 for the artifact but never leveled
**Healing to Saint** takes lethal strain climbing back and dies deep — the Made in Abyss
tragedy, produced entirely by the rank math.

**Hazard mechanics (deterministic):**
- *Miasma* — on L1, each tick applies `miasma_damage` to a need unless a `clear_miasma`
  buff is active (`purified_until > now`, set by `purify`).
- *Fall* — traversing a `cliff` tile on L2 without a `negate_fall` buff triggers a fall:
  heavy strain + possible collapse (→ death if strain lethal). Seeded `rng`.
- *Creatures* — modeled as hazard tiles/encounters that damage needs unless countered by a
  `fire`/`attack` effect of sufficient rank. (Full creature AI is out of scope; encounters
  are deterministic damage-or-counter checks.)

## 7. Downward pull (why agents descend)

Both drivers, per the locked decision:
- **Scarcity by depth** — surface (`L0`) resources are thin and deplete; richer food/
  materials exist deeper, so long-term survival *requires* descent.
- **Relics** — each layer holds relics carrying `value`; deeper = higher value. Agents
  gain a scripted greed/curiosity weight (see §9) that trades safety for value.

New resource/entity types: `mana_crystal` (magic discovery), `relic` (value + payload
such as `+mana_max`), plus the per-layer food/material resources.

## 8. New actions

Add to `VERBS` and give each `validate` + `step` logic in `actions.py`:

- **`descend`** — only on a `descend` link tile; moves agent to the next layer's entry
  tile, `agent.layer += 1`. No strain.
- **`ascend`** — only on an `ascend` link tile; `agent.layer -= 1`, then apply
  `curse_strain` for the layer left. Emits `ascended` + `curse_strain` events.
- **`cast`** — args `{spell}`. Validates the spell is known, `prereqs` met, and
  `mana >= mana_cost`. Takes `cast_minutes` (rank-scaled) to complete, deducts mana,
  applies `effect` via the dispatch table, accrues `attr_xp`, triggers rank-up / mana
  growth checks. Emits `cast` (+ effect-specific events).
- **`harvest_relic`** — picks up a reachable `relic`, adds `value` to the agent and
  applies its payload (e.g. raise `mana_max`).

## 9. Agent behavior (instinct policy)

Extend `choose_action` with a deterministic priority ladder so rule agents exercise the
loop (LLM choice is Plan 4):

1. **Survive** — if a need is critical *or* `strain` is dangerous: eat / warm / `cast`
   Healing / retreat (`ascend` toward safety), and in a hazard, counter it
   (`purify` in miasma, `updraft` before a cliff, `kindle` vs. a creature).
2. **Descend** — if the current layer's resources are thin *and* the agent meets the next
   layer's magic gate: `descend`.
3. **Harvest** — if a relic is reachable and the tile is safe: `harvest_relic`.
4. **Train** — otherwise grind the attribute the next layer demands and `cast` to deplete
   mana (grow the pool).

This makes agents **climb the magic curve to unlock depth** on their own, and mis-judgers
(descending under-ranked) die — the behaviour we want to watch.

## 10. Config & data-model summary

**New config files:**
- `configs/layers.json` — per layer: `name`, `depth_m`, `map`, `curse_strain`, `hazards`,
  `scarcity`, `relics`, `magic_gate`, link-tile coords.
- `configs/magic.json` — `attributes`, `ranks` (+ `use_xp` thresholds), `spells` (typed
  effect records), mana-growth params.
- `configs/maps/layer{0,1,2}.json` — one `WorldMap` each.

**`configs/settings.json` additions:** `strain_decay_per_min`, `strain_lethal_threshold`,
curse side-effect bands + fail chances, `miasma_damage`, fall params,
`mana_depletion_frac`, `mana_growth_step`, base cast-time scaling.

**`state.py` changes:** `Agent` += `layer`, `strain`, `mana`, `mana_max`, `attr_rank`,
`attr_xp`; `status` gains `"dead"`. `Resource` and `Structure` += `layer`. `WorldState`
serialization (`to_json`/`from_json`) updated for the new fields and `maps`.

**`engine.py` changes:** hold `maps: list[WorldMap]`; per-agent map resolution; skip dead
agents; strain decay + curse side-effects in the tick; effect dispatch table.

## 11. Testing (matches Plan 1/2 style; currently 67 tests)

**Unit:**
- Curse strain scales by layer and **stacks** on multi-layer ascent; decays over time;
  `reduce_strain` (Healing) lowers it.
- Curse-only death: collapse with `strain ≥ lethal` → `dead`; ordinary collapse recovers.
- Mana pool grows on depletion; attribute rank-up at XP threshold; `cast_minutes` shrinks
  with rank.
- Spell `prereqs`/`mana_cost` gating; effect dispatch for each `effect.type`.
- Miasma ticks and is cancelled by an active `clear_miasma` buff; cliff fall without
  `negate_fall`; `descend`/`ascend` gated to link tiles only; per-layer resource/structure
  filtering.

**Integration (seeded, asserted via event log):**
- **Successful dive:** a well-ranked agent descends L0→L2, harvests the artifact, and
  returns to L0 alive.
- **Death spiral:** an under-ranked agent descends and **dies** on the climb (curse).

## 12. Follow-on / non-blocking

- Migrate Plan 2's hard-coded effects (`cooked_food`, `stone_tools`) into `effect` records
  (unifies the schema; not required for Plan 3).
- The Plan 2 `DiscoveryGraph.match()` "first recipe in file order" bug (noted in PR #2) —
  fix to match the first *unknown* record here.
- Layers 4–7, real creature AI, and the Phaser viewer are later plans.

## 13. Open questions (resolve during writing-plans)

- Exact numeric balance of `curse_strain`, rank thresholds, and mana curve (tune against
  the two integration scenarios).
- Whether creature encounters need positions or can be pure hazard-tile checks in Plan 3
  (leaning: hazard-tile checks — YAGNI).
