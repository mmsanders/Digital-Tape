#!/usr/bin/env python3
"""Canonical Product run of the imported WP-06 R44 sequential verifier package.

Checks the declared import against history, runs the separately built public-API
adapter once per canonical case, retains the unabridged JSONL (plus a
deterministic gzip of it), and hands it to the verifier's own runner.py, which
binds oracle, plan, input digest, Product commit/tree and adapter source in a
non-overwriting manifest. Nothing here decides a case: runner.py does.

  --evidence DIR   fresh output directory (refuses to reuse one)
  --retained DIR   also require the fresh JSONL to equal the committed evidence
  --replay DIR     offline: verify committed evidence and replay it, no adapter
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / "tests" / "sequential_wp06_r44"
ADAPTER_SRC = HERE / "wp06_adapter.c"
ADAPTER_BIN = HERE / "build" / "wp06_adapter"
ENGINE_LIB = ROOT / "build" / "engine" / "libtape.a"

VERIFIER_TREE = "21d4507149d6b565242df2120148b95eadcadd2f"
VERIFIER_SOURCE = "db2a56901d44defa753d8a715c639be232838215"
PRODUCT_BASE = "2890ea1eeaa94d53630cf64ca49e5f86afef2965"
IMPORT_COMMIT = "1ae9297"
ENGINE_TREE = "054d27ab6e3e72f61118ff7d99e19e48741d05b2"
BUILD_COMMAND = "make -C engine clean all && make -C tests/sequential_wp06_adapter clean all"

sys.path.insert(0, str(PACKAGE))
from oracle import cases, digest_plan  # noqa: E402


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_provenance() -> None:
    if git("rev-parse", "HEAD:tests/sequential_wp06_r44") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/sequential_wp06_r44") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")
    if git("rev-parse", "HEAD:engine") != ENGINE_TREE:
        raise SystemExit("engine tree at HEAD is not the issued " + ENGINE_TREE)


def write_gzip(src: Path, dst: Path) -> None:
    # mtime=0 and no file name: the same JSONL always gives the same header.
    with dst.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                                              compresslevel=9, mtime=0) as gz:
        gz.write(src.read_bytes())


def commit_census(jsonl: Path) -> dict:
    """Derived, not a verdict: commit-step write callbacks versus blocks written."""
    out = {}
    for line in jsonl.read_text().splitlines():
        obs = json.loads(line)
        if not obs["case"].startswith("roundtrip-"):
            continue
        ws = [e for e in obs["events"] if e["step"] == "commit" and e["op"] == "write"]
        out[obs["case"]] = {
            "write_callbacks": len(ws),
            "blocks_written": sum(e["count"] for e in ws),
            "writes": [{"lba": e["lba"], "count": e["count"]} for e in ws],
            "flush_callbacks": sum(1 for e in obs["events"] if e["step"] == "commit" and e["op"] == "flush"),
        }
    return out


def run_runner(jsonl: Path, manifest: Path, product_commit: str, product_tree: str, adapter_sha: str) -> int:
    return subprocess.run([sys.executable, str(PACKAGE / "runner.py"), str(jsonl),
                           "--manifest", str(manifest), "--adapter-kind", "product",
                           "--adapter-source-sha", adapter_sha,
                           "--product-commit", product_commit,
                           "--product-tree", product_tree], cwd=str(PACKAGE)).returncode


def fresh_dir(path: Path) -> Path:
    path = path if path.is_absolute() else ROOT / path
    if path.exists() and any(path.iterdir()):
        raise SystemExit(f"refusing to reuse non-empty evidence directory {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_sums(retained: Path) -> dict:
    sums = {}
    for line in (retained / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(None, 1)
        sums[name.lstrip("*")] = digest
    return sums


def verify_retained(retained: Path) -> bytes:
    sums = read_sums(retained)
    gz = retained / "observations.jsonl.gz"
    if sha256_file(gz) != sums["observations.jsonl.gz"]:
        raise SystemExit("retained gzip does not match its committed SHA-256")
    data = gzip.decompress(gz.read_bytes())
    if hashlib.sha256(data).hexdigest() != sums["observations.jsonl"]:
        raise SystemExit("retained JSONL does not match its committed SHA-256")
    for name in ("build-identity.json", "commit-census.json"):
        if sha256_file(retained / name) != sums[name]:
            raise SystemExit(f"retained {name} does not match its committed SHA-256")
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--evidence", type=Path)
    g.add_argument("--replay", type=Path, help="retained evidence directory")
    ap.add_argument("--retained", type=Path)
    ap.add_argument("--out", type=Path, help="with --replay: fresh directory for the manifest")
    a = ap.parse_args()

    check_provenance()
    head = git("rev-parse", "HEAD")
    product_commit = os.environ.get("PRODUCT_COMMIT") or head
    product_tree = git("rev-parse", product_commit + "^{tree}")
    adapter_sha = sha256_file(ADAPTER_SRC)

    if a.replay:
        retained = a.replay if a.replay.is_absolute() else ROOT / a.replay
        data = verify_retained(retained)
        ident = json.loads((retained / "build-identity.json").read_text())
        out = fresh_dir(a.out or Path("build/wp06-replay"))
        jsonl = out / "observations.jsonl"
        jsonl.write_bytes(data)
        # Bind the replay to the source that produced the retained bytes.
        rc = run_runner(jsonl, out / "manifest.json", product_commit, product_tree,
                        ident["adapter_source_sha256"])
        print(f"replayed retained evidence {read_sums(retained)['observations.jsonl']}")
        return rc

    out = fresh_dir(a.evidence)
    if not ADAPTER_BIN.is_file():
        raise SystemExit("adapter not built: " + BUILD_COMMAND)
    jsonl = out / "observations.jsonl"
    with jsonl.open("wb") as f:
        subprocess.run([str(ADAPTER_BIN)], check=True, stdout=f)
    ids = [json.loads(line)["case"] for line in jsonl.read_text().splitlines()]
    expected = [c.id for c in cases()]
    print(f"adapter emitted {len(ids)} cases; package has {len(expected)}")

    write_gzip(jsonl, out / "observations.jsonl.gz")
    ident = {
        "schema": "wp06-r44-product-build-identity-1",
        "verifier_tree": VERIFIER_TREE,
        "verifier_source_commit": VERIFIER_SOURCE,
        "product_base": PRODUCT_BASE,
        "import_commit": git("rev-parse", IMPORT_COMMIT),
        "engine_tree": git("rev-parse", "HEAD:engine"),
        "adapter_source_sha256": adapter_sha,
        "makefile_sha256": sha256_file(HERE / "Makefile"),
        "run_product_sha256": sha256_file(Path(__file__)),
        "build_command": BUILD_COMMAND,
        "run_command": "tests/sequential_wp06_adapter/build/wp06_adapter > observations.jsonl",
        "plan_sha256": digest_plan(),
        "case_count": len(expected),
        "fixture_sha256": {json.loads(line)["case"]: json.loads(line)["fixture_sha256"]
                           for line in jsonl.read_text().splitlines()},
    }
    (out / "build-identity.json").write_text(json.dumps(ident, indent=2, sort_keys=True) + "\n")
    (out / "commit-census.json").write_text(json.dumps(commit_census(jsonl), indent=2, sort_keys=True) + "\n")
    names = ("observations.jsonl", "observations.jsonl.gz", "build-identity.json", "commit-census.json")
    (out / "SHA256SUMS").write_text("".join(f"{sha256_file(out / n)}  {n}\n" for n in names))

    # Host facts: not part of the retained identity, since they differ by runner.
    (out / "host.json").write_text(json.dumps({
        "product_commit": product_commit, "product_tree": product_tree, "head": head,
        "cc": subprocess.run(["cc", "--version"], capture_output=True, text=True).stdout.splitlines()[0],
        "python": platform.python_version(),
        "engine_archive_sha256": sha256_file(ENGINE_LIB),
        "adapter_binary_sha256": sha256_file(ADAPTER_BIN),
    }, indent=2, sort_keys=True) + "\n")

    if a.retained:
        retained = a.retained if a.retained.is_absolute() else ROOT / a.retained
        data = verify_retained(retained)
        if data != jsonl.read_bytes():
            raise SystemExit("regenerated JSONL differs from the committed retained evidence")
        print("regenerated JSONL is byte-identical to the retained evidence")

    return run_runner(jsonl, out / "manifest.json", product_commit, product_tree, adapter_sha)


if __name__ == "__main__":
    raise SystemExit(main())
