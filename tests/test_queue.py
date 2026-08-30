from genesis.mind.queue import DecisionJob, InlineQueue, ThreadedThinkQueue
from genesis.mind.brain import FakeBrain


def _job(agent_id="a", minute=0):
    return DecisionJob(agent_id=agent_id, sim_minute=minute,
                       affordances=[{"id": "eat"}, {"id": "sleep"}], context={})


def test_inline_queue_resolves_immediately():
    q = InlineQueue()
    q.submit(_job(), FakeBrain(lambda c, a: {"choice": "sleep", "reason": "tired"}))
    out = q.pop("a")
    assert out["choice"] == "sleep" and out["reason"] == "tired" and out["sim_minute"] == 0


def test_inline_queue_drops_invalid_choice():
    q = InlineQueue()
    q.submit(_job(), FakeBrain(lambda c, a: {"choice": "fly", "reason": "nope"}))
    assert q.pop("a") is None
    assert q.pending("a") is False


def test_threaded_queue_delivers_result():
    q = ThreadedThinkQueue(daily_budget=100)
    q.submit(_job(), FakeBrain(lambda c, a: {"choice": "eat", "reason": "r"}))
    done = q.wait_idle(timeout=2.0)   # test helper: block until worker drains
    assert done
    assert q.pop("a")["choice"] == "eat"


def test_threaded_queue_stops_submitting_at_budget():
    q = ThreadedThinkQueue(daily_budget=0)
    q.submit(_job(), FakeBrain(lambda c, a: {"choice": "eat", "reason": "r"}))
    q.wait_idle(timeout=1.0)
    assert q.pop("a") is None          # nothing was processed
    assert q.requests_today == 0


def test_threaded_queue_survives_resolve_exception():
    q = ThreadedThinkQueue(daily_budget=100)
    bad = DecisionJob(agent_id="a", sim_minute=0, affordances=[{"nope": 1}], context={})  # no "id" -> KeyError in _resolve, outside its try
    q.submit(bad, FakeBrain(lambda c, a: {"choice": "eat", "reason": "x"}))
    assert q.wait_idle(timeout=2.0)          # worker drained the bad job, did not die
    assert q.pending("a") is False           # not stuck pending
    # worker still alive: a subsequent good job is still processed
    q.submit(_job(), FakeBrain(lambda c, a: {"choice": "eat", "reason": "ok"}))
    assert q.wait_idle(timeout=2.0)
    assert q.pop("a")["choice"] == "eat"
