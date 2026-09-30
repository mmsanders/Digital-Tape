#!/usr/bin/env python3
"""Independent oracle for the WP-12/WP-12a R53 closure gaps (DRAFT-9)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fixtures as F

HERE = Path(__file__).resolve().parent
SCHEMA = "wp12-r53-observation-v1"
COLUMNS = ("seek", "set_rate", "render", "service", "status_info_tell", "arm", "feed",
           "commit", "abort", "set_side", "reset_b", "promote", "respool", "dup", "unmount")
FAULTED_ALLOWED = ("render", "status_info_tell", "abort", "unmount")
FAULTED_F = tuple(c for c in COLUMNS if c not in FAULTED_ALLOWED)
FN = {"seek": ["tape_seek"], "set_rate": ["tape_set_rate"], "render": ["tape_render"],
      "service": ["tape_service"], "status_info_tell": ["tape_status", "tape_get_info", "tape_tell"],
      "arm": ["tape_arm"], "feed": ["tape_feed"], "commit": ["tape_commit"], "abort": ["tape_abort"],
      "set_side": ["tape_set_side"], "reset_b": ["tape_reset_side_b"], "promote": ["tape_promote"],
      "respool": ["tape_respool"], "dup": ["tape_dup"], "unmount": ["tape_unmount"]}
# Verdict-shaped fields an adapter must never emit; the oracle derives them.
FORBIDDEN_KEYS = {"verdict", "passed", "faulted", "is_faulted", "state", "transport_state",
                  "render_identical", "operation_survived", "restarted", "expected"}


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def plan_bytes():
    return (HERE / "gap_plan.json").read_bytes().replace(b"\r\n", b"\n")


def load_plan():
    return json.loads(plan_bytes())


def plan_sha256():
    return hashlib.sha256(F.canonical(load_plan()).encode()).hexdigest()


def _no_verdicts(value, where="observation"):
    if isinstance(value, dict):
        bad = FORBIDDEN_KEYS & set(value)
        need(not bad, f"{where} carries adapter-derived field(s) {sorted(bad)}")
        for k, v in value.items():
            _no_verdicts(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _no_verdicts(v, f"{where}[{i}]")


def _int(value, what, lo=0):
    need(isinstance(value, int) and not isinstance(value, bool) and value >= lo, f"{what} not int>={lo}")
    return value


def _events(events, what):
    need(isinstance(events, list), f"{what} events not a list")
    for e in events:
        need(isinstance(e, dict) and e.get("op") in ("read", "write", "flush"), f"{what} bad event {e!r}")
        _int(e.get("rc"), f"{what} rc")
        if e["op"] != "flush":
            _int(e.get("lba"), f"{what} lba")
            _int(e.get("count"), f"{what} count", 1)
    return events


# ---------------------------------------------------------------- render rows

def _check_render_phase(phase, name, total, expected_sha, per_call, rate):
    need(phase.get("seek") == {"fn": "tape_seek", "frame": 0, "result": "TAPE_OK"}, f"{name} seek")
    need(phase.get("set_rate") == {"fn": "tape_set_rate", "rate_q16_16": rate, "result": "TAPE_OK"},
         f"{name} set_rate")
    renders = phase.get("renders")
    need(isinstance(renders, list) and renders, f"{name} no render calls")
    got = 0
    for i, r in enumerate(renders):
        need(r.get("result") == "TAPE_OK", f"{name} render[{i}] result {r.get('result')}")
        need(r.get("requested") == per_call, f"{name} render[{i}] requested")
        n = _int(r.get("rendered"), f"{name} render[{i}].rendered")
        need(r.get("block_events") == [], f"{name} render[{i}] touched the block device")
        last = i == len(renders) - 1
        need((n < per_call) if last else (n == per_call), f"{name} render[{i}] short/long")
        got += n
    need(got == total, f"{name} rendered {got} frames, timeline has {total}")
    need(phase.get("pcm_bytes") == total * F.FRAME_BYTES, f"{name} PCM length")
    need(phase.get("pcm_sha256") == expected_sha, f"{name} PCM differs from the logical timeline")
    need(phase.get("tell") == total, f"{name} tell after render")
    need(phase.get("at_end") is True, f"{name} at_end not reached")
    need(phase.get("stop") == {"fn": "tape_set_rate", "rate_q16_16": 0, "result": "TAPE_OK"},
         f"{name} did not stop before the next step")


def check_render(case, obs, plan):
    rp = plan["render"]
    high, entries = F.RENDER_FIXTURES[case["fixture"]]
    total = sum(e[2] for e in entries)
    expected = F.logical_pcm(entries)
    need(len(expected) == total * F.FRAME_BYTES, "oracle timeline length")
    expected_sha = hashlib.sha256(expected).hexdigest()
    need(obs.get("mount") == {"fn": "tape_mount", "side": "B", "result": "TAPE_OK"}, "initial mount")
    for name in ("pre", "post_same_session", "post_remount"):
        phase = obs.get(name)
        need(isinstance(phase, dict), f"{name} phase missing")
        _check_render_phase(phase, name, total, expected_sha, rp["render_frames_per_call"],
                            rp["rate_q16_16"])
    calls = obs.get("respool")
    need(isinstance(calls, list) and calls, "respool loop missing")
    for i, c in enumerate(calls):
        need(c.get("fn") == "tape_respool" and c.get("block_budget") == rp["respool_block_budget"],
             f"respool[{i}] call shape")
        need(c.get("result") == "TAPE_OK", f"respool[{i}] result {c.get('result')}")
        need(c.get("more_work") is (i != len(calls) - 1), f"respool[{i}] more_work")
    need(obs.get("unmount") == {"fn": "tape_unmount", "result": "TAPE_OK"}, "unmount before remount")
    need(obs.get("remount") == {"fn": "tape_mount", "side": "B", "result": "TAPE_OK"}, "remount")
    slots = obs.get("post_b_slots")
    need(isinstance(slots, dict) and set(slots) == {"B0", "B1"}, "post Side-B slots")
    raw = {k: bytes.fromhex(v) for k, v in slots.items()}
    need(all(len(v) == F.RS.SLOT_BYTES for v in raw.values()), "post slot size")
    pre = F.render_media(case["fixture"])
    post = F.RS.Media(pre.blocks, pre.primary, pre.mirror,
                      (pre.slots[0], pre.slots[1], raw["B0"], raw["B1"]))
    live = F.RS.live_slot(post, 1)
    need(live is not None, "no selectable Side B after re-spool")
    post_entries = F.RS.parse_entries(post.slots[live])
    need(len(post_entries) == 1, f"completed pass left {len(post_entries)} entries")
    need(post_entries[0][1] == 0 and post_entries[0][2] == total, "single entry does not span the timeline")
    return True


# ----------------------------------------------------------------- fault rows

def _injected_index(case, calls):
    rule = case["inject"]
    flat = [(ci, ei, e) for ci, c in enumerate(calls) for ei, e in enumerate(c["events"])]
    if rule["rule"] == "first_on_continuation":
        # engine-api §9/§6 budget blocks of work, reads included, so no call index is fixed:
        # the fault goes on the first own-device write/flush of any continuation (call >= 1).
        want = [(ci, ei) for ci, ei, e in flat if ci >= 1 and e["op"] == rule["op"]]
        need(want, "no own-device " + rule["op"] + " was reached on a continuation call")
        return want[0]
    if rule["rule"] == "first_after_write":
        seen = None
        for ci, ei, e in flat:
            if seen is None and e["op"] == "write" and e["lba"] == rule["lba"] and e["count"] == rule["count"]:
                seen = (ci, ei)
            elif seen is not None and e["op"] == rule["op"]:
                need(ci >= 1, "pass-1 header flush fell on the initiating call, not a continuation")
                return ci, ei
        need(False, "pass-1 header write/flush never reached")
    raise AssertionError("unknown injection rule")


def check_fault(case, obs, plan):
    op = case["op"]
    need(obs.get("mount") == {"fn": "tape_mount", "side": case["mount_side"], "result": "TAPE_OK"},
         "fault fixture mount")
    calls = obs.get("calls")
    need(isinstance(calls, list) and len(calls) >= 2, "long operation never reached a continuation")
    for i, c in enumerate(calls):
        need(c.get("fn") == "tape_" + op and c.get("block_budget") == case["block_budget"],
             f"{op}[{i}] call shape")
        _events(c.get("events"), f"{op}[{i}]")
    ci, ei = _injected_index(case, calls)
    need(ci >= 1, "failure was not on a continuation call")
    need(obs.get("fault_call_index") == ci, "fault_call_index does not name the failing continuation")
    need(ci == len(calls) - 1, "calls continued after the failing continuation")
    for i, c in enumerate(calls[:ci]):
        need(c.get("result") == "TAPE_OK" and c.get("more_work") is True, f"{op}[{i}] before failure")
    failed = calls[ci]
    for i, c in enumerate(calls):
        for j, e in enumerate(c["events"]):
            need((e["rc"] != 0) == ((i, j) == (ci, ei)), f"unplanned device failure at {op}[{i}] event {j}")
    need(failed["events"][ei]["op"] == case["inject"]["op"], "failure on wrong callback kind")
    need(failed.get("result") == "TAPE_ERR_IO", f"failing continuation returned {failed.get('result')}")
    need(failed.get("more_work") is False, "failing continuation left more_work set")

    order = plan["fault_probe_order"]
    probe = obs.get("probe")
    need(isinstance(probe, list) and [p.get("column") for p in probe] == order,
         "Faulted row not probed in plan order on the faulted instance")
    need(sorted(order) == sorted(COLUMNS) and len(FAULTED_F) == 11, "15-column census")
    for p in probe:
        col = p["column"]
        fns = [c.get("fn") for c in p.get("calls", [])]
        need(fns == FN[col], f"{col} probe calls {fns}")
        need(p.get("block_events") == [], f"{col} touched the faulted instance's device")
        if col == "dup":
            need(p.get("dst_block_events") == [], "dup touched the destination while FAULTED")
        want = "TAPE_ERR_FAULTED" if col in FAULTED_F else "TAPE_OK"
        for c in p["calls"]:
            need(c.get("result") == want, f"{col}: {c.get('fn')} returned {c.get('result')}, want {want}")
    at_fault = obs.get("device_sha256_at_fault")
    need(isinstance(at_fault, str) and len(at_fault) == 64, "device hash at fault")
    need(obs.get("device_sha256_before_unmount") == at_fault,
         "durable media changed while quarantined")
    return True


def check(case, obs, plan=None):
    plan = plan or load_plan()
    _no_verdicts(obs)
    need(obs.get("schema") == SCHEMA, "schema")
    need(obs.get("case") == case["id"], "case identity")
    need(obs.get("fixture_metadata_sha256") == F.fixture_metadata_sha256(case["fixture"]),
         "fixture metadata identity")
    if case["kind"] == "render":
        return check_render(case, obs, plan)
    return check_fault(case, obs, plan)


def check_all(observations):
    plan = load_plan()
    cases = plan["cases"]
    need(len(observations) == len(cases), "case census")
    need([o.get("case") for o in observations] == [c["id"] for c in cases], "case order")
    for case, obs in zip(cases, observations):
        check(case, obs, plan)
    return len(cases)
