# Genesis Plan 1: World Engine Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deterministic world engine where rule-driven agents survive on a tile map — needs decay, gathering, eating, sleeping, day/night — with SQLite persistence and seeded fast-forward.

**Architecture:** Pure-Python simulation core (no LLM, no web). `Engine.tick()` advances one sim-minute; `Engine.advance(n)` fast-forwards deterministically from a seed. Agents act via a validated action dict schema; when no plan exists they fall back to a rule-based *instinct* policy (this same policy is the LLM-failure fallback in Plan 3, so it is permanent code). SQLite stores full state + an append-only event log.

**Tech Stack:** Python 3.12, uv, pytest, stdlib only (`sqlite3`, `random`, `dataclasses`, `json`). No new dependencies beyond pytest (dev).

**Spec:** `docs/superpowers/specs/2026-08-29-genesis-phase1-design.md` (§3, §4, §11)

## Global Constraints

- Package manager is **uv** (`uv init`, `uv add`, `uv run`) — never pip/venv.
- Engine is deterministic: all randomness through `random.Random(seed)` held by the Engine; **no `random` module-level calls, no wall-clock reads inside the engine**.
- The engine never calls an LLM and never blocks on anything external.
- Actions in this plan: `move_to`, `gather`, `eat`, `drink`, `sleep`, `observe`. (`experiment_with`, `build` arrive in Plan 2; `talk_to`, `give` in Plan 3 — the schema is extensible by design.)
- Needs are floats 0–100. Hitting 0 causes **collapse**, never death.
- Time: 1 tick = 1 sim-minute; 1440 min/day; daytime = 06:00–20:00.
- Git: feature branch `feat/world-engine-core` off `main` (merge `design/phase1-spec` to main first); imperative commit messages; **no Claude attribution anywhere**.
- All work happens in `projects/genesis/`.

## File Structure (this plan)

```
configs/
  settings.json        # decay rates, restore amounts, timing constants
  map.json             # 20x15 starter map: terrain rows + resource nodes
  agents.json          # 4 agents: name, spawn, persona (brain field unused until Plan 3)
src/genesis/
  __init__.py
  world/
    __init__.py
    state.py           # Needs, Agent, Resource, WorldState dataclasses + (de)serialization
    grid.py            # WorldMap: terrain lookup, walkability, adjacency
    needs.py           # per-tick decay/regen + collapse/recovery rules
    actions.py         # action validation + one-tick execution
    instinct.py        # rule-based action chooser (also the Plan-3 LLM fallback)
    engine.py          # Engine: tick(), advance(), event collection
  persistence/
    __init__.py
    db.py              # SQLite schema, save/load state, append/load events
  cli.py               # `python -m genesis.cli --days N` smoke runner
tests/
  test_state.py  test_grid.py  test_needs.py  test_actions.py
  test_instinct.py  test_engine.py  test_db.py  test_cli.py
```

---

### Task 1: Project scaffold + settings config

**Files:**
- Create: `pyproject.toml` (via uv), `src/genesis/__init__.py`, `src/genesis/world/__init__.py`, `src/genesis/persistence/__init__.py`, `configs/settings.json`, `tests/test_state.py` (settings test only for now)

**Interfaces:**
- Produces: `genesis.load_settings(path: str | Path) -> dict` — returns the parsed settings dict; every later task reads constants through it.

- [ ] **Step 1: Scaffold with uv on a new branch**

```bash
cd projects/genesis
git checkout main && git merge design/phase1-spec && git checkout -b feat/world-engine-core
uv init --lib --name genesis --python 3.12
uv add --dev pytest
```

`uv init --lib` creates `src/genesis/__init__.py` and `pyproject.toml`. Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write `configs/settings.json`**

```json
{
  "minutes_per_day": 1440,
  "day_start_minute": 360,
  "day_end_minute": 1200,
  "hunger_decay_per_min": 0.07,
  "energy_decay_per_min": 0.06,
  "energy_regen_sleeping_per_min": 0.35,
  "warmth_decay_night_per_min": 0.25,
  "warmth_decay_night_sleeping_per_min": 0.12,
  "warmth_regen_day_per_min": 0.5,
  "eat_berries_hunger_restore": 30.0,
  "drink_energy_restore": 5.0,
  "collapse_duration_min": 60,
  "collapse_recover_need_value": 25.0,
  "collapse_recover_energy_value": 40.0,
  "wake_energy_threshold": 95.0,
  "morning_wake_min_energy": 50.0
}
```

- [ ] **Step 3: Write the failing test** (in `tests/test_state.py`)

```python
from genesis import load_settings

def test_load_settings():
    s = load_settings("configs/settings.json")
    assert s["minutes_per_day"] == 1440
    assert s["hunger_decay_per_min"] == 0.07
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_settings'`

- [ ] **Step 5: Implement in `src/genesis/__init__.py`**

```python
import json
from pathlib import Path


def load_settings(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py -v` — Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src tests configs .python-version
git commit -m "Scaffold genesis package with uv and settings loader"
```

---

### Task 2: Core state dataclasses + JSON round-trip

**Files:**
- Create: `src/genesis/world/state.py`, `configs/agents.json`
- Test: `tests/test_state.py` (append)

**Interfaces:**
- Produces:
  - `Needs(hunger: float, energy: float, warmth: float)` — all default 100.0
  - `Agent(id: str, name: str, x: int, y: int, needs: Needs, inventory: dict[str, int], status: str, persona: str, brain: str, knowledge: list[str], current_action: dict | None, collapse_until: int)` — `status` in `{"active", "sleeping", "collapsed"}`, defaults: empty inventory, `"active"`, empty strings/list, `None`, `0`
  - `Resource(type: str, x: int, y: int, qty: int)`
  - `WorldState(sim_minutes: int, seed: int, agents: list[Agent], resources: list[Resource])`
  - `WorldState.to_json() -> str` / `WorldState.from_json(s: str) -> WorldState`
  - `load_agents(path) -> list[Agent]` (module function in `state.py`)

- [ ] **Step 1: Write `configs/agents.json`**

```json
{
  "agents": [
    {"id": "ash", "name": "Ash", "x": 9, "y": 5, "persona": "curious and bold", "brain": ""},
    {"id": "bramble", "name": "Bramble", "x": 6, "y": 3, "persona": "cautious and practical", "brain": ""},
    {"id": "cinder", "name": "Cinder", "x": 5, "y": 7, "persona": "social and scatterbrained", "brain": ""},
    {"id": "dew", "name": "Dew", "x": 8, "y": 10, "persona": "quiet and observant", "brain": ""}
  ]
}
```

- [ ] **Step 2: Write the failing tests** (append to `tests/test_state.py`)

```python
from genesis.world.state import Needs, Agent, Resource, WorldState, load_agents

def test_world_state_json_roundtrip():
    a = Agent(id="ash", name="Ash", x=1, y=2, needs=Needs(hunger=50.0))
    ws = WorldState(sim_minutes=10, seed=42, agents=[a],
                    resources=[Resource(type="berries", x=3, y=4, qty=9)])
    ws2 = WorldState.from_json(ws.to_json())
    assert ws2.agents[0].needs.hunger == 50.0
    assert ws2.agents[0].needs.energy == 100.0
    assert ws2.resources[0].qty == 9
    assert ws2.seed == 42

def test_load_agents():
    agents = load_agents("configs/agents.json")
    assert len(agents) == 4
    assert agents[0].name == "Ash"
    assert agents[0].status == "active"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'genesis.world.state'`

- [ ] **Step 4: Implement `src/genesis/world/state.py`**

```python
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Needs:
    hunger: float = 100.0
    energy: float = 100.0
    warmth: float = 100.0


@dataclass
class Agent:
    id: str
    name: str
    x: int
    y: int
    needs: Needs = field(default_factory=Needs)
    inventory: dict[str, int] = field(default_factory=dict)
    status: str = "active"  # active | sleeping | collapsed
    persona: str = ""
    brain: str = ""
    knowledge: list[str] = field(default_factory=list)
    current_action: dict | None = None
    collapse_until: int = 0


@dataclass
class Resource:
    type: str
    x: int
    y: int
    qty: int


@dataclass
class WorldState:
    sim_minutes: int
    seed: int
    agents: list[Agent] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> "WorldState":
        d = json.loads(s)
        agents = [
            Agent(**{**a, "needs": Needs(**a["needs"])}) for a in d["agents"]
        ]
        resources = [Resource(**r) for r in d["resources"]]
        return cls(sim_minutes=d["sim_minutes"], seed=d["seed"],
                   agents=agents, resources=resources)


def load_agents(path: str | Path) -> list[Agent]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Agent(**a) for a in d["agents"]]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_state.py -v` — Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/state.py configs/agents.json tests/test_state.py
git commit -m "Add world state dataclasses with JSON round-trip"
```

---

### Task 3: WorldMap grid + starter map config

**Files:**
- Create: `src/genesis/world/grid.py`, `configs/map.json`
- Test: `tests/test_grid.py`

**Interfaces:**
- Produces:
  - `WorldMap.from_file(path) -> WorldMap`
  - `.width: int`, `.height: int`
  - `.terrain(x, y) -> str` — one of `"grass" | "forest" | "rock" | "water" | "sand" | "cave" | "marsh"`; raises `ValueError` if out of bounds
  - `.walkable(x, y) -> bool` — False for water and out-of-bounds
  - `.neighbors4(x, y) -> list[tuple[int, int]]` — in-bounds 4-adjacent tiles
- Consumes: nothing.
- Terrain letters in map rows: `G`rass, `F`orest, `R`ock, `W`ater, `S`and, `C`ave, `M`arsh.

- [ ] **Step 1: Write `configs/map.json`** (20×15 starter; forest NW, rocks+cave NE, river row 9, marsh by river east)

```json
{
  "rows": [
    "FFFFGGGGRRRRCRRGGGGG",
    "FFFFGGGGGRRRRRGGGGGG",
    "FFFFGGGGGGRRGGGGGGGG",
    "FFFGGGGGGGGGGGGGGGGG",
    "FFGGGGGGGGGGGGGGGGGG",
    "FGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGG",
    "GGSWWWWWWWWWWWWWWSGG",
    "GGSSGGGGGGGGGGMMSSGG",
    "GGGGGGGGGGGGGGMMGGGG",
    "GGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGGGGGG"
  ],
  "resources": [
    {"type": "wood", "x": 1, "y": 1, "qty": 40},
    {"type": "wood", "x": 2, "y": 3, "qty": 40},
    {"type": "berries", "x": 1, "y": 2, "qty": 25},
    {"type": "berries", "x": 13, "y": 11, "qty": 25},
    {"type": "stone", "x": 10, "y": 0, "qty": 40},
    {"type": "flint", "x": 12, "y": 1, "qty": 15},
    {"type": "water", "x": 5, "y": 8, "qty": 9999},
    {"type": "water", "x": 12, "y": 8, "qty": 9999},
    {"type": "fish", "x": 7, "y": 8, "qty": 20}
  ]
}
```

- [ ] **Step 2: Write the failing tests** (`tests/test_grid.py`)

```python
import pytest
from genesis.world.grid import WorldMap

def test_map_loads_and_terrain():
    m = WorldMap.from_file("configs/map.json")
    assert (m.width, m.height) == (20, 15)
    assert m.terrain(0, 0) == "forest"
    assert m.terrain(12, 0) == "cave"
    assert m.terrain(5, 8) == "water"
    assert m.terrain(14, 9) == "marsh"

def test_walkable_and_bounds():
    m = WorldMap.from_file("configs/map.json")
    assert m.walkable(0, 0) is True
    assert m.walkable(5, 8) is False          # water
    assert m.walkable(-1, 0) is False
    with pytest.raises(ValueError):
        m.terrain(99, 99)

def test_neighbors4():
    m = WorldMap.from_file("configs/map.json")
    assert set(m.neighbors4(0, 0)) == {(1, 0), (0, 1)}
    assert len(m.neighbors4(5, 5)) == 4
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_grid.py -v` — Expected: FAIL (module not found)

- [ ] **Step 4: Implement `src/genesis/world/grid.py`**

```python
import json
from pathlib import Path

TERRAIN = {"G": "grass", "F": "forest", "R": "rock", "W": "water",
           "S": "sand", "C": "cave", "M": "marsh"}


class WorldMap:
    def __init__(self, rows: list[str]):
        self.rows = rows
        self.height = len(rows)
        self.width = len(rows[0])

    @classmethod
    def from_file(cls, path: str | Path) -> "WorldMap":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d["rows"])

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def terrain(self, x: int, y: int) -> str:
        if not self.in_bounds(x, y):
            raise ValueError(f"out of bounds: ({x}, {y})")
        return TERRAIN[self.rows[y][x]]

    def walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.terrain(x, y) != "water"

    def neighbors4(self, x: int, y: int) -> list[tuple[int, int]]:
        cand = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [(cx, cy) for cx, cy in cand if self.in_bounds(cx, cy)]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_grid.py -v` — Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/grid.py configs/map.json tests/test_grid.py
git commit -m "Add WorldMap grid with starter map config"
```

---

### Task 4: Needs decay, day/night, collapse & recovery

**Files:**
- Create: `src/genesis/world/needs.py`
- Test: `tests/test_needs.py`

**Interfaces:**
- Consumes: `Needs`, `Agent` from `genesis.world.state`; settings dict from `genesis.load_settings`.
- Produces:
  - `is_daytime(sim_minutes: int, settings: dict) -> bool`
  - `tick_needs(agent: Agent, sim_minutes: int, settings: dict) -> list[dict]` — applies one minute of decay/regen to `agent.needs` in place, handles collapse trigger and recovery, returns event dicts (`{"type": "collapsed", "agent": id, "minute": m}` / `{"type": "recovered", ...}`). Clamps all needs to [0, 100].
- Rules: hunger always decays; energy decays while `active`, regenerates while `sleeping`; warmth decays at night (slower if sleeping), regenerates by day. On any need hitting 0 while not collapsed: `status="collapsed"`, `collapse_until = sim_minutes + collapse_duration_min`, `current_action=None`. At `sim_minutes >= collapse_until`: `status="active"`, zeroed needs set to `collapse_recover_need_value`, energy set to at least `collapse_recover_energy_value`.

- [ ] **Step 1: Write the failing tests** (`tests/test_needs.py`)

```python
from genesis import load_settings
from genesis.world.state import Agent, Needs
from genesis.world.needs import tick_needs, is_daytime

S = load_settings("configs/settings.json")
NOON = 720
MIDNIGHT = 0

def make_agent(**kw):
    return Agent(id="t", name="T", x=0, y=0, **kw)

def test_is_daytime():
    assert is_daytime(NOON, S) is True
    assert is_daytime(MIDNIGHT, S) is False
    assert is_daytime(1440 + NOON, S) is True   # day 2

def test_hunger_and_energy_decay_active_day():
    a = make_agent()
    tick_needs(a, NOON, S)
    assert a.needs.hunger == 100 - S["hunger_decay_per_min"]
    assert a.needs.energy == 100 - S["energy_decay_per_min"]
    assert a.needs.warmth == 100.0    # clamped, regens by day

def test_warmth_decays_at_night():
    a = make_agent()
    tick_needs(a, MIDNIGHT, S)
    assert a.needs.warmth == 100 - S["warmth_decay_night_per_min"]

def test_sleeping_regenerates_energy():
    a = make_agent(status="sleeping", needs=Needs(energy=50.0))
    tick_needs(a, NOON, S)
    assert a.needs.energy == 50 + S["energy_regen_sleeping_per_min"]

def test_collapse_and_recovery():
    a = make_agent(needs=Needs(hunger=0.05))
    events = tick_needs(a, NOON, S)
    assert a.status == "collapsed"
    assert events[0]["type"] == "collapsed"
    assert a.collapse_until == NOON + S["collapse_duration_min"]
    events = tick_needs(a, a.collapse_until, S)
    assert a.status == "active"
    assert a.needs.hunger == S["collapse_recover_need_value"]
    assert a.needs.energy >= S["collapse_recover_energy_value"]
    assert events[0]["type"] == "recovered"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_needs.py -v` — Expected: FAIL (module not found)

- [ ] **Step 3: Implement `src/genesis/world/needs.py`**

```python
from genesis.world.state import Agent


def is_daytime(sim_minutes: int, settings: dict) -> bool:
    m = sim_minutes % settings["minutes_per_day"]
    return settings["day_start_minute"] <= m < settings["day_end_minute"]


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def tick_needs(agent: Agent, sim_minutes: int, settings: dict) -> list[dict]:
    events: list[dict] = []
    n = agent.needs

    if agent.status == "collapsed":
        if sim_minutes >= agent.collapse_until:
            agent.status = "active"
            for attr in ("hunger", "energy", "warmth"):
                if getattr(n, attr) <= 0:
                    setattr(n, attr, settings["collapse_recover_need_value"])
            n.energy = max(n.energy, settings["collapse_recover_energy_value"])
            events.append({"type": "recovered", "agent": agent.id,
                           "minute": sim_minutes})
        return events

    day = is_daytime(sim_minutes, settings)
    n.hunger = _clamp(n.hunger - settings["hunger_decay_per_min"])
    if agent.status == "sleeping":
        n.energy = _clamp(n.energy + settings["energy_regen_sleeping_per_min"])
    else:
        n.energy = _clamp(n.energy - settings["energy_decay_per_min"])
    if day:
        n.warmth = _clamp(n.warmth + settings["warmth_regen_day_per_min"])
    else:
        rate = (settings["warmth_decay_night_sleeping_per_min"]
                if agent.status == "sleeping"
                else settings["warmth_decay_night_per_min"])
        n.warmth = _clamp(n.warmth - rate)

    if min(n.hunger, n.energy, n.warmth) <= 0:
        agent.status = "collapsed"
        agent.collapse_until = sim_minutes + settings["collapse_duration_min"]
        agent.current_action = None
        events.append({"type": "collapsed", "agent": agent.id,
                       "minute": sim_minutes})
    return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_needs.py -v` — Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/needs.py tests/test_needs.py
git commit -m "Add needs decay, day/night cycle, collapse and recovery"
```

---

### Task 5: Action validation + one-tick execution

**Files:**
- Create: `src/genesis/world/actions.py`
- Test: `tests/test_actions.py`

**Interfaces:**
- Consumes: `Agent`, `WorldState`, `Resource` from state; `WorldMap` from grid; settings dict.
- Produces:
  - `validate_action(action: dict, agent: Agent, state: WorldState, world_map: WorldMap) -> tuple[bool, str]` — `(True, "")` or `(False, reason)`. Unknown verbs and malformed dicts are rejected, never raised.
  - `step_action(agent: Agent, state: WorldState, world_map: WorldMap, settings: dict) -> list[dict]` — executes **one tick** of `agent.current_action`, mutating state; clears `current_action` when finished; returns event dicts. Event types: `moved`, `arrived`, `blocked`, `gathered`, `gather_failed`, `ate`, `eat_failed`, `drank`, `drink_failed`, `slept`, `woke`, `observed`, `action_rejected`.
- Action dicts (the complete Plan-1 schema):
  - `{"action": "move_to", "x": int, "y": int}` — one greedy step per tick toward target (prefer larger axis gap; if preferred step unwalkable try the other axis; if both blocked emit `blocked` and clear the action). Emits `arrived` on reaching target.
  - `{"action": "gather", "resource": str}` — requires a resource of that type on the agent's tile or a 4-adjacent tile with `qty > 0`; transfers 1 unit per tick into inventory (water is not gatherable — use drink); finishes after one gather event (LLM/instinct re-issues to keep gathering).
  - `{"action": "eat"}` — consumes 1 `berries` from inventory, hunger += `eat_berries_hunger_restore`.
  - `{"action": "drink"}` — requires agent on/adjacent to a water terrain tile; energy += `drink_energy_restore`.
  - `{"action": "sleep"}` — sets `status="sleeping"`; while sleeping, `step_action` wakes the agent (`status="active"`, emit `woke`, clear action) when `energy >= wake_energy_threshold`, or when daytime begins and `energy >= morning_wake_min_energy`.
  - `{"action": "observe"}` — emits one `observed` event describing terrain + visible agents within 3 tiles (Chebyshev distance), then finishes.

- [ ] **Step 1: Write the failing tests** (`tests/test_actions.py`)

```python
from genesis import load_settings
from genesis.world.state import Agent, Needs, Resource, WorldState
from genesis.world.grid import WorldMap
from genesis.world.actions import validate_action, step_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
NOON = 720

def make_world(agent, resources=None):
    return WorldState(sim_minutes=NOON, seed=1, agents=[agent],
                      resources=resources or [])

def test_validate_rejects_unknown_and_malformed():
    a = Agent(id="t", name="T", x=5, y=5)
    ok, why = validate_action({"action": "fly"}, a, make_world(a), M)
    assert ok is False and "fly" in why
    ok, _ = validate_action({"action": "move_to", "x": 5}, a, make_world(a), M)
    assert ok is False

def test_move_steps_toward_target_and_arrives():
    a = Agent(id="t", name="T", x=5, y=5,
              current_action={"action": "move_to", "x": 7, "y": 5})
    st = make_world(a)
    ev = step_action(a, st, M, S)
    assert (a.x, a.y) == (6, 5) and ev[0]["type"] == "moved"
    ev = step_action(a, st, M, S)
    assert (a.x, a.y) == (7, 5)
    assert any(e["type"] == "arrived" for e in ev)
    assert a.current_action is None

def test_move_does_not_enter_water():
    a = Agent(id="t", name="T", x=5, y=7,
              current_action={"action": "move_to", "x": 5, "y": 10})
    st = make_world(a)
    step_action(a, st, M, S)          # tries (5,8)=water, sidesteps on x
    assert M.walkable(a.x, a.y)

def test_gather_transfers_one_unit():
    r = Resource(type="berries", x=1, y=2, qty=3)
    a = Agent(id="t", name="T", x=1, y=2,
              current_action={"action": "gather", "resource": "berries"})
    st = make_world(a, [r])
    ev = step_action(a, st, M, S)
    assert a.inventory["berries"] == 1 and r.qty == 2
    assert ev[0]["type"] == "gathered" and a.current_action is None

def test_gather_fails_without_resource():
    a = Agent(id="t", name="T", x=5, y=5,
              current_action={"action": "gather", "resource": "berries"})
    ev = step_action(a, make_world(a), M, S)
    assert ev[0]["type"] == "gather_failed" and a.current_action is None

def test_eat_restores_hunger():
    a = Agent(id="t", name="T", x=5, y=5, needs=Needs(hunger=40.0),
              inventory={"berries": 2}, current_action={"action": "eat"})
    step_action(a, make_world(a), M, S)
    assert a.needs.hunger == 40 + S["eat_berries_hunger_restore"]
    assert a.inventory["berries"] == 1

def test_drink_requires_water_adjacency():
    a = Agent(id="t", name="T", x=5, y=7, needs=Needs(energy=50.0),
              current_action={"action": "drink"})   # (5,8) is water
    ev = step_action(a, make_world(a), M, S)
    assert ev[0]["type"] == "drank"
    b = Agent(id="u", name="U", x=1, y=1, current_action={"action": "drink"})
    ev = step_action(b, make_world(b), M, S)
    assert ev[0]["type"] == "drink_failed"

def test_sleep_until_rested():
    a = Agent(id="t", name="T", x=5, y=5, needs=Needs(energy=94.9),
              current_action={"action": "sleep"})
    st = make_world(a)
    step_action(a, st, M, S)
    assert a.status == "sleeping"
    a.needs.energy = 96.0
    ev = step_action(a, st, M, S)
    assert a.status == "active" and ev[0]["type"] == "woke"

def test_observe_sees_nearby_agents():
    a = Agent(id="t", name="T", x=5, y=5, current_action={"action": "observe"})
    b = Agent(id="u", name="U", x=7, y=6)
    st = WorldState(sim_minutes=NOON, seed=1, agents=[a, b])
    ev = step_action(a, st, M, S)
    assert ev[0]["type"] == "observed" and "U" in ev[0]["seen_agents"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_actions.py -v` — Expected: FAIL (module not found)

- [ ] **Step 3: Implement `src/genesis/world/actions.py`**

```python
from genesis.world.grid import WorldMap
from genesis.world.needs import is_daytime
from genesis.world.state import Agent, WorldState

VERBS = {"move_to", "gather", "eat", "drink", "sleep", "observe"}


def validate_action(action: dict, agent: Agent, state: WorldState,
                    world_map: WorldMap) -> tuple[bool, str]:
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
    return True, ""


def _tiles_near(agent: Agent, world_map: WorldMap) -> list[tuple[int, int]]:
    return [(agent.x, agent.y)] + world_map.neighbors4(agent.x, agent.y)


def _find_resource(state: WorldState, rtype: str, tiles: list[tuple[int, int]]):
    for r in state.resources:
        if r.type == rtype and r.qty > 0 and (r.x, r.y) in tiles:
            return r
    return None


def _finish(agent: Agent, event: dict) -> list[dict]:
    agent.current_action = None
    return [event]


def step_action(agent: Agent, state: WorldState, world_map: WorldMap,
                settings: dict) -> list[dict]:
    action = agent.current_action
    if action is None:
        return []
    ok, why = validate_action(action, agent, state, world_map)
    if not ok:
        return _finish(agent, {"type": "action_rejected", "agent": agent.id,
                               "reason": why})
    verb = action["action"]
    m = state.sim_minutes

    if verb == "move_to":
        tx, ty = action["x"], action["y"]
        if (agent.x, agent.y) == (tx, ty):
            return _finish(agent, {"type": "arrived", "agent": agent.id,
                                   "x": tx, "y": ty})
        dx, dy = tx - agent.x, ty - agent.y
        steps = []
        if abs(dx) >= abs(dy) and dx != 0:
            steps = [(agent.x + (1 if dx > 0 else -1), agent.y),
                     (agent.x, agent.y + (1 if dy > 0 else -1)) if dy else None]
        else:
            steps = [(agent.x, agent.y + (1 if dy > 0 else -1)),
                     (agent.x + (1 if dx > 0 else -1), agent.y) if dx else None]
        for step in steps:
            if step and world_map.walkable(*step):
                agent.x, agent.y = step
                events = [{"type": "moved", "agent": agent.id,
                           "x": agent.x, "y": agent.y}]
                if (agent.x, agent.y) == (tx, ty):
                    agent.current_action = None
                    events.append({"type": "arrived", "agent": agent.id,
                                   "x": tx, "y": ty})
                return events
        return _finish(agent, {"type": "blocked", "agent": agent.id})

    if verb == "gather":
        rtype = action["resource"]
        if rtype == "water":
            return _finish(agent, {"type": "gather_failed", "agent": agent.id,
                                   "resource": rtype, "reason": "drink water instead"})
        r = _find_resource(state, rtype, _tiles_near(agent, world_map))
        if r is None:
            return _finish(agent, {"type": "gather_failed", "agent": agent.id,
                                   "resource": rtype, "reason": "nothing here"})
        r.qty -= 1
        agent.inventory[rtype] = agent.inventory.get(rtype, 0) + 1
        return _finish(agent, {"type": "gathered", "agent": agent.id,
                               "resource": rtype, "qty": 1})

    if verb == "eat":
        if agent.inventory.get("berries", 0) < 1:
            return _finish(agent, {"type": "eat_failed", "agent": agent.id,
                                   "reason": "no food carried"})
        agent.inventory["berries"] -= 1
        agent.needs.hunger = min(
            100.0, agent.needs.hunger + settings["eat_berries_hunger_restore"])
        return _finish(agent, {"type": "ate", "agent": agent.id})

    if verb == "drink":
        near_water = any(
            world_map.in_bounds(x, y) and world_map.terrain(x, y) == "water"
            for x, y in _tiles_near(agent, world_map))
        if not near_water:
            return _finish(agent, {"type": "drink_failed", "agent": agent.id,
                                   "reason": "no water here"})
        agent.needs.energy = min(
            100.0, agent.needs.energy + settings["drink_energy_restore"])
        return _finish(agent, {"type": "drank", "agent": agent.id})

    if verb == "sleep":
        if agent.status != "sleeping":
            agent.status = "sleeping"
            return [{"type": "slept", "agent": agent.id, "minute": m}]
        day = is_daytime(m, settings)
        if (agent.needs.energy >= settings["wake_energy_threshold"]
                or (day and agent.needs.energy >= settings["morning_wake_min_energy"])):
            agent.status = "active"
            return _finish(agent, {"type": "woke", "agent": agent.id, "minute": m})
        return []

    if verb == "observe":
        seen = [o.name for o in state.agents if o.id != agent.id
                and max(abs(o.x - agent.x), abs(o.y - agent.y)) <= 3]
        return _finish(agent, {"type": "observed", "agent": agent.id,
                               "terrain": world_map.terrain(agent.x, agent.y),
                               "seen_agents": seen})
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_actions.py -v` — Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/actions.py tests/test_actions.py
git commit -m "Add action validation and per-tick execution"
```

---

### Task 6: Instinct policy (rule-based action chooser)

**Files:**
- Create: `src/genesis/world/instinct.py`
- Test: `tests/test_instinct.py`

**Interfaces:**
- Consumes: `Agent`, `WorldState`, `WorldMap`, `is_daytime`, settings; `random.Random` instance.
- Produces: `choose_action(agent: Agent, state: WorldState, world_map: WorldMap, settings: dict, rng) -> dict | None` — returns an action dict or `None` (collapsed/sleeping agents). **This function is permanent: in Plan 3 it is the fallback when the LLM fails.**
- Priority order (first match wins):
  1. `status != "active"` → `None`
  2. night → `sleep`
  3. `hunger < 40` and carrying berries → `eat`
  4. `hunger < 40` → `gather` berries if adjacent, else `move_to` the nearest berries resource with qty > 0 (nearest by Manhattan distance; ties broken by list order; target the nearest walkable 4-neighbor of the resource tile, or the tile itself if walkable)
  5. `energy < 30` → `sleep`
  6. otherwise → wander: `move_to` a random walkable tile within ±3 of current position (retry up to 10 rng draws, else `observe`)

- [ ] **Step 1: Write the failing tests** (`tests/test_instinct.py`)

```python
import random
from genesis import load_settings
from genesis.world.state import Agent, Needs, Resource, WorldState
from genesis.world.grid import WorldMap
from genesis.world.instinct import choose_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
NOON, MIDNIGHT = 720, 0

def world(agent, minutes=NOON, resources=None):
    return WorldState(sim_minutes=minutes, seed=1, agents=[agent],
                      resources=resources or [])

def test_sleeps_at_night():
    a = Agent(id="t", name="T", x=5, y=5)
    assert choose_action(a, world(a, MIDNIGHT), M, S, random.Random(1)) == {"action": "sleep"}

def test_eats_carried_food_when_hungry():
    a = Agent(id="t", name="T", x=5, y=5, needs=Needs(hunger=30.0),
              inventory={"berries": 1})
    assert choose_action(a, world(a), M, S, random.Random(1)) == {"action": "eat"}

def test_moves_to_food_when_hungry_and_empty_handed():
    a = Agent(id="t", name="T", x=5, y=5, needs=Needs(hunger=30.0))
    r = Resource(type="berries", x=1, y=2, qty=10)
    act = choose_action(a, world(a, resources=[r]), M, S, random.Random(1))
    assert act["action"] == "move_to"

def test_gathers_when_on_food():
    a = Agent(id="t", name="T", x=1, y=2, needs=Needs(hunger=30.0))
    r = Resource(type="berries", x=1, y=2, qty=10)
    act = choose_action(a, world(a, resources=[r]), M, S, random.Random(1))
    assert act == {"action": "gather", "resource": "berries"}

def test_wanders_by_default_to_walkable_tile():
    a = Agent(id="t", name="T", x=5, y=5)
    act = choose_action(a, world(a), M, S, random.Random(1))
    assert act["action"] == "move_to" and M.walkable(act["x"], act["y"])

def test_none_when_collapsed():
    a = Agent(id="t", name="T", x=5, y=5, status="collapsed")
    assert choose_action(a, world(a), M, S, random.Random(1)) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_instinct.py -v` — Expected: FAIL (module not found)

- [ ] **Step 3: Implement `src/genesis/world/instinct.py`**

```python
from genesis.world.grid import WorldMap
from genesis.world.needs import is_daytime
from genesis.world.state import Agent, WorldState


def _nearest_resource(agent: Agent, state: WorldState, rtype: str):
    best, best_d = None, None
    for r in state.resources:
        if r.type == rtype and r.qty > 0:
            d = abs(r.x - agent.x) + abs(r.y - agent.y)
            if best_d is None or d < best_d:
                best, best_d = r, d
    return best


def _target_tile(r, world_map: WorldMap) -> tuple[int, int] | None:
    if world_map.walkable(r.x, r.y):
        return r.x, r.y
    for nx, ny in world_map.neighbors4(r.x, r.y):
        if world_map.walkable(nx, ny):
            return nx, ny
    return None


def choose_action(agent: Agent, state: WorldState, world_map: WorldMap,
                  settings: dict, rng) -> dict | None:
    if agent.status != "active":
        return None
    if not is_daytime(state.sim_minutes, settings):
        return {"action": "sleep"}
    if agent.needs.hunger < 40:
        if agent.inventory.get("berries", 0) > 0:
            return {"action": "eat"}
        r = _nearest_resource(agent, state, "berries")
        if r is not None:
            near = [(agent.x, agent.y)] + world_map.neighbors4(agent.x, agent.y)
            if (r.x, r.y) in near:
                return {"action": "gather", "resource": "berries"}
            t = _target_tile(r, world_map)
            if t is not None:
                return {"action": "move_to", "x": t[0], "y": t[1]}
    if agent.needs.energy < 30:
        return {"action": "sleep"}
    for _ in range(10):
        tx = agent.x + rng.randint(-3, 3)
        ty = agent.y + rng.randint(-3, 3)
        if world_map.walkable(tx, ty) and (tx, ty) != (agent.x, agent.y):
            return {"action": "move_to", "x": tx, "y": ty}
    return {"action": "observe"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_instinct.py -v` — Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/instinct.py tests/test_instinct.py
git commit -m "Add rule-based instinct policy for agent actions"
```

---

### Task 7: Engine — tick, advance, determinism

**Files:**
- Create: `src/genesis/world/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `Engine(state: WorldState, world_map: WorldMap, settings: dict)` — creates `self.rng = random.Random(state.seed)` once at construction.
  - `.tick() -> list[dict]` — one sim-minute: for each agent (list order): `tick_needs`; then if `current_action is None` and status allows, `choose_action` (instinct); then `step_action`. Increments `state.sim_minutes` at the end. Every returned event gets `"minute"` set to the minute it occurred in.
  - `.advance(minutes: int) -> list[dict]` — runs `tick()` n times, returns all events concatenated. This is the fast-forward primitive; live play and catch-up both call it.
- Determinism rule: identical `(state JSON, settings, map)` inputs → `advance(n)` yields identical end-state JSON and identical events.

- [ ] **Step 1: Write the failing tests** (`tests/test_engine.py`)

```python
from genesis import load_settings
from genesis.world.state import WorldState, load_agents
from genesis.world.grid import WorldMap
from genesis.world.engine import Engine

S = load_settings("configs/settings.json")

def fresh_state(seed=42):
    return WorldState(sim_minutes=720, seed=seed,
                      agents=load_agents("configs/agents.json"))

def make_engine(seed=42):
    return Engine(fresh_state(seed), WorldMap.from_file("configs/map.json"), S)

def test_tick_advances_time_and_decays_needs():
    e = make_engine()
    e.tick()
    assert e.state.sim_minutes == 721
    assert e.state.agents[0].needs.hunger < 100

def test_agents_get_instinct_actions_and_move():
    e = make_engine()
    before = [(a.x, a.y) for a in e.state.agents]
    e.advance(30)
    after = [(a.x, a.y) for a in e.state.agents]
    assert before != after             # somebody actually moved

def test_events_carry_minute():
    e = make_engine()
    events = e.advance(10)
    assert events and all("minute" in ev for ev in events)

def test_fast_forward_is_deterministic():
    e1, e2 = make_engine(seed=7), make_engine(seed=7)
    ev1, ev2 = e1.advance(600), e2.advance(600)
    assert e1.state.to_json() == e2.state.to_json()
    assert ev1 == ev2

def test_different_seeds_diverge():
    e1, e2 = make_engine(seed=1), make_engine(seed=2)
    e1.advance(600); e2.advance(600)
    assert e1.state.to_json() != e2.state.to_json()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_engine.py -v` — Expected: FAIL (module not found)

- [ ] **Step 3: Implement `src/genesis/world/engine.py`**

```python
import random

from genesis.world.actions import step_action
from genesis.world.grid import WorldMap
from genesis.world.instinct import choose_action
from genesis.world.needs import tick_needs
from genesis.world.state import WorldState


class Engine:
    def __init__(self, state: WorldState, world_map: WorldMap, settings: dict):
        self.state = state
        self.world_map = world_map
        self.settings = settings
        self.rng = random.Random(state.seed)

    def tick(self) -> list[dict]:
        events: list[dict] = []
        minute = self.state.sim_minutes
        for agent in self.state.agents:
            events += tick_needs(agent, minute, self.settings)
            if agent.current_action is None and agent.status in ("active", "sleeping"):
                agent.current_action = choose_action(
                    agent, self.state, self.world_map, self.settings, self.rng)
            events += step_action(agent, self.state, self.world_map, self.settings)
        for ev in events:
            ev.setdefault("minute", minute)
        self.state.sim_minutes += 1
        return events

    def advance(self, minutes: int) -> list[dict]:
        events: list[dict] = []
        for _ in range(minutes):
            events += self.tick()
        return events
```

Note: a sleeping agent has `current_action == {"action": "sleep"}` until it wakes, so `choose_action` is only consulted when the previous action finished — sleeping agents are not re-planned every tick.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_engine.py -v` — Expected: PASS (5 tests)

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v` — Expected: all tests from Tasks 1–7 PASS

- [ ] **Step 6: Commit**

```bash
git add src/genesis/world/engine.py tests/test_engine.py
git commit -m "Add engine tick and deterministic fast-forward"
```

---

### Task 8: SQLite persistence + event log

**Files:**
- Create: `src/genesis/persistence/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `WorldState` (its `to_json`/`from_json`).
- Produces:
  - `connect(path: str | Path) -> sqlite3.Connection` — opens/creates the DB and ensures schema. Schema: `world(id INTEGER PRIMARY KEY CHECK (id = 1), state_json TEXT NOT NULL)`, `events(id INTEGER PRIMARY KEY AUTOINCREMENT, minute INTEGER NOT NULL, type TEXT NOT NULL, payload_json TEXT NOT NULL)`.
  - `save_state(conn, state: WorldState) -> None` — upsert of row id 1.
  - `load_state(conn) -> WorldState | None` — `None` if never saved.
  - `append_events(conn, events: list[dict]) -> None` — each dict must carry `minute` and `type`; full dict stored as `payload_json`.
  - `load_events(conn, since_minute: int = 0) -> list[dict]` — payload dicts ordered by insertion id.

- [ ] **Step 1: Write the failing tests** (`tests/test_db.py`)

```python
from genesis.world.state import Agent, WorldState
from genesis.persistence.db import connect, save_state, load_state, append_events, load_events

def test_state_roundtrip(tmp_path):
    conn = connect(tmp_path / "w.db")
    assert load_state(conn) is None
    ws = WorldState(sim_minutes=99, seed=5,
                    agents=[Agent(id="a", name="A", x=1, y=1)])
    save_state(conn, ws)
    ws.sim_minutes = 150
    save_state(conn, ws)                     # upsert, not duplicate
    loaded = load_state(conn)
    assert loaded.sim_minutes == 150 and loaded.agents[0].name == "A"

def test_event_log_appends_and_filters(tmp_path):
    conn = connect(tmp_path / "w.db")
    append_events(conn, [{"type": "moved", "minute": 10, "agent": "a"},
                         {"type": "ate", "minute": 20, "agent": "a"}])
    assert len(load_events(conn)) == 2
    later = load_events(conn, since_minute=15)
    assert len(later) == 1 and later[0]["type"] == "ate"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_db.py -v` — Expected: FAIL (module not found)

- [ ] **Step 3: Implement `src/genesis/persistence/db.py`**

```python
import json
import sqlite3
from pathlib import Path

from genesis.world.state import WorldState

SCHEMA = """
CREATE TABLE IF NOT EXISTS world (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    state_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    minute INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    return conn


def save_state(conn: sqlite3.Connection, state: WorldState) -> None:
    conn.execute(
        "INSERT INTO world (id, state_json) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET state_json = excluded.state_json",
        (state.to_json(),))
    conn.commit()


def load_state(conn: sqlite3.Connection) -> WorldState | None:
    row = conn.execute("SELECT state_json FROM world WHERE id = 1").fetchone()
    return WorldState.from_json(row[0]) if row else None


def append_events(conn: sqlite3.Connection, events: list[dict]) -> None:
    conn.executemany(
        "INSERT INTO events (minute, type, payload_json) VALUES (?, ?, ?)",
        [(ev["minute"], ev["type"], json.dumps(ev)) for ev in events])
    conn.commit()


def load_events(conn: sqlite3.Connection, since_minute: int = 0) -> list[dict]:
    rows = conn.execute(
        "SELECT payload_json FROM events WHERE minute >= ? ORDER BY id",
        (since_minute,)).fetchall()
    return [json.loads(r[0]) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_db.py -v` — Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/genesis/persistence/db.py tests/test_db.py
git commit -m "Add SQLite persistence for world state and event log"
```

---

### Task 9: CLI smoke runner

**Files:**
- Create: `src/genesis/cli.py`
- Test: `tests/test_cli.py`
- Modify: `README.md` (create — project intro + how to run)

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `run_sim(days: float, db_path: str | Path, seed: int = 42) -> dict` — loads state from DB if present, else creates a fresh world (agents from `configs/agents.json`, resources from `configs/map.json`, `sim_minutes=720`); advances `int(days * 1440)` minutes; saves state + events; returns a summary dict `{"sim_minutes": int, "days_run": float, "event_counts": dict[str, int], "agents": [{"name", "x", "y", "hunger", "energy", "warmth", "status", "inventory"}]}`.
  - `python -m genesis.cli --days 2 --db world.db` prints the summary as pretty JSON.

- [ ] **Step 1: Write the failing tests** (`tests/test_cli.py`)

```python
from genesis.cli import run_sim
from genesis.persistence.db import connect, load_state

def test_run_sim_two_days_survives_and_persists(tmp_path):
    db = tmp_path / "w.db"
    summary = run_sim(days=2, db_path=db, seed=42)
    assert summary["sim_minutes"] == 720 + 2 * 1440
    assert summary["event_counts"].get("moved", 0) > 0
    assert len(summary["agents"]) == 4
    # persisted: a second run continues from saved time
    summary2 = run_sim(days=0.5, db_path=db, seed=42)
    assert summary2["sim_minutes"] == 720 + 2 * 1440 + 720

def test_agents_do_not_stay_collapsed_forever(tmp_path):
    summary = run_sim(days=3, db_path=tmp_path / "w.db", seed=7)
    collapsed_final = [a for a in summary["agents"] if a["status"] == "collapsed"]
    assert len(collapsed_final) < 4     # world did not dead-end
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v` — Expected: FAIL (module not found)

- [ ] **Step 3: Implement `src/genesis/cli.py`**

```python
import argparse
import json
from collections import Counter
from pathlib import Path

from genesis import load_settings
from genesis.persistence.db import append_events, connect, load_state, save_state
from genesis.world.engine import Engine
from genesis.world.grid import WorldMap
from genesis.world.state import Resource, WorldState, load_agents

CONFIG_DIR = Path("configs")


def _fresh_world(seed: int) -> WorldState:
    map_cfg = json.loads((CONFIG_DIR / "map.json").read_text(encoding="utf-8"))
    return WorldState(
        sim_minutes=720, seed=seed,
        agents=load_agents(CONFIG_DIR / "agents.json"),
        resources=[Resource(**r) for r in map_cfg["resources"]])


def run_sim(days: float, db_path: str | Path, seed: int = 42) -> dict:
    settings = load_settings(CONFIG_DIR / "settings.json")
    conn = connect(db_path)
    state = load_state(conn) or _fresh_world(seed)
    engine = Engine(state, WorldMap.from_file(CONFIG_DIR / "map.json"), settings)
    events = engine.advance(int(days * settings["minutes_per_day"]))
    save_state(conn, state)
    append_events(conn, events)
    return {
        "sim_minutes": state.sim_minutes,
        "days_run": days,
        "event_counts": dict(Counter(ev["type"] for ev in events)),
        "agents": [{
            "name": a.name, "x": a.x, "y": a.y,
            "hunger": round(a.needs.hunger, 1),
            "energy": round(a.needs.energy, 1),
            "warmth": round(a.needs.warmth, 1),
            "status": a.status, "inventory": a.inventory,
        } for a in state.agents],
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Run the Genesis world simulation")
    p.add_argument("--days", type=float, default=1.0)
    p.add_argument("--db", default="world.db")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    print(json.dumps(run_sim(args.days, args.db, args.seed), indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v` — Expected: PASS (2 tests)

- [ ] **Step 5: Run the full suite and a real smoke run**

```bash
uv run pytest -v
uv run python -m genesis.cli --days 2 --db world.db
```

Expected: all tests PASS; the smoke run prints a summary with nonzero `moved`/`gathered`/`slept` counts and 4 agents with sane needs. Add `world.db` to `.gitignore`.

- [ ] **Step 6: Write `README.md`**

```markdown
# Genesis

A fantasy world simulation where AI agents start from nothing — no knowledge,
no tools — and figure out how to survive. Each agent's mind will be a different
LLM (Plan 3); the world itself is a deterministic engine.

## Status

Plan 1 (world engine core) — rule-driven agents, needs, day/night, persistence.

## Run

    uv sync
    uv run pytest
    uv run python -m genesis.cli --days 2 --db world.db

## Docs

- Design spec: docs/superpowers/specs/2026-08-29-genesis-phase1-design.md
- Plans: docs/superpowers/plans/
```

- [ ] **Step 7: Commit**

```bash
git add src/genesis/cli.py tests/test_cli.py README.md .gitignore
git commit -m "Add CLI smoke runner and README"
```

---

## Done criteria (Plan 1)

- `uv run pytest` — full suite green.
- `uv run python -m genesis.cli --days 2` — agents move, gather, eat, sleep through two day/night cycles; collapses recover; run continues from saved DB state on re-run.
- Determinism test proves same seed + same elapsed time = identical world.

## Follow-on plans (not in this document)

- **Plan 2 — Discovery & Danger:** discovery graph + `experiment_with` + `build` + structures; wolves, Cave Lurker, wisps, storms (spec §4–§5).
- **Plan 3 — Minds:** memory stream, retrieval, reflection, planning; Brain adapters (Groq/Gemini/Ollama), ThinkQueue, conversations + `talk_to`/`give` (spec §6–§7, §10).
- **Plan 4 — API & Viewer:** FastAPI + SSE, Phaser 3 viewer with LPC animated sprites, scoreboard, away-digest (spec §8–§9).
