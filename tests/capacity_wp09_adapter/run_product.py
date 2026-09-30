#!/usr/bin/env python3
"""Canonical Product run of the imported WP-09 R52 capacity short-accept package.

Checks the declared import against history, runs the separately built
public-API adapter once per row of the package's evidence/plan.json (a fresh
device each time), and hands the observations to the verifier's own replay.py,
which binds evidence, oracle, Product commit/tree and adapter source in a
non-overwriting manifest. Nothing here decides a verdict: replay.py does.

The only per-row inputs are the plan row plus the two quantities ADAPTER.md
tells the adapter to take from the package: the stimulus sample
(oracle.input_sample) and the prefill request split (oracle.prefill_requests).
Both are restated below from their published definitions rather than imported,
so the oracle is never loaded here.

  --evidence DIR   fresh output directory (refuses to reuse one)
  --retained DIR   also require the fresh JSONL to equal the committed evidence
  --replay DIR     offline: verify committed evidence and replay it, no adapter
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / "tests" / "capacity_wp09_r52"
PLAN = PACKAGE / "evidence" / "plan.json"
ADAPTER_SRC = HERE / "capacity_adapter.c"
ADAPTER_BIN = HERE / "build" / ("capacity_adapter.exe" if os.name == "nt" else "capacity_adapter")
ENGINE_LIB = ROOT / "build" / "engine" / "libtape.a"

VERIFIER_TREE = "85043f530c95257721347a6d991a0d205b299e4f"
VERIFIER_SOURCE = "87ae5746f6892a41d2660d5ef05c4a97b2ea8cf5"
PRODUCT_BASE = "39d2076fa204991ec9c0d43f00b502942556bf9a"
IMPORT_COMMIT = "aba7735"
PLAN_FILE_SHA256 = "ceacb2e064ef3550774064e94580397f213614fa834d7b82b0fdcb2a91b44501"
BUILD_COMMAND = "make -C engine clean all && make -C tests/capacity_wp09_adapter clean all"

CHUNK_FRAMES = 131072
FEED_MAX = 4096
FREE_NEXT = 3   # ADAPTER.md: raw-media derivation of the fixture gives free_next == 3
MODES = ("overwrite", "overdub", "splice")
POSITIONS = ("start", "middle", "end")
SHAPES = ("one-free-one-left", "two-free-seventeen-left", "three-free-4095-left")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_provenance() -> None:
    if git("rev-parse", "HEAD:tests/capacity_wp09_r52") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/capacity_wp09_r52") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")
    if sha256_file(PLAN) != PLAN_FILE_SHA256:
        raise SystemExit("plan.json is not the published plan")


def input_sample(row: dict) -> tuple[int, int]:
    code = 100 * MODES.index(row["mode"]) + 10 * POSITIONS.index(row["position"]) + SHAPES.index(row["shape"])
    return 1000 + code, -1000 - code


def prefill_frames(row: dict) -> int:
    return (row["total_chunks"] - FREE_NEXT) * CHUNK_FRAMES - row["final_accepted"]


def observe(row: dict) -> bytes:
    left, right = input_sample(row)
    args = [str(ADAPTER_BIN), row["mode"], str(row["at"]), str(row["total_chunks"]),
            str(prefill_frames(row)), str(row["final_requested"]), str(row["service_budget"]),
            str(left), str(right)]
    raw = subprocess.run(args, check=True, capture_output=True).stdout
    obs = json.loads(raw)
    pcm = bytes.fromhex(obs["calls"]["render"].pop("pcm_hex"))
    obs["calls"]["render"]["pcm_zlib_b64"] = base64.b64encode(zlib.compress(pcm, 9)).decode()
    obs["schema"] = "wp09-capacity-r52-v1"
    obs["case"] = row["id"]
    obs["fixture_sha256"] = hashlib.sha256(json.dumps(
        obs["raw_before"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return (json.dumps(obs, sort_keys=True, separators=(",", ":")) + "\n").encode()


def census(jsonl: Path) -> dict:
    """Observed facts per case, for reading the evidence. Not a verdict."""
    out = {}
    for line in jsonl.open("rb"):
        o = json.loads(line)
        calls, final = o["calls"], o["calls"]["feed_steps"][-1]
        service = {s["label"] for f in calls["feed_steps"] for s in f["service"]}
        writes = [e for e in o["events"] if e["step"] in service and e["op"] == "write"]
        out[o["case"]] = {
            "final_feed": {k: final[k] for k in ("requested", "accepted", "result", "events_from_call")},
            "premature_commit": calls["premature_commit"],
            "service_calls": len(service),
            "service_write_blocks": sum(e["count"] for e in writes),
            "service_chunks": sorted({(e["lba"] - 2048) // 1024 for e in writes}),
            "commit_events": [[e["op"], e.get("lba")] for e in o["events"] if e["step"] == "commit"],
            "remounted_frames": calls["render"]["rendered"],
            "render_events_from_call": calls["render"]["events_from_call"],
            "free_chunks_after": calls["info_after"]["free_chunks"],
        }
    return out


def write_gzip(src: Path, dst: Path) -> None:
    with dst.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                                              compresslevel=9, mtime=0) as gz:
        gz.write(src.read_bytes())


def run_replay(jsonl: Path, manifest: Path, product_commit: str, product_tree: str, adapter_sha: str) -> int:
    return subprocess.run([sys.executable, "-B", str(PACKAGE / "replay.py"), str(jsonl),
                           "--manifest", str(manifest), "--adapter-kind", "product",
                           "--adapter-source-sha256", adapter_sha,
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
    if sha256_file(retained / "build-identity.json") != sums["build-identity.json"]:
        raise SystemExit("retained build-identity.json does not match its committed SHA-256")
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
        out = fresh_dir(a.out or Path("build/wp09-capacity-replay"))
        jsonl = out / "observations.jsonl"
        jsonl.write_bytes(data)
        rc = run_replay(jsonl, out / "manifest.json", product_commit, product_tree,
                        ident["adapter_source_sha256"])
        print(f"replayed retained evidence {read_sums(retained)['observations.jsonl']}")
        return rc

    out = fresh_dir(a.evidence)
    if not ADAPTER_BIN.is_file():
        raise SystemExit("adapter not built: " + BUILD_COMMAND)
    rows = json.loads(PLAN.read_text())
    jsonl = out / "observations.jsonl"
    with jsonl.open("wb") as f:
        for row in rows:
            f.write(observe(row))
    print(f"adapter emitted {len(rows)} case records")

    write_gzip(jsonl, out / "observations.jsonl.gz")
    (out / "case-census.json").write_text(json.dumps(census(jsonl), indent=2, sort_keys=True) + "\n",
                                          newline="\n")
    ident = {
        "schema": "wp09-capacity-r52-product-build-identity-1",
        "verifier_tree": VERIFIER_TREE,
        "verifier_source_commit": VERIFIER_SOURCE,
        "product_base": PRODUCT_BASE,
        "import_commit": git("rev-parse", IMPORT_COMMIT),
        "engine_tree": git("rev-parse", "HEAD:engine"),
        "adapter_source_sha256": adapter_sha,
        "makefile_sha256": sha256_file(HERE / "Makefile"),
        "run_product_sha256": sha256_file(Path(__file__)),
        "build_command": BUILD_COMMAND,
        "plan_file_sha256": PLAN_FILE_SHA256,
        "case_count": len(rows),
        "fixture": "raw stage-0 media per ADAPTER.md on a fresh flat device per row "
                   "(block_count 2048 + 1024 x total_chunks + 1; nominal_length_s 9/12/15 s "
                   "for 4/5/6 chunks; uuid ASCII WP09-R52-capshrt; sb_generation 7; "
                   "empty Side-A index A0 at sequence 1; live B0 sequence 3 [(2,0,12)]; B1 zero; "
                   "seed frames (100+i,-200-i) in chunk 2)",
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

    return run_replay(jsonl, out / "manifest.json", product_commit, product_tree, adapter_sha)


if __name__ == "__main__":
    raise SystemExit(main())
