#!/usr/bin/env python3
"""Independent oracle for the three #126 strengthening rows (Verification #126, DRAFT-9)."""
from __future__ import annotations

import copy
import functools
import hashlib
import json
import struct
import zlib

import rows as R

SCHEMA = "strengthen-r55-observation-v1"
FORBIDDEN_KEYS = {"verdict", "passed", "permitted", "expected", "outcome_ok", "row_ok", "same_audio",
                  "floor_ok", "pass2_ran", "premise_ok"}
C69 = R.C69
SLOT_LBA = {"A0": C69.LBA_A0, "A1": C69.LBA_A1, "B0": C69.LBA_B0, "B1": C69.LBA_B1}
B_HEADERS = {C69.LBA_B0: "B0", C69.LBA_B1: "B1"}


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _no_verdicts(value, where="observation"):
    if isinstance(value, dict):
        bad = FORBIDDEN_KEYS & set(value)
        need(not bad, f"{where} carries adapter-derived field(s) {sorted(bad)}")
        for k, v in value.items():
            _no_verdicts(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _no_verdicts(v, f"{where}[{i}]")


# ------------------------------------------------------------------ row 1: dup copies every audio block

@functools.lru_cache(maxsize=None)
def dup_expectation(frames, dest):
    timeline = R.dup_expected_timeline(frames)
    return {"source_image": R.sha(R.dup_source_image(frames)), "dest_image": R.sha(R.dup_destination_image(dest)),
            "pcm": R.sha(timeline), "frames": frames}


def check_row1(case, obs):
    exp = dup_expectation(case["frames"], case["destination"])
    need(obs.get("source_image_sha256") == exp["source_image"], "source fixture image")
    need(obs.get("destination_image_sha256_before") == exp["dest_image"], "destination fixture image")
    need(obs.get("call") == {"fn": "tape_dup", "result": "TAPE_OK", "more_work": False}, "dup did not complete")
    need(obs.get("source_pcm_sha256") == exp["pcm"], "source Side A render is not the fixture timeline")
    # tapefs §9.5: the copy lays Side A out as {0, 0, frames}, so destination chunk bytes [0, frames*4) are the
    # source timeline, block for block, whatever the engine's write partitioning (#115).
    need(obs.get("copy_raw_sha256") == exp["pcm"],
         "raw destination frames [0, total_frames) differ from the source timeline (a block was not copied)")
    for side in ("A", "B"):
        m = obs.get("mount_" + side)
        need(isinstance(m, dict) and m.get("result") == "TAPE_OK", f"copy does not mount on Side {side}")
        need(m.get("info") == {"total_frames": exp["frames"], "entry_count": 1}, f"Side {side} info {m.get('info')}")
        need(m.get("pcm_sha256") == exp["pcm"], f"Side {side} of the copy does not render the source's audio")


# ------------------------------------------------------------------ row 2: WP-06f re-spool pass-2 run branch

def _slot_from_bytes(raw):
    if raw[:8] != C69.MAGIC_IDX:
        return None
    seq, side, count, total = struct.unpack_from("<IB3xIQ", raw, 8)
    if count * 12 > len(raw) - C69.BLOCK:
        return None
    entries = [struct.unpack_from("<III", raw, C69.BLOCK + 12 * i) for i in range(count)]
    if C69.crc32(raw[:60] + raw[C69.BLOCK:C69.BLOCK + 12 * count]) != struct.unpack_from("<I", raw, 60)[0]:
        return None
    if total != sum(e[2] for e in entries):
        return None
    return {"sequence": seq, "side": side, "entries": entries}


def _live(slots, side):
    names = ("A0", "A1") if side == "A" else ("B0", "B1")
    valid = [(n, slots[n]) for n in names if slots[n]]
    if not valid or (len(valid) == 2 and valid[0][1]["sequence"] == valid[1][1]["sequence"]):
        return None
    return max(valid, key=lambda v: v[1]["sequence"])


def _live_chunks(slots):
    out = set()
    for side in ("A", "B"):
        got = _live(slots, side)
        if got:
            out |= R.FINAL.chunks_of(got[1]["entries"])
    return out


def check_row2(case, obs):
    """#108 ruling on the WP-06f live-B floor (tapefs §9.3.1-§9.3.2, §9.4; invariant 10), run branch:
    (a) pass-1 allocation, before the first index commit, is one run of len at or above the live-B floor;
    (b) every chunk write is disjoint from both sides' live set, rebuilt from the raw commits seen so far;
    (c) pass 2 RUNS here (a lawful lower run exists after pass 1) and lands at or above a_high_water, strictly
        lower than pass 1, as one run of len, and is committed."""
    image = R.pass2_image()
    need(obs.get("image_sha256_before") == R.sha(image), "fixture image differs from the package's builder")
    need(obs.get("mount") == {"fn": "tape_mount", "side": "A", "result": "TAPE_OK"}, "not a Side-A mount")
    calls = obs.get("calls")
    need(isinstance(calls, list) and calls, "re-spool calls")
    for i, c in enumerate(calls):
        need(c == {"fn": "tape_respool", "block_budget": R.RS_BUDGET, "result": "TAPE_OK",
                   "more_work": i != len(calls) - 1}, f"re-spool call {i}: {c}")
    high, floor, length = R.PASS2_HIGH, R.pass2_floor(), R.pass2_len()
    slots_raw = {n: bytearray(image[lba * C69.BLOCK:(lba + C69.SLOT_BLOCKS) * C69.BLOCK]) for n, lba in SLOT_LBA.items()}
    slots = {n: _slot_from_bytes(bytes(b)) for n, b in slots_raw.items()}
    need(set(range(high, floor)) <= R.FINAL.chunks_of(_live(slots, "B")[1]["entries"]),
         "fixture: live B must densely occupy [a_high_water, floor)")
    events = obs.get("events")
    need(isinstance(events, list), "events")
    commits, passes = [], {0: set(), 1: set(), 2: set()}
    for e in events:
        if e.get("op") != "write":
            continue
        lba, count = e["lba"], e.get("count", 1)
        need(lba not in (0, C69.LBA_MIRROR), "re-spool without stage clearing wrote a superblock")
        if C69.LBA_CHUNK_BASE <= lba < C69.LBA_MIRROR:
            touched = set(range((lba - C69.LBA_CHUNK_BASE) // C69.CHUNK_BLOCKS,
                                (lba + count - 1 - C69.LBA_CHUNK_BASE) // C69.CHUNK_BLOCKS + 1))
            need(not touched & _live_chunks(slots),
                 f"(b) chunk write to {sorted(touched)} intersects the then-live set {sorted(_live_chunks(slots))}")
            need(len(commits) <= 1, "chunk write after the pass-2 commit")
            passes[len(commits)] |= touched
            continue
        name = next((n for n, base in SLOT_LBA.items() if base <= lba < base + C69.SLOT_BLOCKS), None)
        need(name in ("B0", "B1"), f"re-spool wrote LBA {lba} outside Side B's slots and the chunk store")
        data = bytes.fromhex(e.get("data", ""))
        need(len(data) == count * C69.BLOCK, "metadata write without its bytes")
        off = (lba - SLOT_LBA[name]) * C69.BLOCK
        slots_raw[name][off:off + len(data)] = data
        slots[name] = _slot_from_bytes(bytes(slots_raw[name]))
        if lba in B_HEADERS:
            need(slots[name] is not None and slots[name]["side"] == 1, f"{name} header write is not a valid commit")
            commits.append(name)
    need(passes[0] and min(passes[0]) >= floor and passes[0] == set(range(min(passes[0]), min(passes[0]) + length)),
         f"(a) pass-1 allocation {sorted(passes[0])} is not one run of {length} at or above the floor {floor}")
    need(len(commits) == 2 and commits[0] != commits[1],
         f"(c) pass 2 did not run and commit: B commits {commits} (a lawful lower run exists after pass 1)")
    p2 = passes[1]
    need(p2 and min(p2) >= high and min(p2) < min(passes[0]) and p2 == set(range(min(p2), min(p2) + length)),
         f"(c) pass-2 destination {sorted(p2)} is not one run of {length} at or above {high}, below {min(passes[0])}")
    live = _live(slots, "B")[1]["entries"]
    total = sum(e[2] for e in R.PASS2_B)
    need(live == [(min(p2), 0, total)], f"completed re-spool layout {live}")
    m = obs.get("mount_B_after")
    need(isinstance(m, dict) and m.get("result") == "TAPE_OK"
         and m.get("info") == {"total_frames": total, "entry_count": 1}, f"remount after re-spool {m}")
    need(m.get("pcm_sha256") == R.sha(R.FINAL.timeline(R.PASS2_B)), "re-spooled Side B does not render bit-identically")
    return len(commits)


# ------------------------------------------------------------------ row 3: capacity A-slot premise

@functools.lru_cache(maxsize=None)
def capacity_cases():
    return {c.id: c for c in R.CAP.cases()}


def check_row3(case, obs):
    """The #99 oracle's expected commit at sequence 4 rests on cartridge_sequence == 3 (tapefs §5.5: maximum
    over every structurally valid slot, Side A included). Check that premise from raw bytes, then hand the
    unchanged capacity oracle exactly the observation shape it binds."""
    raw = obs.get("raw_before")
    need(isinstance(raw, dict) and set(raw) == {"primary", "mirror", "A0", "A1", "B0", "B1"},
         "raw_before must carry both superblocks and all four slots")
    claimed = obs.get("fixture_sha256")
    need(claimed == hashlib.sha256(canonical(raw).encode()).hexdigest(), "fixture identity over all six blocks")
    a0 = R.CAP.parse_slot(raw["A0"])
    need(a0 is not None and a0["side"] == 0 and a0["sequence"] == 1 and a0["entries"] == [],
         "fixture A0 is not an empty Side-A index at sequence 1")
    need(R.CAP.parse_slot(raw["A1"]) is None, "fixture A1 is structurally valid")
    valid = [s for s in (R.CAP.parse_slot(raw[n]) for n in ("A0", "A1", "B0", "B1")) if s]
    need(max(s["sequence"] for s in valid) == R.CAP.INITIAL_SEQUENCE,
         "cartridge_sequence is not 3, so the expected commit at sequence 4 is not the spec's")
    inner = copy.deepcopy(obs)
    inner["raw_before"] = {k: raw[k] for k in ("primary", "mirror", "B0", "B1")}
    inner["fixture_sha256"] = hashlib.sha256(canonical(inner["raw_before"]).encode()).hexdigest()
    inner["schema"] = "wp09-capacity-r52-v1"
    for k in ("index", "row", "kind", "capacity_case"):
        inner.pop(k, None)
    R.CAP.check(capacity_cases()[case["capacity_case"]], inner)


# ------------------------------------------------------------------ planning

def iter_cases():
    idx = 0
    for frames in R.DUP_FRAMES:
        for dest in R.DUP_DESTS:
            yield {"index": idx, "row": 1, "kind": "dup_audio", "frames": frames, "destination": dest}
            idx += 1
    yield {"index": idx, "row": 2, "kind": "respool_pass2_run", "fixture": "PASS2-RUN-SIDE-A"}
    idx += 1
    for c in R.CAP.cases():
        yield {"index": idx, "row": 3, "kind": "capacity_premise", "capacity_case": c.id}
        idx += 1


@functools.lru_cache(maxsize=None)
def plan_census():
    h = hashlib.sha256()
    census = {"row1": 0, "row2": 0, "row3": 0}
    for c in iter_cases():
        h.update((canonical(c) + "\n").encode())
        census[f"row{c['row']}"] += 1
    census["caseset_sha256"] = h.hexdigest()
    return census


def check(case, obs):
    _no_verdicts(obs)
    need(obs.get("schema") == SCHEMA and obs.get("index") == case["index"] and obs.get("row") == case["row"]
         and obs.get("kind") == case["kind"], "schema/case identity")
    for k in ("frames", "destination", "fixture", "capacity_case"):
        if k in case:
            need(obs.get(k) == case[k], f"case identity: {k}")
    (check_row1, check_row2, check_row3)[case["row"] - 1](case, obs)


def check_stream(lines):
    cases = iter_cases()
    n = 0
    for line in lines:
        case = next(cases, None)
        need(case is not None, "more observations than planned cases")
        check(case, json.loads(line))
        n += 1
    need(next(cases, None) is None, f"only {n} observations; plan has more cases")
    return n
