#!/usr/bin/env python3
from __future__ import annotations

import copy

from oracle import Media, STRICT_NO_CALLBACK_IDS, check, make_cases, synth_observation


def expect_fail(case, post, events, calls, label):
    errors = check(case, post, events, calls)
    if not errors:
        raise AssertionError("mutation escaped: " + label)


def tested_call(case, calls):
    fn = {"format": "tape_format", "dup": "tape_dup", "promote": "tape_promote"}[case.kind]
    return next(c for c in calls if c.get("fn") == fn)


def main():
    cases = {c.id: c for c in make_cases()}
    print("PASS fixture construction:", ", ".join(cases))

    for case in cases.values():
        post, events, calls = synth_observation(case)
        errors = check(case, post, events, calls)
        if errors:
            raise AssertionError((case.id, errors))

        bad = copy.deepcopy(calls)
        tested_call(case, bad)["result"] = "TAPE_OK"
        expect_fail(case, post, events, bad, case.id + " wrong result")

        expect_fail(
            case,
            post,
            [{"op": "write", "device": "destination", "lba": 8, "count": 1}],
            calls,
            case.id + " wrote",
        )

        if case.kind in ("dup", "promote"):
            bad = copy.deepcopy(calls)
            tested_call(case, bad)["more_work"] = True
            expect_fail(case, post, events, bad, case.id + " more_work true")

        fn = tested_call(case, calls)["fn"]
        bad = [c for c in copy.deepcopy(calls) if c.get("fn") != fn]
        expect_fail(case, post, events, bad, case.id + " missing tested call")

    case = cases["FMT-RO"]
    post, events, calls = synth_observation(case)
    p = bytearray(post.primary)
    p[100] ^= 1
    changed = Media(post.blocks, bytes(p), post.mirror, post.slots)
    expect_fail(case, changed, events, calls, "tracked media changed")

    for cid in STRICT_NO_CALLBACK_IDS:
        case = cases[cid]
        post, events, calls = synth_observation(case)
        expect_fail(
            case,
            post,
            [{"op": "read", "device": "destination", "lba": 7, "count": 1}],
            calls,
            cid + " callback",
        )

    case = cases["FMT-RO"]
    post, events, calls = synth_observation(case)
    allowed = [{"op": "read", "device": "destination", "lba": 7, "count": 1}]
    if check(case, post, allowed, calls):
        raise AssertionError("FMT-RO incorrectly constrained to zero callbacks")

    for cid in ("FMT-RO", "FMT-GEOM-FIT", "DUP-ALIAS", "DUP-RO", "DUP-GEOM-FIT", "DUP-TOO-SMALL"):
        case = cases[cid]
        post, events, calls = synth_observation(case)
        expect_fail(
            case,
            post,
            [{"op": "read", "device": "destination", "lba": 0, "count": 1}],
            calls,
            cid + " read destination superblock",
        )

    alias = cases["DUP-ALIAS"]
    post, events, calls = synth_observation(alias)
    bad = copy.deepcopy(calls)
    tested_call(alias, bad)["aliased"] = False
    expect_fail(alias, post, events, bad, "alias flag false")
    errors = check(alias, post, events, [c for c in calls if c.get("fn") != "tape_dup"])
    if not errors:
        raise AssertionError("missing dup call escaped")

    print("PASS all format/dup/empty-promote refusal self-tests")


if __name__ == "__main__":
    main()
