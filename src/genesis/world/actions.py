from genesis.world.abyss import action_fails
from genesis.world.effects import apply_effect
from genesis.world.grid import WorldMap
from genesis.world.needs import is_daytime
from genesis.world.state import Agent, WorldState
from genesis.world.structures import Structure

VERBS = {"move_to", "gather", "eat", "drink", "sleep", "observe",
         "experiment_with", "build", "cast", "descend", "ascend"}


def validate_action(action: dict, agent: Agent, state: WorldState,
                    world_map: WorldMap, graph=None, magic=None, settings: dict = None) -> tuple[bool, str]:
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
    if verb == "experiment_with":
        if graph is None and magic is None:
            return False, "no discovery graph or magic available"
        items = action.get("items")
        if not isinstance(items, list) or not items:
            return False, "experiment_with needs a non-empty items list"
        for it in items:
            if agent.inventory.get(it, 0) < 1:
                return False, f"not holding {it}"
    if verb == "build":
        if graph is None:
            return False, "no discovery graph available"
        spec = graph.buildable(action.get("structure", ""))
        if spec is None:
            return False, f"cannot build '{action.get('structure')}'"
        for req in spec.get("requires", []):
            if req not in agent.knowledge:
                return False, f"needs to know {req} first"
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
                settings: dict, graph=None, magic=None, rng=None) -> list[dict]:
    action = agent.current_action
    if action is None:
        return []
    ok, why = validate_action(action, agent, state, world_map, graph, magic, settings)
    if not ok:
        return _finish(agent, {"type": "action_rejected", "agent": agent.id,
                               "reason": why})
    verb = action["action"]

    if rng is not None and verb in ("move_to", "gather", "experiment_with", "build",
                                    "descend", "ascend", "harvest_relic"):
        layers = settings.get("layers", []) if settings else []
        if layers and 0 <= agent.layer < len(layers):
            if action_fails(agent, layers[agent.layer], rng):
                return _finish(agent, {"type": "action_fail", "agent": agent.id,
                                       "cause": "curse"})

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
        yield_n = 1 + (settings["stone_tools_gather_bonus"]
                       if "stone_tools" in agent.knowledge else 0)
        yield_n = min(yield_n, r.qty)
        r.qty -= yield_n
        agent.inventory[rtype] = agent.inventory.get(rtype, 0) + yield_n
        return _finish(agent, {"type": "gathered", "agent": agent.id,
                               "resource": rtype, "qty": yield_n})

    if verb == "eat":
        if agent.inventory.get("berries", 0) < 1:
            return _finish(agent, {"type": "eat_failed", "agent": agent.id,
                                   "reason": "no food carried"})
        agent.inventory["berries"] -= 1
        restore = settings["eat_berries_hunger_restore"]
        if "cooked_food" in agent.knowledge:
            restore += settings["eat_cooked_hunger_bonus"]
        agent.needs.hunger = min(100.0, agent.needs.hunger + restore)
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

    if verb == "build":
        spec = graph.buildable(action["structure"])
        materials = spec["materials"]
        if any(agent.inventory.get(m, 0) < n for m, n in materials.items()):
            return _finish(agent, {"type": "build_failed", "agent": agent.id,
                                   "structure": action["structure"],
                                   "reason": "missing materials"})
        if not spec.get("carried"):
            if world_map.terrain(agent.x, agent.y) not in spec.get("terrain", []):
                return _finish(agent, {"type": "build_failed", "agent": agent.id,
                                       "structure": action["structure"],
                                       "reason": "wrong terrain"})
            if any((s.x, s.y) == (agent.x, agent.y) for s in state.structures):
                return _finish(agent, {"type": "build_failed", "agent": agent.id,
                                       "structure": action["structure"],
                                       "reason": "tile occupied"})
        for m, n in materials.items():
            agent.inventory[m] -= n
        if spec.get("carried"):
            agent.inventory[action["structure"]] = \
                agent.inventory.get(action["structure"], 0) + 1
        else:
            state.structures.append(Structure(
                type=action["structure"], x=agent.x, y=agent.y,
                built_by=agent.id, built_minute=state.sim_minutes))
        return _finish(agent, {"type": "built", "agent": agent.id,
                               "structure": action["structure"]})

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

    return []
