from genesis.world.state import Agent


def is_daytime(sim_minutes: int, settings: dict) -> bool:
    m = sim_minutes % settings["minutes_per_day"]
    return settings["day_start_minute"] <= m < settings["day_end_minute"]


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def tick_needs(agent: Agent, sim_minutes: int, settings: dict) -> list[dict]:
    events: list[dict] = []
    n = agent.needs

    if agent.status == "collapsed":
        if sim_minutes >= agent.collapse_until:
            agent.status = "active"
            for attr in ("hunger", "energy", "warmth"):
                if getattr(n, attr) <= 0:
                    setattr(n, attr, settings["collapse_recover_need_value"])
            n.energy = max(n.energy, settings["collapse_recover_energy_value"])
            events.append({"type": "recovered", "agent": agent.id,
                           "minute": sim_minutes})
        return events

    day = is_daytime(sim_minutes, settings)
    n.hunger = _clamp(n.hunger - settings["hunger_decay_per_min"])
    if agent.status == "sleeping":
        n.energy = _clamp(n.energy + settings["energy_regen_sleeping_per_min"])
    else:
        n.energy = _clamp(n.energy - settings["energy_decay_per_min"])
    if day:
        n.warmth = _clamp(n.warmth + settings["warmth_regen_day_per_min"])
    else:
        rate = (settings["warmth_decay_night_sleeping_per_min"]
                if agent.status == "sleeping"
                else settings["warmth_decay_night_per_min"])
        n.warmth = _clamp(n.warmth - rate)

    if min(n.hunger, n.energy, n.warmth) <= 0:
        agent.status = "collapsed"
        agent.collapse_until = sim_minutes + settings["collapse_duration_min"]
        agent.current_action = None
        events.append({"type": "collapsed", "agent": agent.id,
                       "minute": sim_minutes})
    return events
