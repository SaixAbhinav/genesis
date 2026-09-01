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
    def __init__(self, daily_budget: int, workers: int = 1,
                 min_interval_s: float = 0.0):
        self.daily_budget = daily_budget
        self.requests_today = 0
        self._jobs: _q.Queue = _q.Queue()
        self._inbox: dict[str, dict] = {}
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        # Per-provider rate limiter: no two brain calls start closer than
        # min_interval_s apart (0 = unthrottled). Free tiers cap requests per
        # minute / tokens per minute; without this the pool 429s.
        self._min_interval = max(0.0, min_interval_s)
        self._next_req = 0.0
        # A pool of daemon workers drains the same queue; shared state is
        # lock-guarded, so concurrent workers let N brain calls run at once
        # (decisions for N agents land together instead of serially).
        self._workers = [threading.Thread(target=self._run, daemon=True)
                         for _ in range(max(1, workers))]
        for w in self._workers:
            w.start()

    def submit(self, job: DecisionJob, brain) -> None:
        with self._lock:
            if self.requests_today >= self.daily_budget:
                return  # budget spent -> agent rides instinct
            self.requests_today += 1
            self._pending.add(job.agent_id)
        self._jobs.put((job, brain))

    def _throttle(self):
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next_req - now)
            self._next_req = max(now, self._next_req) + self._min_interval
        if wait:
            time.sleep(wait)  # sleep outside the lock

    def _run(self):
        while True:
            job, brain = self._jobs.get()
            result = None
            try:
                self._throttle()
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
