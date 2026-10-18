"""Any OpenAI-compatible chat-completions endpoint: OpenAI, Qwen on DashScope, a local vLLM or Ollama.

Text only: an API returns no hidden states, so it can run the text and no-message conditions
but cannot write or read latent posts. The key is read from an environment variable (LF_API_KEY
by default) and is never written to configs or logs; local servers may need no key at all.

    export LF_API_KEY=...
    python -m forum.run --backend api --model qwen3-8b \
        --api-base https://dashscope.aliyuncs.com/compatible-mode/v1 --api-extra '{"enable_thinking": false}' ...
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

from model.backends.base import Backend, Generation, LATENT_RE

_THINK = re.compile(r"<think>.*?</think>\s*", re.S)


class APIBackend(Backend):
    name = "api"
    reads_latents = False

    def __init__(self, model: str, base_url: str, key_env: str = "LF_API_KEY", extra: dict | None = None,
                 timeout: float = 120.0, retries: int = 4):
        if not base_url:
            raise ValueError("the api backend needs --api-base (or LF_API_BASE), e.g. https://api.openai.com/v1")
        self.model, self.url = model, base_url.rstrip("/") + "/chat/completions"
        self.key = os.environ.get(key_env, "")
        self.extra, self.timeout, self.retries = extra or {}, timeout, retries

    def _post(self, body: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers)
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:   # retry rate limits and server errors only
                if e.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise RuntimeError(f"api error {e.code}: {e.read().decode(errors='replace')[:300]}") from None
            except urllib.error.URLError:
                if attempt == self.retries:
                    raise
            time.sleep(2 ** attempt)

    def chat(self, messages, latents=(), *, purpose="", meta=None, max_new_tokens=512, temperature=0.0):
        if latents or any(LATENT_RE.search(m["content"]) for m in messages):
            raise ValueError("the api backend cannot read latent posts; use --backend hf")
        data = self._post({"model": self.model, "messages": messages, "max_tokens": max_new_tokens,
                           "temperature": temperature, **self.extra})
        text = _THINK.sub("", data["choices"][0]["message"].get("content") or "").strip()
        usage = data.get("usage") or {}
        return Generation(text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
