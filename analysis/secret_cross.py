"""SecretBench forum runs: consumer pass rate, split by who wrote the producer `encode`.

    python -m analysis.secret_cross runs/e0s3_<id>/text/*/ runs/e0s3_<id>/latent/*/

Only consumers whose `encode` was written by another agent measure the channel. When the same
agent wrote both, it already knows the format (with `--memory true`) or has forgotten it.
"""
import collections
import json
import sys

CONSUMERS = ("decode", "is_record", "get_field")


def main():
    for d in sys.argv[1:]:
        c = collections.Counter()
        for line in open(d.rstrip("/") + "/projects.jsonl"):
            methods = json.loads(line)["methods"]
            producer = methods["encode"].get("author")
            for m in CONSUMERS:
                v = methods[m]
                k = "cross" if v.get("author") != producer else "self"
                ok = bool(v["iso_ok"])
                c[k] += 1
                c[k + "_ok"] += ok
                c[f"{m}_{k}"] += 1
                c[f"{m}_{k}_ok"] += ok
        rate = lambda k: f"{c[k + '_ok'] / c[k]:.3f} ({c[k + '_ok']}/{c[k]})" if c[k] else "-"
        per = " ".join(f"{m} {rate(m + '_cross')}" for m in CONSUMERS)
        print(f"{d.rstrip('/').split('/')[-1]:45s} cross={rate('cross')} self={rate('self')} | {per}")


if __name__ == "__main__":
    main()
