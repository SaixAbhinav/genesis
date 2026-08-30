import json
import os
import urllib.request
from genesis.mind.brain import BrainError

_URL = "https://api.groq.com/openai/v1/chat/completions"


def _http_post(url: str, headers: dict, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


class GroqAdapter:
    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")

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
        data = _http_post(_URL, headers, body)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
