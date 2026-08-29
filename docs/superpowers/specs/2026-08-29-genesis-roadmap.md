# Genesis — Roadmap & Vision

**Date:** 2026-08-29
**Status:** Living document (captures direction agreed in brainstorming; not all approved for build)
**Repo:** `projects/genesis/`

---

## North Star

An **emergent society simulation**: a small crew of LLM-minded agents starts from
nothing and we watch them not just *survive*, but *invent their own systems* —
technology, social structures, agriculture, lineage. The entire point is to see how
they would come up with these things, given only a world and each other. Every agent's
mind is a different LLM, so the sim doubles as a watchable "which model is smarter?"
benchmark.

**This is a fun project.** Decisions optimize for delight and watchability over
production polish.

## Setting (decided 2026-08-29)

The world is themed after two anime worlds, chosen because they contribute
non-overlapping halves:

- **Made in Abyss → the world.** A vertical, layered abyss. Descending is cheap;
  ascending inflicts an escalating **Curse** (strain) that scales with the depth you
  leave. This "one-way pressure" makes every descent a genuine gamble — perfect for
  watching LLMs weigh risk.
- **Mushoku Tensei → the power system.** Mana pools that grow by depletion,
  per-attribute ranks (Beginner → Intermediate → Advanced → Saint → King → Imperial →
  God), and chant-to-chantless progression. Magic is discoverable and is the tool that
  lets agents survive deeper strata.

The danger curve is deliberately tied to the magic curve: each layer demands a higher
magic rank than the last, so the power system always has a wall to climb.

## Plan roadmap

| Plan | Theme | Status |
|---|---|---|
| 1 | World engine core (grid, needs, persistence) | **Built** |
| 2 | Discovery, crafting & building | **Built** |
| **3** | **The Abyss + magic mechanics** (depth axis, ascent curse, per-layer hazards, MT magic system) — deterministic, validated with rule-driven `instinct` agents | **Designed 2026-08-29, spec pending** |
| 4 | **LLM minds** — agents that choose and reason (replaces `instinct`) | Not designed |
| 5 | **Mortality & lineage ("new generation")** — reproduction, aging, offspring; heritable mana talent (MT bloodlines). Natural follow-on to the permadeath introduced in Plan 3 | Not designed |
| 6 | **Relationships / romance** — bonds, pairing, social memory between agents | Not designed |
| 7 | **Agriculture / farming** — cultivating resources instead of foraging; an emergent discovery once LLM minds exist | Not designed |
| 8 | **Self-building discovery engine** (research track — see below) | Research idea |

Plans 5–7 depend on Plan 4: rule-driven agents follow a scripted ladder and cannot
*invent* romance, farming, or new institutions. Genuine emergence needs minds.

## Plan 3 — decisions locked (2026-08-29)

Full spec to be written separately. Key decisions:

- **Depth model:** each layer is its own `WorldMap`; `Agent` gains a `layer` index;
  layers link through descent tiles. Depth-in-meters is a per-layer config property.
  All layer content is config JSON so layers 4–7 are data, not code.
- **The Curse:** new per-agent `strain` stat that only rises on **ascent**, scaled by
  the layer left, stacking on multi-layer climbs, decaying slowly, burned down fast by
  Healing magic.
- **Death model:** add a `dead` status. Death is **permanent but curse-only** — an
  agent dies if it collapses while `strain` is above a lethal threshold; ordinary
  need-collapse still recovers as today.
- **Magic (MT):** per-agent `mana`, `mana_max`, `attributes` (ranks). Five attributes:
  `fire`, `water`, `wind`, `earth`, `healing` (Detoxification folded into Water for now
  — route A). Mana pool grows by depletion; rank up by use; chant → chantless buys
  speed. Spells are survival verbs (heal burns strain, water purifies miasma, wind
  negates falls, earth builds shelter, fire = warmth/weapon). Magic is **discovered**
  via the existing discovery engine.
- **Layers built:** 3 — Edge of the Abyss, Forest of Temptation, Great Fault — with an
  escalation wall tying each layer's hazards to a required magic rank (discover →
  Intermediate → Advanced/Saint).
- **Downward pull:** both **resource scarcity by depth** (surface is thin, richer
  resources deeper) **and relics** (value that rewards pushing past the safe point).
- **Forward-compat guardrail (typed effect records):** every discovery — including the
  hand-authored magic spells and recipes in Plan 3 — is represented as a
  **typed effect record** (`{name, requires, effect, prereqs}`), not a bare
  `items → result` string. This is the single decision that lets the Plan 8 generative
  engine be *additive* (it coins new records in the same schema) instead of a rewrite.
  It costs nothing extra to build now and de-risks the whole research track.

## Research track — Self-building discovery engine (Plan 8-ish)

The dream: agents figure out they need something (e.g. *electricity*), and **code is
written by an agent behind the scenes to make it real** — the discovery was never
pre-authored by us.

**Precedents that prove it works:**
- **[Infinite Craft](https://en.wikipedia.org/wiki/Infinite_Craft):** never hard-codes
  combinations. Combine two things → cache miss → an LLM adjudicates the result and
  coins a new entity → cached forever (deterministic per input). The tech tree builds
  itself.
- **[Voyager](https://arxiv.org/abs/2305.16291)** (NVIDIA/Caltech, Minecraft): the
  agent **writes its own executable code** for new skills, verifies it by running it in
  the world, and stores it in an ever-growing skill library — genuine lifelong learning
  with no human-authored tech tree.

**The design spectrum (closed → open):**

- **A. Closed graph (today):** humans pre-author every recipe. "Electricity" must exist
  in advance.
- **B. LLM-as-arbiter (Infinite Craft):** free-text combination, coins new names,
  cached. Open-ended but weakly grounded.
- **C. Property-grounded:** materials carry attributes (`conductive`, `magnetic`,
  `flammable`…); the LLM reasons over properties, so electricity emerges only when
  conductor + moving magnet exist. Coherent, less hallucination.
- **D. Code-skills (Voyager):** the agent authors verified executable code; the
  discovery actually *works*, not just a label.

**The hard 20% — naming ≠ mechanics.** Infinite Craft "discovers electricity" as a
*word*; it powers nothing. For Genesis, a discovery must feed back into the
deterministic engine as a **typed effect** the engine can execute:
`{name, requires:[...], effect, prereqs:[...]}`. Turning a coined *concept* into
engine-legible *rules* (or verified code, à la Voyager) is the real frontier.

**Determinism reconciliation:** memoize every LLM adjudication — same inputs → same
coined result forever. The tech tree becomes a growing, persistent cache of judgments,
which keeps the seeded engine deterministic and cuts token cost.

**Guardrails** so it doesn't drift into incoherence (agents "inventing" teleporters on
day 2): a property system, an energy/conservation budget, prerequisite gating, and a
consistency judge. Because the world has magic, these can be deliberately loosened where
wild emergence is a feature rather than a bug.

**Recommended shape — hybrid:** a **small closed core** (survival basics — fire, food,
the magic attributes — stay deterministic and testable) plus a **generative frontier**
layered on top for open-ended invention. Testability where it matters; genuine "they
came up with it themselves" where it's fun. Sits on top of LLM minds (Plan 4);
realistically Plan 8+.

**The bridge back to Plan 3:** the only forward decision that matters *now* is the
**typed effect record** schema (see Plan 3 locked decisions). If every hand-authored
discovery already speaks `{name, requires, effect, prereqs}`, the generative engine
simply coins new records in the same shape — additive, not a rewrite. Everything else
about Plan 8 is deferred until LLM minds exist and can be reasoned against.

## Plan 3 — build status (2026-08-29)

**Built** on branch `feat/abyss-magic` (14 tasks, subagent-driven; 113 tests passing;
whole-branch review = merge-ready, no correctness/determinism/backward-compat blockers).
The depth axis, Curse/strain, curse-only permadeath, magic (mana/ranks/spells as typed
effect records), 3 layers with hazards + relics, and the instinct heal-reflex all work
and interlock end-to-end.

**Known limitations / fast-follows (surfaced by final review):**
- **Mana never regenerates.** `cast` only spends mana; nothing refills it, so the core
  survival loop is currently *one-shot* (an agent can heal a couple of times, then the
  curse counter is gone permanently). `mana_max`-by-depletion growth has no payoff until
  this lands. **#1 follow-up** — natural fit: regen on sleep/rest, or a small passive
  per-tick refill toward `mana_max`. Plan 3 is not demoable without it.
- **The instinct policy does not autonomously drive the Abyss loop.** Rule agents only
  *react* with a heal; they never choose `descend`/`ascend`/`harvest_relic`/`purify`, and
  magic *discovery* isn't reachable autonomously (the experiment branch gates on the
  crafting graph). This is a **deliberate deferral to Plan 4 (LLM minds)** — the dive is
  currently validated only by hand-scripted integration scenarios, not emergent behaviour.
- **Cohesion debt (safe cleanup pass):** three duplicate `_clamp` helpers; dead
  `mana_depletion_frac`/`mana_growth_step` copies in `settings.json` (read from
  `magic.json`); vestigial `Engine(layers=)`, `fall_check(rng=)`, unused `_attack`
  handler; `layers.json` map paths are cwd-relative (latent bug for non-default
  `config_dir`); minor type-hint/sentinel style nits.

## Open questions to revisit

- How do agent-authored discoveries get *sandboxed and verified* before entering canon?
- What's the substrate agents write against — typed effect records, a constrained DSL,
  or real (sandboxed) code?
- How much incoherence is acceptable given the fantasy/magic framing?
- Balancing: does the generative frontier destabilize the deterministic survival core?
