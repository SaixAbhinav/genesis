from dataclasses import dataclass


@dataclass
class DecisionJob:
    agent_id: str
    sim_minute: int
    affordances: list[dict]
    context: dict


def _resolve(job: DecisionJob, brain) -> dict | None:
    ids = {a["id"] for a in job.affordances}
    try:
        out = brain.choose(job.context, job.affordances)
    except Exception:
        return None
    if not isinstance(out, dict) or out.get("choice") not in ids:
        return None
    return {"choice": out["choice"], "reason": out.get("reason", ""),
            "sim_minute": job.sim_minute}


class InlineQueue:
    """Synchronous queue: resolves each job immediately. Deterministic."""
    def __init__(self):
        self._inbox: dict[str, dict] = {}
        self._pending: set[str] = set()

    def submit(self, job: DecisionJob, brain) -> None:
        self._pending.add(job.agent_id)
        result = _resolve(job, brain)
        self._pending.discard(job.agent_id)
        if result is not None:
            self._inbox[job.agent_id] = result

    def pending(self, agent_id: str) -> bool:
        return agent_id in self._pending

    def pop(self, agent_id: str) -> dict | None:
        return self._inbox.pop(agent_id, None)
