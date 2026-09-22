#!/usr/bin/env python3
from __future__ import annotations

import copy

from oracle import check, fixture_contract_errors, make_cases, synth_observation


def expect_fail(case, post, ev, calls, label):
    errors = check(case, post, ev, calls)
    if not errors:
        raise AssertionError("mutation escaped: " + label)
    print("CAUGHT", label, "=>", errors[0])


def mutate_first(calls, fn, phase, **changes):
    out = copy.deepcopy(calls)
    for c in out:
        if c.get("fn") == fn and c.get("phase") == phase:
            c.update(changes)
            return out
    raise AssertionError(("call not found", fn, phase))


def main():
    cases = {c.id: c for c in make_cases()}
    print("PASS fixture construction:", ", ".join(cases))

    for case in cases.values():
        ferr = fixture_contract_errors(case)
        if ferr:
            raise AssertionError((case.id, ferr))
        post, ev, calls = synth_observation(case)
        errors = check(case, post, ev, calls)
        if errors:
            raise AssertionError((case.id, errors))
        print("PASS conforming", case.id)

    playing = cases["SS-PLAYING-A-TO-B"]
    post, ev, calls = synth_observation(playing)
    expect_fail(
        playing,
        post,
        ev,
        mutate_first(calls, "tape_status", "pre-status", at_end=False),
        "playing case never established at_end",
    )
    expect_fail(
        playing,
        post,
        ev,
        mutate_first(calls, "tape_status", "post-switch-status", at_end=True),
        "set_side kept at_end",
    )
    expect_fail(
        playing,
        post,
        ev,
        mutate_first(calls, "tape_render", "pre-service-render", result="TAPE_OK", rendered=1),
        "stale pre-switch ring rendered on Side B",
    )
    expect_fail(
        playing,
        post,
        ev,
        mutate_first(calls, "tape_tell", "post-service-tell", frame=2),
        "playing switch did not retain exact +1.0x rate",
    )
    expect_fail(
        playing,
        post,
        ev,
        mutate_first(calls, "tape_get_info", "post-switch-info", total_frames=256),
        "set_side exposed old-side metadata",
    )

    idle = cases["SS-IDLE-A-TO-B"]
    post, ev, calls = synth_observation(idle)
    expect_fail(
        idle,
        post,
        ev,
        mutate_first(calls, "tape_tell", "post-switch-tell", frame=10),
        "idle switch kept old position",
    )
    expect_fail(
        idle,
        post,
        ev,
        mutate_first(calls, "tape_render", "pre-service-render", result="TAPE_OK", rendered=0),
        "idle pre-service render did not report underrun",
    )
    expect_fail(
        idle,
        post,
        ev,
        mutate_first(calls, "tape_set_rate", "post-switch-rate", rate_q16_16=0),
        "idle case failed to establish non-zero post-switch rate",
    )

    same = cases["SS-SAME-A"]
    post, ev, calls = synth_observation(same)
    expect_fail(
        same,
        post,
        ev,
        mutate_first(calls, "tape_tell", "post-switch-tell", frame=10),
        "same-side success did not apply transition",
    )

    deg = cases["SS-DEGRADED-B"]
    post, ev, calls = synth_observation(deg)
    expect_fail(
        deg,
        post,
        ev,
        mutate_first(calls, "tape_set_side", "set-side", result="TAPE_OK"),
        "degraded set_side B allowed",
    )
    expect_fail(
        deg,
        post,
        ev,
        mutate_first(calls, "tape_tell", "post-refusal-tell", frame=0),
        "degraded refusal changed position",
    )
    expect_fail(
        deg,
        post,
        ev,
        mutate_first(calls, "tape_get_info", "post-refusal-info", total_frames=64),
        "degraded refusal switched mounted-side metadata",
    )

    deg_same = cases["SS-DEGRADED-SAME-A"]
    post, ev, calls = synth_observation(deg_same)
    expect_fail(
        deg_same,
        post,
        ev,
        mutate_first(calls, "tape_set_side", "set-side", result="TAPE_ERR_NO_VALID_INDEX"),
        "degraded same-side A wrongly refused",
    )

    armed = cases["SS-ARMED-BUSY"]
    post, ev, calls = synth_observation(armed)
    expect_fail(
        armed,
        post,
        ev,
        mutate_first(calls, "tape_set_side", "set-side", result="TAPE_OK"),
        "armed set_side allowed",
    )
    expect_fail(
        armed,
        post,
        ev,
        mutate_first(calls, "tape_tell", "post-refusal-tell", frame=0),
        "armed BUSY changed position",
    )
    expect_fail(
        armed,
        post,
        ev,
        mutate_first(calls, "tape_abort", "abort", result="TAPE_ERR_BUSY"),
        "armed BUSY path could not abort",
    )

    # Every warm case must prove its actual descriptor shape, not merely report
    # warm_start_used=false. Mutate the unique defect for each negative case.
    warm_mutations = {
        "WARM-NULL": {"warm_present": True},
        "WARM-DATA-NULL": {"warm_data_present": True},
        "WARM-ZERO-FRAMES": {"warm_valid_frames": 1},
        "WARM-SHORT-BUF": {"warm_data_bytes": 64},
        "WARM-PAST-END": {"warm_start_frame": 32},
        "WARM-U32-OVERFLOW": {"warm_start_frame": 32},
        "WARM-RESUME-OUT": {"resume_frame": 40},
        "WARM-UUID": {"warm_uuid_hex": "000102030405060708090a0b0c0d0e0f"},
        "WARM-SIDE": {"warm_side": "A"},
    }
    for cid, changes in warm_mutations.items():
        case = cases[cid]
        post, ev, calls = synth_observation(case)
        bad = copy.deepcopy(calls)
        mount = next(c for c in bad if c.get("fn") == "tape_mount")
        mount.update(changes)
        expect_fail(case, post, ev, bad, f"{cid} descriptor shape collapsed")

    valid = cases["WARM-VALID-METADATA"]
    post, ev, calls = synth_observation(valid)
    bad = copy.deepcopy(calls)
    for c in bad:
        if c.get("fn") in ("tape_mount", "tape_get_info"):
            c["warm_start_used"] = False
    expect_fail(valid, post, ev, bad, "implementation ignored fully valid warm descriptor")

    uuid = cases["WARM-UUID"]
    post, ev, calls = synth_observation(uuid)
    bad = copy.deepcopy(calls)
    mount = next(c for c in bad if c.get("fn") == "tape_mount")
    mount["warm_data_bytes"] = 63
    expect_fail(uuid, post, ev, bad, "UUID case also failed an earlier predicate")

    side = cases["WARM-SIDE"]
    post, ev, calls = synth_observation(side)
    bad = copy.deepcopy(calls)
    mount = next(c for c in bad if c.get("fn") == "tape_mount")
    mount["warm_uuid_hex"] = "ff" * 16
    expect_fail(side, post, ev, bad, "side case also failed UUID predicate")

    # A rendered frame must remain device-I/O-free.
    post, ev, calls = synth_observation(playing)
    expect_fail(
        playing,
        post,
        [{"phase": "pre-service-render", "op": "read", "lba": 2048, "count": 1}],
        calls,
        "render issued block I/O",
    )

    bad_unmount = mutate_first(calls, "tape_unmount", "unmount", result="TAPE_ERR_BUSY")
    expect_fail(playing, post, ev, bad_unmount, "terminal unmount failed")

    print("PASS all transport extra self-tests")


if __name__ == "__main__":
    main()
