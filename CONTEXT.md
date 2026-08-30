# Genesis — Domain Glossary

The ubiquitous language of the sim. Definitions only — no implementation detail.
Terms sharpened while designing Plan 4 (LLM minds) are marked ★.

## Inhabitants & minds

- **Agent** — an inhabitant of the world: a body (position, layer, inventory,
  needs, strain, mana) driven by a Mind.
- **Mind** ★ — the faculty that decides what an Agent does next. A Mind is either
  an **Instinct** or an LLM **Brain**. Minds never do bookkeeping; they only choose.
- **Instinct** — the deterministic, rule-based Mind. Requires no LLM, always
  available, and is the fallback whenever a Brain is absent, still thinking, or
  returns something invalid. (Called `instinct` in code.)
- **Brain** ★ — an LLM-backed Mind bound to a provider+model (e.g. Groq). Chooses
  among Affordances; never touches raw coordinates.

## Deciding & acting

- **Affordance** ★ — one currently-valid, world-grounded option offered to a Brain
  (e.g. "gather berries at that bush", "descend", "heal the curse"). The engine
  computes the whole set and owns each option's validity and coordinates; the Brain
  only picks one. An Affordance's identity is its verb + its target's own identity
  (a resource's tile, a spell's name), never the Agent's relative position.
- **Goal** ★ — the single Affordance an Agent is currently pursuing. The engine
  drives a Goal to completion across many ticks, re-consulting the Mind only when
  there is no active Goal. A Goal ends when it is satisfied, becomes invalid (its
  target is gone), or is interrupted by a survival-critical need.
- **Action** — one engine-executed step (move, gather, cast, build, descend…).
  One Goal expands into one or more Actions.
- **Decision** ★ — one act of a Brain choosing a Goal from Affordances. Every
  Decision consumes one LLM request, so Decisions are a budgeted resource.

## The world (existing terms)

- **Layer** — one stratum of the Abyss; descending is cheap, ascending inflicts
  Curse. Each Layer demands a higher magic rank than the last.
- **Curse / Strain** — pressure that only rises on ascent, scaled by the Layer
  left behind. Lethal past a threshold; burned down by Healing magic.
- **Mana** — the pool spent to cast magic; grows by depletion, refills over time.
- **Discovery** — a recipe or spell an Agent learns, represented as a typed effect
  record so future generative discovery can be additive.
- **Relic** — deep-layer value that rewards pushing past the safe point.
