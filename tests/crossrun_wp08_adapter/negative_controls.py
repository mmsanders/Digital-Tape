#!/usr/bin/env python3
"""Red controls on the Product evidence itself. NOT the canonical run.

The package's selftest.py kills nine controls on synthetic observations. A green
Product replay also needs to show that the same oracle rejects *this adapter's*
output once one observed fact is wrong. Each control mutates one field of one
case in a copy of the retained Product JSONL and requires the verifier's own
oracle.check to reject it; the unmutated case must pass. Exits non-zero if any
control survives.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "crossrun_wp08_r44"))
from oracle import cases, check  # noqa: E402


def flip_pcm(o):
    r = o["variants"]["whole"]["renders"][0]
    h = r["pcm_hex"]
    r["pcm_hex"] = ("0" if h[0] != "0" else "1") + h[1:]


def tell_plus_one(o):
    o["variants"]["single"]["renders"][0]["tell"] += 1


def endpoint_flag(o):
    r = o["variants"]["uneven"]["renders"][-1]
    r["at_end"] = not r["at_end"]


def render_io(o):
    o["variants"]["whole"]["renders"][0]["block_events"] = [{"op": "read", "lba": 3072, "count": 1}]


def service_over_budget(o):
    s = o["variants"]["single"]["services"][0]
    s["events"] = s["events"] + [{"op": "read", "lba": 3072, "count": 1}]


def raw_pcm(o):
    lba = sorted(o["raw_media"]["chunks"])[0]
    h = o["raw_media"]["chunks"][lba]
    o["raw_media"]["chunks"][lba] = ("f" if h[0] != "f" else "e") + h[1:]


def incomplete_service(o):
    o["variants"]["whole"]["services"][-1]["more_work"] = True


CONTROLS = [flip_pcm, tell_plus_one, endpoint_flag, render_io, service_over_budget, raw_pcm,
            incomplete_service]
TARGET = "boundary-5+0-f"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path)
    a = ap.parse_args()
    by_id = {json.loads(line)["case"]: json.loads(line) for line in a.observations.read_text().splitlines()}
    case = next(c for c in cases() if c.id == TARGET)
    check(case, copy.deepcopy(by_id[TARGET]))
    survived = []
    for control in CONTROLS:
        obs = copy.deepcopy(by_id[TARGET])
        control(obs)
        try:
            check(case, obs)
            survived.append(control.__name__)
            print(f"SURVIVED {control.__name__}")
        except (AssertionError, KeyError, TypeError, ValueError) as e:
            print(f"killed   {control.__name__}: {e}")
    print(f"{len(CONTROLS) - len(survived)}/{len(CONTROLS)} Product-evidence controls killed on {TARGET}")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
