import queue as _q
import threading
import time
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


class ThreadedThinkQueue:
    """Async queue: a worker thread resolves jobs off the sim loop.

    A per-day request budget caps how many jobs may be submitted; at or over
    budget, submit() is a no-op so the agent falls back to instinct.
    """
    def __init__(self, daily_budget: int):
        self.daily_budget = daily_budget
        self.requests_today = 0
        self._jobs: _q.Queue = _q.Queue()
        self._inbox: dict[str, dict] = {}
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def submit(self, job: DecisionJob, brain) -> None:
        with self._lock:
            if self.requests_today >= self.daily_budget:
                return  # budget spent -> agent rides instinct
            self.requests_today += 1
            self._pending.add(job.agent_id)
        self._jobs.put((job, brain))

    def _run(self):
        while True:
            job, brain = self._jobs.get()
            result = None
            try:
                result = _resolve(job, brain)
            except Exception:
                result = None
            with self._lock:
                self._pending.discard(job.agent_id)
                if result is not None:
                    self._inbox[job.agent_id] = result
            self._jobs.task_done()

    def pending(self, agent_id: str) -> bool:
        with self._lock:
            return agent_id in self._pending

    def pop(self, agent_id: str) -> dict | None:
        with self._lock:
            return self._inbox.pop(agent_id, None)

    def wait_idle(self, timeout: float = 2.0) -> bool:
        # test helper: block until the job queue drains
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._jobs.unfinished_tasks == 0:
                return True
            time.sleep(0.01)
        return False
