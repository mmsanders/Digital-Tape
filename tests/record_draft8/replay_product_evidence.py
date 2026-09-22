#!/usr/bin/env python3
"""Verifier-owned offline replay for the exact P1-R25 WP-09 product evidence.

The retained product bundle does not contain raw post-media files. The audited
Software collector did retain SHA-256 for each actual INPUT/OUTPUT VO08. This
replay independently regenerates verifier-authored pre/post media, requires
those hashes to match, then applies the corrected verifier oracles to the
retained product call/event observations. Stored Software "errors" are ignored.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from extra import check_extra, extra_cases, fixture_ok as extra_fixture_ok, synth_extra
from oracle import Media, check, make_cases, synth_observation
from refusals import check_refusal, fixture_ok as refusal_fixture_ok, refusal_cases, synth_refusal

EVIDENCE_SHA256 = "a88850df6554df973fdda6071f65184fcd9012b8886c253dafbff4fc9e0966fc"
PRODUCT_COMMIT = "9d3649d87f2adb093d18b34825e38ca9573ba0a5"
ORIGINAL_VERIFIER_PUBLICATION = "af15a8f4e7069aff9e9d5a98728530702a4f1f56"
PRODUCT_IMPORT_SUBTREE = "b7eb335d08f35b70f55fb54b5a0966c52a25688b"
OBS_FORMAT = "WP09-REC-OBSERVATION-1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plan():
    rows = []
    for case in make_cases():
        post, _synthetic_events, _synthetic_calls = synth_observation(case)
        rows.append((
            case.id,
            case.pre,
            post,
            lambda: [],
            lambda ev, calls, c=case, p=post: check(c, p, ev, calls),
        ))
    for cid, pre, mode, side, expect in refusal_cases():
        post, _synthetic_events, _synthetic_calls = synth_refusal(cid, pre, mode, side, expect)
        args = (cid, pre, mode, side, expect)
        rows.append((
            cid,
            pre,
            post,
            lambda cid=cid, pre=pre: refusal_fixture_ok(cid, pre),
            lambda ev, calls, a=args, p=post: check_refusal(*a, p, ev, calls),
        ))
    for cid, pre, mode, side, seek, feed, kind in extra_cases():
        args = (cid, pre, mode, side, seek, feed, kind)
        post, _synthetic_events, _synthetic_calls = synth_extra(*args)
        rows.append((
            cid,
            pre,
            post,
            lambda cid=cid, pre=pre: extra_fixture_ok(cid, pre),
            lambda ev, calls, a=args, p=post: check_extra(*a, p, ev, calls),
        ))
    return rows


def replay(path: Path) -> tuple[int, list[dict]]:
    raw = path.read_bytes()
    got_bundle_hash = sha256_bytes(raw)
    if got_bundle_hash != EVIDENCE_SHA256:
        raise SystemExit(
            f"evidence SHA-256 mismatch: got {got_bundle_hash}, want {EVIDENCE_SHA256}"
        )

    records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    rows = plan()
    expected_ids = [row[0] for row in rows]
    actual_ids = [rec.get("case") for rec in records]
    if len(rows) != 26:
        raise SystemExit(f"verifier plan drift: expected 26 rows, got {len(rows)}")
    if actual_ids != expected_ids:
        raise SystemExit(
            "evidence case order/set mismatch:\n"
            f"  expected={expected_ids}\n"
            f"  actual={actual_ids}"
        )

    dispositions = []
    failures = 0
    for rec, (cid, pre, expected_post, audit, verdict) in zip(records, rows):
        errors = list(audit())

        if rec.get("case") != cid:
            errors.append("case id mismatch")
        if rec.get("exit") != 0:
            errors.append(f"adapter exit {rec.get('exit')!r}")
        if rec.get("argv") != ["wp09_rec_probe", cid]:
            errors.append(f"argv mismatch: {rec.get('argv')!r}")

        expected_input_hash = sha256_bytes(pre.encode())
        expected_output_hash = sha256_bytes(expected_post.encode())
        if rec.get("input_sha256") != expected_input_hash:
            errors.append(
                f"input hash mismatch: got {rec.get('input_sha256')}, "
                f"want {expected_input_hash}"
            )
        if rec.get("output_sha256") != expected_output_hash:
            errors.append(
                f"output hash mismatch: got {rec.get('output_sha256')}, "
                f"want {expected_output_hash}"
            )

        obs = rec.get("observation")
        if not isinstance(obs, dict):
            errors.append("missing product observation object")
        else:
            if obs.get("format") != OBS_FORMAT:
                errors.append(f"observation format {obs.get('format')!r}")
            if obs.get("adapter_kind") != "product":
                errors.append(f"adapter_kind {obs.get('adapter_kind')!r} is not product")
            if obs.get("event_overflow") is not False:
                errors.append("adapter event trace overflowed or overflow flag missing")
            ev = obs.get("events")
            calls = obs.get("calls")
            if not isinstance(ev, list):
                errors.append("events is not a list")
            if not isinstance(calls, list):
                errors.append("calls is not a list")
            if isinstance(ev, list) and isinstance(calls, list):
                errors.extend(verdict(ev, calls))

        status = "PASS" if not errors else "FAIL"
        failures += bool(errors)
        dispositions.append({
            "case": cid,
            "status": status,
            "errors": errors,
            "stored_software_errors": rec.get("errors"),
            "stored_expected_blocked": rec.get("expected_blocked"),
            "input_sha256": rec.get("input_sha256"),
            "output_sha256": rec.get("output_sha256"),
        })
        print(f"{status} {cid}")
        for error in errors:
            print("  " + error)

    print()
    print(f"bundle_sha256={got_bundle_hash}")
    print(f"product_commit={PRODUCT_COMMIT}")
    print(f"original_verifier_publication={ORIGINAL_VERIFIER_PUBLICATION}")
    print(f"product_import_subtree={PRODUCT_IMPORT_SUBTREE}")
    print(f"{len(dispositions)-failures}/{len(dispositions)} independently replayed cases PASS")
    return failures, dispositions


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    default = Path(__file__).resolve().parent / "evidence" / "p1-r25-product" / "observations.jsonl"
    if len(args) > 1:
        print("usage: replay_product_evidence.py [OBSERVATIONS.jsonl]", file=sys.stderr)
        return 2
    path = Path(args[0]) if args else default
    failures, dispositions = replay(path)
    if "--json" in ():  # reserved: stdout remains human-stable for CI
        print(json.dumps(dispositions, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
