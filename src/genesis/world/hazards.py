def _clamp(v):
    return max(0.0, min(100.0, v))


def miasma_tick(agent, layer_cfg, minute):
    dmg = layer_cfg.get("miasma_damage", 0.0)
    if dmg <= 0 or minute < agent.purified_until:
        return []
    need = layer_cfg.get("miasma_need", "energy")
    setattr(agent.needs, need, _clamp(getattr(agent.needs, need) - dmg))
    return [{"type": "miasma", "agent": agent.id, "need": need}]


def fall_check(agent, world_map, layer_cfg, minute, rng):
    cliffs = layer_cfg.get("cliff_tiles", [])
    if [agent.x, agent.y] not in cliffs or minute < agent.negate_fall_until:
        return []
    agent.strain += layer_cfg.get("fall_strain", 0.0)
    agent.needs.energy = 0.0  # a fall crashes energy → may trigger curse death
    return [{"type": "fell", "agent": agent.id, "strain": agent.strain}]


def creature_damage(agent, layer_cfg):
    dmg = layer_cfg.get("creature_damage", 0.0)
    if dmg <= 0:
        return []
    agent.needs.energy = _clamp(agent.needs.energy - dmg)
    return [{"type": "creature_attack", "agent": agent.id}]
