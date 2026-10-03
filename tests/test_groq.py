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


def _http_error(monkeypatch, code, body, headers=None):
    import io
    import urllib.error

    def fail(req, timeout):
        raise urllib.error.HTTPError(req.full_url, code, "err", headers or {},
                                     io.BytesIO(body))

    monkeypatch.setattr(G.urllib.request, "urlopen", fail)


def test_http_error_body_is_surfaced(monkeypatch):
    # urllib's HTTPError str() is just "HTTP Error 400: Bad Request"; the body
    # says why (json_validate_failed, ...). Keep it.
    _http_error(monkeypatch, 400, b'{"error":{"code":"json_validate_failed"}}')
    with pytest.raises(BrainError, match="HTTP 400.*json_validate_failed"):
        G.GroqAdapter("m", api_key="k").complete("hi", {})


def test_429_parses_wait_from_message(monkeypatch):
    _http_error(monkeypatch, 429,
                b'{"error":{"message":"Rate limit reached. Please try again in 1m2.5s. Need more"}}')
    with pytest.raises(G.RateLimited) as exc:
        G._http_post("https://example.test", {}, {})
    assert exc.value.wait_s == pytest.approx(62.5)


def test_429_prefers_retry_after_header(monkeypatch):
    _http_error(monkeypatch, 429, b'{"error":{"message":"try again in 3s"}}',
                headers={"retry-after": "7"})
    with pytest.raises(G.RateLimited) as exc:
        G._http_post("https://example.test", {}, {})
    assert exc.value.wait_s == 7.0


def _rate_limited_then_ok(n_fail, wait_s=3.5):
    calls = {"n": 0}

    def post(url, headers, body):
        calls["n"] += 1
        if calls["n"] <= n_fail:
            raise G.RateLimited("HTTP 429: busy", wait_s)
        return {"choices": [{"message": {"content": '{"choice":"eat","reason":"r"}'}}]}

    return post, calls


def test_rate_limit_waits_then_succeeds(monkeypatch):
    post, calls = _rate_limited_then_ok(2)
    monkeypatch.setattr(G, "_http_post", post)
    slept = []
    out = G.GroqAdapter("m", api_key="k", sleep=slept.append).complete("p", {})
    assert out["choice"] == "eat" and calls["n"] == 3
    assert len(slept) == 2 and all(s >= 3.5 for s in slept)   # waited as told


def test_rate_limit_gives_up_after_max_retries(monkeypatch):
    post, calls = _rate_limited_then_ok(99)
    monkeypatch.setattr(G, "_http_post", post)
    slept = []
    with pytest.raises(G.RateLimited):
        G.GroqAdapter("m", api_key="k", max_retries=3, sleep=slept.append).complete("p", {})
    assert len(slept) == 3 and calls["n"] == 4


def test_long_wait_is_a_daily_cap_so_fail_fast(monkeypatch):
    post, calls = _rate_limited_then_ok(99, wait_s=450.0)
    monkeypatch.setattr(G, "_http_post", post)
    slept = []
    with pytest.raises(G.RateLimited):
        G.GroqAdapter("m", api_key="k", sleep=slept.append).complete("p", {})
    assert slept == [] and calls["n"] == 1
