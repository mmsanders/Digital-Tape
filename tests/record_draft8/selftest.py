#!/usr/bin/env python3
"""Negative controls for the independent WP-09 record oracles."""
from __future__ import annotations

import copy
import struct
import zlib

from oracle import Media, check, idx, make_cases, overdub_saturate, synth_observation


def expect_fail(case, post, ev, calls, label):
    errors = check(case, post, ev, calls)
    if not errors:
        raise AssertionError("mutation escaped: " + label)
    print("CAUGHT", label, "=>", errors[0])


def expect_fail_extra(check_extra, args, post, ev, calls, label):
    errors = check_extra(*args, post, ev, calls)
    if not errors:
        raise AssertionError("mutation escaped: " + label)
    print("CAUGHT", label, "=>", errors[0])


def main():
    cases = {c.id: c for c in make_cases()}
    print("PASS fixture construction:", ", ".join(cases))

    # Reference arithmetic only. Product PCM remains a later observation/golden gate.
    for existing, incoming, want in (
        (32767, 1, 32767),
        (-32768, -1, -32768),
        (20000, 20000, 32767),
        (-20000, -20000, -32768),
        (100, -40, 60),
        (32767, 32767, 32767),
        (-32768, -32768, -32768),
    ):
        got = overdub_saturate(existing, incoming)
        if got != want:
            raise AssertionError(("saturation", existing, incoming, got, want))
    print("PASS overdub reference saturation vectors")

    for case in cases.values():
        post, ev, calls = synth_observation(case)
        errors = check(case, post, ev, calls)
        if errors:
            raise AssertionError((case.id, errors))
        print("PASS conforming", case.id)

    ow = cases["WP09-OW-MID"]
    post, ev, calls = synth_observation(ow)
    bad_slots = list(post.slots)
    bad_slots[3] = idx(1, [(0, 0, 256)], 701)
    expect_fail(ow, Media(post.blocks, post.primary, post.mirror, tuple(bad_slots)), ev, calls, "overwrite kept tail")

    od = cases["WP09-OD-MID"]
    post, ev, calls = synth_observation(od)
    bad_slots = list(post.slots)
    bad_slots[3] = idx(1, [(0, 0, 128), (3, 0, 64)], 701)
    expect_fail(od, Media(post.blocks, post.primary, post.mirror, tuple(bad_slots)), ev, calls, "overdub truncated timeline")

    sp = cases["WP09-SP-MID"]
    post, ev, calls = synth_observation(sp)
    bad_slots = list(post.slots)
    bad_slots[3] = idx(1, [(0, 0, 128), (3, 0, 64)], 701)
    expect_fail(sp, Media(post.blocks, post.primary, post.mirror, tuple(bad_slots)), ev, calls, "splice dropped suffix")

    empty = cases["WP09-EMPTY-COMMIT"]
    post, ev, calls = synth_observation(empty)
    expect_fail(empty, post, [{"phase": "commit", "op": "write", "lba": 264, "count": 1}], calls, "empty commit wrote")
    expect_fail(empty, post, [{"phase": "commit", "op": "flush"}], calls, "empty commit flushed")
    bad = copy.deepcopy(calls)
    for item in bad:
        if item.get("fn") == "tape_render" and item.get("phase") == "tail-render":
            item["rendered"] = 0
    expect_fail(empty, post, ev, bad, "empty commit tail no longer renders")

    busy = cases["WP09-ARMED-BUSY"]
    post, ev, calls = synth_observation(busy)
    mutated = copy.deepcopy(calls)
    for item in mutated:
        if item.get("fn") == "tape_seek" and item.get("phase") == "armed":
            item["result"] = "TAPE_OK"
    expect_fail(busy, post, ev, mutated, "armed seek allowed")
    mutated = copy.deepcopy(calls)
    for item in mutated:
        if item.get("fn") == "tape_set_rate" and item.get("phase") == "armed":
            item["result"] = "TAPE_OK"
    expect_fail(busy, post, ev, mutated, "armed set_rate allowed")

    rec = cases["WP09-SP-END"]
    post, ev, calls = synth_observation(rec)
    bad_slots = list(post.slots)
    bad_slots[3] = idx(1, rec.expected_entries, 21)
    expect_fail(rec, Media(post.blocks, post.primary, post.mirror, tuple(bad_slots)), ev, calls, "live-only sequence base")

    ev_missing_flush = [e for e in ev if not (e.get("phase") == "commit" and e.get("op") == "flush")]
    expect_fail(rec, post, ev_missing_flush, calls, "commit flush count")

    # Move the header before the first commit flush: entries -> header -> flush -> flush.
    ev_wrong_order = copy.deepcopy(ev)
    commit_positions = [i for i, e in enumerate(ev_wrong_order) if e.get("phase") == "commit"]
    if len(commit_positions) != 4:
        raise AssertionError(("unexpected synthetic commit trace", commit_positions))
    a, b, c, d = commit_positions
    ev_wrong_order[b], ev_wrong_order[c] = ev_wrong_order[c], ev_wrong_order[b]
    expect_fail(rec, post, ev_wrong_order, calls, "commit header before first flush")

    ev_bad_alloc = copy.deepcopy(ev)
    ev_bad_alloc[0] = {"phase": "service", "op": "write", "lba": 8, "count": 1}
    expect_fail(rec, post, ev_bad_alloc, calls, "service write below H")

    ev_sb = list(ev) + [{"phase": "arm", "op": "write", "lba": 0, "count": 1}]
    expect_fail(rec, post, ev_sb, calls, "ordinary record issued same-byte superblock write")

    calls_missing_counter = copy.deepcopy(calls)
    for item in calls_missing_counter:
        if item.get("fn") == "tape_feed":
            item.pop("events_from_call", None)
    expect_fail(rec, post, ev, calls_missing_counter, "feed omitted callback count")

    ev_feed = list(ev) + [{"phase": "feed", "op": "read", "lba": 0, "count": 1}]
    expect_fail(rec, post, ev_feed, calls, "feed issued raw block callback")

    calls_service_busy = copy.deepcopy(calls)
    for item in calls_service_busy:
        if item.get("fn") == "tape_service":
            item["more_work"] = True
    expect_fail(rec, post, ev, calls_service_busy, "service never completed")

    from refusals import check_refusal, fixture_ok, refusal_cases, synth_refusal

    for cid, pre, mode, side, expect in refusal_cases():
        ferr = fixture_ok(cid, pre)
        if ferr:
            raise AssertionError((cid, ferr))
        post, ev, calls = synth_refusal(cid, pre, mode, side, expect)
        errors = check_refusal(cid, pre, mode, side, expect, post, ev, calls)
        if errors:
            raise AssertionError((cid, errors))
        print("PASS conforming", cid)

        if cid == "WP09-RO-SIDE-A":
            bad = copy.deepcopy(calls)
            for item in bad:
                if item.get("fn") == "tape_arm":
                    item["result"] = "TAPE_OK"
            got = check_refusal(cid, pre, mode, side, expect, post, ev, bad)
            if not got:
                raise AssertionError("mutation escaped: Side-A arm allowed")
            print("CAUGHT Side-A arm allowed =>", got[0])

        if cid == "WP09-CART-FULL":
            got = check_refusal(
                cid,
                pre,
                mode,
                side,
                expect,
                post,
                [{"op": "write", "lba": 2048, "count": 1, "phase": "feed"}],
                calls,
            )
            if not got:
                raise AssertionError("mutation escaped: full feed wrote")
            print("CAUGHT full feed wrote =>", got[0])
            bad = copy.deepcopy(calls)
            for item in bad:
                if item.get("fn") == "tape_feed":
                    item.pop("events_from_call", None)
            got = check_refusal(cid, pre, mode, side, expect, post, ev, bad)
            if not got:
                raise AssertionError("mutation escaped: full feed omitted callback count")
            print("CAUGHT full feed omitted callback count =>", got[0])

        if cid == "WP09-ABORT-DISARM":
            bad = copy.deepcopy(calls)
            for item in bad:
                if item.get("fn") == "tape_unmount":
                    item["result"] = "TAPE_ERR_BUSY"
            got = check_refusal(cid, pre, mode, side, expect, post, ev, bad)
            if not got:
                raise AssertionError("mutation escaped: abort left instance armed")
            print("CAUGHT abort left instance armed =>", got[0])

        if cid == "WP09-STAGE-REFUSE":
            mutated = bytearray(post.primary)
            struct.pack_into("<I", mutated, 124, 0)
            struct.pack_into("<I", mutated, 508, zlib.crc32(mutated[:508]))
            bad_post = Media(post.blocks, bytes(mutated), post.mirror, post.slots)
            got = check_refusal(cid, pre, mode, side, expect, bad_post, ev, calls)
            if not got:
                raise AssertionError("mutation escaped: refusal cleared promote_stage")
            print("CAUGHT refusal cleared promote_stage =>", got[0])

    from extra import check_extra, extra_cases, fixture_ok as extra_fixture_ok, synth_extra

    for cid, pre, mode, side, seek, feed, kind in extra_cases():
        args = (cid, pre, mode, side, seek, feed, kind)
        ferr = extra_fixture_ok(cid, pre)
        if ferr:
            raise AssertionError((cid, ferr))
        post, ev, calls = synth_extra(*args)
        errors = check_extra(*args, post, ev, calls)
        if errors:
            raise AssertionError((cid, errors))
        print("PASS conforming", cid)

        if cid == "WP09-OW-MULTICHUNK":
            ev_missing = [
                e
                for e in ev
                if not (e.get("phase") == "service" and e.get("lba", 0) >= 2048 + 4 * 1024)
            ]
            expect_fail_extra(check_extra, args, post, ev_missing, calls, "multi-chunk missed chunk 4")
            ev_extra = list(ev) + [{"phase": "service", "op": "write", "lba": 2048 + 5 * 1024, "count": 1}]
            expect_fail_extra(check_extra, args, post, ev_extra, calls, "multi-chunk wrote chunk 5")

        if cid == "WP09-SP-BOUNDARY":
            bad_slots = list(post.slots)
            bad_slots[3] = idx(1, [(0, 0, 128), (3, 0, 64)], 701)
            bad_post = Media(post.blocks, post.primary, post.mirror, tuple(bad_slots))
            expect_fail_extra(check_extra, args, bad_post, ev, calls, "boundary splice dropped following run")

        if kind == "empty" and cid == "WP09-EMPTY-OD":
            expect_fail_extra(check_extra, args, post, [{"phase": "commit", "op": "flush"}], calls, "empty overdub flushed")
            bad = copy.deepcopy(calls)
            for item in bad:
                if item.get("fn") == "tape_render" and item.get("phase") == "tail-render":
                    item["rendered"] = 0
            expect_fail_extra(check_extra, args, post, ev, bad, "empty overdub tail missing")

        if cid == "WP09-STAGE-CLEAR":
            expect_fail_extra(check_extra, args, pre, ev, calls, "stage-clear left stage 1")
            ev_bad = copy.deepcopy(ev)
            arm_positions = [i for i, e in enumerate(ev_bad) if e.get("phase") == "arm"]
            if len(arm_positions) != 4:
                raise AssertionError(("unexpected stage-clear trace", arm_positions))
            # candidate write before the first flush violates §4.6.
            ev_bad[arm_positions[1]], ev_bad[arm_positions[2]] = ev_bad[arm_positions[2]], ev_bad[arm_positions[1]]
            expect_fail_extra(check_extra, args, post, ev_bad, calls, "stage-clear candidate before partner flush")

    print("PASS all WP-09 record self-tests")


if __name__ == "__main__":
    main()
