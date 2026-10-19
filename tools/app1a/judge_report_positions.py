#!/usr/bin/env python3
"""#466: judge s1_report_positions.py records with Verification #209's imported,
unchanged oracle (tests/wp15_report_faults_r1). Prints each row's result; exit 1 if a
row with complete attempt capture is rejected. Rows without a qualified write
tracer are listed as not judgeable, never passed.

  judge_report_positions.py OUTDIR
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "wp15_report_faults_r1"))
import oracle  # noqa: E402

out = Path(sys.argv[1])
s = json.loads((out / "SUMMARY.json").read_text())
bad = 0
for row in s["rows"]:
    if "record" not in row:
        print(f"{row['fault_position']:7} UNEXECUTED: {row['reason']}")
        continue
    r = json.loads((out / row["record"]).read_text())
    nb = json.loads((out / row["neighbour"]).read_text())
    try:
        oracle.baseline(nb)
        nbv = "neighbour baseline accepted"
    except AssertionError as e:
        nbv = f"neighbour baseline REJECTED ({e})"
        bad += 1
    if not r["attempt_capture_complete"]:
        print(f"{row['fault_position']:7} not judgeable here (no qualified write tracer); {nbv}")
        continue
    try:
        print(f"{row['fault_position']:7} {oracle.writes(r)}; {nbv}")
    except AssertionError as e:
        print(f"{row['fault_position']:7} REJECTED by oracle.writes: {e}; {nbv}")
        bad += 1
sys.exit(1 if bad else 0)
