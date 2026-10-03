import json
import os
import re
import time
import urllib.error
import urllib.request
from genesis.mind.brain import BrainError

_URL = "https://api.groq.com/openai/v1/chat/completions"
_DEFAULT_WAIT_S = 2.0   # when a 429 doesn't say how long to wait
_WAIT_BUFFER_S = 0.25   # retrying exactly on the boundary tends to 429 again
_UNIT_S = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}


class RateLimited(BrainError):
    """HTTP 429. `wait_s` is how long the provider says to wait before retrying."""
    def __init__(self, message: str, wait_s: float):
        super().__init__(message)
        self.wait_s = wait_s


def _parse_wait(text: str) -> float | None:
    # Groq phrases it as e.g. "try again in 3.59s", "234ms", or "1m2.5s".
    m = re.search(r"try again in ([0-9hms.]+)", text)
    if not m:
        return None
    parts = re.findall(r"([\d.]+)(h|ms|m|s)", m.group(1))
    return sum(float(n) * _UNIT_S[u] for n, u in parts) if parts else None


def _http_post(url: str, headers: dict, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        # str(e) is only "HTTP Error 429: ..."; the body says why (rate limit,
        # json_validate_failed, ...), which is what a failure report needs.
        text = e.read().decode(errors="replace")
        if e.code == 429:
            try:
                wait = float((e.headers or {}).get("retry-after"))
            except (TypeError, ValueError):
                wait = _parse_wait(text)
            raise RateLimited(f"HTTP 429: {text[:300]}",
                              wait if wait is not None else _DEFAULT_WAIT_S) from e
        raise BrainError(f"HTTP {e.code}: {text[:300]}") from e


class GroqAdapter:
    def __init__(self, model: str, api_key: str | None = None,
                 max_retries: int = 5, max_wait_s: float = 60.0, sleep=time.sleep):
        self.model = model
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.max_retries = max_retries
        self.max_wait_s = max_wait_s
        self._sleep = sleep

    def complete(self, prompt: str, schema: dict) -> dict:
        if not self.api_key:
            raise BrainError("GROQ_API_KEY not set")
        body = {"model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.7,
                # Reasoning models (e.g. gpt-oss) spend output tokens thinking;
                # too small a budget truncates before the JSON and 400s with
                # json_validate_failed. Keep effort low to stay cheap/fast.
                "max_tokens": 1024, "reasoning_effort": "low"}
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json",
                   # Groq's API sits behind Cloudflare, which rejects urllib's
                   # default User-Agent with a 403 (error 1010). Send our own.
                   "User-Agent": "genesis-sim/0.1"}
        for attempt in range(self.max_retries + 1):
            try:
                data = _http_post(_URL, headers, body)
                break
            except RateLimited as e:
                # Free tiers cap tokens per minute and the 429 says when capacity
                # frees up, so wait that long instead of dropping the decision.
                # A long wait means a daily cap: give up rather than stall the sim.
                if attempt == self.max_retries or e.wait_s > self.max_wait_s:
                    raise
                self._sleep(e.wait_s + _WAIT_BUFFER_S)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
