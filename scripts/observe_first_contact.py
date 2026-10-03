"""Observe first contact between races. Runs the first-contact scenario with
LLM minds and prints the contact timeline, every Brain decision with its reason,
and an hourly trace of how close the races are. Requires GROQ_API_KEY.

Usage: uv run python scripts/observe_first_contact.py [days] [events.jsonl]
The optional JSONL path receives every decision/contact/brain_failed event plus
the hourly snapshots, so a run can be re-analysed without paying for another one.
"""
import json
import sys
from collections import Counter
from genesis.world.engine import Engine

SC = "configs/scenarios/first-contact"
CHUNK = 60  # sim-minutes per snapshot


def _min_cross_race_dist(agents) -> int | None:
    best = None
    for a in agents:
        for b in agents:
            if a.race and b.race and a.race < b.race and a.layer == b.layer:
                d = abs(a.x - b.x) + abs(a.y - b.y)
                best = d if best is None else min(best, d)
    return best


def main(days: float = 2.0, log_path: str | None = None) -> None:
    eng = Engine.from_configs("configs", scenario_dir=SC, seed=42,
                              sim_minutes=0, minds=True)
    who = {a.id: f"{a.name}({a.race})" for a in eng.state.agents}
    total = int(days * eng.settings["minutes_per_day"])
    events, snaps = [], []
    while eng.state.sim_minutes < total:
        events += eng.advance(min(CHUNK, total - eng.state.sim_minutes))
        living = [a for a in eng.state.agents if a.status != "dead"]
        snaps.append({"type": "snapshot", "minute": eng.state.sim_minutes,
                      "min_cross_race_dist": _min_cross_race_dist(living),
                      "positions": {a.name: [a.x, a.y] for a in eng.state.agents}})

    decided = [e for e in events if e["type"] == "decided"]
    failed = [e for e in events if e["type"] == "brain_failed"]
    by_key = {(e["agent"], e["minute"]): e for e in decided}
    fail_key = {(e["agent"], e["minute"]): e for e in failed}
    print(f"=== first contact, {days} day(s), {len(eng.state.agents)} agents ===")

    print("\n-- contact timeline (with the decision it forced) --")
    for e in events:
        if e["type"] == "contact":
            key = (e["agent"], e["minute"])
            if key in by_key:
                tail = f" -> {by_key[key]['choice']}: {by_key[key]['reason']}"
            elif key in fail_key:
                tail = f" -> BRAIN FAILED: {fail_key[key]['error'][:120]}"
            else:
                tail = " -> (no Brain decision)"
            print(f"  min {e['minute']:5d}  {who[e['agent']]} meets {e['other']}{tail}")

    print(f"\n-- brain failures ({len(failed)} of {len(failed) + len(decided)} calls) --")
    if not failed:
        print("  none")
    for err, n in Counter(e["error"][:120] for e in failed).most_common():
        print(f"  x{n}  {err}")

    print(f"\n-- every decision ({len(decided)}) --")
    for e in decided:
        print(f"  min {e['minute']:5d}  {who[e['agent']]:18s} {e['choice']:28s} {e['reason']}")

    print("\n-- hourly trace: closest cross-race distance | positions --")
    for s in snaps:
        pos = "  ".join(f"{n}{tuple(p)}" for n, p in s["positions"].items())
        print(f"  min {s['minute']:5d}  dist {s['min_cross_race_dist']!s:>4}  | {pos}")

    social = Counter((who[e["agent"]], e["choice"]) for e in decided
                     if e["choice"].startswith(("approach:", "avoid:")))
    print("\n-- approach/avoid choices --")
    if not social:
        print("  none")
    for (agent, choice), n in sorted(social.items()):
        print(f"  {agent:18s} {choice:20s} x{n}")

    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            for e in events:
                if e["type"] in ("decided", "contact", "brain_failed"):
                    f.write(json.dumps(e) + "\n")
            for s in snaps:
                f.write(json.dumps(s) + "\n")
        print(f"\nwrote decisions, contacts and snapshots to {log_path}")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 2.0,
         sys.argv[2] if len(sys.argv) > 2 else None)
