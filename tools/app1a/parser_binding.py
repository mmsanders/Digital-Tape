#!/usr/bin/env python3
"""#457: run Verification's APP-1A parser package (tests/wp15_app1a_r1, imported
verbatim) through the app's actual parser and message selection.

The package's own `cases.corpus()` and `parser_runner.compare` decide; this wrapper
only adapts the invocation (ADAPTER.md permits that, not the verdict). The app reads
ingest reports only, because cards/make reports belong to S2/S3, which this build lacks. So
the ingest rows are run and every cards/make row is listed as UNEXECUTED, never passed.

Records the raw stdin/stdout bytes, the adapter source hash and the build command.

  parser_binding.py --adapter BIN --adapter-source FILE --build-command STR --out DIR
"""
import argparse, hashlib, json, subprocess, sys
from collections import Counter
from pathlib import Path

PKG = Path(__file__).resolve().parents[2] / "tests" / "wp15_app1a_r1"
sys.path.insert(0, str(PKG))
import cases  # noqa: E402  (the package's corpus, unchanged)
import parser_runner  # noqa: E402  (the package's comparison, unchanged)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--adapter-source", required=True)
    ap.add_argument("--build-command", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = cases.corpus()
    ingest = [c for c in rows if c["tool"] == "ingest"]
    unexecuted = [c["name"] for c in rows if c["tool"] != "ingest"]
    stdin = "".join(json.dumps(c) + "\n" for c in ingest).encode()
    p = subprocess.run([a.adapter], input=stdin, capture_output=True, check=True)
    (out / "adapter-stdin.jsonl").write_bytes(stdin)
    (out / "adapter-stdout.jsonl").write_bytes(p.stdout)
    got = [json.loads(s) for s in p.stdout.decode().splitlines()]
    mismatches = [{"name": c["name"], "expected": {"valid": c["valid"], "message": c["message"]}, "actual": r}
                  for c, r in zip(ingest, got) if r != {"valid": c["valid"], "message": c["message"]}]
    verdict = "PASS"
    try:
        parser_runner.compare(ingest, got)
    except AssertionError as e:
        verdict = f"FAIL ({e})"
    rec = {
        "package_tree": "bdd861b693516db2e5244660b3e99ee400d506de",
        "corpus_rows": len(rows), "ingest_rows_run": len(ingest),
        "unexecuted_rows": len(unexecuted), "unexecuted_reason": "tapectl cards/make reports are read by S2/S3, not built",
        "unexecuted_by_tool": dict(Counter(c["tool"] for c in rows if c["tool"] != "ingest")),
        "compare": verdict, "mismatches": mismatches,
        "adapter_sha256": sha(Path(a.adapter).read_bytes()),
        "adapter_source_sha256": sha(Path(a.adapter_source).read_bytes()),
        "build_command": a.build_command,
        "stdin_sha256": sha(stdin), "stdout_sha256": sha(p.stdout),
    }
    (out / "parser-binding.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "mismatches"}, indent=1))
    for m in mismatches[:20]:
        print("MISMATCH", json.dumps(m))
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
