#!/usr/bin/env python3
"""Canonical Product run of the imported WP-06 R52 closure-gap package.

Checks the declared import against history, runs the separately built
public-API adapter once per case of the package's gap_plan.json (a fresh
device each time), retains the observations, and hands them to the verifier's
own replay.py, which decides. Nothing here decides a verdict. A failing replay
is reported with its exit status, never hidden: the evidence is retained either
way so Verification can inspect the exact observations.

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
PACKAGE = ROOT / "tests" / "wp06_closure_r52"
PLAN = PACKAGE / "gap_plan.json"
ADAPTER_SRC = HERE / "wp06c_adapter.c"
ADAPTER_BIN = HERE / "build" / ("wp06c_adapter.exe" if os.name == "nt" else "wp06c_adapter")
ENGINE_LIB = ROOT / "build" / "engine" / "libtape.a"

VERIFIER_TREE = "b216baa2a9c160b2a14b3eac25567c5a260eed2f"
VERIFIER_SOURCE = "6b92e5f43de89efa71069084028376cdbc636bf4"
PRODUCT_BASE = "66c6abc69d83cff10da32a6b446690fcd0b927fb"
IMPORT_COMMIT = "051d292"
PLAN_SHA256 = "db9f826a3af4e3c7a2b01780ace2baa9bb5257aead873e484d25173b0c1b8119"
BUILD_COMMAND = "make -C engine clean all && make -C tests/wp06_closure_adapter clean all"


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_provenance() -> None:
    if git("rev-parse", "HEAD:tests/wp06_closure_r52") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/wp06_closure_r52") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")
    if sha256_file(PLAN) != PLAN_SHA256:
        raise SystemExit("gap_plan.json is not the published plan")


def observe(case_id: str) -> bytes:
    raw = subprocess.run([str(ADAPTER_BIN), case_id], check=True, capture_output=True).stdout
    return (json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":")) + "\n").encode()


def census(jsonl: Path) -> dict:
    """Observed facts per case, for reading the evidence. Not a verdict."""
    out = {}
    for line in jsonl.open("rb"):
        o = json.loads(line)
        chunk_writes = {}
        for e in o["events"]:
            if e["op"] == "write" and CHUNK_BASE <= e["lba"] < o["block_count"] - 1:
                chunk_writes.setdefault(e["step"], set()).add((e["lba"] - CHUNK_BASE) // 1024)
        out[o["case"]] = {
            "calls": [[c["step"], c["fn"], c["result"]] for c in o["calls"]],
            "writes_by_step": {s: sum(1 for e in o["events"] if e["op"] == "write" and e["step"] == s)
                               for s in dict.fromkeys(e["step"] for e in o["events"])},
            "chunks_written_by_step": {s: sorted(v) for s, v in chunk_writes.items()},
            "snapshots": sorted(o["snapshots"]),
        }
    return out


CHUNK_BASE = 2048


def write_gzip(src: Path, dst: Path) -> None:
    with dst.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                                              compresslevel=9, mtime=0) as gz:
        gz.write(src.read_bytes())


def run_replay(gz: Path, manifest: Path, product_commit: str, product_tree: str, adapter_sha: str) -> int:
    rc = subprocess.run([sys.executable, "-B", str(PACKAGE / "replay.py"), str(gz),
                         "--manifest", str(manifest), "--adapter-kind", "product",
                         "--adapter-source-sha", adapter_sha,
                         "--product-commit", product_commit,
                         "--product-tree", product_tree], cwd=str(PACKAGE)).returncode
    print(f"replay.py exit status {rc}")
    return rc


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
    for name in ("build-identity.json", "case-census.json"):
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
        verify_retained(retained)
        ident = json.loads((retained / "build-identity.json").read_text())
        out = fresh_dir(a.out or Path("build/wp06-closure-replay"))
        return run_replay(retained / "observations.jsonl.gz", out / "manifest.json",
                          product_commit, product_tree, ident["adapter_source_sha256"])

    out = fresh_dir(a.evidence)
    if not ADAPTER_BIN.is_file():
        raise SystemExit("adapter not built: " + BUILD_COMMAND)
    cases = json.loads(PLAN.read_text())["cases"]
    jsonl = out / "observations.jsonl"
    with jsonl.open("wb") as f:
        for case in cases:
            f.write(observe(case["id"]))
    print(f"adapter emitted {len(cases)} case records")

    write_gzip(jsonl, out / "observations.jsonl.gz")
    (out / "case-census.json").write_text(json.dumps(census(jsonl), indent=2, sort_keys=True) + "\n",
                                          newline="\n")
    ident = {
        "schema": "wp06-r52-product-build-identity-1",
        "verifier_tree": VERIFIER_TREE,
        "verifier_source_commit": VERIFIER_SOURCE,
        "product_base": PRODUCT_BASE,
        "import_commit": git("rev-parse", IMPORT_COMMIT),
        "engine_tree": git("rev-parse", "HEAD:engine"),
        "adapter_source_sha256": adapter_sha,
        "makefile_sha256": sha256_file(HERE / "Makefile"),
        "run_product_sha256": sha256_file(Path(__file__)),
        "build_command": BUILD_COMMAND,
        "plan_sha256": PLAN_SHA256,
        "case_count": len(cases),
        "fixtures": "raw media per gap_plan fixture on a fresh flat device per case; every "
                    "superblock field per tapefs §4, uuid ASCII WP06-R52-closure, sb_generation 10; "
                    "see README.md for each fixture's indices",
    }
    (out / "build-identity.json").write_text(json.dumps(ident, indent=2, sort_keys=True) + "\n",
                                             newline="\n")
    names = ("observations.jsonl", "observations.jsonl.gz", "build-identity.json", "case-census.json")
    (out / "SHA256SUMS").write_text("".join(f"{sha256_file(out / n)}  {n}\n" for n in names),
                                    newline="\n")

    cc = subprocess.run([os.environ.get("CC", "cc"), "--version"], capture_output=True, text=True)
    (out / "host.json").write_text(json.dumps({
        "product_commit": product_commit, "product_tree": product_tree, "head": head,
        "cc": (cc.stdout.splitlines() or ["unknown"])[0],
        "platform": platform.platform(),
        "python": platform.python_version(),
        "engine_archive_sha256": sha256_file(ENGINE_LIB),
        "adapter_binary_sha256": sha256_file(ADAPTER_BIN),
    }, indent=2, sort_keys=True) + "\n", newline="\n")

    if a.retained:
        retained = a.retained if a.retained.is_absolute() else ROOT / a.retained
        if verify_retained(retained) != jsonl.read_bytes():
            raise SystemExit("regenerated JSONL differs from the committed retained evidence")
        print("regenerated JSONL is byte-identical to the retained evidence")

    return run_replay(out / "observations.jsonl.gz", out / "manifest.json",
                      product_commit, product_tree, adapter_sha)


if __name__ == "__main__":
    raise SystemExit(main())
