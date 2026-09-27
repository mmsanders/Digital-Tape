#!/usr/bin/env python3
"""B6 raw-setup audit for the crafted-counter R29-A cases. Software-owned.

For every case in the four crafted-counter families (headroom_exact,
headroom_short, headroom_special, zero_needed_reserved) this collects the
product adapter's observation and retains its raw setup evidence: the image the
worker put on the device before mount, and the verifier-owned base it was
derived from. It then checks, from bytes alone, that:

- the base image equals the verifier fixture/seed recomputed here from
  tests/promote_draft8 (the adapter cannot forge its own base);
- every byte that differs lies in an index header's sequence (8..11) or CRC
  (60..63), or a superblock's sb_generation (12..15) or CRC (508..511);
- every structural slot and superblock stays structural (CRC valid), the set
  of structural slots is unchanged, and their relative sequence order is
  preserved exactly;
- the declared rewrite and the engine-reported counter_values match the image.

Red controls then mutate retained evidence and must each be rejected. This
decides nothing about promote behaviour; the verifier's oracle does that.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests" / "promote_draft8"))

from fixture import BLOCK, mirror_lba, scenario_initial  # noqa: E402
from oracle import RERUN_SEEDS, prefix_media  # noqa: E402
from planner import EXPECTED_CASESET_SHA256, iter_cases  # noqa: E402

FAMILIES = ("headroom_exact", "headroom_short", "headroom_special", "zero_needed_reserved")
SLOTS = (8, 136, 264, 392)
HEADER_FIELDS = (range(8, 12), range(60, 64))
SB_FIELDS = (range(12, 16), range(508, 512))


class AuditError(RuntimeError):
    pass


def need(c, m):
    if not c:
        raise AuditError(m)


def crc(b: bytes) -> int:
    return zlib.crc32(b) & 0xFFFFFFFF


def verifier_base(source) -> tuple[int, dict]:
    kind, key = source["kind"], source["key"]
    if kind == "scenario":
        m = scenario_initial(key)
    elif kind == "seed":
        m = prefix_media(*RERUN_SEEDS[key])
    else:
        raise AuditError(f"unknown base kind {kind}")
    image = {str(lba): bytes(d).hex() for lba, d in sorted(m["blocks"].items()) if any(d)}
    return m["total_chunks"], image


def block(image: dict, lba: int) -> bytes:
    h = image.get(str(lba))
    return bytes.fromhex(h) if h is not None else bytes(BLOCK)


def slot_seq(image, base):
    h, e = block(image, base), block(image, base + 1)
    if h[:8] != b"TAPEIDX\x01":
        return None
    count = struct.unpack_from("<I", h, 16)[0]
    if count > 42 or struct.unpack_from("<I", h, 60)[0] != crc(h[:60] + e[:12 * count]):
        return None
    return struct.unpack_from("<I", h, 8)[0]


def sb_gen(image, lba):
    b = block(image, lba)
    if b[:8] != b"TAPEFS\x00\x01" or struct.unpack_from("<I", b, 508)[0] != crc(b[:508]):
        return None
    return struct.unpack_from("<I", b, 12)[0]


def audit(obs: dict) -> dict:
    ev = obs.get("setup_evidence")
    need(isinstance(ev, dict) and ev.get("format") == "PROMOTE-B6-SETUP-1", "setup evidence missing")
    base, setup = ev.get("base_image"), ev.get("setup_image")
    need(isinstance(base, dict) and isinstance(setup, dict), "setup images missing")
    total, expected_base = verifier_base(ev["base_source"])
    need(base == expected_base, "base image is not the verifier fixture")
    mirror = mirror_lba(total)

    changed = []
    for key in sorted(set(base) | set(setup), key=int):
        lba = int(key)
        a, b = block(base, lba), block(setup, lba)
        for off in range(BLOCK):
            if a[off] == b[off]:
                continue
            if lba in SLOTS:
                ok = any(off in r for r in HEADER_FIELDS)
            elif lba in (0, mirror):
                ok = any(off in r for r in SB_FIELDS)
            else:
                ok = False
            need(ok, f"unauthorized setup-byte drift at lba {lba} offset {off}")
            changed.append((lba, off))

    before = {s: slot_seq(base, s) for s in SLOTS}
    after = {s: slot_seq(setup, s) for s in SLOTS}
    need({s for s, v in before.items() if v is not None} == {s for s, v in after.items() if v is not None},
         "structural slot set changed")
    live = [s for s, v in before.items() if v is not None]
    need(sorted(live, key=lambda s: before[s]) == sorted(live, key=lambda s: after[s]),
         "relative sequence order not preserved")
    need(len({after[s] for s in live}) == len(live), "setup sequences not distinct")
    for lba in (0, mirror):
        need((sb_gen(base, lba) is None) == (sb_gen(setup, lba) is None), "superblock structural state changed")

    rw = ev.get("declared_rewrite", {})
    top = max(after[s] for s in live)
    if rw.get("sequence_top") is not None:
        need(top == rw["sequence_top"], "sequence rewrite differs from declaration")
    else:
        need(before == after, "sequence changed without declaration")
    gens = {sb_gen(setup, lba) for lba in (0, mirror)} - {None}
    if rw.get("sb_generation") is not None:
        need(gens == {rw["sb_generation"]}, "generation rewrite differs from declaration")
    else:
        need(gens == {sb_gen(base, lba) for lba in (0, mirror)} - {None}, "generation changed without declaration")

    cv = obs.get("counter_values")
    need(cv == {"sequence": top, "sb_generation": max(gens)}, "engine counters disagree with setup image")
    return {"media": ev["media"], "changed_bytes": len(changed),
            "changed_lbas": sorted({lba for lba, _ in changed}),
            "sequences_before": {str(s): before[s] for s in live},
            "sequences_after": {str(s): after[s] for s in live},
            "counter_values": cv}


def _set_image_byte(obs, lba, off, value):
    ev = obs["setup_evidence"]
    b = bytearray(block(ev["setup_image"], lba))
    b[off] = value
    ev["setup_image"][str(lba)] = bytes(b).hex()


def _fix_header_crc(obs, base):
    ev = obs["setup_evidence"]
    h = bytearray(block(ev["setup_image"], base))
    e = block(ev["setup_image"], base + 1)
    count = struct.unpack_from("<I", h, 16)[0]
    struct.pack_into("<I", h, 60, crc(bytes(h[:60]) + e[:12 * count]))
    ev["setup_image"][str(base)] = bytes(h).hex()


def red_controls(sample: dict) -> list[dict]:
    """Each mutation must be rejected; returns one record per control."""
    live = [s for s in SLOTS if slot_seq(sample["setup_evidence"]["setup_image"], s) is not None]
    a, b = live[0], live[1]

    def entries_drift(o):
        _set_image_byte(o, a + 1, 0, block(o["setup_evidence"]["setup_image"], a + 1)[0] ^ 1)

    def audio_drift(o):
        img = o["setup_evidence"]["setup_image"]
        chunk = min(int(k) for k in img if int(k) >= 2048)
        _set_image_byte(o, chunk, 5, block(img, chunk)[5] ^ 0x80)

    def order_swap(o):
        img = o["setup_evidence"]["setup_image"]
        sa, sb = slot_seq(img, a), slot_seq(img, b)
        for slot, seq in ((a, sb), (b, sa)):
            h = bytearray(block(img, slot))
            struct.pack_into("<I", h, 8, seq)
            img[str(slot)] = bytes(h).hex()
            _fix_header_crc(o, slot)

    def unauthorized_header_field(o):
        img = o["setup_evidence"]["setup_image"]
        h = bytearray(block(img, a))
        h[12] ^= 1          # side marker, not a sequence/CRC byte
        img[str(a)] = bytes(h).hex()
        _fix_header_crc(o, a)

    def forged_base(o):
        o["setup_evidence"]["base_image"] = dict(o["setup_evidence"]["setup_image"])

    def undeclared_rewrite(o):
        rw = o["setup_evidence"]["declared_rewrite"]
        if rw.get("sequence_top") is not None:
            rw["sequence_top"] -= 1
        else:
            rw["sb_generation"] -= 1

    out = []
    for name, mutate in (("entry_block_drift", entries_drift), ("audio_byte_drift", audio_drift),
                         ("relative_order_swap", order_swap),
                         ("unauthorized_header_field", unauthorized_header_field),
                         ("forged_base_image", forged_base), ("undeclared_rewrite", undeclared_rewrite)):
        o = copy.deepcopy(sample)
        mutate(o)
        try:
            audit(o)
            out.append({"control": name, "rejected": False, "error": None})
        except AuditError as e:
            out.append({"control": name, "rejected": True, "error": str(e)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    out = a.out if a.out.is_absolute() else ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)

    p = subprocess.Popen([sys.executable, str(HERE / "adapter.py")], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True, bufsize=1)
    assert p.stdin is not None and p.stdout is not None
    hello = json.loads(p.stdout.readline())
    need(hello.get("caseset_sha256") == EXPECTED_CASESET_SHA256, "adapter digest mismatch")
    observations = []
    for case in iter_cases():
        if case.get("family") not in FAMILIES:
            continue
        p.stdin.write(json.dumps(case, sort_keys=True, separators=(",", ":")) + "\n")
        p.stdin.flush()
        line = p.stdout.readline()
        need(line != "", f"adapter exited at case {case['case_index']}")
        observations.append((case, json.loads(line)))
    p.stdin.write('{"done":true}\n')
    p.stdin.flush()
    p.wait(timeout=30)

    raw = "".join(json.dumps(o, sort_keys=True, separators=(",", ":")) + "\n" for _, o in observations).encode()
    (out / "b6-setup-evidence.jsonl").write_bytes(raw)

    results, failures = [], []
    for case, obs in observations:
        try:
            results.append({"case_index": case["case_index"], "family": case["family"], **audit(obs)})
        except AuditError as e:
            failures.append({"case_index": case["case_index"], "family": case["family"], "error": str(e)})
    controls = red_controls(observations[0][1]) if observations else []

    report = {
        "format": "PROMOTE-B6-AUDIT-1",
        "caseset_sha256": EXPECTED_CASESET_SHA256,
        "families": list(FAMILIES),
        "cases": len(observations),
        "passed": len(results),
        "failures": failures,
        "results": results,
        "red_controls": controls,
        "evidence_sha256": hashlib.sha256(raw).hexdigest(),
    }
    data = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    (out / "b6-audit.json").write_bytes(data)
    (out / "b6-audit.sha256").write_text(hashlib.sha256(data).hexdigest() + "\n")
    ok = not failures and controls and all(c["rejected"] for c in controls)
    print(f"B6 setup audit: {len(results)}/{len(observations)} crafted-counter cases pass; "
          f"red controls rejected {sum(c['rejected'] for c in controls)}/{len(controls)}")
    for f in failures:
        print(f"  FAIL case {f['case_index']} {f['family']}: {f['error']}")
    for c in controls:
        print(f"  control {c['control']}: {'REJECTED' if c['rejected'] else 'NOT REJECTED'} {c['error'] or ''}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
