#!/usr/bin/env python3
from __future__ import annotations
import copy

from fixture import (
    index_blocks, scenario_initial, snapshot, stage_fixture, target_baseline, transaction,
)
from media import (
    MediaError, inspect_snapshot, require_unique_structural_sequences, resume_rows,
)
from oracle import (
    VerificationError, completed_snapshot, expected_observation, expected_recovery_row,
    failure_reproducer, rerun_seed_snapshot, validate_case,
)
from planner import (
    EXPECTED_CASESET_SHA256, EXPECTED_CONTRACT_CASES, EXPECTED_CRASH_CASES,
    EXPECTED_TOTAL_CASES, counts, iter_cases, validate_planner,
)


def need(c, m):
    if not c:
        raise AssertionError(m)


def reject(fn, label):
    try:
        fn()
    except VerificationError:
        return
    raise AssertionError("negative control escaped: " + label)


def reject_media(fn, label):
    try:
        fn()
    except MediaError:
        return
    raise AssertionError("media negative control escaped: " + label)


def find(**want):
    for case in iter_cases():
        ok = True
        for k, v in want.items():
            if k.startswith("inj_"):
                if case.get("injection", {}).get(k[4:]) != v:
                    ok = False
                    break
            elif case.get(k) != v:
                ok = False
                break
        if ok:
            return case
    raise AssertionError("case not found " + repr(want))


def main():
    need(validate_planner() == [], "planner validation")
    c = counts()
    need(c["crash"] == EXPECTED_CRASH_CASES, "crash census")
    need(c["contract"] == EXPECTED_CONTRACT_CASES, "contract census")
    need(c["total"] == EXPECTED_TOTAL_CASES, "total census")
    print("PASS exhaustive planner", {
        "crash": c["crash"], "contract": c["contract"], "total": c["total"]
    }, EXPECTED_CASESET_SHA256)

    need(len(transaction("fresh_alloc_full")) == 14, "fresh allocating write count")
    need(len(transaction("fresh_adopt_full")) == 11, "adopt write count")
    need(len(transaction("first_use_s0")) == 6, "first-use write count")
    for scenario in ("fresh_alloc_full", "fresh_adopt_full", "first_use_s0"):
        base = target_baseline(scenario)
        need(len(base) == len(transaction(scenario)), "baseline length")
        need([x["ordinal"] for x in base] == list(range(len(base))), "baseline ordinals")
        need(all(x["count"] == 1 and x["flush_ordinal"] == x["ordinal"] for x in base), "write/flush pairing")
    print("PASS exact promote write plans and per-write flush coordinates")

    stage_expected = {
        "row1": ("TAPE_OK", [1]),
        "row2": ("TAPE_OK", [2]),
        "row3": ("TAPE_OK", [3]),
        "row1_s0": ("TAPE_OK", [1]),
        "unmatched": ("TAPE_ERR_INCONSISTENT", []),
    }
    for variant, want in stage_expected.items():
        snap = snapshot(stage_fixture(variant))
        got = inspect_snapshot(snap, "A")
        need(got["mount_result"] == want[0], f"{variant} mount")
        need(got.get("resume_rows", []) == want[1], f"{variant} rows")
    print("PASS §9.3.3 exact-one stage oracle including S==0 and unmatched refusal")

    rows_seen = set()
    representative = {}
    for case in iter_cases():
        if case["scope"] != "crash" or case["scenario"] == "closure":
            continue
        row = expected_recovery_row(case)
        rows_seen.add(row)
        representative.setdefault(row, case)
    need(rows_seen == set(range(1, 12)), f"recovery rows {sorted(rows_seen)}")
    for row in range(1, 12):
        obs = expected_observation(representative[row])
        validate_case(representative[row], obs)
    print("PASS all eleven §9.3.4 recovery rows represented by raw crash cases")

    for phase in ("step4", "step5_decline", "step9"):
        for seed in (
            "primary_only", "mirror_only",
            "primary_current_mirror_stale", "mirror_current_primary_stale",
        ):
            case = find(
                scope="crash", scenario="closure", phase=phase, seed=seed,
                mode="write_through", inj_kind="torn_partner", inj_landed_bytes=37,
            )
            validate_case(case, expected_observation(case))
            case = find(
                scope="crash", scenario="closure", phase=phase, seed=seed,
                mode="write_through", inj_kind="after_partner", inj_landed_bytes=512,
            )
            validate_case(case, expected_observation(case))
    print("PASS promote superblock two-interruption closure / no stale-generation rollback")

    contract = 0
    for case in iter_cases():
        if case["scope"] == "contract":
            validate_case(case, expected_observation(case))
            contract += 1
    need(contract == EXPECTED_CONTRACT_CASES, "contract census")
    print("PASS promote re-run/headroom/position/WP-12a raw-fact contract census", contract)

    # Crash boundary negative controls.
    case = representative[5]
    obs = expected_observation(case)
    obs["injection_fired"] = False
    reject(lambda: validate_case(case, obs), "skipped injection")

    obs = expected_observation(case)
    obs["target_baseline"][0], obs["target_baseline"][1] = (
        obs["target_baseline"][1], obs["target_baseline"][0]
    )
    reject(lambda: validate_case(case, obs), "reordered target baseline")

    obs = expected_observation(case)
    raw = bytearray.fromhex(obs["post_snapshot"]["chunk0_hex"]["3"])
    raw[0] ^= 0x80
    obs["post_snapshot"]["chunk0_hex"]["3"] = bytes(raw).hex()
    reject(lambda: validate_case(case, obs), "durable raw-byte drift")

    # The running sequence rule must catch a second structurally valid slot using
    # an already-issued sequence, even when that slot is not §5.2-live.
    bad = copy.deepcopy(completed_snapshot())
    hdr, _ = index_blocks(503, 0, [(3, 0, 128)])
    bad["a1_header_hex"] = hdr.hex()
    reject_media(lambda: require_unique_structural_sequences(bad), "duplicate structural sequence")

    unmatched = snapshot(stage_fixture("unmatched"))
    need(inspect_snapshot(unmatched, "A")["mount_result"] == "TAPE_ERR_INCONSISTENT", "unmatched stage accepted")

    # Re-run and capacity controls.
    case = find(scope="contract", family="rerun_row", row=7)
    obs = expected_observation(case)
    obs["block_events"].append({"op": "write", "kind": "chunk", "lba": 9999, "count": 1, "rc": 0})
    reject(lambda: validate_case(case, obs), "unnecessary second chunk copy")

    case = find(scope="contract", family="rerun_special", variant="exact_tail_capacity")
    obs = expected_observation(case)
    obs["call_result"] = "TAPE_ERR_CARTRIDGE_FULL"
    reject(lambda: validate_case(case, obs), "false full at exact tail")

    case = find(scope="contract", family="rerun_special", variant="repeated_between3_4")
    obs = expected_observation(case)
    obs["attempts"][2]["staging_start"] = 4
    reject(lambda: validate_case(case, obs), "successive staging run consumed")

    # Stored position and headroom controls.
    case = find(scope="contract", family="stored_position", variant="full_path")
    obs = expected_observation(case)
    obs["calls"][0]["position_table"] = {"A": None, "B": None}
    reject(lambda: validate_case(case, obs), "positions cleared on nonterminal continuation")

    case = find(scope="contract", family="headroom_short", branch="fresh_alloc_run", counter="sequence")
    obs = expected_observation(case)
    obs["block_events"] = [{"op": "write", "lba": 2048, "count": 1, "rc": 0}]
    reject(lambda: validate_case(case, obs), "headroom refusal wrote media")

    case = find(scope="contract", family="headroom_special", variant="fresh_alloc_seq_FFFFFFFC")
    obs = expected_observation(case)
    obs["call_result"] = "TAPE_OK"
    reject(lambda: validate_case(case, obs), "historical FC partial-commit hazard")

    case = find(scope="contract", family="shared_sequence")
    obs = expected_observation(case)
    obs["index_commit_sequences"][0] = 11
    reject(lambda: validate_case(case, obs), "side-local sequence base")

    # WP-12a independence controls.
    case = find(scope="contract", family="promote_in_progress_row", column="seek")
    obs = expected_observation(case)
    obs["after_probe"]["progress_blocks"] += 1
    reject(lambda: validate_case(case, obs), "BUSY advanced operation")

    obs = expected_observation(case)
    obs["operation_running_after"] = True
    reject(lambda: validate_case(case, obs), "product-side derived verdict")

    case = find(scope="contract", family="own_device_failure")
    obs = expected_observation(case)
    obs["transport_after"] = "Mounted, idle"
    reject(lambda: validate_case(case, obs), "own-device failure escaped FAULTED")

    case = find(scope="contract", family="faulted_row", column="service")
    obs = expected_observation(case)
    obs["probe"]["block_events"] = [{"op": "read", "lba": 2048, "count": 1, "rc": 0}]
    reject(lambda: validate_case(case, obs), "FAULTED service touched media")

    case = find(scope="contract", family="faulted_row", column="abort")
    obs = expected_observation(case)
    obs["probe"]["frames_owed_after"] = 9
    reject(lambda: validate_case(case, obs), "FAULTED abort did not drain owed frames")

    case = find(scope="contract", family="callback_reentry", column="promote")
    obs = expected_observation(case)
    obs["callback_after"]["callback_entry_count"] = 2
    obs["callback_after"]["callback_max_depth"] = 2
    reject(lambda: validate_case(case, obs), "callback recursion")

    case = find(scope="contract", family="small_budget_completion")
    obs = expected_observation(case)
    obs["call_sequence"][1]["operation_token"] = "restarted"
    reject(lambda: validate_case(case, obs), "small-budget restart")

    rep_case = representative[7]
    rep_obs = expected_observation(rep_case)
    rep = failure_reproducer(rep_case, rep_obs, "synthetic")
    for key in ("case", "phase", "injection", "pre_snapshot", "post_snapshot", "actual_mount_A", "actual_mount_B"):
        need(rep.get(key) is not None, "failure reproducer missing " + key)

    print("PASS negative controls and exact failure reproducer")
    print("PASS all R29-A promote crash/resume + promote long-op self-tests")


if __name__ == "__main__":
    main()
