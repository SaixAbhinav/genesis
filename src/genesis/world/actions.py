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
