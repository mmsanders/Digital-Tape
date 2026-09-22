#!/usr/bin/env python3
from __future__ import annotations

import copy
import struct
import zlib

from oracle import (
    Media, check, chunk_lba, fixture_contract_errors, live_slot, make_cases,
    parse_entries, structural_sequence, idx, synth_observation,
)


def expect_fail(case, post, events, calls, label):
    errors = check(case, post, events, calls)
    if not errors:
        raise AssertionError("mutation escaped: " + label)


def promote_calls(calls):
    return [c for c in calls if c.get("fn") == "tape_promote"]


def rewrite_generation(block: bytes, generation: int) -> bytes:
    b = bytearray(block)
    struct.pack_into("<I", b, 12, generation)
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    return bytes(b)


def main():
    cases = {c.id: c for c in make_cases()}
    print("PASS fixture construction:", ", ".join(cases))

    for case in cases.values():
        ferr = fixture_contract_errors(case)
        if ferr:
            raise AssertionError((case.id, ferr))
        post, events, calls = synth_observation(case)
        errors = check(case, post, events, calls)
        if errors:
            raise AssertionError((case.id, errors))

        bad = copy.deepcopy(calls)
        promote_calls(bad)[-1]["result"] = "TAPE_OK" if case.expect != "TAPE_OK" else "TAPE_ERR_BUSY"
        expect_fail(case, post, events, bad, case.id + " wrong terminal result")

        bad = copy.deepcopy(calls)
        promote_calls(bad)[-1]["more_work"] = True
        expect_fail(case, post, events, bad, case.id + " terminal more_work true")

        bad = [c for c in copy.deepcopy(calls) if c.get("fn") != "tape_promote"]
        expect_fail(case, post, events, bad, case.id + " missing promote call")

        if case.path is None:
            expect_fail(
                case, post,
                events + [{"op": "write", "lba": 8, "count": 1, "phase": "promote"}],
                calls, case.id + " zero-write classification wrote",
            )
        else:
            bad = copy.deepcopy(calls)
            promote_calls(bad)[0]["more_work"] = False
            expect_fail(case, post, events, bad, case.id + " continuation ended early")

            # Exact post-media sequencing is normative.
            side = 1
            live = live_slot(post, side)
            slot = post.slots[live]
            seq = structural_sequence(slot)
            slots = list(post.slots)
            slots[live] = idx(side, parse_entries(slot), seq - 1)
            expect_fail(
                case, Media(post.blocks, post.primary, post.mirror, tuple(slots)),
                events, calls, case.id + " wrong final sequence",
            )

            gen = struct.unpack_from("<I", post.primary, 12)[0]
            lower = rewrite_generation(post.primary, gen - 1)
            expect_fail(
                case, Media(post.blocks, lower, lower, post.slots),
                events, calls, case.id + " wrong final generation",
            )

    deg = cases["PR-DEGRADED"]
    post, events, calls = synth_observation(deg)
    bad = copy.deepcopy(calls)
    next(c for c in bad if c.get("fn") == "tape_mount")["side"] = "B"
    expect_fail(deg, post, events, bad, "degraded case mounted Side B")

    nothing = cases["PR-NOTHING-HIGH-COUNTERS"]
    post, events, calls = synth_observation(nothing)
    if check(nothing, post, events, calls):
        raise AssertionError("zero-needed NOTHING TO DO rejected high counters")

    complete = cases["PR-ADOPT-COMPLETE"]
    post, events, calls = synth_observation(complete)
    bad = copy.deepcopy(events)
    chunk = next(e for e in bad if e.get("op") == "write" and e.get("lba") == chunk_lba(0))
    chunk["count"] -= 1
    expect_fail(complete, post, bad, calls, "phase-2 chunk coverage short")

    bad = copy.deepcopy(events)
    chunk_i = next(i for i, e in enumerate(bad) if e.get("op") == "write" and e.get("lba") == chunk_lba(0))
    chunk_event = bad.pop(chunk_i)
    bad.insert(0, chunk_event)
    expect_fail(complete, post, bad, calls, "below-H write before stage-1 superblock")

    bad = copy.deepcopy(events)
    mirror = complete.pre.blocks - 1
    mi = next(i for i, e in enumerate(bad) if e.get("op") == "write" and e.get("lba") == mirror)
    pi = next(i for i, e in enumerate(bad) if i > mi and e.get("op") == "write" and e.get("lba") == 0)
    bad[mi]["lba"], bad[pi]["lba"] = bad[pi]["lba"], bad[mi]["lba"]
    expect_fail(complete, post, bad, calls, "superblock candidate written before partner")

    decline = cases["PR-ADOPT-DECLINE"]
    post, events, calls = synth_observation(decline)
    expect_fail(
        decline, post,
        events + [{"op": "write", "lba": chunk_lba(0), "count": 1, "phase": "promote"}],
        calls, "decline copied below staging run",
    )

    alloc = cases["PR-ALLOC-COMPLETE"]
    post, events, calls = synth_observation(alloc)
    bad = [
        e for e in events
        if not (e.get("op") == "write" and e.get("lba") == chunk_lba(alloc.s))
    ]
    expect_fail(alloc, post, bad, calls, "allocating phase-1 copy missing")

    print("PASS all promote classification/metadata-path self-tests")


if __name__ == "__main__":
    main()
