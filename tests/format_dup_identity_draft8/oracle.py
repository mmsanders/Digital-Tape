#!/usr/bin/env python3
"""Exact durable-byte oracle for format/duplicate identity and duplicate WP-12a."""
from __future__ import annotations

from fixture import (
    BLOCK, LBA_MIRROR, LBA_CHUNK_BASE, FRESH_DUP_UUID,
    initial_snapshot, final_index_heads, final_superblock,
    raw_shapes, target_writes, target_baseline,
)
from media import inspect_snapshot, identity_tuple
from planner import DUP_ROW_COLUMNS


class VerificationError(RuntimeError):
    pass


def need(c, m):
    if not c:
        raise VerificationError(m)


def _snapshot_bytes(snapshot):
    return {
        "primary": bytearray.fromhex(snapshot["primary_hex"]),
        "mirror": bytearray.fromhex(snapshot["mirror_hex"]),
    }


def _put_snapshot(snapshot, blocks):
    out = dict(snapshot)
    out["primary_hex"] = bytes(blocks["primary"]).hex()
    out["mirror_hex"] = bytes(blocks["mirror"]).hex()
    return out


def _copy_for_lba(lba):
    if lba == 0:
        return "primary"
    if lba == LBA_MIRROR:
        return "mirror"
    raise VerificationError("unexpected target LBA")


def expected_snapshot(case):
    need(case["scope"] == "crash", "not crash case")
    op, shape_name, mode = case["operation"], case["shape"], case["mode"]
    inj = case["injection"]
    snap = initial_snapshot(shape_name)
    working = _snapshot_bytes(snap)
    durable = {k: bytearray(v) for k, v in working.items()}
    targets = target_writes(op, shape_name)
    final_heads = False

    def successful_write(ord_):
        t = targets[ord_]
        name = _copy_for_lba(t["lba"])
        data = t["bytes"]
        working[name][:] = data
        if mode == "write_through":
            durable[name][:] = data

    def successful_flush():
        nonlocal durable
        durable = {k: bytearray(v) for k, v in working.items()}

    if inj["kind"] == "at_flush":
        stop = inj["flush_ordinal"]
        for o in range(stop):
            successful_write(o)
            successful_flush()
            if o == 1:
                final_heads = True
        if stop >= 2:
            final_heads = True
        successful_write(stop)
    else:
        stop = inj["write_ordinal"]
        for o in range(stop):
            successful_write(o)
            successful_flush()
            if o == 1:
                final_heads = True
        if stop >= 2:
            final_heads = True
        t = targets[stop]
        name = _copy_for_lba(t["lba"])
        data = t["bytes"]
        kind = inj["kind"]
        landed = inj.get("landed_bytes", 0)
        if kind == "before_write":
            pass
        elif kind == "torn_write":
            need(1 <= landed < BLOCK, "bad torn length")
            working[name][:landed] = data[:landed]
            durable[name][:landed] = data[:landed]
        elif kind == "after_write":
            need(landed == BLOCK, "bad complete length")
            working[name][:] = data
            if mode == "write_through":
                durable[name][:] = data
        else:
            raise VerificationError("unknown injection")

    out = _put_snapshot(snap, durable)
    if final_heads:
        a, b = final_index_heads(op)
        out["a0_head_hex"] = a.hex()
        out["b0_head_hex"] = b.hex()
    return out


def expected_crash_observation(case):
    pre = initial_snapshot(case["shape"])
    post = expected_snapshot(case)
    state = inspect_snapshot(post)
    obs = {
        "format": "FMTDUP-ID-OBSERVATION-1",
        "case_index": case["case_index"],
        "scope": "crash",
        "injection_fired": True,
        "pre_snapshot": pre,
        "post_snapshot": post,
        "target_baseline": target_baseline(case["operation"], case["shape"]),
        "actual_remount_result": state["mount_result"],
    }
    if state["mount_result"] == "TAPE_OK":
        obs["actual_selected_uuid"] = state.get("selected_uuid")
    return obs


BUSY_COLUMNS = frozenset(set(DUP_ROW_COLUMNS) - {"render", "service", "status_info_tell", "dup"})
REENTRY_ALLOWED = frozenset({"render", "status_info_tell"})
FIXED_DUP_ARGS = ("dst_ctx", "new_uuid", "epoch", "dst_nominal_length_s")
MUTABLE_DUP_ARGS = ("block_budget", "cb_token", "user_token")

# Product binding must not emit pre-disposed verifier judgments.  These names
# are rejected recursively, not merely ignored.
FORBIDDEN_DERIVED_KEYS = frozenset({
    "operation_running_after", "work_advanced", "next_continuation_advanced",
    "rate_unchanged", "position_unchanged", "ring_unchanged", "audio_continues",
    "source_faulted", "state_changed", "recursed", "all_calls_same_function",
    "saw_more_work_true", "terminal_more_work", "restart_count",
    "next_ordinary_continuation_advanced", "final_identity",
})


def _op_state(token="dup-op-1", progress=10, dest_events=100):
    return {
        "operation_token": token,
        "progress_blocks": progress,
        "destination_event_count": dest_events,
    }


def _terminal_dup_snapshot():
    snap = initial_snapshot("healthy_pair")
    final = final_superblock("dup")
    a0, b0 = final_index_heads("dup")
    snap["primary_hex"] = final.hex()
    snap["mirror_hex"] = final.hex()
    snap["a0_head_hex"] = a0.hex()
    snap["b0_head_hex"] = b0.hex()
    return snap


def _dup_args():
    return {
        "dst_ctx": "dst-A",
        "new_uuid": FRESH_DUP_UUID.hex(),
        "epoch": 7,
        "dst_nominal_length_s": 60,
        "block_budget": 1,
        "cb_token": "cb-A",
        "user_token": "user-A",
    }


def _render_probe(fn="tape_render"):
    return {
        "fn": fn,
        "result": "TAPE_OK",
        "rendered": 1,
        "output_hex": "01000200",
        "block_events": [],
    }


def _status_probe():
    return {
        "calls": [
            {"fn": "tape_status", "result": "TAPE_OK"},
            {"fn": "tape_get_info", "result": "TAPE_OK"},
            {"fn": "tape_tell", "result": "TAPE_OK", "position": 1234},
        ],
        "block_events": [],
    }


def expected_contract_observation(case):
    """Synthetic raw facts used only for verifier self-tests.

    Product adapters may choose different opaque tokens/counters/byte values; the
    validator below derives the verdict from relationships between those facts.
    """
    fam = case["family"]
    o = {
        "format": "FMTDUP-ID-OBSERVATION-1",
        "case_index": case["case_index"],
        "scope": "contract",
        "family": fam,
    }

    if fam == "equal_divergent_refusal":
        v = case["variant"]
        o.update({
            "variant": v,
            "call": {
                "fn": "tape_format" if v == "format_geometry" else "tape_dup",
                "result": "TAPE_ERR_DEST_TOO_SMALL" if v == "dup_capacity" else "TAPE_ERR_GEOMETRY",
            },
            "destination_events": [],
        })

    elif fam == "dup_in_progress_row":
        c = case["column"]
        before = _op_state()
        o.update({"column": c, "before": before})
        if c in BUSY_COLUMNS:
            o.update({
                "probe": {"fn": c, "result": "TAPE_ERR_BUSY", "block_events": []},
                "after_probe": _op_state(),
                "next_continuation": {
                    "before": _op_state(),
                    "call": {"fn": "tape_dup", "result": "TAPE_OK", "more_work": True},
                    "after": _op_state(progress=11, dest_events=101),
                },
            })
        elif c == "dup":
            o.update({
                "probe": {
                    "fn": "tape_dup", "result": "TAPE_OK", "more_work": True,
                    "block_events": [{"op": "write", "device": "destination", "lba": LBA_CHUNK_BASE, "count": 1, "rc": 0}],
                },
                "after_probe": _op_state(progress=11, dest_events=101),
            })
        elif c == "render":
            o.update({"probe": _render_probe(), "after_probe": _op_state()})
        elif c == "service":
            o.update({
                "probe": {
                    "fn": "tape_service", "result": "TAPE_OK",
                    "block_events": [{"op": "read", "device": "source", "lba": LBA_CHUNK_BASE, "count": 1, "rc": 0}],
                },
                "after_probe": _op_state(),
            })
        elif c == "status_info_tell":
            o.update({"probe": _status_probe(), "after_probe": _op_state()})
        else:
            raise VerificationError("unknown matrix column")

    elif fam == "zero_budget":
        v = case["variant"]
        token = None if v == "initiate" else "dup-op-1"
        before = _op_state(token=token, progress=0 if token is None else 10, dest_events=0 if token is None else 100)
        o.update({
            "variant": v,
            "before": before,
            "call": {
                "fn": "tape_dup", "block_budget": 0,
                "result": "TAPE_ERR_INVALID_ARG",
                "more_work": False if v == "initiate" else True,
                "block_events": [],
            },
            "after": dict(before),
        })

    elif fam == "changed_argument":
        a = case["argument"]
        init_args = _dup_args()
        call_args = dict(init_args)
        if a == "dst_ctx":
            call_args[a] = "dst-B"
        elif a == "new_uuid":
            call_args[a] = "00" * 16
        elif a == "epoch":
            call_args[a] = 8
        elif a == "dst_nominal_length_s":
            call_args[a] = 61
        elif a == "allowed_mutables":
            call_args["block_budget"] = 2
            call_args["cb_token"] = "cb-B"
            call_args["user_token"] = "user-B"
        else:
            raise VerificationError("unknown changed argument")
        before = _op_state()
        advancing = a == "allowed_mutables"
        o.update({
            "argument": a,
            "initial_args": init_args,
            "call_args": call_args,
            "before": before,
            "call": {
                "fn": "tape_dup",
                "result": "TAPE_OK" if advancing else "TAPE_ERR_INVALID_ARG",
                "more_work": True,
                "block_events": [] if not advancing else [
                    {"op": "write", "device": "destination", "lba": LBA_CHUNK_BASE, "count": 1, "rc": 0}
                ],
            },
            "after": _op_state(progress=11, dest_events=101) if advancing else dict(before),
        })

    elif fam == "destination_failure_playing":
        ring = {
            "read_index": 2,
            "write_index": 6,
            "valid_frames": 4,
            "content_sha256": "11" * 32,
        }
        source = {
            "transport_state": "Playing",
            "rate_q16_16": 65536,
            "position": 1234,
            "ring": ring,
        }
        o.update({
            "source_before": source,
            "call": {"fn": "tape_dup", "result": "TAPE_ERR_IO", "more_work": False},
            "destination_events": [
                {"op": "write", "device": "destination", "lba": LBA_CHUNK_BASE, "count": 1, "rc": 5}
            ],
            "source_events": [
                {"op": "read", "device": "source", "lba": LBA_CHUNK_BASE, "count": 1, "rc": 0}
            ],
            "source_after": {
                "transport_state": "Playing",
                "rate_q16_16": 65536,
                "position": 1234,
                "ring": dict(ring),
            },
            "render_after_failure": _render_probe(),
        })

    elif fam == "callback_reentry":
        c = case["column"]
        before = {
            "operation": _op_state(),
            "callback_entry_count": 1,
            "callback_max_depth": 1,
        }
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
            "callback_after": {
                "operation": _op_state(),
                "callback_entry_count": 1,
                "callback_max_depth": 1,
            },
            "next_continuation": {
                "before": _op_state(),
                "call": {"fn": "tape_dup", "result": "TAPE_OK", "more_work": True},
                "after": _op_state(progress=11, dest_events=101),
            },
        })

    elif fam == "faulted_source":
        o.update({
            "variant": "dup_call",
            "source_state": "FAULTED",
            "call": {
                "fn": "tape_dup",
                "result": "TAPE_ERR_FAULTED",
                "block_events": [],
            },
        })

    elif fam == "small_budget_completion":
        o.update({
            "variant": "dup",
            "call_sequence": [
                {
                    "fn": "tape_dup", "block_budget": 1, "result": "TAPE_OK", "more_work": True,
                    "operation_token": "dup-op-1", "progress_before": 0, "progress_after": 1,
                    "destination_event_count_before": 0, "destination_event_count_after": 1,
                },
                {
                    "fn": "tape_dup", "block_budget": 1, "result": "TAPE_OK", "more_work": True,
                    "operation_token": "dup-op-1", "progress_before": 1, "progress_after": 2,
                    "destination_event_count_before": 1, "destination_event_count_after": 2,
                },
                {
                    "fn": "tape_dup", "block_budget": 1, "result": "TAPE_OK", "more_work": False,
                    "operation_token": "dup-op-1", "progress_before": 2, "progress_after": 3,
                    "destination_event_count_before": 2, "destination_event_count_after": 3,
                },
            ],
            "terminal_snapshot": _terminal_dup_snapshot(),
        })

    else:
        raise VerificationError("unknown contract family")

    return o


def expected_observation(case):
    return expected_crash_observation(case) if case["scope"] == "crash" else expected_contract_observation(case)


def _reject_derived_fields(value, path="observation"):
    if isinstance(value, dict):
        for k, v in value.items():
            need(k not in FORBIDDEN_DERIVED_KEYS, f"derived adapter verdict forbidden: {path}.{k}")
            _reject_derived_fields(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _reject_derived_fields(v, f"{path}[{i}]")


def _require_int(v, label, minimum=0):
    need(isinstance(v, int) and not isinstance(v, bool), f"{label} not integer")
    need(v >= minimum, f"{label} below {minimum}")
    return v


def _state(v, label, allow_none_token=False):
    need(isinstance(v, dict), f"{label} not object")
    token = v.get("operation_token")
    if allow_none_token and token is None:
        pass
    else:
        need(isinstance(token, str) and token, f"{label}.operation_token missing")
    _require_int(v.get("progress_blocks"), f"{label}.progress_blocks")
    _require_int(v.get("destination_event_count"), f"{label}.destination_event_count")
    return v


def _same_state(a, b, label, allow_none_token=False):
    a = _state(a, label + ".before", allow_none_token=allow_none_token)
    b = _state(b, label + ".after", allow_none_token=allow_none_token)
    need(a == b, f"{label} changed operation state")


def _advance(a, b, label):
    a = _state(a, label + ".before")
    b = _state(b, label + ".after")
    need(a["operation_token"] == b["operation_token"], f"{label} operation token changed/restarted")
    need(b["progress_blocks"] > a["progress_blocks"], f"{label} did not advance")
    need(
        b["destination_event_count"] >= a["destination_event_count"],
        f"{label} destination event count regressed",
    )


def _events(v, label):
    need(isinstance(v, list), f"{label} not list")
    for i, e in enumerate(v):
        need(isinstance(e, dict), f"{label}[{i}] not object")
        need(e.get("op") in ("read", "write", "flush"), f"{label}[{i}] bad op")
        if e.get("op") in ("read", "write"):
            _require_int(e.get("lba"), f"{label}[{i}].lba")
            _require_int(e.get("count", 1), f"{label}[{i}].count", 1)
        if "rc" in e:
            _require_int(e.get("rc"), f"{label}[{i}].rc")
    return v


def _touches_superblock(e):
    if e.get("op") not in ("read", "write"):
        return False
    first = e["lba"]
    count = e.get("count", 1)
    return first <= 0 < first + count or first <= LBA_MIRROR < first + count


def _hex_bytes(v, label, *, nonempty=False):
    need(isinstance(v, str), f"{label} not hex")
    try:
        b = bytes.fromhex(v)
    except ValueError as e:
        raise VerificationError(f"{label} malformed hex") from e
    if nonempty:
        need(bool(b), f"{label} empty")
    return b


def _validate_render(probe, label):
    need(isinstance(probe, dict), f"{label} not object")
    need(probe.get("fn") == "tape_render", f"{label} wrong fn")
    need(probe.get("result") == "TAPE_OK", f"{label} render failed")
    rendered = _require_int(probe.get("rendered"), f"{label}.rendered", 1)
    raw = _hex_bytes(probe.get("output_hex"), f"{label}.output_hex", nonempty=True)
    need(any(raw), f"{label} rendered only silence in non-silent fixture")
    need(probe.get("block_events") == [], f"{label} render touched block device")
    return rendered


def _validate_status_group(probe, label):
    need(isinstance(probe, dict), f"{label} not object")
    calls = probe.get("calls")
    need(isinstance(calls, list) and len(calls) == 3, f"{label} call group")
    expected = ("tape_status", "tape_get_info", "tape_tell")
    need(tuple(c.get("fn") for c in calls) == expected, f"{label} wrong call order")
    need(all(c.get("result") == "TAPE_OK" for c in calls), f"{label} read-only call failed")
    need(probe.get("block_events") == [], f"{label} read-only group touched block device")


def _validate_continuation(cont, label):
    need(isinstance(cont, dict), f"{label} not object")
    call = cont.get("call")
    need(isinstance(call, dict), f"{label}.call not object")
    need(call.get("fn") == "tape_dup", f"{label} wrong fn")
    need(call.get("result") == "TAPE_OK", f"{label} continuation failed")
    need(isinstance(call.get("more_work"), bool), f"{label}.more_work not bool")
    _advance(cont.get("before"), cont.get("after"), label)


def _validate_refusal(case, obs):
    expected_result = "TAPE_ERR_DEST_TOO_SMALL" if case["variant"] == "dup_capacity" else "TAPE_ERR_GEOMETRY"
    call = obs.get("call")
    need(isinstance(call, dict), "refusal call missing")
    need(call.get("result") == expected_result, "refusal result mismatch")
    events = _events(obs.get("destination_events"), "destination_events")
    need(not any(e.get("op") == "write" for e in events), "refusal wrote destination")
    need(not any(_touches_superblock(e) for e in events), "refusal touched destination superblock")


def _validate_dup_row(case, obs):
    c = case["column"]
    before = _state(obs.get("before"), "before")
    probe = obs.get("probe")
    after = obs.get("after_probe")

    if c in BUSY_COLUMNS:
        need(isinstance(probe, dict), "BUSY probe missing")
        need(probe.get("result") == "TAPE_ERR_BUSY", f"{c} did not return BUSY")
        need(probe.get("block_events") == [], f"{c} BUSY touched media")
        _same_state(before, after, f"{c} BUSY")
        cont = obs.get("next_continuation")
        _validate_continuation(cont, f"{c} next continuation")
        need(cont["before"] == after, f"{c} continuation did not resume exact state")
        need(cont["after"]["operation_token"] == before["operation_token"], f"{c} restarted operation")
        return

    if c == "dup":
        need(isinstance(probe, dict) and probe.get("fn") == "tape_dup", "dup probe")
        need(probe.get("result") == "TAPE_OK" and probe.get("more_work") is True, "dup continuation")
        _advance(before, after, "matching duplicate continuation")
        need(after["operation_token"] == before["operation_token"], "matching continuation restarted")
        return

    _same_state(before, after, c)
    if c == "render":
        _validate_render(probe, "in-progress render")
    elif c == "service":
        need(isinstance(probe, dict) and probe.get("fn") == "tape_service", "service probe")
        need(probe.get("result") == "TAPE_OK", "service not allowed")
        _events(probe.get("block_events"), "service.block_events")
    elif c == "status_info_tell":
        _validate_status_group(probe, "status/info/tell")
    else:
        raise VerificationError("unknown duplicate row column")


def _validate_zero_budget(case, obs):
    v = case["variant"]
    allow_none = v == "initiate"
    before = _state(obs.get("before"), "zero-budget before", allow_none_token=allow_none)
    after = _state(obs.get("after"), "zero-budget after", allow_none_token=allow_none)
    call = obs.get("call")
    need(isinstance(call, dict), "zero-budget call missing")
    need(call.get("fn") == "tape_dup" and call.get("block_budget") == 0, "zero-budget call shape")
    need(call.get("result") == "TAPE_ERR_INVALID_ARG", "zero-budget result")
    need(call.get("block_events") == [], "zero-budget call touched media")
    need(before == after, "zero-budget call changed operation state")
    if v == "initiate":
        need(before["operation_token"] is None, "zero-budget initiation created operation")
        need(call.get("more_work") is False, "zero-budget initiation more_work")
    else:
        need(isinstance(before["operation_token"], str), "zero-budget continuation lost operation")
        need(call.get("more_work") is True, "zero-budget continuation lost more_work")


def _validate_changed_argument(case, obs):
    which = case["argument"]
    initial = obs.get("initial_args")
    call_args = obs.get("call_args")
    need(isinstance(initial, dict) and isinstance(call_args, dict), "argument snapshots missing")
    for k in FIXED_DUP_ARGS + MUTABLE_DUP_ARGS:
        need(k in initial and k in call_args, f"missing argument {k}")

    before = _state(obs.get("before"), "arg before")
    after = _state(obs.get("after"), "arg after")
    call = obs.get("call")
    need(isinstance(call, dict) and call.get("fn") == "tape_dup", "arg call missing")

    if which == "allowed_mutables":
        need(all(initial[k] == call_args[k] for k in FIXED_DUP_ARGS), "allowed call changed fixed argument")
        need(any(initial[k] != call_args[k] for k in MUTABLE_DUP_ARGS), "allowed call changed no mutable argument")
        need(call.get("result") == "TAPE_OK", "allowed mutable change rejected")
        _advance(before, after, "allowed mutable continuation")
    else:
        need(which in FIXED_DUP_ARGS, "planner named non-fixed argument")
        need(initial[which] != call_args[which], f"{which} did not actually change")
        need(
            all(initial[k] == call_args[k] for k in FIXED_DUP_ARGS if k != which),
            "multiple fixed arguments changed",
        )
        need(call.get("result") == "TAPE_ERR_INVALID_ARG", f"{which} mismatch result")
        need(call.get("block_events") == [], f"{which} mismatch touched media")
        need(before == after, f"{which} mismatch changed operation state")


def _validate_destination_failure(obs):
    before = obs.get("source_before")
    after = obs.get("source_after")
    need(isinstance(before, dict) and isinstance(after, dict), "source before/after missing")
    for key in ("transport_state", "rate_q16_16", "position", "ring"):
        need(key in before and key in after, f"source {key} missing")
    need(before["transport_state"] == "Playing", "destination failure did not start from Playing")
    need(after["transport_state"] == "Playing", "destination failure left Playing")
    _require_int(before["rate_q16_16"], "source_before.rate_q16_16")
    need(before["rate_q16_16"] != 0, "Playing fixture rate is zero")
    need(after["rate_q16_16"] == before["rate_q16_16"], "destination failure changed source rate")
    _require_int(before["position"], "source_before.position")
    need(after["position"] == before["position"], "destination failure changed source position")
    need(after["ring"] == before["ring"], "destination failure changed source ring")
    need(isinstance(before["ring"], dict), "ring descriptor missing")
    _hex_bytes(before["ring"].get("content_sha256"), "ring.content_sha256")
    _require_int(before["ring"].get("valid_frames"), "ring.valid_frames")

    call = obs.get("call")
    need(isinstance(call, dict), "destination failure call missing")
    need(call.get("fn") == "tape_dup" and call.get("result") == "TAPE_ERR_IO", "destination failure result")
    need(call.get("more_work") is False, "destination failure did not terminate duplicate")

    dest_events = _events(obs.get("destination_events"), "destination_events")
    need(
        any(e.get("op") == "write" and e.get("rc", 0) != 0 for e in dest_events),
        "no failing destination write observed",
    )
    source_events = _events(obs.get("source_events"), "source_events")
    need(not any(e.get("op") in ("write", "flush") for e in source_events), "duplicate mutated source media")
    _validate_render(obs.get("render_after_failure"), "render after destination failure")


def _validate_callback_reentry(case, obs):
    c = case["column"]
    before = obs.get("callback_before")
    after = obs.get("callback_after")
    need(isinstance(before, dict) and isinstance(after, dict), "callback state missing")
    _same_state(before.get("operation"), after.get("operation"), "callback nested call")
    for label, row in (("before", before), ("after", after)):
        _require_int(row.get("callback_entry_count"), f"callback_{label}.entry_count", 1)
        _require_int(row.get("callback_max_depth"), f"callback_{label}.max_depth", 1)
    need(after["callback_entry_count"] == before["callback_entry_count"], "nested call re-entered callback")
    need(after["callback_max_depth"] == before["callback_max_depth"] == 1, "nested recursion depth exceeded one")

    nested = obs.get("nested_call")
    if c == "render":
        _validate_render(nested, "callback render")
    elif c == "status_info_tell":
        _validate_status_group(nested, "callback status/info/tell")
    else:
        need(isinstance(nested, dict), "nested call missing")
        need(nested.get("result") == "TAPE_ERR_BUSY", f"callback {c} did not return BUSY")
        need(nested.get("block_events") == [], f"callback {c} BUSY touched media")

    cont = obs.get("next_continuation")
    _validate_continuation(cont, "post-callback continuation")
    need(cont["before"] == after["operation"], "post-callback continuation state mismatch")
    need(
        cont["after"]["operation_token"] == before["operation"]["operation_token"],
        "callback BUSY terminated/restarted operation",
    )


def _validate_faulted_source(obs):
    need(obs.get("source_state") == "FAULTED", "faulted-source fixture not FAULTED")
    call = obs.get("call")
    need(isinstance(call, dict), "faulted-source call missing")
    need(call.get("fn") == "tape_dup", "faulted-source wrong call")
    need(call.get("result") == "TAPE_ERR_FAULTED", "FAULTED source duplicate result")
    need(call.get("block_events") == [], "FAULTED source duplicate touched media")


def _validate_small_budget(obs):
    seq = obs.get("call_sequence")
    need(isinstance(seq, list) and len(seq) >= 2, "small-budget call sequence too short")
    token = None
    saw_nonterminal = False
    prev_progress = None
    prev_events = None
    for i, row in enumerate(seq):
        need(isinstance(row, dict), f"call_sequence[{i}] not object")
        need(row.get("fn") == "tape_dup", "small-budget used another function")
        _require_int(row.get("block_budget"), f"call_sequence[{i}].block_budget", 1)
        need(row.get("result") == "TAPE_OK", "small-budget call failed")
        need(isinstance(row.get("more_work"), bool), "small-budget more_work not bool")
        t = row.get("operation_token")
        need(isinstance(t, str) and t, "small-budget operation token missing")
        if token is None:
            token = t
        need(t == token, "small-budget operation restarted")
        pb = _require_int(row.get("progress_before"), f"call_sequence[{i}].progress_before")
        pa = _require_int(row.get("progress_after"), f"call_sequence[{i}].progress_after")
        eb = _require_int(row.get("destination_event_count_before"), f"call_sequence[{i}].events_before")
        ea = _require_int(row.get("destination_event_count_after"), f"call_sequence[{i}].events_after")
        need(pa > pb, "small-budget continuation did not advance")
        need(ea >= eb, "small-budget event count regressed")
        if prev_progress is not None:
            need(pb == prev_progress, "small-budget progress chain discontinuity")
            need(eb == prev_events, "small-budget event-count chain discontinuity")
        prev_progress, prev_events = pa, ea
        if row["more_work"]:
            saw_nonterminal = True
        if i < len(seq) - 1:
            need(row["more_work"] is True, "small-budget terminated before final call")
    need(saw_nonterminal, "small budget never produced nonterminal continuation")
    need(seq[-1]["more_work"] is False, "small-budget terminal call still has more_work")

    snap = obs.get("terminal_snapshot")
    need(isinstance(snap, dict), "small-budget terminal raw snapshot missing")
    ident = identity_tuple(snap)
    need(
        ident == (FRESH_DUP_UUID.hex(), 1, 1, 2),
        f"small-budget terminal identity mismatch: {ident}",
    )


def _validate_contract(case, obs):
    _reject_derived_fields(obs)
    need(obs.get("family") == case["family"], "contract family")
    fam = case["family"]
    if fam == "equal_divergent_refusal":
        need(obs.get("variant") == case["variant"], "refusal variant")
        _validate_refusal(case, obs)
    elif fam == "dup_in_progress_row":
        need(obs.get("column") == case["column"], "row column")
        _validate_dup_row(case, obs)
    elif fam == "zero_budget":
        need(obs.get("variant") == case["variant"], "zero-budget variant")
        _validate_zero_budget(case, obs)
    elif fam == "changed_argument":
        need(obs.get("argument") == case["argument"], "argument case")
        _validate_changed_argument(case, obs)
    elif fam == "destination_failure_playing":
        _validate_destination_failure(obs)
    elif fam == "callback_reentry":
        need(obs.get("column") == case["column"], "callback column")
        _validate_callback_reentry(case, obs)
    elif fam == "faulted_source":
        need(obs.get("variant") == "dup_call", "faulted-source variant")
        _validate_faulted_source(obs)
    elif fam == "small_budget_completion":
        need(obs.get("variant") == "dup", "small-budget variant")
        _validate_small_budget(obs)
    else:
        raise VerificationError("unknown contract family")


def validate_case(case, obs):
    need(isinstance(obs, dict), "observation not object")
    need(obs.get("format") == "FMTDUP-ID-OBSERVATION-1", "observation format")
    need(obs.get("case_index") == case["case_index"], "case index")
    need(obs.get("scope") == case["scope"], "scope")

    if case["scope"] == "crash":
        exp = expected_crash_observation(case)
        need(obs.get("injection_fired") is True, "planned injection did not fire")
        need(obs.get("pre_snapshot") == exp["pre_snapshot"], "raw pre snapshot mismatch")
        need(obs.get("post_snapshot") == exp["post_snapshot"], "raw durable post snapshot mismatch")
        need(obs.get("target_baseline") == exp["target_baseline"], "target baseline/order/bytes mismatch")

        parsed = inspect_snapshot(obs["post_snapshot"])
        need(obs.get("actual_remount_result") == parsed["mount_result"], "fresh remount disagrees with raw oracle")
        if parsed["mount_result"] == "TAPE_OK":
            need(obs.get("actual_selected_uuid") == parsed.get("selected_uuid"), "selected UUID mismatch")

        ident = identity_tuple(obs["post_snapshot"])
        if ident and ident[0] in (
            "a0a1a2a3a4a5a6a7a8a9aaabacadaeaf",
            "b0b1b2b3b4b5b6b7b8b9babbbcbdbebf",
        ):
            need(ident[1:] == (1, 1, 2), "identity-assignment boundary drift")

        inj = case["injection"]
        s = raw_shapes()[case["shape"]]
        if s.headroom:
            template_durable = False
            if inj["kind"] == "at_flush":
                template_durable = case["mode"] == "write_through" and inj["flush_ordinal"] <= 1
                if inj["flush_ordinal"] > 0:
                    template_durable = True
            elif inj["write_ordinal"] <= 1:
                if inj["kind"] == "after_write" and case["mode"] == "write_through":
                    template_durable = True
                if inj["write_ordinal"] == 1:
                    template_durable = True
            else:
                template_durable = True
            if template_durable and parsed["mount_result"] == "TAPE_OK" and s.previous_uuid is not None:
                need(parsed.get("selected_uuid") != s.previous_uuid.hex(), "previous UUID selected after durable template")
    else:
        _validate_contract(case, obs)
    return True


def failure_reproducer(case, obs, error):
    rep = {"format": "FMTDUP-ID-FAILURE-1", "case": case, "error": str(error)}
    if case["scope"] == "crash":
        rep.update({
            "pre_primary": (obs.get("pre_snapshot") or {}).get("primary_hex"),
            "pre_mirror": (obs.get("pre_snapshot") or {}).get("mirror_hex"),
            "post_primary": (obs.get("post_snapshot") or {}).get("primary_hex"),
            "post_mirror": (obs.get("post_snapshot") or {}).get("mirror_hex"),
            "actual_remount_result": obs.get("actual_remount_result"),
        })
        try:
            rep["raw_oracle_result"] = inspect_snapshot(obs.get("post_snapshot") or {})["mount_result"]
        except Exception as e:
            rep["raw_oracle_result"] = "PARSER_ERROR:" + str(e)
    return rep
