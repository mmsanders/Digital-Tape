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
    print(f"binaries: observation {index['binary_sha256']}, shipping {index.get('shipping_binary_sha256')}; "
          f"config_sha256 {index['config_sha256']}")
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
    st = root / "observer-selftest" / "result.json"
    if st.exists():
        r = json.loads(st.read_text(encoding="utf-8"))
        print(f"observer selftest: qualified={r.get('qualified')} checks={r.get('checks')}")
        for name, c in (r.get("false_pass_controls") or {}).items():
            print(f"  false-pass control {name}: rejected={c.get('rejected')}")
    if st.exists():
        for key in ("session_alignment", "device_like_rows", "probe_stderr_tail", "probe_paths_outside_python",
                    "limitation"):
            if key in r:
                print(f"  {key}: {json.dumps(r[key], ensure_ascii=True)[:3000]}")
    part = root / "observer-session" / "partition.json"
    if part.exists():
        pj = json.loads(part.read_text(encoding="utf-8"))
        print(f"session partition: records={pj['records']} owned={pj['owned']} unowned={pj['unowned_count']} "
              f"multiply_owned={pj['multiply_owned']} owners={len(pj['owners'])}")
        for u in pj["unowned"][:10]:
            print("  UNOWNED", json.dumps(u, ensure_ascii=True)[:300])
    incomplete = []
    for nat in sorted(root.glob("cases/*/native.json")) + sorted(root.glob("cases/*/comparisons/*/native.json")):
        d = json.loads(nat.read_text(encoding="utf-8"))
        if not d.get("complete") and not d.get("unavailable"):
            incomplete.append((nat.relative_to(root).as_posix(), d.get("scenario"), d.get("process_completion"),
                               {k: v for k, v in (d.get("integrity") or {}).items() if not v}))
    print(f"native records not complete: {len(incomplete)}")
    for x in incomplete[:25]:
        print("  INCOMPLETE", *x)
    print("This summary is Software's observation only; it is not a review, receipt or PASS.")
    return 1 if (mismatch or notequiv or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
