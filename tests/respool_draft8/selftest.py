#!/usr/bin/env python3
from __future__ import annotations

import copy

from oracle import (
    BLOCKS_PER_CHUNK,
    CF,
    LBA_B0,
    LBA_B1,
    LBA_CHUNK_BASE,
    Media,
    SEMANTIC_BUDGET,
    check,
    fixture_contract_errors,
    idx,
    make_cases,
    synth_observation,
)


def expect_fail(case, post, ev, calls, label):
    errors = check(case, post, ev, calls)
    if not errors:
        raise AssertionError("mutation escaped: " + label)
    print("CAUGHT", label, "=>", errors[0])


def main():
    cases = {c.id: c for c in make_cases()}

    for case in cases.values():
        errors = fixture_contract_errors(case)
        if errors:
            raise AssertionError((case.id, errors))
        post, ev, calls = synth_observation(case)
        errors = check(case, post, ev, calls)
        if errors:
            raise AssertionError((case.id, errors))
        print("PASS conforming", case.id)

    # Empty branch: prove both the zero-write behavior and the zero-needed
    # headroom rule using the 0xFFFFFFFF crafted sequence fixture.
    empty = cases["WP12-EMPTY"]
    post, ev, calls = synth_observation(empty)
    expect_fail(
        empty,
        post,
        [{"phase": "respool", "op": "write", "lba": LBA_B0, "count": 1}],
        calls,
        "empty respool wrote",
    )
    expect_fail(
        empty,
        post,
        [{"phase": "respool", "op": "flush"}],
        calls,
        "empty respool flushed",
    )
    bad_calls = copy.deepcopy(calls)
    for x in bad_calls:
        if x.get("fn") == "tape_promote":
            x["more_work"] = True
    expect_fail(empty, post, ev, bad_calls, "empty promote left more_work true")

    # V3-003 must be two real commits with pass 1 durable/live before pass 2
    # reuses the original live-B chunks.
    two = cases["WP12-TWOPASS"]
    post, ev, calls = synth_observation(two)

    # One-block fake copy of a two-full-chunk timeline must not pass.
    short = copy.deepcopy(ev)
    first_data = next(i for i, e in enumerate(short) if e.get("op") == "write" and e.get("lba") == LBA_CHUNK_BASE + 12 * BLOCKS_PER_CHUNK)
    short[first_data]["count"] = 1
    expect_fail(two, post, short, calls, "pass 1 copied only one block")

    # Move pass-2 data before the pass-1 header commit. That write intersects
    # the still-live initial B set and must be rejected by invariant 10.
    unsafe = copy.deepcopy(ev)
    p2_data_i = next(i for i, e in enumerate(unsafe) if e.get("op") == "write" and e.get("lba") == LBA_CHUNK_BASE + 10 * BLOCKS_PER_CHUNK)
    p1_header_i = next(i for i, e in enumerate(unsafe) if e.get("op") == "write" and e.get("lba") == LBA_B1)
    p2_data = unsafe.pop(p2_data_i)
    if p2_data_i < p1_header_i:
        p1_header_i -= 1
    unsafe.insert(p1_header_i, p2_data)
    expect_fail(two, post, unsafe, calls, "pass 2 wrote before pass 1 committed")

    # The final generation must alternate back to B0; leaving B1 as the final
    # 702 generation would not represent two inactive-slot commits.
    bad_slots = list(post.slots)
    bad_slots[2] = two.pre.slots[2]
    bad_slots[3] = idx(1, [(10, 0, 2 * CF)], 702)
    expect_fail(two, Media(post.blocks, post.primary, post.mirror, tuple(bad_slots)), ev, calls, "two passes did not alternate B slots")

    # Extra chunk-region corruption above H but outside either destination.
    extra = list(ev) + [
        {
            "phase": "respool",
            "op": "write",
            "lba": LBA_CHUNK_BASE + 18 * BLOCKS_PER_CHUNK,
            "count": 1,
        }
    ]
    expect_fail(two, post, extra, calls, "respool wrote unrelated chunk 18")

    # Same-byte superblock writes are forbidden on an ordinary stage-0 respool.
    sb_write = list(ev) + [{"phase": "respool", "op": "write", "lba": 0, "count": 1}]
    expect_fail(two, post, sb_write, calls, "ordinary respool issued superblock write")

    # This semantic tranche intentionally uses a generous budget; claiming
    # completion under the old budget=64 script must fail.
    tiny_budget = copy.deepcopy(calls)
    for x in tiny_budget:
        if x.get("fn") == "tape_respool":
            x["block_budget"] = 64
    expect_fail(two, post, ev, tiny_budget, "semantic case falsely completed with budget 64")

    # Mandatory pass-2-decline case: only chunk 10 is initially available,
    # pass 1 lands there and no strictly-lower start exists.
    decline = cases["WP12-DECLINE"]
    post, ev, calls = synth_observation(decline)
    extra_pass = list(ev) + [
        {"phase": "respool", "op": "write", "lba": LBA_CHUNK_BASE + 11 * BLOCKS_PER_CHUNK, "count": 1}
    ]
    expect_fail(decline, post, extra_pass, calls, "decline case performed a second pass")

    # Degraded-B is reachable only from a Side-A mount.
    degraded = cases["WP12-DEGRADED"]
    post, ev, calls = synth_observation(degraded)
    wrong_mount = copy.deepcopy(calls)
    for x in wrong_mount:
        if x.get("fn") == "tape_mount":
            x["side"] = "B"
            x["result"] = "TAPE_ERR_INCONSISTENT"
    expect_fail(degraded, post, ev, wrong_mount, "degraded case tried to mount Side B")

    # Refusal cases must remain zero-write and terminal.
    full = cases["WP12-FULL"]
    post, ev, calls = synth_observation(full)
    accepted = copy.deepcopy(calls)
    for x in accepted:
        if x.get("fn") == "tape_respool":
            x["result"] = "TAPE_OK"
    expect_fail(full, post, ev, accepted, "full destination accepted")

    exhausted = cases["WP12-SEQ-EXHAUSTED"]
    post, ev, calls = synth_observation(exhausted)
    expect_fail(
        exhausted,
        post,
        [{"phase": "respool", "op": "write", "lba": LBA_B1, "count": 1}],
        calls,
        "sequence-exhausted respool wrote",
    )

    # With exactly one sequence left, pass 1 must complete but the optional
    # second pass must be skipped.
    one = cases["WP12-ONE-COMMIT"]
    post, ev, calls = synth_observation(one)
    second = list(ev) + [
        {"phase": "respool", "op": "write", "lba": LBA_CHUNK_BASE + 10 * BLOCKS_PER_CHUNK, "count": 1}
    ]
    expect_fail(one, post, second, calls, "one-commit headroom attempted pass 2")

    # Stage clear must happen in §4.6 order before the first copy/index write.
    stage = cases["WP12-STAGE-CLEAR"]
    post, ev, calls = synth_observation(stage)
    wrong_stage = copy.deepcopy(ev)
    # Swap partner flush with candidate write: partner -> candidate -> flush -> flush.
    wrong_stage[1], wrong_stage[2] = wrong_stage[2], wrong_stage[1]
    expect_fail(stage, post, wrong_stage, calls, "stage clear candidate written before partner flush")

    unmount_bad = copy.deepcopy(calls)
    for x in unmount_bad:
        if x.get("fn") == "tape_unmount":
            x["result"] = "TAPE_ERR_BUSY"
    expect_fail(stage, post, ev, unmount_bad, "terminal unmount failed")

    print("PASS all WP-12 re-spool self-tests")


if __name__ == "__main__":
    main()
