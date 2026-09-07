#!/usr/bin/env python3
"""Run independently assigned expectations against a separately linked public-API probe."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from cases import cases, authenticate, SEED

ROOT=Path(__file__).resolve().parent

def check(c, o):
    errors=[]
    def require(condition,message):
        if not condition: errors.append(message)
    require(o['init']==0,'tape_init failed')
    require(o['result'] in c.allowed,f"result {o['result']} not in {c.allowed}")
    ev=o['events'];traffic=[e for e in ev if e['op'] in ('read','write','flush')]
    for op,key in [('read','reads'),('write','writes'),('flush','flushes')]:
        require(sum(e['op']==op for e in traffic)==o[key],key+' disagrees with trace')
    require(o['oob']==0,'out-of-range callback')
    require(o['chunk_reads']==0,'mount read chunk region')
    for e in traffic:
        if e['op']!='flush':
            require(e['count']>0 and 0<=e['lba'] and e['lba']+e['count']<=c.blocks,'invalid callback range')
            # A mirror at/above the store is metadata, not a chunk read.
            if e['op']=='read':
                lo=max(2048,e['lba']);hi=min(c.blocks-1,e['lba']+e['count'])
                require(hi<=lo,'trace contains a chunk read')
    if c.phase0:require(not traffic,'phase 0 issued callbacks')
    else:
        for lba in (0,c.blocks-1):
            require(any(e['op']=='read' and e['lba']<=lba<e['lba']+e['count'] for e in traffic),
                    f'phase 1 did not read superblock {lba}')
    writable=c.expected().get('writable',0)
    repair=(c.allowed==(0,) and c.repair is not None and writable)
    writes=[e for e in ev if e['op']=='write']
    data=[e for e in ev if e['op']=='write_bytes']
    expected_supers=[s.hex() for s in c.supers]
    if not repair:
        require(not writes and o['flushes']==0,'forbidden write/flush')
    else:
        target=0 if c.repair==0 else c.blocks-1
        require(len(writes)==1,'repair must rewrite only one 512-byte partner')
        require(len(data)==1 and data[0]['hex']==c.supers[c.selected].hex(),'repair bytes differ from selected candidate')
        if writes:
            require(writes[0]['lba']==target and writes[0]['count']==1,'wrong repair destination/extent')
            require(writes[0]['rc']==int(bool(c.fail_write)),'write failure injection not observed')
            at=ev.index(writes[0]);prior=ev[:at]
            for lba in (0,c.blocks-1,8,136,264,392):
                require(any(e['op']=='read' and e['lba']<=lba<e['lba']+e['count'] for e in prior),
                        f'repair preceded required metadata read {lba}')
        if not c.fail_write:
            expected_supers[c.repair]=c.supers[c.selected].hex()
            flush=[e for e in ev if e['op']=='flush']
            require(len(flush)==1,'successful repair write must be flushed exactly once')
            if flush:
                require(flush[0]['rc']==int(bool(c.fail_flush)),'flush failure injection not observed')
                require(bool(writes) and ev.index(flush[0])>ev.index(writes[0]),'repair flush before write')
    require(o['superblocks']==expected_supers,'unexpected superblock mutation')
    if c.allowed==(0,):
        require(o['info_result']==0 and o['tell_result']==0,'successful mount not queryable')
        for k,v in c.expected().items():require(o['info'][k]==v,f"info.{k}: {o['info'][k]} != {v}")
        require(o['position']==min(c.resume,c.expected()['total_frames']),'resume not clamped')
    return errors

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--adapter',type=Path);p.add_argument('--log',type=Path)
    p.add_argument('--list',action='store_true');p.add_argument('--case');p.add_argument('--timeout',type=int,default=30)
    a=p.parse_args(argv);authenticate(ROOT/'spec');cc=cases()
    if a.case:cc=[c for c in cc if c.id==a.case]
    if not cc:p.error('no matching cases')
    if a.list:
        for c in cc:print(c.id+'\t'+c.section)
        print(f'{len(cc)} cases; seed={SEED:#x}; candidate-only');return 0
    if not a.adapter:p.error('--adapter is required; no engine acceptance can run without it')
    adapter=a.adapter.resolve()
    if not adapter.is_file():p.error('adapter executable does not exist')
    if not a.log:p.error('--log is required so failures and observations are preserved')
    a.log.parent.mkdir(parents=True,exist_ok=True)
    failures=0
    with a.log.open('w') as log,tempfile.TemporaryDirectory(prefix='tape-mount-') as temp:
        log.write(json.dumps(dict(kind='provenance',adapter=str(adapter),adapter_sha256=hashlib.sha256(adapter.read_bytes()).hexdigest(),
                                  seed=SEED,candidate=True,cases=len(cc)))+'\n')
        for c in cc:
            f=Path(temp)/'fixture.bin';payload=c.encode();f.write_bytes(payload)
            rec=dict(id=c.id,fixture_sha256=hashlib.sha256(payload).hexdigest(),allowed=c.allowed)
            try:
                r=subprocess.run([str(adapter),str(f)],capture_output=True,text=True,timeout=a.timeout)
                rec.update(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
                if r.returncode:errs=['adapter process failed']
                else:
                    obs=json.loads(r.stdout);errs=check(c,obs)
            except (OSError,subprocess.TimeoutExpired,ValueError,KeyError,TypeError) as e:
                rec['exception']=str(e);errs=['missing/malformed observation or adapter timeout/failure']
            rec['errors']=errs;rec['status']='FAIL' if errs else 'PASS';log.write(json.dumps(rec)+'\n');log.flush()
            if errs:failures+=1;print(c.id+': FAIL: '+'; '.join(errs[:3]))
    print(f'{len(cc)} cases; {failures} failed; seed={SEED:#x}; see {a.log}')
    return 1 if failures else 0
if __name__=='__main__':sys.exit(main())
