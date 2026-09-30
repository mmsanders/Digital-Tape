#!/usr/bin/env python3
"""Canonical Product run of the imported WP-10 R53 crash-injection package.

Checks the declared import against history, writes the adapter's input (the
fixture blocks from the package's model.py and its pinned R29-B builder, the
tracked LBAs, and the planned case list), runs the separately built public-API
adapter over all 57,539 cases, and hands the observations to the verifier's
own replay.py, which decides. The package oracle is never imported: the case
order is restated below from model.injections, exactly as ADAPTER.md's
"oracle.iter_cases() order" defines it.

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
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / "tests" / "wp10_closure_r53"
ADAPTER_SRC = HERE / "wp10c_adapter.c"
ADAPTER_BIN = HERE / "build" / ("wp10c_adapter.exe" if os.name == "nt" else "wp10c_adapter")

VERIFIER_TREE = "2a514c902b9b38901abe6841017cc110987c1ecd"
VERIFIER_SOURCE = "86904a30765eb415d1283fcd1cbb511f2569ed7c"
PRODUCT_BASE = "6e88b0f2458614dd9303bc6be8fc4d35535bdb73"
IMPORT_COMMIT = "2d641f4"
BUILD_COMMAND = "make -C engine clean all && make -C tests/wp10_closure_adapter clean all"
GZ = "observations.jsonl.gz"

sys.path.insert(0, str(PACKAGE))
import model as M  # noqa: E402  fixtures, transactions and the pinned builder; not the oracle


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha(path.read_bytes())


def check_provenance() -> None:
    if git("rev-parse", "HEAD:tests/wp10_closure_r53") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/wp10_closure_r53") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")


def cases():
    """ADAPTER.md's case order: every scenario's injections, then each scenario's
    completion case, then the one empty-family case."""
    idx = 0
    for scenario in M.SCENARIOS:
        for mode, inject in M.injections(scenario):
            yield {"index": idx, "kind": "crash", "scenario": scenario, "mode": mode, "inject": list(inject)}
            idx += 1
    for scenario in M.SCENARIOS:
        yield {"index": idx, "kind": "complete", "scenario": scenario}
        idx += 1
    yield {"index": idx, "kind": "empty_family", "scenario": "DUP-EMPTY-BLANK"}


def source_128() -> dict:
    """ADAPTER.md's 128-frame source: Side A one entry {0,0,128}, chunk 0 block 0
    = model.SOURCE_AUDIO, on the same 4-chunk / 9-second geometry, built with the
    package's pinned superblock builder and model.index_blocks."""
    img = {name: M.ZERO for name in M.TRACKED}
    img["P"] = img["M"] = M.B.superblock(generation=3, uuid=M.B.OLD_UUID_B, high=1)
    img["A0h"], img["A0e"] = M.index_blocks(0, 1, [(0, 0, 128)])
    img["B0h"], img["B0e"] = M.index_blocks(1, 2, [(0, 0, 128)])
    img["C0"] = M.SOURCE_AUDIO
    return img


def fixture_lines(name: str, img: dict) -> list[str]:
    blocks = [(M.TRACKED[n], data) for n, data in sorted(img.items()) if data != M.ZERO]
    return [f"FIXTURE {name} {len(blocks)}"] + [f"{lba} {data.hex()}" for lba, data in blocks]


def input_text() -> str:
    names = sorted(M.TRACKED)
    lines = [f"BLOCK_COUNT {M.B.BLOCK_COUNT}",
             f"TRACKED {len(names)} " + " ".join(str(M.TRACKED[n]) for n in names),
             f"UUIDS {M.B.FRESH_DUP_UUID.hex()} {M.B.FRESH_FORMAT_UUID.hex()}"]
    for shape in ("blank", "reusable_good", "reusable_stale"):
        lines += fixture_lines(shape, M.destination(shape))
    lines += fixture_lines("source_128", source_128())
    lines += ["FIXTURE blank_device 0"]
    for sid, (op, frames, shape, _row) in M.SCENARIOS.items():
        lines.append(f"SCENARIO {sid} {op} {frames} {shape}")
    lines.append("SOURCES")
    for c in cases():
        if c["kind"] == "crash":
            i = c["inject"]
            lines.append(f"CASE {c['index']} crash {c['scenario']} {c['mode']} " + " ".join(str(x) for x in i))
        else:
            lines.append(f"CASE {c['index']} {c['kind']} {c['scenario']}")
    return "\n".join(lines) + "\n"


def census(data: bytes) -> dict:
    """Observed counts per scenario, mode and result; not a verdict."""
    out = {"cases": 0, "by_kind": {}, "crash_by_scenario_mode": {}, "fired": 0,
           "remount_results": {"ro_A": {}, "rw_A": {}, "rw_B": {}}, "repairing_mounts": 0}
    for line in data.splitlines():
        o = json.loads(line)
        out["cases"] += 1
        out["by_kind"][o["kind"]] = out["by_kind"].get(o["kind"], 0) + 1
        if o["kind"] == "crash":
            k = f"{o['scenario']}/{o['mode']}"
            out["crash_by_scenario_mode"][k] = out["crash_by_scenario_mode"].get(k, 0) + 1
            out["fired"] += bool(o["fired"])
        for m in ("ro_A", "rw_A", "rw_B"):
            if m in o:
                r = o[m]["result"]
                out["remount_results"][m][r] = out["remount_results"][m].get(r, 0) + 1
                out["repairing_mounts"] += bool(o[m]["repair_events"])
    return out


def run_replay(gz: Path, manifest: Path, product_commit: str, product_tree: str, adapter_sha: str) -> int:
    rc = subprocess.run([sys.executable, "-B", str(PACKAGE / "replay.py"), str(gz),
                         "--manifest", str(manifest), "--adapter-kind", "product",
                         "--adapter-source-sha", adapter_sha,
                         "--product-commit", product_commit, "--product-tree", product_tree],
                        cwd=str(PACKAGE)).returncode
    print(f"replay.py exit status {rc}")
    return rc


def fresh_dir(path: Path) -> Path:
    path = path if path.is_absolute() else ROOT / path
    if path.exists() and any(path.iterdir()):
        raise SystemExit(f"refusing to reuse non-empty evidence directory {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_sums(d: Path) -> dict:
    out = {}
    for line in (d / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(None, 1)
        out[name.lstrip("*")] = digest
    return out


def retained_gzip(d: Path) -> Path:
    sums = read_sums(d)
    gz = d / GZ
    if sha256_file(gz) != sums[GZ]:
        raise SystemExit("retained gzip does not match its committed SHA-256")
    for name in ("build-identity.json", "case-census.json"):
        if sha256_file(d / name) != sums[name]:
            raise SystemExit(f"retained {name} does not match its committed SHA-256")
    if sha(gzip.decompress(gz.read_bytes())) != sums["observations.jsonl"]:
        raise SystemExit("retained JSONL does not match its committed SHA-256")
    return gz


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--evidence", type=Path)
    g.add_argument("--replay", type=Path)
    ap.add_argument("--retained", type=Path)
    ap.add_argument("--out", type=Path, help="with --replay: fresh directory for the manifest")
    a = ap.parse_args()

    check_provenance()
    head = git("rev-parse", "HEAD")
    product_commit = os.environ.get("PRODUCT_COMMIT") or head
    product_tree = git("rev-parse", product_commit + "^{tree}")
    adapter_sha = sha256_file(ADAPTER_SRC)

    if a.replay:
        d = a.replay if a.replay.is_absolute() else ROOT / a.replay
        gz = retained_gzip(d)
        ident = json.loads((d / "build-identity.json").read_text())
        out = fresh_dir(a.out or Path("build/wp10-closure-replay"))
        return run_replay(gz, out / "manifest.json", product_commit, product_tree, ident["adapter_source_sha256"])

    out = fresh_dir(a.evidence)
    if not ADAPTER_BIN.is_file():
        raise SystemExit("adapter not built: " + BUILD_COMMAND)
    text = input_text()
    with tempfile.TemporaryDirectory(prefix="wp10c-") as tmp:
        inp, jsonl = Path(tmp) / "input.txt", Path(tmp) / "observations.jsonl"
        inp.write_text(text, newline="\n")
        subprocess.run([str(ADAPTER_BIN), str(inp), str(jsonl)], check=True)
        data = jsonl.read_bytes()
    gz = out / GZ
    gz.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))
    (out / "case-census.json").write_text(json.dumps(census(data), indent=2, sort_keys=True) + "\n", newline="\n")
    ident = {
        "schema": "wp10-r53-product-build-identity-1",
        "verifier_tree": VERIFIER_TREE,
        "verifier_source_commit": VERIFIER_SOURCE,
        "product_base": PRODUCT_BASE,
        "import_commit": git("rev-parse", IMPORT_COMMIT),
        "engine_tree": git("rev-parse", "HEAD:engine"),
        "adapter_source_sha256": adapter_sha,
        "makefile_sha256": sha256_file(HERE / "Makefile"),
        "run_product_sha256": sha256_file(Path(__file__)),
        "adapter_input_sha256": sha(text.encode()),
        "build_command": BUILD_COMMAND,
        "case_count": sum(1 for _ in cases()),
    }
    (out / "build-identity.json").write_text(json.dumps(ident, indent=2, sort_keys=True) + "\n", newline="\n")
    (out / "SHA256SUMS").write_text(
        f"{sha(data)}  observations.jsonl\n"
        + "".join(f"{sha256_file(out / n)}  {n}\n" for n in (GZ, "build-identity.json", "case-census.json")),
        newline="\n")
    (out / "host.json").write_text(json.dumps({"product_commit": product_commit, "product_tree": product_tree,
                                               "head": head, "platform": platform.platform()},
                                              indent=2, sort_keys=True) + "\n", newline="\n")
    print(f"{ident['case_count']} cases; JSONL {sha(data)}; gzip {len(gz.read_bytes())} bytes")

    if a.retained:
        d = a.retained if a.retained.is_absolute() else ROOT / a.retained
        if gzip.decompress(retained_gzip(d).read_bytes()) != data:
            raise SystemExit("regenerated JSONL differs from the committed retained evidence")
        print("regenerated JSONL is byte-identical to the retained evidence")

    return run_replay(gz, out / "manifest.json", product_commit, product_tree, adapter_sha)


if __name__ == "__main__":
    raise SystemExit(main())
