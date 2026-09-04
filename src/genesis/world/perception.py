def _bearing(dx: int, dy: int) -> str:
    ns = ("N" if dy < 0 else "S" if dy > 0 else "")
    ew = ("W" if dx < 0 else "E" if dx > 0 else "")
    return (ns + ew) or "here"


def perceive_agents(agent, state, radius: int) -> list[dict]:
    out = []
    for other in state.agents:
        if other.id == agent.id or other.status == "dead" \
                or other.layer != agent.layer:
            continue
        dist = abs(other.x - agent.x) + abs(other.y - agent.y)
        if dist <= radius:
            out.append({"name": other.name, "race": other.race,
                        "dir": _bearing(other.x - agent.x, other.y - agent.y),
                        "dist": dist})
    out.sort(key=lambda o: (o["dist"], o["name"]))
    return out
