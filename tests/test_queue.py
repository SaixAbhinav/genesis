from genesis.mind.queue import DecisionJob, InlineQueue
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
