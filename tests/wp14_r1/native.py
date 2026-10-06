#!/usr/bin/env python3
"""Independent expectations; Software supplies only a native capture transport.

Transport command receives request.json response.json and launches the real candidate.
It must not supply PASS, expectations, finding judgments or synthetic observations.
"""
import argparse
import copy
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from oracle import REFUSALS, policy, trace_audit, provision_order, verify_observations, P2_START, layout_findings, safe_view, mbr, UUID, fat16_readme
from fixtures import build
from catalog import MBR_FIELDS, COMMANDS

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def symbol_absent(binary, symbols):
    data=Path(binary).read_bytes()
    for name in SEAM_STRINGS: assert name.encode() not in data, name
    for name in SEAM_SYMBOLS: assert not re.search(r'\b_?'+name+r'\b',symbols), name

SEAM_SYMBOLS=('tapectl_test_facts_seam','tseam_begin','tseam_flush','tseam_fault_noop_flush',
              'tseam_fault_read','tseam_fault_nonnull_binding')
SEAM_STRINGS=('TAPECTL_TEST_FACTS','TAPECTL_TEST_TRACE','TAPECTL_TEST_FAULT','noop-flush',
              'hidden-flush-error','nonnull-binding','read-error')

def capture_identity(request,response):
    # Provenance failures cannot count as killed candidate mutants.
    assert response['case']==request['case']
    assert response['capture_origin']=='native-candidate'
    assert re.fullmatch('[0-9a-f]{64}',response['binary_sha256'])
    assert re.fullmatch('[0-9a-f]{40}',response['head_sha'])
    assert response['request_sha256']==request['request_sha256']
    material={k:v for k,v in request.items() if k!='request_sha256'}
    assert request['request_sha256']==hashlib.sha256(json.dumps(material,sort_keys=True).encode()).hexdigest()
    assert response['platform']==request['platform']
    assert response['capture_artifacts'], 'missing raw native capture'
    assert isinstance(response['os_build'],str) and response['os_build'], 'missing named OS build'
    assert response.get('control_applied')==request.get('control')

def audit_response(request,response):
    capture_identity(request,response)
    t=response['trace']; assert t['operation']==request['command']
    assert t['platform']==request['platform']
    no_engine=(request.get('expected_refusal') or request.get('required_probe') or
               request.get('lba0_read_failure') or
               request.get('expected_layout') is not None and not request['safe_view'] or
               request.get('failure_text')=='NOT_PROVISIONED')
    if request['command']=='verify' and not no_engine:
        assert any(e['kind']=='engine_bind' for e in t['events'])
    assert t['target_bytes']==request['target_bytes']
    if request['command']=='verify' and not no_engine:
        lines=(response['stdout']+response['stderr']).splitlines()
        verify_observations(t,request.get('expected_layout',[]),[x for x in lines if x])
    if request.get('required_probe'):
        assert not any(e['kind'] in ('write','write_open','engine_bind','engine_mount') for e in t['events'])
        facts=response['probe_facts']
        assert facts['source']=='platform probe' and not response['facts_env_supplied']
        assert all(key in facts for key in ('whole','removable','sd_bus','bytes','holds_os','mounted'))
        assert facts['bytes']==request['target_bytes']
        assert response['exit'] in (0,3) # probe is a test-only diagnostic; exit not issued
        return True
    trace_audit(t)
    if 'expected_refusal' in request:
        assert response['exit']==3 and t.get('refusal')==request['expected_refusal']
        assert request['expected_refusal'] in response['stdout']+response['stderr']
        text=response['stdout']+response['stderr']
        assert re.findall(r'REFUSE_[A-Z_]+',text)==[request['expected_refusal']]
        explanation=text.replace(request['expected_refusal'],'',1).strip(' :-\n\t')
        assert re.search(r'[A-Za-z]{2,}\s+[A-Za-z]{2,}',explanation), 'missing plain refusal explanation'
    if request.get('required_null'):
        binds=[e for e in t['events'] if e['kind']=='engine_bind']
        assert binds and all(e['write_is_null'] for e in binds)
    if request.get('require_large_io'):
        ios=[e for e in t['events'] if e['kind'] in ('read','write')]
        assert any(e['offset']>0xffffffff for e in ios),'no authenticated >4GiB I/O'
    if request.get('required_read_failure'):
        failed=[e for e in t['events'] if e['kind']=='read' and not e['success']]
        assert failed and all(e['phase']=='service' and e['referenced_chunk'] for e in failed)
        assert response['exit']==1 and 'READ_ERROR SIDE A FRAME ' in response['stdout']+response['stderr']
        assert [(e['side'],e['frame']) for e in failed]==[('A',0),('B',0)]
    if request.get('required_flush_failure'):
        fs=[e for e in t['events'] if e['kind']=='flush' and not e['os_success']]
        assert fs and response['exit']!=0 and not t.get('success')
    if request.get('required_native_flush'):
        assert any(e['kind']=='write' for e in t['events'])
        assert any(e['kind']=='flush' and e['os_success'] for e in t['events'])
    if request.get('required_provision_order'): provision_order(t)
    if request.get('expected_layout') is not None:
        output=response['stdout'].splitlines()+response['stderr'].splitlines()
        observed=[x for x in output if x in ('MBR_LAYOUT','PARTITION_TYPE','PARTITION_TRUNCATED')]
        assert observed==request['expected_layout']
        assert response['exit']==1
        if not request['safe_view']:
            assert not any(e['kind']=='engine_bind' for e in t['events'])
            assert not any(x.startswith(('MOUNT ','READ_ERROR ')) for x in output)
        return True
    if request.get('roundtrip'):
        from runner import compare_wav
        assert response['reattached'], 'same open/cache is not a reattach round trip'
        for side in ('A','B'):
            compare_wav(request['source'],response['dumps'][side])
            dump=response['dump_traces'][side]
            assert dump['operation']=='dump' and dump['platform']==request['platform']
            assert dump['target_kind']=='device' and dump['target_bytes']==request['target_bytes']
            trace_audit(dump)
    if request.get('required_os_readme'):
        from oracle import fat16_readme
        assert response['os_readme']['read_via']=='native-filesystem'
        assert response['os_readme']['volume_label']=='DIGITALTAPE'
        want=('This is a Digital Tape cartridge.\r\nLabel: WP14\r\nPlease do not format or erase this card on a computer.\r\nUse the Digital Tape app to load music onto it.\r\n').encode()
        assert bytes.fromhex(response['os_readme']['content_hex'])==want
        snapshot=response['snapshot']
        assert Path(snapshot).stat().st_size==request['target_bytes']
        with Path(snapshot).open('rb') as f: assert f.read(512)==mbr(request['target_bytes']//512)
        fat16_readme(snapshot,'WP14',315532800)
        verify=response['verify_trace']
        assert response['verify_exit']==0 and verify['operation']=='verify'
        assert verify['platform']==request['platform'] and verify['target_kind']=='device'
        assert verify['target_bytes']==request['target_bytes']
        trace_audit(verify)
        verify_observations(verify,[],response['verify_output'].splitlines())
    if request.get('expected_failure'):
        assert response['exit']==request['expected_failure']
        assert request['failure_text'] in response['stdout']+response['stderr']
        assert not any(e['kind']=='write' for e in t['events'])
        assert not t.get('success')
        return True
    if not request.get('expected_refusal') and not request.get('required_read_failure') and not request.get('required_flush_failure'):
        assert response['exit']==0 and t.get('success')
    return True

def requests(platform,backing):
    base={'whole':True,'removable':True,'sd_bus':False,'bytes':64_000_000_000,
          'holds_os':False,'foreign_mount':False,'virtual':False}
    cases=[]
    for i,name in enumerate(REFUSALS):
        facts=dict(base)
        for key,val in list(zip(('whole','removable','bytes','holds_os','foreign_mount'),
                               (False,False,(1<<37)+1,True,True)))[i:]: facts[key]=val
        cases.append({'case':'safety-'+name,'command':'provision','facts':facts,
                      'erase_matches':False,'expected_refusal':name,'control':None})
        # Isolate each forbidden fact, with all other facts admissible, then run
        # its repaired counterpart. These are real candidate input controls.
        isolated=dict(base)
        if i<5: isolated[('whole','removable','bytes','holds_os','foreign_mount')[i]]=(False,False,(1<<37)+1,True,True)[i]
        cases.append({'case':'safety-isolated-'+name,'command':'provision','facts':isolated,
                      'erase_matches':i!=5,'expected_refusal':name,'control':None})
        cases.append({'case':'admitted-pair-'+name,'command':'provision','facts':base,
                      'erase_matches':True,'control':None})
    for command in ('verify','play','scrub','dump'):
        cases.append({'case':'readonly-'+command,'command':command,'facts':base,'required_null':True,'control':None})
        cases.append({'case':'nonnull-'+command,'command':command,'facts':base,'required_null':True,
                      'control':'nonnull-binding','expect_oracle_reject':True})
    for command in COMMANDS:
        cases.append({'case':'large-'+command,'command':command,'facts':base,'require_large_io':True,'control':None})
    for name,changes,erase,refusal in (
        ('ceiling-equality',{'bytes':1<<37},True,None),
        ('ceiling-over',{'bytes':(1<<37)+1},True,'REFUSE_TOO_LARGE'),
        ('sd-bus-exception',{'removable':False,'sd_bus':True},True,None),
        ('non-removable',{'removable':False,'sd_bus':False},True,'REFUSE_NOT_REMOVABLE'),
        ('own-P1-mounted',{'mounted':['1:owned'],'layout_ok':True},True,None),
        ('foreign-P1-mounted',{'foreign_mount':True,'layout_ok':False},True,'REFUSE_FOREIGN_MOUNT'),
        ('unmount-failure',{'mounted':['1:owned'],'layout_ok':True},True,'REFUSE_FOREIGN_MOUNT'),
    ):
        case={'case':name,'command':'provision','facts':dict(base,**changes),'erase_matches':erase,
              'control':'unmount-error' if name=='unmount-failure' else None}
        if refusal: case['expected_refusal']=refusal
        cases.append(case)
    cases.extend([
        {'case':'provision-order','command':'provision','facts':base,'erase_matches':True,
         'required_provision_order':True,'seed_nonzero_mbr':True,'control':None},
        {'case':'provision-order-control','command':'provision','facts':base,'erase_matches':True,
         'required_provision_order':True,'seed_nonzero_mbr':True,'control':'noop-flush','expect_oracle_reject':True},
        {'case':'geometry-zero-write','command':'provision','facts':base,'erase_matches':True,
         'geometry_too_small':True,'expected_failure':1,'failure_text':'TAPE_ERR_GEOMETRY','control':None},
        {'case':'capacity-zero-write','command':'load','facts':base,'label_seconds':1,'source_frames':44101,
         'expected_failure':2,'failure_text':'Too long by 1 s for a 1-second cartridge','control':None},
    ])
    for mutation,token in (('torn-primary','NEEDS_REPAIR'),('both-superblocks-bad','MOUNT TAPE_ERR_'),
                           ('flipped-a-entry','MOUNT TAPE_ERR_NO_VALID_INDEX'),('degraded-b','SIDE_B_DEGRADED')):
        cases.append({'case':mutation,'command':'verify','facts':base,
                      'fixture':mutation,'required_null':True,'expected_failure':1,'failure_text':token,'control':None})
    for mutation in ('clean','invalid-standby'):
        cases.append({'case':'fixture-'+mutation,'command':'verify','facts':base,'fixture':mutation,
                      'required_null':True,'control':None})
    cases.extend([
        {'case':'native-flush','command':'load','facts':base,'control':None,'required_native_flush':True},
        {'case':'native-noop-flush','command':'load','facts':base,'control':'noop-flush','expect_oracle_reject':True,'required_native_flush':True},
        {'case':'native-hidden-flush-error','command':'load','facts':base,'control':'hidden-flush-error',
         'required_native_flush':True,'expect_oracle_reject':True},
        {'case':'native-flush-failure','command':'load','facts':base,'control':'native-flush-error','required_flush_failure':True},
        {'case':'referenced-read-failure','command':'verify','facts':base,'required_null':True,
         'control':'read-error:2048','fixture':'clean','required_read_failure':True},
        {'case':'seam-absent-production','command':'symbols','facts':base,'binary_kind':'shipped','control':None},
        {'case':'seam-present-control','command':'symbols','facts':base,'binary_kind':'test','control':None,
         'expect_oracle_reject':True},
        {'case':'production-loop-refusal','command':'verify','facts':base,'binary_kind':'shipped',
         'logical_target':'/dev/loopN','expected_refusal':'REFUSE_NOT_WHOLE_DEVICE','control':None},
        {'case':'production-virtual-refusal','command':'verify','facts':base,'binary_kind':'shipped',
         'target_setup':'actual-virtual-device','expected_refusal':
         'REFUSE_NOT_WHOLE_DEVICE' if platform=='linux' else 'REFUSE_NOT_REMOVABLE','control':None},
    ])
    cases.append({'case':'native-exact-MBR-FAT-OS-README','command':'provision','facts':base,
                  'required_os_readme':True,'control':None})
    cases.append({'case':'provision-interruption-capture','command':'provision','facts':base,
                  'required_provision_order':True,'required_replay':True,'fixture':'clean',
                  'new_uuid':'ffeeddccbbaa99887766554433221100','new_epoch':946684800,
                  'new_label':'NEW','label_seconds':9,'control':None})
    for off in MBR_FIELDS:
        cases.append({'case':'layout-native-'+str(off),'command':'verify','facts':base,
                      'mbr_corruption':off,'control':None})
    for signed in (False,True):
        cases.append({'case':'zero-table-device-'+str(signed),'command':'verify','facts':base,
                      'zero_table':True,'signed':signed,'control':None})
    cases.append({'case':'empty-facts-default-refusal','command':'provision','facts':{},'control':None,
                  'expected_refusal':'REFUSE_NOT_WHOLE_DEVICE'})
    cases.append({'case':'native-probe','command':'probe','facts':base,'binary_kind':'test','control':None,
                  'required_probe':True})
    cases.append({'case':'lba0-read-failure','command':'verify','facts':base,'control':'target-read-error:0',
                  'lba0_read_failure':True,'expected_failure':1,'failure_text':'TAPE_ERR_IO'})
    for seconds,extra,wording in ((60,1,'1 s for a 1-minute'),(1,2646000,'1 min for a 1-second'),
                                  (1,2646001,'1 min 1 s for a 1-second')):
        cases.append({'case':'native-capacity-'+str(seconds)+'-'+str(extra),'command':'load','facts':base,
                      'label_seconds':seconds,'source_frames':seconds*44100+extra,'expected_failure':2,
                      'failure_text':'Too long by '+wording+' cartridge','control':None})
    for name in sorted(p.name for p in (Path(__file__).parent.parent/'golden/ref').glob('*.wav'))+['c60.wav']:
        cases.append({'case':'native-roundtrip-'+name,'command':'load','facts':base,'roundtrip':True,
                      'source_name':name,'control':None})
    for case in cases:
        case.update(platform=platform,backing=str(backing),target_bytes=64_000_000_000)
        case.setdefault('erase_matches',True)
        if case['case']=='ceiling-equality': case['target_bytes']=1<<37
        if case.get('geometry_too_small'):
            case['target_bytes']=(P2_START+6144)*512
            case['facts']=dict(base,bytes=case['target_bytes'])
            case['label_seconds']=9
        case.setdefault('binary_kind','test')
    return [c for c in cases if platform=='linux' or c['case']!='production-loop-refusal']

def prepare(request,root):
    if request.get('fixture') or 'mbr_corruption' in request or request.get('zero_table'):
        fixture=root/(request['case']+'.img'); build(fixture,request.get('fixture','clean'),whole=True)
        request['backing']=str(fixture); request['target_bytes']=fixture.stat().st_size
        if 'mbr_corruption' in request or request.get('zero_table'):
            with fixture.open('r+b') as f:
                data=bytearray(f.read(512))
                if request.get('zero_table'):
                    data=bytearray(512)
                    if request['signed']: data[510:512]=b'\x55\xaa'
                else: data[request['mbr_corruption']]^=1
                f.seek(0); f.write(data)
            if request.get('zero_table') and not request['signed']:
                request.update(expected_failure=2,failure_text='NOT_PROVISIONED')
            else:
                request['expected_layout']=layout_findings(data,fixture.stat().st_size//512)
                request['safe_view']=safe_view(data,fixture.stat().st_size//512)
        if request['facts']: request['facts']=dict(request['facts'],bytes=fixture.stat().st_size)
        if request.get('required_replay'):
            from fixtures import synthetic_fat
            fat=root/'baseline-fat.img'; synthetic_fat(fat)
            with fat.open('rb') as source,fixture.open('r+b') as target:
                source.seek(2048*512); target.seek(2048*512)
                target.write(source.read(32768*512))
            request['baseline_sha256']=digest(fixture)
    if request.get('roundtrip'):
        from runner import make_c60
        source=Path(__file__).parent.parent/'golden/ref'/request['source_name']
        if request['source_name']=='c60.wav':
            source=root/'c60.wav'
            if not source.exists(): make_c60(source)
        request['source']=str(source); request['source_sha256']=digest(source)
    elif request.get('source_frames'):
        from runner import make_wav
        source=root/(request['case']+'.wav'); make_wav(source,request['source_frames'])
        request['source']=str(source); request['source_sha256']=digest(source)
    return request

def execute(transport,request,head_sha,evidence_dir):
    request['head_sha']=head_sha; request['evidence_dir']=str(evidence_dir)
    req=evidence_dir/(request['case']+'-request.json'); out=evidence_dir/(request['case']+'-response.json')
    request['request_sha256']=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
    req.write_text(json.dumps(request,indent=2)+'\n')
    if out.exists(): out.unlink()
    subprocess.run([*transport,str(req),str(out)],check=True,timeout=1800)
    response=json.loads(out.read_text()); capture_identity(request,response)
    assert response['head_sha']==head_sha
    assert response['binary_sha256']==digest(response['binary_path'])
    for artifact in response['capture_artifacts']:
        assert artifact['sha256']==digest(artifact['path']), 'raw capture hash mismatch'
    if request['command']=='symbols':
        assert isinstance(response['symbols'],str)
        assert response['symbol_tool_exit']==0
        if request['binary_kind']=='test':
            data=Path(response['binary_path']).read_bytes()
            assert all(name.encode() in data for name in SEAM_STRINGS)
            assert all(re.search(r'\b_?'+name+r'\b',response['symbols']) for name in SEAM_SYMBOLS)
    else:
        trace=response['trace']
        assert trace['platform']==request['platform'] and trace['operation']==request['command']
        assert trace['target_bytes']==request['target_bytes']
        assert trace['target_kind']=='device', 'image invocation substituted for native device'
        if request.get('expect_oracle_reject'):
            assert response['exit']==0 and trace['success'], 'unrelated control process failure'
            if request.get('required_null'):
                assert any(e['kind']=='engine_bind' for e in trace['events']), 'missing mutant binding observation'
            if request.get('required_native_flush') or request.get('required_provision_order'):
                assert any(e['kind']=='write' for e in trace['events'])
                assert any(e['kind']=='flush' for e in trace['events']), 'missing mutant callback observation'
    try:
        if request['command']=='symbols': symbol_absent(response['binary_path'],response['symbols'])
        else: audit_response(request,response)
    except AssertionError:
        if not request.get('expect_oracle_reject'): raise
        verdict='control-killed'
    else:
        assert not request.get('expect_oracle_reject'),'candidate control survived '+request['case']
        verdict='observations-pass'
    return {'case':request['case'],'verdict':verdict,'request':request,'response':response}

def run(transport,platform,head_sha,evidence_dir):
    results=[]
    assert re.fullmatch('[0-9a-f]{40}',head_sha)
    evidence_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='wp14-native-') as temp:
        root=Path(temp); backing=root/'backing.img'
        # Transport provisions its 64GB sparse target from this seed and binds its
        # actual native port. The verifier-owned seed contains referenced audio.
        build(backing,whole=True)
        for request in requests(platform,backing):
            prepare(request,root)
            result=execute(transport,request,head_sha,evidence_dir); results.append(result)
            if request.get('required_replay'):
                from provision_replay import replay_cuts
                response=result['response']; baseline=Path(response['baseline']).read_bytes()
                assert digest(response['baseline'])==request['baseline_sha256']
                new_mbr=mbr(request['target_bytes']//512,bytes.fromhex(request['new_uuid']))
                rows=replay_cuts(response['trace'],baseline,new_mbr)
                assert rows[-1]['sha256']==digest(response['final_snapshot'])
                for row in rows:
                    snapshot=evidence_dir/(row['case']+'-snapshot.img'); snapshot.write_bytes(row['snapshot'])
                    if row['outcome']=='new': fat16_readme(snapshot,'NEW',request['new_epoch'])
                    child={'case':'replay-'+row['case'],'platform':platform,'command':'verify','backing':str(snapshot),
                           'facts':dict(request['facts']),'target_bytes':request['target_bytes'],
                           'binary_kind':'test','control':None,'snapshot_sha256':row['sha256']}
                    if row['outcome']=='unprovisioned': child.update(expected_failure=2,failure_text='NOT_PROVISIONED')
                    else: child['required_null']=True
                    results.append(execute(transport,child,head_sha,evidence_dir))
                del rows
    assert len({x['response']['os_build'] for x in results})==1
    return {'kind':'native-candidate-cases','platform':platform,'head_sha':head_sha,
            'os_build':results[0]['response']['os_build'],'results':results,'accepted':False}

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--platform',required=True,choices=['linux','macos','windows'])
    ap.add_argument('--head',required=True); ap.add_argument('--evidence-dir',required=True,type=Path)
    ap.add_argument('transport',nargs='+'); args=ap.parse_args()
    print(json.dumps(run(args.transport,args.platform,args.head,args.evidence_dir.resolve()),indent=2))
