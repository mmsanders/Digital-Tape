"""332 closed first-party receipt predicates. No Product, UI or process execution."""
import argparse,base64,copy,hashlib,json,re
from pathlib import Path
SESSION_LIMIT=16777216
LINE_LIMIT=65536
BLOB_LIMIT=4194304
KINDS={
 'session':{'app_path','app_sha256','source_commit','os','os_build','arch','app_pid','app_os_start_ns','pins','control_scope','opt_in'},
 'ingress':{'drop_id','route','paths','generation'},
 'drop':{'drop_id','decision','reason','next','generation','work_id'},
 'reset':{'old_generation','new_generation'},
 'cancel-request':{'work_id','generation'},
 'work-skipped':{'work_id','generation','reason'},
 'job-admit':{'work_id','generation','drop_id','job_dir'},
 'child-launch':{'work_id','generation','pid','os_start_ns','spawn_call_ns','exe','exe_sha256','version','argv','cwd','report_path','dest','nonce','creation_flags','env_sha256'},
 'child-not-launched':{'work_id','generation','reason'},
 'child-terminal':{'work_id','generation','pid','exit','cancelled','wait_kind','end_ns'},
 'blob':{'work_id','generation','pid','role','leaf','bytes','sha256'},
 'missing':{'work_id','generation','role','reason'},
 'audio':{'work_id','generation','pid','sha256','bytes','total_frames'},
 'outcome':{'work_id','generation','disposition','state_ref'},
 'cleanup':{'work_id','generation','job_dir','result','error'},
 'incomplete':{'reason'},
 'session-end':{'complete','reason'}
}
def sha(b):return hashlib.sha256(b).hexdigest()
def hx(x,n):assert isinstance(x,str) and re.fullmatch('[0-9a-f]{'+str(n)+'}',x)
def number(x):assert type(x) is int and 0<=x<2**53
def opt_in(argv):return len(argv)==2 and argv[1]=='--diagnostic-receipts'
def encode(rows):return b''.join((json.dumps(r,separators=(',',':'),ensure_ascii=False)+'\n').encode() for r in rows)
def unpack(files):return {k:base64.b64decode(v,validate=True) for k,v in files.items()}
def validate(files,expect_complete=True):
    """Only transcript consistency. Raw authenticity and production linkage need independent review."""
    assert set(files)>={'.digital-tape-diagnostic-session','records.jsonl'}
    for name in files:
        assert name in ['.digital-tape-diagnostic-session','records.jsonl'] or re.fullmatch(r'blobs/[0-9]{8}-(report|stdout|stderr|manifest)\.bin',name)
    assert sum(map(len,files.values()))<=SESSION_LIMIT
    raw=files['records.jsonl'];assert raw.endswith(b'\n')
    lines=raw.splitlines(keepends=True);assert lines and all(len(x)<=LINE_LIMIT for x in lines)
    rows=[json.loads(x) for x in lines]
    sid=rows[0]['session'];hx(sid,32)
    marker=json.loads(files['.digital-tape-diagnostic-session']);assert marker==dict(schema=1,session=sid)
    ingress={};drops={};jobs={};launches={};terminal={};roles={};cleaned=set();skipped=set();outcomes=set();ended=False;incomplete=False;last_reset=-1
    for i,r in enumerate(rows):
        assert set(r)=={'schema','session','seq','kind','data'} and r['schema']==1 and r['session']==sid and type(r['seq']) is int and r['seq']==i
        assert not ended and r['kind'] in KINDS
        k,d=r['kind'],r['data'];assert set(d)==KINDS[k]
        if i==0:
            assert k=='session' and d['app_path'];hx(d['app_sha256'],64)
            assert d['source_commit'] is None or re.fullmatch('[0-9a-f]{40}',d['source_commit'])
            assert d['os'] and d['arch'] and type(d['app_pid']) is int and d['app_pid']>0
            assert d['control_scope']=='app-private/control' and d['opt_in']=='--diagnostic-receipts'
            assert set(d['pins'])=={'DT_INGEST_SHA256','DT_INGEST_VERSION','DT_TAPECTL_SHA256','DT_TAPECTL_VERSION'}
            for name,value in d['pins'].items():
                if name.endswith('SHA256'):hx(value,64)
                else:assert isinstance(value,str) and value
        else:assert k!='session'
        if 'work_id' in d and d['work_id'] is not None:
            assert re.fullmatch('ingest-[0-9a-f]{32}',d['work_id']);number(d['generation'])
            assert d['work_id'] not in cleaned
        if k=='ingress':
            assert d['drop_id'] not in ingress and d['route'] in ['native-event','tauri-command','controlled-test']
            assert isinstance(d['paths'],list) and all(isinstance(p,str) for p in d['paths']);number(d['generation']);ingress[d['drop_id']]=d
        elif k=='drop':
            assert d['drop_id'] in ingress and d['drop_id'] not in drops and d['generation']>=ingress[d['drop_id']]['generation']
            assert d['decision'] in ['reject','no-change','schedule']
            if d['decision']=='schedule':assert d['next']=='RunIngest' and re.fullmatch('ingest-[0-9a-f]{32}',d['work_id'])
            else:assert d['next']!='RunIngest' and d['work_id'] is None
            drops[d['drop_id']]=d
        elif k=='reset':
            number(d['old_generation']);number(d['new_generation']);assert d['new_generation']>d['old_generation'] and d['new_generation']>last_reset;last_reset=d['new_generation']
        elif k=='work-skipped':
            assert d['reason']=='cancelled-before-admission' and d['work_id'] not in jobs
            assert any(x['work_id']==d['work_id'] and x['generation']==d['generation'] for x in drops.values())
            skipped.add(d['work_id'])
        elif k=='cancel-request':
            assert any(x['work_id']==d['work_id'] and x['generation']==d['generation'] for x in drops.values())
        elif k=='job-admit':
            assert d['work_id'] not in jobs and d['drop_id'] in drops
            a=drops[d['drop_id']];assert a['decision']=='schedule' and a['work_id']==d['work_id'] and a['generation']==d['generation']
            assert d['job_dir'];jobs[d['work_id']]=d
        elif k in ['child-launch','child-not-launched']:
            w=d['work_id'];assert w in jobs and jobs[w]['generation']==d['generation'] and w not in launches
            if k=='child-launch':
                assert type(d['pid']) is int and d['pid']>0 and d['spawn_call_ns']>0
                if d['os_start_ns'] is None:incomplete=True
                else:number(d['os_start_ns']);assert d['os_start_ns']>0
                hx(d['exe_sha256'],64);hx(d['env_sha256'],64);hx(d['nonce'],32)
                flags=d['creation_flags'];assert type(flags) is int
                if rows[0]['data']['os']=='windows':assert flags&0x08000000 and flags&(0x10|0x8)==0
                assert d['cwd']==jobs[w]['job_dir'] and d['argv'][0]==d['exe'] and d['version']
                argv=d['argv'];assert len(argv)>=10 and argv[1:9]==['--report',d['report_path'],'--report-nonce',d['nonce'],'--out',d['dest'],'--length','3600'] and argv[9]=='--'
                assert argv[10:]==ingress[jobs[w]['drop_id']]['paths']
            else:assert d['reason']
            launches[w]=d;roles[w]=set()
        elif k=='child-terminal':
            w=d['work_id'];a=launches[w];assert 'pid' in a and d['pid']==a['pid'] and d['generation']==a['generation'] and w not in terminal
            assert d['wait_kind'] in ['wait','try_wait-terminal'] and type(d['cancelled']) is bool
            assert d['exit'] is None or type(d['exit']) is int
            assert d['end_ns']>=a['spawn_call_ns'];terminal[w]=d
        elif k in ['blob','audio','missing']:
            w=d['work_id'];assert w in terminal and d['generation']==launches[w]['generation']
            if k in ['blob','audio']:assert d['pid']==launches[w]['pid']
            if k=='blob':
                assert d['role'] in ['report','stdout','stderr','manifest'] and d['role'] not in roles[w]
                assert re.fullmatch(r'blobs/[0-9]{8}-'+d['role']+r'\.bin',d['leaf'])
                b=files[d['leaf']];assert len(b)==d['bytes']<=BLOB_LIMIT and sha(b)==d['sha256'];roles[w].add(d['role'])
                if d['role']=='report':
                    try:
                        parsed=[json.loads(line) for line in b.splitlines()]
                        assert parsed[0]['t']=='start' and parsed[0]['tool']=='ingest' and parsed[0]['nonce']==launches[w]['nonce'] and parsed[0]['version']==launches[w]['version']
                        assert parsed[-1]==dict(t='end',exit=terminal[w]['exit'])
                    except (ValueError,KeyError,IndexError,AssertionError):incomplete=True
            elif k=='audio':hx(d['sha256'],64);number(d['total_frames']);assert d['bytes']==44+4*d['total_frames'];roles[w].add('audio')
            else:assert d['role'] in ['report','stdout','stderr','manifest','audio'] and d['reason'];incomplete=True
        elif k=='outcome':
            w=d['work_id'];assert w in launches and (w in terminal or 'pid' not in launches[w])
            assert d['generation']==jobs[w]['generation'] and d['state_ref'] and d['disposition'] in ['delivered','stale-dropped','failed']
            if last_reset> d['generation']:assert d['disposition']=='stale-dropped'
            outcomes.add(w)
        elif k=='cleanup':
            w=d['work_id'];assert w in launches and (w in terminal or 'pid' not in launches[w])
            assert d['generation']==jobs[w]['generation'] and d['job_dir']==jobs[w]['job_dir']
            assert d['result'] in ['removed','failed','missing'];cleaned.add(w)
        elif k=='incomplete':assert d['reason'];incomplete=True;ended=True
        elif k=='session-end':
            assert type(d['complete']) is bool
            if d['complete']:
                assert not incomplete and set(jobs)==cleaned==outcomes and set(ingress)==set(drops)
                assert {x['work_id'] for x in drops.values() if x['decision']=='schedule'}==set(jobs)|skipped
                h=rows[0]['data'];assert h['source_commit'] and h['os_build'] and h['app_os_start_ns']
                for w,t in terminal.items():
                    if not t['cancelled']:
                        assert {'report','stdout','stderr'}<=roles[w]
                        if t['exit']==0:assert {'manifest','audio'}<=roles[w]
            else:assert d['reason'];incomplete=True
            ended=True
    complete=ended and rows[-1]['kind']=='session-end' and rows[-1]['data']['complete'] and not incomplete
    assert complete==expect_complete
    return 'FIRST-PARTY consistency only; no native/UI/whole-machine absence acceptance'
def fixture():
    sid='a'*32;w='ingest-'+'b'*32;n='c'*32;rows=[];files={}
    def add(k,**d):rows.append(dict(schema=1,session=sid,seq=len(rows),kind=k,data=d))
    add('session',app_path='SYNTHETIC/app.exe',app_sha256='d'*64,source_commit='e'*40,os='windows',os_build='SYNTHETIC',arch='x86_64',app_pid=10,app_os_start_ns=1,pins=dict(DT_INGEST_SHA256='f'*64,DT_INGEST_VERSION='probe1',DT_TAPECTL_SHA256='a'*64,DT_TAPECTL_VERSION='probe2'),control_scope='app-private/control',opt_in='--diagnostic-receipts')
    add('ingress',drop_id='drop1',route='controlled-test',paths=['fixture/Music'],generation=0)
    add('drop',drop_id='drop1',decision='schedule',reason=None,next='RunIngest',generation=0,work_id=w)
    add('job-admit',work_id=w,generation=0,drop_id='drop1',job_dir='owned/jobs/'+w)
    add('child-launch',work_id=w,generation=0,pid=11,os_start_ns=2,spawn_call_ns=2,exe='probe.exe',exe_sha256='f'*64,version='probe1',argv=['probe.exe','--report','owned/report','--report-nonce',n,'--out','owned/DEST','--length','3600','--','fixture/Music'],cwd='owned/jobs/'+w,report_path='owned/report',dest='owned/DEST',nonce=n,creation_flags=0x08000000,env_sha256='1'*64)
    add('child-terminal',work_id=w,generation=0,pid=11,exit=0,cancelled=False,wait_kind='try_wait-terminal',end_ns=3)
    for role,b in [('report',b'{"t":"start","tool":"ingest","version":"probe1","nonce":"'+n.encode()+b'"}\n{"t":"end","exit":0}\n'),('stdout',b'PROBE-OUT\0\xff\n'),('stderr',b'PROBE-ERR\r\n'),('manifest',b'{"total_frames":88200}\n')]:
        leaf=f'blobs/{len(rows):08d}-{role}.bin';files[leaf]=b;add('blob',work_id=w,generation=0,pid=11,role=role,leaf=leaf,bytes=len(b),sha256=sha(b))
    add('audio',work_id=w,generation=0,pid=11,sha256='2'*64,bytes=352844,total_frames=88200)
    add('outcome',work_id=w,generation=0,disposition='delivered',state_ref='SYNTHETIC-actual-view')
    add('cleanup',work_id=w,generation=0,job_dir='owned/jobs/'+w,result='removed',error=None)
    add('session-end',complete=True,reason=None)
    files['.digital-tape-diagnostic-session']=json.dumps(dict(schema=1,session=sid)).encode();files['records.jsonl']=encode(rows)
    return rows,files
def controls():
    rows,files=fixture();validate(files)
    changes=[('wrongPID',lambda r:r[5]['data'].update(pid=999)),('wrongNonce',lambda r:r[4]['data'].update(nonce='0'*32)),('wrongGeneration',lambda r:r[5]['data'].update(generation=8)),('lostFlag',lambda r:r[4]['data'].update(creation_flags=0)),('newConsole',lambda r:r[4]['data'].update(creation_flags=0x08000010)),('detached',lambda r:r[4]['data'].update(creation_flags=0x08000008)),('wrongArgv',lambda r:r[4]['data']['argv'].__setitem__(8,'60')),('wrongCwd',lambda r:r[4]['data'].update(cwd='foreign')),('wrongHash',lambda r:r[6]['data'].update(sha256='0'*64)),('wrongSource',lambda r:r[0]['data'].update(source_commit=None)),('missingOS',lambda r:r[0]['data'].update(os_build=None)),('wrongOrigin',lambda r:r[1]['data'].update(route='injected')),('unknownField',lambda r:r[0]['data'].update(fake=True)),('sequenceGap',lambda r:r[3].update(seq=99)),('wrongSession',lambda r:r[3].update(session='0'*32)),('wrongFrames',lambda r:r[10]['data'].update(total_frames=2)),('droppedWait',lambda r:r.pop(5)),('cleanupEarly',lambda r:r.insert(5,r.pop(12)))]
    for name,mutate in changes:
        r=copy.deepcopy(rows);f=copy.deepcopy(files);mutate(r)
        if name!='sequenceGap':
            for i,row in enumerate(r):row['seq']=i
        f['records.jsonl']=encode(r)
        try:validate(f)
        except (AssertionError,KeyError,TypeError,ValueError):continue
        raise AssertionError('receipt negative survived: '+name)
    for name,mutate in [('corruptBytes',lambda f:f.__setitem__('blobs/00000006-report.bin',b'corrupt')),('truncatedLine',lambda f:f.__setitem__('records.jsonl',f['records.jsonl'][:-1])),('unsafeLeaf',lambda f:f.__setitem__('../foreign',b'bad')),('audioCopied',lambda f:f.__setitem__('audio.wav',b'bad')),('fullSink',lambda f:f.__setitem__('blobs/99999999-stdout.bin',b'x'*SESSION_LIMIT)),('largeLine',lambda f:f.__setitem__('records.jsonl',b' '*LINE_LIMIT+f['records.jsonl']))]:
        f=copy.deepcopy(files);mutate(f)
        try:validate(f)
        except (AssertionError,KeyError,TypeError,ValueError):continue
        raise AssertionError('storage negative survived: '+name)
    partial=copy.deepcopy(rows[:6]);partial.append(dict(schema=1,session=rows[0]['session'],seq=6,kind='incomplete',data=dict(reason='write-failed')))
    f={k:v for k,v in files.items() if not k.startswith('blobs/')};f['records.jsonl']=encode(partial);validate(f,False)
    assert opt_in(['app','--diagnostic-receipts'])
    for argv in [['app'],['app','--diagnostic-receipts=x'],['app','--diagnostic-receipts','--diagnostic-receipts'],['app','--diagnostic-receipts','arbitrary-path']]:assert not opt_in(argv)
    # A malformed original remains retainable, never rewritten into an expected report.
    r,f=fixture();leaf=r[6]['data']['leaf'];f[leaf]=b'actual malformed report\xff'
    r[6]['data'].update(bytes=len(f[leaf]),sha256=sha(f[leaf]));r[-1]['data'].update(complete=False,reason='invalid-original-report');f['records.jsonl']=encode(r);validate(f,False)
    # Valid no-child outcomes must not be forced into fabricated process records.
    for decision in ['reject','no-change']:
        r,f=fixture();r=[r[0],r[1],r[2],r[-1]];r[2]['data'].update(decision=decision,reason='fixture-refusal',next='None',work_id=None)
        for i,row in enumerate(r):row['seq']=i
        f={k:v for k,v in f.items() if not k.startswith('blobs/')};f['records.jsonl']=encode(r);validate(f)
    r,f=fixture();w=r[3]['data']['work_id'];r=[r[0],r[1],r[2],dict(schema=1,session=r[0]['session'],seq=3,kind='work-skipped',data=dict(work_id=w,generation=0,reason='cancelled-before-admission')),r[-1]]
    for i,row in enumerate(r):row['seq']=i
    f={k:v for k,v in f.items() if not k.startswith('blobs/')};f['records.jsonl']=encode(r);validate(f)
    print('PASS24 causal receipt/storage negatives, 2 incomplete +3 no-child positives and5 opt-in controls; ZERO Product/process/UI execution')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path);p.add_argument('--incomplete',action='store_true');p.add_argument('--schema',action='store_true');a=p.parse_args()
    if a.schema:print(json.dumps(dict(schema=1,max_session_bytes=SESSION_LIMIT,max_jsonl_line_bytes=LINE_LIMIT,max_blob_bytes=BLOB_LIMIT,fields={k:sorted(v) for k,v in KINDS.items()}),indent=2))
    elif a.input:print(validate(unpack(json.loads(a.input.read_text(encoding='utf-8-sig'))['files']),not a.incomplete))
    else:controls()
