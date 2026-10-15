#!/usr/bin/env python3
"""Software's observation summary of one Stage1 packet. NOT a disposition: it reports
which observed exits differ from the census descriptors, which cases this platform
could not set up, and whether the shipping binary reproduced every success's bytes.

Exit status is nonzero only for a Software defect the job should not hide: an
observed exit that differs from its descriptor on a case that actually ran, a
shipping/observation byte difference, or a missing census record. Unavailable cases
(no native method on this platform) are listed, not failed -- and they are never PASS.

usage: summarize_packet.py PACKET --package tests/wp16_ingest_stage1
"""
import argparse, json, sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("packet")
    ap.add_argument("--package", required=True)
    a = ap.parse_args()
    root = Path(a.packet)
    index = json.loads((root / "INDEX.json").read_text(encoding="utf-8"))
    census = json.loads(Path(a.package, "CENSUS.json").read_text(encoding="utf-8"))["cases"]
    missing, mismatch, unavailable, notequiv, ran = [], [], [], [], 0
    for c in census:
        path = index["cases"].get(c["id"])
        if not path:
            missing.append(c["id"])
            continue
        rec = json.loads((root / path).read_text(encoding="utf-8"))
        if rec.get("unavailable"):
            unavailable.append((c["id"], rec["unavailable"]))
            continue
        ran += 1
        exp = c["expected_exit"]
        ok = rec["exit"] == exp or (isinstance(exp, list) and rec["exit"] in exp)
        if not ok:
            mismatch.append((c["id"], rec["exit"], exp))
        eq = rec.get("shipping_equivalence")
        if eq is not None and not eq.get("identical"):
            notequiv.append(c["id"])
    print(f"packet {root}: platform {index['platform']}/{index['architecture']}, observer {index.get('observer')}, "
          f"profile {index['profile']}, candidate {index['candidate_sha']}")
    print(f"census {len(census)}: ran {ran}, unavailable {len(unavailable)}, missing {len(missing)}, "
          f"exit differs from descriptor {len(mismatch)}, shipping/observe byte differences {len(notequiv)}")
    for cid, why in unavailable:
        print(f"  UNAVAILABLE {cid}: {why}")
    for cid, got, exp in mismatch:
        print(f"  EXIT {cid}: observed {got}, descriptor {exp}")
    for cid in notequiv:
        print(f"  NOT-EQUIVALENT {cid}")
    for cid in missing:
        print(f"  MISSING {cid}")
    print("This summary is Software's observation only; it is not a review, receipt or PASS.")
    return 1 if (mismatch or notequiv or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
