#!/usr/bin/env python3
"""Build one adapter source with real GCC and Clang, then bind exact evidence."""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from oracle import SPEC_HASHES, observations_sha256, parse_jsonl
from vectors import plan_sha256, vectors, write_header, write_plan

FLAGS = ("-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-fno-strict-overflow")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compiler(path, family):
    resolved = shutil.which(path)
    if not resolved:
        raise SystemExit(f"required {family} compiler unavailable: {path}")
    identity = subprocess.run([resolved, "--version"], check=True, capture_output=True,
                              text=True).stdout.splitlines()[0]
    if family.lower() not in identity.lower():
        raise SystemExit(f"{path} did not identify as {family}: {identity}")
    return resolved, identity


def collect(gcc, clang):
    here = Path(__file__).resolve().parent
    gcc_path, gcc_identity = compiler(gcc, "gcc")
    clang_path, clang_identity = compiler(clang, "clang")
    with tempfile.TemporaryDirectory(prefix="wp08-r52-") as temporary:
        tmp = Path(temporary)
        header = tmp / "vectors.h"
        write_header(header)
        outputs = {}
        for family, executable in (("gcc", gcc_path), ("clang", clang_path)):
            binary = tmp / family
            command = [executable, *FLAGS, "-I", str(tmp),
                       str(here / "reference_adapter.c"), "-o", str(binary)]
            subprocess.run(command, check=True)
            outputs[family] = subprocess.run([str(binary)], check=True,
                                             capture_output=True).stdout
        if outputs["gcc"] != outputs["clang"]:
            raise AssertionError("cross-toolchain public evidence diverged")
        for raw in outputs.values():
            parse_jsonl(raw)
        metadata = {
            "gcc": {"identity": gcc_identity, "flags": list(FLAGS)},
            "clang": {"identity": clang_identity, "flags": list(FLAGS)},
            "adapter_sha256": digest(here / "reference_adapter.c"),
            "generated_header_sha256": digest(header),
        }
    return outputs, metadata


def gzip_bytes(raw):
    # gzip.compress with mtime=0 is deterministic and omits a source filename.
    return gzip.compress(raw, compresslevel=9, mtime=0)


def emit(directory, outputs, metadata, red_controls):
    if directory.exists():
        raise SystemExit("refusing to overwrite evidence directory")
    directory.mkdir()
    write_plan(directory / "plan.json")
    packed = {}
    for family in ("gcc", "clang"):
        packed[family] = gzip_bytes(outputs[family])
        (directory / f"{family}.jsonl.gz").write_bytes(packed[family])
    raw_sha = observations_sha256(outputs["gcc"])
    manifest = {
        "schema": "wp08-portability-r52-manifest-v1",
        "verdict": "PASS",
        "scope": "verifier reference adapter; not Product acceptance",
        "case_count": len(vectors()),
        "red_controls_killed": red_controls,
        "plan_sha256": plan_sha256(),
        "spec_sha256": SPEC_HASHES,
        "observations_sha256": raw_sha,
        "gcc_gzip_sha256": hashlib.sha256(packed["gcc"]).hexdigest(),
        "clang_gzip_sha256": hashlib.sha256(packed["clang"]).hexdigest(),
        "byte_identical_observations": outputs["gcc"] == outputs["clang"],
        **metadata,
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    paths = [directory / name for name in
             ("plan.json", "gcc.jsonl.gz", "clang.jsonl.gz", "manifest.json")]
    (directory / "SHA256SUMS").write_text("".join(
        f"{digest(path)}  {path.name}\n" for path in paths))
    return manifest
