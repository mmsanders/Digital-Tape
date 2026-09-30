#!/usr/bin/env python3
"""Canonical Product run of the imported WP-12/WP-12a R53 closure-gap package.

Checks the declared import against history, writes each gap_plan case's device
image from the package's own fixture builders (fixtures.py, which loads the two
pinned, already-accepted builders), runs the separately built public-API
adapter on a fresh image per case, retains the observations and hands them to
the verifier's replay.py, which decides. The package oracle is never imported.

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
PACKAGE = ROOT / "tests" / "wp12_closure_r53"
PLAN = PACKAGE / "gap_plan.json"
ADAPTER_SRC = HERE / "wp12c_adapter.c"
ADAPTER_BIN = HERE / "build" / ("wp12c_adapter.exe" if os.name == "nt" else "wp12c_adapter")

VERIFIER_TREE = "5641e39d5b72f367468e2a8d121f6a0e6106fc2f"
VERIFIER_SOURCE = "c65ed4357c9d4b9fe915910e0a669d335e611a80"
PRODUCT_BASE = "66c6abc69d83cff10da32a6b446690fcd0b927fb"
IMPORT_COMMIT = "1c1c036"
PLAN_FILE_SHA256 = "e44e57c3dc1650f98c78d9b8012efcae1dacc071c76aa190aebf06f1223b3fd6"
BUILD_COMMAND = "make -C engine clean all && make -C tests/wp12_closure_adapter clean all"
BLOCK, CHUNK_BASE, CHUNK_BLOCKS = 512, 2048, 1024
SLOT_LBAS = (8, 136, 264, 392)

sys.path.insert(0, str(PACKAGE))
import fixtures as F  # noqa: E402  the package's fixture builders; not the oracle


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha(path.read_bytes())


def check_provenance() -> None:
    if git("rev-parse", "HEAD:tests/wp12_closure_r53") != VERIFIER_TREE:
        raise SystemExit("verifier tree at HEAD is not " + VERIFIER_TREE)
    imp = git("rev-parse", IMPORT_COMMIT)
    if git("rev-parse", imp + "^") != PRODUCT_BASE:
        raise SystemExit(f"import {imp} parent is not the declared base {PRODUCT_BASE}")
    if git("rev-parse", imp + ":tests/wp12_closure_r53") != VERIFIER_TREE:
        raise SystemExit(f"import {imp} does not carry tree {VERIFIER_TREE}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", imp, "HEAD"]).returncode:
        raise SystemExit(f"import {imp} is not an ancestor of HEAD")
    if sha256_file(PLAN) != PLAN_FILE_SHA256:
        raise SystemExit("gap_plan.json is not the published plan")


def media_image(m, audio_entries) -> bytearray:
    """A respool_draft8 Media as a whole device, with fixtures.chunk_audio in
    every chunk a live Side-B entry references."""
    img = bytearray(m.blocks * BLOCK)
    img[0:BLOCK] = m.primary
    img[(m.blocks - 1) * BLOCK:m.blocks * BLOCK] = m.mirror
    for lba, slot in zip(SLOT_LBAS, m.slots):
        img[lba * BLOCK:lba * BLOCK + len(slot)] = slot
    for c in F.referenced_chunks(audio_entries):
        off = (CHUNK_BASE + c * CHUNK_BLOCKS) * BLOCK
        img[off:off + CHUNK_BLOCKS * BLOCK] = F.chunk_audio(c)
    return img


def image_for(fixture: str) -> bytearray:
    if fixture in F.RENDER_FIXTURES:
        return media_image(F.render_media(fixture), F.RENDER_FIXTURES[fixture][1])
    if fixture == "respool_v3_003":
        return media_image(F.respool_fault_media(), [(10, 0, 2 * F.CF)])
    if fixture == "promote_fresh_alloc_full":
        initial = F.PF.scenario_initial("fresh_alloc_full")
        img = bytearray(F.PF.block_count(initial["total_chunks"]) * BLOCK)
        for lba, data in initial["blocks"].items():
            img[lba * BLOCK:lba * BLOCK + len(data)] = data
        return img
    raise KeyError(fixture)


def adapter_args(case: dict, image: Path) -> list[str]:
    if case["kind"] == "render":
        return [str(ADAPTER_BIN), "render", str(image)]
    inj = case["inject"]
    return [str(ADAPTER_BIN), "fault", str(image), case["op"], case["mount_side"],
            str(case["block_budget"]), inj["rule"], inj["op"], str(inj.get("call", -1)),
            str(inj.get("lba", 0)), str(inj.get("count", 0))]


def observe(case: dict, tmp: Path) -> tuple[bytes, dict]:
    image = tmp / f"{case['id']}.img"
    image.write_bytes(image_for(case["fixture"]))
    raw = subprocess.run(adapter_args(case, image), check=True, capture_output=True).stdout
    image.unlink()
    obs = json.loads(raw)
    metadata = bytes.fromhex(obs.pop("fixture_metadata_hex"))
    obs["fixture_metadata_sha256"] = sha(metadata)
    obs["schema"] = "wp12-r53-observation-v1"
    obs["case"] = case["id"]
    return (json.dumps(obs, sort_keys=True, separators=(",", ":")) + "\n").encode(), obs


def census(records: list[dict]) -> dict:
    """Observed facts per case, for reading the evidence. Not a verdict."""
    out = {}
    for o in records:
        if "respool" in o:
            out[o["case"]] = {
                "respool_calls": len(o["respool"]),
                "phases": {p: {"renders": len(o[p]["renders"]), "pcm_bytes": o[p]["pcm_bytes"],
                               "pcm_sha256": o[p]["pcm_sha256"], "tell": o[p]["tell"],
                               "render_results": sorted({r["result"] for r in o[p]["renders"]}),
                               "render_block_events": sum(len(r["block_events"]) for r in o[p]["renders"])}
                           for p in ("pre", "post_same_session", "post_remount")},
            }
        else:
            out[o["case"]] = {
                "calls": [[c["result"], c["more_work"], sum(1 for e in c["events"] if e["rc"])] for c in o["calls"]],
                "probe": [[p["column"], [c["result"] for c in p["calls"]], len(p["block_events"])] for p in o["probe"]],
                "device_unchanged": o["device_sha256_at_fault"] == o["device_sha256_before_unmount"],
            }
    return out


def write_gzip(data: bytes, dst: Path) -> None:
    dst.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))


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


def verify_retained(d: Path) -> bytes:
    sums = read_sums(d)
    for name in ("observations.jsonl.gz", "build-identity.json", "case-census.json"):
        if sha256_file(d / name) != sums[name]:
            raise SystemExit(f"retained {name} does not match its committed SHA-256")
    data = gzip.decompress((d / "observations.jsonl.gz").read_bytes())
    if sha(data) != sums["observations.jsonl"]:
        raise SystemExit("retained JSONL does not match its committed SHA-256")
    return data


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
        verify_retained(d)
        ident = json.loads((d / "build-identity.json").read_text())
        out = fresh_dir(a.out or Path("build/wp12-closure-replay"))
        return run_replay(d / "observations.jsonl.gz", out / "manifest.json",
                          product_commit, product_tree, ident["adapter_source_sha256"])

    out = fresh_dir(a.evidence)
    if not ADAPTER_BIN.is_file():
        raise SystemExit("adapter not built: " + BUILD_COMMAND)
    cases = json.loads(PLAN.read_text())["cases"]
    lines, records = [], []
    with tempfile.TemporaryDirectory(prefix="wp12c-") as tmp:
        for case in cases:
            line, obs = observe(case, Path(tmp))
            lines.append(line)
            records.append(obs)
    data = b"".join(lines)
    print(f"adapter emitted {len(cases)} case records")
    write_gzip(data, out / "observations.jsonl.gz")
    (out / "case-census.json").write_text(json.dumps(census(records), indent=2, sort_keys=True) + "\n", newline="\n")
    ident = {
        "schema": "wp12-r53-product-build-identity-1",
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
        "case_count": len(cases),
        "fixtures": "device images written from the package's fixtures.py builders; fixtures.chunk_audio in "
                    "every chunk a live Side-B entry references (render and respool_v3_003 fixtures)",
    }
    (out / "build-identity.json").write_text(json.dumps(ident, indent=2, sort_keys=True) + "\n", newline="\n")
    (out / "SHA256SUMS").write_text(
        f"{sha(data)}  observations.jsonl\n"
        + "".join(f"{sha256_file(out / n)}  {n}\n"
                  for n in ("observations.jsonl.gz", "build-identity.json", "case-census.json")),
        newline="\n")
    (out / "host.json").write_text(json.dumps({"product_commit": product_commit, "product_tree": product_tree,
                                               "head": head, "platform": platform.platform()},
                                              indent=2, sort_keys=True) + "\n", newline="\n")

    if a.retained:
        d = a.retained if a.retained.is_absolute() else ROOT / a.retained
        if verify_retained(d) != data:
            raise SystemExit("regenerated JSONL differs from the committed retained evidence")
        print("regenerated JSONL is byte-identical to the retained evidence")

    return run_replay(out / "observations.jsonl.gz", out / "manifest.json",
                      product_commit, product_tree, adapter_sha)


if __name__ == "__main__":
    raise SystemExit(main())
