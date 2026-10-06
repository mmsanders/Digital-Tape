#!/usr/bin/env python3
"""ADR164 delta cases and rejecting controls. All observations here are synthetic."""
import copy
import hashlib
import json
import struct
import tempfile
from pathlib import Path
from oracle import *
from fixtures import build, synthetic_fat, BLOCKS, crc
from native import audit_response, requests, symbol_absent
from runner import make_wav, compare_wav

def fails(fn,*args):
    try: fn(*args)
    except AssertionError: return True
    raise AssertionError('control survived')

def main():
    checks=[]; controls=[]
    good=mbr(P2_START+BLOCKS)
    for off in (0,444,446,447,450,454,458,462,463,466,470,474,478,510):
        bad=bytearray(good); bad[off]^=1
        assert candidate_recognition(bad)
        want=['PARTITION_TYPE'] if off in (450,466) else ['MBR_LAYOUT']
        if off==474: want=['MBR_LAYOUT']  # one-sector-short declared extent
        if off==470: want=['MBR_LAYOUT','PARTITION_TRUNCATED']
        assert layout_findings(bad,P2_START+BLOCKS)==want,(off,layout_findings(bad,P2_START+BLOCKS))
        checks.append('candidate-reaches-finding-'+str(off))
    bad=bytearray(good); bad[0]=1; bad[450]^=1
    struct.pack_into('<I',bad,474,0xffffffff)
    assert layout_findings(bad,P2_START+BLOCKS)==['MBR_LAYOUT','PARTITION_TYPE','PARTITION_TRUNCATED']
    assert not safe_view(bad,P2_START+BLOCKS)
    checks.append('multiple-findings-order-safe-extents')
    bad=bytearray(good); bad[510]=0; assert candidate_recognition(bad)
    bad=bytearray(512); bad[510:512]=b'\x55\xaa'; assert candidate_recognition(bad)
    assert not candidate_recognition(bytes(512))
    checks.append('OR-signature-damaged-signature-zero')
    assert fat_time(0)==fat_time(1)==fat_time(315532799)==(0,33)
    assert fat_time(315532800)==fat_time(315532801)==(0,33)
    assert fat_time(315532802)==(1,33)
    checks.append('UTC-clamp-and-two-second-floor')
    with tempfile.TemporaryDirectory() as temp:
        source=Path(temp)/'source.wav'; output=Path(temp)/'output.wav'
        make_wav(source,129); output.write_bytes(source.read_bytes()); compare_wav(source,output)
        checks.append('exact-final-frame-roundtrip')
        output.write_bytes(source.read_bytes()[:-4])
        assert fails(compare_wav,source,output); controls.append('drop-final-frame')
        output.write_bytes(source.read_bytes()+bytes(4))
        assert fails(compare_wav,source,output); controls.append('append-zero-tail')
        data=bytearray(source.read_bytes()); data[-1]^=1; output.write_bytes(data)
        assert fails(compare_wav,source,output); controls.append('wrong-last-sample')
        image=Path(temp)/'fat.img'
        for epoch in (0,1,315532799,315532800,315532801,946684799,946684800,0xffffffff):
            synthetic_fat(image,epoch=epoch); fat16_readme(image,'WP14',epoch)
            checks.append('timestamp-'+str(epoch))
        synthetic_fat(image,epoch=315532802)
        assert fails(fat16_readme,image,'WP14',315532800); controls.append('wrong-UTC-timestamp')
        blocks=build(Path(temp)/'collision.img','crc-signature')
        s=blocks[0]
        assert s==blocks[BLOCKS-1] and crc(s[:508])==struct.unpack_from('<I',s,508)[0]
        assert geometry(9,BLOCKS) and not any(s[446:508])
        assert s[510:512]==b'\x55\xaa' and candidate_recognition(s,'device')
        # Historical delta witness retained; now covered by ADR165.
        assert not candidate_recognition(s,'image')
        checks.append('ADR165-valid-bare-CRC-collision')
        for kind in ('shipped','test'):
            binary=Path(temp)/kind; binary.write_bytes(b'native-code'+(b'TAPECTL_TEST_FACTS' if kind=='test' else b''))
            symbols='tapectl_test_facts_seam' if kind=='test' else 'main'
            if kind=='shipped': symbol_absent(binary,symbols)
            else: assert fails(symbol_absent,binary,symbols); controls.append('production-seam-gate')
    for platform in ('linux','macos','windows'):
        reqs=requests(platform,Path('/synthetic/owned-image'))
        assert len({x['case'] for x in reqs})==len(reqs)
        for request in reqs:
            if request['case'].startswith('safety-'):
                assert policy(request['facts'],True,request['erase_matches'])==request['expected_refusal']
        checks.append(platform+'-ordered-and-isolated-safety')
        checks.append('native-case-census-'+platform+'-'+str(len(reqs)))
        t={'operation':'load','platform':platform,'target_kind':'device','target_bytes':64_000_000_000,
           'success':True,'events':[{'kind':'write','offset':(1<<32)+512,'bytes':512,'issued_before_return':True},
           {'kind':'flush','success':True,'os_success':True,'os_call':{'linux':'fsync','macos':'F_FULLFSYNC','windows':'FlushFileBuffers'}[platform]}]}
        trace_audit(t); checks.append('native-trace-oracle-'+platform)
        bad=copy.deepcopy(t); bad['events'][-1]['os_call']='none'
        assert fails(trace_audit,bad); controls.append('no-op-native-call-'+platform)
        bad=copy.deepcopy(t); bad['events'][-1]['os_success']=False
        assert fails(trace_audit,bad); controls.append('false-flush-success-'+platform)
        if platform=='macos':
            fallback=copy.deepcopy(t); fallback['events'][-1].update(os_call='DKIOCSYNCHRONIZECACHE',fullfsync_unsupported='ENOTTY')
            trace_audit(fallback); checks.append('explicit-unsupported-raw-fallback')
            bad=copy.deepcopy(fallback); bad['target_kind']='image'
            assert fails(trace_audit,bad); controls.append('image-fallback-refused')
            bad=copy.deepcopy(fallback); bad['events'][-1]['fullfsync_unsupported']='EIO'
            assert fails(trace_audit,bad); controls.append('unrelated-error-fallback-refused')
        for command in ('verify','play','scrub','dump'):
            v={'operation':command,'platform':platform,'target_kind':'device','target_bytes':6145*512,
               'events':[{'kind':'engine_bind','write_is_null':True}]}
            trace_audit(v); checks.append(platform+'-NULL-'+command)
            v['events'][0]['write_is_null']=False
            assert fails(trace_audit,v); controls.append(platform+'-nonNULL-'+command)
        provision=copy.deepcopy(t); provision['operation']='provision'
        flush=copy.deepcopy(t['events'][-1]); provision['events']=[]
        for off,data in ((0,bytes(512)),(P2_START*512,bytes(512)),(P1_START*512,bytes(512)),(0,good)):
            provision['events'].extend([{'kind':'write','offset':off,'bytes':512,'data_hex':data.hex(),
                                        'issued_before_return':True},copy.deepcopy(flush)])
        provision_order(provision); checks.append(platform+'-provision-order')
        bad=copy.deepcopy(provision); bad['events']=bad['events'][2:]+bad['events'][:2]
        assert fails(provision_order,bad); controls.append(platform+'-MBR-last-order')
        bad=copy.deepcopy(provision); del bad['events'][1]
        assert fails(provision_order,bad); controls.append(platform+'-invalidation-barrier')
    print(json.dumps({'kind':'amendment-oracle-selftest','checks':checks,'controls_killed':controls,
                      'native_product_runs':0,'P2V005':'ADR165-resolved'},indent=2))

if __name__=='__main__': main()
