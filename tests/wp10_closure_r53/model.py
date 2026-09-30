#!/usr/bin/env python3
"""Verifier-owned model for the WP-10 R53 format/duplicate crash rows (DRAFT-9).

Transactions are transcribed from tapefs Â§9.5/Â§9.6.  Superblock and WIP-template
bytes come from the accepted R29-B builders, pinned by Git blob identity.  The
mount classifier follows tapefs Â§4.1/Â§4.2/Â§5.2/Â§5.3; selftest cross-checks it
against the Â§9.5/Â§9.6 permitted-outcome tables.
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN_REL = "format_dup_identity_draft8/fixture.py"
PIN_BLOB = "86df43a254479464559e299855e900d5637836a9"


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _load_r29b():
    path = HERE.parent / PIN_REL
    if git_blob_sha(path) != PIN_BLOB:
        raise AssertionError(f"pinned R29-B fixture drifted: {git_blob_sha(path)}")
    spec = importlib.util.spec_from_file_location("wp10r53_r29b", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wp10r53_r29b"] = module
    spec.loader.exec_module(module)
    return module


B = _load_r29b()
BLOCK = B.BLOCK
CF = B.CHUNK_FRAMES
MIRROR = B.LBA_MIRROR
TOTAL_CHUNKS = B.TOTAL_CHUNKS
ZERO = bytes(BLOCK)
SLOTS = {"A0": B.LBA_A0, "A1": B.LBA_A1, "B0": B.LBA_B0, "B1": B.LBA_B1}
# Every block the oracle binds: both superblocks, header+entry block of each slot, chunk 0 block 0.
TRACKED = {"P": 0, "M": MIRROR, "C0": B.LBA_CHUNK_BASE}
for _name, _base in SLOTS.items():
    TRACKED[_name + "h"] = _base
    TRACKED[_name + "e"] = _base + 1
LBA_NAME = {lba: name for name, lba in TRACKED.items()}
OLD_UUID = B.OLD_UUID_A
SOURCE_AUDIO = bytes(((i * 37 + 5) & 0xFF) for i in range(BLOCK))   # 128 source frames
OLD_AUDIO = bytes(((i * 11 + 200) & 0xFF) for i in range(BLOCK))    # the destination's old album


def crc32(b):
    return zlib.crc32(b) & 0xFFFFFFFF


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


# ------------------------------------------------------------------ fixtures

OLD_SB = B.superblock(generation=7, uuid=OLD_UUID, high=1)


def destination(shape):
    img = {name: ZERO for name in TRACKED}
    if shape == "blank":
        return img
    img["P"] = img["M"] = OLD_SB
    img["C0"] = OLD_AUDIO
    img["A0h"], img["A0e"] = index_blocks(0, 100, [(0, 0, 128)])
    img["B0h"], img["B0e"] = index_blocks(1, 101, [(0, 0, 128)])
    if shape == "reusable_stale":
        # A different album's live index at a far higher sequence in slot 1 (acceptance WP-10
        # "reusable destination" (iii)); only Â§9.5/Â§9.6 step 2 prevents it winning Â§5.3.
        img["A1h"], img["A1e"] = index_blocks(0, 500, [(0, 32, 64)])
        img["B1h"], img["B1e"] = index_blocks(1, 501, [(0, 32, 64)])
    elif shape != "reusable_good":
        raise KeyError(shape)
    return img


SCENARIOS = {
    # id: (operation, source_frames, destination shape, gap row)
    "DUP-EMPTY-BLANK": ("dup", 0, "blank", "WP10.dup.empty_source.every_boundary"),
    "DUP-EMPTY-REUSABLE": ("dup", 0, "reusable_good", "WP10.dup.empty_source.every_boundary"),
    "DUP-REUSABLE-STALE": ("dup", 128, "reusable_stale", "WP10.format_dup.steps2_3.reusable_stale_slot1"),
    "FMT-REUSABLE-STALE": ("format", 0, "reusable_stale", "WP10.format_dup.steps2_3.reusable_stale_slot1"),
    "FMT-BLANK": ("format", 0, "blank", "WP10.format_dup.blank_media_table"),
    "DUP-BLANK": ("dup", 128, "blank", "WP10.format_dup.blank_media_table"),
}


def final_sb(op, frames):
    uuid = B.FRESH_DUP_UUID if op == "dup" else B.FRESH_FORMAT_UUID
    return B.superblock(generation=1, state=0, uuid=uuid, high=-(-frames // CF))


def transaction(scenario, mutant=None):
    """Ordered ('w', block-name, bytes) / ('f',) operations of tapefs Â§9.5 / Â§9.6."""
    op, frames, shape, _ = SCENARIOS[scenario]
    ops = []
    if shape != "blank":
        tmpl = B.wip_template(OLD_SB, existing_generation=7)
        ops += [("w", "M", tmpl), ("f",)]
        if mutant == "template_flush_skipped":
            ops.pop()
        ops += [("w", "P", tmpl), ("f",)]
    zeroed = ("A0h", "A1h", "B0h", "B1h") if op == "dup" else ("A1h", "B1h")
    if mutant == "slot1_not_zeroed":
        zeroed = tuple(n for n in zeroed if not n.startswith(("A1", "B1")))
    ops += [("w", n, ZERO) for n in zeroed] + [("f",)]
    if op == "dup" and frames:
        a_h, a_e = index_blocks(0, 1, [(0, 0, frames)])
        b_h, b_e = index_blocks(1, 2, [(0, 0, frames)])
        ops += [("w", "C0", SOURCE_AUDIO), ("f",), ("w", "A0e", a_e), ("f",), ("w", "A0h", a_h), ("f",),
                ("w", "B0e", b_e), ("f",), ("w", "B0h", b_h), ("f",)]
    else:
        entries = [(0, 0, 0)] if mutant == "empty_source_zero_frame_entry" else []
        a_h, a_e = index_blocks(0, 1, entries)
        b_h, b_e = index_blocks(1, 2, entries)
        if entries:
            ops += [("w", "A0e", a_e), ("w", "B0e", b_e)]
        ops += [("w", "A0h", a_h), ("w", "B0h", b_h), ("f",)]
    final = final_sb(op, frames)
    order = ("P", "M") if mutant == "primary_before_mirror" else ("M", "P")
    ops += [("w", order[0], final), ("f",), ("w", order[1], final), ("f",)]
    return ops


def writes_and_flushes(ops):
    return sum(o[0] == "w" for o in ops), sum(o[0] == "f" for o in ops)


# ------------------------------------------------------- crash durability model

def possible_images(scenario, inject, mode, mutant=None):
    """All durable images a conforming device may hold at the crash (tapefs Â§8.1).

    inject: ("write", k, landed 0..512) or ("flush", j).  Torn prefixes are durable in
    both modes; a completed write is durable at once in write-through, and only after
    its flush returns in flush-required (before that it may or may not have landed).
    """
    op, frames, shape, _ = SCENARIOS[scenario]
    base = destination(shape)
    ops = transaction(scenario, mutant)
    durable = dict(base)
    pending = []
    wk = fk = 0
    for o in ops:
        if o[0] == "w":
            if inject[0] == "write" and inject[1] == wk:
                landed = inject[2]
                if landed == BLOCK:
                    if mode == "write_through":
                        durable[o[1]] = o[2]
                    else:
                        pending.append((o[1], o[2]))
                elif landed:
                    torn = (o[1], o[2][:landed] + durable[o[1]][landed:])
                    return _expand(durable, pending, torn)
                return _expand(durable, pending)
            if mode == "write_through":
                durable[o[1]] = o[2]
            else:
                pending.append((o[1], o[2]))
            wk += 1
        else:
            if inject[0] == "flush" and inject[1] == fk:
                return _expand(durable, pending)
            for name, data in pending:
                durable[name] = data
            pending = []
            fk += 1
    raise AssertionError("injection coordinate beyond transaction")


def _expand(durable, pending, torn=None):
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


def injections(scenario, mutant=None):
    nw, nf = writes_and_flushes(transaction(scenario, mutant))
    for mode in ("flush_required", "write_through"):
        for k in range(nw):
            for landed in range(BLOCK + 1):
                yield mode, ("write", k, landed)
        for j in range(nf):
            yield mode, ("flush", j)


def completed_image(scenario, mutant=None):
    op, frames, shape, _ = SCENARIOS[scenario]
    img = destination(shape)
    for o in transaction(scenario, mutant):
        if o[0] == "w":
            img[o[1]] = o[2]
    return img


def image_hashes(img):
    return {name: hashlib.sha256(img[name]).hexdigest() for name in sorted(TRACKED)}


# ------------------------------------------------------------ mount classifier

def _sb_valid(x):
    return x[:8] == B.MAGIC_SB and crc32(x[:508]) == struct.unpack_from("<I", x, 508)[0]


def _slot(img, name, side, high):
    h, e = img[name + "h"], img[name + "e"]
    if h[:8] != B.MAGIC_IDX:
        return None
    seq, sd, count, total = struct.unpack_from("<I", h, 8)[0], h[12], *struct.unpack_from("<I", h, 16), \
        struct.unpack_from("<Q", h, 20)[0]
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
    """Public mount outcome predicted from raw durable bytes."""
    p, m = img["P"], img["M"]
    vp, vm = _sb_valid(p), _sb_valid(m)
    if not vp and not vm:
        magic = p[:8] == B.MAGIC_SB or m[:8] == B.MAGIC_SB
        # tapefs Â§4.1 allows BAD_MAGIC or CRC here; Â§9.5/Â§9.6 and WP-10 name only BAD_MAGIC.
        return {"result": ("TAPE_ERR_BAD_MAGIC", "TAPE_ERR_CRC") if magic else ("TAPE_ERR_BAD_MAGIC",),
                "pm_finding_crc": magic}
    gp = struct.unpack_from("<I", p, 12)[0] if vp else -1
    gm = struct.unpack_from("<I", m, 12)[0] if vm else -1
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
            "layout": layout, "high": high}


def rendered_sha256(img, layout):
    """SHA-256 of the side rendered at 1.0x from frame 0; fixtures keep audio in chunk 0 block 0."""
    out = b""
    for first, start, n in layout:
        if first != 0 or start + n > 128:
            raise AssertionError("fixture layout outside the tracked audio block")
        out += img["C0"][start * 4:(start + n) * 4]
    return hashlib.sha256(out).hexdigest()
