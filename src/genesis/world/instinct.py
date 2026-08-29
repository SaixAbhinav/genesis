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


def choose_action(agent: Agent, state: WorldState, world_map: WorldMap,
                  settings: dict, rng, graph=None) -> dict | None:
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
    for _ in range(10):
        tx = agent.x + rng.randint(-3, 3)
        ty = agent.y + rng.randint(-3, 3)
        if world_map.walkable(tx, ty) and (tx, ty) != (agent.x, agent.y):
            return {"action": "move_to", "x": tx, "y": ty}
    return {"action": "observe"}
