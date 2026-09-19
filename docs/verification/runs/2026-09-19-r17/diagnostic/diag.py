#!/usr/bin/env python3
"""SOFTWARE-OWNED DIAGNOSTIC. Not evidence, not acceptance, not a package run.

It imports tests/ops_draft8/ READ-ONLY and changes exactly one field of the two
VT8-001 fixtures: the superblock's nominal_length_s at offset 48, from 60 to 46.
Every oracle assertion, every expected value, every other fixture byte and the
whole runner are the package's own, unmodified.

Purpose: answer one question for the blocked return -- is the fixture's geometry
the ONLY thing standing between this engine and the package's verdict?
"""
import struct, sys, zlib
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv.pop(1))))

import oracle, hardened, runner

def fix_sb(b: bytes, seconds: int) -> bytes:
    m = bytearray(b)
    struct.pack_into('<I', m, 48, seconds)          # nominal_length_s only
    struct.pack_into('<I', m, 508, zlib.crc32(m[:508]))
    return bytes(m)

def patched_cases():
    out = []
    for c in oracle.make_cases():
        p = c.pre
        out.append(oracle.Case(c.id, c.operation,
                   oracle.Media(p.blocks, fix_sb(p.primary, 46), fix_sb(p.mirror, 46), p.slots)))
    return out

runner.make_cases = patched_cases
sys.exit(runner.main())
