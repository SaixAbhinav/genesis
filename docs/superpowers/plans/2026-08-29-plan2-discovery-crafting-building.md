# Genesis Plan 2: Discovery, Crafting & Building — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rule-driven agents can now *experiment* to discover recipes (fire, stone tools, cooked food), *build* structures (campfire, hut, torch), and gain real payoffs from what they know — better gather yields, warmer nights, safer sleep.

**Architecture:** Extends the Plan 1 deterministic engine. A `DiscoveryGraph` (loaded from config) maps item combinations → discoveries and defines buildable structures. Two new validated actions (`experiment_with`, `build`) plug into the existing `step_action` dispatcher. Structures live in `WorldState.structures`; their effects flow through the existing `tick_needs` (warmth) and `gather`/`eat` (yields) code paths. No LLM yet — the instinct policy gains curiosity so the CLI demonstrates discovery end-to-end.

**Tech Stack:** Python 3.12, uv, pytest, stdlib only. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-29-genesis-phase1-design.md` (§4 structures, §5 mundane discovery branch)

**Depends on:** Plan 1 (world engine core) — merged or on branch `feat/world-engine-core`.

## Global Constraints

- Package manager is **uv** (`uv run pytest`, `uv add`) — never pip/venv.
- Engine stays deterministic: all randomness via the Engine's `random.Random(seed)`; no module-level `random`, no wall-clock reads in the engine.
- The engine never calls an LLM and never blocks on anything external.
- **Backward compatibility:** `WorldState.from_json` must still load Plan 1 JSON that has no `structures` key. Use `d.get("structures", [])`.
- **New signatures are additive:** `validate_action`, `step_action`, and `choose_action` gain an optional `graph=None` parameter so every existing Plan 1 test (which omits it) still passes unchanged.
- New action verbs this plan: `experiment_with`, `build`. Full verb set becomes `{move_to, gather, eat, drink, sleep, observe, experiment_with, build}`.
- Discoveries are stored on `Agent.knowledge` (a `list[str]` that already exists). Knowledge *sharing* between agents is Plan 3 (conversations) — in this plan an agent only learns from its own experiments.
- Experimenting does **not** consume items (you keep your flint after striking it). Building **does** consume its materials.
- Git: feature branch `feat/discovery-crafting-building` off the Plan 1 branch; imperative commit messages; **no Claude attribution anywhere**.
- All work happens in `projects/genesis/`.

## File Structure (this plan)

```
configs/
  discoveries.json     # NEW: recipes (experiment) + buildables (build)
  settings.json        # MODIFY: warmth/yield/eat tuning constants
  agents.json          # MODIFY: seed small starting inventories so discovery is lively
src/genesis/world/
  discovery.py         # NEW: DiscoveryGraph — recipe match + buildable lookup
  structures.py        # NEW: Structure dataclass + has_warmth_source() helper
  state.py             # MODIFY: WorldState.structures + from_json backward-compat
  actions.py           # MODIFY: experiment_with + build verbs; stone_tools/cooked payoffs
  needs.py             # MODIFY: tick_needs gains near_warmth flag
  instinct.py          # MODIFY: choose_action gains graph; curiosity (gather/experiment/build)
  engine.py            # MODIFY: construct graph, compute near_warmth, pass graph through
  cli.py               # MODIFY: report discoveries + structures in the summary
tests/
  test_discovery.py  test_structures.py  test_experiment.py  test_build.py
  test_payoffs.py    test_warmth_effects.py  test_instinct_curiosity.py
  test_cli.py (MODIFY: assert discoveries happen)
```

---

### Task 1: DiscoveryGraph — recipes + buildables config and lookup

**Files:**
- Create: `configs/discoveries.json`, `src/genesis/world/discovery.py`
- Test: `tests/test_discovery.py`

**Interfaces:**
- Consumes: nothing (stdlib json).
- Produces:
  - `DiscoveryGraph.from_file(path) -> DiscoveryGraph`
  - `.match(items: list[str], knowledge: list[str]) -> str | None` — returns the result name of the first recipe whose item multiset is a sub-multiset of `items` **and** whose `requires` list is all present in `knowledge`; else `None`.
  - `.buildable(name: str) -> dict | None` — returns the buildable spec dict (`materials`, `requires`, optional `terrain`, optional `carried`) or `None` if `name` is not buildable.
  - `.buildable_names() -> list[str]`

- [ ] **Step 1: Write `configs/discoveries.json`**

```json
{
  "recipes": [
    {"items": ["flint", "wood"], "requires": [], "result": "fire"},
    {"items": ["stone", "flint"], "requires": [], "result": "stone_tools"},
    {"items": ["berries"], "requires": ["fire"], "result": "cooked_food"}
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

- [ ] **Step 2: Write the failing tests** (`tests/test_discovery.py`)

```python
from genesis.world.discovery import DiscoveryGraph

G = DiscoveryGraph.from_file("configs/discoveries.json")


def test_match_simple_recipe():
    assert G.match(["flint", "wood"], []) == "fire"
    assert G.match(["wood", "flint"], []) == "fire"     # order independent


def test_match_ignores_extra_items():
    assert G.match(["flint", "wood", "berries"], []) == "fire"


def test_match_requires_knowledge():
    assert G.match(["berries"], []) is None             # needs fire known
    assert G.match(["berries"], ["fire"]) == "cooked_food"


def test_match_returns_none_when_nothing_fits():
    assert G.match(["berries", "water"], []) is None
    assert G.match([], []) is None


def test_buildable_lookup():
    camp = G.buildable("campfire")
    assert camp["materials"] == {"wood": 2} and camp["requires"] == ["fire"]
    assert G.buildable("nonsense") is None
    assert "hut" in G.buildable_names()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_discovery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'genesis.world.discovery'`

- [ ] **Step 4: Implement `src/genesis/world/discovery.py`**

```python
import json
from collections import Counter
from pathlib import Path


class DiscoveryGraph:
    def __init__(self, recipes: list[dict], buildables: dict[str, dict]):
        self.recipes = recipes
        self.buildables = buildables

    @classmethod
    def from_file(cls, path: str | Path) -> "DiscoveryGraph":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d["recipes"], d["buildables"])

    def match(self, items: list[str], knowledge: list[str]) -> str | None:
        have = Counter(items)
        for recipe in self.recipes:
            need = Counter(recipe["items"])
            if all(have[k] >= n for k, n in need.items()) and \
                    all(req in knowledge for req in recipe.get("requires", [])):
                return recipe["result"]
        return None

    def buildable(self, name: str) -> dict | None:
        return self.buildables.get(name)

    def buildable_names(self) -> list[str]:
        return list(self.buildables.keys())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_discovery.py -v` — Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add configs/discoveries.json src/genesis/world/discovery.py tests/test_discovery.py
git commit -m "Add DiscoveryGraph with recipe matching and buildable lookup"
```

---

### Task 2: Structures — dataclass, world state, serialization

**Files:**
- Create: `src/genesis/world/structures.py`
- Modify: `src/genesis/world/state.py`
- Test: `tests/test_structures.py`

**Interfaces:**
- Consumes: `Agent`, `WorldState` from state.
- Produces:
  - `Structure(type: str, x: int, y: int, built_by: str, built_minute: int)` (dataclass in `structures.py`)
  - `WorldState.structures: list[Structure]` (new field, defaults `[]`)
  - `WorldState.from_json` reconstructs structures with backward-compat (`d.get("structures", [])`)
  - `has_warmth_source(agent: Agent, state: WorldState, settings: dict) -> bool` (in `structures.py`) — True if the agent holds a torch, OR a campfire is within Chebyshev `campfire_warmth_radius`, OR the agent is `sleeping` and a hut is Chebyshev-adjacent (≤1).

- [ ] **Step 1: Write the failing tests** (`tests/test_structures.py`)

```python
from genesis import load_settings
from genesis.world.state import Agent, WorldState
from genesis.world.structures import Structure, has_warmth_source

S = load_settings("configs/settings.json")


def test_worldstate_serializes_structures():
    st = WorldState(sim_minutes=5, seed=1,
                    agents=[Agent(id="a", name="A", x=0, y=0)],
                    structures=[Structure(type="campfire", x=3, y=3,
                                          built_by="a", built_minute=4)])
    st2 = WorldState.from_json(st.to_json())
    assert st2.structures[0].type == "campfire"
    assert st2.structures[0].built_by == "a"


def test_from_json_backward_compatible_without_structures():
    legacy = '{"sim_minutes": 1, "seed": 2, "agents": [], "resources": []}'
    st = WorldState.from_json(legacy)
    assert st.structures == []


def test_warmth_from_nearby_campfire():
    a = Agent(id="a", name="A", x=5, y=5)
    st = WorldState(sim_minutes=0, seed=1, agents=[a],
                    structures=[Structure(type="campfire", x=6, y=6,
                                          built_by="a", built_minute=0)])
    assert has_warmth_source(a, st, S) is True
    a.x, a.y = 20, 20
    assert has_warmth_source(a, st, S) is False


def test_warmth_from_held_torch():
    a = Agent(id="a", name="A", x=0, y=0, inventory={"torch": 1})
    st = WorldState(sim_minutes=0, seed=1, agents=[a])
    assert has_warmth_source(a, st, S) is True


def test_hut_only_shelters_when_sleeping_and_adjacent():
    a = Agent(id="a", name="A", x=5, y=5)
    st = WorldState(sim_minutes=0, seed=1, agents=[a],
                    structures=[Structure(type="hut", x=5, y=6,
                                          built_by="a", built_minute=0)])
    assert has_warmth_source(a, st, S) is False     # awake
    a.status = "sleeping"
    assert has_warmth_source(a, st, S) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_structures.py -v` — Expected: FAIL (module not found)

- [ ] **Step 3: Implement `src/genesis/world/structures.py`**

```python
from dataclasses import dataclass

from genesis.world.state import Agent, WorldState


@dataclass
class Structure:
    type: str
    x: int
    y: int
    built_by: str
    built_minute: int


def _cheb(ax: int, ay: int, bx: int, by: int) -> int:
    return max(abs(ax - bx), abs(ay - by))


def has_warmth_source(agent: Agent, state: WorldState, settings: dict) -> bool:
    if agent.inventory.get("torch", 0) > 0:
        return True
    radius = settings["campfire_warmth_radius"]
    for s in state.structures:
        if s.type == "campfire" and _cheb(agent.x, agent.y, s.x, s.y) <= radius:
            return True
        if (s.type == "hut" and agent.status == "sleeping"
                and _cheb(agent.x, agent.y, s.x, s.y) <= 1):
            return True
    return False
```

- [ ] **Step 4: Modify `src/genesis/world/state.py`**

Add the import and field, and update `from_json`. The `Structure` import lives at the bottom to avoid a circular import (`structures.py` imports from `state.py`).

Change the `WorldState` dataclass and `from_json`:

```python
@dataclass
class WorldState:
    sim_minutes: int
    seed: int
    agents: list[Agent] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    structures: list = field(default_factory=list)  # list[Structure]

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> "WorldState":
        from genesis.world.structures import Structure
        d = json.loads(s)
        agents = [
            Agent(**{**a, "needs": Needs(**a["needs"])}) for a in d["agents"]
        ]
        resources = [Resource(**r) for r in d["resources"]]
        structures = [Structure(**s) for s in d.get("structures", [])]
        return cls(sim_minutes=d["sim_minutes"], seed=d["seed"],
                   agents=agents, resources=resources, structures=structures)
```

Add the warmth constant to `configs/settings.json` (needed by the tests here and Task 6):

```json
  "campfire_warmth_radius": 2,
```

Insert it after the existing `"minutes_per_day"` line (any position in the object is fine; keep valid JSON — mind the commas).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_structures.py -v` — Expected: PASS (5 tests)

- [ ] **Step 6: Run the existing suite to confirm no regressions**

Run: `uv run pytest -v` — Expected: all Plan 1 tests still PASS (from_json backward-compat holds).

- [ ] **Step 7: Commit**

```bash
git add src/genesis/world/structures.py src/genesis/world/state.py configs/settings.json tests/test_structures.py
git commit -m "Add Structure state, serialization, and warmth-source helper"
```

---

### Task 3: `experiment_with` action

**Files:**
- Modify: `src/genesis/world/actions.py`
- Test: `tests/test_experiment.py`

**Interfaces:**
- Consumes: `DiscoveryGraph` from discovery; `Agent`, `WorldState`, `WorldMap`.
- Produces (signature changes — additive, `graph` defaults `None`):
  - `validate_action(action, agent, state, world_map, graph=None) -> tuple[bool, str]`
  - `step_action(agent, state, world_map, settings, graph=None) -> list[dict]`
- Action dict: `{"action": "experiment_with", "items": [str, ...]}` — the agent must hold each listed item (qty ≥ 1). Execution: `graph.match(items, agent.knowledge)`; if a result comes back and it is **not** already in `agent.knowledge`, append it and emit `discovered`; if already known emit `experiment_known`; if no match emit `experiment_failed`. Items are **not** consumed. Requires `graph`; if `graph is None`, reject.
- Event types added: `discovered`, `experiment_known`, `experiment_failed`.

- [ ] **Step 1: Write the failing tests** (`tests/test_experiment.py`)

```python
from genesis import load_settings
from genesis.world.state import Agent, WorldState
from genesis.world.grid import WorldMap
from genesis.world.discovery import DiscoveryGraph
from genesis.world.actions import validate_action, step_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
G = DiscoveryGraph.from_file("configs/discoveries.json")


def world(agent):
    return WorldState(sim_minutes=0, seed=1, agents=[agent])


def test_experiment_discovers_fire_and_keeps_items():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1},
              current_action={"action": "experiment_with", "items": ["flint", "wood"]})
    ev = step_action(a, world(a), M, S, G)
    assert "fire" in a.knowledge
    assert ev[0]["type"] == "discovered" and ev[0]["discovery"] == "fire"
    assert a.inventory == {"flint": 1, "wood": 1}     # not consumed
    assert a.current_action is None


def test_experiment_known_when_already_discovered():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1},
              knowledge=["fire"],
              current_action={"action": "experiment_with", "items": ["flint", "wood"]})
    ev = step_action(a, world(a), M, S, G)
    assert ev[0]["type"] == "experiment_known"


def test_experiment_failed_when_no_recipe():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"berries": 1},
              current_action={"action": "experiment_with", "items": ["berries"]})
    ev = step_action(a, world(a), M, S, G)
    assert ev[0]["type"] == "experiment_failed"


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

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_experiment.py -v` — Expected: FAIL (`step_action() takes 4 positional arguments` / import error)

- [ ] **Step 3: Modify `src/genesis/world/actions.py`**

Update `VERBS`, the two signatures, add validation, and add the handler. Change the top of the file:

```python
VERBS = {"move_to", "gather", "eat", "drink", "sleep", "observe",
         "experiment_with", "build"}


def validate_action(action: dict, agent: Agent, state: WorldState,
                    world_map: WorldMap, graph=None) -> tuple[bool, str]:
    if not isinstance(action, dict) or "action" not in action:
        return False, "malformed action"
    verb = action["action"]
    if verb not in VERBS:
        return False, f"unknown action '{verb}'"
    if verb == "move_to":
        if not (isinstance(action.get("x"), int) and isinstance(action.get("y"), int)):
            return False, "move_to needs integer x and y"
        if not world_map.walkable(action["x"], action["y"]):
            return False, "target tile is not walkable"
    if verb == "gather" and not isinstance(action.get("resource"), str):
        return False, "gather needs a resource name"
    if verb == "experiment_with":
        if graph is None:
            return False, "no discovery graph available"
        items = action.get("items")
        if not isinstance(items, list) or not items:
            return False, "experiment_with needs a non-empty items list"
        for it in items:
            if agent.inventory.get(it, 0) < 1:
                return False, f"not holding {it}"
    return True, ""
```

Change the `step_action` signature line:

```python
def step_action(agent: Agent, state: WorldState, world_map: WorldMap,
                settings: dict, graph=None) -> list[dict]:
```

And update its validate call near the top of the body:

```python
    ok, why = validate_action(action, agent, state, world_map, graph)
```

Then add this handler (place it after the `observe` block, before the final `return []`):

```python
    if verb == "experiment_with":
        result = graph.match(action["items"], agent.knowledge)
        if result is None:
            return _finish(agent, {"type": "experiment_failed", "agent": agent.id,
                                   "items": action["items"]})
        if result in agent.knowledge:
            return _finish(agent, {"type": "experiment_known", "agent": agent.id,
                                   "discovery": result})
        agent.knowledge.append(result)
        return _finish(agent, {"type": "discovered", "agent": agent.id,
                               "discovery": result})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_experiment.py -v` — Expected: PASS (5 tests)

- [ ] **Step 5: Confirm no regressions**

Run: `uv run pytest -v` — Expected: all prior tests still PASS (graph defaults None; existing calls unaffected).

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/actions.py tests/test_experiment.py
git commit -m "Add experiment_with action for recipe discovery"
```

---

### Task 4: `build` action

**Files:**
- Modify: `src/genesis/world/actions.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `DiscoveryGraph`, `Structure`.
- Produces: `build` handling inside the existing `validate_action` / `step_action` (graph-aware).
- Action dict: `{"action": "build", "structure": str}`. Validation & execution rules:
  - `structure` must be a known buildable (`graph.buildable(name)`); else reject.
  - Agent must know all `requires`; else reject.
  - Agent must hold all `materials`; else the step emits `build_failed` (missing materials is a runtime shortfall, not a malformed request).
  - For a placed (non-`carried`) buildable: the agent's tile terrain must be in the spec's `terrain` list, and no structure of any type may already occupy that tile; else `build_failed`.
  - Execution consumes the materials from inventory. A `carried` buildable (torch) is added to `agent.inventory[name]`; a placed buildable appends a `Structure` at the agent's tile. Emits `built`.
- Event types added: `built`, `build_failed`.

- [ ] **Step 1: Write the failing tests** (`tests/test_build.py`)

```python
from genesis import load_settings
from genesis.world.state import Agent, WorldState
from genesis.world.grid import WorldMap
from genesis.world.discovery import DiscoveryGraph
from genesis.world.actions import validate_action, step_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
G = DiscoveryGraph.from_file("configs/discoveries.json")


def world(agent):
    return WorldState(sim_minutes=7, seed=1, agents=[agent])


def test_build_campfire_places_structure_and_consumes_wood():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"],
              inventory={"wood": 3},
              current_action={"action": "build", "structure": "campfire"})
    st = world(a)
    ev = step_action(a, st, M, S, G)
    assert ev[0]["type"] == "built" and ev[0]["structure"] == "campfire"
    assert a.inventory["wood"] == 1                       # 3 - 2
    assert st.structures[0].type == "campfire"
    assert (st.structures[0].x, st.structures[0].y) == (5, 5)
    assert st.structures[0].built_by == "a"


def test_build_torch_goes_to_inventory_not_map():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"],
              inventory={"wood": 1},
              current_action={"action": "build", "structure": "torch"})
    st = world(a)
    ev = step_action(a, st, M, S, G)
    assert ev[0]["type"] == "built"
    assert a.inventory.get("torch") == 1 and st.structures == []


def test_build_rejected_without_knowledge():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"wood": 3})
    ok, why = validate_action(
        {"action": "build", "structure": "campfire"}, a, world(a), M, G)
    assert ok is False and "fire" in why


def test_build_failed_without_materials():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"], inventory={"wood": 1},
              current_action={"action": "build", "structure": "campfire"})
    ev = step_action(a, world(a), M, S, G)
    assert ev[0]["type"] == "build_failed"


def test_build_failed_on_wrong_terrain():
    # (12,0) is cave terrain, which is not in campfire's allowed terrain list.
    a = Agent(id="a", name="A", x=12, y=0, knowledge=["fire"], inventory={"wood": 3},
              current_action={"action": "build", "structure": "campfire"})
    ev = step_action(a, world(a), M, S, G)
    assert ev[0]["type"] == "build_failed"


def test_build_failed_when_tile_occupied():
    from genesis.world.structures import Structure
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"], inventory={"wood": 3},
              current_action={"action": "build", "structure": "campfire"})
    st = world(a)
    st.structures.append(Structure(type="campfire", x=5, y=5,
                                   built_by="b", built_minute=1))
    ev = step_action(a, st, M, S, G)
    assert ev[0]["type"] == "build_failed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build.py -v` — Expected: FAIL (build not handled)

- [ ] **Step 3: Modify `src/genesis/world/actions.py`**

Add build validation inside `validate_action` (after the `experiment_with` block, before `return True, ""`):

```python
    if verb == "build":
        if graph is None:
            return False, "no discovery graph available"
        spec = graph.buildable(action.get("structure", ""))
        if spec is None:
            return False, f"cannot build '{action.get('structure')}'"
        for req in spec.get("requires", []):
            if req not in agent.knowledge:
                return False, f"needs to know {req} first"
```

Add the build handler (after the `experiment_with` handler, before the final `return []`). Import `Structure` at the top of the file: `from genesis.world.structures import Structure`.

```python
    if verb == "build":
        spec = graph.buildable(action["structure"])
        materials = spec["materials"]
        if any(agent.inventory.get(m, 0) < n for m, n in materials.items()):
            return _finish(agent, {"type": "build_failed", "agent": agent.id,
                                   "structure": action["structure"],
                                   "reason": "missing materials"})
        if not spec.get("carried"):
            if world_map.terrain(agent.x, agent.y) not in spec.get("terrain", []):
                return _finish(agent, {"type": "build_failed", "agent": agent.id,
                                       "structure": action["structure"],
                                       "reason": "wrong terrain"})
            if any((s.x, s.y) == (agent.x, agent.y) for s in state.structures):
                return _finish(agent, {"type": "build_failed", "agent": agent.id,
                                       "structure": action["structure"],
                                       "reason": "tile occupied"})
        for m, n in materials.items():
            agent.inventory[m] -= n
        if spec.get("carried"):
            agent.inventory[action["structure"]] = \
                agent.inventory.get(action["structure"], 0) + 1
        else:
            state.structures.append(Structure(
                type=action["structure"], x=agent.x, y=agent.y,
                built_by=agent.id, built_minute=state.sim_minutes))
        return _finish(agent, {"type": "built", "agent": agent.id,
                               "structure": action["structure"]})
```

Note on the circular import: `actions.py` importing `Structure` from `structures.py`, which imports `Agent`/`WorldState` from `state.py`, is fine — `actions.py` already imports from `state.py` and there is no cycle back into `actions.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build.py -v` — Expected: PASS (6 tests)

- [ ] **Step 5: Confirm no regressions**

Run: `uv run pytest -v` — Expected: all prior tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/actions.py tests/test_build.py
git commit -m "Add build action for placing and carrying structures"
```

---

### Task 5: Discovery payoffs — better yields, tastier food

**Files:**
- Modify: `src/genesis/world/actions.py`, `configs/settings.json`
- Test: `tests/test_payoffs.py`

**Interfaces:**
- No signature changes. Behavior changes inside the existing `gather` and `eat` handlers:
  - `gather`: if the agent knows `stone_tools`, transfer `1 + stone_tools_gather_bonus` units in one gather step (capped at the resource's remaining qty); else 1.
  - `eat`: hunger restore is `eat_berries_hunger_restore` plus `eat_cooked_hunger_bonus` if the agent knows `cooked_food`.

- [ ] **Step 1: Add constants to `configs/settings.json`**

```json
  "stone_tools_gather_bonus": 1,
  "eat_cooked_hunger_bonus": 15.0,
```

(Insert as new keys; keep valid JSON.)

- [ ] **Step 2: Write the failing tests** (`tests/test_payoffs.py`)

```python
from genesis import load_settings
from genesis.world.state import Agent, Needs, Resource, WorldState
from genesis.world.grid import WorldMap
from genesis.world.actions import step_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")


def test_stone_tools_double_gather_yield():
    r = Resource(type="wood", x=5, y=5, qty=10)
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["stone_tools"],
              current_action={"action": "gather", "resource": "wood"})
    st = WorldState(sim_minutes=0, seed=1, agents=[a], resources=[r])
    step_action(a, st, M, S)
    assert a.inventory["wood"] == 1 + S["stone_tools_gather_bonus"]
    assert r.qty == 10 - (1 + S["stone_tools_gather_bonus"])


def test_gather_yield_capped_at_remaining_qty():
    r = Resource(type="wood", x=5, y=5, qty=1)
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["stone_tools"],
              current_action={"action": "gather", "resource": "wood"})
    st = WorldState(sim_minutes=0, seed=1, agents=[a], resources=[r])
    step_action(a, st, M, S)
    assert a.inventory["wood"] == 1 and r.qty == 0


def test_cooked_food_restores_more_hunger():
    a = Agent(id="a", name="A", x=5, y=5, needs=Needs(hunger=10.0),
              knowledge=["cooked_food"], inventory={"berries": 1},
              current_action={"action": "eat"})
    st = WorldState(sim_minutes=0, seed=1, agents=[a])
    step_action(a, st, M, S)
    assert a.needs.hunger == 10 + S["eat_berries_hunger_restore"] + S["eat_cooked_hunger_bonus"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_payoffs.py -v` — Expected: FAIL (yields/restore still Plan 1 values)

- [ ] **Step 4: Modify the `gather` handler in `src/genesis/world/actions.py`**

Replace the two lines that transfer one unit:

```python
        r.qty -= 1
        agent.inventory[rtype] = agent.inventory.get(rtype, 0) + 1
        return _finish(agent, {"type": "gathered", "agent": agent.id,
                               "resource": rtype, "qty": 1})
```

with a yield that respects `stone_tools`:

```python
        yield_n = 1 + (settings["stone_tools_gather_bonus"]
                       if "stone_tools" in agent.knowledge else 0)
        yield_n = min(yield_n, r.qty)
        r.qty -= yield_n
        agent.inventory[rtype] = agent.inventory.get(rtype, 0) + yield_n
        return _finish(agent, {"type": "gathered", "agent": agent.id,
                               "resource": rtype, "qty": yield_n})
```

- [ ] **Step 5: Modify the `eat` handler in `src/genesis/world/actions.py`**

Replace the hunger-restore line:

```python
        agent.needs.hunger = min(
            100.0, agent.needs.hunger + settings["eat_berries_hunger_restore"])
```

with:

```python
        restore = settings["eat_berries_hunger_restore"]
        if "cooked_food" in agent.knowledge:
            restore += settings["eat_cooked_hunger_bonus"]
        agent.needs.hunger = min(100.0, agent.needs.hunger + restore)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_payoffs.py -v` — Expected: PASS (3 tests)

- [ ] **Step 7: Confirm no regressions**

Run: `uv run pytest -v` — Expected: Plan 1 gather/eat tests still PASS (agents without the knowledge get the old values).

- [ ] **Step 8: Commit**

```bash
git add src/genesis/world/actions.py configs/settings.json tests/test_payoffs.py
git commit -m "Add stone-tools gather bonus and cooked-food eat bonus"
```

---

### Task 6: Warmth from fire and shelter (needs + engine)

**Files:**
- Modify: `src/genesis/world/needs.py`, `src/genesis/world/engine.py`, `configs/settings.json`
- Test: `tests/test_warmth_effects.py`

**Interfaces:**
- `tick_needs(agent, sim_minutes, settings, near_warmth: bool = False) -> list[dict]` — new optional flag. When `near_warmth` is True and it is night, warmth **regenerates** by `warmth_regen_near_fire_per_min` instead of decaying. Day behavior and all other rules unchanged. The default `False` preserves every existing caller.
- `Engine.tick()` computes `near_warmth` per agent via `has_warmth_source(agent, state, settings)` and passes it into `tick_needs`.

- [ ] **Step 1: Add the constant to `configs/settings.json`**

```json
  "warmth_regen_near_fire_per_min": 0.4,
```

- [ ] **Step 2: Write the failing tests** (`tests/test_warmth_effects.py`)

```python
from genesis import load_settings
from genesis.world.state import Agent, Needs
from genesis.world.needs import tick_needs

S = load_settings("configs/settings.json")
MIDNIGHT = 0


def test_near_warmth_regenerates_warmth_at_night():
    a = Agent(id="a", name="A", x=0, y=0, needs=Needs(warmth=50.0))
    tick_needs(a, MIDNIGHT, S, near_warmth=True)
    assert a.needs.warmth == 50 + S["warmth_regen_near_fire_per_min"]


def test_without_warmth_source_still_decays_at_night():
    a = Agent(id="a", name="A", x=0, y=0, needs=Needs(warmth=50.0))
    tick_needs(a, MIDNIGHT, S, near_warmth=False)
    assert a.needs.warmth == 50 - S["warmth_decay_night_per_min"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_warmth_effects.py -v` — Expected: FAIL (`tick_needs() got an unexpected keyword argument 'near_warmth'`)

- [ ] **Step 4: Modify `src/genesis/world/needs.py`**

Change the signature and the night-warmth branch. The signature:

```python
def tick_needs(agent: Agent, sim_minutes: int, settings: dict,
               near_warmth: bool = False) -> list[dict]:
```

Replace the day/night warmth block:

```python
    if day:
        n.warmth = _clamp(n.warmth + settings["warmth_regen_day_per_min"])
    else:
        rate = (settings["warmth_decay_night_sleeping_per_min"]
                if agent.status == "sleeping"
                else settings["warmth_decay_night_per_min"])
        n.warmth = _clamp(n.warmth - rate)
```

with:

```python
    if day:
        n.warmth = _clamp(n.warmth + settings["warmth_regen_day_per_min"])
    elif near_warmth:
        n.warmth = _clamp(n.warmth + settings["warmth_regen_near_fire_per_min"])
    else:
        rate = (settings["warmth_decay_night_sleeping_per_min"]
                if agent.status == "sleeping"
                else settings["warmth_decay_night_per_min"])
        n.warmth = _clamp(n.warmth - rate)
```

- [ ] **Step 5: Modify `src/genesis/world/engine.py`**

Add the import and compute the flag before calling `tick_needs`:

```python
from genesis.world.structures import has_warmth_source
```

In `tick()`, change the `tick_needs` call inside the agent loop:

```python
        for agent in self.state.agents:
            near = has_warmth_source(agent, self.state, self.settings)
            events += tick_needs(agent, minute, self.settings, near_warmth=near)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_warmth_effects.py -v` — Expected: PASS (2 tests)

- [ ] **Step 7: Confirm no regressions**

Run: `uv run pytest -v` — Expected: Plan 1 needs tests still PASS (default `near_warmth=False`).

- [ ] **Step 8: Commit**

```bash
git add src/genesis/world/needs.py src/genesis/world/engine.py configs/settings.json tests/test_warmth_effects.py
git commit -m "Add warmth regeneration near fire and shelter at night"
```

---

### Task 7: Instinct curiosity — gather, experiment, build

**Files:**
- Modify: `src/genesis/world/instinct.py`
- Test: `tests/test_instinct_curiosity.py`

**Interfaces:**
- `choose_action(agent, state, world_map, settings, rng, graph=None) -> dict | None` — new optional `graph`. When `graph is None`, behavior is exactly Plan 1 (existing tests pass). When a graph is provided, after the survival priorities (night-sleep, hunger, low-energy) and before wandering, the agent, in order:
  1. **Experiment:** if `graph.match(held_item_types, agent.knowledge)` returns a result the agent does not yet know → `experiment_with` those held item types.
  2. **Build campfire:** if it knows `fire`, holds ≥ the campfire wood cost, its tile terrain allows a campfire, and no campfire is within `campfire_warmth_radius` → `build` campfire.
  3. **Build hut:** if it knows `stone_tools`, holds the hut materials, its tile terrain allows a hut, and no hut exists within 3 tiles → `build` hut.
  4. **Gather raw materials:** if standing on/adjacent to a gatherable raw material (`wood`, `stone`, `flint`) it is not already carrying → `gather` it.
  - `held_item_types` = inventory keys with qty > 0.
- Uses `DiscoveryGraph.buildable` for material costs and terrain; no hardcoded recipe values.

- [ ] **Step 1: Write the failing tests** (`tests/test_instinct_curiosity.py`)

```python
import random
from genesis import load_settings
from genesis.world.state import Agent, Resource, WorldState
from genesis.world.grid import WorldMap
from genesis.world.discovery import DiscoveryGraph
from genesis.world.instinct import choose_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
G = DiscoveryGraph.from_file("configs/discoveries.json")
NOON = 720


def world(agent, resources=None):
    return WorldState(sim_minutes=NOON, seed=1, agents=[agent],
                      resources=resources or [])


def test_experiments_with_held_materials():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"flint": 1, "wood": 1})
    act = choose_action(a, world(a), M, S, random.Random(1), G)
    assert act["action"] == "experiment_with"
    assert set(act["items"]) == {"flint", "wood"}


def test_builds_campfire_when_fire_known_and_wood_available():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"],
              inventory={"wood": 2})
    act = choose_action(a, world(a), M, S, random.Random(1), G)
    assert act == {"action": "build", "structure": "campfire"}


def test_gathers_raw_material_underfoot():
    r = Resource(type="wood", x=5, y=5, qty=5)
    a = Agent(id="a", name="A", x=5, y=5)   # no inventory, knows nothing
    act = choose_action(a, world(a, [r]), M, S, random.Random(1), G)
    assert act == {"action": "gather", "resource": "wood"}


def test_without_graph_matches_plan1_wander():
    a = Agent(id="a", name="A", x=5, y=5)
    act = choose_action(a, world(a), M, S, random.Random(1))   # graph=None
    assert act["action"] in ("move_to", "observe")


def test_does_not_re_experiment_known_recipe():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"],
              inventory={"flint": 1, "wood": 1})
    # holds fire materials but already knows fire, and has 1 wood (< campfire cost 2)
    act = choose_action(a, world(a), M, S, random.Random(1), G)
    assert act["action"] != "experiment_with"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_instinct_curiosity.py -v` — Expected: FAIL (`choose_action() takes 5 positional arguments`)

- [ ] **Step 3: Modify `src/genesis/world/instinct.py`**

Add a Chebyshev helper and the curiosity block. Change the signature:

```python
def choose_action(agent: Agent, state: WorldState, world_map: WorldMap,
                  settings: dict, rng, graph=None) -> dict | None:
```

Keep the existing survival priorities (collapsed → None, night → sleep, hunger, low-energy). **Immediately before** the final wander loop, insert:

```python
    if graph is not None:
        held = [k for k, v in agent.inventory.items() if v > 0]
        result = graph.match(held, agent.knowledge)
        if result is not None and result not in agent.knowledge:
            return {"action": "experiment_with", "items": held}
        camp = graph.buildable("campfire")
        if ("fire" in agent.knowledge
                and _has_materials(agent, camp["materials"])
                and world_map.terrain(agent.x, agent.y) in camp["terrain"]
                and not _structure_within(state, "campfire", agent,
                                          settings["campfire_warmth_radius"])):
            return {"action": "build", "structure": "campfire"}
        hut = graph.buildable("hut")
        if ("stone_tools" in agent.knowledge
                and _has_materials(agent, hut["materials"])
                and world_map.terrain(agent.x, agent.y) in hut["terrain"]
                and not _structure_within(state, "hut", agent, 3)):
            return {"action": "build", "structure": "hut"}
        raw = _raw_material_here(agent, state, world_map)
        if raw is not None:
            return {"action": "gather", "resource": raw}
```

Add these module-level helpers (near the other helpers):

```python
RAW_MATERIALS = ("wood", "stone", "flint")


def _has_materials(agent: Agent, materials: dict) -> bool:
    return all(agent.inventory.get(m, 0) >= n for m, n in materials.items())


def _structure_within(state: WorldState, stype: str, agent: Agent,
                      radius: int) -> bool:
    for s in state.structures:
        if s.type == stype and max(abs(s.x - agent.x), abs(s.y - agent.y)) <= radius:
            return True
    return False


def _raw_material_here(agent: Agent, state: WorldState, world_map: WorldMap):
    near = [(agent.x, agent.y)] + world_map.neighbors4(agent.x, agent.y)
    for r in state.resources:
        if (r.type in RAW_MATERIALS and r.qty > 0 and (r.x, r.y) in near
                and agent.inventory.get(r.type, 0) == 0):
            return r.type
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_instinct_curiosity.py -v` — Expected: PASS (5 tests)

- [ ] **Step 5: Confirm no regressions**

Run: `uv run pytest -v` — Expected: Plan 1 instinct tests still PASS (they call `choose_action` without a graph → the curiosity block is skipped).

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/instinct.py tests/test_instinct_curiosity.py
git commit -m "Add instinct curiosity: gather, experiment, and build"
```

---

### Task 8: Wire the graph into the engine + demonstrate discovery

**Files:**
- Modify: `src/genesis/world/engine.py`, `src/genesis/cli.py`, `configs/agents.json`
- Test: `tests/test_cli.py` (append; keep the Plan 1 assertions)

**Interfaces:**
- `Engine.__init__` loads a `DiscoveryGraph` (from `configs/discoveries.json`) and stores it as `self.graph`.
- `Engine.tick()` passes `self.graph` to both `choose_action` and `step_action`.
- `run_sim` includes discoveries and structures in its summary: adds `"discoveries"` (a `dict[str, list[str]]` of agent name → known discoveries) and `"structures"` (a `list[dict]` of `{type, x, y}`) to the returned summary.
- `configs/agents.json` seeds small starting inventories so the crew can experiment early.

- [ ] **Step 1: Modify `configs/agents.json`** — add starting inventories

```json
{
  "agents": [
    {"id": "ash", "name": "Ash", "x": 9, "y": 5, "persona": "curious and bold", "brain": "", "inventory": {"flint": 1, "wood": 2}},
    {"id": "bramble", "name": "Bramble", "x": 6, "y": 3, "persona": "cautious and practical", "brain": "", "inventory": {"stone": 2, "flint": 1, "wood": 4}},
    {"id": "cinder", "name": "Cinder", "x": 5, "y": 7, "persona": "social and scatterbrained", "brain": "", "inventory": {"wood": 2, "flint": 1}},
    {"id": "dew", "name": "Dew", "x": 8, "y": 10, "persona": "quiet and observant", "brain": "", "inventory": {"berries": 2}}
  ]
}
```

- [ ] **Step 2: Write the failing tests** (append to `tests/test_cli.py`)

```python
def test_discoveries_and_structures_emerge(tmp_path):
    summary = run_sim(days=2, db_path=tmp_path / "w.db", seed=42)
    # someone should have discovered fire and stone_tools from seeded materials
    all_known = {d for known in summary["discoveries"].values() for d in known}
    assert "fire" in all_known
    assert "stone_tools" in all_known
    # and at least one structure should have been built
    assert len(summary["structures"]) >= 1
    assert summary["structures"][0]["type"] in ("campfire", "hut")
```

- [ ] **Step 3: Run the new test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_discoveries_and_structures_emerge -v`
Expected: FAIL with `KeyError: 'discoveries'` (summary has no such key yet).

- [ ] **Step 4: Modify `src/genesis/world/engine.py`**

Load and store the graph, and thread it through. Add the import:

```python
from genesis.world.discovery import DiscoveryGraph
```

Change `__init__` to accept an optional graph (default: load from config) so tests and the CLI stay simple:

```python
    def __init__(self, state: WorldState, world_map: WorldMap, settings: dict,
                 graph: DiscoveryGraph | None = None):
        self.state = state
        self.world_map = world_map
        self.settings = settings
        self.rng = random.Random(state.seed)
        self.graph = graph or DiscoveryGraph.from_file("configs/discoveries.json")
```

Update the two calls inside `tick()`:

```python
            if agent.current_action is None and agent.status in ("active", "sleeping"):
                agent.current_action = choose_action(
                    agent, self.state, self.world_map, self.settings, self.rng,
                    self.graph)
            events += step_action(agent, self.state, self.world_map,
                                  self.settings, self.graph)
```

- [ ] **Step 5: Modify `src/genesis/cli.py`** — enrich the summary

In `run_sim`, `_fresh_world` already loads resources from `map.json`. Add discoveries and structures to the returned dict:

```python
        "discoveries": {a.name: list(a.knowledge) for a in state.agents},
        "structures": [{"type": s.type, "x": s.x, "y": s.y}
                       for s in state.structures],
```

Insert these two keys into the summary dict returned by `run_sim` (alongside `"agents"`).

- [ ] **Step 6: Run the new test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS — including the Plan 1 CLI tests and the new discovery test.

If `fire`/`stone_tools` do not appear within 2 days, that is a real signal the instinct chain or seeded inventories are wrong — debug the chain (are agents reaching the experiment branch? are materials present?), do not weaken the assertion.

- [ ] **Step 7: Run the full suite and a real smoke run**

```bash
uv run pytest -v
uv run python -m genesis.cli --days 3 --db world.db
```

Expected: all tests PASS; the smoke summary shows nonzero `discovered`/`built` in `event_counts`, at least one campfire or hut in `structures`, and `fire`/`stone_tools` in `discoveries`. Delete `world.db` afterward (it is gitignored).

- [ ] **Step 8: Update `README.md` status line**

Change the Status section to:

```markdown
## Status

Plan 2 (discovery, crafting & building) — agents experiment to discover fire,
stone tools, and cooked food; build campfires and huts; and gain real payoffs
(better yields, warm nights). Still rule-driven; LLM minds come next.
```

- [ ] **Step 9: Commit**

```bash
git add src/genesis/world/engine.py src/genesis/cli.py configs/agents.json tests/test_cli.py README.md
git commit -m "Wire discovery graph into engine and demonstrate emergent discovery"
```

---

## Done criteria (Plan 2)

- `uv run pytest` — full suite green (Plan 1 + Plan 2).
- `uv run python -m genesis.cli --days 3` — rule-driven agents discover fire and stone tools from their starting materials, build a campfire and/or hut, gather faster once they know stone tools, and hold warmth near fire at night.
- Every new action is validated and can never crash the engine (missing graph, missing materials, wrong terrain all degrade to a rejection/failure event).
- Backward compatibility verified: Plan 1 JSON without a `structures` key still loads.

## Follow-on plans (not in this document)

- **Plan 3 — Danger & Magic:** wolves (chase/injure, repelled by fire/torch), storms (douse campfires, huts shelter), wisps (drop glimmer shards, seed curiosity), the Cave Lurker, and the magic branch (glimmer shard → spark → everflame → wisp-calling; everflame opens the cave → rune wall). Reuses this plan's `DiscoveryGraph`, structures, and `has_warmth_source` seam. (Spec §4 hostiles, §5 magic branch.)
- **Plan 4 — Minds:** memory stream, retrieval, reflection, planning; Brain adapters (Groq/Gemini/Ollama), ThinkQueue; the instinct policy becomes the LLM-failure fallback. Conversations enable knowledge *sharing* between agents. (Spec §6–§7, §10.)
- **Plan 5 — API & Viewer:** FastAPI + SSE, Phaser 3 viewer with LPC animated sprites, scoreboard, away-digest. (Spec §8–§9.)
