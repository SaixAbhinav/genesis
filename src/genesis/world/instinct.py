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
