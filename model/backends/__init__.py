from .base import Backend, Generation, Latent, LATENT_MARK, LATENT_RE


def make_backend(cfg) -> Backend:
    if cfg.backend == "mock":
        from .mock import MockBackend
        return MockBackend(p_correct=cfg.mock_p_correct, seed=cfg.seed)
    if cfg.backend == "hf":
        from .hf import HFBackend
        b = HFBackend(cfg.model, enable_thinking=cfg.enable_thinking)
        if cfg.reader_adapter:
            from ..train_reader import load_adapter
            b.reader_adapter = load_adapter(cfg.reader_adapter, b.device)
        if cfg.writer_head:
            from ..train_writer import load_head
            b.writer_head = load_head(cfg.writer_head, b.device, b.emb)
        return b
    raise ValueError(f"unknown backend {cfg.backend!r}")
