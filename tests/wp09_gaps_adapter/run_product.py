#!/usr/bin/env python3
"""Canonical Product run of the imported #130 package (wp09_gaps_r56, #345).

Checks the declared import against history and hands the gzip JSONL to the
verifier's own replay.py, which decides. The package's oracle.py is never
imported; its plan order is restated below from rows.py:

  row 1  rows.POSITIONS (start, middle, straddle_end): the separately built
         public-API adapter overdubs rows.input_frames(at) onto a fresh copy of
         rows.overdub_image(), then remounts and renders Side B.
  row 2  rows.FIXTURES: no engine run. Each case wraps, unchanged, the #118
         row-3 record of that fixture from the accepted #336 bundle
         (tests/wp10_final_adapter/evidence/p1-r55-product). Its release asset is
         fetched into memory, never into the pinned bundle, and refused unless it
         hashes to that bundle's committed SHA256SUMS.

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
PACKAGE = ROOT / "tests" / "wp09_gaps_r56"
W10_BUNDLE = ROOT / "tests" / "wp10_final_adapter" / "evidence" / "p1-r55-product"
W10_ASSET = "wp10-final-r54-product-observations.jsonl.gz"
W10_URL = ("https://github.com/mmsanders/Digital-Tape/releases/download/evidence-p1-r55-wp10-final/"
           + W10_ASSET)
BUILD = HERE / "build"
SOURCES = ("wp09g_adapter.c",)

VERIFIER_TREE = "d8d6d6f8a9df02cb6125b73bedbde422afe5d909"
VERIFIER_SOURCE = "508ada857a5badf376da4428e87791333f1f0657"
PRODUCT_BASE = "480121099e33b6caf2a9f3169f39538135d0f6c6"
IMPORT_COMMIT = "acdf004"
CASESET_SHA256 = "5b14062694cfc1ef219612d8086bac56e0a1536680c129537548b687cfbc5fe0"
BUILD_COMMAND = "make -C engine clean all && make -C tests/wp09_gaps_adapter clean all"
SCHEMA = "wp09-gaps-r56-observation-v1"

sys.path.insert(0, str(PACKAGE))
import rows as R  # noqa: E402  fixture builder and plan constants; not the oracle
import urllib.request  # noqa: E402


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
    if git("rev-parse", "HEAD:tests/wp09_gaps_r56") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/wp09_gaps_r56") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")


# ------------------------------------------------------------------- plan

def cases():
    idx = 0
    for pos in R.POSITIONS:
        yield {"index": idx, "row": 1, "kind": "overdub_saturation", "position": pos}
        idx += 1
    for fid in R.FIXTURES:
        yield {"index": idx, "row": 2, "kind": "respool_floor", "fixture": fid}
        idx += 1


def caseset_sha256(plan: list) -> str:
    h = hashlib.sha256()
    for c in plan:
        h.update((canonical(c) + "\n").encode())
    return h.hexdigest()


# ------------------------------------------------------------------- run

def exe() -> Path:
    return BUILD / ("wp09g_adapter.exe" if os.name == "nt" else "wp09g_adapter")


def wp10_row3_records() -> dict:
    """The accepted #336 row-3 records, by fixture, read from its release asset
    after checking the asset and its JSONL against the bundle's SHA256SUMS."""
    sums = read_sums(W10_BUNDLE / "SHA256SUMS")
    local = W10_BUNDLE / W10_ASSET
    if local.exists():
        data = local.read_bytes()
    else:
        print(f"fetch {W10_URL}")
        with urllib.request.urlopen(W10_URL) as r:
            data = r.read()
    if sha(data) != sums[W10_ASSET]:
        raise SystemExit("REFUSED: the #336 release asset does not hash to its committed SHA-256")
    raw = gzip.decompress(data)
    if sha(raw) != sums["observations.jsonl"]:
        raise SystemExit("REFUSED: the #336 JSONL does not hash to its committed SHA-256")
    out = {}
    for line in raw.splitlines():
        if b'"row":3,' in line:
            rec = json.loads(line)
            if rec.get("row") == 3:
                out[rec["fixture"]] = rec
    return out


def generate() -> tuple[bytes, dict]:
    plan = list(cases())
    if caseset_sha256(plan) != CASESET_SHA256:
        raise SystemExit("restated plan does not match the package's recorded case set")
    records = wp10_row3_records()
    lines = []
    with tempfile.TemporaryDirectory(prefix="wp09g-") as t:
        tmp = Path(t)
        for c in plan:
            if c["row"] == 1:
                at = R.POSITIONS[c["position"]]
                img = tmp / f"overdub{c['index']}.img"     # a fresh device image per case
                img.write_bytes(R.overdub_image())
                out = tmp / f"obs{c['index']}.json"
                subprocess.run([str(exe()), str(img), str(at), R.pcm(R.input_frames(at)).hex(), str(out)],
                               check=True)
                obs = json.loads(out.read_bytes())
            else:
                obs = {"wp10_final_record": records[c["fixture"]]}
            obs.update(c)
            obs["schema"] = SCHEMA
            lines.append((canonical(obs) + "\n").encode())
    census = {"cases": len(lines), "row1": sum(c["row"] == 1 for c in plan),
              "row2": sum(c["row"] == 2 for c in plan),
              "wp10_final_bundle_jsonl": read_sums(W10_BUNDLE / "SHA256SUMS")["observations.jsonl"]}
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
        out = fresh_dir(a.out or Path("build/wp09g-replay"))
        return run_replay(gz, out, product_commit, product_tree, ident["adapter_source_sha256"])

    out = fresh_dir(a.evidence)
    if not exe().is_file():
        raise SystemExit("adapter not built: " + BUILD_COMMAND)
    data, census = generate()
    print(f"assembled {census['cases']} observations: {census}")
    gz = out / "observations.jsonl.gz"
    write_gzip(data, gz)
    ident = {
        "schema": "wp09-gaps-r56-product-build-identity-1",
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
