"""Adapter-driven BE1 suite. Self-test tests the harness, never Product behavior."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from fixtures import catalog,materialize,references

HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()

def snapshot(root):
    return {p.relative_to(root).as_posix():sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}

def codes(report):
    if isinstance(report,dict):
        return set(report.get('reasons',[])) | set().union(*(codes(v) for k,v in report.items() if k!='reasons'))
    if isinstance(report,list):
        return set().union(*(codes(v) for v in report))
    return set()

def check(report,exitcode,expected):
    assert exitcode==expected['exit'], ('exit',exitcode,expected['exit'])
    assert report['schema']=='digital-tape/be1-report/1'
    assert report['complete'] is expected['complete']
    assert report['physical_run'] is expected['physical_run']
    assert set(report['criteria'])=={'F1','F2','F3','F4','F5'}
    assert report['criteria']['F3']['state']=='NOT_RUN'
    assert report['criteria']['F4']['state']=='NOT_RUN'
    if expected['criterion']:
        assert report['criteria'][expected['criterion']]['state']==expected['state']
    else:
        assert report['overall']==expected['state']
    if expected['code']:
        assert expected['code'] in codes(report), ('missing reason',expected['code'])
    assert all(v.get('state')!='PASS' for v in report['criteria'].values())

def execute(checker,bundle,report,golden,expected):
    before=snapshot(bundle)
    log=report.with_suffix('.guard.json')
    proc=subprocess.run([sys.executable,'-B',str(HERE/'guard.py'),str(checker),str(bundle),str(report),str(golden),str(log)],
        capture_output=True,timeout=30,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    violations=json.loads(log.read_text(encoding='utf-8'))
    assert not violations,violations
    assert snapshot(bundle)==before,'Input bytes changed'
    check(json.loads(report.read_text(encoding='utf-8')),proc.returncode,expected)

def pretend(expected):
    criteria={x:dict(state='NOT_RUN',reasons=[]) for x in ('F1','F2','F3','F4','F5')}
    if expected['criterion']:
        criteria[expected['criterion']]=dict(state=expected['state'],reasons=[expected['code']] if expected['code'] else [])
    return dict(schema='digital-tape/be1-report/1',criteria=criteria,complete=False,physical_run=False,
                overall=expected['state'] if not expected['criterion'] else 'NOT_RUN',
                reasons=[expected['code']] if expected['code'] else [])

def selftest(golden,out):
    cases=catalog(references(golden))
    assert len({c['name'] for c in cases})==len(cases)
    # Verify deterministic, schema-shaped fixtures and exact local file hashes.
    for c in cases:
        b=out/'bundles'/c['name'];m=materialize(c,b)
        for f in m['files'] if not c.get('wire') else []:
            raw=(b/f['path']).read_bytes()
            assert sha(raw)==f['sha256'] and len(raw)==f['bytes']
        assert all(o['provenance']!='actual' for o in m['observations']) or c['name']=='simulation-actual-marker'
        assert m['session']['kind'] in ('simulation','physical')
        r=pretend(c['expected']);check(r,c['expected']['exit'],c['expected'])
    good=cases[0]
    b=out/'bundles'/good['name']
    stubdir=out/'stub';stubdir.mkdir()
    stub=stubdir/'checker.py'
    def stub_source(report,exit=0,extra=''):
        return ('import json,sys\nfrom pathlib import Path\n'+extra+'\n'
          +f"Path(sys.argv[sys.argv.index('--out')+1]).write_text({json.dumps(json.dumps(report))},encoding='utf-8')\nraise SystemExit({exit})\n")
    stub.write_text(stub_source(pretend(good['expected'])),encoding='utf-8')
    execute(stub,b,out/'stub-pass.json',golden,good['expected'])
    detected=[]
    for label,extra in (
      ('bundle-write',"Path(sys.argv[sys.argv.index('--offline')+1],'intrusion').write_text('bad')"),
      ('network',"import socket\nsocket.socket()"),
      ('serial-import',"import serial"),
      ('subprocess',"import subprocess\nsubprocess.run(['irrelevant'])"),
    ):
        stub.write_text(stub_source(pretend(good['expected']),extra=extra),encoding='utf-8')
        try:execute(stub,b,out/(label+'.json'),golden,good['expected'])
        except AssertionError:detected.append(label)
        else:raise AssertionError('undetected '+label)
    e=good['expected'];r=pretend(e)
    for label,mut in [('false-complete',dict(complete=True)),('false-physical',dict(physical_run=True)),('wrong-state',dict(criteria={**r['criteria'],'F1':dict(state='PASS',reasons=[])}))]:
        try:check(dict(r,**mut),0,e)
        except AssertionError:detected.append(label)
        else:raise AssertionError('undetected '+label)
    # Blanket-success and missing diagnostic controls on genuine negative expectations.
    e=next(c['expected'] for c in cases if c['name'].endswith('wrong-pcm-digest'))
    for label,r,rc in [('blanket-success',pretend(good['expected']),0),('hidden-reason',{**pretend(e),'reasons':[], 'criteria':{**pretend(e)['criteria'],'F1':dict(state='MISMATCH',reasons=[])}},1)]:
        try:check(r,rc,e)
        except AssertionError:detected.append(label)
        else:raise AssertionError('undetected '+label)
    return dict(mode='harness-selftest-only',product_executed=False,fixture_cases=len(cases),
                controls_detected=detected,physical_run=False,complete=False)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--golden',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--checker',type=Path)
    ap.add_argument('--selftest',action='store_true');a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    if a.selftest:
        assert not a.checker
        result=selftest(a.golden.resolve(),out)
    else:
        assert a.checker and a.checker.is_file(),'An implemented checker must actually exist'
        results=[]
        for c in catalog(references(a.golden)):
            bundle=out/c['name'];materialize(c,bundle)
            try:
                execute(a.checker.resolve(),bundle,out/(c['name']+'.json'),a.golden.resolve(),c['expected'])
                results.append(dict(case=c['name'],passed=True))
            except Exception as exc:results.append(dict(case=c['name'],passed=False,error=repr(exc)))
        result=dict(mode='candidate-execution',checker_sha256=sha(a.checker.read_bytes()),cases=results,
                    physical_run=False,complete=False,passed=all(r['passed'] for r in results))
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
    return 0 if result.get('passed',True) else 1

if __name__=='__main__':raise SystemExit(main())
