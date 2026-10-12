#!/usr/bin/env python3
"""Finite contract regression and causal oracle controls, never Product evidence."""
import copy
import json
import struct
import tempfile
from oracle import *
from fixtures import build, BLOCKS, crc, synthetic_fat

def rejected(fn, *args):
    try: fn(*args)
    except AssertionError: return True
    raise AssertionError('negative control survived')

def main():
    checks, controls = [], []
    for length in (1,9,21,60,3600,5400,7200,97391):
        n = minimum_blocks(length)
        assert geometry(length, n) and not geometry(length,n-1)
        checks.append('geometry-exact-and-one-short-'+str(length))
    assert not geometry(0, 0xffffffff) and not geometry(97392,0xffffffff)
    assert minimum_blocks(3600) == 1243137
    checks.append('label-arithmetic-overflow')
    with tempfile.TemporaryDirectory() as temp:
        for mutation in ('clean','invalid-standby','torn-primary','both-superblocks-bad',
                         'flipped-a-entry','degraded-b'):
            blocks=build(Path(temp)/'fixture.img',mutation)
            s=blocks[BLOCKS-1]
            assert geometry(struct.unpack_from('<I',s,48)[0],BLOCKS)
            assert struct.unpack_from('<I',s,52)[0]==4
            primary_ok=crc(blocks[0][:508])==struct.unpack_from('<I',blocks[0],508)[0]
            assert primary_ok==(mutation not in ('torn-primary','both-superblocks-bad'))
            if mutation=='flipped-a-entry':
                assert crc(blocks[8][:60]+blocks[9][:12])!=struct.unpack_from('<I',blocks[8],60)[0]
            checks.append('fixture-'+mutation)
        image=Path(temp)/'fat.img'
        for fatsecs in (32,33):
            synthetic_fat(image,fatsecs)
            assert fat16_readme(image,'WP14')['clusters']==(32768-1-2*fatsecs-32)//4
            checks.append('fat-alternate-conforming-'+str(fatsecs))
        for offset in (13,43,510):
            synthetic_fat(image)
            with image.open('r+b') as f:
                f.seek(P1_START*512+offset); v=f.read(1)
                f.seek(P1_START*512+offset); f.write(bytes((v[0]^1,)))
            assert rejected(fat16_readme,image,'WP14')
            controls.append('fat-field-'+str(offset))
        synthetic_fat(image)
        assert rejected(fat16_readme,image,'wrong-label')
        controls.append('wrong-readme-label')
    good = mbr(64_000_000_000//BLOCK)
    assert exact_recognition(good,64_000_000_000//BLOCK)
    assert layout_findings(good,64_000_000_000//BLOCK,UUID) == []
    # These are contradiction witnesses, not proposed conforming CLI outcomes.
    for off in (450,466,446,447,454,478,510):
        bad = bytearray(good); bad[off] ^= 1
        assert not exact_recognition(bad,64_000_000_000//BLOCK)
        assert layout_findings(bad,64_000_000_000//BLOCK)
        checks.append('unreachable-layout-'+str(off))
    assert not exact_recognition(good,64_000_000_000//BLOCK-1)
    assert 'PARTITION_TRUNCATED' in layout_findings(good,64_000_000_000//BLOCK-1)
    checks.append('unreachable-truncation')
    base = {'whole':True,'removable':True,'sd_bus':False,'bytes':1<<37,
            'holds_os':False,'foreign_mount':False}
    assert policy(base,True,True) is None
    assert policy(dict(base,removable=False,sd_bus=True)) is None
    for i, name in enumerate(REFUSALS):
        bad = dict(base)
        for key,val in list(zip(('whole','removable','bytes','holds_os','foreign_mount'),
                                (False,False,(1<<37)+1,True,True)))[i:]:
            bad[key] = val
        assert policy(bad,True,False) == name
        checks.append('refusal-order-'+name)
    # A later block without an earlier block is absent even from all prefix cuts.
    states = permitted_subsets({0:b'a',1:b'b'},[(0,b'A'),(1,b'B')])
    later_only = ((0,b'a'),(1,b'B'))
    prefixes = {((0,b'a'),(1,b'b')),((0,b'A'),(1,b'b')),((0,b'A'),(1,b'B'))}
    assert len(states)==4 and later_only in states and later_only not in prefixes
    checks.append('subset-counterexample')
    trace = {'operation':'load','platform':'linux','target_bytes':1<<36,'success':True,
             'events':[{'kind':'write','offset':(1<<32)+512,'bytes':512,'issued_before_return':True},
                       {'kind':'flush','success':True,'os_call':'fsync','os_success':True}]}
    trace_audit(trace); checks.append('large-offset-and-durable-flush')
    noflush = copy.deepcopy(trace); noflush['events'].pop()
    assert rejected(trace_audit,noflush); controls.append('no-op-flush')
    falseflush = copy.deepcopy(trace); falseflush['events'][1]['os_success']=False
    assert rejected(trace_audit,falseflush); controls.append('flush-error-hidden')
    coalesced = copy.deepcopy(trace); coalesced['events'][0]['coalesced']=True
    assert rejected(trace_audit,coalesced); controls.append('write-coalescing')
    for platform,call in (('macos','F_FULLFSYNC'),('windows','FlushFileBuffers')):
        t=copy.deepcopy(trace); t['platform']=platform; t['events'][1]['os_call']=call
        trace_audit(t); checks.append('flush-'+platform)
    verify = {'operation':'verify','platform':'linux','target_bytes':1<<36,
              'events':[{'kind':'engine_bind','write_is_null':True}]}
    trace_audit(verify); checks.append('literal-null-binding')
    bad=copy.deepcopy(verify); bad['events'][0]['write_is_null']=False
    assert rejected(trace_audit,bad); controls.append('non-null-binding')
    bad=copy.deepcopy(verify); bad['events'].append({'kind':'write_open'})
    assert rejected(trace_audit,bad); controls.append('verify-write-open')
    for name in REFUSALS:
        t={'operation':'provision','refusal':name,'exit':3,'platform':'linux',
           'target_bytes':1<<36,'events':[]}
        trace_audit(t)
        t['events']=[{'kind':'write_open'}]
        assert rejected(trace_audit,t); controls.append('write-open-after-'+name)
    print(json.dumps({'kind':'verifier-selftest','checks':checks,'controls_killed':controls,
                      'product_runs':0},indent=2))

if __name__=='__main__': main()
