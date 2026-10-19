"""Backends and writers. The api backend is tested against a local fake server (no network, no key);
the hf backend against a tiny randomly initialized model built in memory (skipped without torch)."""
import http.server
import json
import os
import tempfile
import threading
import unittest

from benchmark.tasks import toy_projects
from forum.config import RunConfig
from forum.run import run_condition
from model.backends.api import APIBackend
from model.backends.base import LATENT_MARK, Latent
from model.writers import MockWriter, make_writer

try:
    import torch
    import transformers  # noqa: F401
except ImportError:
    torch = None


class _FakeAPI(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.seen.append((self.headers.get("Authorization"), body))
        reply = {"choices": [{"message": {"content": "<think>hidden</think>STATUS: DONE\nok"}}],
                 "usage": {"prompt_tokens": 7, "completion_tokens": 3}}
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class TestAPIBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FakeAPI)
        cls.server.seen = []
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/v1"
        os.environ["LF_TEST_KEY"] = "sk-test"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_chat_sends_key_model_and_extra_fields(self):
        b = APIBackend("qwen3-8b", self.url, "LF_TEST_KEY", {"enable_thinking": False})
        g = b.chat([{"role": "user", "content": "hi"}], max_new_tokens=5)
        self.assertEqual(g.text, "STATUS: DONE\nok")   # a leading think block is dropped
        self.assertEqual((g.prompt_tokens, g.gen_tokens), (7, 3))
        auth, body = self.server.seen[-1]
        self.assertEqual(auth, "Bearer sk-test")
        self.assertEqual((body["model"], body["max_tokens"], body["enable_thinking"]), ("qwen3-8b", 5, False))

    def test_text_only(self):
        b = APIBackend("m", self.url, "LF_TEST_KEY")
        with self.assertRaises(ValueError):
            b.chat([{"role": "user", "content": LATENT_MARK.format(i=0)}], [Latent({}, 1)])
        with self.assertRaises(ValueError):
            make_writer(b)

    def test_forum_runs_on_the_api(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = RunConfig(backend="api", channel="text", rounds=1, out=d).validate()
            s = run_condition(cfg, APIBackend("m", self.url, "LF_TEST_KEY"), toy_projects())
            self.assertGreater(s["calls"], 0)
            with open(os.path.join(d, cfg.tag(), "config.json")) as f:
                self.assertNotIn("sk-test", f.read())   # the key itself is never saved


class TestMockWriter(unittest.TestCase):
    def test_record(self):
        lat = MockWriter(8).write([], "STATUS: DONE\nx", meta={"anchor": "add", "visible_ok": False})
        self.assertEqual(lat.data, {"anchor": "add", "visible_ok": False, "claimed": "DONE"})
        self.assertEqual(lat.blank().data, {})


def tiny_backend():
    """A 2-layer Qwen3 with a 400-token byte-level BPE vocabulary and a ChatML template."""
    from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers
    from transformers import PreTrainedTokenizerFast, Qwen3Config, Qwen3ForCausalLM
    from model.backends.hf import HFBackend
    specials = ["<|endoftext|>", "<|im_start|>", "<|im_end|>", "<think>", "</think>"]
    bpe = Tokenizer(models.BPE())
    bpe.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    bpe.decoder = decoders.ByteLevel()
    bpe.train_from_iterator(["def encode(self): return STATUS DONE message from agent"] * 20,
                            trainers.BpeTrainer(vocab_size=400, special_tokens=specials,
                                                initial_alphabet=pre_tokenizers.ByteLevel.alphabet()))
    tok = PreTrainedTokenizerFast(tokenizer_object=bpe, eos_token="<|im_end|>", pad_token="<|endoftext|>")
    tok.chat_template = ("{% for m in messages %}<|im_start|>{{ m['role'] }}\n{{ m['content'] }}<|im_end|>\n{% endfor %}"
                         "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}")
    torch.manual_seed(0)
    cfg = Qwen3Config(vocab_size=len(tok), hidden_size=64, intermediate_size=128, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, head_dim=16, max_position_embeddings=1024,
                      tie_word_embeddings=False)
    return HFBackend(Qwen3ForCausalLM(cfg).float(), tok)


@unittest.skipIf(torch is None, "needs torch and transformers")
class TestHFBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = tiny_backend()
        cls.msgs = [{"role": "system", "content": "You are agent0."}, {"role": "user", "content": "Report on encode."}]

    def test_latents_are_spliced_in(self):
        from model.hf_writers import GistWriter, random_head
        w = GistWriter(self.b, random_head(self.b.emb, 4))
        lat = w.write(self.msgs, "STATUS: DONE\nencode works")
        self.assertEqual(tuple(lat.data.shape), (4, 64))
        g = self.b.chat([{"role": "user", "content": "x " + LATENT_MARK.format(i=0)}], [lat], max_new_tokens=2)
        bare = self.b.render([{"role": "user", "content": "x "}])   # the mark sits right before <|im_end|>
        self.assertEqual(g.prompt_tokens, self.b.count_tokens(bare) + 4)

    def test_input_space_avoids_control_tokens(self):
        e = self.b.to_input_space(torch.randn(5, 64))
        self.assertLess((e @ self.b.ctrl_basis.float()).abs().max().item(), 1e-3)
        self.assertTrue(torch.allclose(e.norm(dim=-1), torch.full((5,), self.b.target_norm), rtol=1e-3))

    def test_chunk_mean_and_random_head_spec(self):
        from model.hf_writers import ChunkMeanWriter, load_head
        lat = ChunkMeanWriter(self.b, 3).write(self.msgs, "STATUS: DONE\nencode works fine")
        self.assertEqual(lat.data.shape[0], 3)
        self.assertEqual(load_head("random:6:1", self.b).k, 6)

    def test_kv_posts(self):
        from model.kv_posts import KVWriter, chat_after
        report = "STATUS: DONE\nencode works"
        full = KVWriter(self.b).write(self.msgs, report)
        self.assertEqual(full.k, full.end)
        snap = KVWriter(self.b, "snap", 8).write(self.msgs, report)
        self.assertEqual((snap.k, snap.end, tuple(snap.layers[0][0].shape[1:])), (8, full.end, (2, 8, 16)))
        recent = KVWriter(self.b, "recent", 8).write(self.msgs, report)
        self.assertTrue(torch.equal(recent.layers[1][1][:, :, 4:], full.layers[1][1][:, :, -4:]))
        self.assertTrue(torch.equal(recent.layers[1][1][:, :, :4], full.layers[1][1][:, :, :4]))   # the sinks
        self.assertEqual(KVWriter(self.b, "uniform", 8).write(self.msgs, report).k, 8)
        # the whole cache as a prefix is the author's context itself: greedy replies match
        reader = [{"role": "user", "content": "Go on."}]
        g = chat_after(self.b, full, reader, max_new_tokens=4, temperature=0)
        author = self.b.render(self.msgs + [{"role": "assistant", "content": report}], add_generation_prompt=False)
        ids = torch.cat([self.b.tok(t, add_special_tokens=False, return_tensors="pt").input_ids
                         for t in (author, self.b.render(reader))], 1).to(self.b.device)
        out = self.b.model.generate(input_ids=ids, attention_mask=torch.ones_like(ids), do_sample=False,
                                    max_new_tokens=4, eos_token_id=None, pad_token_id=0)
        self.assertEqual(g.text, self.b.tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True).strip())

    def test_kv_concat_shifts_positions(self):
        from model.kv_posts import KVWriter, _layer_kv, concat
        report = "STATUS: DONE\nencode works"
        post = KVWriter(self.b).write(self.msgs, report)
        two, n = concat(self.b, [post, post]), post.end
        self.assertEqual((two.k, two.end), (2 * n, 2 * n))
        # the second copy is the same context computed n positions later
        author = self.b.render(self.msgs + [{"role": "assistant", "content": report}], add_generation_prompt=False)
        ids = self.b.tok(author, add_special_tokens=False, return_tensors="pt").input_ids.to(self.b.device)
        out = self.b.model.model(input_ids=ids, position_ids=torch.arange(n, 2 * n, device=self.b.device)[None],
                                 use_cache=True)
        k, v = _layer_kv(out.past_key_values, 1)
        self.assertTrue(torch.allclose(two.layers[1][0][:, :, n:].cpu(), k.cpu(), atol=1e-4))
        self.assertTrue(torch.allclose(two.layers[1][1][:, :, n:].cpu(), v.cpu(), atol=1e-4))
        c = post.shared
        self.assertGreater(c, 0)
        par = concat(self.b, [post, post], "parallel", dedup=True)
        self.assertEqual((par.k, par.end), (2 * n - c, n))
        self.assertTrue(torch.equal(par.layers[1][0][:, :, n:].cpu(), post.layers[1][0][:, :, c:]))
        seq = concat(self.b, [post, post], dedup=True)
        self.assertEqual((seq.k, seq.end), (2 * n - c, 2 * n - c))

    def test_kv_stream(self):
        from model.kv_posts import _layer_kv
        from model.writers import make_stream
        s = make_stream(self.b)
        a = s.append(self.msgs, "STATUS: DONE\nfirst")
        b = s.append(self.msgs, "STATUS: PARTIAL\nsecond")
        both = s.prefix([b, a])
        self.assertEqual((both.k, both.end), (a.k + b.k, a.k + b.k))
        # the stream is the two sessions encoded together
        texts = [self.b.render(self.msgs + [{"role": "assistant", "content": r}], add_generation_prompt=False)
                 for r in ("STATUS: DONE\nfirst", "STATUS: PARTIAL\nsecond")]
        ids = torch.cat([self.b.tok(t, add_special_tokens=False, return_tensors="pt").input_ids for t in texts],
                        1).to(self.b.device)
        k, v = _layer_kv(self.b.model.model(input_ids=ids, use_cache=True).past_key_values, 1)
        self.assertTrue(torch.allclose(both.layers[1][0].cpu(), k.cpu(), atol=1e-4))
        only_b = s.prefix([b])
        self.assertEqual((only_b.k, only_b.end), (b.k, a.k + b.k))
        self.assertTrue(torch.equal(only_b.layers[1][1], both.layers[1][1][:, :, a.k:]))
        g = s.chat(only_b, [{"role": "user", "content": "Go on."}], max_new_tokens=3)
        self.assertGreaterEqual(g.gen_tokens, 0)

    def test_kv_assemble_captions(self):
        from model.kv_posts import KVWriter, _layer_kv, assemble
        report, cap = "STATUS: DONE\nencode works", "[post 0] from agent1 on `encode`\n"
        post = KVWriter(self.b).write(self.msgs, report)
        both = assemble(self.b, [post, post], [cap, cap])
        m = self.b.count_tokens(cap)
        self.assertEqual((both.k, both.end), (2 * (post.end + m),) * 2)
        # one post and its caption: the same as encoding the author's text and the caption together
        author = self.b.render(self.msgs + [{"role": "assistant", "content": report}], add_generation_prompt=False)
        ids = torch.cat([self.b.tok(t, add_special_tokens=False, return_tensors="pt").input_ids for t in (author, cap)],
                        1).to(self.b.device)
        k, v = _layer_kv(self.b.model.model(input_ids=ids, use_cache=True).past_key_values, 1)
        one = assemble(self.b, [post], [cap])
        self.assertEqual(one.k, ids.shape[1])
        self.assertTrue(torch.allclose(one.layers[1][1].cpu(), v.cpu(), atol=1e-4))

    def test_only_the_head_gets_gradients(self):
        from model.hf_writers import GistWriter, random_head
        from training.common import batch_loss
        head = random_head(self.b.emb, 4)
        e = GistWriter(self.b, head).gist(self.b.embed_chat(self.msgs), grad=True)
        loss = batch_loss(self.b, [("Message: " + LATENT_MARK.format(i=0), "DONE", Latent(e, 4))])
        loss.backward()
        self.assertIsNotNone(head.q.grad)
        self.assertTrue(all(p.grad is None for p in self.b.model.parameters()))


if __name__ == "__main__":
    unittest.main()
