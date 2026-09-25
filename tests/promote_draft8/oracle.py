#!/usr/bin/env python3
"""Independent byte oracle and raw-fact contract validator for R29-A."""
from __future__ import annotations
import copy
import hashlib

from fixture import (
    BLOCK, PROMOTED_BLOCK, OLD_A_BLOCK, closure_initial, freeze_media,
    scenario_initial, snapshot, stage_fixture, target_baseline, transaction,
)
from media import (
    MediaError, free_next, inspect_snapshot, logical_fingerprint,
    render_sha256, require_unique_structural_sequences, resume_rows,
)
from planner import HEADROOM_BRANCHES, PROMOTE_ROW_COLUMNS

MAX_WRITABLE = 0xFFFFFFFD

class VerificationError(RuntimeError):
    pass


def need(c, m):
    if not c:
        raise VerificationError(m)


FORBIDDEN_DERIVED_KEYS = frozenset({
    "operation_running_after", "work_advanced", "next_continuation_advanced",
    "state_changed", "recursed", "audio_continues", "source_faulted",
    "same_operation", "restart_count", "row_matched", "positions_cleared",
    "headroom_ok", "completed", "no_second_copy", "unique_stage_row",
})


def _reject_derived(value, path="observation"):
    if isinstance(value, dict):
        for k, v in value.items():
            need(k not in FORBIDDEN_DERIVED_KEYS, f"derived verdict forbidden: {path}.{k}")
            _reject_derived(v, path + "." + k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _reject_derived(v, f"{path}[{i}]")


def _copy_media(media):
    return {
        "total_chunks": media["total_chunks"],
        "blocks": {k: bytearray(v) for k, v in media["blocks"].items()},
    }


def _flush(working, durable):
    durable["blocks"] = {k: bytearray(v) for k, v in working["blocks"].items()}


def _full_write(media, w):
    media["blocks"][w["lba"]][:] = w["data"]


def _torn_write(working, durable, w, landed):
    need(1 <= landed < BLOCK, "bad torn length")
    lba = w["lba"]
    working["blocks"][lba][:landed] = w["data"][:landed]
    durable["blocks"][lba][:landed] = w["data"][:landed]


def prefix_media(scenario, writes):
    base = _copy_media(scenario_initial(scenario))
    for w in transaction(scenario)[:writes]:
        _full_write(base, w)
    return freeze_media(base)


def prefix_snapshot(scenario, writes):
    return snapshot(prefix_media(scenario, writes))


def completed_snapshot(scenario="fresh_alloc_full"):
    return prefix_snapshot(scenario, len(transaction(scenario)))


RERUN_SEEDS = {
    1: ("fresh_alloc_full", 1),   # copy may be durable, step 2 not committed
    2: ("fresh_alloc_full", 3),   # A header committed, invalid under old H
    3: ("fresh_adopt_full", 2),   # adopt: A committed, B unchanged compact run
    4: ("fresh_alloc_full", 5),   # B high committed, old SB still selected
    5: ("fresh_alloc_full", 7),   # step 4 complete
    6: ("fresh_alloc_full", 8),   # low copy durable, no low index
    7: ("fresh_alloc_full", 10),  # low A committed
    8: ("fresh_alloc_full", 12),  # low A+B committed
    9: ("first_use_s0", 4),       # decline reached, clear write not landed
    10: ("first_use_s0", 6),      # decline clear complete
    11: ("fresh_alloc_full", 14), # step 9 complete
}

RERUN_CHUNK_WRITES = {
    1: 2, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1,
    7: 0, 8: 0, 9: 0, 10: 0, 11: 0,
}


def rerun_seed_snapshot(row):
    scenario, writes = RERUN_SEEDS[row]
    return prefix_snapshot(scenario, writes)


def _target_fully_durable(case):
    inj = case["injection"]
    return (
        inj["kind"] in ("after_write", "at_flush")
        and case["mode"] == "write_through"
    )


def expected_recovery_row(case):
    if case["scenario"] == "closure":
        return None
    scenario = case["scenario"]
    ordinal = case["injection"].get("write_ordinal", case["injection"].get("flush_ordinal"))
    durable = ordinal + (1 if _target_fully_durable(case) else 0)

    if scenario == "fresh_alloc_full":
        if durable <= 2:
            return 1
        if durable <= 4:
            return 2
        if durable == 5:
            return 4
        if durable <= 7:
            return 5
        if durable <= 9:
            return 6
        if durable <= 11:
            return 7
        if durable == 12:
            return 8
        return 11

    if scenario == "fresh_adopt_full":
        if durable <= 1:
            return 1
        if durable == 2:
            return 3
        if durable <= 4:
            return 5
        if durable <= 6:
            return 6
        if durable <= 8:
            return 7
        if durable == 9:
            return 8
        return 11

    if scenario == "first_use_s0":
        if ordinal <= 1:
            return 1 if durable <= 1 else 3
        if ordinal <= 3:
            return 3 if durable <= 2 else 5
        if ordinal == 4:
            return 10 if durable >= 5 else 9
        return 10

    raise VerificationError("unknown scenario")

def expected_snapshot(case):
    if case["scenario"] == "closure":
        info = closure_initial(case["phase"], case["seed"])
        working = _copy_media(info["media"])
        durable = _copy_media(info["media"])
        w = info["target"]
        kind = case["injection"]["kind"]
        if kind == "before_partner":
            pass
        elif kind == "torn_partner":
            _torn_write(working, durable, w, case["injection"]["landed_bytes"])
        elif kind in ("after_partner", "at_partner_flush"):
            _full_write(working, w)
            if case["mode"] == "write_through":
                _full_write(durable, w)
        else:
            raise VerificationError("unknown closure injection")
        return snapshot(freeze_media(durable))

    base = scenario_initial(case["scenario"])
    working = _copy_media(base)
    durable = _copy_media(base)
    tx = transaction(case["scenario"])
    inj = case["injection"]
    target = inj.get("write_ordinal", inj.get("flush_ordinal"))

    for i, w in enumerate(tx):
        if i < target:
            _full_write(working, w)
            if case["mode"] == "write_through":
                _full_write(durable, w)
            _flush(working, durable)
            continue
        if i > target:
            break

        kind = inj["kind"]
        if kind == "before_write":
            pass
        elif kind == "torn_write":
            _torn_write(working, durable, w, inj["landed_bytes"])
        elif kind in ("after_write", "at_flush"):
            _full_write(working, w)
            if case["mode"] == "write_through":
                _full_write(durable, w)
        else:
            raise VerificationError("unknown injection")
        break

    return snapshot(freeze_media(durable))


def crash_baseline(case):
    if case["scenario"] != "closure":
        return target_baseline(case["scenario"])
    info = closure_initial(case["phase"], case["seed"])
    w = info["target"]
    return [{
        "ordinal": 0,
        "phase": w["phase"],
        "kind": w["kind"],
        "lba": w["lba"],
        "count": 1,
        "sha256": hashlib.sha256(w["data"]).hexdigest(),
        "flush_ordinal": 0,
    }]


def expected_crash_observation(case):
    pre = (
        snapshot(closure_initial(case["phase"], case["seed"])["media"])
        if case["scenario"] == "closure"
        else snapshot(scenario_initial(case["scenario"]))
    )
    post = expected_snapshot(case)
    a = inspect_snapshot(post, "A")
    b = inspect_snapshot(post, "B")
    obs = {
        "format": "PROMOTE-OBSERVATION-1",
        "case_index": case["case_index"],
        "scope": "crash",
        "pre_snapshot": pre,
        "post_snapshot": post,
        "target_baseline": crash_baseline(case),
        "injection_fired": True,
        "actual_mount_A": a["mount_result"],
        "actual_mount_B": b["mount_result"],
    }
    if a["mount_result"] == "TAPE_OK":
        obs["actual_audio_A_sha256"] = render_sha256(post, "A")
    if b["mount_result"] == "TAPE_OK":
        obs["actual_audio_B_sha256"] = render_sha256(post, "B")
    return obs


def _op_state(token="promote-op-1", progress=10, events=100):
    return {
        "operation_token": token,
        "progress_blocks": progress,
        "own_device_event_count": events,
    }


def _render_probe():
    return {
        "fn": "tape_render",
        "result": "TAPE_OK",
        "rendered": 2,
        "output_hex": "0100020003000400",
        "block_events": [],
    }


def _status_probe():
    return {
        "calls": [
            {"fn": "tape_status", "result": "TAPE_OK"},
            {"fn": "tape_get_info", "result": "TAPE_OK"},
            {"fn": "tape_tell", "result": "TAPE_OK", "position": 64},
        ],
        "block_events": [],
    }


BUSY_COLUMNS = frozenset(set(PROMOTE_ROW_COLUMNS) - {"render", "service", "status_info_tell", "promote"})
REENTRY_ALLOWED = frozenset({"render", "status_info_tell"})
FAULTED_ALLOWED = frozenset({"render", "status_info_tell", "abort", "unmount"})


def expected_contract_observation(case):
    fam = case["family"]
    o = {
        "format": "PROMOTE-OBSERVATION-1",
        "case_index": case["case_index"],
        "scope": "contract",
        "family": fam,
    }

    if fam == "stage_oracle":
        snap = snapshot(stage_fixture(case["variant"]))
        o.update({"variant": case["variant"], "snapshot": snap, "actual_mount_result": inspect_snapshot(snap, "A")["mount_result"]})

    elif fam == "rerun_row":
        row = case["row"]
        seed = rerun_seed_snapshot(row)
        copies = RERUN_CHUNK_WRITES[row]
        events = [
            {"op": "write", "kind": "chunk", "lba": 2048 + i * 1024, "count": 1, "rc": 0}
            for i in range(copies)
        ]
        o.update({
            "row": row,
            "seed_snapshot": seed,
            "call_result": "TAPE_OK",
            "block_events": events,
            "terminal_snapshot": completed_snapshot(),
        })

    elif fam == "rerun_special":
        v = case["variant"]
        if v == "exact_tail_capacity":
            o.update({
                "variant": v,
                "seed_snapshot": rerun_seed_snapshot(4),
                "block_count": 2048 + 4 * 1024 + 1,
                "call_result": "TAPE_OK",
                "block_events": [{"op": "write", "kind": "chunk", "lba": 2048, "count": 1, "rc": 0}],
                "terminal_snapshot": completed_snapshot("fresh_adopt_full"),
            })
        else:
            o.update({
                "variant": v,
                "attempts": [
                    {"staging_start": 3, "free_next_before": 4, "chunk_write_lbas": [2048]},
                    {"staging_start": 3, "free_next_before": 4, "chunk_write_lbas": [2048]},
                    {"staging_start": 3, "free_next_before": 4, "chunk_write_lbas": [2048]},
                ],
            })

    elif fam == "stored_position":
        calls = []
        if case["variant"] != "nothing_to_do":
            calls.append({
                "result": "TAPE_OK", "more_work": True,
                "position_table": {"A": 111, "B": 222},
            })
        calls.append({
            "result": "TAPE_OK", "more_work": False,
            "position_table": {"A": None, "B": None},
        })
        o.update({
            "variant": case["variant"],
            "position_table_before": {"A": 111, "B": 222},
            "calls": calls,
        })

    elif fam in ("headroom_exact", "headroom_short"):
        branch = case["branch"]
        sn, gn = HEADROOM_BRANCHES[branch]
        seq = MAX_WRITABLE - sn
        gen = MAX_WRITABLE - gn
        if fam == "headroom_short":
            if case["counter"] == "sequence":
                seq += 1
            else:
                gen += 1
        refused = fam == "headroom_short"
        o.update({
            "branch": branch,
            "counter_values": {"sequence": seq, "sb_generation": gen},
            "call_result": "TAPE_ERR_SEQUENCE_EXHAUSTED" if refused else "TAPE_OK",
            "block_events": [] if refused else [{"op": "write", "kind": "first_branch_write", "lba": 2048, "count": 1, "rc": 0}],
        })
        if fam == "headroom_short":
            o["counter"] = case["counter"]

    elif fam == "headroom_special":
        v = case["variant"]
        if v == "fresh_decline_seq_FFFFFFFB":
            o.update({
                "variant": v,
                "counter_values": {"sequence": 0xFFFFFFFB, "sb_generation": 10},
                "call_result": "TAPE_OK",
                "index_commit_sequences": [0xFFFFFFFC, 0xFFFFFFFD],
                "superblock_generations": [11],
            })
        elif v == "fresh_alloc_seq_FFFFFFFC":
            o.update({
                "variant": v,
                "counter_values": {"sequence": 0xFFFFFFFC, "sb_generation": 10},
                "call_result": "TAPE_ERR_SEQUENCE_EXHAUSTED",
                "block_events": [],
            })
        else:
            o.update({
                "variant": v,
                "counter_values": {"sequence": 0xFFFFFFFC, "sb_generation": 10},
                "call_result": "TAPE_OK",
                "index_commit_sequences": [],
                "superblock_generations": [11],
            })

    elif fam == "zero_needed_reserved":
        o.update({
            "counter": case["counter"],
            "value": case["value"],
            "call_result": "TAPE_OK",
            "block_events": [],
        })

    elif fam == "shared_sequence":
        o.update({
            "structural_sequences_before": {"A0": 10, "A1": 9, "B0": 500, "B1": 499},
            "index_commit_sequences": [501, 502, 503, 504],
            "call_result": "TAPE_OK",
        })

    elif fam == "counter_domains":
        o.update({
            "index_only": {"sequence_before": 500, "sequence_after": 501, "sb_generation_before": 10, "sb_generation_after": 10},
            "superblock_only": {"sequence_before": 501, "sequence_after": 501, "sb_generation_before": 10, "sb_generation_after": 11},
        })

    elif fam == "entry_refusal":
        result = {
            "empty_b": "TAPE_ERR_INVALID_ARG",
            "degraded_b": "TAPE_ERR_NO_VALID_INDEX",
            "capacity_full": "TAPE_ERR_CARTRIDGE_FULL",
        }[case["variant"]]
        o.update({"variant": case["variant"], "call_result": result, "block_events": []})

    elif fam == "promote_in_progress_row":
        c = case["column"]
        before = _op_state()
        o.update({"column": c, "before": before})
        if c in BUSY_COLUMNS:
            o.update({
                "probe": {"fn": c, "result": "TAPE_ERR_BUSY", "block_events": []},
                "after_probe": _op_state(),
                "next_continuation": {
                    "before": _op_state(),
                    "call": {"fn": "tape_promote", "result": "TAPE_OK", "more_work": True},
                    "after": _op_state(progress=11, events=101),
                },
            })
        elif c == "promote":
            o.update({
                "probe": {"fn": "tape_promote", "result": "TAPE_OK", "more_work": True, "block_events": [{"op": "write", "lba": 2048, "count": 1, "rc": 0}]},
                "after_probe": _op_state(progress=11, events=101),
            })
        elif c == "render":
            o.update({"probe": _render_probe(), "after_probe": _op_state()})
        elif c == "service":
            o.update({"probe": {"fn": "tape_service", "result": "TAPE_OK", "block_events": [{"op": "read", "lba": 2048, "count": 1, "rc": 0}]}, "after_probe": _op_state()})
        else:
            o.update({"probe": _status_probe(), "after_probe": _op_state()})

    elif fam == "zero_budget":
        token = None if case["variant"] == "initiate" else "promote-op-1"
        before = _op_state(token=token, progress=0 if token is None else 10, events=0 if token is None else 100)
        o.update({
            "variant": case["variant"], "before": before,
            "call": {"fn": "tape_promote", "block_budget": 0, "result": "TAPE_ERR_INVALID_ARG", "block_events": []},
            "after": dict(before),
        })

    elif fam == "allowed_mutables":
        o.update({
            "before": _op_state(),
            "initial_args": {"block_budget": 1, "more_work_ptr": "mw-a", "cb": "cb-a", "user": "u-a"},
            "call_args": {"block_budget": 2, "more_work_ptr": "mw-b", "cb": "cb-b", "user": "u-b"},
            "call": {"fn": "tape_promote", "result": "TAPE_OK", "more_work": True},
            "after": _op_state(progress=11, events=101),
        })

    elif fam == "own_device_failure":
        o.update({
            "transport_before": "Playing",
            "operation_before": _op_state(),
            "call": {"fn": "tape_promote", "result": "TAPE_ERR_IO", "more_work": False},
            "own_device_events": [{"op": "write", "lba": 2048, "count": 1, "rc": 5}],
            "transport_after": "FAULTED",
        })

    elif fam == "faulted_row":
        c = case["column"]
        o["column"] = c
        if c == "render":
            o["probe"] = {
                "calls": [
                    {"result": "TAPE_OK", "ring_frames_before": 4, "ring_frames_after": 2, "rendered": 2, "output_hex": "0100020003000400"},
                    {"result": "TAPE_OK", "ring_frames_before": 2, "ring_frames_after": 0, "rendered": 2, "output_hex": "0500060007000800"},
                    {"result": "TAPE_ERR_UNDERRUN", "ring_frames_before": 0, "ring_frames_after": 0, "rendered": 0, "output_hex": ""},
                ],
                "block_events": [],
            }
        elif c == "status_info_tell":
            o["probe"] = _status_probe()
        elif c == "abort":
            o["probe"] = {"fn": "tape_abort", "result": "TAPE_OK", "frames_owed_before": 9, "frames_owed_after": 0, "armed_before": True, "block_events": []}
        elif c == "unmount":
            o["probe"] = {"fn": "tape_unmount", "result": "TAPE_OK", "block_events": []}
        else:
            o["probe"] = {"fn": c, "result": "TAPE_ERR_FAULTED", "block_events": []}

    elif fam == "callback_reentry":
        c = case["column"]
        before = {"operation": _op_state(), "callback_entry_count": 1, "callback_max_depth": 1}
        if c == "render":
            nested = _render_probe()
        elif c == "status_info_tell":
            nested = _status_probe()
        else:
            nested = {"fn": c, "result": "TAPE_ERR_BUSY", "block_events": []}
        o.update({
            "column": c,
            "callback_before": before,
            "nested_call": nested,
            "callback_after": {"operation": _op_state(), "callback_entry_count": 1, "callback_max_depth": 1},
            "next_continuation": {
                "before": _op_state(),
                "call": {"fn": "tape_promote", "result": "TAPE_OK", "more_work": True},
                "after": _op_state(progress=11, events=101),
            },
        })

    elif fam == "small_budget_completion":
        o.update({
            "call_sequence": [
                {"fn": "tape_promote", "budget": 1, "result": "TAPE_OK", "more_work": True, "operation_token": "promote-op-1", "progress_before": 0, "progress_after": 1},
                {"fn": "tape_promote", "budget": 1, "result": "TAPE_OK", "more_work": True, "operation_token": "promote-op-1", "progress_before": 1, "progress_after": 2},
                {"fn": "tape_promote", "budget": 1, "result": "TAPE_OK", "more_work": False, "operation_token": "promote-op-1", "progress_before": 2, "progress_after": 3},
            ],
            "terminal_snapshot": completed_snapshot(),
        })
    else:
        raise VerificationError("unknown contract family")

    return o


def expected_observation(case):
    if case["scope"] == "crash":
        return expected_crash_observation(case)
    return expected_contract_observation(case)


def _state(v, label, allow_none=False):
    need(isinstance(v, dict), f"{label} missing")
    token = v.get("operation_token")
    if not allow_none:
        need(isinstance(token, str) and token, f"{label} token")
    else:
        need(token is None or isinstance(token, str), f"{label} token")
    for k in ("progress_blocks", "own_device_event_count"):
        need(isinstance(v.get(k), int) and not isinstance(v.get(k), bool) and v[k] >= 0, f"{label}.{k}")
    return v


def _same_state(a, b, label, allow_none=False):
    a = _state(a, label + ".before", allow_none)
    b = _state(b, label + ".after", allow_none)
    need(a == b, f"{label} state changed")


def _advance(a, b, label):
    a = _state(a, label + ".before")
    b = _state(b, label + ".after")
    need(a["operation_token"] == b["operation_token"], f"{label} restarted")
    need(b["progress_blocks"] > a["progress_blocks"], f"{label} no progress")
    need(b["own_device_event_count"] >= a["own_device_event_count"], f"{label} event regression")


def _events(events, label):
    need(isinstance(events, list), f"{label} not list")
    for i, e in enumerate(events):
        need(isinstance(e, dict), f"{label}[{i}]")
        need(e.get("op") in ("read", "write", "flush"), f"{label}[{i}] op")
        if e.get("op") in ("read", "write"):
            need(isinstance(e.get("lba"), int) and e["lba"] >= 0, f"{label}[{i}] lba")
    return events


def _validate_render(p, label):
    need(isinstance(p, dict), f"{label} missing")
    need(p.get("fn") == "tape_render", f"{label} fn")
    need(p.get("result") == "TAPE_OK", f"{label} result")
    need(isinstance(p.get("rendered"), int) and p["rendered"] > 0, f"{label} rendered")
    raw = bytes.fromhex(p.get("output_hex", ""))
    need(raw and any(raw), f"{label} silent/empty")
    need(p.get("block_events") == [], f"{label} media touched")


def _validate_status(p, label):
    need(isinstance(p, dict), f"{label} missing")
    calls = p.get("calls")
    need(isinstance(calls, list) and [x.get("fn") for x in calls] == ["tape_status", "tape_get_info", "tape_tell"], f"{label} calls")
    need(all(x.get("result") == "TAPE_OK" for x in calls), f"{label} result")
    need(p.get("block_events") == [], f"{label} media touched")


def _validate_terminal_promoted(snap):
    ins = inspect_snapshot(snap, "A")
    need(ins["mount_result"] == "TAPE_OK", "terminal promote not mountable")
    sb = ins["sb"]["selected"]
    need(sb["promote_stage"] == 0 and sb["a_high_water"] == 1, "terminal water/stage")
    need(ins["A"]["selected"]["entries"] == [(0, 0, 128)], "terminal A layout")
    need(ins["B"]["selected"]["entries"] == [(0, 0, 128)], "terminal B layout")
    need(render_sha256(snap, "A") == hashlib.sha256(PROMOTED_BLOCK).hexdigest(), "terminal A audio")
    need(render_sha256(snap, "B") == hashlib.sha256(PROMOTED_BLOCK).hexdigest(), "terminal B audio")
    require_unique_structural_sequences(snap)


def _validate_contract(case, obs):
    _reject_derived(obs)
    fam = case["family"]
    need(obs.get("family") == fam, "contract family")

    if fam == "stage_oracle":
        need(obs.get("variant") == case["variant"], "stage variant")
        snap = obs.get("snapshot")
        ins = inspect_snapshot(snap, "A")
        expected = {
            "row1": ("TAPE_OK", [1]),
            "row2": ("TAPE_OK", [2]),
            "row3": ("TAPE_OK", [3]),
            "row1_s0": ("TAPE_OK", [1]),
            "unmatched": ("TAPE_ERR_INCONSISTENT", []),
        }[case["variant"]]
        need(ins["mount_result"] == expected[0], "stage mount result")
        need(ins.get("resume_rows", []) == expected[1], "stage row match")
        need(obs.get("actual_mount_result") == ins["mount_result"], "stage product/raw mismatch")

    elif fam == "rerun_row":
        row = case["row"]
        need(obs.get("row") == row, "rerun row")
        need(obs.get("seed_snapshot") == rerun_seed_snapshot(row), "rerun seed bytes")
        need(obs.get("call_result") == "TAPE_OK", "rerun result")
        events = _events(obs.get("block_events"), "rerun events")
        copies = sum(1 for e in events if e.get("op") == "write" and e.get("kind") == "chunk")
        need(copies == RERUN_CHUNK_WRITES[row], f"rerun row {row} copied {copies}")
        _validate_terminal_promoted(obs.get("terminal_snapshot"))

    elif fam == "rerun_special":
        if case["variant"] == "exact_tail_capacity":
            need(obs.get("variant") == case["variant"], "tail variant")
            need(obs.get("seed_snapshot") == rerun_seed_snapshot(4), "tail seed")
            need(obs.get("call_result") == "TAPE_OK", "tail false full")
            events = _events(obs.get("block_events"), "tail events")
            chunk_writes = [e for e in events if e.get("op") == "write" and e.get("kind") == "chunk"]
            need(len(chunk_writes) == 1 and chunk_writes[0]["lba"] == 2048, "tail did not adopt in place")
            _validate_terminal_promoted(obs.get("terminal_snapshot"))
        else:
            attempts = obs.get("attempts")
            need(isinstance(attempts, list) and len(attempts) >= 3, "retry attempts")
            starts = [x.get("staging_start") for x in attempts]
            frees = [x.get("free_next_before") for x in attempts]
            need(len(set(starts)) == 1 and starts[0] == 3, "retry consumed staging runs")
            need(len(set(frees)) == 1 and frees[0] == 4, "retry free_next drift")
            for x in attempts:
                need(all(lba < 2048 + 3 * 1024 for lba in x.get("chunk_write_lbas", [])), "retry copied new high staging run")

    elif fam == "stored_position":
        need(obs.get("variant") == case["variant"], "position variant")
        before = obs.get("position_table_before")
        need(before == {"A": 111, "B": 222}, "position seed")
        calls = obs.get("calls")
        need(isinstance(calls, list) and calls, "position calls")
        for c in calls[:-1]:
            need(c.get("more_work") is True, "nonterminal flag")
            need(c.get("position_table") == before, "position cleared before terminal")
        terminal = calls[-1]
        need(terminal.get("result") == "TAPE_OK" and terminal.get("more_work") is False, "terminal call")
        need(terminal.get("position_table") == {"A": None, "B": None}, "terminal positions not cleared")

    elif fam in ("headroom_exact", "headroom_short"):
        branch = case["branch"]
        need(obs.get("branch") == branch, "headroom branch")
        sn, gn = HEADROOM_BRANCHES[branch]
        vals = obs.get("counter_values")
        need(isinstance(vals, dict), "counter values")
        ok = ((sn == 0 or vals["sequence"] + sn <= MAX_WRITABLE) and (gn == 0 or vals["sb_generation"] + gn <= MAX_WRITABLE))
        if fam == "headroom_exact":
            need(ok and obs.get("call_result") == "TAPE_OK", "exact headroom refused")
        else:
            need(not ok, "short case not actually short")
            need(obs.get("call_result") == "TAPE_ERR_SEQUENCE_EXHAUSTED", "short headroom result")
            need(obs.get("block_events") == [], "short headroom wrote media")

    elif fam == "headroom_special":
        v = case["variant"]
        need(obs.get("variant") == v, "headroom special variant")
        if v == "fresh_decline_seq_FFFFFFFB":
            need(obs.get("call_result") == "TAPE_OK", "fresh decline refused")
            need(obs.get("index_commit_sequences") == [0xFFFFFFFC, 0xFFFFFFFD], "fresh decline sequence writes")
        elif v == "fresh_alloc_seq_FFFFFFFC":
            need(obs.get("call_result") == "TAPE_ERR_SEQUENCE_EXHAUSTED", "FC hazard not refused")
            need(obs.get("block_events") == [], "FC hazard wrote")
        else:
            need(obs.get("call_result") == "TAPE_OK", "resume decline refused")
            need(obs.get("index_commit_sequences") == [], "resume decline committed index")

    elif fam == "zero_needed_reserved":
        need(obs.get("counter") == case["counter"] and obs.get("value") == case["value"], "reserved case")
        need(obs.get("call_result") == "TAPE_OK" and obs.get("block_events") == [], "zero-needed consulted counter")

    elif fam == "shared_sequence":
        seqs = obs.get("structural_sequences_before")
        need(max(seqs.values()) == 500, "shared base")
        need(obs.get("index_commit_sequences") == [501, 502, 503, 504], "running sequence base")

    elif fam == "counter_domains":
        i = obs.get("index_only")
        s = obs.get("superblock_only")
        need(i["sequence_after"] == i["sequence_before"] + 1, "index sequence")
        need(i["sb_generation_after"] == i["sb_generation_before"], "index advanced sb generation")
        need(s["sequence_after"] == s["sequence_before"], "sb update advanced sequence")
        need(s["sb_generation_after"] == s["sb_generation_before"] + 1, "sb generation")

    elif fam == "entry_refusal":
        expected = {"empty_b": "TAPE_ERR_INVALID_ARG", "degraded_b": "TAPE_ERR_NO_VALID_INDEX", "capacity_full": "TAPE_ERR_CARTRIDGE_FULL"}[case["variant"]]
        need(obs.get("call_result") == expected, "entry refusal result")
        need(obs.get("block_events") == [], "entry refusal wrote")

    elif fam == "promote_in_progress_row":
        c = case["column"]
        need(obs.get("column") == c, "row column")
        before = obs.get("before")
        after = obs.get("after_probe")
        if c in BUSY_COLUMNS:
            need(obs["probe"].get("result") == "TAPE_ERR_BUSY" and obs["probe"].get("block_events") == [], "BUSY probe")
            _same_state(before, after, "BUSY")
            cont = obs.get("next_continuation")
            need(cont["call"].get("fn") == "tape_promote" and cont["call"].get("result") == "TAPE_OK", "next continuation")
            need(cont["before"] == after, "continuation state mismatch")
            _advance(cont["before"], cont["after"], "next continuation")
            need(cont["after"]["operation_token"] == before["operation_token"], "BUSY restarted op")
        elif c == "promote":
            need(obs["probe"].get("result") == "TAPE_OK", "matching continuation")
            _advance(before, after, "matching continuation")
        else:
            _same_state(before, after, c)
            if c == "render":
                _validate_render(obs["probe"], "row render")
            elif c == "status_info_tell":
                _validate_status(obs["probe"], "row status")
            else:
                need(obs["probe"].get("result") == "TAPE_OK", "service result")

    elif fam == "zero_budget":
        allow_none = case["variant"] == "initiate"
        _same_state(obs.get("before"), obs.get("after"), "zero budget", allow_none)
        need(obs["call"].get("block_budget") == 0 and obs["call"].get("result") == "TAPE_ERR_INVALID_ARG", "zero budget result")
        need(obs["call"].get("block_events") == [], "zero budget media")

    elif fam == "allowed_mutables":
        need(set(obs.get("initial_args", {})) == {"block_budget", "more_work_ptr", "cb", "user"}, "promote arg surface")
        need(all(obs["initial_args"][k] != obs["call_args"][k] for k in obs["initial_args"]), "mutables not changed")
        need(obs["call"].get("result") == "TAPE_OK", "mutable continuation refused")
        _advance(obs["before"], obs["after"], "mutable continuation")

    elif fam == "own_device_failure":
        need(obs.get("transport_before") == "Playing", "failure pre transport")
        need(obs["call"].get("result") == "TAPE_ERR_IO" and obs["call"].get("more_work") is False, "failure termination")
        events = _events(obs.get("own_device_events"), "failure events")
        need(any(e.get("op") in ("write", "flush") and e.get("rc", 0) != 0 for e in events), "no own-device fault")
        need(obs.get("transport_after") == "FAULTED", "own-device failure not faulted")

    elif fam == "faulted_row":
        c = case["column"]
        p = obs.get("probe")
        if c not in FAULTED_ALLOWED:
            need(p.get("result") == "TAPE_ERR_FAULTED" and p.get("block_events") == [], f"FAULTED {c}")
        elif c == "render":
            calls = p.get("calls")
            need(isinstance(calls, list) and len(calls) >= 3, "faulted render sequence")
            need(calls[-1]["result"] == "TAPE_ERR_UNDERRUN" and calls[-1]["ring_frames_before"] == 0, "ring did not drain")
            need(p.get("block_events") == [], "faulted render media")
        elif c == "status_info_tell":
            _validate_status(p, "faulted status")
        elif c == "abort":
            need(p.get("result") == "TAPE_OK" and p.get("frames_owed_before", 0) > 0 and p.get("frames_owed_after") == 0, "faulted abort")
            need(p.get("armed_before") is True and p.get("block_events") == [], "faulted armed override")
        else:
            need(p.get("result") == "TAPE_OK" and p.get("block_events") == [], "faulted unmount")

    elif fam == "callback_reentry":
        c = case["column"]
        before = obs["callback_before"]
        after = obs["callback_after"]
        _same_state(before["operation"], after["operation"], "callback nested")
        need(before["callback_entry_count"] == after["callback_entry_count"] == 1, "callback re-entered")
        need(before["callback_max_depth"] == after["callback_max_depth"] == 1, "callback recursed")
        if c == "render":
            _validate_render(obs["nested_call"], "callback render")
        elif c == "status_info_tell":
            _validate_status(obs["nested_call"], "callback status")
        else:
            need(obs["nested_call"].get("result") == "TAPE_ERR_BUSY" and obs["nested_call"].get("block_events") == [], "callback BUSY")
        cont = obs["next_continuation"]
        need(cont["before"] == after["operation"], "post-callback state")
        _advance(cont["before"], cont["after"], "post-callback continuation")
        need(cont["after"]["operation_token"] == before["operation"]["operation_token"], "callback restarted op")

    elif fam == "small_budget_completion":
        seq = obs.get("call_sequence")
        need(isinstance(seq, list) and len(seq) >= 2, "small-budget sequence")
        token = seq[0].get("operation_token")
        need(all(x.get("fn") == "tape_promote" and x.get("operation_token") == token for x in seq), "same function/token")
        need(any(x.get("more_work") is True for x in seq[:-1]), "no nonterminal call")
        need(seq[-1].get("more_work") is False, "no terminal call")
        for a, b in zip(seq, seq[1:]):
            need(a["progress_after"] == b["progress_before"], "progress discontinuity")
        need(all(x["progress_after"] > x["progress_before"] for x in seq), "no progress")
        _validate_terminal_promoted(obs.get("terminal_snapshot"))

    else:
        raise VerificationError("unknown family")


def validate_case(case, obs):
    need(isinstance(obs, dict), "observation object")
    need(obs.get("format") == "PROMOTE-OBSERVATION-1", "observation format")
    need(obs.get("case_index") == case["case_index"], "case index")
    need(obs.get("scope") == case["scope"], "scope")

    if case["scope"] == "contract":
        _validate_contract(case, obs)
        return True

    need(obs.get("injection_fired") is True, "injection skipped")
    exp = expected_crash_observation(case)
    need(obs.get("pre_snapshot") == exp["pre_snapshot"], "pre snapshot")
    need(obs.get("target_baseline") == exp["target_baseline"], "target baseline")
    need(obs.get("post_snapshot") == exp["post_snapshot"], "durable post snapshot")

    post = obs["post_snapshot"]
    a = inspect_snapshot(post, "A")
    b = inspect_snapshot(post, "B")
    need(obs.get("actual_mount_A") == a["mount_result"], "A remount/raw mismatch")
    need(obs.get("actual_mount_B") == b["mount_result"], "B remount/raw mismatch")

    if a["mount_result"] == "TAPE_OK":
        need(obs.get("actual_audio_A_sha256") == render_sha256(post, "A"), "A audio digest")
    if b["mount_result"] == "TAPE_OK":
        need(obs.get("actual_audio_B_sha256") == render_sha256(post, "B"), "B audio digest")

    if case["scenario"] != "closure":
        require_unique_structural_sequences(post)
        if a["mount_result"] == "TAPE_OK":
            sb = a["sb"]["selected"]
            if sb["promote_stage"] == 1 and not a.get("degraded_b"):
                need(len(a.get("resume_rows", [])) == 1, "stage-1 media did not match exactly one resume row")
            if b["mount_result"] == "TAPE_OK":
                # B audio is always the promoted source timeline in these fixtures.
                need(render_sha256(post, "B") == hashlib.sha256(PROMOTED_BLOCK).hexdigest(), "B referenced audio corrupted")
            ad = render_sha256(post, "A")
            need(ad in {
                hashlib.sha256(OLD_A_BLOCK).hexdigest(),
                hashlib.sha256(PROMOTED_BLOCK).hexdigest(),
                hashlib.sha256(b"").hexdigest(),
            }, "A referenced audio corrupted")
    else:
        info = closure_initial(case["phase"], case["seed"])
        if a["mount_result"] == "TAPE_OK":
            generation = a["sb"]["selected"]["sb_generation"]
            need(generation >= info["current_generation"], "stale-generation rollback after closure interruption")

    return True


def failure_reproducer(case, obs, error):
    return {
        "format": "PROMOTE-FAILURE-1",
        "case": case,
        "phase": case.get("phase"),
        "injection": case.get("injection"),
        "error": str(error),
        "pre_snapshot": obs.get("pre_snapshot") if isinstance(obs, dict) else None,
        "post_snapshot": obs.get("post_snapshot") if isinstance(obs, dict) else None,
        "actual_mount_A": obs.get("actual_mount_A") if isinstance(obs, dict) else None,
        "actual_mount_B": obs.get("actual_mount_B") if isinstance(obs, dict) else None,
    }
