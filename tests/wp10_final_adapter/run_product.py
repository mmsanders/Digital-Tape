#!/usr/bin/env python3
"""Canonical Product run of the imported WP-10 final backlog package (#118).

Checks the declared import against history, writes the adapter's input (fixture
images from the package's model.py / dupmodel.py and the planned case list),
runs the separately built public-API adapter over every case, and hands the gzip
JSONL to the verifier's own replay.py, which decides. The package's oracle.py is
never imported; its plan order is restated below from model.py / dupmodel.py:

  row 1  model.ROW1 keys          row 2  model.ROW2 keys
  row 3  model.ROW3 keys          row 4  model.rerun_representatives() x
                                         dupmodel.injections(dupmodel.dup_ops(crashed))

The gzip is over 1 MiB, so it is a release asset (CLAUDE.md §4). Its SHA-256 is
committed in SHA256SUMS; --replay fetches it when absent and refuses a mismatch.

  --evidence DIR   fresh output directory (refuses to reuse one)
  --retained DIR   also require the fresh JSONL to equal the committed SHA-256
  --replay DIR     offline: verify the retained evidence (fetching the asset if
                   needed) and replay it, no adapter
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
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / "tests" / "wp10_final_r54"
BUILD = HERE / "build"
SOURCES = ("wp10f_adapter.c",)

VERIFIER_TREE = "598ebcd8f0914040558f565809b90bdb22bb8221"
VERIFIER_SOURCE = "7c0410e0042d00c05b72affccd4de0a03ce8abd6"
PRODUCT_BASE = "d1ef20292c443ec55be2c32945f3171b8d7ec04d"
IMPORT_COMMIT = "f5ffeef"
CASESET_SHA256 = "159b4ac64a5e653df2625a025f5f8cf13bcb90fed9a11905a1733f7a97167cd1"
BUILD_COMMAND = "make -C engine clean all && make -C tests/wp10_final_adapter clean all"
RELEASE_TAG = "evidence-p1-r55-wp10-final"
ASSET = "wp10-final-r54-product-observations.jsonl.gz"
ASSET_URL = f"https://github.com/mmsanders/Digital-Tape/releases/download/{RELEASE_TAG}/{ASSET}"

sys.path.insert(0, str(PACKAGE))
import model as M  # noqa: E402  fixtures and transactions; not the oracle
import dupmodel as DM  # noqa: E402

B = DM.B


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
    if git("rev-parse", "HEAD:tests/wp10_final_r54") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/wp10_final_r54") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")


# ------------------------------------------------------------------- plan

def cases():
    idx = 0
    for cid in M.ROW1:
        yield {"index": idx, "row": 1, "kind": "contract", "case": cid}
        idx += 1
    for cid in M.ROW2:
        yield {"index": idx, "row": 2, "kind": "contract", "case": cid}
        idx += 1
    for fid in M.ROW3:
        yield {"index": idx, "row": 3, "kind": "respool_render", "fixture": fid}
        idx += 1
    for rep in M.rerun_representatives():
        for mode, inject in DM.injections(DM.dup_ops(rep["crashed"])):
            yield {"index": idx, "row": 4, "kind": "rerun_crash", "shape": rep["shape"], "class": rep["class"],
                   "first_mode": rep["first_mode"], "first_inject": rep["first_inject"],
                   "mode": mode, "inject": list(inject)}
            idx += 1


def caseset_sha256(plan: list) -> str:
    h = hashlib.sha256()
    for c in plan:
        h.update((canonical(c) + "\n").encode())
    return h.hexdigest()


# ------------------------------------------------------------------- fixtures

def image_blocks(image: bytes) -> dict:
    n = len(image) // M.BLOCK
    return {lba: image[lba * M.BLOCK:(lba + 1) * M.BLOCK] for lba in range(n)}


def tracked_blocks(img: dict) -> dict:
    return {DM.TRACKED[n]: d for n, d in img.items()}


def source_128() -> dict:
    """#116 ADAPTER.md row 2's source: a fresh 4-chunk / 9 s cartridge (the pinned R29-B
    builder), generation 1, a_high_water 1, Side A {0,0,128}, Side B a valid empty
    index, chunk 0 block 0 = SOURCE_AUDIO. Identical to the #330 binding's src128."""
    sb = DM.with_label(B.superblock(generation=1, uuid=B.OLD_UUID_A, high=1), b"")
    a_h, a_e = DM.index_blocks(0, 1, [(0, 0, 128)])
    b_h, _ = DM.index_blocks(1, 2, [])
    return {0: sb, B.LBA_MIRROR: sb, B.LBA_A0: a_h, B.LBA_A0 + 1: a_e, B.LBA_B0: b_h,
            B.LBA_CHUNK_BASE: DM.SOURCE_AUDIO}


def fixture_lines(name: str, count: int, blocks: dict) -> list[str]:
    if len(name) > 95:
        raise SystemExit("fixture name too long for the adapter: " + name)
    zero = bytes(M.BLOCK)
    items = [(lba, data) for lba, data in sorted(blocks.items()) if data != zero]
    return [f"FIXTURE {name} {count} {len(items)}"] + [f"{lba} {data.hex()}" for lba, data in items]


def inject_tokens(inject) -> str:
    return " ".join(str(x) for x in inject)


def adapter_input(plan: list) -> str:
    names = sorted(DM.TRACKED)
    lines = ["TRACKED %d " % len(names) + " ".join(str(DM.TRACKED[n]) for n in names),
             f"DUP {B.FRESH_DUP_UUID.hex()} {B.NOMINAL_LENGTH_S}"]
    c69_blocks = M.F.BLOCK_COUNT
    for cid, (spec, *_rest) in M.ROW1.items():
        lines += fixture_lines("c_" + cid, c69_blocks, image_blocks(M.row1_image(spec)))
    for cid, (args, *_rest) in M.ROW2.items():
        lines += fixture_lines("c_" + cid, c69_blocks, image_blocks(M.row2_image(args)))
    for fid in M.ROW3:
        lines += fixture_lines("r3_" + fid, c69_blocks, image_blocks(M.row3_image(fid)))
    for shape in DM.RERUN_SHAPES:
        lines += fixture_lines("dst_" + shape, B.BLOCK_COUNT, tracked_blocks(DM.rerun_destination(shape)))
    lines += fixture_lines("src128", B.BLOCK_COUNT, source_128())
    for c in plan:
        if c["row"] == 1:
            spec, side, fn, *_ = M.ROW1[c["case"]]
            lines.append(f"CASE {c['index']} 1 {c['case']} {side} {fn}")
        elif c["row"] == 2:
            lines.append(f"CASE {c['index']} 2 {c['case']} B tape_respool")
        elif c["row"] == 3:
            lines.append(f"CASE {c['index']} 3 {c['fixture']}")
        else:
            cls1 = "null" if c["class"][1] is None else c["class"][1]
            lines.append(f"CASE {c['index']} 4 {c['shape']} {c['class'][0]} {cls1} {c['first_mode']} "
                         f"{inject_tokens(c['first_inject'])} {c['mode']} {inject_tokens(c['inject'])}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------- run

def generate() -> tuple[bytes, dict]:
    plan = list(cases())
    if caseset_sha256(plan) != CASESET_SHA256:
        raise SystemExit("restated plan does not match the package's recorded case set")
    with tempfile.TemporaryDirectory(prefix="wp10f-") as t:
        tmp = Path(t)
        (tmp / "cases.in").write_text(adapter_input(plan), newline="\n")
        exe = BUILD / ("wp10f_adapter.exe" if os.name == "nt" else "wp10f_adapter")
        subprocess.run([str(exe), str(tmp / "cases.in"), str(tmp / "obs.jsonl")], check=True)
        raw = (tmp / "obs.jsonl").read_bytes().splitlines()
    lines = [(canonical(json.loads(line)) + "\n").encode() for line in raw]
    census = {"cases": len(lines)}
    for r in (1, 2, 3, 4):
        census[f"row{r}"] = sum(c["row"] == r for c in plan)
    census["row4_by_mode"] = {m: sum(c["row"] == 4 and c["mode"] == m for c in plan)
                              for m in ("flush_required", "write_through")}
    census["row3_injections"] = sum(len(json.loads(l)["crashes"]) for l in lines if json.loads(l)["row"] == 3)
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


def retained_gzip(retained: Path) -> Path:
    """The retained gzip: local if present, else fetched from the release asset;
    refused unless it hashes to the committed SHA-256."""
    sums = read_sums(retained / "SHA256SUMS")
    gz = retained / ASSET
    if not gz.exists():
        print(f"fetch {ASSET_URL}")
        with urllib.request.urlopen(ASSET_URL) as r:
            data = r.read()
        if sha(data) != sums[ASSET]:
            raise SystemExit("REFUSED: the fetched asset does not hash to the committed SHA-256")
        gz.write_bytes(data)
    if sha256_file(gz) != sums[ASSET]:
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
        gz = retained_gzip(retained)
        ident = json.loads((retained / "build-identity.json").read_text())
        out = fresh_dir(a.out or Path("build/wp10f-replay"))
        return run_replay(gz, out, product_commit, product_tree, ident["adapter_source_sha256"])

    out = fresh_dir(a.evidence)
    exe = BUILD / ("wp10f_adapter.exe" if os.name == "nt" else "wp10f_adapter")
    if not exe.is_file():
        raise SystemExit("adapter not built: " + BUILD_COMMAND)
    data, census = generate()
    print(f"assembled {census['cases']} observations: {census}")
    gz = out / ASSET
    write_gzip(data, gz)
    ident = {
        "schema": "wp10-final-r54-product-build-identity-1",
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
        "release_asset": ASSET_URL,
        "adapter_origin": "tests/wp10_backlog_r54_adapter/wp10r54_adapter.c (#330) device, settling, "
                          "remounts and dup runner; row 1-4 case drivers new",
    }
    (out / "build-identity.json").write_text(json.dumps(ident, indent=2, sort_keys=True) + "\n", newline="\n")
    sums = {"observations.jsonl": sha(data), ASSET: sha256_file(gz),
            "build-identity.json": sha256_file(out / "build-identity.json")}
    (out / "SHA256SUMS").write_text("".join(f"{v}  {k}\n" for k, v in sums.items()), newline="\n")
    cc = subprocess.run([os.environ.get("CC", "cc"), "--version"], capture_output=True, text=True)
    (out / "host.json").write_text(json.dumps({
        "product_commit": product_commit, "product_tree": product_tree, "head": head,
        "cc": (cc.stdout.splitlines() or ["unknown"])[0], "platform": platform.platform(),
        "python": platform.python_version(),
    }, indent=2, sort_keys=True) + "\n", newline="\n")
    print(f"observations.jsonl {len(data)} bytes {sums['observations.jsonl']}; gzip {gz.stat().st_size} bytes "
          f"{sums[ASSET]}")

    if a.retained:
        retained = a.retained if a.retained.is_absolute() else ROOT / a.retained
        want = read_sums(retained / "SHA256SUMS")
        if want["observations.jsonl"] != sums["observations.jsonl"]:
            raise SystemExit("regenerated JSONL differs from the committed SHA-256")
        print("regenerated JSONL is byte-identical to the committed SHA-256")

    return run_replay(gz, out, product_commit, product_tree, ident["adapter_source_sha256"])


if __name__ == "__main__":
    raise SystemExit(main())
