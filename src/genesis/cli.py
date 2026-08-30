import argparse
import json
from collections import Counter
from pathlib import Path

from genesis.persistence.db import append_events, connect, load_state, save_state
from genesis.world.engine import Engine

CONFIG_DIR = Path("configs")


def _top_rank(agent) -> str:
    if not agent.attr_rank:
        return "none"
    attr, rank_idx = max(agent.attr_rank.items(), key=lambda kv: kv[1])
    return f"{attr}:{rank_idx}"


def run_sim(days: float, db_path: str | Path, seed: int = 42,
            minds: bool = False) -> dict:
    engine = Engine.from_configs(CONFIG_DIR, seed=seed, minds=minds)
    conn = connect(db_path)
    saved = load_state(conn)
    if saved is not None:
        engine.state = saved
    state = engine.state
    settings = engine.settings
    events = engine.advance(int(days * settings["minutes_per_day"]))
    save_state(conn, state)
    append_events(conn, events)
    return {
        "sim_minutes": state.sim_minutes,
        "days_run": days,
        "event_counts": dict(Counter(ev["type"] for ev in events)),
        "agents": [{
            "name": a.name, "x": a.x, "y": a.y,
            "hunger": round(a.needs.hunger, 1),
            "energy": round(a.needs.energy, 1),
            "warmth": round(a.needs.warmth, 1),
            "status": a.status, "inventory": a.inventory,
            "layer": a.layer,
            "strain": round(a.strain, 1),
            "mana": f"{round(a.mana, 1)}/{round(a.mana_max, 1)}",
            "top_rank": _top_rank(a),
        } for a in state.agents],
        "discoveries": {a.name: list(a.knowledge) for a in state.agents},
        "structures": [{"type": s.type, "x": s.x, "y": s.y}
                       for s in state.structures],
        "deaths": sum(1 for a in state.agents if a.status == "dead"),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Run the Genesis world simulation")
    p.add_argument("--days", type=float, default=1.0)
    p.add_argument("--db", default="world.db")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--minds", action="store_true",
                   help="Enable LLM-driven decisions (requires GROQ_API_KEY)")
    args = p.parse_args()
    print(json.dumps(run_sim(args.days, args.db, args.seed, args.minds), indent=2))


if __name__ == "__main__":
    main()
