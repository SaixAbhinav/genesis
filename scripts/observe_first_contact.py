"""Observe first contact between races. Runs the first-contact scenario with
LLM minds and prints a contact timeline + per-race positions. Requires
GROQ_API_KEY in the environment. Usage: uv run python scripts/observe_first_contact.py [days]
"""
import sys
from collections import defaultdict
from genesis.world.engine import Engine

SC = "configs/scenarios/first-contact"


def main(days: float = 2.0) -> None:
    eng = Engine.from_configs("configs", scenario_dir=SC, seed=42,
                              sim_minutes=0, minds=True)
    race_of = {a.id: a.race for a in eng.state.agents}
    events = eng.advance(int(days * eng.settings["minutes_per_day"]))

    decided = {(e["agent"], e["minute"]): e for e in events if e["type"] == "decided"}
    print(f"=== first contact, {days} day(s), {len(eng.state.agents)} agents ===")
    print("\n-- contact timeline --")
    for e in events:
        if e["type"] == "contact":
            d = decided.get((e["agent"], e["minute"]))
            reason = f' -> {d["choice"]}: {d["reason"][:80]}' if d else ""
            print(f"  min {e['minute']:6d}  {e['agent']} ({race_of[e['agent']]}) "
                  f"meets {e['other']} ({e['race']}){reason}")

    approaches = sum(1 for e in events if e["type"] == "decided"
                     and str(e["choice"]).startswith("approach"))
    avoids = sum(1 for e in events if e["type"] == "decided"
                 and str(e["choice"]).startswith("avoid"))
    print(f"\napproach decisions: {approaches}   avoid decisions: {avoids}")
    print("\n-- final positions --")
    byrace = defaultdict(list)
    for a in eng.state.agents:
        byrace[a.race].append(f"{a.name}@({a.x},{a.y})")
    for race, who in sorted(byrace.items()):
        print(f"  {race:10s} {who}")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 2.0)
