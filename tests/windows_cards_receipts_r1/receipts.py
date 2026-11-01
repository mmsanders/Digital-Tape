"""352 cards-1 first-party consistency oracle. ZERO Product/process/native execution."""
import copy,hashlib,importlib.util,json,os,re
from pathlib import Path,PureWindowsPath
TESTS=Path(os.environ.get('VERIFICATION_TESTS',Path(__file__).resolve().parent.parent))
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
legacy=load('cards_legacy_diagnostics',TESTS/'windows_diagnostics_r2/receipts.py')
discovery=load('cards_accepted_discovery',TESTS/'windows_discovery_r1/contract.py')
LIMIT=16777216; BLOB=4194304; LINE=65536
FIELDS={
 'cards-contract':{'cards_schema'},
 'cards-admit':{'run_id','ticket','job_dir','job_error'},
 'cards-admission-refused':{'run_id','ticket','reason'},
 'cards-launch':{'run_id','ticket','pid','os_start_ns','spawn_call_ns','exe','exe_sha256_observed','pin_sha256','pin_version_label','argv','cwd','report_path','nonce','creation_flags','env_sha256'},
 'cards-not-launched':{'run_id','ticket','reason','pin_sha256','pin_version_label'},
 'cards-invalidate':{'run_id','ticket','reason','changed'},
 'cards-terminal':{'run_id','ticket','pid','exit','end','wait_kind','end_ns','timeout_ms'},
 'cards-publication-attempt':{'run_id','ticket','state_ref','intent'},
 'cards-publication':{'run_id','ticket','state_ref','result','error'},
 'cards-blob':{'run_id','ticket','pid','role','leaf','bytes','original_bytes','status','sha256'},
 'cards-missing':{'run_id','ticket','role','reason'},
 'cards-cleanup':{'run_id','ticket','job_dir','attempted','result','error'}
}
def num(x):assert type(x) is int and 0<=x<2**64
def hx(x,n):assert isinstance(x,str) and re.fullmatch('[0-9a-f]{'+str(n)+'}',x)
def sha(b):return hashlib.sha256(b).hexdigest()
def obj(pairs):
    d={}
    for k,v in pairs:assert k not in d;d[k]=v
    return d
def parse(b):return json.loads(b,object_pairs_hook=obj)
def encode(rows):return b''.join((json.dumps(r,separators=(',',':'))+'\n').encode() for r in rows)
def inside(path,root):
    assert isinstance(path,str) and path and '\0' not in path and '..' not in path.replace('\\','/').split('/')
    assert PureWindowsPath(path).is_absolute() and PureWindowsPath(root) in PureWindowsPath(path).parents
def validate(files,binding,expect_complete=True):
    """Authenticity/actual seam provenance is reviewed separately against originals/source."""
    assert set(files)>={'.digital-tape-diagnostic-session','records.jsonl'}
    assert sum(map(len,files.values()))<=LIMIT
    for name in files:assert name in ['.digital-tape-diagnostic-session','records.jsonl'] or re.fullmatch(r'blobs/[0-9]{8}-(report|stdout|stderr|manifest)\.bin',name)
    raw=files['records.jsonl'];assert raw.endswith(b'\n') and all(len(x)<=LINE for x in raw.splitlines(keepends=True))
    rows=[parse(x) for x in raw.splitlines()];assert len(rows)>=2
    sid=rows[0]['session'];hx(sid,32)
    assert parse(files['.digital-tape-diagnostic-session'])==dict(schema=1,session=sid)
    assert rows[0]['kind']=='session' and rows[1]['kind']=='cards-contract'
    head=rows[0]['data'];assert head['app_path']==binding['app_path'] and head['app_sha256']==binding['app_sha256']
    assert head['pins']['DT_TAPECTL_SHA256']==binding['sha256'] and head['pins']['DT_TAPECTL_VERSION']==binding['version_label']
    assert PureWindowsPath(binding['exe']).parent==PureWindowsPath(binding['app_path']).parent
    runs={};last_ticket=-1;last_run=0;used_nonces=set();used_reports=set();cards_leaves=set();ended=False;flaw=False;shut=False
    for i,r in enumerate(rows):
        assert set(r)=={'schema','session','seq','kind','data'} and type(r['schema']) is int and r['schema']==1 and r['session']==sid and type(r['seq']) is int and r['seq']==i and not ended
        k,d=r['kind'],r['data']
        if k in ['session-end','incomplete']:ended=True
        if not k.startswith('cards-'):assert k in legacy.KINDS;continue
        assert k in FIELDS and set(d)==FIELDS[k]
        if k=='cards-contract':assert i==1 and type(d['cards_schema']) is int and d['cards_schema']==1;continue
        if k=='cards-admission-refused':
            assert d==dict(run_id=None,ticket=None,reason='stopped');shut=True;continue
        rid=d['run_id'];assert isinstance(rid,str) and re.fullmatch(r'cards-[1-9][0-9]*',rid)
        num(d['ticket'])
        if k=='cards-admit':
            assert not shut and rid not in runs and int(rid[6:])==last_run+1 and d['ticket']>last_ticket
            assert all(x.get('cleanup') for x in runs.values()) # single-flight includes terminal-owned cleanup
            last_ticket=d['ticket'];last_run+=1
            if d['job_dir'] is None:assert isinstance(d['job_error'],str) and d['job_error']
            else:inside(d['job_dir'],binding['private_root']);assert d['job_error'] is None
            runs[rid]={'admit':d,'roles':{},'files':{}};continue
        q=runs[rid];assert d['ticket']==q['admit']['ticket'] and not q.get('cleanup')
        if k=='cards-launch':
            assert 'launch' not in q and 'not-launched' not in q and q['admit']['job_dir']
            num(d['pid']);assert d['pid']>0
            if d['os_start_ns'] is None:flaw=True
            else:num(d['os_start_ns']);assert d['os_start_ns']>0
            num(d['spawn_call_ns']);assert d['spawn_call_ns']>0
            assert d['exe']==binding['exe'] and d['exe_sha256_observed']==d['pin_sha256']==binding['sha256']
            assert d['pin_version_label']==binding['version_label']
            hx(d['env_sha256'],64);hx(d['nonce'],32)
            assert d['nonce'] not in used_nonces and d['report_path'] not in used_reports
            used_nonces.add(d['nonce']);used_reports.add(d['report_path'])
            assert d['cwd']==q['admit']['job_dir'];inside(d['report_path'],d['cwd']+'\\control')
            assert len(d['argv'])==6 and d['argv'][:2]==[d['exe'],'cards']
            for flag,val in [('--report',d['report_path']),('--report-nonce',d['nonce'])]:assert d['argv'].count(flag)==1 and d['argv'][d['argv'].index(flag)+1]==val
            flags=d['creation_flags'];num(flags);assert flags&0x08000000 and flags&(0x10|0x8)==0
            q['launch']=d
        elif k=='cards-not-launched':
            assert 'launch' not in q and 'not-launched' not in q and d['reason']
            assert d['pin_sha256']==binding['sha256'] and d['pin_version_label']==binding['version_label'];q['not-launched']=d
        elif k=='cards-invalidate':
            assert 'launch' in q and 'terminal' not in q and not q.get('invalidated')
            assert d['reason']=='timeout' and type(d['changed']) is bool;q['invalidated']=True
        elif k=='cards-terminal':
            a=q['launch'];assert 'terminal' not in q and d['pid']==a['pid'] and d['timeout_ms']==10000
            assert d['end'] in ['exited','timed_out','cancelled'] and d['wait_kind'] in ['wait','try_wait-terminal']
            num(d['end_ns']);assert d['end_ns']>=a['spawn_call_ns']
            assert d['exit'] is None or type(d['exit']) is int
            if d['end']!='exited':flaw=True
            if d['end']=='timed_out':assert q.get('invalidated')
            q['terminal']=d
        elif k=='cards-publication-attempt':
            assert ('terminal' in q or 'not-launched' in q) and 'attempt' not in q
            assert d['intent'] in ['publish','stale-drop'] and d['state_ref'];q['attempt']=d
        elif k=='cards-publication':
            assert 'attempt' in q and 'publication' not in q and d['state_ref']==q['attempt']['state_ref']
            if d['result']=='failed':assert isinstance(d['error'],str) and d['error'];flaw=True
            else:assert d['result']=={'publish':'published','stale-drop':'stale-dropped'}[q['attempt']['intent']] and d['error'] is None
            q['publication']=d
        elif k in ['cards-blob','cards-missing']:
            assert 'terminal' in q and 'publication' in q and d['role'] in ['report','stdout','stderr'] and d['role'] not in q['roles']
            role=d['role'];q['roles'][role]=d
            if k=='cards-missing':assert d['reason'];flaw=True;continue
            assert d['pid']==q['launch']['pid'] and re.fullmatch(r'blobs/[0-9]{8}-'+role+r'\.bin',d['leaf'])
            assert d['leaf'] not in cards_leaves;cards_leaves.add(d['leaf'])
            b=files[d['leaf']];num(d['bytes']);num(d['original_bytes']);assert len(b)==d['bytes']<=BLOB and sha(b)==d['sha256']
            assert d['status'] in ['complete','truncated']
            if d['status']=='complete':assert d['original_bytes']==len(b)
            else:assert d['original_bytes']>len(b);flaw=True
            q['files'][role]=b
        elif k=='cards-cleanup':
            assert 'publication' in q and d['job_dir']==q['admit']['job_dir'] and type(d['attempted']) is bool
            if 'launch' in q:
                assert 'terminal' in q
                if set(q['roles'])!={'report','stdout','stderr'}:flaw=True
            else:assert 'not-launched' in q and not q['roles']
            if d['job_dir'] is None:assert not d['attempted'] and d['result']=='not-created' and d['error'] is None
            else:
                assert d['attempted'] and d['result'] in ['removed','failed','missing']
                if d['result']!='removed':assert d['error'];flaw=True
                else:assert d['error'] is None
            q['cleanup']=d
    complete=rows[-1]['kind']=='session-end' and rows[-1]['data']['complete'] is True
    for q in runs.values():
        if 'launch' in q:
            if not q.get('terminal') or not q.get('publication') or not q.get('cleanup'):flaw=True;continue
            a,t=q['launch'],q['terminal']
            if set(q['files'])=={'report','stdout','stderr'} and all(x.get('status')=='complete' for x in q['roles'].values()) and type(t['exit']) is int:
                r=discovery.prior.parse(q['files']['report'],'tapectl cards',a['pin_version_label'],a['nonce'],t['exit'])
                if r is None:flaw=True
                if t['exit']==0:
                    try:discovery.stdout(q['files']['stdout'].decode('utf-8'))
                    except (AssertionError,ValueError,UnicodeError):flaw=True
            else:flaw=True
        elif not all(k in q for k in ['not-launched','publication','cleanup']):flaw=True
    if complete:assert not flaw
    assert complete is expect_complete
    # Legacy-only validation projection preserves every old data field. Original full seq/session
    # and all cards bytes were checked above. This projection is never substituted for originals.
    old=[copy.deepcopy(r) for r in rows if not r['kind'].startswith('cards-')]
    for i,r in enumerate(old):r['seq']=i
    assert not cards_leaves.intersection(r['data'].get('leaf') for r in old if r['kind']=='blob')
    projected={k:v for k,v in files.items() if k not in cards_leaves};projected['records.jsonl']=encode(old)
    legacy.validate(projected,expect_complete)
    return 'CARDS-1 FIRST-PARTY consistency ONLY; raw authenticity/source/native/G1 remain separate'

def fixture():
    old,files=legacy.fixture();head=copy.deepcopy(old[0]);head['data']['pins']['DT_TAPECTL_VERSION']='tapectl-wp15-s2+'+'b'*12
    binding=dict(app_path=head['data']['app_path'],app_sha256=head['data']['app_sha256'],exe='C:\\MODEL\\bundle\\tapectl.exe',sha256='a'*64,version_label=head['data']['pins']['DT_TAPECTL_VERSION'],private_root='C:\\MODEL\\appdata')
    head['data']['app_path']=binding['app_path']='C:\\MODEL\\bundle\\digital-tape.exe'
    rows=[head];files={'.digital-tape-diagnostic-session':files['.digital-tape-diagnostic-session']}
    def add(k,**d):rows.append(dict(schema=1,session=head['session'],seq=len(rows),kind=k,data=d))
    add('cards-contract',cards_schema=1)
    for i in range(2):
        rid='cards-'+str(i+1);ticket=i+1;job=binding['private_root']+'\\jobs\\'+rid;nonce=str(i+1)*32;pid=20+i
        common=dict(run_id=rid,ticket=ticket)
        add('cards-admit',**common,job_dir=job,job_error=None)
        report=job+'\\control\\cards-'+nonce+'.jsonl'
        add('cards-launch',**common,pid=pid,os_start_ns=2+i,spawn_call_ns=3+i,exe=binding['exe'],exe_sha256_observed=binding['sha256'],pin_sha256=binding['sha256'],pin_version_label=binding['version_label'],argv=[binding['exe'],'cards','--report',report,'--report-nonce',nonce],cwd=job,report_path=report,nonce=nonce,creation_flags=0x08000000,env_sha256='1'*64)
        add('cards-terminal',**common,pid=pid,exit=0,end='exited',wait_kind='try_wait-terminal',end_ns=9+i,timeout_ms=10000)
        add('cards-publication-attempt',**common,state_ref='SYNTHETIC-VIEW-'+rid,intent='publish')
        add('cards-publication',**common,state_ref='SYNTHETIC-VIEW-'+rid,result='published',error=None)
        for role,b in [('report',discovery.report(nonce=nonce,version=binding['version_label']).encode()),('stdout',discovery.output().encode()),('stderr',b'RAW\0\xff\r\n')]:
            leaf=f'blobs/{len(rows):08d}-{role}.bin';files[leaf]=b
            add('cards-blob',**common,pid=pid,role=role,leaf=leaf,bytes=len(b),original_bytes=len(b),status='complete',sha256=sha(b))
        add('cards-cleanup',**common,job_dir=job,attempted=True,result='removed',error=None)
    add('session-end',complete=True,reason=None);files['records.jsonl']=encode(rows)
    return rows,files,binding
