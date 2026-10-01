#!/usr/bin/env python3
"""Canonical Product run of the imported WP-08 mapped-run package (wp08_mapping_r56, #345).

Checks the declared import against history, builds the fixture image byte for
byte from the package's rows.py, runs the separately built public-API adapter
on a fresh device per planned case, and hands the gzip JSONL to the verifier's
own replay.py, which decides. The package's oracle.py is never imported; its
plan order is restated below from rows.py:

  row 1  side A, B x rows.crossings(side) x rows.OFFSETS x rows.RATES
  row 2  side A, B: seek rows.TOTAL, rate -1.0x, render rows.ROW2_RENDER until short

  --evidence DIR   fresh output directory (refuses to reuse one)
  --retained DIR   also require the fresh JSONL to equal the committed SHA-256
  --replay DIR     offline: verify the retained evidence and replay it, no adapter
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
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / "tests" / "wp08_mapping_r56"
BUILD = HERE / "build"
SOURCES = ("wp08m_adapter.c",)

VERIFIER_TREE = "466bf8193e53a39a4e5a51710ede9cd2b2458858"
VERIFIER_SOURCE = "5b7c3641e972bdbf080885ac01142927434487fa"
PRODUCT_BASE = "480121099e33b6caf2a9f3169f39538135d0f6c6"
IMPORT_COMMIT = "acdf004"
CASESET_SHA256 = "9eca914a4f2ed87db31bb5cd1212b89dec52731e37cdd76e1fb8aa2af8424e30"
BUILD_COMMAND = "make -C engine clean all && make -C tests/wp08_mapping_adapter clean all"
SCHEMA = "wp08-mapping-r56-observation-v1"

sys.path.insert(0, str(PACKAGE))
import rows as R  # noqa: E402  fixture builder and plan constants; not the oracle


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha(path.read_bytes())


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def check_provenance() -> None:
    if git("rev-parse", "HEAD:tests/wp08_mapping_r56") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/wp08_mapping_r56") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")


# ------------------------------------------------------------------- plan

def cases():
    idx = 0
    for side in R.SIDES:
        for b in R.crossings(side):
            for off in R.OFFSETS:
                for rate in R.RATES:
                    yield {"index": idx, "row": 1, "kind": "seek_boundary", "side": side, "crossing": b,
                           "seek": b + off, "rate": rate}
                    idx += 1
    for side in R.SIDES:
        yield {"index": idx, "row": 2, "kind": "reverse_end", "side": side}
        idx += 1


def caseset_sha256(plan: list) -> str:
    h = hashlib.sha256()
    for c in plan:
        h.update((canonical(c) + "\n").encode())
    return h.hexdigest()


# ------------------------------------------------------------------- run

def exe() -> Path:
    return BUILD / ("wp08m_adapter.exe" if os.name == "nt" else "wp08m_adapter")


def generate() -> tuple[bytes, dict]:
    plan = list(cases())
    if caseset_sha256(plan) != CASESET_SHA256:
        raise SystemExit("restated plan does not match the package's recorded case set")
    lines = []
    with tempfile.TemporaryDirectory(prefix="wp08m-") as t:
        tmp = Path(t)
        img = tmp / "fixture.img"
        img.write_bytes(R.image())
        for c in plan:
            out = tmp / f"obs{c['index']}.json"
            if c["row"] == 1:
                args = ["1", c["side"], str(c["seek"]), str(c["rate"]), str(R.ROW1_RENDER)]
            else:
                args = ["2", c["side"], str(R.TOTAL), str(-R.ONE), str(R.ROW2_RENDER)]
            # A fresh device per case: the adapter loads the image anew each run.
            subprocess.run([str(exe()), str(img), *args, str(out)], check=True)
            obs = json.loads(out.read_bytes())
            obs.update({k: v for k, v in c.items()})
            obs["schema"] = SCHEMA
            lines.append((canonical(obs) + "\n").encode())
    census = {"cases": len(lines), "row1": sum(c["row"] == 1 for c in plan),
              "row2": sum(c["row"] == 2 for c in plan)}
    census["service_calls"] = sum(sum(1 for k in json.loads(l)["calls"] if k["fn"] == "tape_service") for l in lines)
    census["read_blocks"] = sum(sum(e["count"] for k in json.loads(l)["calls"] for e in k["events"]) for l in lines)
    return b"".join(lines), census


def write_gzip(data: bytes, dst: Path) -> None:
    c = zlib.compressobj(9, zlib.DEFLATED, 31, 8, zlib.Z_FILTERED)
    dst.write_bytes(c.compress(data) + c.flush())


def run_replay(gz: Path, out: Path, product_commit: str, product_tree: str, adapter_sha: str) -> int:
    r = subprocess.run([sys.executable, "-B", str(PACKAGE / "replay.py"), str(gz), "--manifest", str(out / "manifest.json"),
                        "--adapter-kind", "product", "--adapter-source-sha", adapter_sha,
                        "--product-commit", product_commit, "--product-tree", product_tree],
                       cwd=str(PACKAGE), capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    (out / "replay.log").write_text(r.stdout + r.stderr, newline="\n")
    if r.returncode:
        tail = (r.stderr.strip().splitlines() or ["(no output)"])[-1]
        print(f"replay.py FAIL (exit {r.returncode}): {tail}")
    return r.returncode


def adapter_source_sha() -> str:
    h = hashlib.sha256()
    for name in SOURCES:
        data = (HERE / name).read_bytes()
        h.update(f"{name} {len(data)}\n".encode() + data)
    return h.hexdigest()


def fresh_dir(path: Path) -> Path:
    path = path if path.is_absolute() else ROOT / path
    if path.exists() and any(path.iterdir()):
        raise SystemExit(f"refusing to reuse non-empty evidence directory {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_sums(path: Path) -> dict:
    out = {}
    for line in path.read_text().splitlines():
        digest, name = line.split(None, 1)
        out[name.lstrip("*")] = digest
    return out


def verify_retained(retained: Path) -> Path:
    sums = read_sums(retained / "SHA256SUMS")
    gz = retained / "observations.jsonl.gz"
    if sha256_file(gz) != sums["observations.jsonl.gz"]:
        raise SystemExit("retained gzip does not match its committed SHA-256")
    if sha(gzip.decompress(gz.read_bytes())) != sums["observations.jsonl"]:
        raise SystemExit("retained JSONL does not match its committed SHA-256")
    if sha256_file(retained / "build-identity.json") != sums["build-identity.json"]:
        raise SystemExit("retained build-identity.json does not match its committed SHA-256")
    return gz


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--evidence", type=Path)
    g.add_argument("--replay", type=Path, help="retained evidence directory")
    ap.add_argument("--retained", type=Path, help="committed evidence directory (SHA256SUMS)")
    ap.add_argument("--out", type=Path, help="with --replay: fresh directory for the manifest")
    a = ap.parse_args()

    check_provenance()
    print("current engine/ tree " + git("rev-parse", "HEAD:engine"))
    head = git("rev-parse", "HEAD")
    product_commit = os.environ.get("PRODUCT_COMMIT") or head
    product_tree = git("rev-parse", product_commit + "^{tree}")

    if a.replay:
        retained = a.replay if a.replay.is_absolute() else ROOT / a.replay
        gz = verify_retained(retained)
        ident = json.loads((retained / "build-identity.json").read_text())
        out = fresh_dir(a.out or Path("build/wp08m-replay"))
        return run_replay(gz, out, product_commit, product_tree, ident["adapter_source_sha256"])

    out = fresh_dir(a.evidence)
    if not exe().is_file():
        raise SystemExit("adapter not built: " + BUILD_COMMAND)
    data, census = generate()
    print(f"assembled {census['cases']} observations: {census}")
    gz = out / "observations.jsonl.gz"
    write_gzip(data, gz)
    ident = {
        "schema": "wp08-mapping-r56-product-build-identity-1",
        "verifier_tree": VERIFIER_TREE,
        "verifier_source_commit": VERIFIER_SOURCE,
        "product_base": PRODUCT_BASE,
        "import_commit": git("rev-parse", IMPORT_COMMIT),
        "engine_tree": git("rev-parse", "HEAD:engine"),
        "caseset_sha256": CASESET_SHA256,
        "adapter_source_sha256": adapter_source_sha(),
        "sources_sha256": {n: sha256_file(HERE / n) for n in SOURCES},
        "makefile_sha256": sha256_file(HERE / "Makefile"),
        "run_product_sha256": sha256_file(Path(__file__)),
        "build_command": BUILD_COMMAND,
        "census": census,
    }
    (out / "build-identity.json").write_text(json.dumps(ident, indent=2, sort_keys=True) + "\n", newline="\n")
    sums = {"observations.jsonl": sha(data), "observations.jsonl.gz": sha256_file(gz),
            "build-identity.json": sha256_file(out / "build-identity.json")}
    (out / "SHA256SUMS").write_text("".join(f"{v}  {k}\n" for k, v in sums.items()), newline="\n")
    cc = subprocess.run([os.environ.get("CC", "cc"), "--version"], capture_output=True, text=True)
    (out / "host.json").write_text(json.dumps({
        "product_commit": product_commit, "product_tree": product_tree, "head": head,
        "cc": (cc.stdout.splitlines() or ["unknown"])[0], "platform": platform.platform(),
        "python": platform.python_version(),
    }, indent=2, sort_keys=True) + "\n", newline="\n")
    print(f"observations.jsonl {len(data)} bytes {sums['observations.jsonl']}; gzip {gz.stat().st_size} bytes "
          f"{sums['observations.jsonl.gz']}")

    if a.retained:
        retained = a.retained if a.retained.is_absolute() else ROOT / a.retained
        want = read_sums(retained / "SHA256SUMS")
        if want["observations.jsonl"] != sums["observations.jsonl"]:
            raise SystemExit("regenerated JSONL differs from the committed SHA-256")
        print("regenerated JSONL is byte-identical to the committed SHA-256")

    return run_replay(gz, out, product_commit, product_tree, ident["adapter_source_sha256"])


if __name__ == "__main__":
    raise SystemExit(main())
