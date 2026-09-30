#!/usr/bin/env python3
"""Require two real toolchains and kill the WP-08 R52 causal controls."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from oracle import check, parse_jsonl
from mutants import MUTANTS, legacy_model, record_for
from oracle import model
from toolchains import collect, emit
from vectors import vectors


def expect_red(name, vector, record):
    try:
        check(vector, record)
    except AssertionError:
        return
    raise AssertionError("red control survived: " + name)


def run_controls(raw):
    plan = vectors()
    records = parse_jsonl(raw)
    by_id = {vector.id: (vector, record) for vector, record in zip(plan, records)}
    controls = []

    def changed_pcm(case, start=8):
        vector, record = by_id[case]
        bad = copy.deepcopy(record)
        value = bad["pcm_hex"]
        pivot = min(start, max(0, len(value) - 1))
        replacement = "0" if value[pivot] != "0" else "1"
        bad["pcm_hex"] = value[:pivot] + replacement + value[pivot + 1:]
        return vector, bad

    controls.append(("negative fractional floor rounding", *changed_pcm("extrema-down-half")))
    controls.append(("signed interpolation overflow or wrap", *changed_pcm("extrema-up-three-quarter", 16)))

    vector, record = by_id["multirun-intmin-reverse"]
    bad = copy.deepcopy(record); bad["tell"] = bad["tell"] + 1
    controls.append(("INT32_MIN handling", vector, bad))

    vector, record = by_id["one-intmax-forward"]
    bad = copy.deepcopy(record); bad["at_end"] = False
    controls.append(("INT32_MAX clamp", vector, bad))

    controls.append(("reverse-from-end grid snap", *changed_pcm("end-reverse-grid", 0)))
    controls.append(("stale run sample", *changed_pcm("run-7+0-f", 0)))

    vector, record = by_id["end-forward"]
    bad = copy.deepcopy(record); bad["trace"][-1]["at_end"] = False
    controls.append(("endpoint flag drift", vector, bad))

    vector, record = by_id["tiny-positive"]
    bad = copy.deepcopy(record); bad["trace"][-2]["value"] += 1
    controls.append(("tell drift", vector, bad))

    for name, vector, record in controls:
        expect_red(name, vector, record)

    def write_during_mount(r):
        r["trace"][0]["block_events"].append({"count": 1, "lba": 0, "op": "write", "rc": 0})

    def flush_during_service(r):
        r["trace"][3]["block_events"].append({"op": "flush", "rc": 0})

    def read_on_render(r):
        r["trace"][4]["block_events"].append({"count": 1, "lba": 2048, "op": "read", "rc": 0})

    def out_of_range_read(r):
        r["trace"][0]["block_events"].append({"count": 1, "lba": r["block_count"], "op": "read", "rc": 0})

    def mount_skips_superblock(r):
        r["trace"][0]["block_events"] = [e for e in r["trace"][0]["block_events"] if e.get("lba") != 0]

    for mutate in (write_during_mount, flush_during_service, read_on_render,
                   out_of_range_read, mount_skips_superblock):
        for vector in plan:
            bad = copy.deepcopy(by_id[vector.id][1])
            mutate(bad)
            expect_red(f"{mutate.__name__} on {vector.id}", vector, bad)
        controls.append((mutate.__name__, None, None))

    regression = "reverse-end-acceptance-0-1000-2000"
    for name, config in MUTANTS.items():
        affected = [v.id for v in plan if legacy_model(v, **config) != model(v)]
        if regression not in affected:
            raise AssertionError("mutant does not reach acceptance regression: " + name)
        for case in affected:
            vector, record = by_id[case]
            expect_red(f"{name} on {case}",
                       vector, record_for(vector, legacy_model(vector, **config), record))
        controls.append((name, None, None))

    def require_same(left, right):
        if left != right:
            raise AssertionError("cross-toolchain public evidence diverged")

    require_same(raw, raw)
    try:
        require_same(raw, raw + b"\n")
    except AssertionError:
        pass
    else:
        raise AssertionError("cross-toolchain divergence control survived")
    return len(controls) + 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gcc", default="gcc")
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--emit", type=Path)
    args = parser.parse_args()
    outputs, metadata = collect(args.gcc, args.clang)
    red_controls = run_controls(outputs["gcc"])
    result = {"cases": len(vectors()), "red_controls_killed": red_controls,
              "gcc": metadata["gcc"]["identity"],
              "clang": metadata["clang"]["identity"],
              "byte_identical": outputs["gcc"] == outputs["clang"]}
    if args.emit:
        result["manifest"] = emit(args.emit, outputs, metadata, red_controls)
    print("PASS", json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
