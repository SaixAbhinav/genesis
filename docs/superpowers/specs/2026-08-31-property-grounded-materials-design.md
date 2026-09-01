# Genesis — Property-Grounded Materials & Fallible Discovery (Design Spec)

**Date:** 2026-08-31
**Status:** Approved design (brainstormed 2026-08-31); ready for implementation plan
**Branch target:** new feature branch off `feat/abyss-magic` (or `main` once that merges)
**Roadmap slot:** the first *density layer* of the world-enrichment direction. This
supersedes the earlier "Economy of desire" framing of roadmap item **E**: instead of a
scripted descend→spend→survive economy loop, we make the world **richer and more
interconnected** and let LLM minds explore it in any order. See "Relation to the roadmap"
below.

---

## 1. Context & problem

The engine (Plans 1–4a, all merged) has depth, Curse/strain, permadeath, magic
(mana + ranks + spells), discovery/crafting, and an LLM Brain seam. Live runs exposed
that the world is **thin**: there is little to *figure out*. Two concrete symptoms in the
current discovery system:

- **Discovery is exact-string matching.** `DiscoveryGraph.match()`
  ([discovery.py:16](../../../src/genesis/world/discovery.py)) matches a recipe only when
  the agent holds the *exact named items* (`{flint, wood} → fire`). There is one path to
  each result and no notion of *why* those items work. Nothing substitutes, nothing
  generalizes, nothing chains in a non-obvious way.
- **Experiments cannot fail.** The `experiment_with` affordance is only offered when
  `graph.match()` has *already* confirmed the combo succeeds
  ([affordances.py:44](../../../src/genesis/world/affordances.py)). The engine spoon-feeds
  the answer, so agents never try-and-fail — there is no real "figuring out."

**Goal of this spec:** replace exact-item matching with **property-grounded discovery**
(materials carry property *tags*; recipes require *properties*, not names), and make
**experimentation genuinely fallible**, so the discovery space becomes wide, non-linear,
and something LLM minds actually explore. Inspiration: **RimWorld** — its "stuff" system
(a thing's material determines its properties and outcomes), skills that level by *doing*
(never bought), and emergent behaviour from *systems interacting under pressure* rather
than scripted goals.

### Design decisions locked during brainstorming
- **Approach 1 (property-set superset)**, not property-counts (Approach 2) or
  effects-computed-from-properties (Approach 3). Those two are named as future upgrades.
- **No purchased power.** Ranks still grow only by casting; `mana_max` still grows only by
  depletion. Nothing in this spec sells capability. (Explicitly rejected during
  brainstorming as gamey.)
- **Experiments cost time; failures are free.** Exploration is cheap enough to actually do;
  material cost is paid on success/production.
- **One cross-system consequence ships now** (§10), to prove properties are not inert
  decoration. Broader property-driven physics is deferred.

## 2. Goals & non-goals

**Goals**
1. Materials and discovery *results* carry property tags, defined in config data.
2. Recipes and spell-discovery match on the **union of chosen items' properties ⊇ required
   properties**, deterministically, first-match-wins.
3. `experiment_with` is offered as combinations the mind can *try and fail*, not a
   pre-confirmed answer. Experiments take in-world time.
4. Discoveries can **produce items with properties**, so the graph *chains* (a made item is
   an input to a deeper recipe). Ship at least one multi-step chain.
5. Properties are visible to minds so a **Brain can reason** toward combinations, and the
   deterministic **Instinct** has a curiosity policy so the system is demoable/testable
   without LLM calls.
6. All existing behaviour that should still work keeps working; the 113-test suite stays
   green except where old exact-item semantics are *intentionally* replaced (documented).

**Non-goals (this spec)**
- Numeric property attributes / distinct-item roles (Approach 2).
- Effects synthesized from properties / LLM-coined recipes (Approach 3, Plan 8).
- Full property physics (fire spread, temperature fields, toxicity) beyond the single
  consequence in §10.
- Any economy sink, currency, home-upgrade store, or purchased stats.
- Memory, conversation, factions (later roadmap items).

## 3. Design overview

The discovery loop becomes:

```
hold some items ──▶ choose a combination to experiment with (may fail)
        │                        │
        │                   time passes
        ▼                        ▼
  properties of items    union(properties) ⊇ recipe.requires  AND  prereqs met?
                                 │                    │
                            no ──┘                    └── yes ──▶ learn knowledge
                        (experiment_failed,                      and/or produce item,
                         nothing consumed)                       consume the covering set
```

Width comes from substitution (many item-sets satisfy one property requirement). Depth
comes from produced items re-entering as inputs. "Figuring out" comes from experiments
that can fail plus properties the mind can reason over.

## 4. Property model — `configs/properties.json` (new)

A single table maps every material **and every discovery result** to a set of property
tags (unordered, deduplicated strings). Tags have no values in v1.

```json
{
  "materials": {
    "wood":         ["flammable", "fibrous", "solid"],
    "dry_grass":    ["flammable", "fibrous", "light"],
    "flint":        ["sharp", "hard", "sparks"],
    "stone":        ["hard", "heavy", "solid"],
    "berries":      ["edible", "nourishing", "small"],
    "fish":         ["edible", "nourishing", "wet"],
    "water":        ["wet", "solvent"],
    "mana_shard":   ["mana_rich", "luminous"],
    "ember_dust":   ["flammable", "hot", "ether_fire"],
    "arcane_moss":  ["wet", "medicinal", "ether_water"],
    "thick_moss":   ["insulating", "fibrous", "damp"],
    "quarry_dust":  ["gritty", "earthy", "ether_earth"],
    "feather_charm":["light", "airy", "ether_wind"],
    "ore":          ["hard", "heavy", "metallic", "earthy"],

    "charcoal":     ["flammable", "hot_burning", "sooty"],
    "metal_ingot":  ["hard", "heavy", "metallic"]
  }
}
```

**Starter vocabulary (~18 tags)** across four families, so the plan authors against a
fixed set (no free-invented tags):
- *physical:* `flammable, fibrous, solid, sharp, hard, heavy, light, small, gritty`
- *reactive:* `sparks, hot, hot_burning, wet, solvent`
- *biological:* `edible, nourishing, medicinal`
- *material/other:* `metallic, earthy, luminous, insulating, damp, sooty`
- *magical (ether):* `mana_rich, ether_fire, ether_water, ether_wind, ether_earth`

A small loader (`PropertyBook`) exposes `props_of(name) -> frozenset[str]`, returning an
empty set for unknown names (an unknown material simply can't satisfy any property).

**New materials introduced by this spec** (all placed as real resources, §7/§10/§8):
`dry_grass` (surface, alternate fire path), `thick_moss` (Forest, warmth consequence),
`ore` (Great Fault, metal chain). Produced items: `charcoal`, `metal_ingot`.

## 5. Discovery record schema

Every discovery — crafting recipe **and** spell — is a typed effect record. This unifies
the schema the Plan 8 generative engine will one day coin into (the roadmap's "typed
effect record" guardrail).

```jsonc
{
  "name": "charcoal",
  "requires": ["flammable"],            // PROPERTIES that the item-union must cover
  "prereqs":  { "knowledge": ["fire"] },// optional: known tech and/or attribute ranks
  "min_items": 1,                        // floor on the size of the covering subset (default 1)
  "kind": "item",                        // "knowledge" (unlocks a capability) | "item" (produces a material)
  "produces": "charcoal"                 // for kind:"item" — the material name added to inventory
  // "effect": {...}                     // for spells only — the cast effect (unchanged shape)
}
```

- `requires` is a **set of property tags**, not item names. This is the whole change.
- `prereqs.knowledge` = list of tech that must be in `agent.knowledge`.
  `prereqs.attribute_rank` = `{attr: rank_name}` (spells only; unchanged meaning).
- `kind:"knowledge"` results append to `agent.knowledge` (as today: `fire`, `stone_tools`).
  `kind:"item"` results add `produces` to `agent.inventory` and can be discovered/produced
  repeatedly.
- Spell records keep their existing `attribute / base_cast_minutes / mana_cost /
  xp_per_cast / effect` fields; only their `requires` changes from an item list to a
  property list (§11).

### Starter recipes (crafting) — `configs/discoveries.json`

| name | requires (props) | prereqs | kind | produces | min_items | example inputs |
|---|---|---|---|---|---|---|
| `fire` | `flammable, sparks` | — | knowledge | — | 2 | wood+flint, dry_grass+flint, ember_dust+flint |
| `stone_tools` | `hard, sharp` | — | knowledge | — | 2 | stone+flint |
| `cooked_food` | `edible` | knows `fire` | knowledge | — | 1 | berries (or fish) |
| `charcoal` | `flammable` | knows `fire` | item | `charcoal` | 1 | wood → charcoal |
| `metal_ingot` | `metallic, hot_burning` | — | item | `metal_ingot` | 2 | ore + charcoal |
| `metal_tools` | `metallic, hard` | knows `stone_tools` | knowledge | — | 1 | metal_ingot |

**The demonstrating chain** (goal #4): `wood` + `fire` → **charcoal**; deep-only `ore`
(Great Fault) + `charcoal` → **metal_ingot**; `metal_ingot` → **metal_tools** (a better
gather bonus than stone_tools). This shows (a) width — three item-sets make fire; and
(b) depth tied to descent — the metal ladder is unreachable without going deep for `ore`,
so density and the Abyss's downward pull reinforce each other *without* a scripted economy.

`metal_tools` grants a gather bonus: `actions.py` gather currently keys the bonus on
`"stone_tools" in agent.knowledge`; extend it to also honour `metal_tools` with
`settings["metal_tools_gather_bonus"]` (a small additive step above stone tools).

### Starter recipes (spells) — `configs/magic.json`
Each spell's `requires` migrates to the *defining property* of its current reagent, so
existing single-reagent discovery is **preserved** while gaining substitutability:

| spell | requires (props) | discoverable from (today, still works) |
|---|---|---|
| `minor_heal` | `mana_rich` | mana_shard |
| `purify` | `ether_water` | arcane_moss |
| `kindle` | `ether_fire` | ember_dust |
| `stone_shape` | `ether_earth` | quarry_dust |
| `updraft` | `ether_wind` | feather_charm |

## 6. Matching algorithm (deterministic)

Given the agent's chosen combination `items` (a list of inventory item names, each held in
qty ≥ 1) and the agent's `knowledge`/ranks:

```
def resolve_experiment(items, agent, recipes, props_of):
    have = { it for it in items if agent.inventory.get(it, 0) > 0 }
    for recipe in recipes:                      # file order == priority; first match wins
        if not prereqs_met(recipe, agent):      # knowledge + attribute_rank
            continue
        cover = covering_subset(have, recipe["requires"], props_of)
        if cover is None:                        # union of properties didn't cover
            continue
        if len(cover) < recipe.get("min_items", 1):
            continue
        return recipe, cover
    return None, None

def covering_subset(have, required_props, props_of):
    remaining = set(required_props)
    used = []
    for item in sorted(have):                    # sorted => deterministic
        contrib = props_of(item) & remaining
        if contrib:
            used.append(item)
            remaining -= contrib
    return used if not remaining else None
```

- **Union-superset semantics:** the union of the chosen items' properties must cover
  `requires`. Extra properties are harmless.
- **Covering subset** = the deterministic minimal set of items that actually supplied a
  required property. Only these are consumed (§7), so substitution is preserved on the cost
  side too ("you spend what you used"; unused extras the mind threw in are not consumed).
- **`min_items`** guards against a single super-item trivially satisfying a multi-property
  recipe.
- **First-match-wins in declared order.** When a combination could satisfy several recipes
  (e.g. `ember_dust`+`flint` covers both `fire` and, via ember_dust alone, would cover the
  `kindle` spell), the crafting graph is consulted before the spell book, and within each,
  file order decides. This is deterministic and documented; authors order recipes
  intentionally.

Two matchers run in sequence inside `experiment_with`, as today: crafting
(`DiscoveryGraph`) first, then magic (`MagicBook`). Both switch to property semantics.

## 7. Fallible experimentation

### Affordances (no pre-check)
`affordances.py` stops calling `graph.match()` to gate the option. Instead, when the agent
holds ≥1 combinable item it surfaces **candidate combinations** as distinct affordances,
each with an explicit `items` list and *without* checking whether they will succeed:

- Consider up to `K` (default 6) distinct held item types, sorted.
- Emit one affordance per **unordered pair** of held types (`C(K,2)`), plus one
  "combine everything you hold" affordance. When the agent holds only a single item type,
  that lone item is still offered as an experiment (this is how a single-reagent spell —
  e.g. `mana_shard` → `minor_heal` — remains discoverable, preserving current behaviour).
- Cap the total experiment affordances emitted (default 10) for prompt sanity; the cap is
  logged/deterministic (sorted order), never silent beyond the note.
- Each affordance label includes the items and their properties, e.g.
  `experiment: wood [flammable,fibrous,solid] + flint [sharp,hard,sparks]`, so a Brain can
  reason about *why* a combination might react.

### Action + timing
`experiment_with` gains a duration, mirroring `cast`:
- On first tick, set `current_action["experiment_until"] = m + settings["experiment_minutes"]`
  (default 15) and return `[]` (working).
- While `m < experiment_until`, return `[]`.
- When done, run `resolve_experiment` and emit the outcome.

Time cost means brute-forcing has real opportunity cost (needs decay, Curse pressure keep
running), which is the intended check on mindless enumeration — matching RimWorld's
"research is an activity that takes time."

### Consumption rule
- **Failure** (no recipe matched): consume **nothing**; emit
  `{type:"experiment_failed", items:[...]}`. Cheap to explore.
- **Success:** consume **one unit of each item in the covering subset**; then:
  - `kind:"knowledge"` and not already known → append to `knowledge`, emit
    `{type:"discovered", discovery:name}`.
  - `kind:"knowledge"` already known → emit `{type:"experiment_known"}`, consume nothing
    (no point re-learning).
  - `kind:"item"` → add `produces` to inventory (this is production, repeatable), emit
    `{type:"crafted"/"discovered", produces:name}`. First time also counts as discovery.

This preserves substitution, makes production cost real, and keeps learning affordable.
(Note: this changes the current behaviour where discovering `fire` consumed nothing — see
§11 for the tests that intentionally change.)

## 8. Chains & produced items

Produced items (`charcoal`, `metal_ingot`) get entries in `properties.json` and can be
gathered into experiments like any material. The starter chain (§5) proves depth compounds
and ties the deepest rung to descent (`ore` is Great-Fault-only). No new subsystem — just
recipes whose inputs include other recipes' outputs.

## 9. Minds & properties

- **Brain (LLM):** the affordance labels already carry item properties (§7). Additionally,
  the Brain prompt context (`mind/llm_brain.py`) includes a compact "materials you carry
  and their properties" block, so the model can plan combinations it hasn't been told will
  work. This is what turns width into *reasoned* discovery rather than luck.
- **Instinct (deterministic):** gains a **curiosity** branch (there is already
  `test_instinct_curiosity`). When the agent is safe (no urgent need/Curse action pending)
  and holds ≥2 items, Instinct picks the first experiment affordance (sorted, deterministic)
  whose two items **share ≥1 property** — a cheap "these might react" heuristic — and that
  it is not already known to produce. This drives autonomous discovery for demos/tests with
  zero LLM cost, without brute-forcing every combination.

## 10. One cross-system consequence — insulation

To prove properties act outside the crafting bench: **carrying an `insulating` material
slows warmth loss at night.** In `tick_needs` ([needs.py:46](../../../src/genesis/world/needs.py)),
the night-decay branch checks whether the agent holds any item whose properties include
`insulating`; if so, multiply the decay rate by `settings["insulation_warmth_factor"]`
(default `0.4`). Implemented via a `props_of` lookup passed into `tick_needs`.

`thick_moss` (Forest) is the starter insulating material, giving the Forest of Temptation a
reason to gather beyond passing through — deeper layers holding materially useful stuff,
which is the density we want (and a hook the "society/economy" work can build on later,
un-scripted). This is the *only* consequence in scope; fire spread, temperature fields, and
toxicity are named follow-ups, not built here.

## 11. Migration & back-compat

Files touched and how:

- **`configs/properties.json`** — new. Property table (§4).
- **`src/genesis/world/properties.py`** — new. `PropertyBook.props_of(name)`; loader.
- **`discovery.py`** — `match()` reworked to property-superset + covering subset (§6);
  add a `produces`/`kind` accessor. Keep `buildable*` untouched.
- **`magic.py`** — `discoverable()` reworked to property-superset over reagent properties;
  spells' `requires` reinterpreted as properties. `note_cast_mana`, `award_xp`, `cast_*`
  unchanged.
- **`actions.py`** — `experiment_with`: add duration/timing, run the new resolver, apply the
  consumption rule, handle `kind:"item"` production; gather bonus honours `metal_tools`.
- **`affordances.py`** — emit fallible experiment combinations (§7); drop the `graph.match`
  pre-check; add property hints to labels.
- **`instinct.py`** — curiosity branch (§9).
- **`mind/llm_brain.py`** — carried-materials-and-properties block in prompt context (§9).
- **`needs.py`** — insulation hook (§10); `tick_needs` gains a `props_of` parameter (default
  a no-op that returns empty set, so existing callers/tests are unaffected until wired).
- **`configs/discoveries.json`, `configs/magic.json`** — recipes/spells migrated to property
  `requires`; new chain recipes added.
- **`configs/maps/layer0.json`** (`dry_grass`), **`layer1.json`** (`thick_moss`),
  **`layer2.json`** (`ore`) — new resources.
- **`configs/settings.json`** — `experiment_minutes`, `insulation_warmth_factor`,
  `metal_tools_gather_bonus`.

**Tests that intentionally change** (semantics replaced by design — updated to the new
behaviour, never edited merely to pass):
- `test_discovery.py`, `test_experiment.py` — exact-item expectations → property semantics;
  discovering a recipe now consumes the covering subset.
- `test_magic_discovery.py` — spell discovery still succeeds from the same reagents, now via
  properties; add a substitution case.
- `test_affordances.py` — experiment affordance is now offered without a success pre-check.
- `test_instinct_curiosity.py` — asserts the new curiosity heuristic.

All other tests must stay green unchanged.

## 12. Determinism

- Property tables and recipe lists are ordered; matching iterates in file order.
- `covering_subset` iterates `sorted(have)`; affordance enumeration iterates sorted item
  types and capped counts.
- No randomness introduced. Experiment timing is deterministic (minute arithmetic).
- Same seed + same config ⇒ identical discovery outcomes, as required by the engine's
  determinism contract.

## 13. Testing plan (new tests)

1. **Property loader:** `props_of` returns the right set; unknown ⇒ empty set.
2. **Superset match:** `{wood, flint}` and `{dry_grass, flint}` and `{ember_dust, flint}`
   all discover `fire`; `{wood, stone}` does not.
3. **Covering subset / consumption:** discovering `fire` from `{wood, flint, berries}`
   consumes exactly one `wood` and one `flint`, leaves `berries`.
4. **min_items guard:** a single item that happens to hold two required props does not
   satisfy a `min_items:2` recipe.
5. **Prereq gating:** `charcoal` not discoverable without `fire`; becomes discoverable after.
6. **Item production & chain:** produce `charcoal`; then `ore + charcoal` → `metal_ingot`;
   then `metal_ingot` → `metal_tools`; `metal_tools` raises gather yield.
7. **Failure path:** an incoherent combination emits `experiment_failed` and consumes
   nothing.
8. **Timing:** experiment occupies `experiment_minutes` before resolving.
9. **First-match determinism:** a combination satisfying two recipes resolves to the
   declared-first one, reproducibly.
10. **Affordances:** experiment combinations are offered for held items without a success
    pre-check; labels include properties; cap respected.
11. **Instinct curiosity:** picks a property-sharing combination deterministically when safe.
12. **Spell migration:** all five spells still discoverable from their current reagents;
    one substitution case passes.
13. **Insulation:** carrying `thick_moss` reduces night warmth loss by the configured
    factor; carrying nothing insulating does not.
14. **Regression:** full suite green except the documented intentional changes.

Run with `uv run pytest`.

## 14. Relation to the roadmap

The roadmap's item **E** was framed as an "economy of desire" — a scripted
descend→spend→survive loop with relics/mana spendable into power. During this brainstorm
the direction was **redefined**: build a *rich, dense, interconnected world* the LLM minds
explore in any order (RimWorld-style systemic emergence), not a prescribed loop, and never
sell capability. Property-grounded materials is the first density layer of that direction.
The roadmap doc should be updated to reflect this reframe (item E → "World enrichment:
density layers", with property-grounded discovery as the first), but that edit is out of
scope for this spec's implementation and can be a small standalone doc change.

## 15. Deferred / explicitly out of scope
- Approach 2 (property counts / distinct-item roles) and Approach 3 (effects computed from
  properties / LLM-coined recipes, Plan 8).
- Property physics beyond §10 (fire spread, temperature, toxicity, decay).
- Any economy/currency/home-store/purchased power.
- Exposing the full property graph to a benchmark scoreboard.

## 16. Open questions
- **Prompt budget:** does the carried-materials-and-properties block (§9) meaningfully grow
  Brain token cost? If so, cap it to the N most relevant items. (Decide during the LLM-facing
  task; deterministic mechanics don't depend on it.)
- **Experiment affordance explosion:** is `C(6,2)+1` combinations the right cap, or should
  Instinct/Brain get a smaller curated set? Tunable via the `K`/cap settings; start with the
  defaults above and revisit after a live run.
- **Should knowledge-discovery consume inputs at all?** Chosen: yes (uniform rule, adds
  cost). Revisit if it makes early survival too punishing in playtests.
