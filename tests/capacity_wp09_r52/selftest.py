#!/usr/bin/env python3
"""Exercise all 27 cells and prove the required verifier red controls."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from oracle import cases, check, decode_pcm, encode_pcm, plan_digest
from synthetic import observation, observations_bytes


def expect_red(name, case, obs):
    try:
        check(case, obs)
    except AssertionError:
        return
    raise AssertionError("red control survived: " + name)


def run():
    all_cases = cases()
    observations = [observation(case) for case in all_cases]
    for case, obs in zip(all_cases, observations):
        check(case, obs)

    # Untrusted labels have no effect on an oracle result.
    spoof = copy.deepcopy(observations[0])
    spoof["adapter_claimed_verdict"] = "FAIL"
    check(all_cases[0], spoof)

    controls = []

    wrong_count = copy.deepcopy(observations[0])
    wrong_count["calls"]["feed_steps"][-1]["accepted"] -= 1
    controls.append(("wrong accepted count", all_cases[0], wrong_count))

    corrupt = copy.deepcopy(observations[0])
    pcm = decode_pcm(corrupt["calls"]["render"]["pcm_zlib_b64"])
    pcm[-1] = (pcm[-1][0] + 1, pcm[-1][1])
    corrupt["calls"]["render"]["pcm_zlib_b64"] = encode_pcm(pcm)
    controls.append(("lost or corrupt accepted prefix", all_cases[0], corrupt))

    suffix = copy.deepcopy(observations[0])
    pcm = decode_pcm(suffix["calls"]["render"]["pcm_zlib_b64"])
    suffix["calls"]["render"]["pcm_zlib_b64"] = encode_pcm(pcm + [(222, -222)])
    controls.append(("invented suffix", all_cases[0], suffix))

    illegal = copy.deepcopy(observations[0])
    next(e for e in illegal["events"] if e["op"] == "write" and
         e["step"].startswith("service-"))["lba"] = 2048 + 1024
    controls.append(("illegal allocation below Side A", all_cases[0], illegal))

    feed_io = copy.deepcopy(observations[0])
    feed_io["events"].append({"step": "feed-final", "op": "read",
                              "ordinal": len(feed_io["events"]) + 1,
                              "rc": 0, "lba": 0, "count": 1})
    controls.append(("feed performed I/O", all_cases[0], feed_io))

    early = copy.deepcopy(observations[0])
    early["calls"]["premature_commit"]["result"] = "TAPE_OK"
    controls.append(("premature commit", all_cases[0], early))

    no_flush = copy.deepcopy(observations[0])
    commit_flushes = [i for i, e in enumerate(no_flush["events"])
                      if e["step"] == "commit" and e["op"] == "flush"]
    del no_flush["events"][commit_flushes[-1]]
    for ordinal, event in enumerate(no_flush["events"], 1):
        event["ordinal"] = ordinal
    controls.append(("absent final commit flush", all_cases[0], no_flush))

    for name, case, obs in controls:
        expect_red(name, case, obs)
    return {"cases": len(all_cases), "red_controls_killed": len(controls),
            "plan_sha256": plan_digest()}


def emit(directory):
    directory.mkdir(parents=False, exist_ok=False)
    plan = (json.dumps([asdict(case) for case in cases()], indent=2,
                       sort_keys=True) + "\n").encode()
    raw = observations_bytes()
    plan_path = directory / "plan.json"
    evidence_path = directory / "observations.jsonl.gz"
    plan_path.write_bytes(plan)
    with evidence_path.open("xb") as target:
        with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0,
                           compresslevel=9) as zipped:
            zipped.write(raw)
    sums = []
    for path in (plan_path, evidence_path):
        sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n")
    (directory / "SHA256SUMS").write_text("".join(sums))
    return {"observations_uncompressed_bytes": len(raw),
            "observations_compressed_bytes": evidence_path.stat().st_size,
            "observations_sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", type=Path)
    args = parser.parse_args()
    result = run()
    if args.emit:
        result.update(emit(args.emit))
    print("PASS", json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
