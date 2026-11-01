"""325 PM593 additive source/diagnostic-default guard; existing archive/r1 bytes unchanged."""
import argparse,copy,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('candidate_r1',HERE.parent/'windows_discovery_candidate_r1/contract.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
MAX=16*1024*1024
def metadata(build,registry,r):
    prior.metadata(build,registry,r)
    dep=r['console_receipt_clearance'];prior.hex40(dep['publication']);prior.hex40(dep['product_commit'])
    assert dep['kind']=='exact332 source PASS integrated' and dep['exact_source_refs']
    d=r['diagnostics'];assert d['default']=='OFF' and build['diagnostics_default']=='OFF'
    assert d['control_root']=='private per-user CONTROL' and d['max_session_bytes']==MAX
    assert d['default_config_source_refs'] and d['published_schema_refs'] and d['opt_in_omitted_from_build_environment'] is True
    assert d['native_session_admission']=='UNISSUED' and d['packaged_private_session_data'] is False
    guide=r['readme'].lower();assert 'diagnostics' in guide and 'default off' in guide
    sheet=r['manual_sheet'].lower()
    for phrase in ['564 completed partial','no repeat','separate final-candidate admission','poller']:assert phrase in sheet,phrase
    assert r['final_build_count']==1 and r['receipt_availability_is_native_acceptance'] is False
    return 'BUILD/ARCHIVE ONLY; accepted332 integration required; diagnostics default OFF; no native/poller admission'
def check(data,registry,r):
    prior.check(data,registry,r)
    import io,zipfile
    with zipfile.ZipFile(io.BytesIO(data)) as z:build=json.loads(z.read('BUILD.json').decode('utf-8-sig'))
    return metadata(build,registry,r)
def fixture():
    b,g,r=prior.fixture();b['diagnostics_default']='OFF'
    r.update(console_receipt_clearance=dict(publication='2'*40,product_commit='3'*40,kind='exact332 source PASS integrated',exact_source_refs=['SYNTHETIC']),diagnostics=dict(default='OFF',control_root='private per-user CONTROL',max_session_bytes=MAX,default_config_source_refs=['SYNTHETIC'],published_schema_refs=['SYNTHETIC'],opt_in_omitted_from_build_environment=True,native_session_admission='UNISSUED',packaged_private_session_data=False),final_build_count=1,receipt_availability_is_native_acceptance=False)
    r['readme']+=' Diagnostics default OFF.'
    r['manual_sheet']+=' Original564 completed partial; no repeat. New receipt/poller needs separate final-candidate admission.'
    return b,g,r
def controls():
    b,g,r=fixture();metadata(b,g,r)
    cases=[('missing332',lambda b,r:r['console_receipt_clearance'].update(publication='')),('not integrated',lambda b,r:r['console_receipt_clearance'].update(kind='tests ready')),('on by default',lambda b,r:b.update(diagnostics_default='ON')),('build optin',lambda b,r:r['diagnostics'].update(opt_in_omitted_from_build_environment=False)),('arbitrary sink',lambda b,r:r['diagnostics'].update(control_root='user-specified export')),('unbounded sink',lambda b,r:r['diagnostics'].update(max_session_bytes=MAX+1)),('private data shipped',lambda b,r:r['diagnostics'].update(packaged_private_session_data=True)),('native promotion',lambda b,r:r.update(receipt_availability_is_native_acceptance=True)),('repeat build',lambda b,r:r.update(final_build_count=2)),('no source binding',lambda b,r:r['diagnostics'].update(default_config_source_refs=[])),('runtime granted',lambda b,r:r['diagnostics'].update(native_session_admission='READY')),('obsolete guide',lambda b,r:r.update(manual_sheet='repeat564'))]
    for name,mutate in cases:
        x,y=copy.deepcopy(b),copy.deepcopy(r);mutate(x,y)
        try:metadata(x,g,y)
        except AssertionError:continue
        raise AssertionError('candidate PM593 negative survived: '+name)
    print('PASS12 PM593 candidate guards; ZERO build/archive/Product execution')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);p.add_argument('--registry',type=Path);p.add_argument('--record',type=Path);p.add_argument('--emit',action='store_true');a=p.parse_args()
    if a.emit:print(json.dumps(dict(scope='BUILD/ARCHIVE ONLY',dependency='exact integrated332/594 clearance, plus completed324/584',diagnostics_default='OFF',max_session_bytes=MAX,native_admission='NONE',old_packages='windows_discovery_candidate_r1 and windows_preview_r1 unchanged'),indent=2))
    elif a.archive:print(check(a.archive.read_bytes(),json.loads(a.registry.read_text(encoding='utf-8-sig')),json.loads(a.record.read_text(encoding='utf-8-sig'))))
    else:controls()
