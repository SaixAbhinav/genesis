from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState


def _adjacent(agent, x, y, world_map):
    tiles = [(agent.x, agent.y)] + world_map.neighbors4(agent.x, agent.y)
    return (x, y) in tiles


def _move_toward(agent, x, y, world_map):
    # walk onto the target if walkable, else onto a walkable neighbor of it
    if world_map.walkable(x, y):
        return {"action": "move_to", "x": x, "y": y}
    for nx, ny in world_map.neighbors4(x, y):
        if world_map.walkable(nx, ny):
            return {"action": "move_to", "x": nx, "y": ny}
    return None


def _agent_by_name(state, name):
    return next((a for a in state.agents if a.name == name), None)


def _move_away(agent, x, y, world_map):
    dx = 0 if agent.x == x else (1 if agent.x > x else -1)
    dy = 0 if agent.y == y else (1 if agent.y > y else -1)
    for tx, ty in ((agent.x + dx, agent.y + dy),
                   (agent.x + dx, agent.y), (agent.x, agent.y + dy)):
        if (tx, ty) != (agent.x, agent.y) and world_map.walkable(tx, ty):
            return {"action": "move_to", "x": tx, "y": ty}
    return None


def resolve_goal(agent: Agent, goal: dict, state: WorldState, world_map: WorldMap,
                 settings: dict, graph=None, magic=None) -> dict | None:
    verb = goal["verb"]
    p = goal.get("params", {})

    if verb in ("gather", "harvest_relic"):
        r = next((r for r in state.resources
                  if r.type == p["resource"] and r.x == p["x"] and r.y == p["y"]
                  and r.layer == agent.layer), None)
        if r is None or r.qty <= 0:
            return None
        if _adjacent(agent, r.x, r.y, world_map):
            return {"action": verb, "resource": r.type}
        return _move_toward(agent, r.x, r.y, world_map)

    if verb == "eat":
        return {"action": "eat"} if agent.inventory.get("berries", 0) > 0 else None
    if verb in ("sleep", "observe"):
        return {"action": verb}
    if verb == "experiment_with":
        return {"action": "experiment_with", "items": p["items"]}
    if verb == "build":
        return {"action": "build", "structure": p["structure"]}
    if verb == "cast":
        return {"action": "cast", "spell": p["spell"]}
    if verb in ("descend", "ascend"):
        layers = settings.get("layers", [])
        tile = layers[agent.layer].get("link", {}).get(verb) if layers else None
        if tile is None:
            return None
        if [agent.x, agent.y] == tile:
            return {"action": verb}
        return _move_toward(agent, tile[0], tile[1], world_map)

    if verb in ("approach", "avoid"):
        radius = settings.get("perception_radius", 6)
        target = _agent_by_name(state, p["target"])
        if target is None or target.status == "dead" \
                or target.layer != agent.layer:
            return None
        if abs(target.x - agent.x) + abs(target.y - agent.y) > radius:
            return None
        if verb == "approach":
            if _adjacent(agent, target.x, target.y, world_map):
                return None
            return _move_toward(agent, target.x, target.y, world_map)
        return _move_away(agent, target.x, target.y, world_map)
    return None
