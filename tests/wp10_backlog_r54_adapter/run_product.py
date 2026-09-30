#!/usr/bin/env python3
"""Canonical Product run of the imported WP-10 backlog r54 package (rows 1-3).

Checks the declared import against history, runs the separately built
public-API adapter for every planned case, and hands the gzip JSONL to the
verifier's own replay.py, which decides. The package's oracle.py is never
imported; its plan order is restated below from the package's model.py (and
the row-3 source table from ADAPTER.md):

  row 1  model.REPAIR_SHAPES x model.injections(model.repair_ops(cartridge))
  row 2  model.RERUN_SHAPES x model.injections(model.dup_ops(rerun_destination))
  row 3  ROW3_SOURCES x ROW3_DESTS

  --evidence DIR   fresh output directory (refuses to reuse one)
  --retained DIR   also require the fresh JSONL to equal the committed SHA-256
  --replay GZ      offline: verify a retained gzip against the committed SHA-256
                   and replay it, no adapter
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
PACKAGE = ROOT / "tests" / "wp10_backlog_r54"
BUILD = HERE / "build"
SOURCES = ("wp10r54_adapter.c",)

VERIFIER_TREE = "d6e9a2427ed9b6c4b703c65dc44eb7e13224cabc"
VERIFIER_SOURCE = "dea9b521ccee76a69cfd0d517903eb27474d41fc"
PRODUCT_BASE = "66c6abc69d83cff10da32a6b446690fcd0b927fb"
IMPORT_COMMIT = "dee538e"
CASESET_SHA256 = "6808330224da3129371f482e1828eab36b801d7caa13652dfc69a99e7493aaf3"
BUILD_COMMAND = "make -C engine clean all && make -C tests/wp10_backlog_r54_adapter clean all"

sys.path.insert(0, str(PACKAGE))
import model as M  # noqa: E402  fixtures and transactions; not the oracle

B = M.B
# ADAPTER.md row 3 (oracle.ROW3_SOURCES / ROW3_DESTS), restated: (id, frames, label).
ROW3_SOURCES = (("EMPTY", 0, "Blank tape"), ("SHORT", 128, "Grandma's Songs"),
                ("ONE-CHUNK", M.CF, "Exactly one chunk"),
                ("CHUNK-PLUS-ONE", M.CF + 1, "0123456789abcdefghijklmnopqrstuv"))
ROW3_DESTS = ("blank", "healthy_pair")


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
    if git("rev-parse", "HEAD:tests/wp10_backlog_r54") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/wp10_backlog_r54") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")


# ------------------------------------------------------------------- plan

def cases():
    idx = 0
    for shape in M.REPAIR_SHAPES:
        for mode, inject in M.injections(M.repair_ops(M.cartridge(*M.REPAIR_SHAPES[shape]))):
            yield {"index": idx, "row": 1, "shape": shape, "mode": mode, "inject": list(inject)}
            idx += 1
    for shape in M.RERUN_SHAPES:
        for mode, inject in M.injections(M.dup_ops(M.rerun_destination(shape))):
            yield {"index": idx, "row": 2, "shape": shape, "mode": mode, "inject": list(inject)}
            idx += 1
    for source, _, _ in ROW3_SOURCES:
        for dest in ROW3_DESTS:
            yield {"index": idx, "row": 3, "source": source, "destination": dest}
            idx += 1


def caseset_sha256(plan: list) -> str:
    h = hashlib.sha256()
    for c in plan:
        h.update((canonical(c) + "\n").encode())
    return h.hexdigest()


# ------------------------------------------------------------------- fixtures

def tracked_blocks(img: dict) -> dict:
    return {M.TRACKED[n]: d for n, d in img.items()}


def source_blocks(frames: int, label: bytes, audio: bytes) -> dict:
    """A fresh 4-chunk / 9 s cartridge (the pinned R29-B builder): generation 1,
    a_high_water ceil(frames / CHUNK_FRAMES), both superblock copies, Side A
    {0,0,frames} (or an empty index), Side B a valid empty index, chunk 0
    block 0 = audio, every other audio block zero."""
    sb = M.with_label(B.superblock(generation=1, uuid=B.OLD_UUID_A, high=-(-frames // M.CF)), label)
    a_h, a_e = M.index_blocks(0, 1, [(0, 0, frames)] if frames else [])
    b_h, _ = M.index_blocks(1, 2, [])
    return {0: sb, B.LBA_MIRROR: sb, B.LBA_A0: a_h, B.LBA_A0 + 1: a_e, B.LBA_B0: b_h,
            B.LBA_CHUNK_BASE: audio}


def fixture_lines(name: str, count: int, blocks: dict) -> list[str]:
    if len(name) > 31:
        raise SystemExit("fixture name too long for the adapter: " + name)
    items = [(lba, data) for lba, data in sorted(blocks.items()) if data != M.ZERO]
    return [f"FIXTURE {name} {count} {len(items)}"] + [f"{lba} {data.hex()}" for lba, data in items]


def adapter_input(plan: list) -> str:
    names = sorted(M.TRACKED)
    lines = ["TRACKED %d " % len(names) + " ".join(str(M.TRACKED[n]) for n in names),
             f"DUP {B.FRESH_DUP_UUID.hex()} {B.NOMINAL_LENGTH_S}"]
    for shape, pair in M.REPAIR_SHAPES.items():
        lines += fixture_lines("rep_" + shape, B.BLOCK_COUNT, tracked_blocks(M.cartridge(*pair)))
    for shape in M.RERUN_SHAPES:
        lines += fixture_lines("dst_" + shape, B.BLOCK_COUNT, tracked_blocks(M.rerun_destination(shape)))
    lines += fixture_lines("src128", B.BLOCK_COUNT, source_blocks(128, b"", M.SOURCE_AUDIO))
    for source, frames, label in ROW3_SOURCES:
        audio = M.SOURCE_AUDIO if frames == 128 else M.ZERO
        lines += fixture_lines("r3src_" + source, B.BLOCK_COUNT, source_blocks(frames, label.encode(), audio))
    for c in plan:
        if c["row"] == 3:
            lines.append(f"CASE {c['index']} 3 {c['source']} {c['destination']}")
        else:
            lines.append(f"CASE {c['index']} {c['row']} {c['shape']} {c['mode']} "
                         + " ".join(str(x) for x in c["inject"]))
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------- run

def generate() -> tuple[bytes, dict]:
    plan = list(cases())
    if caseset_sha256(plan) != CASESET_SHA256:
        raise SystemExit("restated plan does not match the package's recorded case set")
    with tempfile.TemporaryDirectory(prefix="wp10r54-") as t:
        tmp = Path(t)
        (tmp / "cases.in").write_text(adapter_input(plan), newline="\n")
        subprocess.run([str(BUILD / "wp10r54_adapter"), str(tmp / "cases.in"), str(tmp / "obs.jsonl")], check=True)
        raw = (tmp / "obs.jsonl").read_bytes().splitlines()
    lines = [(canonical(json.loads(line)) + "\n").encode() for line in raw]
    census = {r: sum(c["row"] == int(r[-1]) for c in plan) for r in ("row1", "row2", "row3")}
    census["cases"] = len(lines)
    return b"".join(lines), census


def write_gzip(data: bytes, dst: Path) -> None:
    """Standard gzip (zlib, level 9, Z_FILTERED, mtime 0, no name): keeps the retained
    evidence under the 1 MiB tree limit; the stdlib default strategy does not."""
    c = zlib.compressobj(9, zlib.DEFLATED, 31, 8, zlib.Z_FILTERED)
    blob = c.compress(data) + c.flush()
    if len(blob) > 1 << 20:
        raise SystemExit(f"gzip evidence {len(blob)} bytes exceeds the 1 MiB tree limit")
    dst.write_bytes(blob)


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
    """One digest over the Software sources, in a fixed order."""
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


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--evidence", type=Path)
    g.add_argument("--replay", type=Path, help="a retained observations.jsonl.gz")
    ap.add_argument("--retained", type=Path, help="committed evidence directory (SHA256SUMS)")
    ap.add_argument("--out", type=Path, help="with --replay: fresh directory for the manifest")
    a = ap.parse_args()

    check_provenance()
    print("current engine/ tree " + git("rev-parse", "HEAD:engine"))
    head = git("rev-parse", "HEAD")
    product_commit = os.environ.get("PRODUCT_COMMIT") or head
    product_tree = git("rev-parse", product_commit + "^{tree}")
    retained = None
    if a.retained:
        retained = a.retained if a.retained.is_absolute() else ROOT / a.retained

    if a.replay:
        if retained is None:
            raise SystemExit("--replay needs --retained for the committed SHA-256")
        sums = read_sums(retained / "SHA256SUMS")
        gz = a.replay if a.replay.is_absolute() else ROOT / a.replay
        if sha256_file(gz) != sums["observations.jsonl.gz"]:
            raise SystemExit("retained gzip does not match its committed SHA-256")
        if sha(gzip.decompress(gz.read_bytes())) != sums["observations.jsonl"]:
            raise SystemExit("retained JSONL does not match its committed SHA-256")
        ident = json.loads((retained / "build-identity.json").read_text())
        out = fresh_dir(a.out or Path("build/wp10r54-replay"))
        return run_replay(gz, out, product_commit, product_tree, ident["adapter_source_sha256"])

    out = fresh_dir(a.evidence)
    if not (BUILD / "wp10r54_adapter").is_file():
        raise SystemExit("adapter not built: " + BUILD_COMMAND)
    data, census = generate()
    print(f"assembled {census['cases']} observations: row1 {census['row1']}, row2 {census['row2']}, "
          f"row3 {census['row3']}")
    gz = out / "observations.jsonl.gz"
    write_gzip(data, gz)
    ident = {
        "schema": "wp10-backlog-r54-product-build-identity-1",
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
        "adapter_origin": "tests/wp10_backlog_adapter/wp10b_row1.c (PR #329) device, settling and trace; "
                          "row 1-3 case drivers new",
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
        "engine_archive_sha256": sha256_file(ROOT / "build" / "engine" / "libtape.a"),
    }, indent=2, sort_keys=True) + "\n", newline="\n")
    print(f"observations.jsonl {len(data)} bytes {sums['observations.jsonl']}; gzip {gz.stat().st_size} bytes "
          f"{sums['observations.jsonl.gz']}")

    if retained is not None:
        want = read_sums(retained / "SHA256SUMS")
        if want["observations.jsonl"] != sums["observations.jsonl"]:
            raise SystemExit("regenerated JSONL differs from the committed SHA-256")
        print("regenerated JSONL is byte-identical to the committed SHA-256")

    return run_replay(gz, out, product_commit, product_tree, ident["adapter_source_sha256"])


if __name__ == "__main__":
    raise SystemExit(main())
