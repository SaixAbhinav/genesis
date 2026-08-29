from genesis.world.structures import Structure


def _clamp(v):
    return max(0.0, min(100.0, v))


def _reduce_strain(effect, agent, state, wm, settings, minute):
    agent.strain = max(0.0, agent.strain - float(effect.get("amount", 0)))
    for need, amt in effect.get("bonus", {}).items():
        cur = getattr(agent.needs, need)
        setattr(agent.needs, need, _clamp(cur + float(amt)))
    return [{"type": "healed", "agent": agent.id, "strain": agent.strain}]


def _warmth(effect, agent, state, wm, settings, minute):
    agent.needs.warmth = _clamp(agent.needs.warmth + float(effect.get("amount", 0)))
    return [{"type": "warmed", "agent": agent.id}]


def _clear_miasma(effect, agent, state, wm, settings, minute):
    agent.purified_until = minute + int(effect.get("duration", 0))
    return [{"type": "purified", "agent": agent.id, "until": agent.purified_until}]


def _negate_fall(effect, agent, state, wm, settings, minute):
    agent.negate_fall_until = minute + int(effect.get("duration", 0))
    return [{"type": "wind_ready", "agent": agent.id, "until": agent.negate_fall_until}]


def _build_shelter(effect, agent, state, wm, settings, minute):
    state.structures.append(Structure(type=effect.get("structure", "stone_hut"),
                                       x=agent.x, y=agent.y, built_by=agent.id,
                                       built_minute=minute, layer=agent.layer))
    return [{"type": "shaped", "agent": agent.id, "structure": effect.get("structure")}]


def _attack(effect, agent, state, wm, settings, minute):
    # Combat resolution lives in hazards.creature_encounter; here we just flag intent.
    return [{"type": "attacked", "agent": agent.id, "power": effect.get("power", 0)}]


_HANDLERS = {
    "reduce_strain": _reduce_strain, "warmth": _warmth,
    "clear_miasma": _clear_miasma, "negate_fall": _negate_fall,
    "build_shelter": _build_shelter, "attack": _attack,
}


def apply_effect(effect, agent, state, world_map, settings, minute):
    handler = _HANDLERS.get(effect.get("type"))
    if handler is None:
        return [{"type": "effect_noop", "agent": agent.id,
                 "effect": effect.get("type")}]
    return handler(effect, agent, state, world_map, settings, minute)
