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
