#!/usr/bin/env python3
"""Drive the WP-09 product adapter against the independent record oracles.

Software-owned, and deliberately OUTSIDE tests/record_draft8/. The verifier
publication ships no product runner -- unlike ops_draft8 and playback_draft8 --
so this file supplies the plumbing that tests/record_draft8/ADAPTER.md
specifies: build each case's input VO08 from the VERIFIER's own fixture, invoke

    wp09_rec_probe CASE_ID INPUT.vo08 OUTPUT.vo08

decode the VO08 the adapter wrote, and hand the media, the event trace and the
call trace to the verifier's own check functions.

It asserts NOTHING of its own about engine behaviour. Every verdict below comes
from oracle.check, refusals.check_refusal or extra.check_extra, imported
unmodified. It does not edit fixtures, expected values, tolerances, ordering,
classifications or assertions, and it cannot: it does not contain any.

A green run here is product OBSERVATION, not acceptance. Disposition is
Verification's, on evidence it did not watch being produced.

--expect-blocked CASE_ID names a case whose failure is a KNOWN PACKAGE BLOCKER
rather than an engine defect. The case still runs, its verdict is still printed
verbatim, and nothing about it is suppressed -- only the process exit code
changes, and it changes in BOTH directions: a named case that starts PASSING
fails the run too, so the exception cannot be forgotten once it stops being
true. It is a Software annotation on CI, not a disposition; only PM and
Verification can dispose of a verifier assertion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent / "record_draft8"
sys.path.insert(0, str(PKG))

from extra import check_extra, extra_cases, fixture_ok as extra_fixture_ok   # noqa: E402
from oracle import Media, check, make_cases                                  # noqa: E402
from refusals import check_refusal, fixture_ok as refusal_fixture_ok, refusal_cases  # noqa: E402

OBS_FORMAT = "WP09-REC-OBSERVATION-1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plan():
    """(case_id, pre_media, fixture_audit, verdict) for every published case."""
    rows = []
    for case in make_cases():
        rows.append((case.id, case.pre, lambda: [],
                     lambda post, ev, calls, c=case: check(c, post, ev, calls)))
    for cid, pre, mode, side, expect in refusal_cases():
        rows.append((cid, pre,
                     lambda cid=cid, pre=pre: refusal_fixture_ok(cid, pre),
                     lambda post, ev, calls, a=(cid, pre, mode, side, expect):
                        check_refusal(*a, post, ev, calls)))
    for cid, pre, mode, side, seek, feed, kind in extra_cases():
        args = (cid, pre, mode, side, seek, feed, kind)
        rows.append((cid, pre,
                     lambda cid=cid, pre=pre: extra_fixture_ok(cid, pre),
                     lambda post, ev, calls, a=args: check_extra(*a, post, ev, calls)))
    return rows


def run(adapter: Path, workdir: Path, evidence: Path | None,
        expect_blocked: set[str]) -> int:
    workdir.mkdir(parents=True, exist_ok=True)
    if evidence is not None:
        evidence.mkdir(parents=True, exist_ok=True)
    records, failures, blocked = [], 0, 0

    for cid, pre, audit, verdict in plan():
        errors = list(audit())
        if errors:
            # The fixture itself is wrong: that is a finding for Verification,
            # never something to work around here.
            print(f"FIXTURE {cid}: {errors}")
            failures += 1
            continue

        inp = workdir / f"{cid}.in.vo08"
        out = workdir / f"{cid}.out.vo08"
        inp.write_bytes(pre.encode())
        if out.exists():
            out.unlink()

        proc = subprocess.run([str(adapter), cid, str(inp), str(out)],
                              capture_output=True, text=True, timeout=600)
        rec = {
            "case": cid,
            "argv": [adapter.name, cid],
            "exit": proc.returncode,
            "input_sha256": sha256(inp.read_bytes()),
            "stderr": proc.stderr.strip(),
        }

        if proc.returncode != 0:
            errors.append(f"adapter exit {proc.returncode}")
        if not out.exists():
            errors.append("adapter wrote no output media")
        else:
            rec["output_sha256"] = sha256(out.read_bytes())

        obs = None
        try:
            obs = json.loads(proc.stdout)
        except Exception as exc:                       # noqa: BLE001
            errors.append(f"adapter stdout is not one JSON object: {exc}")

        if obs is not None:
            rec["observation"] = obs
            if obs.get("format") != OBS_FORMAT:
                errors.append(f"observation format {obs.get('format')!r}")
            if obs.get("adapter_kind") != "product":
                errors.append(f"adapter_kind {obs.get('adapter_kind')!r} is not product")
            if obs.get("event_overflow"):
                errors.append("adapter event trace overflowed")

        if obs is not None and out.exists():
            post = Media.decode(out.read_bytes())
            errors.extend(verdict(post, obs.get("events", []), obs.get("calls", [])))

        rec["errors"] = errors
        rec["expected_blocked"] = cid in expect_blocked
        records.append(rec)
        if errors:
            if cid in expect_blocked:
                blocked += 1
                print(f"BLOCKED {cid}  (declared known package blocker)")
            else:
                failures += 1
                print(f"FAIL {cid}")
            for e in errors:
                print(f"       {e}")
        else:
            if cid in expect_blocked:
                # The negative control on the exception itself.
                failures += 1
                print(f"UNBLOCKED {cid}  (declared blocked but passed; drop the exception)")
            else:
                print(f"PASS {cid}")

    total = len(records)
    passed = total - failures - blocked
    print(f"\n{passed}/{total} WP-09 cases pass against the product engine"
          + (f", {blocked} declared blocked." if blocked else "."))
    print("Product observation only. Not package acceptance, not a listened golden.")

    if evidence is not None:
        path = evidence / "observations.jsonl"
        with path.open("w") as f:
            for rec in records:
                f.write(json.dumps(rec, sort_keys=True) + "\n")
        print(f"evidence: {path} sha256={sha256(path.read_bytes())}")

    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default=str(HERE / "build" / "wp09_rec_probe"))
    ap.add_argument("--workdir", default=str(HERE / "build" / "media"))
    ap.add_argument("--evidence", default=None)
    ap.add_argument("--expect-blocked", action="append", default=[],
                    help="case id whose failure is a known package blocker")
    args = ap.parse_args()
    adapter = Path(args.adapter).resolve()
    if not adapter.exists():
        print(f"adapter not built: {adapter}", file=sys.stderr)
        return 2
    return run(adapter, Path(args.workdir),
               Path(args.evidence) if args.evidence else None,
               set(args.expect_blocked))


if __name__ == "__main__":
    raise SystemExit(main())
