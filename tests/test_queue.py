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


def test_threaded_queue_pool_delivers_all_agents():
    from genesis.mind.brain import FakeBrain
    q = ThreadedThinkQueue(daily_budget=100, workers=4)
    brain = FakeBrain(lambda c, a: {"choice": a[0]["id"], "reason": "r"})
    for aid in ("a", "b", "c", "d"):
        q.submit(DecisionJob(agent_id=aid, sim_minute=0,
                             affordances=[{"id": "eat"}], context={}), brain)
    assert q.wait_idle(timeout=3.0)
    for aid in ("a", "b", "c", "d"):
        assert q.pop(aid)["choice"] == "eat"
    assert q.requests_today == 4


def test_threaded_queue_rate_limiter_spaces_requests():
    import time
    from genesis.mind.brain import FakeBrain
    q = ThreadedThinkQueue(daily_budget=100, workers=4, min_interval_s=0.05)
    brain = FakeBrain(lambda c, a: {"choice": a[0]["id"], "reason": "r"})
    t0 = time.monotonic()
    for aid in ("a", "b", "c"):
        q.submit(DecisionJob(agent_id=aid, sim_minute=0,
                             affordances=[{"id": "eat"}], context={}), brain)
    assert q.wait_idle(timeout=3.0)
    # 3 requests with a 0.05s floor between starts -> >= ~0.10s even with a pool
    assert time.monotonic() - t0 >= 0.08
    for aid in ("a", "b", "c"):
        assert q.pop(aid)["choice"] == "eat"
