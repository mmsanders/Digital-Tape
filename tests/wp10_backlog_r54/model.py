#!/usr/bin/env python3
"""Verifier-owned model for WP-10 backlog rows (Verification #116, DRAFT-9).

Mount classification follows tapefs §4.1/§4.2/§5.2/§5.3. The duplicate transaction
is derived from the destination's raw bytes exactly as tapefs §9.5 item 5 and the
write order classify it, so a re-run starting from any crash state is planned by
the same rule. Superblock and WIP-template bytes come from the accepted R29-B
builders (pinned in deps.py).
"""
from __future__ import annotations

import hashlib
import itertools
import struct
import zlib

import deps

B = deps.R29B.fixture
BLOCK = B.BLOCK
CF = B.CHUNK_FRAMES
MIRROR = B.LBA_MIRROR
TOTAL_CHUNKS = B.TOTAL_CHUNKS
ZERO = bytes(BLOCK)
SLOTS = {"A0": B.LBA_A0, "A1": B.LBA_A1, "B0": B.LBA_B0, "B1": B.LBA_B1}
TRACKED = {"P": 0, "M": MIRROR, "C0": B.LBA_CHUNK_BASE}
for _name, _base in SLOTS.items():
    TRACKED[_name + "h"] = _base
    TRACKED[_name + "e"] = _base + 1
OLD_UUID = B.OLD_UUID_A
OLD_AUDIO = bytes(((i * 11 + 200) & 0xFF) for i in range(BLOCK))
SOURCE_AUDIO = bytes(((i * 37 + 5) & 0xFF) for i in range(BLOCK))   # 128 source frames, one block
LABEL_OFFSET, LABEL_BYTES = 88, 32                                  # tapefs §4


def crc32(b):
    return zlib.crc32(b) & 0xFFFFFFFF


def sha(b):
    return hashlib.sha256(b).hexdigest()


def gen(sb):
    return struct.unpack_from("<I", sb, 12)[0]


def sb_valid(x):
    return x[:8] == B.MAGIC_SB and crc32(x[:508]) == struct.unpack_from("<I", x, 508)[0]


def with_label(sb, label: bytes):
    b = bytearray(sb)
    b[LABEL_OFFSET:LABEL_OFFSET + LABEL_BYTES] = label.ljust(LABEL_BYTES, b"\0")
    struct.pack_into("<I", b, 508, crc32(bytes(b[:508])))
    return bytes(b)


def index_blocks(side, sequence, entries):
    raw = b"".join(struct.pack("<III", *e) for e in entries)
    h = bytearray(BLOCK)
    h[:8] = B.MAGIC_IDX
    struct.pack_into("<I", h, 8, sequence)
    h[12] = side
    struct.pack_into("<I", h, 16, len(entries))
    struct.pack_into("<Q", h, 20, sum(e[2] for e in entries))
    struct.pack_into("<I", h, 60, crc32(bytes(h[:60]) + raw))
    return bytes(h), raw.ljust(BLOCK, b"\0")


# ------------------------------------------------------------ fixtures

OLD_SB = B.superblock(generation=7, uuid=OLD_UUID, high=1)
STALE_SB = B.superblock(generation=6, uuid=OLD_UUID, high=1)


def cartridge(primary, mirror):
    img = {name: ZERO for name in TRACKED}
    img["P"], img["M"], img["C0"] = primary, mirror, OLD_AUDIO
    img["A0h"], img["A0e"] = index_blocks(0, 100, [(0, 0, 128)])
    img["B0h"], img["B0e"] = index_blocks(1, 101, [(0, 0, 128)])
    return img


# Row 1: phase-4 repair shapes (tapefs §4.1: invalid partner, or valid at strictly lower generation).
REPAIR_SHAPES = {
    "REPAIR-PRIMARY-ONLY": (OLD_SB, ZERO),
    "REPAIR-MIRROR-ONLY": (ZERO, OLD_SB),
    "REPAIR-MIRROR-STALE": (OLD_SB, STALE_SB),
    "REPAIR-PRIMARY-STALE": (STALE_SB, OLD_SB),
}

# Row 2: destination shapes spanning every class of the tapefs §9.5 crash table.
RERUN_SHAPES = ("blank", "healthy_pair", "equal_divergent", "exhaustion_candidate", "exhaustion_equal_divergent")


def rerun_destination(shape):
    if shape == "blank":
        return {name: ZERO for name in TRACKED}
    s = B.raw_shapes()[shape]
    return cartridge(s.primary, s.mirror)


# ------------------------------------------------------------ transactions

def is_residue(img):
    """DRAFT-10 tapefs §9.5 item 5 (V10-001): no structurally valid copy, but not both blocks all zero."""
    return not (sb_valid(img["P"]) or sb_valid(img["M"])) and (any(img["P"]) or any(img["M"]))


def step1_ops(img):
    """tapefs §9.5 / §9.6 step 1 for a destination whose raw state is img (item 5 classification, DRAFT-10)."""
    p, m = img["P"], img["M"]
    vp, vm = sb_valid(p), sb_valid(m)
    ops = []
    if is_residue(img):                                         # V10-001: mirror, flush, primary, flush
        return [("w", "M", ZERO), ("f",), ("w", "P", ZERO), ("f",)]
    if vp or vm:
        gp, gm = (gen(p) if vp else -1), (gen(m) if vm else -1)
        top = max(gp, gm)
        if vp and vm and gp == gm:
            partner, cand = "M", ("P" if p == m else None)      # healthy tie or equal-divergent
        elif gp > gm:
            partner, cand = "M", "P"
        else:
            partner, cand = "P", "M"
        if top >= 0xFFFFFFFD:                                   # §4.5 generation-exhausted fallback
            first = partner
            ops += [("w", first, ZERO), ("f",), ("w", "P" if first == "M" else "M", ZERO), ("f",)]
        else:
            tmpl = B.wip_template(img[cand] if cand else None, existing_generation=top)
            ops += [("w", partner, tmpl), ("f",), ("w", "P" if partner == "M" else "M", tmpl), ("f",)]
    return ops                                                  # all-zero blank: no step-1 write


def dup_ops(img, frames=128, label=b"", audio=SOURCE_AUDIO):
    """tapefs §9.5 write order for a destination whose raw state is img (item 5 classification, DRAFT-10)."""
    ops = step1_ops(img)
    ops += [("w", n, ZERO) for n in ("A0h", "A1h", "B0h", "B1h")] + [("f",)]
    if frames:
        a_h, a_e = index_blocks(0, 1, [(0, 0, frames)])
        b_h, b_e = index_blocks(1, 2, [(0, 0, frames)])
        ops += [("w", "C0", audio), ("f",), ("w", "A0e", a_e), ("f",), ("w", "A0h", a_h), ("f",),
                ("w", "B0e", b_e), ("f",), ("w", "B0h", b_h), ("f",)]
    else:
        a_h, _ = index_blocks(0, 1, [])
        b_h, _ = index_blocks(1, 2, [])
        ops += [("w", "A0h", a_h), ("w", "B0h", b_h), ("f",)]
    final = with_label(B.superblock(generation=1, state=0, uuid=B.FRESH_DUP_UUID, high=-(-frames // CF)), label)
    return ops + [("w", "M", final), ("f",), ("w", "P", final), ("f",)]


def apply(img, ops):
    out = dict(img)
    for o in ops:
        if o[0] == "w":
            out[o[1]] = o[2]
    return out


def repair_ops(img):
    c = classify(img, "A", True)
    if not c.get("repair"):
        return []
    lba, cand = c["repair"]
    return [("w", "M" if lba == MIRROR else "P", cand), ("f",)]


# ------------------------------------------------------------ crash model (tapefs §8.1)

def injections(ops):
    nw = sum(o[0] == "w" for o in ops)
    nf = sum(o[0] == "f" for o in ops)
    for mode in ("flush_required", "write_through"):
        for k in range(nw):
            for landed in range(BLOCK + 1):
                yield mode, ("write", k, landed)
        for j in range(nf):
            yield mode, ("flush", j)


def prefix(ops, inject):
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
    raise AssertionError("injection beyond transaction")


def possible_images(base, ops, inject, mode):
    """Durable images a conforming device may hold: torn prefixes durable in both modes; a completed
    write is durable at once in write-through, and possibly-or-not until its flush in flush-required."""
    durable, pending = dict(base), []
    for o in prefix(ops, inject)[:-1]:
        if o[0] == "w":
            if mode == "write_through":
                durable[o[1]] = o[2]
            else:
                pending.append((o[1], o[2]))
        else:
            for name, data in pending:
                durable[name] = data
            pending = []
    last = prefix(ops, inject)[-1]
    torn = None
    if inject[0] == "write":
        landed = inject[2]
        if landed == BLOCK:
            if mode == "write_through":
                durable[last[1]] = last[2]
            else:
                pending.append((last[1], last[2]))
        elif landed:
            torn = (last[1], last[2][:landed] + durable[last[1]][landed:])
    out = []
    for keep in itertools.product((False, True), repeat=len(pending)):
        img = dict(durable)
        for (name, data), k in zip(pending, keep):
            if k:
                img[name] = data
        if torn:
            img[torn[0]] = torn[1]
        out.append(img)
    return out


def digest(img):
    return sha(b"".join(img[n] for n in sorted(TRACKED)))


# ------------------------------------------------------------ mount classifier

def _slot(img, name, side, high):
    h, e = img[name + "h"], img[name + "e"]
    if h[:8] != B.MAGIC_IDX:
        return None
    seq, sd = struct.unpack_from("<I", h, 8)[0], h[12]
    count, total = struct.unpack_from("<I", h, 16)[0], struct.unpack_from("<Q", h, 20)[0]
    if count * 12 > BLOCK:
        return None
    entries = [struct.unpack_from("<III", e, 12 * i) for i in range(count)]
    raw = b"".join(struct.pack("<III", *x) for x in entries)
    if crc32(h[:60] + raw) != struct.unpack_from("<I", h, 60)[0] or sd != side:
        return None
    if total != sum(x[2] for x in entries):
        return None
    spans = []
    for first, start, n in entries:
        last = first + (start + n - 1) // CF if n else first
        if n < 1 or start >= CF or last >= TOTAL_CHUNKS or (side == 0 and last >= high):
            return None
        spans.append((first * CF + start, first * CF + start + n))
    spans.sort()
    if any(spans[i][1] > spans[i + 1][0] for i in range(len(spans) - 1)):
        return None
    return seq, tuple(entries)


def _side(img, side, high):
    names = ("A0", "A1") if side == 0 else ("B0", "B1")
    found = [s for s in (_slot(img, n, side, high) for n in names) if s]
    if not found:
        return "TAPE_ERR_NO_VALID_INDEX", None
    if len(found) == 2 and found[0][0] == found[1][0]:
        return "TAPE_ERR_INCONSISTENT", None
    return "TAPE_OK", max(found)[1]


def classify(img, requested_side, writable):
    p, m = img["P"], img["M"]
    vp, vm = sb_valid(p), sb_valid(m)
    if not vp and not vm:
        magic = p[:8] == B.MAGIC_SB or m[:8] == B.MAGIC_SB
        # PM ruling (#109): both conform where a torn copy keeps the magic.
        return {"result": ("TAPE_ERR_BAD_MAGIC", "TAPE_ERR_CRC") if magic else ("TAPE_ERR_BAD_MAGIC",)}
    gp = gen(p) if vp else -1
    gm = gen(m) if vm else -1
    if vp and vm and gp == gm and p != m:
        return {"result": ("TAPE_ERR_INCONSISTENT",)}
    cand, partner_lba = (p, MIRROR) if gp >= gm else (m, 0)
    stale = not (vp and vm) or gp != gm
    if struct.unpack_from("<H", cand, 8)[0] != 1:
        return {"result": ("TAPE_ERR_VERSION",)}
    if cand[16] == 1:
        return {"result": ("TAPE_ERR_INCOMPLETE",)}
    high = struct.unpack_from("<I", cand, 56)[0]
    ra, a = _side(img, 0, high)
    if ra != "TAPE_OK":
        return {"result": (ra,)}
    rb, bl = _side(img, 1, high)
    if requested_side == "B" and rb != "TAPE_OK":
        return {"result": (rb,)}
    layout = a if requested_side == "A" else bl
    live_b = [] if bl is None else bl
    free_next = max([high] + [f + (s + n - 1) // CF + 1 for f, s, n in live_b])
    return {"result": ("TAPE_OK",), "uuid": cand[20:36].hex(), "free_chunks": TOTAL_CHUNKS - free_next,
            "total_frames": sum(e[2] for e in layout), "entry_count": len(layout),
            "side_b_valid": rb == "TAPE_OK", "needs_repair": stale and not writable,
            "repair": (partner_lba, cand) if stale and writable else None,
            "layout": layout, "high": high, "generation": gen(cand)}


def rendered_sha256(img, layout):
    out = b""
    for first, start, n in layout:
        if first != 0 or start + n > 128:
            raise AssertionError("fixture layout outside the tracked audio block")
        out += img["C0"][start * 4:(start + n) * 4]
    return sha(out)
