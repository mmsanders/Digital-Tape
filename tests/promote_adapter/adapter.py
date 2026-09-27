#!/usr/bin/env python3
"""Product adapter for the imported R29-A promote verifier (tests/promote_draft8).

Mechanical binding only. Setup media come from the verifier's own fixture.py
and oracle seed helpers; where the package names a state but supplies no bytes
(branch-exact counters, entry refusals, the Faulted-row Playing fixture) the
media are built from the verifier's own encoders and documented in README.md.
The C worker drives the real engine and reports raw facts; this file labels
and forwards them. Nothing here decides a verdict.
"""
from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

HERE = Path(__file__).resolve().parent
PKG = HERE.parent / "promote_draft8"
sys.path.insert(0, str(PKG))

from fixture import (  # noqa: E402
    B_LEFT, B_RIGHT, BLOCK, LBA_A0, LBA_A1, LBA_B0, LBA_B1, LBA_CHUNK_BASE,
    CHUNK_BLOCKS, OLD_A_BLOCK, PROMOTED_BLOCK, ZERO_BLOCK, closure_initial,
    index_blocks, mirror_lba, scenario_initial, stage_fixture, superblock,
)
from oracle import RERUN_SEEDS, prefix_media  # noqa: E402
from planner import (  # noqa: E402
    CLOSURE_PHASES, CLOSURE_SEEDS, EXPECTED_CASESET_SHA256, HEADROOM_BRANCHES,
    SCENARIO_PHASES,
)

WORKER = HERE / "build" / "r29a_promote_worker"
ADAPTER_ID = "digital-tape-r29a-promote-product"
MAX_WRITABLE = 0xFFFFFFFD
SLOTS = (LBA_A0, LBA_A1, LBA_B0, LBA_B1)
KIND_LABEL = {"chunk": "audio"}


def need(c: bool, m: str) -> None:
    if not c:
        raise RuntimeError(m)


def plain(media) -> dict:
    return {"total_chunks": media["total_chunks"],
            "blocks": {k: bytes(v) for k, v in media["blocks"].items()}}


# --- product setup media, from the verifier's encoders ---------------------

def _crc(b: bytes) -> int:
    return zlib.crc32(b) & 0xFFFFFFFF


def _structural_slot(blocks, base):
    h = blocks.get(base, ZERO_BLOCK)
    e = blocks.get(base + 1, ZERO_BLOCK)
    if h[:8] != b"TAPEIDX\x01":
        return None
    count = struct.unpack_from("<I", h, 16)[0]
    if count > 42 or struct.unpack_from("<I", h, 60)[0] != _crc(h[:60] + e[:12 * count]):
        return None
    return struct.unpack_from("<I", h, 8)[0]


def with_counters(media, sequence_top=None, generation=None):
    """Rewrite structural slot sequences (order preserved, maximum = top) and
    both structural superblock generations. CRCs recomputed; nothing else
    changes."""
    m = plain(media)
    b = dict(m["blocks"])
    if sequence_top is not None:
        present = [(s, base) for base in SLOTS if (s := _structural_slot(b, base)) is not None]
        present.sort()
        for rank, (_, base) in enumerate(present):
            h = bytearray(b[base])
            e = b.get(base + 1, ZERO_BLOCK)
            count = struct.unpack_from("<I", h, 16)[0]
            struct.pack_into("<I", h, 8, sequence_top - (len(present) - 1 - rank))
            struct.pack_into("<I", h, 60, _crc(bytes(h[:60]) + e[:12 * count]))
            b[base] = bytes(h)
    if generation is not None:
        for lba in (0, mirror_lba(m["total_chunks"])):
            raw = bytearray(b.get(lba, ZERO_BLOCK))
            if raw[:8] == b"TAPEFS\x00\x01" and struct.unpack_from("<I", raw, 508)[0] == _crc(bytes(raw[:508])):
                struct.pack_into("<I", raw, 12, generation)
                struct.pack_into("<I", raw, 508, _crc(bytes(raw[:508])))
                b[lba] = bytes(raw)
    m["blocks"] = b
    return m


def _slot(blocks, base, sequence, side, entries):
    h, e = index_blocks(sequence, side, entries)
    blocks[base] = h
    blocks[base + 1] = e


def entry_refusal_media(variant):
    if variant == "capacity_full":
        total = 4
        sb = superblock(10, 1, 0, 0, total_chunks=total)
        blocks = {0: sb, mirror_lba(total): sb}
        _slot(blocks, LBA_A0, 10, 0, [(0, 0, 128)])
        _slot(blocks, LBA_B0, 500, 1, [(1, 0, 64), (3, 0, 64)])
        blocks[LBA_CHUNK_BASE] = OLD_A_BLOCK
        blocks[LBA_CHUNK_BASE + CHUNK_BLOCKS] = B_LEFT + bytes(BLOCK // 2)
        blocks[LBA_CHUNK_BASE + 3 * CHUNK_BLOCKS] = B_RIGHT + bytes(BLOCK // 2)
        return {"total_chunks": total, "blocks": blocks}
    m = plain(scenario_initial("fresh_alloc_full"))
    b = dict(m["blocks"])
    if variant == "empty_b":
        _slot(b, LBA_B0, 500, 1, [])
        _slot(b, LBA_B1, 499, 1, [])
    elif variant == "degraded_b":
        for base in (LBA_B0, LBA_B1):
            b[base] = ZERO_BLOCK
            b[base + 1] = ZERO_BLOCK
    else:
        raise KeyError(variant)
    m["blocks"] = b
    return m


def playing_fault_media():
    """Faulted-row render fixture: a stage-1 row-1 cartridge whose one live
    run (20,000 frames at chunk 3) is longer than the 16,384-frame play ring,
    so the ring can drain before the timeline ends."""
    total = 8
    sb = superblock(20, 4, 1, 3, total_chunks=total)
    blocks = {0: sb, mirror_lba(total): sb}
    _slot(blocks, LBA_A0, 600, 0, [(3, 0, 20000)])
    _slot(blocks, LBA_B0, 601, 1, [(3, 0, 20000)])
    blocks[LBA_CHUNK_BASE + 3 * CHUNK_BLOCKS] = PROMOTED_BLOCK
    return {"total_chunks": total, "blocks": blocks}


def closure_start_media(phase, seed):
    """Step 9 and the step-5 decline are resumed from the verifier's seed.
    Step 4 is a FRESH-path update with no RESUME entry, so the product reaches
    the seed in flight: scenario_initial with the seed's superblock pair, then
    its own phase-1 copy and steps 2-3 (README.md, binding choice B2)."""
    info = closure_initial(phase, seed)
    if phase != "step4":
        return plain(info["media"])
    base = plain(scenario_initial("fresh_alloc_full"))
    b = dict(base["blocks"])
    total = base["total_chunks"]
    for lba in (0, mirror_lba(total)):
        b[lba] = bytes(info["media"]["blocks"][lba])
    base["blocks"] = b
    return base


HR_BASE = {
    "fresh_alloc_run": ("scenario", "fresh_alloc_full"),
    # No valid-media allocating decline exists (S = free_next >= len for any
    # §5.1-disjoint Side B); the only allocating fixture is used and the
    # engine classifies it by its media. See README.md finding F1.
    "fresh_alloc_decline": ("scenario", "fresh_alloc_full"),
    "fresh_adopt_run": ("scenario", "fresh_adopt_full"),
    "fresh_adopt_decline": ("scenario", "first_use_s0"),
    "resume5_run": ("seed", 5),
    "resume5_decline": ("seed", 9),
    "resume8": ("seed", 7),
    "resume9": ("seed", 8),
}


def seed_media(row):
    scenario, writes = RERUN_SEEDS[row]
    return plain(prefix_media(scenario, writes))


def hr_base(branch):
    kind, key = HR_BASE[branch]
    return plain(scenario_initial(key)) if kind == "scenario" else seed_media(key)


def build_media() -> dict:
    media = {}
    for s in SCENARIO_PHASES:
        media[s] = plain(scenario_initial(s))
    for phase in CLOSURE_PHASES:
        for seed in CLOSURE_SEEDS:
            media[f"closure_{phase}_{seed}"] = closure_start_media(phase, seed)
    for v in ("row1", "row2", "row3", "unmatched", "row1_s0"):
        media[f"stage_{v}"] = plain(stage_fixture(v))
    for row in RERUN_SEEDS:
        media[f"seed_{row}"] = seed_media(row)
    for branch, (sn, gn) in HEADROOM_BRANCHES.items():
        if branch == "nothing":
            continue
        seq, gen = MAX_WRITABLE - sn, MAX_WRITABLE - gn
        media[f"hr_{branch}_exact"] = with_counters(hr_base(branch), seq, gen)
        if sn:
            media[f"hr_{branch}_short_sequence"] = with_counters(hr_base(branch), seq + 1, gen)
        if gn:
            media[f"hr_{branch}_short_sb_generation"] = with_counters(hr_base(branch), seq, gen + 1)
    media["hs_fresh_decline_seq_FFFFFFFB"] = with_counters(hr_base("fresh_alloc_decline"), 0xFFFFFFFB, 10)
    media["hs_fresh_alloc_seq_FFFFFFFC"] = with_counters(hr_base("fresh_alloc_run"), 0xFFFFFFFC, 10)
    media["hs_resume5_decline_seq_FFFFFFFC"] = with_counters(hr_base("resume5_decline"), 0xFFFFFFFC, 10)
    for counter in ("sequence", "sb_generation"):
        for value in ("FFFFFFFE", "FFFFFFFF"):
            v = int(value, 16)
            done = seed_media(11)
            media[f"zr_{counter}_{value}"] = (
                with_counters(done, sequence_top=v) if counter == "sequence"
                else with_counters(done, generation=v)
            )
    for v in ("empty_b", "degraded_b", "capacity_full"):
        media[f"er_{v}"] = entry_refusal_media(v)
    media["play_stage1_long"] = playing_fault_media()
    return media


def contract_media(case) -> list[str]:
    fam = case["family"]
    if fam == "stage_oracle":
        return [f"stage_{case['variant']}"]
    if fam == "rerun_row":
        return [f"seed_{case['row']}"]
    if fam == "rerun_special":
        return ["seed_4"]
    if fam == "stored_position":
        return [{"full_path": "fresh_alloc_full", "step5_decline": "first_use_s0",
                 "resume8": "seed_7", "resume9": "seed_8",
                 "nothing_to_do": "seed_11"}[case["variant"]]]
    if fam == "headroom_exact":
        return [f"hr_{case['branch']}_exact"]
    if fam == "headroom_short":
        return [f"hr_{case['branch']}_short_{case['counter']}"]
    if fam == "headroom_special":
        return [f"hs_{case['variant']}"]
    if fam == "zero_needed_reserved":
        return [f"zr_{case['counter']}_{case['value']}"]
    if fam == "shared_sequence":
        return ["fresh_alloc_full"]
    if fam == "counter_domains":
        return ["fresh_adopt_full"]
    if fam == "entry_refusal":
        return [f"er_{case['variant']}"]
    if fam == "faulted_row":
        return ["fresh_alloc_full", "play_stage1_long"]
    return ["fresh_alloc_full"]


CONTRACT_PARAM = {
    "stage_oracle": "variant", "rerun_row": "row", "rerun_special": "variant",
    "stored_position": "variant", "headroom_exact": "branch",
    "headroom_short": "branch", "headroom_special": "variant",
    "zero_needed_reserved": "counter", "entry_refusal": "variant",
    "promote_in_progress_row": "column", "zero_budget": "variant",
    "faulted_row": "column", "callback_reentry": "column",
}
ECHO = ("variant", "row", "branch", "counter", "value", "column")


class Worker:
    def __init__(self):
        need(WORKER.is_file(), f"worker missing: {WORKER}")
        self.p = subprocess.Popen([str(WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=sys.stderr, text=True, bufsize=1)

    def send(self, line: str) -> None:
        assert self.p.stdin is not None
        self.p.stdin.write(line + "\n")

    def ask(self, line: str) -> dict:
        self.send(line)
        assert self.p.stdin is not None and self.p.stdout is not None
        self.p.stdin.flush()
        out = self.p.stdout.readline()
        if out == "":
            raise RuntimeError("worker stdout closed")
        obj = json.loads(out)
        need(isinstance(obj, dict), "worker response is not an object")
        return obj

    def load(self, name: str, m: dict) -> None:
        blocks = sorted(m["blocks"].items())
        self.send(f"M\t{name}\t{m['total_chunks']}\t{len(blocks)}")
        for lba, data in blocks:
            need(len(data) == BLOCK, f"{name}:{lba} block size")
            self.send(f"{lba}\t{bytes(data).hex()}")


def ordinary_baseline(w: Worker, scenario: str) -> list[dict]:
    raw = w.ask(f"B\t{scenario}")
    phases = SCENARIO_PHASES[scenario]
    out = []
    for x in raw["writes"]:
        i = x["write_ordinal"]
        out.append({
            "ordinal": i,
            "phase": phases[i] if i < len(phases) else f"unlabelled_{i}",
            "kind": KIND_LABEL.get(x["kind"], x["kind"]),
            "lba": x["lba"],
            "count": x["count"],
            "sha256": x["sha256"],
            "flush_ordinal": x["following_flush_ordinal"],
        })
    return out


def closure_baseline(w: Worker, media_name: str, phase: str) -> list[dict]:
    raw = w.ask(f"BZ\t{media_name}")
    for x in raw["writes"]:
        if x["kind"] == "superblock":
            rel = x["following_flush_ordinal"]
            return [{
                "ordinal": 0,
                "phase": phase + "_partner",
                "kind": "superblock",
                "lba": x["lba"],
                "count": x["count"],
                "sha256": x["sha256"],
                "flush_ordinal": rel - x["flushes_before"] if rel >= 0 else -1,
            }]
    return []


def _span(calls, start_kind, end_kind):
    """The logical update from the first call that wrote a `start_kind` block
    through the next call that wrote an `end_kind` block, by raw write kind."""
    def wrote(c, kind):
        return any(e.get("op") == "write" and e.get("kind") == kind for e in c["block_events"])
    for i, c in enumerate(calls):
        if wrote(c, start_kind):
            for d in calls[i + 1:]:
                if wrote(d, end_kind):
                    return {"sequence_before": c["sequence_before"], "sequence_after": d["sequence_after"],
                            "sb_generation_before": c["sb_generation_before"],
                            "sb_generation_after": d["sb_generation_after"]}
    return None


def main() -> int:
    media = build_media()
    w = Worker()
    for name, m in media.items():
        w.load(name, m)

    print(json.dumps({
        "format": "PROMOTE-ADAPTER-2",
        "adapter_kind": "product",
        "adapter_id": ADAPTER_ID,
        "caseset_sha256": EXPECTED_CASESET_SHA256,
        "raw_observation_only": True,
    }, sort_keys=True, separators=(",", ":")), flush=True)

    baselines: dict[str, list[dict]] = {}
    try:
        for line in sys.stdin:
            case = json.loads(line)
            need(isinstance(case, dict), "runner case is not an object")
            if case.get("done") is True:
                w.send("D")
                assert w.p.stdin is not None
                w.p.stdin.close()
                return 0 if w.p.wait(timeout=10) == 0 else 2

            idx = case["case_index"]
            if case["scope"] == "crash":
                inj = case["injection"]
                if case["scenario"] == "closure":
                    mname = f"closure_{case['phase']}_{case['seed']}"
                    if mname not in baselines:
                        baselines[mname] = closure_baseline(w, mname, case["phase"])
                    raw = w.ask("\t".join(["Z", str(idx), mname, case["mode"], inj["kind"],
                                           str(inj.get("landed_bytes", 0))]))
                else:
                    mname = case["scenario"]
                    if mname not in baselines:
                        baselines[mname] = ordinary_baseline(w, mname)
                    ordinal = inj.get("write_ordinal", inj.get("flush_ordinal"))
                    raw = w.ask("\t".join(["C", str(idx), mname, case["mode"], inj["kind"],
                                           str(ordinal), str(inj.get("landed_bytes", 0))]))
                need(raw.get("case_index") == idx, "worker case drift")
                obs = {"format": "PROMOTE-OBSERVATION-2", "scope": "crash",
                       "target_baseline": baselines[mname], **raw}
            else:
                fam = case["family"]
                key = CONTRACT_PARAM.get(fam)
                param = str(case[key]) if key else "-"
                raw = w.ask("\t".join(["K", str(idx), fam, param, *contract_media(case)]))
                need(raw.get("case_index") == idx, "worker case drift")
                obs = {"format": "PROMOTE-OBSERVATION-2", "scope": "contract", "family": fam, **raw}
                if fam == "counter_domains":
                    # Index-only: entry block through header (§8). Superblock-
                    # only: partner through candidate (§4.6). Spans chosen by
                    # the raw write kinds in the trace, not by counter values.
                    obs["index_only"] = _span(raw["calls"], "index_entries", "index_header")
                    obs["superblock_only"] = _span(raw["calls"], "superblock", "superblock")
                for k in ECHO:
                    if k in case:
                        obs[k] = case[k]
            print(json.dumps(obs, sort_keys=True, separators=(",", ":")), flush=True)
    except Exception as exc:  # noqa: BLE001 - report and exit non-zero
        try:
            w.p.kill()
        except OSError:
            pass
        print(f"adapter failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
