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
    status: str = "active"  # active | sleeping | collapsed | dead
    persona: str = ""
    brain: str = ""
    knowledge: list[str] = field(default_factory=list)
    current_action: dict | None = None
    goal: dict | None = None
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


@dataclass
class Resource:
    type: str
    x: int
    y: int
    qty: int
    layer: int = 0


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


def load_agents(path: str | Path) -> list[Agent]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Agent(**a) for a in d["agents"]]
