def action_fails(agent, layer_cfg, rng):
    band = layer_cfg.get("curse_band")
    if not band:
        return False
    lo, hi = band
    if lo <= agent.strain < hi:
        return rng.random() < layer_cfg.get("curse_fail_chance", 0.0)
    return False
