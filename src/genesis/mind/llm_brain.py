import json
from genesis.mind.brain import BrainError

_SCHEMA = {"type": "object",
           "properties": {"choice": {"type": "string"}, "reason": {"type": "string"}},
           "required": ["choice", "reason"]}


def _prompt(context: dict, affordances: list[dict]) -> str:
    # Drop "options" from the state dump — the Options list below already spells
    # them out, and duplicating the full affordance JSON roughly doubles the
    # prompt tokens (which is what the free-tier TPM limit is spent on).
    # A "notice" is something that just happened (e.g. first contact). It gets its
    # own line ahead of the State dump so it registers instead of being one more
    # JSON field.
    state = {k: v for k, v in context.items() if k not in ("options", "notice")}
    lines = ["You are an agent in a survival world. Pick ONE option by its id.",
             "Needs run 0-100: 100 means fully satisfied, 0 means critical."]
    for note in context.get("notice", []):
        lines.append(f"Just happened: {note}")
    lines += [f"State: {json.dumps(state, default=str)}", "Options:"]
    for a in affordances:
        lines.append(f"- {a['id']}: {a.get('label','')} ({a.get('dir','')}, {a.get('dist','')})")
    lines.append('Reply JSON: {"choice": "<id>", "reason": "<one short line>"}')
    return "\n".join(lines)


class LLMBrain:
    def __init__(self, provider, model: str):
        self.provider = provider
        self.model = model

    def choose(self, context: dict, affordances: list[dict]) -> dict:
        ids = {a["id"] for a in affordances}
        prompt = _prompt(context, affordances)
        last = "no reply"
        for _ in range(2):  # one try + one retry
            try:
                out = self.provider.complete(prompt, _SCHEMA)
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
                continue
            if isinstance(out, dict) and out.get("choice") in ids:
                return {"choice": out["choice"], "reason": out.get("reason", "")}
            last = f"invalid reply {out!r}"
        raise BrainError(f"no valid choice after retry: {last[:300]}")
