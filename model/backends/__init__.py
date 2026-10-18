"""Model backends: `mock` (no model, for tests), `hf` (a local HuggingFace model; needed for latent
posts) and `api` (any OpenAI-compatible endpoint; text only)."""
import json
import os

from model.backends.base import Backend, Generation, Latent, LATENT_MARK, LATENT_RE

DEFAULT_MODEL = os.environ.get("LF_MODEL", "Qwen/Qwen3-8B")


def make_backend(cfg) -> Backend:
    if cfg.backend == "mock":
        from model.backends.mock import MockBackend
        return MockBackend(p_correct=cfg.mock_p_correct, seed=cfg.seed)
    if cfg.backend == "api":
        from model.backends.api import APIBackend
        return APIBackend(cfg.model, cfg.api_base, cfg.api_key_env, json.loads(cfg.api_extra or "{}"))
    if cfg.backend == "hf":
        from model.backends.hf import HFBackend
        b = HFBackend.load(cfg.model, enable_thinking=cfg.enable_thinking)
        if cfg.reader_adapter:
            from model.read_adapter import load_adapter
            b.latent_map = load_adapter(cfg.reader_adapter, b.device)
        return b
    raise ValueError(f"unknown backend {cfg.backend!r}")
