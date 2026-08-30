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

    # experiment_with: combine held items toward an undiscovered recipe result
    if graph is not None:
        held = [k for k, v in agent.inventory.items() if v > 0]
        if held:
            result = graph.match(held, agent.knowledge)
            if result is not None and result not in agent.knowledge:
                opts.append({"id": "experiment", "verb": "experiment_with",
                             "params": {"items": held},
                             "label": "experiment with what you're carrying",
                             "dir": "here", "dist": 0})

    # build: known structures whose materials are fully held
    if graph is not None:
        for s in ("campfire", "hut"):
            spec = graph.buildable(s)
            if spec is None:
                continue
            if not all(req in agent.knowledge for req in spec.get("requires", [])):
                continue
            materials = spec.get("materials", {})
            if not all(agent.inventory.get(m, 0) >= n for m, n in materials.items()):
                continue
            opts.append({"id": f"build:{s}", "verb": "build",
                         "params": {"structure": s},
                         "label": f"build a {s}", "dir": "here", "dist": 0})

    # sleep and observe are always available
    opts.append({"id": "sleep", "verb": "sleep", "params": {},
                 "label": "sleep to recover energy", "dir": "here", "dist": 0})
    opts.append({"id": "observe", "verb": "observe", "params": {},
                 "label": "watch and wait", "dir": "here", "dist": 0})
    return opts
