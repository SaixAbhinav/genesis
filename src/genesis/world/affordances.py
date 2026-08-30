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

    # gather any reachable resource on this layer (relics use harvest_relic instead)
    for r in state.resources:
        if r.qty > 0 and r.layer == agent.layer and not r.type.startswith("relic:"):
            dx, dy = r.x - agent.x, r.y - agent.y
            opts.append({
                "id": f"gather:{r.type}@({r.x},{r.y},{r.layer})",
                "verb": "gather", "params": {"resource": r.type, "x": r.x, "y": r.y},
                "label": f"gather {r.type}", "dir": _dir(dx, dy),
                "dist": abs(dx) + abs(dy)})

    # harvest_relic: relic resources on this layer
    for r in state.resources:
        if r.qty > 0 and r.layer == agent.layer and r.type.startswith("relic:"):
            dx, dy = r.x - agent.x, r.y - agent.y
            opts.append({
                "id": f"harvest_relic:{r.type}@({r.x},{r.y},{r.layer})",
                "verb": "harvest_relic", "params": {"resource": r.type, "x": r.x, "y": r.y},
                "label": f"harvest {r.type}", "dir": _dir(dx, dy),
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

    # cast: known spells the agent can currently afford and is ranked for
    if magic is not None:
        for name in agent.knowledge:
            spell = magic.spell(name)
            if spell is None or agent.mana < spell["mana_cost"]:
                continue
            reqs = spell.get("prereqs", {}).get("attribute_rank", {})
            if any(agent.attr_rank.get(attr, 0) < magic.ranks.index(rank_name)
                  for attr, rank_name in reqs.items()):
                continue
            opts.append({"id": f"cast:{name}", "verb": "cast",
                         "params": {"spell": name},
                         "label": f"cast {name}", "dir": "here", "dist": 0})

    # descend / ascend: the layer-link tile, offered even if not yet reached
    layers = settings.get("layers", []) if settings else []
    if layers and 0 <= agent.layer < len(layers):
        link = layers[agent.layer].get("link", {})
        for verb in ("descend", "ascend"):
            tile = link.get(verb)
            if tile is None:
                continue
            if verb == "descend" and agent.layer + 1 >= len(layers):
                continue
            if verb == "ascend" and agent.layer == 0:
                continue
            tx, ty = tile
            dx, dy = tx - agent.x, ty - agent.y
            opts.append({"id": verb, "verb": verb, "params": {},
                         "label": f"{verb} via the layer link",
                         "dir": _dir(dx, dy), "dist": abs(dx) + abs(dy)})

    # sleep and observe are always available
    opts.append({"id": "sleep", "verb": "sleep", "params": {},
                 "label": "sleep to recover energy", "dir": "here", "dist": 0})
    opts.append({"id": "observe", "verb": "observe", "params": {},
                 "label": "watch and wait", "dir": "here", "dist": 0})
    return opts
