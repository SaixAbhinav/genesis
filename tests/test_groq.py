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


def test_request_sets_user_agent_and_ample_token_budget(monkeypatch):
    # Groq sits behind Cloudflare, which 403s urllib's default User-Agent, and
    # reasoning models need room to finish the JSON. Capture what we send.
    captured = {}

    def fake_post(url, headers, body):
        captured["headers"] = headers
        captured["body"] = body
        return {"choices": [{"message": {"content": '{"choice":"x","reason":"y"}'}}]}

    monkeypatch.setattr(G, "_http_post", fake_post)
    G.GroqAdapter("m", api_key="k").complete("prompt", {})
    assert captured["headers"].get("User-Agent")            # non-default UA sent
    assert captured["body"]["max_tokens"] >= 512            # room for reasoning
