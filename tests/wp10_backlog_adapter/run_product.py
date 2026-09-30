#!/usr/bin/env python3
"""Canonical Product run of the imported WP-10 backlog rows 1-3 package.

Checks the declared import against history, runs the separately built public-API
programs for every planned case, assembles one wp10-backlog-r53-observation-v1
object per case in the package's plan order, and hands the gzip JSONL to the
verifier's own replay.py, which decides. The package's oracle.py is never
imported; the plan order is restated below:

  row 1  dupfrag.SCENARIOS x dupfrag.injections(), then one completion per
         scenario                                   -> wp10b_row1
  row 2  every C69 case, then every R29-B crash case, whose accepted campaign
         model (crash_core_draft8 / format_dup_identity_draft8, loaded through
         the package's pinned deps.py) remounts TAPE_OK -> copies of the accepted
         C69 and R29-B workers with a post-remount tape_get_info
  row 3  record modes x durability modes              -> wp10b_row3

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
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / "tests" / "wp10_backlog_r53"
BUILD = HERE / "build"
SOURCES = ("wp10b_row1.c", "wp10b_row3.c", "wp10b_c69_worker.c", "wp10b_r29b_worker.c")

VERIFIER_TREE = "7f80e382fc915aec4d9b8e1a9226b6c22a2da3f8"
VERIFIER_SOURCE = "fd139dfa42a9447d889c700b0818e3d1f9099e81"
PRODUCT_BASE = "66c6abc69d83cff10da32a6b446690fcd0b927fb"
IMPORT_COMMIT = "014df20"
CASESET_SHA256 = "036e255eb2a704d041b87eb21116900ea307ba450a5cf72f3b0440dffdd3b2d7"
BUILD_COMMAND = "make -C engine clean all && make -C tests/wp10_backlog_adapter clean all"
RECORD_MODES = ("overwrite", "overdub", "splice")
MODES = ("flush_required", "write_through")

sys.path.insert(0, str(PACKAGE))
import deps  # noqa: E402  pinned accepted campaign models; not this package's oracle
import dupfrag as D  # noqa: E402  row-1 fixtures and transactions; not the oracle

C, R = deps.C69, deps.R29B


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
    if git("rev-parse", "HEAD:tests/wp10_backlog_r53") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/wp10_backlog_r53") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")


# ------------------------------------------------------------------- plan

def row1_cases():
    for scenario in D.SCENARIOS:
        for mode, inject in D.injections(scenario):
            yield {"row": 1, "kind": "crash", "scenario": scenario, "mode": mode, "inject": list(inject)}
    for scenario in D.SCENARIOS:
        yield {"row": 1, "kind": "complete", "scenario": scenario}


def c69_cases():
    for case in C.planner.iter_cases():
        side = "A" if case["family"] == "reset_b" and case["variant"] == "degraded_equal" else "B"
        post = C.oracle.expected_snapshot(case, C.oracle._fixture_snapshot(case))
        if C.media.inspect_snapshot(post, requested_side=side)["mount_result"] == "TAPE_OK":
            yield case


def r29b_cases():
    for case in R.planner.iter_cases():
        if case["scope"] == "crash" and \
                R.media.inspect_snapshot(R.oracle.expected_snapshot(case))["mount_result"] == "TAPE_OK":
            yield case


# ------------------------------------------------------------------- row 1

SRC_BLOCK_COUNT = D.B.LBA_CHUNK_BASE + D.SRC_TOTAL_CHUNKS * D.B.CHUNK_BLOCKS + 1


def source_blocks() -> dict:
    """ADAPTER.md row 1 source: 8 chunks / 21 s, Side A = dupfrag.SRC_ENTRIES with
    a_high_water 8, every referenced frame dupfrag.src_frame(chunk, frame); Side B a
    valid empty index; label zero. The superblock is the pinned R29-B builder's,
    with nominal_length_s 21, total_chunks 8 and the mirror LBA rewritten for this
    geometry, and its CRC recomputed."""
    sb = bytearray(D.B.superblock(generation=1, uuid=D.B.OLD_UUID_A, high=D.SRC_HIGH, nominal=D.SRC_NOMINAL_S))
    struct.pack_into("<I", sb, 52, D.SRC_TOTAL_CHUNKS)
    struct.pack_into("<I", sb, 84, SRC_BLOCK_COUNT - 1)
    struct.pack_into("<I", sb, 508, D.crc32(bytes(sb[:508])))
    blocks = {0: bytes(sb), SRC_BLOCK_COUNT - 1: bytes(sb)}
    a_h, a_e = D.index_blocks(0, 1, list(D.SRC_ENTRIES))
    b_h, _ = D.index_blocks(1, 2, [])
    blocks[D.B.LBA_A0], blocks[D.B.LBA_A0 + 1], blocks[D.B.LBA_B0] = a_h, a_e, b_h
    audio: dict = {}
    for first, start, n in D.SRC_ENTRIES:
        for j in range(n):
            frame = start + j
            lba = D.B.LBA_CHUNK_BASE + first * D.B.CHUNK_BLOCKS + (frame * 4) // D.BLOCK
            off = (frame * 4) % D.BLOCK
            audio.setdefault(lba, bytearray(D.BLOCK))[off:off + 4] = D.src_frame(first, frame)
    blocks.update({lba: bytes(b) for lba, b in audio.items()})
    return blocks


def fixture_lines(name: str, count: int, blocks: dict) -> list[str]:
    items = [(lba, data) for lba, data in sorted(blocks.items()) if data != D.ZERO]
    return [f"FIXTURE {name} {count} {len(items)}"] + [f"{lba} {data.hex()}" for lba, data in items]


def row1_input(cases: list) -> str:
    names = sorted(D.TRACKED)
    lines = ["TRACKED %d " % len(names) + " ".join(str(D.TRACKED[n]) for n in names),
             f"DUP {D.B.FRESH_DUP_UUID.hex()} 9"]
    for shape in ("blank", "reusable_good"):
        lines += fixture_lines(shape, D.B.BLOCK_COUNT, {D.TRACKED[n]: d for n, d in D.destination(shape).items()})
    lines += fixture_lines("source", SRC_BLOCK_COUNT, source_blocks())
    for c in cases:
        shape = D.SCENARIOS[c["scenario"]][2]
        if c["kind"] == "crash":
            lines.append(f"CASE {c['index']} crash {c['scenario']} {shape} {c['mode']} "
                         + " ".join(str(x) for x in c["inject"]))
        else:
            lines.append(f"CASE {c['index']} complete {c['scenario']} {shape}")
    return "\n".join(lines) + "\n"


def run_row1(cases: list, tmp: Path) -> list[bytes]:
    (tmp / "row1.in").write_text(row1_input(cases), newline="\n")
    subprocess.run([str(BUILD / "wp10b_row1"), str(tmp / "row1.in"), str(tmp / "row1.jsonl")], check=True)
    return (tmp / "row1.jsonl").read_bytes().splitlines(keepends=True)


# ------------------------------------------------------------------- row 2

def c69_fixtures(tmp: Path) -> list[str]:
    """The accepted C69 runner's fixture set, in its worker's argument order."""
    F, paths = C.fixture, []

    def put(name, family, variant, seed=None):
        p = tmp / f"c69_{name}.img"
        p.write_bytes(F.fixture_bytes(family, variant, seed=seed))
        paths.append(str(p))

    put("record_commit", "record_commit", "overwrite")
    put("reset_healthy", "reset_b", "healthy")
    put("reset_degraded_equal", "reset_b", "degraded_equal")
    put("stage_healthy", "stage_clear", "arm")
    for seed in ("primary_only", "mirror_only", "primary_newer_mirror_stale", "mirror_newer_primary_stale"):
        put("stage_" + seed, "stage_clear", "arm", seed)
    return paths


def r29b_fixtures(tmp: Path) -> list[str]:
    """The accepted R29-B adapter's source, big source and seven shapes."""
    F = R.fixture
    audio = bytearray(F.BLOCK)
    for i in range(100):
        struct.pack_into("<hh", audio, i * 4, i + 1, 100 - i)
    sb = F.superblock(generation=1, uuid=F.OLD_UUID_A, high=1, nominal=10)
    entry = bytearray(F.BLOCK)
    struct.pack_into("<III", entry, 0, 0, 0, 100)
    (tmp / "r29b_source.bin").write_bytes(sb + sb + F.OLD_A0 + bytes(entry) + F.OLD_B0 + bytes(audio))
    frames = 131_073
    sb2 = F.superblock(generation=1, uuid=F.OLD_UUID_A, high=2, nominal=10)
    entry2 = bytearray(F.BLOCK)
    struct.pack_into("<III", entry2, 0, 0, 0, frames)
    (tmp / "r29b_source_big.bin").write_bytes(
        sb2 + sb2 + F.index_head(side=0, sequence=100, frames=frames) + bytes(entry2) + F.OLD_B0 + bytes(audio))
    paths = [str(tmp / "r29b_source.bin"), str(tmp / "r29b_source_big.bin")]
    for name in F.raw_shapes():
        s = F.initial_snapshot(name)
        p = tmp / f"r29b_{name}.bin"
        p.write_bytes(bytes.fromhex(s["primary_hex"]) + bytes.fromhex(s["mirror_hex"])
                      + bytes.fromhex(s["a0_head_hex"]) + bytes.fromhex(s["b0_head_hex"]))
        paths.append(str(p))
    return paths


def _remount(o: dict, side: str) -> dict:
    m = {"side": side, "result": o["actual_remount_result"]}
    if "remount_total_chunks" in o:
        m["total_chunks"] = o["remount_total_chunks"]
        m["free_chunks"] = o["remount_free_chunks"]
    return m


def _obs2(index: int, campaign: str, case_index: int, post: dict, remount: dict) -> bytes:
    obs = {"schema": "wp10-backlog-r53-observation-v1", "index": index, "row": 2, "kind": "frontier",
           "campaign": campaign, "case_index": case_index,
           "post_snapshot_sha256": sha(canonical(post).encode()), "remount": remount}
    return (canonical(obs) + "\n").encode()


def run_row2(c69: list, r29b: list, first_index: int, tmp: Path) -> list[bytes]:
    out, index = [], first_index
    proc = subprocess.Popen([str(BUILD / "wp10b_c69_worker"), *c69_fixtures(tmp)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True, bufsize=1)
    assert proc.stdin is not None and proc.stdout is not None
    seen = set()
    for case in c69:
        # The accepted C69 adapter's protocol: one baseline per scope/family/variant/seed.
        key = (case["scope"], case["family"], case["variant"], case.get("seed"))
        if key not in seen:
            proc.stdin.write("\t".join(["B", case["family"], case["variant"], case.get("seed", "-")]) + "\n")
            proc.stdin.flush()
            proc.stdout.readline()
            seen.add(key)
        inj = case["injection"]
        ordinal = inj["flush_ordinal"] if "flush_ordinal" in inj else inj["write_ordinal"]
        landed = 0 if "flush_ordinal" in inj else inj["landed_bytes"]
        proc.stdin.write("\t".join(["C", str(case["case_index"]), case["scope"], case["family"], case["variant"],
                                    case["mode"], inj["kind"], str(ordinal), str(landed),
                                    case.get("seed", "-")]) + "\n")
        proc.stdin.flush()
        o = json.loads(proc.stdout.readline())
        out.append(_obs2(index, "C69", case["case_index"], o["post_snapshot"], _remount(o, o["remount_side"])))
        index += 1
    proc.stdin.write("D\n")
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("C69 worker failed")

    proc = subprocess.Popen([str(BUILD / "wp10b_r29b_worker"), *r29b_fixtures(tmp)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True, bufsize=1)
    assert proc.stdin is not None and proc.stdout is not None
    for case in r29b:
        inj = case["injection"]
        ordinal = inj.get("write_ordinal", inj.get("flush_ordinal", 0))
        proc.stdin.write("\t".join(["C", str(case["case_index"]), case["operation"], case["shape"], case["mode"],
                                    inj["kind"], str(ordinal), str(inj.get("landed_bytes", 0))]) + "\n")
        proc.stdin.flush()
        o = json.loads(proc.stdout.readline())
        out.append(_obs2(index, "R29B", case["case_index"], o["post_snapshot"], _remount(o, "A")))
        index += 1
    proc.stdin.write("D\n")
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("R29-B worker failed")
    return out


# ------------------------------------------------------------------- row 3

def run_row3(first_index: int, tmp: Path) -> list[bytes]:
    image = tmp / "c69_record.img"
    image.write_bytes(C.fixture.record_fixture())
    out, index = [], first_index
    for rm in RECORD_MODES:
        for mode in MODES:
            raw = subprocess.run([str(BUILD / "wp10b_row3"), str(image), rm, mode],
                                 check=True, capture_output=True).stdout
            obs = json.loads(raw)
            obs["index"] = index
            out.append((canonical(obs) + "\n").encode())
            index += 1
    return out


# ------------------------------------------------------------------- run

def generate() -> tuple[bytes, dict]:
    r1 = list(row1_cases())
    for i, c in enumerate(r1):
        c["index"] = i
    c69, r29b = list(c69_cases()), list(r29b_cases())
    with tempfile.TemporaryDirectory(prefix="wp10b-") as t:
        tmp = Path(t)
        lines = run_row1(r1, tmp)
        # Row 1 objects carry their own index; normalise their key order like rows 2-3.
        lines = [(canonical(json.loads(line)) + "\n").encode() for line in lines]
        lines += run_row2(c69, r29b, len(r1), tmp)
        lines += run_row3(len(r1) + len(c69) + len(r29b), tmp)
    census = {"row1": len(r1), "row2": {"C69": len(c69), "R29B": len(r29b)},
              "row3_groups": len(RECORD_MODES) * len(MODES), "cases": len(lines)}
    return b"".join(lines), census


def write_gzip(data: bytes, dst: Path) -> None:
    with dst.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
        gz.write(data)


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
    """One digest over the four Software sources, in a fixed order."""
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
        out = fresh_dir(a.out or Path("build/wp10b-replay"))
        return run_replay(gz, out, product_commit, product_tree, ident["adapter_source_sha256"])

    out = fresh_dir(a.evidence)
    for name in ("wp10b_row1", "wp10b_row3", "wp10b_c69_worker", "wp10b_r29b_worker"):
        if not (BUILD / name).is_file():
            raise SystemExit("adapter not built: " + BUILD_COMMAND)
    data, census = generate()
    print(f"assembled {census['cases']} observations: row1 {census['row1']}, row2 {census['row2']}, "
          f"row3 {census['row3_groups']} groups")
    gz = out / "observations.jsonl.gz"
    write_gzip(data, gz)
    ident = {
        "schema": "wp10-backlog-r53-product-build-identity-1",
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
        "accepted_worker_origins": {
            "wp10b_c69_worker.c": "tests/crash_core_adapter/wp10_core_worker.c "
                                  "46ec919d5aed74c4e3364904afe8df01c18f12bff6c22ec6fd8d8b8ffc5acc0f + remount get_info",
            "wp10b_r29b_worker.c": "tests/format_dup_identity_adapter/r29_format_dup_worker.c "
                                   "c6a43b9d2df2668d11e036592142b79738e62502fdd01b974dc90d14b6d318cf, crash path only "
                                   "+ remount get_info",
            "wp10b_row1.c": "held PR #318 tests/wp10_closure_adapter/wp10c_adapter.c, per-device geometry "
                            "+ dst_chunk_lbas",
        },
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
