#!/usr/bin/env python3
"""Per-row census and red controls on the Product evidence. NOT canonical.

Runs the package's own oracle.check on every case of the retained stream and
prints the per-row outcome census and the V-R54-03 count, then requires
oracle.check to reject single-fact mutations of this Product's own passing
observations, one per assertion family. Exit status: 1 if any case fails or
any control survives.
"""
from __future__ import annotations

import argparse
import collections
import copy
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "wp10_final_r54"))
import oracle as O  # noqa: E402


def outcome(case, obs):
    try:
        O.check(case, obs)
        return None
    except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
        return str(e) or type(e).__name__


# rows 1-2
def contract_wrong_result(o):
    o["call"]["result"] = "TAPE_OK" if o["call"]["result"] != "TAPE_OK" else "TAPE_ERR_SEQUENCE_EXHAUSTED"


def contract_write_on_refusal(o):
    o["events"] = o["events"] + [{"op": "write", "lba": 264, "count": 1}]


def contract_side_a_changed(o):
    h = o["after_raw"]["A0"]
    o["after_raw"]["A0"] = ("1" if h[0] == "0" else "0") + h[1:]


# row 3
def row3_crash_wrong_audio(o):
    o["crashes"][0]["remount_B"]["pcm_sha256"] = "0" * 64


def row3_missing_crash(o):
    o["crashes"] = o["crashes"][:-1]


def row3_side_a_changed(o):
    o["crashes"][-1]["remount_A"]["pcm_sha256"] = "0" * 64


# row 4
def row4_trace(o):
    o["trace_sha256"] = "0" * 64


def row4_durable(o):
    o["durable_sha256"] = "0" * 64


def row4_source_written(o):
    o["source_sha256_after"] = "0" * 64


def row4_first_state(o):
    o["first_durable_sha256"] = "0" * 64


CONTROLS = {
    "contract_refusal": [contract_wrong_result, contract_write_on_refusal],
    "contract_ok": [contract_side_a_changed],
    3: [row3_crash_wrong_audio, row3_missing_crash, row3_side_a_changed],
    4: [row4_trace, row4_durable, row4_source_written, row4_first_state],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl.gz")
    a = ap.parse_args()
    census: collections.Counter = collections.Counter()
    reasons: collections.Counter = collections.Counter()
    findings = O.new_findings()
    first = {}
    failing = 0
    with gzip.open(a.observations, "rt", encoding="utf-8") as f:
        for case, line in zip(O.iter_cases(), f):
            obs = json.loads(line)
            try:
                O.check(case, obs, findings=findings)
                why = None
            except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
                why = str(e) or type(e).__name__
            census[(case["row"], "PASS" if why is None else "FAIL")] += 1
            if why is not None:
                failing += 1
                reasons[(case["row"], why[:120])] += 1
                continue
            if case["row"] in (1, 2):
                key = "contract_ok" if obs["call"]["result"] == "TAPE_OK" and obs["events"] else "contract_refusal"
                if obs["call"]["result"] != "TAPE_OK" and key not in first:
                    first[key] = (case, obs)
                elif key == "contract_ok" and key not in first:
                    first[key] = (case, obs)
            elif case["row"] not in first:
                first[case["row"]] = (case, obs)
    for k, v in sorted(census.items()):
        print(f"row{k[0]} {k[1]} {v}")
    for (row, why), v in sorted(reasons.items()):
        print(f"  row{row}: {v} x {why}")
    print(f"V-R54-03 cells: {findings['v_r54_03_resurrected_previous_superblock']}; failing cases: {failing}")

    survived, total = [], 0
    for key, fns in CONTROLS.items():
        case, obs = first[key]
        for fn in fns:
            total += 1
            m = copy.deepcopy(obs)
            fn(m)
            why = outcome(case, m)
            print(("killed   " if why else "SURVIVED ") + f"case {case['index']}/{fn.__name__}: {why}")
            if why is None:
                survived.append(fn.__name__)
    print(f"{total - len(survived)}/{total} Product-evidence controls killed")
    return 1 if survived or failing else 0


if __name__ == "__main__":
    raise SystemExit(main())
