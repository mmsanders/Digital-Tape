#!/usr/bin/env python3
"""Once-only frozen harmless corpus plus separately labelled POSIX sensor observations."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT/'tests/budget_gate_r1'
sys.path.insert(0, str(PKG))
from cases import corpus
from oracle import check_actual
import controller as C

def put(p, obj):
    C.immutable(p, obj)

def inventory(root):
    return {p.relative_to(root).as_posix(): dict(bytes=p.stat().st_size, sha256=C.sha(p.read_bytes()))
            for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--source',required=True)
    a=ap.parse_args();a.out.mkdir(exist_ok=False)
    start_cpu=C.own_completed_cpu();start=time.monotonic_ns()
    sourcecopy=a.out/'source';sourcecopy.mkdir()
    for parent in (ROOT/'host/budget-controller', PKG):
        for p in parent.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                q=sourcecopy/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
    put(a.out/'SOURCE.json',dict(commit=a.source,files=inventory(sourcecopy),interpreter=sys.executable,
          interpreter_sha256=C.sha(Path(sys.executable).read_bytes()),python=sys.version,platform=platform.platform(),
          method='00dd03edde05deacfc4935f61018ca8de43b9b6e',method_tree='26ac65c74926f8b607f37412cc0ff026f231b76e',
          source_material_scope='copied task source plus all request/raw/temp/archive paths under this root'))
    outcomes=[];raw_count=0
    for case in corpus():
        # Identity fixed outside child controller; no retries, fresh owned output per case.
        name=case['name'];request=a.out/(name+'-request.json');put(request,case['request'])
        target=a.out/'cases'/name;target.parent.mkdir(exist_ok=True)
        argv=[sys.executable,'-B',str(ROOT/'host/budget-controller/controller.py'),
              '--request',str(request),'--request-sha',C.sha(request.read_bytes()),'--out',str(target),
              '--helper',str(PKG/'helper.py'),'--helper-sha',C.sha((PKG/'helper.py').read_bytes()),
              '--mode',case['helper_mode'],'--name',name]
        scan=C.census(a.out);used=C.own_completed_cpu()-start_cpu
        if used>7000000000000 or scan['allocated_bytes']+16*1024**2>512*1024**2:
            raise RuntimeError('focused task cap; preserve prefix, no next case')
        put(a.out/(name+'-PRE.json'),dict(argv=argv,parent=os.getpid(),start_ns=time.monotonic_ns(),
              source=a.source,request_sha256=C.sha(request.read_bytes()),snapshot=scan,cpu_ns=used))
        with (a.out/(name+'-stdout.bin')).open('xb') as stdout,(a.out/(name+'-stderr.bin')).open('xb') as stderr:
            proc=subprocess.Popen(argv,stdout=stdout,stderr=stderr)
            try:code=proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait();raise RuntimeError('controller timeout; no retry')
        put(a.out/(name+'-PROCESS.json'),dict(pid=proc.pid,parent=os.getpid(),exit=code,end_ns=time.monotonic_ns(),
              scope_cpu_ns=C.own_completed_cpu()-start_cpu))
        if code:raise RuntimeError('controller failed: '+name)
        row=json.loads((target/'RESULT.json').read_bytes());check_actual(row,case)
        assert row['gate']['request_sha256']==C.sha(request.read_bytes())
        assert row['gate']['pid']==proc.pid
        for filename,pin in row['raw'].items():
            b=(target/filename).read_bytes();assert C.sha(b)==pin['sha256'] and len(b)==pin['bytes']
        if case['expected']=='ALLOW':
            child=json.loads((target/'spy.jsonl').read_bytes().splitlines()[0]);launch=row['launches'][0]
            assert child['pid']==launch['pid'] and child['nonce']==case['request']['nonce']
            assert row['measurement']['child_cpu_ns']>=0
            assert b'\x00\xffretained\n' in (target/'stdout.bin').read_bytes()
            assert b'\x80diagnostic\n' in (target/'stderr.bin').read_bytes()
            raw_count+=1
        if case['helper_mode']!='ok':
            assert row['session_stopped'] and row['second_command_spy_unchanged']
            if case['helper_mode']=='incomplete':assert row['measurement']['accounting_complete'] is False
            elif case['helper_mode']=='timeout':assert row['measurement']['reason']=='timeout'
            else:assert row['measurement']['exit']==7
        outcomes.append(row)
    put(a.out/'CORPUS.json',outcomes)
    # Six rehashed evidence corruptions, externally compared with original bytes/request.
    first=next(x for x in outcomes if x['decision']=='ALLOW')
    rejected=next(x for x in outcomes if x['decision'].startswith('REJECT_PHASE'))
    checks=[]
    for label in ('launch-on-reject','stale-external-snapshot','changed-reservation',
                  'truncated-raw','missing-final-charge','phase-reclassified-allow'):
        row=copy.deepcopy(rejected if label in ('launch-on-reject','phase-reclassified-allow') else first)
        case=next(c for c in corpus() if c['name']==row['name'])
        if label=='launch-on-reject':row['launches']=[dict(pid=1,start_ns=2)]
        elif label=='stale-external-snapshot':row['request']['sequence']-=1
        elif label=='changed-reservation':row['request']['next_bytes']+=1
        elif label=='truncated-raw':row['raw']['stdout.bin']['sha256']=C.sha(b'')
        elif label=='missing-final-charge':row['measurement']['child_cpu_ns']=None
        else:row['decision']='ALLOW'
        data=(json.dumps(row,sort_keys=True)+'\n').encode();p=a.out/(label+'-mutation.json');p.write_bytes(data)
        detected=False
        try:
            check_actual(row,case)
            assert row['request']==case['request']
            assert row['measurement']['child_cpu_ns'] is not None
            original=a.out/'cases'/row['name']
            for filename,pin in row['raw'].items():assert C.sha((original/filename).read_bytes())==pin['sha256']
        except (AssertionError,KeyError,TypeError):detected=True
        assert detected,label
        checks.append(dict(name=label,sha256=C.sha(data),detected=True,external_original_name=row['name']))
    put(a.out/'MUTATIONS.json',checks)

    # Distinct REAL allocation observations: sparse, hardlink aliases, temporary and archive.
    sensor=a.out/'sensors';sensor.mkdir();snapshots=[]
    def snap(label):
        s=C.census(a.out);snapshots.append(dict(label=label,scan=s));return s
    snap('before')
    with (sensor/'sparse.bin').open('xb') as f:f.seek(1024*1024-1);f.write(b'\x01')
    (sensor/'original.raw').write_bytes(bytes(range(256))*32)
    os.link(sensor/'original.raw',sensor/'alias.raw')
    sparse=snap('sparse-and-hardlinks')
    (sensor/'temporary.bin').write_bytes(b'T'*16384)
    with zipfile.ZipFile(sensor/'retained.zip','x',compression=zipfile.ZIP_STORED) as z:
        z.write(sensor/'original.raw','original.raw')
    final=snap('temp-and-archive')
    rows=final['rows'];original=next(x for x in rows if x['path']=='sensors/original.raw')
    alias=next(x for x in rows if x['path']=='sensors/alias.raw')
    assert original['inode']==alias['inode'] and original['allocated']==alias['allocated'] and original['links']==2
    sparse_row=next(x for x in rows if x['path']=='sensors/sparse.bin')
    assert sparse_row['logical']==1048576 # allocated receipt separate, no filesystem savings premise
    session=C.Session('real-sensors');baseline=snapshots[0]['scan']['allocated_bytes']
    highs=[session.storage(x['scan']['allocated_bytes'],baseline) for x in snapshots]
    assert highs[-1][0]>=highs[0][0] and highs[-1][1]>=highs[0][1]
    # Deliberate failed scan after retained raw. No deletion/favourable replacement or child launch.
    try:C.census(sensor/'intentionally-missing-measurement-root')
    except FileNotFoundError as e:failure=str(e);session.stopped=True
    else:raise AssertionError('missing measurement root was admitted')
    # The actual failed measurement remains a terminal probe outcome, not a fabricated zero.
    retained_hash=C.sha((sensor/'original.raw').read_bytes())
    try:session.require_next()
    except RuntimeError:failure_next_refused=True
    else:failure_next_refused=False
    assert failure_next_refused
    put(a.out/'SENSORS.json',dict(snapshots=snapshots,highwater=highs,sparse=sparse_row,
         failed_scan=failure,terminal=True,next_refused=True,retained_original_sha256=retained_hash,
         failed_measurement_path='sensors/intentionally-missing-measurement-root'))
    # CPU includes actual parent+completed wait4 child charge; no injected thresholds here.
    cpu_before=C.own_completed_cpu();busy_start=time.process_time_ns()
    while time.process_time_ns()-busy_start<30000000:
        hashlib.sha256(b'harmless268').digest()
    cpu_after=C.own_completed_cpu();assert cpu_after>cpu_before
    put(a.out/'CPU-SENSOR.json',dict(before_ns=cpu_before,after_ns=cpu_after,increment_ns=cpu_after-cpu_before,
         process_time_interval_ns=time.process_time_ns()-busy_start,scope='parent plus reaped children once; direct helper live ticks separately'))
    summary=dict(cases=len(outcomes),actual_helper_calls=raw_count,mutations=len(checks),source=a.source,
          method='00dd03edde05deacfc4935f61018ca8de43b9b6e',cpu_ns=C.own_completed_cpu()-start_cpu,
          wall_ns=time.monotonic_ns()-start,build_supervision_reserve_ns=60000000000,
          allocated_highwater=max(s['scan']['allocated_bytes'] for s in snapshots),
          final_complete_namespace_scan=True,failed_probe_separate_from_task_census=True,
          hard_overshoot_guarantee=False,product_calls=0)
    put(a.out/'RESULT.json',summary)
    put(a.out/'FILES.json',inventory(a.out))
    archive=a.out.parent/'software525-exact-return.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(a.out.rglob('*')):
            if p.is_file() and not p.is_symlink():z.write(p,p.relative_to(a.out).as_posix())
    # Archive is charged as retained task material, not an assumed compression saving.
    post_cpu=C.own_completed_cpu()-start_cpu
    complete=C.census(a.out.parent)
    assert complete['allocated_bytes']+65536<=512*1024**2
    assert post_cpu+60000000000<=7200000000000
    put(a.out.parent/'software525-ARCHIVE.json',dict(bytes=archive.stat().st_size,sha256=C.sha(archive.read_bytes()),
        cpu_ns=post_cpu,final_allocated_bytes=complete['allocated_bytes'],final_namespace=complete,
        final_accounting_storage_reserve_bytes=65536,build_supervision_reserve_ns=60000000000,
        retained_source_and_case_bytes_not_deleted=True))
    print(json.dumps(summary))

if __name__=='__main__':main()
