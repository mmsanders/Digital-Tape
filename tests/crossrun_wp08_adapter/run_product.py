#!/usr/bin/env python3
"""Canonical Product run of the imported WP-08 R44 cross-run verifier package.

Checks the declared import against history, runs the separately built
public-API adapter once for all 33 canonical cases, retains the unabridged
JSONL, the raw fixture image and the build identity, and hands the JSONL to the
verifier's own replay.py, which binds oracle, plan, evidence, Product
commit/tree and adapter source in a non-overwriting manifest. Nothing here
decides a case: replay.py does.

  --evidence DIR   fresh output directory (refuses to reuse one)
  --retained DIR   also require the fresh JSONL and fixture to equal the committed ones
  --replay DIR     offline: verify committed evidence and replay it, no adapter
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / "tests" / "crossrun_wp08_r44"
ADAPTER_SRC = HERE / "wp08_adapter.c"
ADAPTER_BIN = HERE / "build" / "wp08_adapter"
ENGINE_LIB = ROOT / "build" / "engine" / "libtape.a"

VERIFIER_TREE = "9ed67a8594476822ba5ee35e07a1bf048e23100e"
VERIFIER_SOURCE = "58ca7599157d1da7c13794fb0f0859feb2210374"
PRODUCT_BASE = "2890ea1eeaa94d53630cf64ca49e5f86afef2965"
IMPORT_COMMIT = "2928853"
# The engine this binding was independently accepted on. The retained evidence must
# keep naming it; the current engine/ is checked by byte-identical regeneration
# (--retained), not by pinning HEAD to it (PM ruling, #320).
ACCEPTED_ENGINE_TREE = "054d27ab6e3e72f61118ff7d99e19e48741d05b2"
BUILD_COMMAND = "make -C engine clean all && make -C tests/crossrun_wp08_adapter clean all"
RETAINED = ("observations.jsonl", "fixture.json", "build-identity.json")

sys.path.insert(0, str(PACKAGE))
from oracle import cases, digest_plan  # noqa: E402


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_provenance() -> None:
    if git("rev-parse", "HEAD:tests/crossrun_wp08_r44") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/crossrun_wp08_r44") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")


def run_replay(jsonl: Path, manifest: Path, product_commit: str, product_tree: str, adapter_sha: str) -> int:
    return subprocess.run([sys.executable, "-B", str(PACKAGE / "replay.py"), str(jsonl),
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


def verify_retained(retained: Path) -> None:
    sums = {}
    for line in (retained / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(None, 1)
        sums[name.lstrip("*")] = digest
    for name in RETAINED:
        if sha256_file(retained / name) != sums[name]:
            raise SystemExit(f"retained {name} does not match its committed SHA-256")


def check_accepted_engine(retained: Path) -> None:
    """Ruling (a): the retained evidence still records the engine it was accepted on."""
    named = json.loads((retained / "build-identity.json").read_text())["engine_tree"]
    if named != ACCEPTED_ENGINE_TREE:
        raise SystemExit(f"retained provenance names engine {named}, not the accepted "
                         f"{ACCEPTED_ENGINE_TREE}")


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--evidence", type=Path)
    g.add_argument("--replay", type=Path, help="retained evidence directory")
    ap.add_argument("--retained", type=Path)
    ap.add_argument("--out", type=Path, help="with --replay: fresh directory for the manifest")
    a = ap.parse_args()

    check_provenance()
    print("current engine/ tree " + git("rev-parse", "HEAD:engine"))
    head = git("rev-parse", "HEAD")
    product_commit = os.environ.get("PRODUCT_COMMIT") or head
    product_tree = git("rev-parse", product_commit + "^{tree}")

    if a.replay:
        retained = a.replay if a.replay.is_absolute() else ROOT / a.replay
        verify_retained(retained)
        check_accepted_engine(retained)
        ident = json.loads((retained / "build-identity.json").read_text())
        out = fresh_dir(a.out or Path("build/wp08-replay"))
        # Bind the replay to the source that produced the retained bytes.
        rc = run_replay(retained / "observations.jsonl", out / "manifest.json", product_commit,
                        product_tree, ident["adapter_source_sha256"])
        print(f"replayed retained evidence {sha256_file(retained / 'observations.jsonl')}")
        return rc

    out = fresh_dir(a.evidence)
    if not ADAPTER_BIN.is_file():
        raise SystemExit("adapter not built: " + BUILD_COMMAND)
    jsonl = out / "observations.jsonl"
    with jsonl.open("wb") as f:
        subprocess.run([str(ADAPTER_BIN)], check=True, stdout=f)
    with (out / "fixture.json").open("wb") as f:
        subprocess.run([str(ADAPTER_BIN), "--fixture"], check=True, stdout=f)
    ids = [json.loads(line)["case"] for line in jsonl.read_text().splitlines()]
    print(f"adapter emitted {len(ids)} cases; package has {len(cases())}")

    ident = {
        "schema": "wp08-r44-product-build-identity-1",
        "verifier_tree": VERIFIER_TREE,
        "verifier_source_commit": VERIFIER_SOURCE,
        "product_base": PRODUCT_BASE,
        "import_commit": git("rev-parse", IMPORT_COMMIT),
        "engine_tree": git("rev-parse", "HEAD:engine"),
        "adapter_source_sha256": sha256_file(ADAPTER_SRC),
        "makefile_sha256": sha256_file(HERE / "Makefile"),
        "run_product_sha256": sha256_file(Path(__file__)),
        "build_command": BUILD_COMMAND,
        "run_command": "tests/crossrun_wp08_adapter/build/wp08_adapter > observations.jsonl; "
                       "tests/crossrun_wp08_adapter/build/wp08_adapter --fixture > fixture.json",
        "fixture_sha256": sha256_file(out / "fixture.json"),
        "plan_sha256": digest_plan(),
        "case_count": len(cases()),
    }
    (out / "build-identity.json").write_text(json.dumps(ident, indent=2, sort_keys=True) + "\n")
    (out / "SHA256SUMS").write_text("".join(f"{sha256_file(out / n)}  {n}\n" for n in RETAINED))

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
        verify_retained(retained)
        check_accepted_engine(retained)
        for name in ("observations.jsonl", "fixture.json"):
            if (retained / name).read_bytes() != (out / name).read_bytes():
                raise SystemExit(f"regenerated {name} differs from the committed retained evidence")
        print("regenerated JSONL and fixture are byte-identical to the retained evidence")

    return run_replay(jsonl, out / "manifest.json", product_commit, product_tree, ident["adapter_source_sha256"])


if __name__ == "__main__":
    raise SystemExit(main())
