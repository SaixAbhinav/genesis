import argparse
import json
from collections import Counter
from pathlib import Path

from genesis import load_settings
from genesis.persistence.db import append_events, connect, load_state, save_state
from genesis.world.engine import Engine
from genesis.world.grid import WorldMap
from genesis.world.state import Resource, WorldState, load_agents

CONFIG_DIR = Path("configs")


def _fresh_world(seed: int) -> WorldState:
    map_cfg = json.loads((CONFIG_DIR / "map.json").read_text(encoding="utf-8"))
    return WorldState(
        sim_minutes=720, seed=seed,
        agents=load_agents(CONFIG_DIR / "agents.json"),
        resources=[Resource(**r) for r in map_cfg["resources"]])


def run_sim(days: float, db_path: str | Path, seed: int = 42) -> dict:
    settings = load_settings(CONFIG_DIR / "settings.json")
    conn = connect(db_path)
    state = load_state(conn) or _fresh_world(seed)
    engine = Engine(state, WorldMap.from_file(CONFIG_DIR / "map.json"), settings)
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
        } for a in state.agents],
        "discoveries": {a.name: list(a.knowledge) for a in state.agents},
        "structures": [{"type": s.type, "x": s.x, "y": s.y}
                       for s in state.structures],
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Run the Genesis world simulation")
    p.add_argument("--days", type=float, default=1.0)
    p.add_argument("--db", default="world.db")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    print(json.dumps(run_sim(args.days, args.db, args.seed), indent=2))


if __name__ == "__main__":
    main()
