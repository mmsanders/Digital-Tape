#!/usr/bin/env python3
"""Mutation test for the VT8-001 oracle. Does not emulate or accept an engine."""
import copy, struct
from oracle import *

def expect_fail(c,post,ev,label):
    e=check(c,post,ev)
    if not e: raise AssertionError('mutation escaped: '+label)
    print('CAUGHT',label,'=>',e[0])

def main():
    cases=make_cases(); rb,rec=cases
    for c in cases:
        p,e=synth_post(c); errors=check(c,p,e)
        if errors: raise AssertionError((c.id,errors))
        print('PASS conforming',c.id)
    # Reset incorrectly uses live/equal-B max 500 instead of all-slot 900.
    p,e=synth_post(rb); s=list(p.slots); s[2]=idx(1,[(0,0,128)],501); expect_fail(rb,Media(p.blocks,p.primary,p.mirror,tuple(s)),e,'reset live-only sequence base')
    # Reset moves/writes audio.
    p,e=synth_post(rb); e=copy.deepcopy(e); e.insert(1,{'phase':'reset_b','op':'write','lba':LBA_CHUNK_BASE+2*1024,'count':1}); expect_fail(rb,p,e,'reset chunk write')
    # Recording ignores high structural A1 sequence.
    p,e=synth_post(rec); s=list(p.slots); s[3]=idx(1,[(0,0,128),(3,0,128)],21); expect_fail(rec,Media(p.blocks,p.primary,p.mirror,tuple(s)),e,'record live-only sequence base')
    # Recording writes below H.
    p,e=synth_post(rec); e=copy.deepcopy(e); e[0]['lba']=LBA_CHUNK_BASE+2*1024; expect_fail(rec,p,e,'record allocation below H/free_next')
    # Ordinary recording increments sb_generation.
    p,e=synth_post(rec); b=bytearray(p.primary); struct.pack_into('<I',b,12,8); struct.pack_into('<I',b,508,zlib.crc32(b[:508])); bad=bytes(b); expect_fail(rec,Media(p.blocks,bad,bad,p.slots),e,'record sb_generation increment')
    # New B index overlaps physical frame 0.
    p,e=synth_post(rec); s=list(p.slots); s[3]=idx(1,[(0,0,128),(0,64,128)],701); expect_fail(rec,Media(p.blocks,p.primary,p.mirror,tuple(s)),e,'record overlapping committed index')
    print('SELFTEST PASS: 2 conforming + 6 required mutations')
if __name__=='__main__': main()
