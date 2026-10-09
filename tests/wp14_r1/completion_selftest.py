#!/usr/bin/env python3
"""ADR165 and final-package oracle controls. Synthetic, zero Product runs."""
import copy
import hashlib
import json
import struct
import tempfile
from pathlib import Path
from oracle import *
from fixtures import build,BLOCKS,crc,synthetic_fat
from native import audit_response,capture_identity,requests,prepare,symbol_absent,SEAM_SYMBOLS,SEAM_STRINGS
from runner import fat_controls,roundtrip_image_name,DEFAULT_TIMEOUT,C60_TIMEOUT
from catalog import image_cases,IMAGE_CONTROLS
from provision_replay import replay_cuts
from qualification import census
from a8_identity import tree_equal,ENGINE

def rejected(fn,*args):
    try: fn(*args)
    except AssertionError: return
    raise AssertionError('control survived')

def response(request,trace,code=0,text='OK\n'):
    request['request_sha256']=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
    return {'case':request['case'],'platform':request['platform'],'head_sha':'1'*40,
            'binary_sha256':'2'*64,'request_sha256':request['request_sha256'],
            'capture_origin':'native-candidate','control_applied':request.get('control'),
            'os_build':'synthetic oracle sample; not native evidence',
            'capture_artifacts':[{'path':'synthetic-not-candidate','sha256':'3'*64}],
            'exit':code,'stdout':text,'stderr':'','trace':trace}

def main():
    checks=[]; controls=[]
    names=[roundtrip_image_name(Path(name),kind) for name in ('one.wav','two.wav') for kind in ('bare','whole')]
    assert len(names)==len(set(names))==4 and DEFAULT_TIMEOUT < C60_TIMEOUT
    checks.append('roundtrip-image-isolation-and-c60-budget')
    def old_reuse(_source,_kind): return 'bare.img'
    assert len({old_reuse(Path(name),kind) for name in ('one.wav','two.wav') for kind in ('bare','whole')})==1
    controls.append('roundtrip-constant-image-reuse')
    signed=bytearray(512);signed[510:512]=b'\x55\xaa'
    entered=bytearray(512);entered[446]=1
    for kind in ('image','device'):
        for name,data,want in (('empty',bytes(512),False),('signed',signed,kind=='device'),
                               ('damaged-signature-surviving-entry',entered,True)):
            assert bool(candidate_recognition(data,kind))==want
            checks.append(kind+'-'+name)
    def old_or(data,kind): return bool(any(data[446:508]) or data[510:512]==b'\x55\xaa')
    assert old_or(signed,'image')!=candidate_recognition(signed,'image')
    controls.append('old-unconditional-OR-classifier')
    for name in ('verifier import','final verifier subtree','engine','golden src','golden ref','golden manifest/model'):
        tree_equal(ENGINE,ENGINE,name)
        rejected(tree_equal,ENGINE,'0'*40,name)
        checks.append('A8-identity-'+name);controls.append('A8-changed-'+name)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        for mutation in ('crc-signature','crc-signature-corrupt'):
            blocks=build(root/'crc.img',mutation)
            for lba in (0,BLOCKS-1):
                s=blocks[lba];assert not any(s[446:508]) and s[510:512]==b'\x55\xaa'
                assert not candidate_recognition(s,'image') and candidate_recognition(s,'device')
                assert (crc(s[:508])==struct.unpack_from('<I',s,508)[0])==(mutation=='crc-signature')
            checks.append('bare-admission-engine-judges-'+mutation)
        fat=root/'fat.img';synthetic_fat(fat,epoch=0)
        assert fat_controls(fat,'WP14',0)==IMAGE_CONTROLS[3:]
        fat16_readme(fat,'WP14',0); checks.append('all-candidate-FAT-controls-restore');controls.extend(IMAGE_CONTROLS[3:])
        for name in SEAM_STRINGS:
            binary=root/'binary';binary.write_bytes(b'native'+name.encode())
            rejected(symbol_absent,binary,'main');controls.append('string-absence-'+name)
        for name in SEAM_SYMBOLS:
            binary.write_bytes(b'native');rejected(symbol_absent,binary,' T _'+name)
            controls.append('symbol-absence-'+name)
        for platform in ('linux','macos','windows'):
            planned=requests(platform,root/'seed')
            names=[x['case'] for x in planned]
            assert len(names)==len(set(names))
            assert {'lba0-read-failure','provision-interruption-capture','empty-facts-default-refusal',
                    'native-hidden-flush-error','native-probe','native-exact-MBR-FAT-OS-README'}<=set(names)
            assert len([x for x in names if x.startswith('native-roundtrip-')])==11
            for name in REFUSALS:
                assert 'safety-isolated-'+name in names and 'admitted-pair-'+name in names
                guard=copy.deepcopy(next(r for r in planned if r['case']=='safety-isolated-'+name))
                gt={'operation':'provision','platform':platform,'target_kind':'device','target_bytes':guard['target_bytes'],
                    'refusal':name,'exit':3,'success':False,'engine_used':False,'events':[]}
                gr=response(guard,gt,3,name+': Forbidden device for this fixture.\n');audit_response(guard,gr)
                checks.append(platform+'-isolated-refusal-'+name)
                bad=copy.deepcopy(gr);bad['trace']['events']=[{'kind':'write_open'}]
                rejected(audit_response,guard,bad);controls.append(platform+'-write-open-on-'+name)
                bad=copy.deepcopy(gr);bad['stdout']=name+'\n'
                rejected(audit_response,guard,bad);controls.append(platform+'-missing-refusal-explanation-'+name)
            extras=['replay-before-first-write','replay-after-final-flush']
            census(names+extras,names);checks.append(platform+'-complete-census-'+str(len(names)))
            rejected(census,names[:-1]+extras,names);controls.append(platform+'-omitted-case')
            rejected(census,names+extras+[names[0]],names);controls.append(platform+'-duplicate-case')
            rejected(census,names,names);controls.append(platform+'-replay-omitted')
            req={'case':'synthetic-load','platform':platform,'command':'load','control':None,
                 'target_bytes':64_000_000_000,'require_large_io':True,'required_native_flush':True}
            call={'linux':'fsync','macos':'F_FULLFSYNC','windows':'FlushFileBuffers'}[platform]
            trace={'operation':'load','platform':platform,'target_kind':'device','target_bytes':64_000_000_000,
                   'success':True,'events':[{'kind':'write','offset':64_000_000_000-512,'bytes':512,
                                           'issued_before_return':True},
                                          {'kind':'flush','success':True,'os_call':call,'os_success':True}]}
            good=response(req,trace);audit_response(req,good);checks.append(platform+'-native-response')
            for name,modify in (
                ('wrapped-32-bit-offset',lambda r:r['trace']['events'][0].update(offset=512)),
                ('coalesced-write',lambda r:r['trace']['events'][0].update(coalesced=True)),
                ('unissued-write',lambda r:r['trace']['events'][0].update(issued_before_return=False)),
                ('hidden-barrier-error',lambda r:r['trace']['events'][1].update(os_success=False)),
                ('no-op-flush',lambda r:r['trace']['events'][1].update(os_call='none'))):
                bad=copy.deepcopy(good);modify(bad);rejected(audit_response,req,bad);controls.append(platform+'-'+name)
            bad=copy.deepcopy(good);bad['request_sha256']='0'*64
            rejected(capture_identity,req,bad);controls.append(platform+'-bad-capture-provenance')
            fault=copy.deepcopy(next(x for x in planned if x['case']=='native-flush-failure'))
            ft=copy.deepcopy(trace);ft['success']=False;ft['events'][-1].update(success=False,os_success=False)
            fr=response(fault,ft,1,'TAPE_ERR_IO\n');audit_response(fault,fr)
            checks.append(platform+'-OS-flush-error-propagated')
            bad=copy.deepcopy(fr);bad['exit']=0
            rejected(audit_response,fault,bad);controls.append(platform+'-OS-error-exit-zero')
            read=copy.deepcopy(next(x for x in planned if x['case']=='referenced-read-failure'))
            prepare(read,root)
            rt={'operation':'verify','platform':platform,'target_kind':'device','target_bytes':read['target_bytes'],
                'success':False,'events':[{'kind':'engine_bind','write_is_null':True}]+
                [{'kind':'engine_mount','side':s,'cold':True,'result':'TAPE_OK'} for s in ('A','B')]+
                [{'kind':'engine_info','side':s,'needs_repair':False,'side_b_valid':True} for s in ('A','B')]+
                [{'kind':'read','offset':(P2_START+2048)*512,'bytes':512,'success':False,
                  'phase':'service','referenced_chunk':True,'side':s,'frame':0} for s in ('A','B')]}
            rr=response(read,rt,1,'READ_ERROR SIDE A FRAME 0\nREAD_ERROR SIDE B FRAME 0\n')
            audit_response(read,rr);checks.append(platform+'-both-side-referenced-service-fault')
            for name,modify in (
                ('mount-error-not-service',lambda r:r['trace']['events'][-1].update(phase='mount')),
                ('unreferenced-chunk',lambda r:r['trace']['events'][-1].update(referenced_chunk=False)),
                ('warm-mount',lambda r:r['trace']['events'][1].update(cold=False)),
                ('missing-frame-finding',lambda r:r.update(stdout='READ_ERROR SIDE A FRAME 0\n')),
                ('nonnull-with-zero-writes',lambda r:r['trace']['events'][0].update(write_is_null=False))):
                bad=copy.deepcopy(rr);modify(bad);rejected(audit_response,read,bad);controls.append(platform+'-'+name)
            for request in planned:
                if 'mbr_corruption' not in request and not request.get('zero_table'): continue
                prepare(request,root)
                tr={'operation':'verify','platform':platform,'target_kind':'device',
                    'target_bytes':request['target_bytes'],'success':False,'engine_used':request.get('safe_view',False),
                    'events':[{'kind':'engine_bind','write_is_null':True}] if request.get('safe_view') else []}
                if request.get('safe_view'):
                    tr['events'] += [{'kind':'engine_mount','side':s,'cold':True,'result':'TAPE_OK'} for s in ('A','B')]
                    tr['events'] += [{'kind':'engine_info','side':s,'needs_repair':False,'side_b_valid':True} for s in ('A','B')]
                code=request.get('expected_failure',1)
                text=request.get('failure_text','\n'.join(request['expected_layout']) if 'expected_layout' in request else '')+'\n'
                got=response(request,tr,code,text);audit_response(request,got)
                checks.append(platform+'-'+request['case'])
                bad=copy.deepcopy(got);bad['stdout']='OK\n';bad['exit']=0
                rejected(audit_response,request,bad);controls.append(platform+'-missed-'+request['case'])
            # A truthful old whole image; synthetic transcript is only model validation.
            old=root/'old.img';build(old,whole=True);baseline=old.read_bytes()
            new_mbr=mbr(len(baseline)//512,bytes.fromhex('ffeeddccbbaa99887766554433221100'))
            events=[]
            for offset,data in ((0,bytes(512)),(P2_START*512,bytes(512)),(P1_START*512,bytes(512)),(0,new_mbr)):
                events.extend([{'kind':'write','offset':offset,'bytes':512,'data_hex':data.hex(),'issued_before_return':True},
                               {'kind':'flush','success':True,'os_success':True,'os_call':call}])
            journal={'operation':'provision','platform':platform,'target_kind':'device','target_bytes':len(baseline),
                     'success':True,'events':events}
            rows=replay_cuts(journal,baseline,new_mbr)
            assert len(rows)==18 and {r['outcome'] for r in rows}=={'old','unprovisioned','new'}
            checks.append(platform+'-all-provision-frontiers-18')
            bad=copy.deepcopy(journal);bad['events']=bad['events'][-2:]+bad['events'][:-2]
            rejected(replay_cuts,bad,baseline,new_mbr);controls.append(platform+'-published-MBR-first')
            bad=copy.deepcopy(journal);del bad['events'][1]
            rejected(replay_cuts,bad,baseline,new_mbr);controls.append(platform+'-missing-invalidation-barrier')
            bad=copy.deepcopy(journal);bad['events'][2]['data_hex']='01'*512;bad['events'][2]['bytes']=511
            rejected(replay_cuts,bad,baseline,new_mbr);controls.append(platform+'-wrong-write-payload-length')
    assert len(image_cases())==79 and len(set(image_cases()))==79 and len(IMAGE_CONTROLS)==11
    checks.append('image-census-79-controls-11')
    print(json.dumps({'kind':'completion-oracle-selftest','checks':checks,'controls_killed':controls,
                      'native_product_runs':0,'P2V005':'ADR165-resolved'},indent=2))

if __name__=='__main__':main()
