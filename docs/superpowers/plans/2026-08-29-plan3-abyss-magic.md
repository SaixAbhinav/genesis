# Genesis Plan 3: The Abyss & Magic — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the flat survival world into a vertical, layered Abyss where descending is cheap but ascending inflicts an escalating Curse (strain), and give rule-driven agents a Mushoku Tensei magic system (mana, attributes, ranks, spells) that lets them survive deeper strata.

**Architecture:** Extends the Plan 1–2 deterministic engine. Each layer is its own `WorldMap`; `Engine` holds `maps: list[WorldMap]` and resolves the map per agent via `agent.layer`. A new `strain` stat rises only on ascent. Magic is data-driven: spells are **typed effect records** (`{name, kind, requires, prereqs, effect}`) executed by an `effects.py` dispatch table — the same schema a future generative engine will coin into. New actions (`cast`, `descend`, `ascend`, `harvest_relic`) plug into the existing `step_action` dispatcher. No LLM yet — the instinct policy gains an Abyss/magic ladder.

**Tech Stack:** Python 3.12, uv, pytest, stdlib only. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-29-plan3-abyss-magic-design.md`
**Roadmap:** `docs/superpowers/specs/2026-08-29-genesis-roadmap.md`

**Depends on:** Plans 1–2 — merged or on branch `feat/discovery-crafting-building`.

## Global Constraints

- Package manager is **uv** (`uv run pytest`, `uv add`) — never pip/venv.
- Engine stays deterministic: all randomness via the Engine's `random.Random(seed)`; no module-level `random`, no wall-clock reads in the engine.
- The engine never calls an LLM and never blocks on anything external.
- **Backward compatibility:** `WorldState.from_json` must still load Plan 1–2 JSON lacking the new keys. Use `d.get(...)` with defaults; new `Agent`/`Resource`/`Structure` fields all have defaults so old JSON loads unchanged.
- **New signatures are additive:** `validate_action`, `step_action`, `choose_action` gain an optional `magic=None` parameter (alongside the existing `graph=None`) so every existing test still passes unchanged. `Engine` accepts either a single `world_map` (wrapped into a one-element `maps` list) or `maps=[...]`.
- New action verbs this plan: `cast`, `descend`, `ascend`, `harvest_relic`. Full verb set becomes `{move_to, gather, eat, drink, sleep, observe, experiment_with, build, cast, descend, ascend, harvest_relic}`.
- **Discoveries are typed effect records** (spec §2). Spells live in `configs/magic.json`; each is a record the engine interprets via `effects.apply_effect`. Do NOT hard-code spell behaviour in `actions.py`.
- Engine layers are **0-indexed** (`agent.layer`): `L0` = Edge of the Abyss, `L1` = Forest of Temptation, `L2` = Great Fault.
- Git: continue on branch `feat/discovery-crafting-building` (or a new `feat/abyss-magic` branch off it); imperative commit messages; **no Claude attribution anywhere**.
- All work happens in `projects/genesis/`.

## File Structure (this plan)

```
configs/
  layers.json          # NEW: per-layer depth, curse_strain, hazards, scarcity, relics, magic_gate, link tiles
  magic.json           # NEW: attributes, ranks (+xp thresholds), spells (typed effect records), mana params
  maps/layer0.json     # NEW: Edge of the Abyss map
  maps/layer1.json     # NEW: Forest of Temptation map
  maps/layer2.json     # NEW: Great Fault map
  settings.json        # MODIFY: strain / curse / miasma / fall / mana tuning constants
  agents.json          # MODIFY: seed starting attributes + mana
src/genesis/world/
  state.py             # MODIFY: Agent/Resource/Structure new fields; "dead" status; serialization
  effects.py           # NEW: apply_effect() dispatch table (typed effect records)
  magic.py             # NEW: MagicBook — spells, ranks, xp, mana growth, cast-time
  abyss.py             # NEW: layer config + Curse helpers (curse_strain, strain decay, side-effect bands)
  hazards.py           # NEW: miasma / fall / creature encounter checks
  actions.py           # MODIFY: cast, descend, ascend, harvest_relic verbs; per-layer resource filtering
  needs.py             # MODIFY: strain decay + curse-only death in tick_needs
  instinct.py          # MODIFY: Abyss/magic ladder (survive/descend/harvest/train)
  engine.py            # MODIFY: maps list, layers, magic; skip dead; strain + hazards in tick
  cli.py               # MODIFY: report layer/strain/mana/ranks/deaths
tests/
  test_state_abyss.py  test_effects.py  test_magic.py  test_cast.py
  test_magic_discovery.py  test_curse.py  test_death.py  test_curse_bands.py
  test_hazards.py  test_relics.py  test_instinct_abyss.py
  test_integration_dive.py
```

---

### Task 1: State model — Abyss & magic fields

**Files:**
- Modify: `src/genesis/world/state.py`
- Test: `tests/test_state_abyss.py`

**Interfaces:**
- Consumes: existing `Agent`, `Resource`, `WorldState`, `Needs`.
- Produces: `Agent` fields `layer:int`, `strain:float`, `mana:float`, `mana_max:float`, `attr_rank:dict[str,int]`, `attr_xp:dict[str,float]`, `purified_until:int`, `negate_fall_until:int`; `status` may be `"dead"`. `Resource.layer:int`, `Structure.layer:int`. Serialization round-trips all new fields and still loads pre-Plan-3 JSON.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state_abyss.py
import json
from genesis.world.state import Agent, Resource, WorldState


def test_new_agent_fields_default():
    a = Agent(id="a1", name="Riko", x=0, y=0)
    assert a.layer == 0 and a.strain == 0.0
    assert a.mana == 0.0 and a.mana_max == 0.0
    assert a.attr_rank == {} and a.attr_xp == {}
    assert a.purified_until == 0 and a.negate_fall_until == 0


def test_resource_layer_defaults_zero():
    r = Resource(type="berries", x=1, y=2, qty=3)
    assert r.layer == 0


def test_roundtrip_preserves_abyss_fields():
    a = Agent(id="a1", name="Riko", x=0, y=0, layer=2, strain=12.5,
              mana=30.0, mana_max=50.0, attr_rank={"healing": 1},
              attr_xp={"healing": 25.0}, status="dead")
    ws = WorldState(sim_minutes=0, seed=1, agents=[a],
                    resources=[Resource("relic", 3, 3, 1, layer=2)])
    back = WorldState.from_json(ws.to_json())
    b = back.agents[0]
    assert b.layer == 2 and b.strain == 12.5 and b.status == "dead"
    assert b.attr_rank == {"healing": 1} and b.mana_max == 50.0
    assert back.resources[0].layer == 2


def test_from_json_loads_pre_plan3_agent():
    # Old JSON with no abyss/magic keys must still load.
    old = json.dumps({"sim_minutes": 0, "seed": 1,
                      "agents": [{"id": "a1", "name": "R", "x": 0, "y": 0,
                                  "needs": {"hunger": 100.0, "energy": 100.0,
                                            "warmth": 100.0}, "inventory": {},
                                  "status": "active", "persona": "", "brain": "",
                                  "knowledge": [], "current_action": None,
                                  "collapse_until": 0}],
                      "resources": [{"type": "berries", "x": 1, "y": 1, "qty": 2}],
                      "structures": []})
    ws = WorldState.from_json(old)
    assert ws.agents[0].layer == 0 and ws.agents[0].mana_max == 0.0
    assert ws.resources[0].layer == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state_abyss.py -v`
Expected: FAIL (`TypeError`/`AttributeError` — new fields/params not defined).

- [ ] **Step 3: Add the fields**

In `src/genesis/world/state.py`, extend the dataclasses (keep existing fields; add these with defaults so old JSON loads):

```python
@dataclass
class Agent:
    id: str
    name: str
    x: int
    y: int
    needs: Needs = field(default_factory=Needs)
    inventory: dict[str, int] = field(default_factory=dict)
    status: str = "active"  # active | sleeping | collapsed | dead
    persona: str = ""
    brain: str = ""
    knowledge: list[str] = field(default_factory=list)
    current_action: dict | None = None
    collapse_until: int = 0
    # Plan 3 — Abyss & magic
    layer: int = 0
    strain: float = 0.0
    mana: float = 0.0
    mana_max: float = 0.0
    attr_rank: dict[str, int] = field(default_factory=dict)
    attr_xp: dict[str, float] = field(default_factory=dict)
    purified_until: int = 0
    negate_fall_until: int = 0
```

Add `layer: int = 0` to `Resource`. In `structures.py` (Task uses it) add `layer: int = 0` to `Structure` — do it here too so serialization matches:

```python
@dataclass
class Resource:
    type: str
    x: int
    y: int
    qty: int
    layer: int = 0
```

Update `WorldState.from_json` for backward-compatible loading:

```python
@classmethod
def from_json(cls, s: str) -> "WorldState":
    from genesis.world.structures import Structure
    d = json.loads(s)
    agents = [Agent(**{**a, "needs": Needs(**a["needs"])}) for a in d["agents"]]
    resources = [Resource(**r) for r in d["resources"]]
    structures = [Structure(**s) for s in d.get("structures", [])]
    return cls(sim_minutes=d["sim_minutes"], seed=d["seed"],
               agents=agents, resources=resources, structures=structures)
```

(`Agent(**a)` / `Resource(**r)` already tolerate missing keys because every new field has a default; no code change needed beyond the field additions. Keep `**a` spreads intact.)

Also add `layer: int = 0` to `Structure` in `src/genesis/world/structures.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_state_abyss.py -v`
Expected: PASS. Also run `uv run pytest -q` — all prior 67 tests still pass (fields are additive).

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/state.py src/genesis/world/structures.py tests/test_state_abyss.py
git commit -m "Add Abyss and magic fields to Agent/Resource/Structure state"
```

---

### Task 2: Engine holds multiple layer maps

**Files:**
- Modify: `src/genesis/world/engine.py`
- Test: `tests/test_state_abyss.py` (add cases) or new `tests/test_engine_layers.py`

**Interfaces:**
- Consumes: `WorldMap`, `WorldState`, Task 1 `Agent.layer`.
- Produces: `Engine(state, world_map=None, settings, graph=None, maps=None, layers=None, magic=None)`. `Engine.map_for(agent) -> WorldMap` returns `self.maps[agent.layer]`. A single `world_map` is wrapped as `maps=[world_map]`. `step_action`/`tick_needs`/`choose_action` receive `self.map_for(agent)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine_layers.py
from genesis.world.engine import Engine
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState

M0 = WorldMap(["GG", "GG"])
M1 = WorldMap(["RR", "RR"])
SET = {"minutes_per_day": 100, "day_start_minute": 0, "day_end_minute": 100,
       "hunger_decay_per_min": 0.0, "energy_decay_per_min": 0.0,
       "energy_regen_sleeping_per_min": 0.0, "warmth_decay_night_per_min": 0.0,
       "warmth_decay_night_sleeping_per_min": 0.0, "warmth_regen_day_per_min": 0.0,
       "warmth_regen_near_fire_per_min": 0.0, "campfire_warmth_radius": 1,
       "collapse_duration_min": 1, "collapse_recover_need_value": 50.0,
       "collapse_recover_energy_value": 50.0, "wake_energy_threshold": 80.0,
       "morning_wake_min_energy": 50.0, "strain_decay_per_min": 0.0,
       "strain_lethal_threshold": 60.0}


def test_map_for_returns_agents_layer():
    a0 = Agent(id="a0", name="A", x=0, y=0, layer=0)
    a1 = Agent(id="a1", name="B", x=0, y=0, layer=1)
    ws = WorldState(sim_minutes=0, seed=1, agents=[a0, a1])
    eng = Engine(ws, settings=SET, maps=[M0, M1])
    assert eng.map_for(a0).terrain(0, 0) == "grass"
    assert eng.map_for(a1).terrain(0, 0) == "rock"


def test_single_world_map_still_supported():
    ws = WorldState(sim_minutes=0, seed=1,
                    agents=[Agent(id="a", name="A", x=0, y=0)])
    eng = Engine(ws, world_map=M0, settings=SET)
    assert eng.maps == [M0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_engine_layers.py -v`
Expected: FAIL (`Engine` has no `maps`/`map_for`).

- [ ] **Step 3: Update the Engine constructor and tick**

```python
class Engine:
    def __init__(self, state, world_map=None, settings=None, graph=None,
                 maps=None, layers=None, magic=None):
        self.state = state
        if maps is None:
            maps = [world_map] if world_map is not None else []
        self.maps = maps
        self.settings = settings
        self.rng = random.Random(state.seed)
        self.graph = graph or DiscoveryGraph.from_file("configs/discoveries.json")
        self.layers = layers or []
        self.magic = magic

    def map_for(self, agent):
        return self.maps[agent.layer]

    def tick(self):
        events = []
        minute = self.state.sim_minutes
        for agent in self.state.agents:
            if agent.status == "dead":
                continue
            wm = self.map_for(agent)
            near = has_warmth_source(agent, self.state, self.settings)
            events += tick_needs(agent, minute, self.settings, near_warmth=near)
            if agent.current_action is None and agent.status in ("active", "sleeping"):
                agent.current_action = choose_action(
                    agent, self.state, wm, self.settings, self.rng,
                    self.graph, self.magic)
            events += step_action(agent, self.state, wm, self.settings,
                                  self.graph, self.magic)
        for ev in events:
            ev.setdefault("minute", minute)
        self.state.sim_minutes += 1
        return events
```

(`choose_action` and `step_action` gain the trailing `magic` arg in later tasks; add `magic=None` params to their signatures now so this call is valid — a one-line signature change in `instinct.py` and `actions.py`, no behaviour change yet.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_engine_layers.py -v` then `uv run pytest -q`
Expected: PASS; all prior tests still green.

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/engine.py src/genesis/world/instinct.py src/genesis/world/actions.py tests/test_engine_layers.py
git commit -m "Engine holds per-layer maps and resolves map per agent"
```

---

### Task 3: Typed effect records — effect dispatch table

**Files:**
- Create: `src/genesis/world/effects.py`
- Test: `tests/test_effects.py`

**Interfaces:**
- Consumes: Task 1 `Agent` fields.
- Produces: `apply_effect(effect: dict, agent, state, world_map, settings, minute) -> list[dict]`. Handlers by `effect["type"]`: `reduce_strain`, `warmth`, `clear_miasma`, `negate_fall`, `build_shelter`, `attack`. Unknown type → `[{"type": "effect_noop", ...}]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_effects.py
from genesis.world.effects import apply_effect
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GG", "GG"])
SET = {"campfire_warmth_radius": 1}


def _agent(**kw):
    return Agent(id="a", name="A", x=0, y=0, **kw)


def test_reduce_strain_lowers_strain_and_gives_bonus_energy():
    a = _agent(strain=30.0)
    a.needs.energy = 40.0
    apply_effect({"type": "reduce_strain", "amount": 20, "bonus": {"energy": 10}},
                 a, WorldState(0, 1, [a]), WM, SET, minute=5)
    assert a.strain == 10.0 and a.needs.energy == 50.0


def test_reduce_strain_clamps_at_zero():
    a = _agent(strain=5.0)
    apply_effect({"type": "reduce_strain", "amount": 20}, a,
                 WorldState(0, 1, [a]), WM, SET, minute=0)
    assert a.strain == 0.0


def test_clear_miasma_sets_buff_window():
    a = _agent()
    apply_effect({"type": "clear_miasma", "duration": 30}, a,
                 WorldState(0, 1, [a]), WM, SET, minute=10)
    assert a.purified_until == 40


def test_negate_fall_sets_buff_window():
    a = _agent()
    apply_effect({"type": "negate_fall", "duration": 15}, a,
                 WorldState(0, 1, [a]), WM, SET, minute=10)
    assert a.negate_fall_until == 25


def test_unknown_effect_is_noop_event():
    a = _agent()
    evs = apply_effect({"type": "teleport"}, a, WorldState(0, 1, [a]), WM, SET, 0)
    assert evs and evs[0]["type"] == "effect_noop"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_effects.py -v`
Expected: FAIL (`effects` module missing).

- [ ] **Step 3: Implement the dispatch table**

```python
# src/genesis/world/effects.py
from genesis.world.structures import Structure


def _clamp(v):
    return max(0.0, min(100.0, v))


def _reduce_strain(effect, agent, state, wm, settings, minute):
    agent.strain = max(0.0, agent.strain - float(effect.get("amount", 0)))
    for need, amt in effect.get("bonus", {}).items():
        cur = getattr(agent.needs, need)
        setattr(agent.needs, need, _clamp(cur + float(amt)))
    return [{"type": "healed", "agent": agent.id, "strain": agent.strain}]


def _warmth(effect, agent, state, wm, settings, minute):
    agent.needs.warmth = _clamp(agent.needs.warmth + float(effect.get("amount", 0)))
    return [{"type": "warmed", "agent": agent.id}]


def _clear_miasma(effect, agent, state, wm, settings, minute):
    agent.purified_until = minute + int(effect.get("duration", 0))
    return [{"type": "purified", "agent": agent.id, "until": agent.purified_until}]


def _negate_fall(effect, agent, state, wm, settings, minute):
    agent.negate_fall_until = minute + int(effect.get("duration", 0))
    return [{"type": "wind_ready", "agent": agent.id, "until": agent.negate_fall_until}]


def _build_shelter(effect, agent, state, wm, settings, minute):
    state.structures.append(Structure(type=effect.get("structure", "stone_hut"),
                                       x=agent.x, y=agent.y, built_by=agent.id,
                                       built_minute=minute, layer=agent.layer))
    return [{"type": "shaped", "agent": agent.id, "structure": effect.get("structure")}]


def _attack(effect, agent, state, wm, settings, minute):
    # Combat resolution lives in hazards.creature_encounter; here we just flag intent.
    return [{"type": "attacked", "agent": agent.id, "power": effect.get("power", 0)}]


_HANDLERS = {
    "reduce_strain": _reduce_strain, "warmth": _warmth,
    "clear_miasma": _clear_miasma, "negate_fall": _negate_fall,
    "build_shelter": _build_shelter, "attack": _attack,
}


def apply_effect(effect, agent, state, world_map, settings, minute):
    handler = _HANDLERS.get(effect.get("type"))
    if handler is None:
        return [{"type": "effect_noop", "agent": agent.id,
                 "effect": effect.get("type")}]
    return handler(effect, agent, state, world_map, settings, minute)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_effects.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/effects.py tests/test_effects.py
git commit -m "Add typed effect-record dispatch table (effects.apply_effect)"
```

---

### Task 4: Magic model — MagicBook (ranks, xp, mana growth, cast time)

**Files:**
- Create: `src/genesis/world/magic.py`
- Test: `tests/test_magic.py`

**Interfaces:**
- Consumes: Task 1 `Agent` fields.
- Produces: `MagicBook(attributes, ranks, rank_xp, spells, params)` with `from_dict(d)`/`from_file(path)`. Methods: `spell(name) -> dict|None`; `cast_minutes(spell, agent) -> int`; `award_xp(agent, attribute) -> bool` (returns True on rank-up, mutates `attr_xp`/`attr_rank`); `note_cast_mana(agent) -> None` (grows `mana_max` if depleted below `mana_depletion_frac`). `ranks` is the ordered list e.g. `["beginner","intermediate","advanced","saint","king"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_magic.py
from genesis.world.magic import MagicBook
from genesis.world.state import Agent

BOOK = MagicBook.from_dict({
    "attributes": ["fire", "water", "wind", "earth", "healing"],
    "ranks": ["beginner", "intermediate", "advanced", "saint", "king"],
    "rank_xp": {"beginner": 0, "intermediate": 20, "advanced": 60,
                "saint": 140, "king": 300},
    "spells": [
        {"name": "minor_heal", "kind": "spell", "attribute": "healing",
         "requires": [], "prereqs": {"attribute_rank": {"healing": "beginner"}},
         "base_cast_minutes": 4, "mana_cost": 10, "xp_per_cast": 6,
         "effect": {"type": "reduce_strain", "amount": 20}},
    ],
    "params": {"mana_depletion_frac": 0.15, "mana_growth_step": 5.0},
})


def _mage(**kw):
    return Agent(id="m", name="M", x=0, y=0, **kw)


def test_spell_lookup():
    assert BOOK.spell("minor_heal")["attribute"] == "healing"
    assert BOOK.spell("nope") is None


def test_cast_minutes_shrinks_with_rank():
    beginner = _mage(attr_rank={"healing": 0})
    advanced = _mage(attr_rank={"healing": 2})
    sp = BOOK.spell("minor_heal")
    assert BOOK.cast_minutes(sp, beginner) == 4
    assert BOOK.cast_minutes(sp, advanced) == 2  # 4 - rank_index, min 1


def test_award_xp_ranks_up_at_threshold():
    a = _mage(attr_rank={"healing": 0}, attr_xp={"healing": 18.0})
    ranked = BOOK.award_xp(a, "healing", amount=6)  # 24 >= 20 -> intermediate
    assert ranked is True and a.attr_rank["healing"] == 1


def test_award_xp_no_rankup_below_threshold():
    a = _mage(attr_rank={"healing": 0}, attr_xp={"healing": 5.0})
    assert BOOK.award_xp(a, "healing", amount=6) is False
    assert a.attr_rank["healing"] == 0


def test_mana_pool_grows_when_depleted():
    a = _mage(mana=1.0, mana_max=50.0)  # 1/50 = 0.02 < 0.15
    BOOK.note_cast_mana(a)
    assert a.mana_max == 55.0


def test_mana_pool_stable_when_not_depleted():
    a = _mage(mana=40.0, mana_max=50.0)
    BOOK.note_cast_mana(a)
    assert a.mana_max == 50.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_magic.py -v`
Expected: FAIL (`magic` module missing).

- [ ] **Step 3: Implement MagicBook**

```python
# src/genesis/world/magic.py
import json
from pathlib import Path


class MagicBook:
    def __init__(self, attributes, ranks, rank_xp, spells, params):
        self.attributes = attributes
        self.ranks = ranks
        self.rank_xp = rank_xp
        self.spells = {s["name"]: s for s in spells}
        self.params = params

    @classmethod
    def from_dict(cls, d):
        return cls(d["attributes"], d["ranks"], d["rank_xp"],
                   d["spells"], d.get("params", {}))

    @classmethod
    def from_file(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def spell(self, name):
        return self.spells.get(name)

    def cast_minutes(self, spell, agent):
        rank = agent.attr_rank.get(spell["attribute"], 0)
        return max(1, int(spell["base_cast_minutes"]) - rank)

    def award_xp(self, agent, attribute, amount):
        agent.attr_xp[attribute] = agent.attr_xp.get(attribute, 0.0) + float(amount)
        rank = agent.attr_rank.get(attribute, 0)
        # rank up while the next rank's threshold is met and one exists
        while rank + 1 < len(self.ranks):
            nxt = self.ranks[rank + 1]
            if agent.attr_xp[attribute] >= self.rank_xp[nxt]:
                rank += 1
            else:
                break
        ranked_up = rank != agent.attr_rank.get(attribute, 0)
        agent.attr_rank[attribute] = rank
        return ranked_up

    def note_cast_mana(self, agent):
        frac = self.params.get("mana_depletion_frac", 0.15)
        step = self.params.get("mana_growth_step", 5.0)
        if agent.mana_max > 0 and agent.mana <= frac * agent.mana_max:
            agent.mana_max += step
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_magic.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/magic.py tests/test_magic.py
git commit -m "Add MagicBook: ranks, use-XP rank-up, mana-by-depletion, cast time"
```

---

### Task 5: The `cast` action

**Files:**
- Modify: `src/genesis/world/actions.py`
- Test: `tests/test_cast.py`

**Interfaces:**
- Consumes: Task 3 `apply_effect`, Task 4 `MagicBook`.
- Produces: `cast` verb. Action shape `{"action": "cast", "spell": <name>}`. Validation: spell known (in `agent.knowledge`), `magic` provided, `prereqs.attribute_rank` met, `mana >= mana_cost`. Execution spans `cast_minutes` (like `sleep`, it returns `[]` while chanting via a `cast_until` marker on `current_action`), then deducts mana, applies effect, awards xp, grows mana pool.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cast.py
from genesis.world.actions import step_action, validate_action
from genesis.world.grid import WorldMap
from genesis.world.magic import MagicBook
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GG", "GG"])
SET = {"campfire_warmth_radius": 1}
BOOK = MagicBook.from_dict({
    "attributes": ["healing"], "ranks": ["beginner", "intermediate"],
    "rank_xp": {"beginner": 0, "intermediate": 20},
    "spells": [{"name": "minor_heal", "kind": "spell", "attribute": "healing",
                "requires": [], "prereqs": {"attribute_rank": {"healing": "beginner"}},
                "base_cast_minutes": 2, "mana_cost": 10, "xp_per_cast": 6,
                "effect": {"type": "reduce_strain", "amount": 20}}],
    "params": {"mana_depletion_frac": 0.15, "mana_growth_step": 5.0}})


def _mage():
    return Agent(id="m", name="M", x=0, y=0, mana=30.0, mana_max=40.0,
                 strain=30.0, knowledge=["minor_heal"],
                 attr_rank={"healing": 0}, attr_xp={"healing": 0.0})


def test_cast_rejected_when_spell_unknown():
    a = _mage(); a.knowledge = []
    ok, why = validate_action({"action": "cast", "spell": "minor_heal"},
                              a, WorldState(0, 1, [a]), WM, magic=BOOK)
    assert not ok and "know" in why


def test_cast_rejected_when_insufficient_mana():
    a = _mage(); a.mana = 3.0
    ok, why = validate_action({"action": "cast", "spell": "minor_heal"},
                              a, WorldState(0, 1, [a]), WM, magic=BOOK)
    assert not ok and "mana" in why


def test_cast_completes_after_chant_and_applies_effect():
    a = _mage()
    st = WorldState(0, 1, [a])
    a.current_action = {"action": "cast", "spell": "minor_heal"}
    # First tick: chanting (2 minutes) -> no completion yet
    st.sim_minutes = 0
    ev = step_action(a, st, WM, SET, None, BOOK)
    assert a.current_action is not None  # still chanting
    # Advance to completion minute
    st.sim_minutes = 2
    ev = step_action(a, st, WM, SET, None, BOOK)
    assert a.strain == 10.0            # reduced by 20
    assert a.mana == 20.0              # 30 - 10
    assert a.attr_xp["healing"] == 6.0
    assert a.current_action is None
    assert any(e["type"] == "cast" for e in ev)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cast.py -v`
Expected: FAIL (`cast` not a known verb; `validate_action`/`step_action` lack `magic`).

- [ ] **Step 3: Implement `cast`**

Add `magic=None` to `validate_action`/`step_action` signatures (if not already from Task 2), add `"cast"` to `VERBS`, and:

```python
# in validate_action, after existing verb checks
if verb == "cast":
    if magic is None:
        return False, "no magic available"
    name = action.get("spell", "")
    if name not in agent.knowledge:
        return False, f"does not know {name}"
    spell = magic.spell(name)
    if spell is None:
        return False, f"no such spell {name}"
    for attr, rank_name in spell.get("prereqs", {}).get("attribute_rank", {}).items():
        need = magic.ranks.index(rank_name)
        if agent.attr_rank.get(attr, 0) < need:
            return False, f"{attr} rank too low"
    if agent.mana < spell["mana_cost"]:
        return False, "not enough mana"
```

```python
# in step_action, add a branch (before the final `return []`)
if verb == "cast":
    spell = magic.spell(action["spell"])
    ca = agent.current_action
    if "cast_until" not in ca:
        ca["cast_until"] = m + magic.cast_minutes(spell, agent)
        return []  # chanting
    if m < ca["cast_until"]:
        return []  # still chanting
    agent.mana -= spell["mana_cost"]
    events = apply_effect(spell["effect"], agent, state, world_map, settings, m)
    ranked = magic.award_xp(agent, spell["attribute"], spell["xp_per_cast"])
    magic.note_cast_mana(agent)
    agent.current_action = None
    events.append({"type": "cast", "agent": agent.id, "spell": spell["name"],
                   "ranked_up": ranked})
    return events
```

Add `from genesis.world.effects import apply_effect` to `actions.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cast.py -v` then `uv run pytest -q`
Expected: PASS; prior tests green.

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/actions.py tests/test_cast.py
git commit -m "Add cast action: chant timing, mana cost, effect, xp, mana growth"
```

---

### Task 6: Discovering magic (spells via experiment near mana crystals)

**Files:**
- Modify: `src/genesis/world/discovery.py`, `src/genesis/world/actions.py`
- Test: `tests/test_magic_discovery.py`

**Interfaces:**
- Consumes: Task 4 `MagicBook`, existing `experiment_with`.
- Produces: `MagicBook.discoverable(items, knowledge, attribute_seed) -> str|None` returning the name of the first not-yet-known spell whose `requires` (item names) are all held and whose seed item (e.g. `mana_shard`) is present. `experiment_with` also consults `magic` and, on a match, appends the spell to `knowledge`, initialising `attr_rank[attribute]=0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_magic_discovery.py
from genesis.world.actions import step_action
from genesis.world.grid import WorldMap
from genesis.world.magic import MagicBook
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GG", "GG"])
SET = {"campfire_warmth_radius": 1, "stone_tools_gather_bonus": 1}
BOOK = MagicBook.from_dict({
    "attributes": ["healing"], "ranks": ["beginner"], "rank_xp": {"beginner": 0},
    "spells": [{"name": "minor_heal", "kind": "spell", "attribute": "healing",
                "requires": ["mana_shard"], "prereqs": {},
                "base_cast_minutes": 2, "mana_cost": 10, "xp_per_cast": 6,
                "effect": {"type": "reduce_strain", "amount": 20}}],
    "params": {}})


def test_experiment_discovers_spell_and_inits_rank():
    a = Agent(id="m", name="M", x=0, y=0, inventory={"mana_shard": 1})
    st = WorldState(0, 1, [a])
    a.current_action = {"action": "experiment_with", "items": ["mana_shard"]}
    ev = step_action(a, st, WM, SET, graph=None, magic=BOOK)
    assert "minor_heal" in a.knowledge
    assert a.attr_rank["healing"] == 0
    assert any(e["type"] == "discovered" for e in ev)


def test_experiment_without_seed_item_finds_nothing():
    a = Agent(id="m", name="M", x=0, y=0, inventory={"wood": 1})
    st = WorldState(0, 1, [a])
    a.current_action = {"action": "experiment_with", "items": ["wood"]}
    ev = step_action(a, st, WM, SET, graph=None, magic=BOOK)
    assert "minor_heal" not in a.knowledge
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_magic_discovery.py -v`
Expected: FAIL (`discoverable` missing; `experiment_with` ignores `magic`).

- [ ] **Step 3: Implement spell discovery**

In `magic.py`:

```python
def discoverable(self, items, knowledge):
    have = set(items)
    for name, spell in self.spells.items():
        if name in knowledge:
            continue
        if all(req in have for req in spell.get("requires", [])) and spell["requires"]:
            return name
    return None
```

In `actions.py`, extend the `experiment_with` branch so it also tries magic (run the existing recipe `graph.match` first; if that yields nothing, try `magic.discoverable`):

```python
if verb == "experiment_with":
    if graph is not None:
        result = graph.match(action["items"], agent.knowledge)
    else:
        result = None
    if result is None and magic is not None:
        result = magic.discoverable(action["items"], agent.knowledge)
        if result is not None:
            agent.knowledge.append(result)
            spell = magic.spell(result)
            agent.attr_rank.setdefault(spell["attribute"], 0)
            agent.attr_xp.setdefault(spell["attribute"], 0.0)
            return _finish(agent, {"type": "discovered", "agent": agent.id,
                                   "discovery": result})
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

Note: keep the `experiment_with` validation branch tolerant of `graph is None` when `magic` is present (relax the "no discovery graph available" guard to require *either* `graph` or `magic`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_magic_discovery.py -v` then `uv run pytest -q`
Expected: PASS; prior tests green.

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/magic.py src/genesis/world/actions.py tests/test_magic_discovery.py
git commit -m "Discover spells via experiment_with near mana material"
```

---

### Task 7: `descend`/`ascend` actions and the Curse (strain)

**Files:**
- Modify: `src/genesis/world/actions.py`, `src/genesis/world/needs.py`
- Test: `tests/test_curse.py`

**Interfaces:**
- Consumes: Task 1 `Agent.layer`/`strain`, layer config (passed as `settings["layers"]` list of dicts each with `curse_strain`, `link` tiles `{"descend": [x,y], "ascend": [x,y], "entry_down": [x,y], "entry_up": [x,y]}`).
- Produces: `descend`/`ascend` verbs (link-tile gated). `ascend` adds `curse_strain` of the layer left (stacks). `tick_needs` decays `strain` by `strain_decay_per_min` each active minute.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_curse.py
from genesis.world.actions import step_action, validate_action
from genesis.world.grid import WorldMap
from genesis.world.needs import tick_needs
from genesis.world.state import Agent, WorldState

WM = WorldMap(["CC", "CC"])  # all cave tiles, walkable
LAYERS = [
    {"curse_strain": 5, "link": {"descend": [0, 0], "entry_down": [1, 1]}},
    {"curse_strain": 20, "link": {"ascend": [1, 1], "entry_up": [0, 0]}},
]
SET = {"layers": LAYERS, "strain_decay_per_min": 0.5, "minutes_per_day": 100,
       "day_start_minute": 0, "day_end_minute": 100, "hunger_decay_per_min": 0.0,
       "energy_decay_per_min": 0.0, "energy_regen_sleeping_per_min": 0.0,
       "warmth_decay_night_per_min": 0.0, "warmth_decay_night_sleeping_per_min": 0.0,
       "warmth_regen_day_per_min": 0.0, "warmth_regen_near_fire_per_min": 0.0,
       "collapse_duration_min": 1, "collapse_recover_need_value": 50.0,
       "collapse_recover_energy_value": 50.0, "strain_lethal_threshold": 60.0}


def test_descend_requires_link_tile():
    a = Agent(id="a", name="A", x=1, y=0, layer=0)  # not on descend tile
    ok, why = validate_action({"action": "descend"}, a, WorldState(0, 1, [a]),
                              WM, magic=None)
    assert not ok


def test_descend_moves_to_next_layer_no_strain():
    a = Agent(id="a", name="A", x=0, y=0, layer=0)
    st = WorldState(0, 1, [a]); a.current_action = {"action": "descend"}
    step_action(a, st, WM, SET, None, None)
    assert a.layer == 1 and (a.x, a.y) == (1, 1) and a.strain == 0.0


def test_ascend_adds_curse_strain_of_layer_left():
    a = Agent(id="a", name="A", x=1, y=1, layer=1)
    st = WorldState(0, 1, [a]); a.current_action = {"action": "ascend"}
    step_action(a, st, WM, SET, None, None)
    assert a.layer == 0 and (a.x, a.y) == (0, 0) and a.strain == 20.0


def test_strain_decays_each_minute():
    a = Agent(id="a", name="A", x=0, y=0, strain=10.0)
    tick_needs(a, 0, SET)
    assert a.strain == 9.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_curse.py -v`
Expected: FAIL (verbs unknown; no strain decay).

- [ ] **Step 3: Implement descend/ascend + strain decay**

Add `"descend"`, `"ascend"` to `VERBS`. Validation:

```python
if verb in ("descend", "ascend"):
    layers = settings.get("layers", []) if settings else []
    if not layers:
        return False, "no layers configured"
    link = layers[agent.layer].get("link", {})
    tile = link.get(verb)
    if tile is None or [agent.x, agent.y] != tile:
        return False, f"not on a {verb} tile"
    if verb == "descend" and agent.layer + 1 >= len(layers):
        return False, "no deeper layer"
    if verb == "ascend" and agent.layer == 0:
        return False, "already at the top"
```

Step logic:

```python
if verb == "descend":
    layers = settings["layers"]
    agent.layer += 1
    ex, ey = layers[agent.layer]["link"]["entry_down"]
    agent.x, agent.y = ex, ey
    return _finish(agent, {"type": "descended", "agent": agent.id,
                           "layer": agent.layer})

if verb == "ascend":
    layers = settings["layers"]
    left = agent.layer
    agent.layer -= 1
    ex, ey = layers[agent.layer]["link"]["entry_up"]
    agent.x, agent.y = ex, ey
    agent.strain += layers[left]["curse_strain"]
    return _finish(agent, {"type": "ascended", "agent": agent.id,
                           "layer": agent.layer, "strain": agent.strain,
                           "curse_from": left})
```

In `needs.py` `tick_needs`, after the collapse-guard early return and before the day/night block (i.e. for active/sleeping agents), decay strain:

```python
if agent.strain > 0:
    agent.strain = max(0.0, agent.strain - settings.get("strain_decay_per_min", 0.0))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_curse.py -v` then `uv run pytest -q`
Expected: PASS; prior tests green.

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/actions.py src/genesis/world/needs.py tests/test_curse.py
git commit -m "Add descend/ascend actions and Curse strain (gain on ascent, slow decay)"
```

---

### Task 8: Curse-only permadeath

**Files:**
- Modify: `src/genesis/world/needs.py`
- Test: `tests/test_death.py`

**Interfaces:**
- Consumes: Task 1 `status="dead"`, Task 7 strain, `settings["strain_lethal_threshold"]`.
- Produces: in `tick_needs`, when a need hits 0 the agent becomes `"dead"` (with a `died` event) **iff** `strain >= strain_lethal_threshold`; otherwise it becomes `"collapsed"` exactly as before.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_death.py
from genesis.world.needs import tick_needs
from genesis.world.state import Agent

BASE = {"minutes_per_day": 100, "day_start_minute": 0, "day_end_minute": 100,
        "hunger_decay_per_min": 100.0, "energy_decay_per_min": 0.0,
        "energy_regen_sleeping_per_min": 0.0, "warmth_decay_night_per_min": 0.0,
        "warmth_decay_night_sleeping_per_min": 0.0, "warmth_regen_day_per_min": 0.0,
        "warmth_regen_near_fire_per_min": 0.0, "collapse_duration_min": 5,
        "collapse_recover_need_value": 50.0, "collapse_recover_energy_value": 50.0,
        "strain_decay_per_min": 0.0, "strain_lethal_threshold": 60.0}


def test_collapse_recovers_when_strain_low():
    a = Agent(id="a", name="A", x=0, y=0, strain=10.0)  # below lethal
    evs = tick_needs(a, 0, BASE)  # hunger crashes to 0
    assert a.status == "collapsed"
    assert any(e["type"] == "collapsed" for e in evs)


def test_dies_when_collapsing_with_high_strain():
    a = Agent(id="a", name="A", x=0, y=0, strain=70.0)  # above lethal
    evs = tick_needs(a, 0, BASE)
    assert a.status == "dead"
    assert any(e["type"] == "died" for e in evs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_death.py -v`
Expected: FAIL (`test_dies...` — currently always collapses).

- [ ] **Step 3: Implement curse-only death**

In `tick_needs`, replace the collapse block:

```python
if min(n.hunger, n.energy, n.warmth) <= 0:
    if agent.strain >= settings.get("strain_lethal_threshold", float("inf")):
        agent.status = "dead"
        agent.current_action = None
        events.append({"type": "died", "agent": agent.id, "minute": sim_minutes,
                       "cause": "curse"})
    else:
        agent.status = "collapsed"
        agent.collapse_until = sim_minutes + settings["collapse_duration_min"]
        agent.current_action = None
        events.append({"type": "collapsed", "agent": agent.id,
                       "minute": sim_minutes})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_death.py -v` then `uv run pytest -q`
Expected: PASS; prior tests green.

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/needs.py tests/test_death.py
git commit -m "Add curse-only permadeath (collapse with lethal strain = dead)"
```

---

### Task 9: Curse side-effects — numbness & hallucination bands

**Files:**
- Create: `src/genesis/world/abyss.py`
- Modify: `src/genesis/world/actions.py`
- Test: `tests/test_curse_bands.py`

**Interfaces:**
- Consumes: Task 7 strain, seeded rng.
- Produces: `abyss.action_fails(agent, layer_cfg, rng) -> bool` — returns True when `strain` is in the layer's `curse_band` and `rng.random() < curse_fail_chance`. `step_action` consults it at the top (needs `rng`); on failure it emits `action_fail` and clears the action. To keep `step_action` deterministic and its signature stable, pass `rng` via `settings["_rng"]` set by the Engine each tick, or add an optional `rng=None` param. **Chosen:** add `rng=None` to `step_action`; Engine passes `self.rng`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_curse_bands.py
import random
from genesis.world.abyss import action_fails


def test_action_fails_inside_band_when_roll_low():
    cfg = {"curse_band": [20, 50], "curse_fail_chance": 1.0}

    class A:  # minimal stand-in
        strain = 30.0
    assert action_fails(A(), cfg, random.Random(0)) is True


def test_action_ok_outside_band():
    cfg = {"curse_band": [20, 50], "curse_fail_chance": 1.0}

    class A:
        strain = 10.0
    assert action_fails(A(), cfg, random.Random(0)) is False


def test_action_ok_when_roll_high():
    cfg = {"curse_band": [20, 50], "curse_fail_chance": 0.0}

    class A:
        strain = 30.0
    assert action_fails(A(), cfg, random.Random(0)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_curse_bands.py -v`
Expected: FAIL (`abyss` module missing).

- [ ] **Step 3: Implement the band check and wire it in**

```python
# src/genesis/world/abyss.py
def action_fails(agent, layer_cfg, rng):
    band = layer_cfg.get("curse_band")
    if not band:
        return False
    lo, hi = band
    if lo <= agent.strain < hi:
        return rng.random() < layer_cfg.get("curse_fail_chance", 0.0)
    return False
```

In `actions.py` `step_action`, add `rng=None` param and, right after resolving `action`/`verb` but before executing (skip for the passive `observe` and for completing an in-progress `cast`/`sleep`), consult it:

```python
if rng is not None and verb in ("move_to", "gather", "experiment_with", "build",
                                "descend", "ascend", "harvest_relic"):
    layers = settings.get("layers", []) if settings else []
    if layers and 0 <= agent.layer < len(layers):
        if action_fails(agent, layers[agent.layer], rng):
            return _finish(agent, {"type": "action_fail", "agent": agent.id,
                                   "cause": "curse"})
```

Add `from genesis.world.abyss import action_fails` to `actions.py`, and pass `self.rng` from the Engine's `step_action` call (update the call to `step_action(agent, self.state, wm, self.settings, self.graph, self.magic, self.rng)`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_curse_bands.py -v` then `uv run pytest -q`
Expected: PASS; prior tests green.

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/abyss.py src/genesis/world/actions.py src/genesis/world/engine.py tests/test_curse_bands.py
git commit -m "Add curse side-effect bands (numbness/hallucination action failure)"
```

---

### Task 10: Hazards — miasma, fall, and creature encounters

**Files:**
- Create: `src/genesis/world/hazards.py`
- Modify: `src/genesis/world/engine.py` (miasma tick), `src/genesis/world/actions.py` (fall on cliff)
- Test: `tests/test_hazards.py`

**Interfaces:**
- Consumes: Task 1 buffs (`purified_until`, `negate_fall_until`), Task 7 strain, seeded rng.
- Produces: `hazards.miasma_tick(agent, layer_cfg, minute) -> list[dict]` (damages a need unless purified); `hazards.fall_check(agent, world_map, layer_cfg, minute, rng) -> list[dict]` (on a `cliff` tile without an active `negate_fall` buff → strain + energy crash); `hazards.creature_damage(agent, layer_cfg) -> list[dict]` (flat need damage on hazard-tagged layers unless the agent has a counter — kept minimal). Engine calls `miasma_tick` and `creature_damage` per active agent each tick; `fall_check` runs after a successful `move_to`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hazards.py
import random
from genesis.world.grid import WorldMap
from genesis.world.hazards import miasma_tick, fall_check
from genesis.world.state import Agent

L1 = {"miasma_damage": 5.0, "miasma_need": "energy"}
L2 = {"cliff_tiles": [[1, 0]], "fall_strain": 40.0}
WM = WorldMap(["GG", "GG"])


def test_miasma_damages_when_not_purified():
    a = Agent(id="a", name="A", x=0, y=0, purified_until=0)
    a.needs.energy = 50.0
    miasma_tick(a, L1, minute=10)
    assert a.needs.energy == 45.0


def test_miasma_blocked_by_purify_buff():
    a = Agent(id="a", name="A", x=0, y=0, purified_until=20)
    a.needs.energy = 50.0
    miasma_tick(a, L1, minute=10)  # 10 < 20 -> purified
    assert a.needs.energy == 50.0


def test_fall_on_cliff_without_wind_adds_strain():
    a = Agent(id="a", name="A", x=1, y=0, negate_fall_until=0)
    evs = fall_check(a, WM, L2, minute=5, rng=random.Random(0))
    assert a.strain == 40.0 and any(e["type"] == "fell" for e in evs)


def test_fall_prevented_by_wind_buff():
    a = Agent(id="a", name="A", x=1, y=0, negate_fall_until=10)
    evs = fall_check(a, WM, L2, minute=5, rng=random.Random(0))
    assert a.strain == 0.0 and evs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_hazards.py -v`
Expected: FAIL (`hazards` module missing).

- [ ] **Step 3: Implement hazards and wire into engine/actions**

```python
# src/genesis/world/hazards.py
def _clamp(v):
    return max(0.0, min(100.0, v))


def miasma_tick(agent, layer_cfg, minute):
    dmg = layer_cfg.get("miasma_damage", 0.0)
    if dmg <= 0 or minute < agent.purified_until:
        return []
    need = layer_cfg.get("miasma_need", "energy")
    setattr(agent.needs, need, _clamp(getattr(agent.needs, need) - dmg))
    return [{"type": "miasma", "agent": agent.id, "need": need}]


def fall_check(agent, world_map, layer_cfg, minute, rng):
    cliffs = layer_cfg.get("cliff_tiles", [])
    if [agent.x, agent.y] not in cliffs or minute < agent.negate_fall_until:
        return []
    agent.strain += layer_cfg.get("fall_strain", 0.0)
    agent.needs.energy = 0.0  # a fall crashes energy → may trigger curse death
    return [{"type": "fell", "agent": agent.id, "strain": agent.strain}]


def creature_damage(agent, layer_cfg):
    dmg = layer_cfg.get("creature_damage", 0.0)
    if dmg <= 0:
        return []
    agent.needs.energy = _clamp(agent.needs.energy - dmg)
    return [{"type": "creature_attack", "agent": agent.id}]
```

In `engine.py` `tick`, after `tick_needs` for each active agent, add per-layer hazards:

```python
if self.layers and 0 <= agent.layer < len(self.layers):
    lc = self.layers[agent.layer]
    events += miasma_tick(agent, lc, minute)
    events += creature_damage(agent, lc)
```

In `actions.py`, after a `move_to` that changes position, call `fall_check` (guard `rng`/`layers` present) and append its events. (Simplest: after setting `agent.x, agent.y = step`, if `rng` and layers, `events += fall_check(agent, world_map, layers[agent.layer], m, rng)` before returning.)

Import the three helpers where used.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_hazards.py -v` then `uv run pytest -q`
Expected: PASS; prior tests green.

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/hazards.py src/genesis/world/engine.py src/genesis/world/actions.py tests/test_hazards.py
git commit -m "Add layer hazards: miasma poison, cliff falls, creature damage"
```

---

### Task 11: Relics — `harvest_relic` and value/payload

**Files:**
- Modify: `src/genesis/world/actions.py`
- Test: `tests/test_relics.py`

**Interfaces:**
- Consumes: Task 1 `Resource.layer`, `Agent.mana_max`.
- Produces: `harvest_relic` verb. A `relic` is a `Resource` of `type="relic"` on the agent's layer/tile carrying a payload encoded in a parallel `state`-level lookup — to avoid schema churn, relics are `Resource`s with `type` starting `relic:` and an optional payload map in `settings["relics"]` keyed by the full type (e.g. `{"relic:artifact": {"value": 50, "mana_max": 10}}`). Harvest removes the relic, adds `value` to `agent.inventory["relic_value"]`, and applies `mana_max` bonus.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_relics.py
from genesis.world.actions import step_action
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, Resource, WorldState

WM = WorldMap(["GG", "GG"])
SET = {"campfire_warmth_radius": 1,
       "relics": {"relic:artifact": {"value": 50, "mana_max": 10}}}


def test_harvest_relic_adds_value_and_mana_max():
    a = Agent(id="a", name="A", x=0, y=0, layer=1, mana_max=40.0)
    r = Resource(type="relic:artifact", x=0, y=0, qty=1, layer=1)
    st = WorldState(0, 1, [a], resources=[r])
    a.current_action = {"action": "harvest_relic"}
    ev = step_action(a, st, WM, SET, None, None)
    assert a.inventory.get("relic_value") == 50
    assert a.mana_max == 50.0
    assert r.qty == 0 and any(e["type"] == "relic_taken" for e in ev)


def test_harvest_relic_fails_when_none_here():
    a = Agent(id="a", name="A", x=0, y=0, layer=1)
    st = WorldState(0, 1, [a], resources=[])
    a.current_action = {"action": "harvest_relic"}
    ev = step_action(a, st, WM, SET, None, None)
    assert any(e["type"] == "harvest_failed" for e in ev)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_relics.py -v`
Expected: FAIL (`harvest_relic` unknown).

- [ ] **Step 3: Implement `harvest_relic`**

Add `"harvest_relic"` to `VERBS`, then:

```python
if verb == "harvest_relic":
    tiles = _tiles_near(agent, world_map)
    relic = next((r for r in state.resources
                  if r.type.startswith("relic") and r.qty > 0
                  and r.layer == agent.layer and (r.x, r.y) in tiles), None)
    if relic is None:
        return _finish(agent, {"type": "harvest_failed", "agent": agent.id,
                               "reason": "no relic here"})
    payload = (settings or {}).get("relics", {}).get(relic.type, {})
    relic.qty -= 1
    agent.inventory["relic_value"] = (agent.inventory.get("relic_value", 0)
                                      + int(payload.get("value", 0)))
    if payload.get("mana_max"):
        agent.mana_max += float(payload["mana_max"])
    return _finish(agent, {"type": "relic_taken", "agent": agent.id,
                           "relic": relic.type,
                           "value": payload.get("value", 0)})
```

Also ensure the existing per-layer resource filtering (`_find_resource`) respects `r.layer == agent.layer` — update `_find_resource` and `_nearest_resource` to filter by layer.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_relics.py -v` then `uv run pytest -q`
Expected: PASS; prior tests green.

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/actions.py tests/test_relics.py
git commit -m "Add harvest_relic action with value + mana_max payload"
```

---

### Task 12: Instinct policy — the Abyss/magic ladder

**Files:**
- Modify: `src/genesis/world/instinct.py`
- Test: `tests/test_instinct_abyss.py`

**Interfaces:**
- Consumes: all prior tasks; `choose_action(..., graph=None, magic=None)`.
- Produces: extended `choose_action` priority ladder: (1) survive — if `strain` high and Healing known/affordable → `cast` heal; if a need critical → existing eat/sleep; in miasma without purify buff and `purify` known → cast purify; (2) descend — on a `descend` tile, if current-layer food is scarce and the next layer's magic gate is met → `descend`; (3) harvest — relic in reach → `harvest_relic`; (4) train — cast a known spell to grind xp/deplete mana; else existing Plan-2 curiosity.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_instinct_abyss.py
from genesis.world.grid import WorldMap
from genesis.world.instinct import choose_action
from genesis.world.magic import MagicBook
from genesis.world.state import Agent, Resource, WorldState
import random

WM = WorldMap(["CC", "CC"])
BOOK = MagicBook.from_dict({
    "attributes": ["healing"], "ranks": ["beginner"], "rank_xp": {"beginner": 0},
    "spells": [{"name": "minor_heal", "kind": "spell", "attribute": "healing",
                "requires": ["mana_shard"], "prereqs": {}, "base_cast_minutes": 2,
                "mana_cost": 10, "xp_per_cast": 6,
                "effect": {"type": "reduce_strain", "amount": 20}}],
    "params": {}})
SET = {"minutes_per_day": 100, "day_start_minute": 0, "day_end_minute": 100,
       "campfire_warmth_radius": 1, "strain_heal_threshold": 25.0,
       "layers": [{}, {}]}


def test_high_strain_triggers_heal_when_able():
    a = Agent(id="a", name="A", x=0, y=0, strain=40.0, mana=20.0, mana_max=40.0,
              knowledge=["minor_heal"], attr_rank={"healing": 0})
    a.needs.hunger = 100.0; a.needs.energy = 100.0
    act = choose_action(a, WorldState(0, 1, [a]), WM, SET, random.Random(0),
                        None, BOOK)
    assert act == {"action": "cast", "spell": "minor_heal"}


def test_low_strain_does_not_heal():
    a = Agent(id="a", name="A", x=0, y=0, strain=5.0, mana=20.0, mana_max=40.0,
              knowledge=["minor_heal"], attr_rank={"healing": 0})
    a.needs.hunger = 100.0; a.needs.energy = 100.0
    act = choose_action(a, WorldState(0, 1, [a]), WM, SET, random.Random(0),
                        None, BOOK)
    assert act != {"action": "cast", "spell": "minor_heal"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_instinct_abyss.py -v`
Expected: FAIL (`choose_action` lacks `magic` handling / heal branch).

- [ ] **Step 3: Implement the ladder**

Add `magic=None` to `choose_action`. Insert a survive-by-magic check high in the function (after the `status != "active"` guard, before/around the hunger logic):

```python
# --- Abyss survival: heal off dangerous strain ---
if magic is not None and agent.strain >= settings.get("strain_heal_threshold", 1e9):
    for name in agent.knowledge:
        spell = magic.spell(name)
        if (spell and spell["effect"]["type"] == "reduce_strain"
                and agent.mana >= spell["mana_cost"]):
            return {"action": "cast", "spell": name}
```

(Keep the remaining descend/harvest/train branches minimal; the two tests above only assert the heal branch. Add descend/harvest/train opportunistically after the Plan-2 curiosity block, gated on `magic`/layer config, but they are not required to pass this task's tests — do not add untested speculative logic beyond simple, obviously-correct guards.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_instinct_abyss.py -v` then `uv run pytest -q`
Expected: PASS; prior tests green.

- [ ] **Step 5: Commit**

```bash
git add src/genesis/world/instinct.py tests/test_instinct_abyss.py
git commit -m "Instinct: heal off dangerous strain (Abyss survival ladder)"
```

---

### Task 13: Content configs + Engine/CLI integration

**Files:**
- Create: `configs/layers.json`, `configs/magic.json`, `configs/maps/layer0.json`, `configs/maps/layer1.json`, `configs/maps/layer2.json`
- Modify: `configs/settings.json`, `configs/agents.json`, `src/genesis/world/engine.py`, `src/genesis/cli.py`
- Test: `tests/test_cli.py` (extend)

**Interfaces:**
- Consumes: everything above.
- Produces: a runnable 3-layer world. `Engine.from_configs(config_dir)` (or CLI wiring) loads `maps` from `layers[i].map`, `layers` from `layers.json`, `magic` from `magic.json`, merges `layers.json` into `settings["layers"]` and relic payloads into `settings["relics"]`. CLI prints per-agent `layer`, `strain`, `mana/mana_max`, top attribute rank, and a death tally.

- [ ] **Step 1: Write the config content**

`configs/magic.json` — five attributes, ranks to King, the survival-verb spells (each a typed effect record with `attribute`, `requires`, `prereqs`, `base_cast_minutes`, `mana_cost`, `xp_per_cast`, `effect`), and `params` (`mana_depletion_frac`, `mana_growth_step`). Include at least: `minor_heal` (healing/reduce_strain), `purify` (water/clear_miasma), `kindle` (fire/warmth+attack), `stone_shape` (earth/build_shelter), `updraft` (wind/negate_fall). Seed items via `requires: ["mana_shard"]` for the first spell.

`configs/layers.json` — array of 3 layers, each with `name`, `depth_m`, `map` (path), `curse_strain`, `curse_band` + `curse_fail_chance`, hazard fields (`miasma_damage`/`miasma_need` on L1; `cliff_tiles`/`fall_strain` on L2; optional `creature_damage`), `link` tiles (`descend`/`ascend`/`entry_down`/`entry_up`), and a `relics` list placed as `relic:*` resources. Recommended starting values: `curse_strain` = [5, 20, 45]; `strain_lethal_threshold` = 60.

`configs/maps/layer{0,1,2}.json` — three small `{"rows": [...]}` maps using the existing `TERRAIN` letters, each with a cave `C` link tile positioned to match `layers.json`.

`configs/settings.json` — add: `strain_decay_per_min` (0.5), `strain_lethal_threshold` (60.0), `strain_heal_threshold` (25.0), `mana_depletion_frac` (0.15), `mana_growth_step` (5.0), plus any per-layer defaults not carried in `layers.json`.

`configs/agents.json` — give starting agents empty `attr_rank`/`attr_xp` and a small `mana_max` (e.g. 20) so casting is possible once a spell is discovered; seed a `mana_shard` or place `mana_crystal` resources on L0.

- [ ] **Step 2: Wire the Engine + CLI (write a smoke test first)**

```python
# tests/test_cli.py (add)
def test_engine_loads_three_layer_world(tmp_path=None):
    from genesis.world.engine import Engine
    from genesis.world.grid import WorldMap
    import json, pathlib
    layers = json.loads(pathlib.Path("configs/layers.json").read_text())
    assert len(layers["layers"]) == 3
    maps = [WorldMap.from_file(l["map"]) for l in layers["layers"]]
    assert len(maps) == 3
```

Then implement `Engine.from_configs(config_dir="configs")` that builds `state`, `maps`, `layers`, `magic`, folds `layers` and relic payloads into `settings`, and returns an `Engine`. Update `cli.py` to use it and to print `layer/strain/mana/rank/deaths` in the summary. Run a short sim to confirm no crash:

Run: `uv run python -m genesis.cli --days 1 --db world.db`
Expected: completes; summary shows layer/strain/mana columns.

- [ ] **Step 3: Run tests to verify**

Run: `uv run pytest -q`
Expected: PASS (all suites, including the extended CLI smoke test).

- [ ] **Step 4: Commit**

```bash
git add configs src/genesis/world/engine.py src/genesis/cli.py tests/test_cli.py
git commit -m "Add 3-layer Abyss + magic configs and wire Engine.from_configs + CLI"
```

---

### Task 14: Integration — successful dive vs. death spiral

**Files:**
- Test: `tests/test_integration_dive.py`

**Interfaces:**
- Consumes: the whole engine.
- Produces: two seeded, deterministic scenario tests asserting on the event log — no new production code (if a test reveals a wiring gap, fix the relevant module and note it in the commit).

- [ ] **Step 1: Write the scenario tests**

```python
# tests/test_integration_dive.py
from genesis.world.engine import Engine
from genesis.world.grid import WorldMap
from genesis.world.magic import MagicBook
from genesis.world.state import Agent, Resource, WorldState


def _book():
    return MagicBook.from_dict({
        "attributes": ["healing"], "ranks": ["beginner", "intermediate"],
        "rank_xp": {"beginner": 0, "intermediate": 20},
        "spells": [{"name": "minor_heal", "kind": "spell", "attribute": "healing",
                    "requires": ["mana_shard"], "prereqs": {}, "base_cast_minutes": 1,
                    "mana_cost": 5, "xp_per_cast": 6,
                    "effect": {"type": "reduce_strain", "amount": 40}}],
        "params": {"mana_depletion_frac": 0.15, "mana_growth_step": 5.0}})


BASE = {"minutes_per_day": 1000, "day_start_minute": 0, "day_end_minute": 1000,
        "hunger_decay_per_min": 0.0, "energy_decay_per_min": 0.0,
        "energy_regen_sleeping_per_min": 0.0, "warmth_decay_night_per_min": 0.0,
        "warmth_decay_night_sleeping_per_min": 0.0, "warmth_regen_day_per_min": 0.0,
        "warmth_regen_near_fire_per_min": 0.0, "campfire_warmth_radius": 1,
        "collapse_duration_min": 5, "collapse_recover_need_value": 50.0,
        "collapse_recover_energy_value": 50.0, "wake_energy_threshold": 80.0,
        "morning_wake_min_energy": 50.0, "strain_decay_per_min": 0.0,
        "strain_lethal_threshold": 60.0, "strain_heal_threshold": 20.0}

MAPS = [WorldMap(["CC", "CC"]), WorldMap(["CC", "CC"]), WorldMap(["CC", "CC"])]
LAYERS = [
    {"curse_strain": 5, "link": {"descend": [0, 0], "entry_down": [1, 1]}},
    {"curse_strain": 20, "link": {"descend": [0, 0], "ascend": [1, 1],
                                  "entry_down": [1, 1], "entry_up": [0, 0]}},
    {"curse_strain": 45, "link": {"ascend": [1, 1], "entry_up": [0, 0]}},
]


def test_well_ranked_agent_survives_the_climb():
    # Scripted: an agent with a strong heal and mana returns from L2 without dying.
    a = Agent(id="hero", name="Reg", x=1, y=1, layer=2, strain=45.0,
              mana=50.0, mana_max=50.0, knowledge=["minor_heal"],
              attr_rank={"healing": 1})
    a.needs.energy = 100.0
    st = WorldState(0, 7, [a])
    settings = {**BASE, "layers": LAYERS}
    eng = Engine(st, settings=settings, maps=MAPS, layers=LAYERS, magic=_book())
    # Heal then ascend twice; assert never dead.
    a.current_action = {"action": "cast", "spell": "minor_heal"}
    eng.advance(2)
    a.current_action = {"action": "ascend"}
    eng.advance(1)
    a.current_action = {"action": "cast", "spell": "minor_heal"}
    eng.advance(2)
    a.current_action = {"action": "ascend"}
    eng.advance(1)
    assert a.status != "dead" and a.layer == 0


def test_under_ranked_agent_dies_on_the_climb():
    # No heal, energy already spent: ascending from L2 pushes strain past lethal,
    # and the next need-crash kills instead of collapsing.
    a = Agent(id="fool", name="Nanachi", x=1, y=1, layer=2, strain=20.0)
    a.needs.energy = 0.0  # will crash on next tick
    st = WorldState(0, 7, [a])
    settings = {**BASE, "layers": LAYERS, "hunger_decay_per_min": 0.0}
    eng = Engine(st, settings=settings, maps=MAPS, layers=LAYERS, magic=_book())
    a.current_action = {"action": "ascend"}     # +45 strain -> 65 >= lethal
    eng.advance(1)
    eng.advance(1)                               # need already 0 -> curse death
    assert a.status == "dead"
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_integration_dive.py -v`
Expected: PASS. If a scenario fails due to a wiring gap (e.g. strain not applied, death not triggered), fix the responsible module (Tasks 7/8 code) and re-run.

- [ ] **Step 3: Run the whole suite**

Run: `uv run pytest -q`
Expected: all tests pass (Plan 1–2's 67 + all Plan 3 tests).

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_dive.py
git commit -m "Add integration scenarios: successful dive vs. curse death spiral"
```

---

## Self-Review (completed by author)

- **Spec coverage:** §3 depth axis → Tasks 1–2, 13; §4 Curse + side-effects → Tasks 7, 9; death model → Task 8; §5 magic → Tasks 4–6; §2 typed effect records → Task 3 (+ used by 5/6/13); §6 layers/hazards → Tasks 10, 13; §7 scarcity+relics → Tasks 11, 13; §8 actions → Tasks 5, 7, 11; §9 instinct → Task 12; §11 tests → every task + Task 14; §12 `DiscoveryGraph.match` fix → fold into Task 6 (match first *unknown* record) — **noted here so it isn't missed.**
- **Placeholder scan:** every code step contains runnable code; Task 12/13 explicitly bound the "opportunistic" logic to *tested, obviously-correct* guards to avoid speculative placeholders.
- **Type consistency:** `magic` param threaded through `validate_action`/`step_action`/`choose_action` and `Engine.tick`; `MagicBook.award_xp(agent, attribute, amount)`, `cast_minutes(spell, agent)`, `note_cast_mana(agent)`, `spell(name)` used consistently across Tasks 4/5/6/12; `apply_effect(effect, agent, state, world_map, settings, minute)` signature identical in Tasks 3/5.

## Follow-on (non-blocking)

- Migrate Plan 2's hard-coded effects (`cooked_food`, `stone_tools`) into `effect` records to fully unify the schema.
- Fix `DiscoveryGraph.match()` to prefer the first *unknown* recipe (PR #2 note) — do it in Task 6 while touching discovery.
- Layers 4–7, real creature AI/positions, and the Phaser viewer are later plans.
