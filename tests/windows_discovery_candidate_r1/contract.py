"""325 additive dual-pin/current-source/guide preflight. Reuses the existing archive judge."""
import argparse,copy,hashlib,importlib.util,io,json,re,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('accepted_archive',HERE.parent/'windows_preview_r1/archive.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
INGEST='3895f3f356c91b8a9fe870c33694da64bf2765df308bef118d657c1be4bb9a20'
TAPECTL='44ef26869ba2d01a8a183660a2c7a050d0e7e9ff37c40b727131512739ea6ded'
TAP_SOURCE='f9306c2c5a42ebd039edd67b0b7cef6a7d434b2b'
ENGINE='d96b4245e04d74078f8938744b1394c3018516f7'
WAV='48f1b3c7ce7fe27a90469364f841803087a9d274a4af9a4ec8ee195a2846ac18'
PINS=dict(DT_INGEST_SHA256=INGEST,DT_INGEST_VERSION='0.1.1 INGEST-1 arithmetic-profile INGEST1-AP4',DT_TAPECTL_SHA256=TAPECTL,DT_TAPECTL_VERSION='tapectl-wp15-s2+f9306c2c5a42')
def hex40(x):assert re.fullmatch('[0-9a-f]{40}',x)
def metadata(b,registry,r):
    assert r['scope']=='BUILD/ARCHIVE ONLY' and r['app_launches']==r['child_invocations']==r['metadata_runs']==0
    assert r['readiness']=='BUILD/ARCHIVE READY, UI METHOD HELD' and r['ui_method_missing']
    for k in ['source_head','source_tree','host_app_tree','tools_app_tree','current_base']:hex40(r[k])
    assert r['engine_tree']==ENGINE and b['source_head']==r['source_head']
    dep=r['interaction_clearance'];hex40(dep['publication']);hex40(dep['product_commit'])
    assert dep['kind'] in ['exact source PASS integrated','explicit no-change PASS'] and dep['exact_source_refs']
    assert r['compile_env']==PINS and b['compile_pins']==PINS
    assert b['tapectl_source']==TAP_SOURCE and b['child_pin']==INGEST
    assert r['tapectl_artifact']==12610149859 and r['tapectl_build_run']==40225724763
    assert r['tapectl_bytes']==493712 and r['tapectl_version']==PINS['DT_TAPECTL_VERSION']
    assert r['ingest_transport']['artifact_id'] in [12578829894,12471942204]
    assert r['ingest_transport']['member_sha256']==INGEST and r['ingest_transport']['member_bytes']==889856
    assert re.fullmatch('[0-9a-f]{64}',r['ingest_transport']['container_sha256'])
    if r['ingest_transport']['artifact_id']==12578829894:
        assert r['ingest_transport']['container_sha256']=='a19c47d7d474414cfb0c8cf992fd6e984bf9ff160c5e38efdd7e09a45b12aa94'
    assert registry['components']['ingest.exe']['sha256']==INGEST
    assert registry['components']['tapectl.exe']['sha256']==TAPECTL
    assert registry['components']['tapectl.exe']['source']==TAP_SOURCE
    assert registry['components']['digital-tape.exe']['source']==r['source_head']
    assert registry['components']['digital-tape.exe']['sha256']!='ee4c84acb03655c4fb1344db1548ab283054eabe9caea9c2482b0181b39fa250'
    cmd=r['build_argv'];assert 'cargo' in Path(cmd[0]).stem and 'build' in cmd and '--release' in cmd and '--locked' in cmd
    for k in ['compiler_refs','lock_refs','pin_source_refs','actual_build_log_refs','artifact_refs','member_hash_refs','source_crosswalk_refs','negative_mismatch_control_refs','guide_refs']:assert r[k]
    assert r['old564_unchanged'] and not r['shipping_fake_route'] and not r['make_or_elevation_enabled']
    assert r['inventory_location']=='outside five-member ZIP'
    guide=r['readme'].lower()
    for word in ['unsigned','preview','webview2','make','disabled','extract','digital-tape.exe','unexecuted']:assert word in guide,word
    sheet=r['manual_sheet'].lower()
    for word in ['317','564','585','no-card','observed','unexecuted','permission','make','disabled',WAV]:assert word in sheet,word
    assert r['manual_sheet_is_optional'] and not r['claims_old_startup_for_new_app'] and not r['claims_native_ui']
    return 'ONLY additive build/archive readiness; no launch/poller/native/child/card/Make admission'
def check(data,registry,r):
    # The old five-member/source/hash/claim gate remains byte-identical. No relaxation.
    prior.check(data,registry)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        b=json.loads(z.read('BUILD.json').decode('utf-8-sig'))
        assert z.read('README.txt').decode('utf-8-sig')==r['readme']
    assert hashlib.sha256(data).hexdigest()==r['zip_sha256']
    return metadata(b,registry,r)
def fixture():
    # Synthetic metadata qualifier control, not an executable or accepted registry.
    b=dict(source_head='a'*40,compile_pins=PINS.copy(),tapectl_source=TAP_SOURCE,child_pin=INGEST)
    registry=dict(components={'digital-tape.exe':dict(source='a'*40,sha256='b'*64),'ingest.exe':dict(sha256=INGEST),'tapectl.exe':dict(sha256=TAPECTL,source=TAP_SOURCE)})
    r=dict(scope='BUILD/ARCHIVE ONLY',app_launches=0,child_invocations=0,metadata_runs=0,readiness='BUILD/ARCHIVE READY, UI METHOD HELD',ui_method_missing=['SYNTHETIC missing actual new-binary app/poller/actor/gesture method'],source_head='a'*40,source_tree='b'*40,host_app_tree='c'*40,tools_app_tree='d'*40,current_base='e'*40,engine_tree=ENGINE,
      interaction_clearance=dict(publication='f'*40,product_commit='1'*40,kind='exact source PASS integrated',exact_source_refs=['SYNTHETIC']),compile_env=PINS.copy(),tapectl_artifact=12610149859,tapectl_build_run=40225724763,tapectl_bytes=493712,tapectl_version=PINS['DT_TAPECTL_VERSION'],
      ingest_transport=dict(artifact_id=12578829894,member_sha256=INGEST,member_bytes=889856,container_sha256='a19c47d7d474414cfb0c8cf992fd6e984bf9ff160c5e38efdd7e09a45b12aa94'),build_argv=['cargo','build','--release','--locked'],compiler_refs=['SYNTHETIC'],lock_refs=['SYNTHETIC'],pin_source_refs=['SYNTHETIC'],actual_build_log_refs=['SYNTHETIC'],artifact_refs=['SYNTHETIC'],member_hash_refs=['SYNTHETIC'],source_crosswalk_refs=['SYNTHETIC'],negative_mismatch_control_refs=['SYNTHETIC'],guide_refs=['SYNTHETIC'],old564_unchanged=True,shipping_fake_route=False,make_or_elevation_enabled=False,inventory_location='outside five-member ZIP',readme='Unsigned preview. Existing WebView2. Extract all. digital-tape.exe. Make disabled. Actual UI UNEXECUTED.',manual_sheet='Optional no-card 317 rows, original564/new585 distinct. observed/unexecuted. Permission needed; Make disabled. WAV '+WAV,manual_sheet_is_optional=True,claims_old_startup_for_new_app=False,claims_native_ui=False)
    return b,registry,r
def controls():
    b,g,r=fixture();metadata(b,g,r)
    for kind in ['missing-pin','old-child','no-interaction-clearance','no-locked-build','app-launched','ui-ready','inventory-extra','wrong-ingest','old-app-promotion','native-claim']:
        x,y,z=copy.deepcopy(b),copy.deepcopy(g),copy.deepcopy(r)
        if kind=='missing-pin':del x['compile_pins']['DT_TAPECTL_SHA256']
        elif kind=='old-child':y['components']['tapectl.exe']['sha256']='82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9'
        elif kind=='no-interaction-clearance':z['interaction_clearance']['publication']=''
        elif kind=='no-locked-build':z['build_argv'].remove('--locked')
        elif kind=='app-launched':z['app_launches']=1
        elif kind=='ui-ready':z['readiness']='READY FOR MANUAL NO-CARD UI TEST'
        elif kind=='inventory-extra':z['inventory_location']='inside ZIP'
        elif kind=='wrong-ingest':z['ingest_transport']['member_sha256']='0'*64
        elif kind=='old-app-promotion':y['components']['digital-tape.exe']['sha256']='ee4c84acb03655c4fb1344db1548ab283054eabe9caea9c2482b0181b39fa250'
        elif kind=='native-claim':z['claims_native_ui']=True
        try:metadata(x,y,z)
        except AssertionError:continue
        raise AssertionError('candidate additive negative control survived: '+kind)
    print('PASS dual-pin/dependency/transport/readiness10 causal controls; ZERO build/archive/Product execution')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);p.add_argument('--registry',type=Path);p.add_argument('--record',type=Path);p.add_argument('--emit',action='store_true');a=p.parse_args()
    if a.emit:print(json.dumps(dict(pins=PINS,preferred_child_source=TAP_SOURCE,scope='BUILD/ARCHIVE ONLY',final_build_dependency='published324/584 exact source integration or explicit no-change PASS',zip_members=sorted(prior.MEMBERS),inventory='sidecar outside ZIP',runtime_admission='NONE'),indent=2))
    elif a.archive:print(check(a.archive.read_bytes(),json.loads(a.registry.read_text(encoding='utf-8-sig')),json.loads(a.record.read_text(encoding='utf-8-sig'))))
    else:controls()
