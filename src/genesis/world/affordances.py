from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState


def _dir(dx, dy):
    ns = ("N" if dy < 0 else "S" if dy > 0 else "")
    ew = ("W" if dx < 0 else "E" if dx > 0 else "")
    return (ns + ew) or "here"


def affordances(agent: Agent, state: WorldState, world_map: WorldMap,
                settings: dict, graph=None, magic=None) -> list[dict]:
    opts: list[dict] = []

    # eat / drink from inventory
    if agent.inventory.get("berries", 0) > 0:
        opts.append({"id": "eat", "verb": "eat", "params": {},
                     "label": "eat berries you carry", "dir": "here", "dist": 0})

    # gather any reachable resource on this layer
    for r in state.resources:
        if r.qty > 0 and r.layer == agent.layer:
            dx, dy = r.x - agent.x, r.y - agent.y
            opts.append({
                "id": f"gather:{r.type}@({r.x},{r.y},{r.layer})",
                "verb": "gather", "params": {"resource": r.type, "x": r.x, "y": r.y},
                "label": f"gather {r.type}", "dir": _dir(dx, dy),
                "dist": abs(dx) + abs(dy)})

    # sleep and observe are always available
    opts.append({"id": "sleep", "verb": "sleep", "params": {},
                 "label": "sleep to recover energy", "dir": "here", "dist": 0})
    opts.append({"id": "observe", "verb": "observe", "params": {},
                 "label": "watch and wait", "dir": "here", "dist": 0})
    return opts
