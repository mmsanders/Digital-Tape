#!/usr/bin/env python3
"""Independent oracle for the WP-10 R53 format/duplicate crash rows (DRAFT-9)."""
from __future__ import annotations

import hashlib
import json

import model as M

SCHEMA = "wp10-r53-observation-v1"
MODES = ("flush_required", "write_through")
FORBIDDEN_KEYS = {"verdict", "passed", "permitted", "expected", "outcome_ok", "selected_copy",
                  "phase", "row"}


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def durable_digest(img):
    return sha(b"".join(img[n] for n in sorted(M.TRACKED)))


def trace_events(ops):
    return [{"op": "write", "lba": M.TRACKED[o[1]], "count": 1, "data_sha256": sha(o[2])}
            if o[0] == "w" else {"op": "flush"} for o in ops]


def planned_prefix(scenario, inject):
    ops = M.transaction(scenario)
    out, wk, fk = [], 0, 0
    for o in ops:
        out.append(o)
        if o[0] == "w":
            if inject[0] == "write" and inject[1] == wk:
                return out
            wk += 1
        else:
            if inject[0] == "flush" and inject[1] == fk:
                return out
            fk += 1
    raise AssertionError("injection beyond plan")


def iter_cases():
    idx = 0
    for scenario in M.SCENARIOS:
        for mode, inject in M.injections(scenario):
            yield {"index": idx, "kind": "crash", "scenario": scenario, "mode": mode, "inject": list(inject)}
            idx += 1
    for scenario in M.SCENARIOS:
        yield {"index": idx, "kind": "complete", "scenario": scenario}
        idx += 1
    yield {"index": idx, "kind": "empty_family", "scenario": "DUP-EMPTY-BLANK"}


def plan_census():
    census = {"crash": 0, "complete": 0, "empty_family": 0, "by_scenario": {}, "by_mode": {m: 0 for m in MODES},
              "torn": 0, "before": 0, "after": 0, "flush": 0}
    h = hashlib.sha256()
    for c in iter_cases():
        h.update((canonical(c) + "\n").encode())
        census[c["kind"]] += 1
        if c["kind"] != "crash":
            continue
        census["by_scenario"][c["scenario"]] = census["by_scenario"].get(c["scenario"], 0) + 1
        census["by_mode"][c["mode"]] += 1
        i = c["inject"]
        key = "flush" if i[0] == "flush" else "before" if i[2] == 0 else "after" if i[2] == M.BLOCK else "torn"
        census[key] += 1
    census["caseset_sha256"] = h.hexdigest()
    return census


def _no_verdicts(value, where="observation"):
    if isinstance(value, dict):
        bad = FORBIDDEN_KEYS & set(value)
        need(not bad, f"{where} carries adapter-derived field(s) {sorted(bad)}")
        for k, v in value.items():
            _no_verdicts(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _no_verdicts(v, f"{where}[{i}]")


def _check_mount(obs_mount, img, side, writable, label, findings):
    exp = M.classify(img, side, writable)
    need(isinstance(obs_mount, dict), f"{label} missing")
    result = obs_mount.get("result")
    need(result in exp["result"], f"{label}: {result} not in permitted {list(exp['result'])}")
    if exp.get("pm_finding_crc") and result == "TAPE_ERR_CRC":
        findings["blank_torn_magic_crc"] += 1
    if result != "TAPE_OK":
        need("info" not in obs_mount, f"{label}: info reported for a failed mount")
        need(obs_mount.get("repair_events") == [], f"{label}: a failed mount wrote (only phase 4 writes)")
        return exp
    info = obs_mount.get("info")
    want = {"uuid": exp["uuid"], "free_chunks": exp["free_chunks"],
            "total_frames": exp["total_frames"], "entry_count": exp["entry_count"],
            "side_b_valid": exp["side_b_valid"], "needs_repair": exp["needs_repair"]}
    need(info == want, f"{label}: info {info} != {want}")
    if writable:
        rep = exp["repair"]
        want_ev = [] if rep is None else [{"op": "write", "lba": rep[0], "count": 1, "data_sha256": sha(rep[1])},
                                          {"op": "flush"}]
        need(obs_mount.get("repair_events") == want_ev, f"{label}: phase-4 repair events")
    else:
        need(obs_mount.get("repair_events") == [], f"{label}: read-only mount wrote")
    if side == "A" and writable:
        need(obs_mount.get("pcm_sha256") == M.rendered_sha256(img, exp["layout"]),
             f"{label}: rendered Side A is not the selected generation's audio")
    return exp


def _check_mounts(obs, img, findings):
    _check_mount(obs.get("ro_A"), img, "A", False, "read-only Side-A remount", findings)
    _check_mount(obs.get("rw_A"), img, "A", True, "writable Side-A remount", findings)
    _check_mount(obs.get("rw_B"), img, "B", True, "writable Side-B remount", findings)


def check(case, obs, findings, trust_trace=False):
    _no_verdicts(obs)
    need(obs.get("schema") == SCHEMA and obs.get("index") == case["index"], "schema/case identity")
    need(obs.get("scenario") == case["scenario"] and obs.get("kind") == case["kind"], "scenario identity")
    op, frames, shape, _ = M.SCENARIOS[case["scenario"]]
    if op == "dup":
        need(obs.get("source_sha256_before") == obs.get("source_sha256_after") and
             isinstance(obs.get("source_sha256_before"), str), "duplicate changed its source")
    if case["kind"] == "crash":
        inject = tuple(case["inject"])
        need(obs.get("mode") == case["mode"] and obs.get("inject") == case["inject"], "injection identity")
        need(obs.get("fired") is True, "planned injection did not fire")
        if not trust_trace:
            need(obs.get("trace_sha256") == sha(canonical(trace_events(planned_prefix(case["scenario"], inject))).encode()),
                 "write/flush trace differs from the tapefs Â§9.5/Â§9.6 order")
        images = {durable_digest(i): i for i in M.possible_images(case["scenario"], inject, case["mode"])}
        img = images.get(obs.get("durable_sha256"))
        need(img is not None, "durable media is not a state the durability model permits")
        _check_mounts(obs, img, findings)
        return
    img = M.completed_image(case["scenario"])
    if not trust_trace:
        need(obs.get("trace_sha256") == sha(canonical(trace_events(M.transaction(case["scenario"]))).encode()),
             "complete-run trace")
    need(obs.get("durable_sha256") == durable_digest(img), "completed media bytes")
    need(obs.get("call") == {"fn": "tape_" + op, "result": "TAPE_OK"} | ({"more_work": False} if op == "dup" else {}),
         "operation did not complete")
    if case["kind"] == "complete":
        _check_mounts(obs, img, findings)
        return
    family = obs.get("family")
    want = [{"fn": "tape_promote", "result": "TAPE_ERR_INVALID_ARG", "more_work": False, "block_events": []},
            {"fn": "tape_respool", "result": "TAPE_OK", "more_work": False, "block_events": []},
            {"fn": "tape_arm", "result": "TAPE_OK", "block_events": []},
            {"fn": "tape_commit", "result": "TAPE_OK", "block_events": []}]
    need(family == want, "empty family: promote/respool/zero-frame commit not asserted together")
    need(obs.get("mount_B") == {"fn": "tape_mount", "side": "B", "result": "TAPE_OK"}, "empty copy Side-B mount")


def new_findings():
    return {"blank_torn_magic_crc": 0}


def check_stream(lines, trust_trace=False):
    findings = new_findings()
    cases = iter_cases()
    n = 0
    for line in lines:
        case = next(cases, None)
        need(case is not None, "more observations than planned cases")
        check(case, json.loads(line), findings, trust_trace)
        n += 1
    need(next(cases, None) is None, f"only {n} observations; plan has more cases")
    return n, findings
