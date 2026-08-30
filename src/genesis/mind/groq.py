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
                "temperature": 0.7, "max_tokens": 120}
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        data = _http_post(_URL, headers, body)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
