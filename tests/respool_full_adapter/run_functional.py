#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "tests" / "respool_full_draft8"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(HERE))

from fixture import BASE, clean_cases, empty_at  # noqa: E402
from oracle import validate_clean_case, validate_longop_contract, validate_zero_needed_empty  # noqa: E402
from media_image import build_raw_image  # noqa: E402

OLD_PROBE = ROOT / "tests" / "respool_adapter" / "build" / "wp12_respool_probe"
LONGOP = HERE / "build" / "respool_longop_probe"
EXPECTED_TREE = "5637fbd3e89316889b4bbd52d2a72c95e3c278e1"
IMPORT_COMMIT = "895351d17de9332e0804140858049d3608eeecd4"
PRODUCT_BASE = "8276d8f22da34a53f9f52dae8d3bd1acb3c763d9"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_clean(case, tmp: Path) -> dict:
    inp = tmp / f"{case.id}.in.vo08"
    out = tmp / f"{case.id}.out.vo08"
    inp.write_bytes(case.pre.encode())
    proc = subprocess.run(
        [str(OLD_PROBE), case.id, str(inp), str(out)],
        cwd=ROOT, text=True, capture_output=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{case.id}: old product probe exit {proc.returncode}: {proc.stderr}")
    obs = json.loads(proc.stdout)
    post = BASE.Media.decode(out.read_bytes())
    validate_clean_case(case, post, obs["events"], obs["calls"])
    return {
        "case": case.id,
        "input_sha256": hashlib.sha256(case.pre.encode()).hexdigest(),
        "output_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "observation_sha256": hashlib.sha256(
            json.dumps(obs, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def run_zero_needed(name: str, pre, tmp: Path) -> dict:
    inp = tmp / f"{name}.in.vo08"
    out = tmp / f"{name}.out.vo08"
    inp.write_bytes(pre.encode())
    proc = subprocess.run(
        [str(OLD_PROBE), name, str(inp), str(out)],
        cwd=ROOT, text=True, capture_output=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{name}: probe exit {proc.returncode}: {proc.stderr}")
    obs = json.loads(proc.stdout)
    post = BASE.Media.decode(out.read_bytes())
    calls = [c for c in obs["calls"] if c.get("fn") == "tape_respool"]
    if len(calls) != 1:
        raise RuntimeError(f"{name}: expected one respool call")
    validate_zero_needed_empty(pre, post, obs["events"], calls[0])
    return {
        "case": name,
        "sequence": BASE.cartridge_sequence(pre),
        "sb_generation": int.from_bytes(BASE.select_sb(pre)[12:16], "little"),
        "output_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, required=True)
    args = ap.parse_args()

    evidence = args.evidence if args.evidence.is_absolute() else ROOT / args.evidence
    evidence.mkdir(parents=True, exist_ok=True)
    head = git("rev-parse", "HEAD")
    product_commit = os.environ.get("PRODUCT_COMMIT") or head
    if product_commit != head:
        raise SystemExit(f"workspace/head mismatch {head} != {product_commit}")
    tree = git("rev-parse", "HEAD^{tree}")
    verifier_tree = git("rev-parse", "HEAD:tests/respool_full_draft8")
    if verifier_tree != EXPECTED_TREE:
        raise SystemExit(f"verifier tree mismatch: {verifier_tree}")
    if not OLD_PROBE.is_file() or not LONGOP.is_file():
        raise SystemExit("functional probe binaries missing")

    summary = {
        "format": "WP10-RESPOOL-FUNCTIONAL-1",
        "product_base": PRODUCT_BASE,
        "product_commit": product_commit,
        "product_tree": tree,
        "verifier_import_commit": IMPORT_COMMIT,
        "verifier_tree": verifier_tree,
        "clean_cases": [],
        "zero_needed": [],
        "longop": None,
        "status": "FAIL",
    }

    try:
        with tempfile.TemporaryDirectory(prefix="respool-functional-") as td:
            tmp = Path(td)
            for case in clean_cases():
                summary["clean_cases"].append(run_clean(case, tmp))

            # Both independent counter domains are deliberately at the reserved
            # value on a branch that consumes neither. No headroom may be read.
            summary["zero_needed"].append(
                run_zero_needed("WP12-ZERO-NEEDED-RESERVED",
                                empty_at(0xFFFFFFFF, 0xFFFFFFFF), tmp)
            )
            summary["zero_needed"].append(
                run_zero_needed("WP12-ZERO-NEEDED-NEAR-CAP",
                                empty_at(0xFFFFFFFD, 0xFFFFFFFD), tmp)
            )

            raw = tmp / "longop.raw"
            build_raw_image("v3_003", "pass1", raw)
            proc = subprocess.run(
                [str(LONGOP), str(raw)],
                cwd=ROOT, text=True, capture_output=True, timeout=180,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"longop probe exit {proc.returncode}: {proc.stderr}")
            obs = json.loads(proc.stdout)
            summary["longop"] = obs
            validate_longop_contract(obs)

        summary["status"] = "PASS"
        (evidence / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n"
        )
        print("PASS re-spool clean/headroom + WP-12a long-op contract")
        return 0
    except Exception as exc:
        summary["failure"] = f"{type(exc).__name__}: {exc}"
        (evidence / "functional-failure.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n"
        )
        print(f"FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
