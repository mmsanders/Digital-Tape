#!/usr/bin/env python3
"""Canonical Product run of the imported #126 strengthening package (strengthen_r55).

Checks the declared import against history, builds every fixture image byte for
byte from the package's rows.py, runs the separately built public-API adapters
over every planned case, and hands the gzip JSONL to the verifier's own
replay.py, which decides. The package's oracle.py is never imported; its plan
order is restated below from rows.py and the capacity package's plan.json:

  row 1  rows.DUP_FRAMES x rows.DUP_DESTS        (str55_adapter dup)
  row 2  PASS2-RUN-SIDE-A                         (str55_adapter pass2)
  row 3  capacity_wp09_r52/evidence/plan.json     (str55_capacity, the #311 binding
                                                   with a six-key raw_before)

  --evidence DIR   fresh output directory (refuses to reuse one)
  --retained DIR   also require the fresh JSONL to equal the committed SHA-256
  --replay DIR     offline: verify the retained evidence and replay it, no adapter
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
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / "tests" / "strengthen_r55"
CAPACITY = ROOT / "tests" / "capacity_wp09_r52"
CAP_PLAN = CAPACITY / "evidence" / "plan.json"
BUILD = HERE / "build"
SOURCES = ("str55_adapter.c", "str55_capacity.c")

VERIFIER_TREE = "72d24675fc40432c29d7f225bac3169124e5d12f"
CAPACITY_TREE = "4c754247d2769a9033d7b921cbd248e3e943b62a"
VERIFIER_SOURCE = "7a914cd7c76bcc933e896a26fa0b3b7349c11b2d"
PRODUCT_BASE = "00c69783143bbb736e9c53598799baaa67ee0d39"
IMPORT_COMMIT = "6feb6fe"
CASESET_SHA256 = "9ee1c5d6083dda0e9fd3f331a56dbc4903d659a157daa91615ff30212101ebea"
CAP_PLAN_SHA256 = "ceacb2e064ef3550774064e94580397f213614fa834d7b82b0fdcb2a91b44501"
BUILD_COMMAND = "make -C engine clean all && make -C tests/strengthen_r55_adapter clean all"
SCHEMA = "strengthen-r55-observation-v1"

sys.path.insert(0, str(PACKAGE))
import rows as R  # noqa: E402  fixture builders; not the oracle

# capacity_wp09_r52/ADAPTER.md inputs, restated as the #311 binding does (run_product.py there).
CHUNK_FRAMES = 131072
FREE_NEXT = 3
MODES = ("overwrite", "overdub", "splice")
POSITIONS = ("start", "middle", "end")
SHAPES = ("one-free-one-left", "two-free-seventeen-left", "three-free-4095-left")


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
    for sub, tree in (("tests/strengthen_r55", VERIFIER_TREE), ("tests/capacity_wp09_r52", CAPACITY_TREE)):
        if git("rev-parse", "HEAD:" + sub) != tree:
            raise SystemExit(f"{sub} at HEAD is not {tree}")
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    for sub, tree in (("tests/strengthen_r55", VERIFIER_TREE), ("tests/capacity_wp09_r52", CAPACITY_TREE)):
        if git("rev-parse", f"{imp}:{sub}") != tree:
            raise SystemExit(f"import {imp} does not carry {sub} {tree}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")
    if sha256_file(CAP_PLAN) != CAP_PLAN_SHA256:
        raise SystemExit("capacity plan.json is not the published plan")


# ------------------------------------------------------------------- plan

def cases():
    idx = 0
    for frames in R.DUP_FRAMES:
        for dest in R.DUP_DESTS:
            yield {"index": idx, "row": 1, "kind": "dup_audio", "frames": frames, "destination": dest}
            idx += 1
    yield {"index": idx, "row": 2, "kind": "respool_pass2_run", "fixture": "PASS2-RUN-SIDE-A"}
    idx += 1
    for row in json.loads(CAP_PLAN.read_text()):
        yield {"index": idx, "row": 3, "kind": "capacity_premise", "capacity_case": row["id"]}
        idx += 1


def caseset_sha256(plan: list) -> str:
    h = hashlib.sha256()
    for c in plan:
        h.update((canonical(c) + "\n").encode())
    return h.hexdigest()


# ------------------------------------------------------------------- run

def exe(name: str) -> Path:
    return BUILD / (name + ".exe" if os.name == "nt" else name)


def capacity_observation(row: dict) -> dict:
    """capacity_wp09_r52/ADAPTER.md, exactly as the #311 binding runs it, on str55_capacity."""
    code = 100 * MODES.index(row["mode"]) + 10 * POSITIONS.index(row["position"]) + SHAPES.index(row["shape"])
    prefill = (row["total_chunks"] - FREE_NEXT) * CHUNK_FRAMES - row["final_accepted"]
    args = [str(exe("str55_capacity")), row["mode"], str(row["at"]), str(row["total_chunks"]), str(prefill),
            str(row["final_requested"]), str(row["service_budget"]), str(1000 + code), str(-1000 - code)]
    obs = json.loads(subprocess.run(args, check=True, capture_output=True).stdout)
    pcm = bytes.fromhex(obs["calls"]["render"].pop("pcm_hex"))
    obs["calls"]["render"]["pcm_zlib_b64"] = base64.b64encode(zlib.compress(pcm, 9)).decode()
    obs["case"] = row["id"]
    obs["capacity_case"] = row["id"]
    obs["fixture_sha256"] = sha(canonical(obs["raw_before"]).encode())
    return obs


def generate() -> tuple[bytes, dict]:
    plan = list(cases())
    if caseset_sha256(plan) != CASESET_SHA256:
        raise SystemExit("restated plan does not match the package's recorded case set")
    cap_rows = {r["id"]: r for r in json.loads(CAP_PLAN.read_text())}
    lines = []
    with tempfile.TemporaryDirectory(prefix="str55-") as t:
        tmp = Path(t)
        for c in plan:
            out = tmp / f"obs{c['index']}.json"
            if c["row"] == 1:
                src, dst = tmp / f"src{c['frames']}.img", tmp / f"dst_{c['destination']}.img"
                if not src.exists():
                    src.write_bytes(R.dup_source_image(c["frames"]))
                if not dst.exists():
                    dst.write_bytes(R.dup_destination_image(c["destination"]))
                subprocess.run([str(exe("str55_adapter")), "dup", str(src), str(dst), str(c["frames"]),
                                R.B.FRESH_DUP_UUID.hex(), str(R.B.NOMINAL_LENGTH_S), str(out)], check=True)
                obs = json.loads(out.read_bytes())
                obs.update(frames=c["frames"], destination=c["destination"])
            elif c["row"] == 2:
                img = tmp / "pass2.img"
                img.write_bytes(R.pass2_image())
                subprocess.run([str(exe("str55_adapter")), "pass2", str(img), str(out)], check=True)
                obs = json.loads(out.read_bytes())
                obs["fixture"] = c["fixture"]
            else:
                obs = capacity_observation(cap_rows[c["capacity_case"]])
            obs.update(schema=SCHEMA, index=c["index"], row=c["row"], kind=c["kind"])
            lines.append((canonical(obs) + "\n").encode())
    census = {"cases": len(lines)}
    for r in (1, 2, 3):
        census[f"row{r}"] = sum(c["row"] == r for c in plan)
    p2 = json.loads(lines[census["row1"]])
    census["row2_respool_calls"] = len(p2["calls"])
    census["row2_metadata_writes"] = sum(1 for e in p2["events"] if "data" in e)
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
        out = fresh_dir(a.out or Path("build/str55-replay"))
        return run_replay(gz, out, product_commit, product_tree, ident["adapter_source_sha256"])

    out = fresh_dir(a.evidence)
    for name in ("str55_adapter", "str55_capacity"):
        if not exe(name).is_file():
            raise SystemExit("adapter not built: " + BUILD_COMMAND)
    data, census = generate()
    print(f"assembled {census['cases']} observations: {census}")
    gz = out / "observations.jsonl.gz"
    write_gzip(data, gz)
    ident = {
        "schema": "strengthen-r55-product-build-identity-1",
        "verifier_tree": VERIFIER_TREE,
        "capacity_verifier_tree": CAPACITY_TREE,
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
        "adapter_origin": "str55_adapter.c: device and render shapes from tests/wp10_final_adapter/wp10f_adapter.c "
                          "(#334), row 1-2 drivers new; str55_capacity.c: tests/capacity_wp09_adapter/"
                          "capacity_adapter.c (#311) with A0/A1 added to raw_before",
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
