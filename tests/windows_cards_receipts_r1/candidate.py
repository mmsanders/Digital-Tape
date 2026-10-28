"""NEW PM611/612 budget, old r1 technical archive predicate unchanged. ZERO execution."""
import copy,datetime,io,json,zipfile
from receipts import load,TESTS,hx
old=load('candidate612_accepted_r2',TESTS/'windows_discovery_candidate_r2/contract.py')

def stamp(s):
    x=datetime.datetime.fromisoformat(s.replace('Z','+00:00'));assert x.tzinfo;return x
def metadata(build,registry,r):
    # Do not call old r2 with a forged count=1. r1 remains the byte/archive technical gate;
    # r2's additive guards are carried here, with only its old single-build rule superseded.
    old.prior.metadata(build,registry,r)
    dep=r['console_receipt_clearance'];old.prior.hex40(dep['publication']);old.prior.hex40(dep['product_commit'])
    assert dep['kind']=='exact332 source PASS integrated' and dep['exact_source_refs']
    d=r['diagnostics'];assert d['default']=='OFF' and build['diagnostics_default']=='OFF'
    assert d['control_root']=='private per-user CONTROL' and d['max_session_bytes']==old.MAX
    assert d['default_config_source_refs'] and d['published_schema_refs'] and d['opt_in_omitted_from_build_environment'] is True
    assert d['native_session_admission']=='UNISSUED' and d['packaged_private_session_data'] is False
    assert 'diagnostics' in r['readme'].lower() and 'default off' in r['readme'].lower()
    for phrase in ['564 completed partial','no repeat','separate final-candidate admission','poller']:assert phrase in r['manual_sheet'].lower()
    assert r['receipt_availability_is_native_acceptance'] is False
    assert r['candidate_authorization']=='PM611/Software612 NEW replacement' and build['profile']=='612'
    dep=r['cards_receipt_clearance'];old.prior.hex40(dep['publication']);old.prior.hex40(dep['product_commit'])
    assert dep['kind']=='exact352 source PASS integrated' and dep['exact_source_refs'] and dep['component_original_refs']
    assert dep['contract']=='cards-1' and dep['product_commit']==r['source_head']
    assert r['source_correction_responses'] in [0,1,2] and r['functional_scope_unchanged'] is True
    attempts=r['candidate_attempts'];assert type(r['final_build_count']) is int and r['final_build_count']==len(attempts) and 1<=len(attempts)<=2
    assert r['uploaded_candidates']==1 and r['children_rebuilt']==0 and r['old585_rebuilt'] is False
    assert r['budget_exhausted_retry'] is False and r['candidate_compilation_refs'] and r['ci_build_inventory']
    assert len({a['log_ref'] for a in attempts})==len(attempts)
    prior_end=None
    for i,a in enumerate(attempts):
        assert set(a)=={'attempt','source_head','source_clearance_ref','integration_ref','clearance_at','integration_at','started_at','finished_at','exit','artifacts','log_ref'}
        assert a['attempt']==i+1 and a['log_ref'] and a['source_clearance_ref'] and a['integration_ref']
        old.prior.hex40(a['source_head']);start=stamp(a['started_at']);end=stamp(a['finished_at'])
        assert stamp(a['clearance_at'])<=start and stamp(a['integration_at'])<=start<=end
        if prior_end is not None:assert start>=prior_end
        prior_end=end;assert type(a['exit']) is int and isinstance(a['artifacts'],list)
        for item in a['artifacts']:assert set(item)=={'name','bytes','sha256','ref'} and item['name'] and item['ref'] and type(item['bytes']) is int and item['bytes']>0;hx(item['sha256'],64)
        if i<len(attempts)-1:assert a['exit']!=0 # no reproducibility/extra successful compile
    final=attempts[-1];assert final['exit']==0 and final['source_head']==r['source_head'] and final['artifacts']
    app=registry['components']['digital-tape.exe']['sha256'];hx(app,64)
    assert any(a['name']=='digital-tape.exe' and a['sha256']==app for a in final['artifacts'])
    return '612 BUILD/ARCHIVE ONLY; truthful 1-or-2 attempts/ONE candidate; all native/UI/G1 holds'
def check(data,registry,r):
    old.prior.check(data,registry,r)
    with zipfile.ZipFile(io.BytesIO(data)) as z:b=json.loads(z.read('BUILD.json').decode('utf-8-sig'))
    return metadata(b,registry,r)
def fixture():
    b,g,r=old.fixture();b['profile']='612'
    a=dict(attempt=1,source_head=r['source_head'],source_clearance_ref='SYNTHETIC',integration_ref='SYNTHETIC',clearance_at='2026-10-28T01:00:00Z',integration_at='2026-10-28T01:01:00Z',started_at='2026-10-28T01:02:00Z',finished_at='2026-10-28T01:03:00Z',exit=0,artifacts=[dict(name='digital-tape.exe',bytes=1,sha256=g['components']['digital-tape.exe']['sha256'],ref='SYNTHETIC')],log_ref='SYNTHETIC1')
    r.update(candidate_authorization='PM611/Software612 NEW replacement',cards_receipt_clearance=dict(publication='4'*40,product_commit=r['source_head'],kind='exact352 source PASS integrated',exact_source_refs=['SYNTHETIC'],component_original_refs=['SYNTHETIC'],contract='cards-1'),source_correction_responses=0,functional_scope_unchanged=True,candidate_attempts=[a],uploaded_candidates=1,children_rebuilt=0,old585_rebuilt=False,budget_exhausted_retry=False,candidate_compilation_refs=['SYNTHETIC'],ci_build_inventory=['SYNTHETIC: none'])
    return b,g,r
def controls():
    b,g,r=fixture();metadata(b,g,r)
    x=copy.deepcopy(r);first=copy.deepcopy(x['candidate_attempts'][0]);first.update(exit=1,artifacts=[],finished_at=first['started_at']);second=x['candidate_attempts'][0];second.update(attempt=2,log_ref='SYNTHETIC2');x.update(candidate_attempts=[first,second],final_build_count=2);metadata(b,g,x)
    cases=[('third attempt',lambda z:z.update(candidate_attempts=z['candidate_attempts']*3,final_build_count=3)),('count lie',lambda z:z.update(final_build_count=2)),('two uploads',lambda z:z.update(uploaded_candidates=2)),('child rebuilt',lambda z:z.update(children_rebuilt=1)),('old585 rebuild',lambda z:z.update(old585_rebuilt=True)),('no cards clearance',lambda z:z['cards_receipt_clearance'].update(publication='')),('not integrated',lambda z:z['cards_receipt_clearance'].update(kind='tests ready')),('false integration source',lambda z:z['cards_receipt_clearance'].update(product_commit='0'*40)),('missing original components',lambda z:z['cards_receipt_clearance'].update(component_original_refs=[])),('build before clearance',lambda z:z['candidate_attempts'][0].update(clearance_at='2026-10-28T02:00:00Z')),('no attempt log',lambda z:z['candidate_attempts'][0].update(log_ref='')),('failed candidate',lambda z:z['candidate_attempts'][0].update(exit=1)),('wrong output hash',lambda z:z['candidate_attempts'][0]['artifacts'][0].update(sha256='0'*64)),('missing CI inventory',lambda z:z.update(ci_build_inventory=[])),('scope expansion',lambda z:z.update(functional_scope_unchanged=False)),('diagnostics defaultON',lambda z:z['diagnostics'].update(default='ON')),('runtime promotion',lambda z:z['diagnostics'].update(native_session_admission='READY'))]
    for name,mutate in cases:
        z=copy.deepcopy(r);mutate(z)
        try:metadata(b,g,z)
        except (AssertionError,ValueError):continue
        raise AssertionError(name)
    print(json.dumps(dict(scope='SYNTHETIC CANDIDATE METADATA ONLY',positive=2,negative=len(cases),product_builds=0)))
if __name__=='__main__':controls()
