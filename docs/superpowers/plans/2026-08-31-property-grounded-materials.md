# Property-Grounded Materials & Fallible Discovery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace exact-item recipe matching with property-grounded discovery (materials carry property tags; recipes require *properties*), and make experimentation genuinely fallible and time-consuming, so the world's discovery space becomes wide, non-linear, and worth exploring.

**Architecture:** A new `PropertyBook` maps every material and discovery result to a set of property tags. `DiscoveryGraph` and `MagicBook` gain a `resolve()` that matches when the *union* of an agent's chosen items' properties covers a recipe's required properties, consuming a deterministic minimal "covering subset". The `experiment_with` action gains a duration (like `cast`) and can fail; item-producing recipes let the graph chain. One cross-system consequence (insulating material slows night warmth loss) proves properties are not inert.

**Tech Stack:** Python 3, `uv` for env/test (`uv run pytest`), JSON config files. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-31-property-grounded-materials-design.md`

## Global Constraints

- **Determinism:** same seed + same config ⇒ identical outcomes. All iteration over sets must be `sorted()`; recipe/spell order is file order; no randomness added.
- **No new dependencies.** Standard library only.
- **No purchased power.** Nothing sells ranks or `mana_max`; capability grows only by use.
- **Style:** match existing code exactly — 4-space indent, `snake_case`, type hints as in neighbouring files, no docstrings unless the surrounding file has them. Minimal diffs.
- **Tests:** `uv run pytest` must be green after every task. Never weaken a test to pass; where semantics are *intentionally* replaced, rewrite the test to the new behaviour (each such case is called out below).
- **Git:** never commit to `main`; work on a feature branch. No Claude/Anthropic attribution in any commit message.
- **Property vocabulary is fixed** (Task 1). Do not invent new tags outside that set.

---

## Task 1: PropertyBook + properties.json

**Files:**
- Create: `configs/properties.json`
- Create: `src/genesis/world/properties.py`
- Test: `tests/test_properties.py`

**Interfaces:**
- Produces: `PropertyBook.from_file(path) -> PropertyBook`; `PropertyBook(materials: dict[str, list[str]])`; `book.props_of(name: str) -> frozenset[str]` (empty frozenset for unknown names).

- [ ] **Step 1: Write `configs/properties.json`**

```json
{
  "materials": {
    "wood":          ["flammable", "fibrous", "solid"],
    "dry_grass":     ["flammable", "fibrous", "light"],
    "flint":         ["sharp", "hard", "sparks"],
    "stone":         ["hard", "heavy", "solid"],
    "berries":       ["edible", "nourishing", "small"],
    "fish":          ["edible", "nourishing", "wet"],
    "water":         ["wet", "solvent"],
    "mana_shard":    ["mana_rich", "luminous"],
    "ember_dust":    ["flammable", "hot", "ether_fire"],
    "arcane_moss":   ["wet", "medicinal", "ether_water"],
    "thick_moss":    ["insulating", "fibrous", "damp"],
    "quarry_dust":   ["gritty", "earthy", "ether_earth"],
    "feather_charm": ["light", "airy", "ether_wind"],
    "ore":           ["hard", "heavy", "metallic", "earthy"],
    "charcoal":      ["flammable", "hot_burning", "sooty"],
    "metal_ingot":   ["hard", "heavy", "metallic"]
  }
}
```

- [ ] **Step 2: Write the failing test** — `tests/test_properties.py`

```python
from genesis.world.properties import PropertyBook

B = PropertyBook.from_file("configs/properties.json")


def test_props_of_known_material():
    assert B.props_of("flint") == frozenset({"sharp", "hard", "sparks"})
    assert "flammable" in B.props_of("wood")


def test_props_of_unknown_is_empty():
    assert B.props_of("nonsense") == frozenset()


def test_produced_items_carry_properties():
    assert "hot_burning" in B.props_of("charcoal")
    assert "metallic" in B.props_of("metal_ingot")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_properties.py -v`
Expected: FAIL with `ModuleNotFoundError: genesis.world.properties`

- [ ] **Step 4: Write `src/genesis/world/properties.py`**

```python
import json
from pathlib import Path


class PropertyBook:
    def __init__(self, materials: dict[str, list[str]]):
        self._props = {k: frozenset(v) for k, v in materials.items()}

    @classmethod
    def from_file(cls, path: str | Path) -> "PropertyBook":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d.get("materials", {}))

    def props_of(self, name: str) -> frozenset:
        return self._props.get(name, frozenset())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_properties.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add configs/properties.json src/genesis/world/properties.py tests/test_properties.py
git commit -m "Add PropertyBook and material property table"
```

---

## Task 2: Property matching in DiscoveryGraph (additive)

Add the new `resolve()` and `covering_subset()` **without touching** `match()` or the config files, so the whole existing suite stays green. `resolve()` is exercised here with inline fixtures.

**Files:**
- Modify: `src/genesis/world/discovery.py`
- Test: `tests/test_resolve.py`

**Interfaces:**
- Consumes: `PropertyBook.props_of` (Task 1); reads `agent.inventory`, `agent.knowledge`.
- Produces:
  - `covering_subset(have: set[str], required: list[str], props_of) -> list[str] | None` (module-level in `discovery.py`) — deterministic minimal cover, or `None` if the union doesn't cover `required`.
  - `DiscoveryGraph(recipes, buildables, props=None)`; `DiscoveryGraph.from_file(path, props=None)`.
  - `graph.resolve(items: list[str], agent) -> tuple[dict, list[str]] | tuple[None, None]` — first recipe (file order) whose prereqs are met and whose covering subset exists and is ≥ `min_items`; returns `(recipe_dict, cover_list)`. Knowledge recipes already in `agent.knowledge` are skipped; `kind:"item"` recipes are never skipped (repeatable production).

- [ ] **Step 1: Write the failing test** — `tests/test_resolve.py`

```python
from genesis.world.discovery import DiscoveryGraph, covering_subset
from genesis.world.properties import PropertyBook
from genesis.world.state import Agent

PROPS = PropertyBook({
    "wood": ["flammable", "fibrous"], "flint": ["sharp", "sparks"],
    "dry_grass": ["flammable", "light"], "berries": ["edible"],
    "ore": ["metallic", "hard"], "charcoal": ["hot_burning", "flammable"],
})
RECIPES = [
    {"name": "fire", "requires": ["flammable", "sparks"], "prereqs": {},
     "kind": "knowledge", "min_items": 2},
    {"name": "cooked_food", "requires": ["edible"],
     "prereqs": {"knowledge": ["fire"]}, "kind": "knowledge", "min_items": 1},
    {"name": "metal_ingot", "requires": ["metallic", "hot_burning"], "prereqs": {},
     "kind": "item", "produces": "metal_ingot", "min_items": 2},
]
G = DiscoveryGraph(RECIPES, {}, props=PROPS)


def _agent(inv, know=None):
    return Agent(id="a", name="A", x=0, y=0, inventory=dict(inv),
                 knowledge=list(know or []))


def test_covering_subset_minimal_and_sorted():
    assert covering_subset({"wood", "flint"}, ["flammable", "sparks"],
                           PROPS.props_of) == ["flint", "wood"]
    assert covering_subset({"berries"}, ["flammable"], PROPS.props_of) is None


def test_resolve_fire_from_two_item_sets():
    r, cover = G.resolve(["wood", "flint"], _agent({"wood": 1, "flint": 1}))
    assert r["name"] == "fire" and cover == ["flint", "wood"]
    r2, _ = G.resolve(["dry_grass", "flint"], _agent({"dry_grass": 1, "flint": 1}))
    assert r2["name"] == "fire"


def test_resolve_ignores_extra_and_respects_min_items():
    # flint alone would cover nothing for fire; single item can't meet min_items 2
    r, _ = G.resolve(["flint"], _agent({"flint": 1}))
    assert r is None


def test_resolve_prereq_and_known_skip():
    a = _agent({"berries": 1})
    assert G.resolve(["berries"], a) == (None, None)          # needs fire
    a.knowledge.append("fire")
    r, cover = G.resolve(["berries"], a)
    assert r["name"] == "cooked_food" and cover == ["berries"]
    a.knowledge.append("cooked_food")
    assert G.resolve(["berries"], a) == (None, None)          # already known


def test_resolve_item_recipe_repeatable_when_known():
    a = _agent({"ore": 1, "charcoal": 1}, know=["metal_ingot"])
    r, cover = G.resolve(["ore", "charcoal"], a)
    assert r["name"] == "metal_ingot" and cover == ["charcoal", "ore"]  # item: not skipped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resolve.py -v`
Expected: FAIL with `ImportError: cannot import name 'covering_subset'`

- [ ] **Step 3: Edit `src/genesis/world/discovery.py`**

Add the module-level function (after the imports, before the class):

```python
def covering_subset(have, required, props_of):
    remaining = set(required)
    used = []
    for item in sorted(have):
        contrib = props_of(item) & remaining
        if contrib:
            used.append(item)
            remaining -= contrib
    return used if not remaining else None
```

Change the constructor and `from_file` to carry `props`, and add `resolve` + a prereq helper:

```python
class DiscoveryGraph:
    def __init__(self, recipes: list[dict], buildables: dict[str, dict], props=None):
        self.recipes = recipes
        self.buildables = buildables
        self.props = props

    @classmethod
    def from_file(cls, path: str | Path, props=None) -> "DiscoveryGraph":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d["recipes"], d["buildables"], props)

    def _prereqs_met(self, recipe: dict, agent) -> bool:
        for tech in recipe.get("prereqs", {}).get("knowledge", []):
            if tech not in agent.knowledge:
                return False
        return True

    def resolve(self, items: list[str], agent):
        if self.props is None:
            return None, None
        have = {it for it in items if agent.inventory.get(it, 0) > 0}
        for recipe in self.recipes:
            if recipe.get("kind", "knowledge") != "item" \
                    and recipe["name"] in agent.knowledge:
                continue
            if not self._prereqs_met(recipe, agent):
                continue
            cover = covering_subset(have, recipe.get("requires", []),
                                    self.props.props_of)
            if cover is None or len(cover) < recipe.get("min_items", 1):
                continue
            return recipe, cover
        return None, None
```

Leave the existing `match()`, `buildable()`, `buildable_names()` methods untouched.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_resolve.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full suite (nothing else should break)**

Run: `uv run pytest -q`
Expected: all green (113 + new tests)

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/discovery.py tests/test_resolve.py
git commit -m "Add property-superset resolve() to DiscoveryGraph"
```

---

## Task 3: Property matching in MagicBook (additive)

**Files:**
- Modify: `src/genesis/world/magic.py`
- Test: `tests/test_magic_resolve.py`

**Interfaces:**
- Consumes: `covering_subset` (Task 2), `PropertyBook.props_of` (Task 1).
- Produces: `MagicBook(..., props=None)`; `MagicBook.from_dict(d, props=None)`; `MagicBook.from_file(path, props=None)`; `magic.resolve(items, agent) -> tuple[dict, list[str]] | tuple[None, None]` — first not-yet-known spell whose property `requires` are covered and cover ≥ `min_items` (default 1).

- [ ] **Step 1: Write the failing test** — `tests/test_magic_resolve.py`

```python
from genesis.world.magic import MagicBook
from genesis.world.properties import PropertyBook
from genesis.world.state import Agent

PROPS = PropertyBook({"mana_shard": ["mana_rich", "luminous"],
                      "ember_dust": ["ether_fire", "flammable"],
                      "wood": ["flammable"]})
BOOK = MagicBook.from_dict({
    "attributes": ["healing", "fire"], "ranks": ["beginner"],
    "rank_xp": {"beginner": 0},
    "spells": [
        {"name": "minor_heal", "attribute": "healing", "requires": ["mana_rich"],
         "prereqs": {}, "base_cast_minutes": 2, "mana_cost": 8, "xp_per_cast": 6,
         "effect": {"type": "reduce_strain", "amount": 20}},
        {"name": "kindle", "attribute": "fire", "requires": ["ether_fire"],
         "prereqs": {}, "base_cast_minutes": 3, "mana_cost": 5, "xp_per_cast": 4,
         "effect": {"type": "warmth", "amount": 25}},
    ], "params": {}}, props=PROPS)


def _agent(inv, know=None):
    return Agent(id="m", name="M", x=0, y=0, inventory=dict(inv),
                 knowledge=list(know or []))


def test_resolve_spell_from_reagent_property():
    r, cover = BOOK.resolve(["mana_shard"], _agent({"mana_shard": 1}))
    assert r["name"] == "minor_heal" and cover == ["mana_shard"]


def test_resolve_skips_known_spell():
    assert BOOK.resolve(["mana_shard"], _agent({"mana_shard": 1},
                        know=["minor_heal"])) == (None, None)


def test_resolve_none_without_matching_property():
    assert BOOK.resolve(["wood"], _agent({"wood": 1})) == (None, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_magic_resolve.py -v`
Expected: FAIL with `TypeError: from_dict() got an unexpected keyword argument 'props'`

- [ ] **Step 3: Edit `src/genesis/world/magic.py`**

Add the import at top: `from genesis.world.discovery import covering_subset`. Thread `props` through construction and add `resolve`:

```python
class MagicBook:
    def __init__(self, attributes, ranks, rank_xp, spells, params, props=None):
        self.attributes = attributes
        self.ranks = ranks
        self.rank_xp = rank_xp
        self.spells = {s["name"]: s for s in spells}
        self.params = params
        self.props = props

    @classmethod
    def from_dict(cls, d, props=None):
        return cls(d["attributes"], d["ranks"], d["rank_xp"],
                   d["spells"], d.get("params", {}), props)

    @classmethod
    def from_file(cls, path, props=None):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")), props)

    def resolve(self, items, agent):
        if self.props is None:
            return None, None
        have = {it for it in items if agent.inventory.get(it, 0) > 0}
        for name, spell in self.spells.items():
            if name in agent.knowledge:
                continue
            req = spell.get("requires", [])
            if not req:
                continue
            cover = covering_subset(have, req, self.props.props_of)
            if cover is None or len(cover) < spell.get("min_items", 1):
                continue
            return spell, cover
        return None, None
```

Leave `spell`, `cast_minutes`, `award_xp`, `discoverable`, `note_cast_mana` untouched.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_magic_resolve.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Full suite**

Run: `uv run pytest -q`
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/magic.py tests/test_magic_resolve.py
git commit -m "Add property-superset resolve() to MagicBook"
```

---

## Task 4: Crafting cutover — configs, action rework, engine wiring

Migrate crafting configs to the property schema, add the chain content, rewrite the `experiment_with` action (timing + `resolve` + consumption + item production), and wire `PropertyBook` into the engine. `match()` becomes a thin property-based shim so `affordances.py` and `instinct.py` keep working unchanged (their full rework is Tasks 6). This is the crafting half of the semantic cutover; the magic half is Task 5.

**Files:**
- Modify: `configs/discoveries.json`, `configs/settings.json`
- Modify: `configs/maps/layer0.json` (add `dry_grass`), `configs/maps/layer2.json` (add `ore`)
- Modify: `src/genesis/world/discovery.py` (replace `match` body with a resolve-based shim)
- Modify: `src/genesis/world/actions.py` (rework `experiment_with`; `metal_tools` gather bonus)
- Modify: `src/genesis/world/engine.py` (build `self.props`, pass to `DiscoveryGraph`)
- Test: rewrite `tests/test_experiment.py`; update `tests/test_discovery.py`, `tests/test_instinct_curiosity.py`, and the two experiment cases in `tests/test_affordances.py`

**Interfaces:**
- Consumes: `graph.resolve` (Task 2), `PropertyBook` (Task 1).
- Produces: `experiment_with` emits `{"type":"discovered","discovery":name}` (knowledge), `{"type":"crafted","produces":item,"discovery":name,"first":bool}` (item), or `{"type":"experiment_failed","items":[...]}`; consumes the covering subset on success; occupies `settings["experiment_minutes"]`. `DiscoveryGraph.match(items, knowledge) -> str | None` now uses property semantics (shim). `Engine(props=...)` and `Engine.props`.

- [ ] **Step 1: Rewrite `configs/discoveries.json`**

```json
{
  "recipes": [
    {"name": "fire", "requires": ["flammable", "sparks"], "prereqs": {},
     "kind": "knowledge", "min_items": 2},
    {"name": "stone_tools", "requires": ["hard", "sharp"], "prereqs": {},
     "kind": "knowledge", "min_items": 2},
    {"name": "cooked_food", "requires": ["edible"],
     "prereqs": {"knowledge": ["fire"]}, "kind": "knowledge", "min_items": 1},
    {"name": "charcoal", "requires": ["flammable"],
     "prereqs": {"knowledge": ["fire"]}, "kind": "item",
     "produces": "charcoal", "min_items": 1},
    {"name": "metal_ingot", "requires": ["metallic", "hot_burning"], "prereqs": {},
     "kind": "item", "produces": "metal_ingot", "min_items": 2},
    {"name": "metal_tools", "requires": ["metallic", "hard"],
     "prereqs": {"knowledge": ["stone_tools"]}, "kind": "knowledge", "min_items": 1}
  ],
  "buildables": {
    "campfire": {"requires": ["fire"], "materials": {"wood": 2},
                 "terrain": ["grass", "sand", "forest", "rock", "marsh"]},
    "torch": {"requires": ["fire"], "materials": {"wood": 1}, "carried": true},
    "hut": {"requires": ["stone_tools"], "materials": {"wood": 4, "stone": 2},
            "terrain": ["grass", "sand"]}
  }
}
```

- [ ] **Step 2: Add settings keys** — edit `configs/settings.json`, add before the closing brace:

```json
  "experiment_minutes": 15,
  "metal_tools_gather_bonus": 3,
  "insulation_warmth_factor": 0.4,
  "experiment_max_items": 6,
  "experiment_affordance_cap": 10
```

(Add a comma to the current last line so the JSON stays valid.)

- [ ] **Step 3: Add new resources to maps**

In `configs/maps/layer0.json`, add to the `resources` array:
```json
    {"type": "dry_grass", "x": 3, "y": 6, "qty": 10}
```
In `configs/maps/layer2.json`, add to the `resources` array:
```json
    {"type": "ore", "x": 6, "y": 5, "qty": 10}
```

- [ ] **Step 4: Replace `match()` with a property shim** — edit `src/genesis/world/discovery.py`, replacing the old `match` method body:

```python
    def match(self, items: list[str], knowledge: list[str]) -> str | None:
        if self.props is None:
            return None
        have = set(items)
        for recipe in self.recipes:
            if recipe.get("kind", "knowledge") != "item" \
                    and recipe["name"] in knowledge:
                continue
            if any(t not in knowledge
                   for t in recipe.get("prereqs", {}).get("knowledge", [])):
                continue
            cover = covering_subset(have, recipe.get("requires", []),
                                    self.props.props_of)
            if cover is None or len(cover) < recipe.get("min_items", 1):
                continue
            return recipe["name"]
        return None
```

- [ ] **Step 5: Rewrite the `experiment_with` branch in `src/genesis/world/actions.py`**

Replace the whole `if verb == "experiment_with":` block (currently lines ~199–221) with:

```python
    if verb == "experiment_with":
        ca = agent.current_action
        if "experiment_until" not in ca:
            ca["experiment_until"] = m + settings.get("experiment_minutes", 15)
            return []
        if m < ca["experiment_until"]:
            return []
        items = action["items"]
        recipe, cover = graph.resolve(items, agent) if graph is not None else (None, None)
        if recipe is not None:
            for it in cover:
                agent.inventory[it] -= 1
            if recipe.get("kind") == "item":
                prod = recipe["produces"]
                agent.inventory[prod] = agent.inventory.get(prod, 0) + 1
                first = recipe["name"] not in agent.knowledge
                if first:
                    agent.knowledge.append(recipe["name"])
                return _finish(agent, {"type": "crafted", "agent": agent.id,
                                       "produces": prod, "discovery": recipe["name"],
                                       "first": first})
            agent.knowledge.append(recipe["name"])
            return _finish(agent, {"type": "discovered", "agent": agent.id,
                                   "discovery": recipe["name"]})
        spell, cover = magic.resolve(items, agent) if magic is not None else (None, None)
        if spell is not None:
            for it in cover:
                agent.inventory[it] -= 1
            agent.knowledge.append(spell["name"])
            agent.attr_rank.setdefault(spell["attribute"], 0)
            agent.attr_xp.setdefault(spell["attribute"], 0.0)
            return _finish(agent, {"type": "discovered", "agent": agent.id,
                                   "discovery": spell["name"]})
        return _finish(agent, {"type": "experiment_failed", "agent": agent.id,
                               "items": items})
```

Note: `magic.resolve` is called here but `configs/magic.json` is still item-shaped until Task 5. That is fine — `magic.resolve` reads the (still item-name) `requires` as property tags, which won't match real materials, so spell discovery via experiment is briefly inert. Task 5 migrates `magic.json` and its tests. The old `magic.discoverable` is left unused by this task and removed in Task 5. Verify `magic.json` spells still validate/cast (untouched fields).

- [ ] **Step 6: Give `metal_tools` a gather bonus** — in `actions.py`, in the `gather` branch, replace the `yield_n = 1 + (...)` line with:

```python
        if "metal_tools" in agent.knowledge:
            yield_n = 1 + settings["metal_tools_gather_bonus"]
        elif "stone_tools" in agent.knowledge:
            yield_n = 1 + settings["stone_tools_gather_bonus"]
        else:
            yield_n = 1
```

- [ ] **Step 7: Wire PropertyBook into the engine** — edit `src/genesis/world/engine.py`.

Add import: `from genesis.world.properties import PropertyBook`.

In `__init__`, add a `props=None` parameter and build it before the graph:
```python
    def __init__(self, state, world_map=None, settings=None, graph=None,
                 maps=None, magic=None, brains=None, queue=None, props=None):
        ...
        self.props = props or PropertyBook.from_file("configs/properties.json")
        self.graph = graph or DiscoveryGraph.from_file("configs/discoveries.json", self.props)
```

In `from_configs`, load the book and pass it to the graph and the constructor:
```python
        props = PropertyBook.from_file(config_dir / "properties.json")
        graph = DiscoveryGraph.from_file(config_dir / "discoveries.json", props)
        ...
        return cls(state, settings=settings, maps=maps, magic=magic, graph=graph,
                   brains=brains, queue=queue, props=props)
```

- [ ] **Step 8: Rewrite `tests/test_experiment.py`** to the new timing + consumption + chain behaviour:

```python
from genesis import load_settings
from genesis.world.state import Agent, WorldState
from genesis.world.grid import WorldMap
from genesis.world.discovery import DiscoveryGraph
from genesis.world.properties import PropertyBook
from genesis.world.actions import validate_action, step_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
P = PropertyBook.from_file("configs/properties.json")
G = DiscoveryGraph.from_file("configs/discoveries.json", P)


def world(agent):
    return WorldState(sim_minutes=0, seed=1, agents=[agent])


def _run(a, st, items):
    a.current_action = {"action": "experiment_with", "items": items}
    step_action(a, st, M, S, G)                 # tick 1: starts the experiment
    st.sim_minutes += S["experiment_minutes"]
    return step_action(a, st, M, S, G)          # resolves


def test_experiment_takes_time_before_resolving():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1},
              current_action={"action": "experiment_with", "items": ["flint", "wood"]})
    ev = step_action(a, world(a), M, S, G)
    assert ev == [] and "fire" not in a.knowledge   # still chanting


def test_experiment_discovers_fire_and_consumes_cover():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1})
    ev = _run(a, world(a), ["flint", "wood"])
    assert "fire" in a.knowledge
    assert ev[0]["type"] == "discovered" and ev[0]["discovery"] == "fire"
    assert a.inventory.get("wood", 0) == 0 and a.inventory.get("flint", 0) == 0


def test_substitution_ember_dust_also_makes_fire():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "ember_dust": 1})
    _run(a, world(a), ["flint", "ember_dust"])
    assert "fire" in a.knowledge


def test_experiment_failed_consumes_nothing():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"berries": 1})
    ev = _run(a, world(a), ["berries"])
    assert ev[0]["type"] == "experiment_failed"
    assert a.inventory == {"berries": 1}


def test_item_recipe_chain_charcoal_then_ingot():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"],
              inventory={"wood": 1, "ore": 1})
    ev = _run(a, world(a), ["wood"])
    assert ev[0]["type"] == "crafted" and a.inventory.get("charcoal", 0) == 1
    assert a.inventory.get("wood", 0) == 0
    ev2 = _run(a, world(a), ["ore", "charcoal"])
    assert ev2[0]["type"] == "crafted" and a.inventory.get("metal_ingot", 0) == 1


def test_validate_rejects_experiment_without_held_items():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1})
    ok, why = validate_action(
        {"action": "experiment_with", "items": ["flint", "wood"]}, a, world(a), M, G)
    assert ok is False and "wood" in why


def test_validate_rejects_experiment_without_graph():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1})
    ok, _ = validate_action(
        {"action": "experiment_with", "items": ["flint", "wood"]}, a, world(a), M, None)
    assert ok is False
```

- [ ] **Step 9: Update `tests/test_discovery.py`** — construct the graph with properties, and add a substitution assertion. Replace the top and the first test:

```python
from genesis.world.discovery import DiscoveryGraph
from genesis.world.properties import PropertyBook

P = PropertyBook.from_file("configs/properties.json")
G = DiscoveryGraph.from_file("configs/discoveries.json", P)


def test_match_simple_recipe():
    assert G.match(["flint", "wood"], []) == "fire"
    assert G.match(["wood", "flint"], []) == "fire"          # order independent
    assert G.match(["flint", "ember_dust"], []) == "fire"    # substitution
```

The remaining `test_discovery.py` assertions (`extra items`, `requires_knowledge`, `none_when_nothing_fits`, `buildable_lookup`) are unchanged and still pass under property semantics.

- [ ] **Step 10: Update `tests/test_instinct_curiosity.py`** — graph needs properties; the "does not re-experiment" case must hold a combination with nothing new to discover.

Replace the header:
```python
from genesis.world.properties import PropertyBook
...
P = PropertyBook.from_file("configs/properties.json")
G = DiscoveryGraph.from_file("configs/discoveries.json", P)
```
Replace `test_does_not_re_experiment_known_recipe` with:
```python
def test_does_not_re_experiment_when_nothing_new():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"],
              inventory={"stone": 1})     # stone alone yields no new discovery
    act = choose_action(a, world(a), M, S, random.Random(1), G)
    assert act["action"] != "experiment_with"
```
(`test_experiments_with_held_materials`, `test_builds_campfire...`, `test_gathers_raw_material...`, `test_without_graph...` are unchanged and pass.)

- [ ] **Step 11: Update the two experiment cases in `tests/test_affordances.py`** so they use property recipes + a PropertyBook (they still exercise the interim `match`-based pre-check; Task 6 replaces them with enumeration).

Add near the top: `from genesis.world.properties import PropertyBook`.
Replace `test_offers_experiment_when_recipe_matches_and_result_unknown` and `test_no_experiment_when_result_already_known` with:
```python
_P = PropertyBook({"wood": ["flammable"], "flint": ["sparks"]})


def test_offers_experiment_when_recipe_matches_and_result_unknown():
    g = DiscoveryGraph(
        recipes=[{"name": "fire", "requires": ["flammable", "sparks"],
                  "prereqs": {}, "kind": "knowledge", "min_items": 2}],
        buildables={}, props=_P)
    a = _agent(inventory={"wood": 1, "flint": 1})
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, S, graph=g)
    exp = [o for o in opts if o["verb"] == "experiment_with"]
    assert exp and set(exp[0]["params"]["items"]) == {"wood", "flint"}


def test_no_experiment_when_result_already_known():
    g = DiscoveryGraph(
        recipes=[{"name": "fire", "requires": ["flammable", "sparks"],
                  "prereqs": {}, "kind": "knowledge", "min_items": 2}],
        buildables={}, props=_P)
    a = _agent(inventory={"wood": 1, "flint": 1}, knowledge=["fire"])
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, S, graph=g)
    assert not any(o["verb"] == "experiment_with" for o in opts)
```

- [ ] **Step 12: Run the full suite**

Run: `uv run pytest -q`
Expected: all green. If `test_integration_dive.py` or `test_instinct_abyss.py` fail, confirm they build the engine via `Engine.from_configs` (which now wires `props`); if they construct a bare `DiscoveryGraph`, pass a `PropertyBook`. Fix by wiring props, never by weakening assertions.

- [ ] **Step 13: Commit**

```bash
git add configs/discoveries.json configs/settings.json configs/maps/layer0.json configs/maps/layer2.json src/genesis/world/discovery.py src/genesis/world/actions.py src/genesis/world/engine.py tests/test_experiment.py tests/test_discovery.py tests/test_instinct_curiosity.py tests/test_affordances.py
git commit -m "Cut crafting discovery over to property-grounded, fallible, timed experiments"
```

---

## Task 5: Magic cutover — spell discovery by property

**Files:**
- Modify: `configs/magic.json` (spell `requires` → properties)
- Modify: `src/genesis/world/magic.py` (remove now-unused `discoverable`)
- Modify: `src/genesis/world/engine.py` (`from_configs` passes `props` to `MagicBook`)
- Test: rewrite `tests/test_magic_discovery.py`

**Interfaces:**
- Consumes: `magic.resolve` (Task 3), the `experiment_with` magic branch (Task 4).
- Produces: spells discoverable from their reagents via properties; `MagicBook` no longer exposes `discoverable`.

- [ ] **Step 1: Migrate `configs/magic.json`** — change each spell's `requires` to a single property tag (keep every other field exactly):

| spell | new `requires` |
|---|---|
| `minor_heal` | `["mana_rich"]` |
| `purify` | `["ether_water"]` |
| `kindle` | `["ether_fire"]` |
| `stone_shape` | `["ether_earth"]` |
| `updraft` | `["ether_wind"]` |

- [ ] **Step 2: Pass props to MagicBook in the engine** — edit `src/genesis/world/engine.py` `from_configs`:
```python
        magic = MagicBook.from_file(config_dir / "magic.json", props)
```
(`props` already exists from Task 4, loaded just above the graph.)

- [ ] **Step 3: Rewrite `tests/test_magic_discovery.py`** to property semantics + timing + a substitution case:

```python
from genesis import load_settings
from genesis.world.actions import step_action
from genesis.world.grid import WorldMap
from genesis.world.magic import MagicBook
from genesis.world.properties import PropertyBook
from genesis.world.state import Agent, WorldState

S = load_settings("configs/settings.json")
WM = WorldMap(["GG", "GG"])
P = PropertyBook({"mana_shard": ["mana_rich", "luminous"],
                  "ember_dust": ["ether_fire", "flammable"], "wood": ["flammable"]})
BOOK = MagicBook.from_dict({
    "attributes": ["healing", "fire"], "ranks": ["beginner"],
    "rank_xp": {"beginner": 0},
    "spells": [
        {"name": "minor_heal", "attribute": "healing", "requires": ["mana_rich"],
         "prereqs": {}, "base_cast_minutes": 2, "mana_cost": 10, "xp_per_cast": 6,
         "effect": {"type": "reduce_strain", "amount": 20}},
        {"name": "kindle", "attribute": "fire", "requires": ["ether_fire"],
         "prereqs": {}, "base_cast_minutes": 3, "mana_cost": 5, "xp_per_cast": 4,
         "effect": {"type": "warmth", "amount": 25}},
    ], "params": {}}, props=P)


def _run(a, st, items):
    a.current_action = {"action": "experiment_with", "items": items}
    step_action(a, st, WM, S, graph=None, magic=BOOK)
    st.sim_minutes += S["experiment_minutes"]
    return step_action(a, st, WM, S, graph=None, magic=BOOK)


def test_experiment_discovers_spell_and_inits_rank():
    a = Agent(id="m", name="M", x=0, y=0, inventory={"mana_shard": 1})
    ev = _run(a, WorldState(0, 1, [a]), ["mana_shard"])
    assert "minor_heal" in a.knowledge and a.attr_rank["healing"] == 0
    assert any(e["type"] == "discovered" for e in ev)
    assert a.inventory.get("mana_shard", 0) == 0        # reagent consumed


def test_substitution_discovers_kindle_from_ether_fire():
    a = Agent(id="m", name="M", x=0, y=0, inventory={"ember_dust": 1})
    _run(a, WorldState(0, 1, [a]), ["ember_dust"])
    assert "kindle" in a.knowledge


def test_experiment_without_matching_property_finds_nothing():
    a = Agent(id="m", name="M", x=0, y=0, inventory={"wood": 1})
    _run(a, WorldState(0, 1, [a]), ["wood"])
    assert "minor_heal" not in a.knowledge
```

- [ ] **Step 4: Remove the unused `discoverable` method** from `src/genesis/world/magic.py` (Task 4's action no longer calls it; confirm with `grep -rn "discoverable" src tests` returns nothing before deleting).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all green. Check `test_instinct_abyss.py` / `test_integration_dive.py` — if either asserts a spell is discovered mid-run, it now needs the reagent present and the engine's `props` wired (done). Fix by wiring, not by weakening.

- [ ] **Step 6: Commit**

```bash
git add configs/magic.json src/genesis/world/magic.py src/genesis/world/engine.py tests/test_magic_discovery.py
git commit -m "Cut spell discovery over to property-grounded matching"
```

---

## Task 6: Fallible experiment affordances + Brain material context

Remove the success pre-check: offer experiment *combinations* the mind can try and fail, with property hints in the labels, and surface carried materials' properties to the Brain.

**Files:**
- Modify: `src/genesis/world/affordances.py`
- Modify: `src/genesis/world/engine.py` (`_context` adds a `materials` map)
- Test: rewrite the two experiment cases in `tests/test_affordances.py`; add `tests/test_affordances_experiment.py`

**Interfaces:**
- Consumes: `graph.props` (Task 2), `settings["experiment_max_items"]`, `settings["experiment_affordance_cap"]`.
- Produces: experiment affordances with `id` `"experiment:<a>+<b>"`, `params={"items":[...]}`, `label` including each item's sorted properties; offered whenever the agent holds ≥1 combinable item, **without** checking success. `_context` returns a `"materials"` key mapping each held item to its sorted property list.

- [ ] **Step 1: Write the failing test** — `tests/test_affordances_experiment.py`

```python
from genesis.world.affordances import affordances
from genesis.world.discovery import DiscoveryGraph
from genesis.world.properties import PropertyBook
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GGGG", "GGGG", "GGGG", "GGGG"])
S = {"campfire_warmth_radius": 2, "experiment_max_items": 6,
     "experiment_affordance_cap": 10}
P = PropertyBook({"wood": ["flammable"], "flint": ["sparks"], "stone": ["hard"]})
G = DiscoveryGraph(recipes=[], buildables={}, props=P)


def _a(**kw):
    return Agent(id="a", name="A", x=0, y=0, **kw)


def test_offers_pairs_without_success_precheck():
    a = _a(inventory={"wood": 1, "flint": 1, "stone": 1})
    opts = affordances(a, WorldState(0, 1, [a]), WM, S, graph=G)
    exp = {o["id"] for o in opts if o["verb"] == "experiment_with"}
    # C(3,2) pairs + the full set, even though no recipe exists (fallible)
    assert "experiment:flint+wood" in exp
    assert "experiment:flint+stone" in exp
    assert "experiment:stone+wood" in exp
    assert any(id.count("+") == 2 for id in exp)   # combine-all option


def test_label_includes_properties():
    a = _a(inventory={"wood": 1, "flint": 1})
    opts = affordances(a, WorldState(0, 1, [a]), WM, S, graph=G)
    exp = next(o for o in opts if o["verb"] == "experiment_with")
    assert "flammable" in exp["label"] and "sparks" in exp["label"]


def test_lone_item_still_offered():
    a = _a(inventory={"mana_shard": 1})
    g = DiscoveryGraph(recipes=[], buildables={},
                       props=PropertyBook({"mana_shard": ["mana_rich"]}))
    opts = affordances(a, WorldState(0, 1, [a]), WM, S, graph=g)
    assert any(o["id"] == "experiment:mana_shard" for o in opts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_affordances_experiment.py -v`
Expected: FAIL (old affordances offers a single `id="experiment"` gated on a match)

- [ ] **Step 3: Replace the experiment block in `src/genesis/world/affordances.py`** (the `# experiment_with:` block, ~lines 40–49) with:

```python
    # experiment_with: offer combinations to TRY (may fail) — no success pre-check
    if graph is not None:
        held = sorted(k for k, v in agent.inventory.items() if v > 0)
        pool = held[: settings.get("experiment_max_items", 6)]
        combos: list[list[str]] = []
        for i in range(len(pool)):
            for j in range(i + 1, len(pool)):
                combos.append([pool[i], pool[j]])
        if pool:
            combos.append(list(pool))          # combine everything (lone item incl.)
        cap = settings.get("experiment_affordance_cap", 10)
        for combo in combos[:cap]:
            if graph.props is not None:
                shown = ", ".join(
                    f"{it} [{','.join(sorted(graph.props.props_of(it)))}]"
                    for it in combo)
            else:
                shown = ", ".join(combo)
            opts.append({"id": f"experiment:{'+'.join(combo)}",
                         "verb": "experiment_with", "params": {"items": combo},
                         "label": f"experiment: {shown}", "dir": "here", "dist": 0})
```

Note: when the agent holds a single item, `combos` is just `[[item]]`, so the lone item is offered as `experiment:<item>` (preserves single-reagent spell discovery).

- [ ] **Step 4: Run the new test to verify it passes**

Run: `uv run pytest tests/test_affordances_experiment.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Update the two interim experiment cases in `tests/test_affordances.py`** — the pre-check they asserted is gone. Replace both (from Task 4 Step 11) with:

```python
def test_experiment_offered_without_success_precheck():
    g = DiscoveryGraph(recipes=[], buildables={},
                       props=PropertyBook({"wood": ["flammable"], "flint": ["sparks"]}))
    a = _agent(inventory={"wood": 1, "flint": 1})
    st = WorldState(0, 1, [a])
    opts = affordances(a, st, WM, {**S, "experiment_max_items": 6,
                                   "experiment_affordance_cap": 10}, graph=g)
    assert any(o["id"] == "experiment:flint+wood" for o in opts)
```

(Delete `test_no_experiment_when_result_already_known` — experiments are no longer gated on being unknown; a known combo simply resolves to `experiment_failed`/`experiment_known` at action time, which is covered in `test_experiment.py`.)

- [ ] **Step 6: Add carried-material properties to the Brain context** — edit `_context` in `src/genesis/world/engine.py`:

```python
    def _context(self, agent, menu):
        return {"persona": agent.persona, "needs": vars(agent.needs),
                "strain": agent.strain, "mana": agent.mana, "mana_max": agent.mana_max,
                "layer": agent.layer, "inventory": dict(agent.inventory),
                "materials": {it: sorted(self.props.props_of(it))
                              for it in agent.inventory if agent.inventory[it] > 0},
                "known": list(agent.knowledge), "options": menu}
```

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -q`
Expected: all green. If `test_cli.py` / `test_engine_minds.py` assert on affordance ids or context keys, update them to the new experiment ids / added `materials` key (behaviour intentionally changed).

- [ ] **Step 8: Commit**

```bash
git add src/genesis/world/affordances.py src/genesis/world/engine.py tests/test_affordances.py tests/test_affordances_experiment.py
git commit -m "Offer fallible experiment combinations and surface material properties to Brains"
```

---

## Task 7: Insulation — one cross-system property consequence

Carrying an `insulating` material slows night warmth loss. Adds `thick_moss` to the Forest and threads a `props_of` lookup into `tick_needs`.

**Files:**
- Modify: `configs/maps/layer1.json` (add `thick_moss`)
- Modify: `src/genesis/world/needs.py` (`tick_needs` gains `props_of=None`; insulation in night decay)
- Modify: `src/genesis/world/engine.py` (`tick` passes `self.props.props_of`)
- Test: `tests/test_insulation.py`

**Interfaces:**
- Consumes: `PropertyBook.props_of` (Task 1), `settings["insulation_warmth_factor"]` (Task 4).
- Produces: `tick_needs(agent, sim_minutes, settings, near_warmth=False, props_of=None)` — night warmth decay is multiplied by `insulation_warmth_factor` when the agent holds any item whose properties include `insulating`.

- [ ] **Step 1: Add `thick_moss` to the Forest** — `configs/maps/layer1.json`, add to `resources`:
```json
    {"type": "thick_moss", "x": 2, "y": 6, "qty": 10}
```

- [ ] **Step 2: Write the failing test** — `tests/test_insulation.py`

```python
from genesis import load_settings
from genesis.world.state import Agent, WorldState
from genesis.world.needs import tick_needs
from genesis.world.properties import PropertyBook

S = load_settings("configs/settings.json")
P = PropertyBook.from_file("configs/properties.json")
MIDNIGHT = 0


def _warmth_after_night_tick(inventory):
    a = Agent(id="a", name="A", x=0, y=0, inventory=dict(inventory))
    a.needs.warmth = 50.0
    tick_needs(a, MIDNIGHT, S, near_warmth=False, props_of=P.props_of)
    return a.needs.warmth


def test_insulating_item_slows_night_warmth_loss():
    plain = 50.0 - _warmth_after_night_tick({})            # loss with nothing
    insulated = 50.0 - _warmth_after_night_tick({"thick_moss": 1})
    assert insulated < plain
    assert abs(insulated - plain * S["insulation_warmth_factor"]) < 1e-9


def test_no_insulation_without_props_of():
    a = Agent(id="a", name="A", x=0, y=0, inventory={"thick_moss": 1})
    a.needs.warmth = 50.0
    tick_needs(a, MIDNIGHT, S, near_warmth=False)          # props_of defaults None
    assert a.needs.warmth == 50.0 - S["warmth_decay_night_per_min"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_insulation.py -v`
Expected: FAIL (`tick_needs() got an unexpected keyword argument 'props_of'`)

- [ ] **Step 4: Edit `src/genesis/world/needs.py`** — add the parameter and the insulation multiplier in the night-decay branch:

```python
def tick_needs(agent: Agent, sim_minutes: int, settings: dict,
               near_warmth: bool = False, props_of=None) -> list[dict]:
```
Replace the final `else:` warmth branch (currently lines ~45–49) with:
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

- [ ] **Step 5: Thread props into the engine tick** — `src/genesis/world/engine.py`, in `tick`:
```python
            events += tick_needs(agent, minute, self.settings,
                                 near_warmth=near, props_of=self.props.props_of)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_insulation.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Full suite**

Run: `uv run pytest -q`
Expected: all green (existing `tick_needs` callers unaffected — `props_of` defaults to `None`).

- [ ] **Step 8: Commit**

```bash
git add configs/maps/layer1.json src/genesis/world/needs.py src/genesis/world/engine.py tests/test_insulation.py
git commit -m "Add insulating-material night-warmth consequence"
```

---

## Self-Review

**Spec coverage:**
- §4 property model → Task 1. §5 discovery-record schema → Tasks 2/4 (crafting), 3/5 (spells). §6 matching algorithm (`covering_subset`, first-match, `min_items`) → Task 2. §7 fallible experimentation (no pre-check, timing, consumption) → Task 4 (timing/consume) + Task 6 (fallible affordances). §8 chains & item results → Task 4 (charcoal→ingot→tools). §9 minds & properties → Task 6 (Brain context) + Task 4 (Instinct via property `match` shim; note the spec's "shares a property" phrasing is imprecise — productive combos are complementary, so Instinct picks the first combo `resolve`/`match` says is *productive and new*, which is deterministic and correct). §10 insulation → Task 7. §11 migration/back-compat → covered file-by-file across Tasks 4/5/7. §12 determinism → Global Constraints + `sorted()` everywhere. §13 test plan → tests across all tasks. §14 roadmap edit → out of scope per spec (noted, not a task).
- Gap check: the spec's `metal_tools` gather bonus → Task 4 Step 6. New materials `dry_grass`/`ore`/`thick_moss` placed → Tasks 4/7. All covered.

**Placeholder scan:** No TBD/TODO; every code and test step contains literal content.

**Type consistency:** `resolve()` returns `(recipe_dict, cover_list)` in both `DiscoveryGraph` (Task 2) and `MagicBook` (Task 3), consumed identically in Task 4's action. `covering_subset(have, required, props_of)` signature identical in Tasks 2/3/4/6. `PropertyBook.props_of` used with the same signature in Tasks 2/3/6/7. `props` parameter name consistent across `DiscoveryGraph`, `MagicBook`, `Engine`, and `tick_needs(props_of=...)`. Event types (`discovered`/`crafted`/`experiment_failed`) consistent between Task 4 action and its tests.

---

## Execution note

`test_integration_dive.py`, `test_instinct_abyss.py`, `test_cli.py`, `test_engine_minds.py`, and `test_engine_layers.py` are end-to-end and may touch discovery/affordances/needs indirectly. They are expected to stay green because the engine wires `props` (Tasks 4/5/7); if one fails, the fix is to wire the `PropertyBook` through the construction path it uses — never to relax an assertion. Run `uv run pytest -q` after each task to catch this immediately.
