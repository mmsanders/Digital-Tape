"""Correction-1 manifest/plan4/complete-judge binding. Synthetic inputs only."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from fixtures import CONTROLS,CID,manifest_cases,judge_cases,manifest,write_bundle,run_fixture,plan_digest,sha

def check_load(actual,path,valid):
    assert isinstance(actual,(tuple,list)) and len(actual)==3,'load_manifest result contract'
    parsed,digest,problems=actual
    assert isinstance(problems,list) and all(isinstance(x,str) for x in problems)
    if valid:
        assert not problems,problems
        assert isinstance(parsed,dict) and parsed==json.loads(path.read_bytes())
        assert digest==sha(path.read_bytes()),'Hash must authenticate exact bytes'
    else:assert problems,'Bad manifest/evidence accepted'

def check_judge(actual,e,manifest_sha):
    assert actual['verdict']==e['verdict'],('verdict',actual['verdict'],e['verdict'])
    assert actual['required_qualifying']==1000,'Production minimum changed'
    if e['qualifying'] is not None:assert actual['qualifying']==e['qualifying']
    if e['problems']:assert actual['problems'],'Missing run-integrity problem'
    elif e['verdict']=='PASS':assert not actual['problems']
    assert actual['completed_write_reverted']==e['rollback'],'Wrong completed-write proof'
    assert actual['torn_iterations']==e['tears'],'Rollback must not be relabelled TORN'
    assert actual['corrupt_iterations']==e['corrupt']
    assert actual['neighbour_damage']==e['neighbour']
    if e['verdict']=='PASS':
        assert actual['method']=='rig-r2' and actual['rig_manifest_sha256']==manifest_sha
        assert actual['bus_mode']=='spi' and actual['sck_hz']==4000000
        assert actual['qualification_scope']=='spi-characterisation','False scope transfer'

def pretend(e,mhash):
    return dict(verdict=e['verdict'],required_qualifying=1000,qualifying=e['qualifying'] or 0,
      problems=['synthetic problem'] if e['problems'] else [],completed_write_reverted=list(e['rollback']),
      torn_iterations=list(e['tears']),corrupt_iterations=list(e['corrupt']),neighbour_damage=copy.deepcopy(e['neighbour']),
      method='rig-r2',rig_manifest_sha256=mhash,bus_mode='spi',sck_hz=4000000,qualification_scope='spi-characterisation')

def predicate_cases():
    base=run_fixture('0'*64)[1][0]
    cs=[('rail-high-true',dict(base),True,None),('rail-high-omitted-predicate-compatibility',{k:v for k,v in base.items() if k!='rail_high_at_arm'},True,None)]
    for value in (False,0,1,None,'true'):
        r=copy.deepcopy(base);r['rail_high_at_arm']=value;cs.append(('rail-high-'+repr(value),r,False,'record invalid'))
    for edges in ([150.0,160.0],[150.0,160.0,170.0]):
        r=copy.deepcopy(base);r['rail_edges_us']=edges;cs.append(('chatter-'+str(len(edges)),r,False,'chatter'))
    return cs

def cli_case(module,args,expected_success):
    p=subprocess.run([sys.executable,'-B',str(module),*args],capture_output=True,timeout=60)
    assert (p.returncode==0)==expected_success,('CLI exit',args,p.returncode,p.stderr.decode(errors='replace')[-1000:])
    return p

def check_plan(p,count,mhash):
    assert p['plan_version']==4 and p['method']=='rig-r2' and p['rig_manifest_sha256']==mhash
    assert (p['sku'],p['revision'],p['card_cid'])==('SYNTHETIC-MPN','SIM12/1.0',CID)
    assert len(p['trials'])==count and len({t['iteration'] for t in p['trials']})==count
    assert p['plan_digest']==plan_digest(p),'Plan digest does not bind declared identities/method/manifest/schedule'

def cli_checks(module,out,jhash):
    directory=out/'cli';_,mp,ev,mhash=write_bundle(directory,jhash)
    plan=directory/'plan.json'
    args=['--manifest',str(mp),'--evidence',str(ev)]
    cli_case(module,['plan','--sku','SYNTHETIC-MPN','--revision','SIM12/1.0','--cid',CID,'--attempts','1001',*args,'--out',str(plan)],True)
    check_plan(json.loads(plan.read_text()),1001,mhash)
    extension=directory/'extension.json'
    cli_case(module,['plan','--extend',str(plan),'--attempts','20',*args,'--out',str(extension)],True)
    ext=json.loads(extension.read_text());check_plan(ext,20,mhash)
    initial=json.loads(plan.read_text());assert ext['extends']==initial['run_id'],'Extension not auditable'
    assert set(t['iteration'] for t in ext['trials']).isdisjoint(t['iteration'] for t in initial['trials'])
    cli_case(module,['plan','--sku','OTHER','--revision','SIM12/1.0','--cid',CID,'--attempts','1001',*args,'--out',str(directory/'bad-plan.json')],False)
    cli_case(module,['plan','--sku','SYNTHETIC-MPN','--revision','SIM12/1.0','--cid',CID,'--attempts','999',*args,'--out',str(directory/'short-plan.json')],False)
    # Independent fixed plan/results for strict wire-reader and manifest-byte checks.
    plans,rows=run_fixture(mhash);plan.write_text(json.dumps(plans[0])+'\n',encoding='utf-8')
    results=directory/'results.jsonl';raw=''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows)
    results.write_text(raw,encoding='utf-8');report=directory/'RESULT.json'
    cmd=['judge','--plan',str(plan),'--results',str(results),*args,'--json',str(report)]
    cli_case(module,cmd,True)
    check_judge(json.loads(report.read_text()),judge_cases()[0]['expected'],mhash)
    for token in ('NaN','Infinity','-Infinity'):
        results.write_text(raw.replace('"cut_command_us": 140.0','"cut_command_us": '+token,1),encoding='utf-8')
        cli_case(module,cmd,False)
    results.write_text('{"iteration":9999,'+raw[1:],encoding='utf-8');cli_case(module,cmd,False)
    results.write_text(raw,encoding='utf-8')
    # Semantically identical JSON but different bytes cannot reuse an old plan hash.
    mp.write_bytes(mp.read_bytes()+b' \n');cli_case(module,cmd,False)
    cli_case(module,['plan','--extend',str(plan),'--attempts','20',*args,'--out',str(directory/'repointed.json')],False)
    return 11

def selftest(out):
    jhash=sha(b'HARNESS-ONLY source, not a Product judge\n')
    mcs=manifest_cases();jcs=judge_cases()
    assert len({c['name'] for c in mcs})==len(mcs) and len({c['name'] for c in jcs})==len(jcs)
    for c in mcs:
        m,p,ev,mhash=write_bundle(out/c['name'],jhash,c['edit'],c['files_edit'],c['raw_edit'])
        if c['name']=='missing-manifest-file':p.unlink()
        if c['valid']:check_load((m,mhash,[]),p,True)
        else:check_load(({},mhash,['deliberately bad test input']),p,False)
    _,mp,_,mhash=write_bundle(out/'judge-fixture',jhash)
    for c in jcs:
        p,r=run_fixture(mhash);c['edit'](p,r)
        assert len(r)>=1000,'Never lower the production aggregation fixture'
        check_judge(pretend(c['expected'],mhash),c['expected'],mhash)
    controls=[]
    def reject(name,action):
        try:action()
        except AssertionError:controls.append(name)
        else:raise AssertionError('Undetected control '+name)
    reject('accept-bad-manifest',lambda:check_load(({},mhash,[]),mp,False))
    parsed=json.loads(mp.read_bytes())
    reject('wrong-exact-manifest-hash',lambda:check_load((parsed,'0'*64,[]),mp,True))
    reject('blanket-reject-good-manifest',lambda:check_load((parsed,mhash,['always reject']),mp,True))
    good=jcs[0]['expected'];bad=next(c['expected'] for c in jcs if c['name']=='completed-write-OLD-fails')
    for name,e,edit in [
      ('lower-minimum',good,dict(required_qualifying=1)),('miss-counted',good,dict(qualifying=1001)),
      ('rollback-report-only',bad,dict(verdict='PASS')),('rollback-erased',bad,dict(completed_write_reverted=[])),
      ('rollback-labelled-TORN',bad,dict(torn_iterations=[1001])),('missing-integrity-problem',bad,dict(problems=[])),
      ('false-native-scope',good,dict(qualification_scope='sd4'))]:
        reject(name,lambda e=e,edit=edit:check_judge(dict(pretend(e,mhash),**edit),e,mhash))
    for name in ('ambiguous-OLD-149.0','ambiguous-OLD-151.0','OLD-no-completion-proof-chatter','record-invalid-is-problem-not-rollback'):
        e=next(c['expected'] for c in jcs if c['name']==name)
        reject('false-rollback-'+name,lambda e=e:check_judge(dict(pretend(e,mhash),completed_write_reverted=[1001]),e,mhash))
    for field in ('torn_iterations','neighbour_damage'):
        c=next(c for c in jcs if c['expected']['tears' if field=='torn_iterations' else 'neighbour'])
        reject('hide-'+field,lambda c=c,field=field:check_judge(dict(pretend(c['expected'],mhash),**{field:[]}),c['expected'],mhash))
    p,_=run_fixture(mhash);check_plan(p[0],1001,mhash)
    for field,value in [('plan_version',3),('method','other'),('rig_manifest_sha256','0'*64),('plan_digest','0'*64)]:
        reject('plan-does-not-bind-'+field,lambda field=field,value=value:check_plan(dict(p[0],**{field:value}),1001,mhash))
    return dict(mode='harness-selftest-only',manifest_cases=len(mcs),complete_judge_cases=len(jcs),predicate_cases=len(predicate_cases()),
      cli_scenarios_authored=11,controls_detected=controls,product_executed=False,physical_run=False,method_clearance=False)

def candidate(module,out):
    jhash=sha(module.read_bytes());spec=importlib.util.spec_from_file_location('independent_rig_candidate',module)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    observations=[]
    def record(name,fn):
        try:fn();observations.append(dict(case=name,passed=True))
        except Exception as e:observations.append(dict(case=name,passed=False,error=repr(e)))
    for c in manifest_cases():
        _,p,ev,_=write_bundle(out/('manifest-'+c['name']),jhash,c['edit'],c['files_edit'],c['raw_edit'])
        if c['name']=='missing-manifest-file':p.unlink()
        record('load-'+c['name'],lambda p=p,ev=ev,c=c:check_load(m.load_manifest(p,ev),p,c['valid']))
    _,mp,ev,mhash=write_bundle(out/'judge-fixture',jhash)
    for c in judge_cases():
        def run(c=c):
            loaded=m.load_manifest(mp,ev);check_load(loaded,mp,True)
            p,r=run_fixture(mhash);c['edit'](p,r)
            if c['loader']=='none':loaded=None
            elif c['loader']=='bad':loaded=(loaded[0],loaded[1],['synthetic failed prerequisite'])
            elif c['loader']=='changed-bytes':loaded=(loaded[0],sha(mp.read_bytes()+b' \n'),[])
            actual=m.judge(p,r,manifest=loaded);check_judge(actual,c['expected'],mhash)
        record(c['name'],run)
    for name,r,expected,reason in predicate_cases():
        def run(r=r,expected=expected,reason=reason):
            actual=m.qualifies(copy.deepcopy(r));assert actual[0] is expected
            if reason:assert reason in actual[1].lower()
        record('predicate-'+name,run)
    record('plan4-and-strict-wire-CLI',lambda:cli_checks(module,out,jhash))
    # The current interim v3 refusal is explicit, and not a substitute for v4 success.
    def interim():
        p,r=run_fixture(mhash);p[0]['plan_version']=3
        p[0].pop('method');p[0].pop('rig_manifest_sha256')
        core={k:p[0][k] for k in ('run_id','sku','revision','card_cid','block','neighbour_offsets')}
        core['trials']=[[t['iteration'],t['cut_offset_fraction']] for t in p[0]['trials']]
        p[0]['plan_digest']=sha(json.dumps(core,sort_keys=True,separators=(',',':')).encode())
        for item in r:item['plan_digest']=p[0]['plan_digest']
        actual=m.judge(p,r)
        assert actual['verdict']=='FAIL' and actual['problems'] and actual['qualifying']==0
    record('method-rows-cannot-enter-v3-without-manifest',interim)
    return dict(mode='candidate-synthetic-records',judge_sha256=jhash,cases=observations,
      passed=all(v['passed'] for v in observations),physical_run=False,method_clearance=False)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--judge',type=Path);ap.add_argument('--selftest',action='store_true');ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    if a.selftest:assert not a.judge;result=selftest(out)
    else:assert a.judge and a.judge.is_file();result=candidate(a.judge.resolve(),out)
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}));return 0 if result.get('passed',True) else 1

if __name__=='__main__':raise SystemExit(main())
