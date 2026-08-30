import pytest
from genesis.mind.llm_brain import LLMBrain
from genesis.mind.brain import BrainError


class StubProvider:
    def __init__(self, replies): self.replies = list(replies); self.calls = 0
    def complete(self, prompt, schema):
        r = self.replies[min(self.calls, len(self.replies) - 1)]; self.calls += 1
        return r


AFFS = [{"id": "eat", "label": "eat", "dir": "here", "dist": 0},
        {"id": "sleep", "label": "sleep", "dir": "here", "dist": 0}]


def test_returns_valid_choice():
    b = LLMBrain(StubProvider([{"choice": "sleep", "reason": "tired"}]), "m")
    assert b.choose({"persona": "lazy"}, AFFS) == {"choice": "sleep", "reason": "tired"}


def test_retries_once_then_succeeds():
    p = StubProvider([{"choice": "fly", "reason": "x"}, {"choice": "eat", "reason": "ok"}])
    b = LLMBrain(p, "m")
    assert b.choose({}, AFFS)["choice"] == "eat"
    assert p.calls == 2


def test_raises_after_two_invalid():
    p = StubProvider([{"choice": "fly"}, {"choice": "swim"}])
    with pytest.raises(BrainError):
        LLMBrain(p, "m").choose({}, AFFS)
