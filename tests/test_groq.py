import pytest
from genesis.mind import groq as G
from genesis.mind.brain import BrainError


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(BrainError):
        G.GroqAdapter("llama-3.3-70b-versatile").complete("hi", {})


def test_parses_json_content(monkeypatch):
    # patch the HTTP layer so no network call happens
    monkeypatch.setattr(G, "_http_post",
                        lambda url, headers, body: {
                            "choices": [{"message": {"content": '{"choice":"eat","reason":"hungry"}'}}]})
    out = G.GroqAdapter("m", api_key="k").complete("prompt", {})
    assert out == {"choice": "eat", "reason": "hungry"}
