#!/usr/bin/env python3
"""Canonical Product run of the imported WP-10 residue-destination package (V10-001, #359).

Checks the declared import against history, writes the adapter's input (the tracked
LBAs, the call arguments, the fixture images from the package's plan.py bases and the
group list from plan.iter_groups()), runs the separately built public-API adapter over
every group, and hands the JSONL to the verifier's own replay.py, which decides. The
oracle is never imported, and neither is the planner's injection list: the adapter
derives each group's injection coordinates from its own clean re-run trace.

The stream is far over 1 MiB, so its gzip is a release asset (CLAUDE.md §4). Its
SHA-256, the uncompressed stream's SHA-256 and the replay manifest are committed.

  --evidence DIR   fresh output directory (refuses to reuse one)
  --retained DIR   also require the fresh stream to equal the committed SHA-256 and
                   the replay to reproduce the committed manifest exactly
  --replay DIR     offline: verify the retained asset (fetching it if absent) and
                   replay it against the committed manifest, no adapter
  --jobs N         adapter processes (default: CPU count); output is identical for any N
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / "tests" / "wp10_residue_d10"
BUILD = HERE / "build"
ADAPTER = BUILD / "wp10res_adapter"
SOURCES = ("wp10res_adapter.c",)

VERIFIER_TREE = "e1b885301768d7b541a5704c526881a800d7116b"
VERIFIER_SOURCE = "5ca24fb9c0773e715889c235c339ef035e87d63b"
PRODUCT_BASE = "56619e8a2ebc0429756e2047e7b326f31264aac1"
IMPORT_COMMIT = "a34d409"
CASESET_SHA256 = "849a82ab2e8e4b207a52789e2c6e9dd247c3db947431e7beb4ed14916f04b1f8"
BUILD_COMMAND = "make -C engine clean all && make -C tests/wp10_residue_adapter clean all"
RELEASE_TAG = "evidence-p1-r60-wp10-residue"
ASSET = "wp10-residue-d10-product-observations.jsonl.gz"
ASSET_URL = f"https://github.com/mmsanders/Digital-Tape/releases/download/{RELEASE_TAG}/{ASSET}"

sys.path.insert(0, str(PACKAGE))
import plan as P  # noqa: E402  groups and fixture bases; not the oracle

M, B = P.M, P.B


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_provenance() -> None:
    if git("rev-parse", "HEAD:tests/wp10_residue_d10") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/wp10_residue_d10") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")
    census = P.census()
    if census["caseset_sha256"] != CASESET_SHA256:
        raise SystemExit(f"planner case set {census['caseset_sha256']} is not {CASESET_SHA256}")


# ------------------------------------------------------------------- input

def tracked_blocks(img: dict) -> dict:
    return {M.TRACKED[n]: d for n, d in img.items()}


def source_blocks() -> dict:
    """ADAPTER.md dup source: a 4-chunk device, Side A {0,0,128}, chunk 0 block 0 =
    model.SOURCE_AUDIO, empty label (the pinned R29-B builder, generation 1)."""
    sb = M.with_label(B.superblock(generation=1, uuid=B.OLD_UUID_A, high=1), b"")
    a_h, a_e = M.index_blocks(0, 1, [(0, 0, 128)])
    b_h, _ = M.index_blocks(1, 2, [])
    return {0: sb, B.LBA_MIRROR: sb, B.LBA_A0: a_h, B.LBA_A0 + 1: a_e, B.LBA_B0: b_h,
            B.LBA_CHUNK_BASE: M.SOURCE_AUDIO}


def fixture_lines(name: str, blocks: dict) -> list[str]:
    if len(name) > 63:
        raise SystemExit("fixture name too long for the adapter: " + name)
    items = [(lba, data) for lba, data in sorted(blocks.items()) if data != M.ZERO]
    return [f"FIXTURE {name} {B.BLOCK_COUNT} {len(items)}"] + [f"{lba} {data.hex()}" for lba, data in items]


def header() -> str:
    names = sorted(M.TRACKED)
    lines = ["TRACKED %d " % len(names) + " ".join(str(M.TRACKED[n]) for n in names),
             f"ARGS {B.FRESH_DUP_UUID.hex()} {B.FRESH_FORMAT_UUID.hex()} {B.NOMINAL_LENGTH_S}"]
    for shape, pair in {**P.EXHAUSTION_SHAPES, **P.RESIDUE_SHAPES}.items():
        lines += fixture_lines("base_" + shape, tracked_blocks(P.base(*pair)))
    for variant in P.BLANK_VARIANTS:
        lines += fixture_lines("blank_" + variant, tracked_blocks(P.blank(variant)))
    lines += fixture_lines("src128", source_blocks())
    return "\n".join(lines) + "\n"


def group_line(g: dict) -> str:
    if g["row"] == "R1":
        return f"GROUP {g['index']} R1 {g['op']} {g['shape']} {g['mode']} {g['l1']} {g['scope']}"
    if g["row"] == "R2":
        return f"GROUP {g['index']} R2 {g['op']} {g['shape']} {g['mode']} {g['scope']}"
    return f"GROUP {g['index']} R3 {g['op']} {g['variant']} {g['mode']}"


# ------------------------------------------------------------------- run

def generate(out_jsonl: Path, jobs: int) -> int:
    groups = list(P.iter_groups())
    head = header()
    # Shards are contiguous and interleave-free, so concatenation is plan order for any N.
    n = max(1, min(jobs, len(groups)))
    bounds = [len(groups) * i // n for i in range(n + 1)]
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        procs = []
        for i in range(n):
            inp, part = tmp / f"in{i}.txt", tmp / f"out{i}.jsonl"
            inp.write_text(head + "".join(group_line(g) + "\n" for g in groups[bounds[i]:bounds[i + 1]]),
                           newline="\n")
            procs.append((subprocess.Popen([str(ADAPTER), str(inp), str(part)]), part))
        for p, _ in procs:
            if p.wait() != 0:
                raise SystemExit(f"adapter exited {p.returncode}")
        with out_jsonl.open("wb") as dst:
            for _, part in procs:
                with part.open("rb") as src:
                    shutil.copyfileobj(src, dst, 1 << 22)
    return len(groups)


def write_gzip(src: Path, dst: Path) -> None:
    """Standard gzip (zlib level 9, mtime 0, no name), streamed."""
    c = zlib.compressobj(9, zlib.DEFLATED, 31)
    with src.open("rb") as f, dst.open("wb") as o:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            o.write(c.compress(chunk))
        o.write(c.flush())


def run_replay(evidence: Path, out: Path, product_commit: str, product_tree: str, adapter_sha: str) -> int:
    r = subprocess.run([sys.executable, "-B", str(PACKAGE / "replay.py"), str(evidence),
                        "--manifest", str(out / "manifest.json"),
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


def stream_sha_of_gzip(gz: Path) -> str:
    h = hashlib.sha256()
    with gzip.open(gz, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def replay_retained(retained: Path, out: Path) -> int:
    sums = read_sums(retained / "SHA256SUMS")
    gz = retained / ASSET
    if not gz.exists():
        print(f"fetch {ASSET_URL}")
        tmp = gz.with_suffix(".part")
        with urllib.request.urlopen(ASSET_URL) as r, tmp.open("wb") as f:
            shutil.copyfileobj(r, f, 1 << 22)
        tmp.replace(gz)
    if sha256_file(gz) != sums[ASSET]:
        gz.unlink()
        raise SystemExit("REFUSED: retained asset does not match its committed SHA-256; nothing installed")
    if stream_sha_of_gzip(gz) != sums["observations.jsonl"]:
        raise SystemExit("retained stream does not match its committed SHA-256")
    ident = json.loads((retained / "build-identity.json").read_text())
    shutil.copyfile(retained / "manifest.json", out / "manifest.json")
    return run_replay(gz, out, ident["product_commit"], ident["product_tree"], ident["adapter_source_sha256"])


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--evidence", type=Path, help="fresh output directory")
    g.add_argument("--replay", type=Path, help="a retained evidence directory")
    ap.add_argument("--retained", type=Path, help="committed evidence directory")
    ap.add_argument("--out", type=Path, help="--replay output directory")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    a = ap.parse_args()
    check_provenance()

    if a.replay:
        retained = a.replay if a.replay.is_absolute() else ROOT / a.replay
        return replay_retained(retained, fresh_dir(a.out or Path(tempfile.mkdtemp())))

    out = fresh_dir(a.evidence)
    head = git("rev-parse", "HEAD")
    product_commit = os.environ.get("PRODUCT_COMMIT") or head
    if product_commit != head:
        raise SystemExit(f"workspace/head mismatch PRODUCT_COMMIT={product_commit} HEAD={head}")
    product_tree = git("rev-parse", "HEAD^{tree}")
    print(f"current engine/ tree {git('rev-parse', 'HEAD:engine')}")
    if not ADAPTER.exists():
        raise SystemExit("adapter not built: " + BUILD_COMMAND)

    jsonl = out / "observations.jsonl"
    groups = generate(jsonl, a.jobs)
    gz = out / ASSET
    write_gzip(jsonl, gz)
    stream = sha256_file(jsonl)
    ident = {
        "schema": "wp10-residue-d10-product-build-identity-1",
        "verifier_tree": VERIFIER_TREE,
        "verifier_source_commit": VERIFIER_SOURCE,
        "product_base": PRODUCT_BASE,
        "import_commit": git("rev-parse", IMPORT_COMMIT),
        "product_commit": product_commit,
        "product_tree": product_tree,
        "engine_tree": git("rev-parse", "HEAD:engine"),
        "caseset_sha256": CASESET_SHA256,
        "adapter_source_sha256": adapter_source_sha(),
        "sources_sha256": {n: sha256_file(HERE / n) for n in SOURCES},
        "makefile_sha256": sha256_file(HERE / "Makefile"),
        "build_command": BUILD_COMMAND,
        "groups": groups,
        "release_asset": {"tag": RELEASE_TAG, "name": ASSET},
    }
    cc = subprocess.run([os.environ.get("CC", "cc"), "--version"], capture_output=True, text=True)
    (out / "host.json").write_text(json.dumps({
        "head": head, "cc": (cc.stdout.splitlines() or ["unknown"])[0], "platform": platform.platform(),
        "python": platform.python_version(), "jobs": a.jobs,
        "engine_archive_sha256": sha256_file(ROOT / "build" / "engine" / "libtape.a"),
    }, indent=2, sort_keys=True) + "\n", newline="\n")
    print(f"observations.jsonl {jsonl.stat().st_size} bytes {stream}; gzip {gz.stat().st_size} bytes "
          f"{sha256_file(gz)}")

    if a.retained is not None:
        retained = a.retained if a.retained.is_absolute() else ROOT / a.retained
        want = read_sums(retained / "SHA256SUMS")
        if want["observations.jsonl"] != stream:
            raise SystemExit("regenerated stream differs from the committed SHA-256")
        print("regenerated stream is byte-identical to the committed SHA-256")
        # The committed manifest binds the accepted product commit; replay checks every
        # other field (stream, census, outcomes) against it.
        keep = json.loads((retained / "build-identity.json").read_text())
        shutil.copyfile(retained / "manifest.json", out / "manifest.json")
        rc = run_replay(jsonl, out, keep["product_commit"], keep["product_tree"], adapter_source_sha())
        jsonl.unlink()
        return rc

    (out / "build-identity.json").write_text(json.dumps(ident, indent=2, sort_keys=True) + "\n", newline="\n")
    rc = run_replay(jsonl, out, product_commit, product_tree, ident["adapter_source_sha256"])
    sums = {"observations.jsonl": stream, ASSET: sha256_file(gz),
            "build-identity.json": sha256_file(out / "build-identity.json"),
            "manifest.json": sha256_file(out / "manifest.json") if (out / "manifest.json").exists() else "MISSING"}
    (out / "SHA256SUMS").write_text("".join(f"{v}  {k}\n" for k, v in sums.items()), newline="\n")
    jsonl.unlink()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
