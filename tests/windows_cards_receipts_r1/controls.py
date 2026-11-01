"""Independent synthetic detecting controls. No Product inspection or execution."""
import copy,json
import receipts as c

positive=[];negative=[]
def base():return c.fixture()
def at(rows,kind,n=0):return [r['data'] for r in rows if r['kind']==kind][n]
def finish(rows,files):
    for i,r in enumerate(rows):r['seq']=i
    files['records.jsonl']=c.encode(rows)
def reject(name,mutate):
    rows,files,b=base();mutate(rows,files,b);finish(rows,files)
    try:c.validate(files,b)
    except (AssertionError,KeyError,ValueError,TypeError,IndexError):negative.append(name);return
    raise AssertionError('negative survived: '+name)
def accept(name,rows,files,b,complete=True):
    finish(rows,files);c.validate(files,b,complete);positive.append(name)
def partial(name,mutate):
    rows,files,b=base();mutate(rows,files,b);at(rows,'session-end').update(complete=False,reason='SYNTHETIC '+name)
    accept(name,rows,files,b,False)
def replace_blob(rows,files,role,raw):
    d=next(r['data'] for r in rows if r['kind']=='cards-blob' and r['data']['role']==role)
    files[d['leaf']]=raw;d.update(bytes=len(raw),original_bytes=len(raw),sha256=c.sha(raw))
def first_only(rows):return [r for r in rows if r['data'].get('run_id')!='cards-2']

def main():
    accept('two sequential real-shape synthetic runs; raw NUL/nonUTF8 stderr',*base())
    rows,files,b=base();old,oldfiles=c.legacy.fixture()
    old[0]=copy.deepcopy(rows[0]);mixed=[old[0],rows[1]]+old[1:-1]+rows[2:]
    files.update({k:v for k,v in oldfiles.items() if k.startswith('blobs/')})
    accept('mixed legacy INGEST and cards, original data unchanged',mixed,files,b)
    for field,value in [('exe','C:\\wrong.exe'),('exe_sha256_observed','0'*64),('pin_sha256','0'*64),('pin_version_label','observed-version'),('nonce',''),('cwd','C:\\foreign'),('report_path','C:\\foreign\\report'),('creation_flags',0x10),('os_start_ns',0),('env_sha256','bad')]:
        reject('launch '+field,lambda r,f,b,k=field,v=value:at(r,'cards-launch').update({k:v}))
    reject('missing nonce',lambda r,f,b:at(r,'cards-launch').pop('nonce'))
    reject('observed version lie',lambda r,f,b:at(r,'cards-launch').update(observed_version=b['version_label']))
    reject('foreign job root',lambda r,f,b:at(r,'cards-admit').update(job_dir='C:\\foreign'))
    reject('job parent traversal',lambda r,f,b:at(r,'cards-admit').update(job_dir=b['private_root']+'\\..\\outside'))
    reject('wrong argv nonce',lambda r,f,b:at(r,'cards-launch')['argv'].__setitem__(5,'9'*32))
    reject('wrong child argv',lambda r,f,b:at(r,'cards-launch')['argv'].__setitem__(0,'C:\\wrong.exe'))
    reject('reused nonce',lambda r,f,b:at(r,'cards-launch',1).update(nonce=at(r,'cards-launch')['nonce']))
    reject('reused report',lambda r,f,b:at(r,'cards-launch',1).update(report_path=at(r,'cards-launch')['report_path']))
    for kind in ['cards-terminal','cards-blob','cards-cleanup','cards-publication']:
        reject('wrong ticket '+kind,lambda r,f,b,k=kind:at(r,k).update(ticket=999))
    for kind in ['cards-terminal','cards-blob']:
        reject('wrong pid '+kind,lambda r,f,b,k=kind:at(r,k).update(pid=999))
    reject('unknown run',lambda r,f,b:at(r,'cards-terminal').update(run_id='cards-99'))
    reject('nonmonotonic ticket',lambda r,f,b:at(r,'cards-admit',1).update(ticket=1))
    reject('bool pid',lambda r,f,b:at(r,'cards-launch').update(pid=True))
    reject('terminal before spawn',lambda r,f,b:at(r,'cards-terminal').update(end_ns=1))
    reject('unobserved wait',lambda r,f,b:at(r,'cards-terminal').update(wait_kind='kill-request'))
    reject('different timeout',lambda r,f,b:at(r,'cards-terminal').update(timeout_ms=1))
    reject('publication ref disagreement',lambda r,f,b:at(r,'cards-publication').update(state_ref='WRONG'))
    reject('publication result disagreement',lambda r,f,b:at(r,'cards-publication').update(result='stale-dropped'))
    reject('missing publication attempt',lambda r,f,b:r.remove(next(x for x in r if x['kind']=='cards-publication-attempt')))
    reject('premature cleanup',lambda r,f,b:r.insert(4,r.pop(next(i for i,x in enumerate(r) if x['kind']=='cards-cleanup'))))
    reject('cleanup attempted false',lambda r,f,b:at(r,'cards-cleanup').update(attempted=False))
    reject('cleanup fabricated success',lambda r,f,b:at(r,'cards-cleanup').update(result='removed',error='failed'))
    reject('cleanup failed complete',lambda r,f,b:at(r,'cards-cleanup').update(result='failed',error='denied'))
    reject('publication failed complete',lambda r,f,b:at(r,'cards-publication').update(result='failed',error='poisoned'))
    reject('missing terminal',lambda r,f,b:r.remove(next(x for x in r if x['kind']=='cards-terminal')))
    reject('missing raw blob',lambda r,f,b:f.pop(at(r,'cards-blob')['leaf']))
    reject('wrong raw digest',lambda r,f,b:at(r,'cards-blob').update(sha256='0'*64))
    reject('overwritten shared blob',lambda r,f,b:at(r,'cards-blob',3).update(leaf=at(r,'cards-blob')['leaf']))
    reject('traversal leaf',lambda r,f,b:at(r,'cards-blob').update(leaf='../report'))
    reject('foreign file',lambda r,f,b:f.update({'foreign.txt':b'x'}))
    reject('blob length lie',lambda r,f,b:at(r,'cards-blob').update(bytes=0))
    reject('blob over4MiB',lambda r,f,b:replace_blob(r,f,'stderr',b'x'*(c.BLOB+1)))
    reject('session over16MiB',lambda r,f,b:f.update({f'blobs/{900+i:08d}-manifest.bin':b'x'*c.BLOB for i in range(4)}))
    reject('line over64KiB',lambda r,f,b:at(r,'cards-publication-attempt').update(state_ref='x'*c.LINE))
    reject('unknown schema',lambda r,f,b:r[1]['data'].update(cards_schema=2))
    reject('wrong session',lambda r,f,b:r[2].update(session='0'*32))
    reject('unknown kind',lambda r,f,b:r[3].update(kind='cards-fiction'))
    reject('malformed report',lambda r,f,b:replace_blob(r,f,'report',b'not-json\n'))
    reject('wrong report nonce',lambda r,f,b:replace_blob(r,f,'report',c.discovery.report(nonce='9'*32,version=b['version_label']).encode()))
    reject('wrong report version',lambda r,f,b:replace_blob(r,f,'report',c.discovery.report(nonce='1'*32,version='wrong').encode()))
    reject('report exit mismatch',lambda r,f,b:replace_blob(r,f,'report',c.discovery.report(exit=1,nonce='1'*32,version=b['version_label']).encode()))
    reject('stdout count mismatch',lambda r,f,b:replace_blob(r,f,'stdout',b'cards-summary offered=1 unprobed=0\n'))
    reject('malformed stdout',lambda r,f,b:replace_blob(r,f,'stdout',b'\xff'))
    reject('no terminal exit complete',lambda r,f,b:at(r,'cards-terminal').update(exit=None))
    reject('shutdown late admission',lambda r,f,b:r.insert(next(i for i,x in enumerate(r) if x['kind']=='cards-admit' and x['data']['run_id']=='cards-2'),dict(schema=1,session=r[0]['session'],seq=12,kind='cards-admission-refused',data=dict(run_id=None,ticket=None,reason='stopped'))))
    partial('truthful publication failure',lambda r,f,b:at(r,'cards-publication').update(result='failed',error='actual failure'))
    partial('truthful cleanup failure',lambda r,f,b:at(r,'cards-cleanup').update(result='failed',error='actual failure'))
    partial('truthful malformed output retained',lambda r,f,b:replace_blob(r,f,'stdout',b'\xff'))
    partial('truthful report mismatch retained',lambda r,f,b:replace_blob(r,f,'report',c.discovery.report(nonce='9'*32,version=b['version_label']).encode()))
    partial('truthful missing creation time',lambda r,f,b:at(r,'cards-launch').update(os_start_ns=None))
    partial('truthful truncated blob',lambda r,f,b:at(r,'cards-blob').update(status='truncated',original_bytes=999999))
    def missing(r,f,b):
        x=next(x for x in r if x['kind']=='cards-blob');d=x['data'];f.pop(d['leaf']);x.update(kind='cards-missing',data=dict(run_id=d['run_id'],ticket=d['ticket'],role=d['role'],reason='actual read failure'))
    partial('truthful missing blob',missing)
    partial('truthful cancelled and reaped',lambda r,f,b:at(r,'cards-terminal').update(end='cancelled'))
    def timeout(r,f,b):
        at(r,'cards-terminal').update(end='timed_out');i=next(i for i,x in enumerate(r) if x['kind']=='cards-terminal');r.insert(i,dict(schema=1,session=r[0]['session'],seq=i,kind='cards-invalidate',data=dict(run_id='cards-1',ticket=1,reason='timeout',changed=True)))
    partial('truthful timeout invalidation and reap',timeout)
    for no_job in [False,True]:
        rows,files,b=base();rows=first_only(rows);launch=next(x for x in rows if x['kind']=='cards-launch');launch.update(kind='cards-not-launched',data=dict(run_id='cards-1',ticket=1,reason='actual spawn or job failure',pin_sha256=b['sha256'],pin_version_label=b['version_label']))
        rows=[r for r in rows if r['kind'] not in ['cards-terminal','cards-blob']]
        files={k:v for k,v in files.items() if not k.startswith('blobs/')}
        if no_job:at(rows,'cards-admit').update(job_dir=None,job_error='actual create failure');at(rows,'cards-cleanup').update(job_dir=None,attempted=False,result='not-created')
        accept('no invented PID on '+('job failure' if no_job else 'spawn failure'),rows,files,b)
    rows,files,b=base();at(rows,'cards-publication-attempt').update(intent='stale-drop');at(rows,'cards-publication').update(result='stale-dropped');accept('truthful stale drop',rows,files,b)
    rows,files,b=base();rows=rows[:4]+[dict(schema=1,session=rows[0]['session'],seq=4,kind='incomplete',data=dict(reason='session-limit'))];accept('sink failure prefix retained incomplete',rows,files,b,False)
    # Envelope byte controls bypass finish() deliberately.
    for name,change in [('sequence gap',lambda z:z.replace(b'"seq":2',b'"seq":99',1)),('duplicate key',lambda z:z.replace(b'"seq":2',b'"seq":2,"seq":2',1)),('partial final line',lambda z:z[:-1])]:
        rows,f,b=base();f['records.jsonl']=change(f['records.jsonl'])
        try:c.validate(f,b)
        except (AssertionError,ValueError):negative.append(name);continue
        raise AssertionError(name)
    print(json.dumps(dict(scope='SYNTHETIC FIRST-PARTY CONTROLS ONLY',positive=len(positive),negative=len(negative),positive_cases=positive,negative_cases=negative,product_executions=0),indent=2))
if __name__=='__main__':main()
