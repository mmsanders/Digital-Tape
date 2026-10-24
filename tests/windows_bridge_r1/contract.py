"""306 thin production bridge expectations; controlled-order component facts only."""
import argparse, copy, importlib.util, json, re
from pathlib import Path, PureWindowsPath

ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('accepted_lifecycle',ROOT/'windows_app_jobs_r1/lifecycle.py')
lifecycle=importlib.util.module_from_spec(spec);spec.loader.exec_module(lifecycle)
CHILD='3895f3f356c91b8a9fe870c33694da64bf2765df308bef118d657c1be4bb9a20'
FOLDERS=[r'C:\Music\A & literal',r'C:\Music\B',r'C:\Music\C']
INVALID=[None,{},'A',[],[1],[''],['A',None]]

def below(child,parent):
    c,p=PureWindowsPath(child),PureWindowsPath(parent)
    return c.is_absolute() and c!=p and p in c.parents

def request(r):
    assert r['tool']=='ingest' and r['binary_sha256']==CHILD and r['report_version']==lifecycle.VERSION
    assert r['shell'] is False and r['elevated'] is False and r['length_seconds']==3600
    assert r['folders']==FOLDERS and r['argv'][-len(FOLDERS):]==FOLDERS
    argv=r['argv'];assert argv[0]==r['resolved_child'] and PureWindowsPath(argv[0]).is_absolute()
    assert PureWindowsPath(r['resolved_child']).parent==PureWindowsPath(r['executable_dir'])
    for flag,value in [('--out',r['dest']),('--length','3600'),('--report',r['report']),('--report-nonce',r['nonce'])]:
        assert argv.count(flag)==1 and argv[argv.index(flag)+1]==value
    assert re.fullmatch('[0-9a-f]{32}',r['nonce'])
    assert below(r['job'],r['private_root']) and below(r['control'],r['job']) and below(r['dest'],r['job'])
    assert below(r['report'],r['control']) and not below(r['report'],r['dest']) and r['control']!=r['dest']
    assert r['cwd'] not in FOLDERS and r['cwd']!=r['executable_dir'] # foreign cwd control, resolution must not depend on it
    assert not any(below(r['job'],folder) or below(r['control'],folder) for folder in FOLDERS)

def qualify(r,head):
    assert re.fullmatch('[0-9a-f]{40}',head) and r['source_head']==head
    assert r['evidence_class']=='production bridge / controlled order' and r['raw_refs'] and r['adapter_ref']
    assert not r['actual_os_race'] and not r['native_ui'] and not r['real_child_executed']
    assert r['capabilities']==dict(discovery=False,make=False,elevation=False,raw_device=False,shipping_fake_switch=False)
    assert r['delivery_rows']=={name:lifecycle.deliveries(events) for name,events in lifecycle.SEQUENCES.items()}
    assert r['state_rows']=={c['id']:lifecycle.expected(c) for c in lifecycle.CASES}
    assert r['mount_calls']==['snapshot','subscribe'] and r['mount_jobs']==0
    assert r['label_calls']==['set_label'] and r['label_jobs']==0 and r['details_calls']==['raw_details']
    assert r['details_text']=='raw\r\n<unsafe>& stderr' and r['stderr_selected_outcome'] is False
    assert r['valid_drop_workers']==[[FOLDERS[0]],FOLDERS] and r['accepted_folders']==FOLDERS
    assert r['invalid_payload_workers']==[0]*len(INVALID)
    for key in ['single_file','mixed','symlink','unknown_identity']:
        d=r['classified_drops'][key]
        if key!='unknown_identity':assert d['new_workers']==0 and d['accepted_before']==d['accepted_after']
        else:assert d['forwarded_to_ingest'] # unknown identity cannot silently disappear / be falsely deduplicated
    duplicate=r['same_identity_duplicate'];assert duplicate['new_workers']==0 and duplicate['accepted_after']==[FOLDERS[0]]
    assert r['lock_probe']==['worker-enter','coordinator-lock-acquired','completion-delivered']
    assert r['cleanup_order']==['cancel-request','old-worker-terminal','remove-old-owned-job','replacement-worker-start']
    assert r['start_over_order']==['invalidate-current','cancel-request','empty-view','worker-terminal','remove-owned-job']
    assert r['stale_emissions']==0 and r['duplicate_emissions']==0 and r['auto_relaunches']==0
    assert r['ui_thread_waits_for_worker'] is False and r['foreign_sentinel_before']==r['foreign_sentinel_after']
    assert r['source_before']==r['source_after'] and r['external_cleanup_calls']==[]
    request(r['request'])
    assert r['linkage_refs'] and r['unchanged_backend_blobs'] and r['tauri_entry_refs']
    return 'ONLY thin production bridge/wiring component; no native UI/race/real-child clearance'

def fixture():
    private=r'C:\Users\component-test\AppData\Local\DigitalTape';job=private+r'\jobs\new';control=job+r'\control';dest=job+r'\out'
    req=dict(tool='ingest',binary_sha256=CHILD,report_version=lifecycle.VERSION,shell=False,elevated=False,length_seconds=3600,folders=FOLDERS,
             resolved_child=r'C:\bundle\ingest.exe',executable_dir=r'C:\bundle',private_root=private,job=job,control=control,dest=dest,
             report=control+r'\report.jsonl',nonce='a'*32,cwd=r'C:\foreign')
    req['argv']=[req['resolved_child'],'--out',dest,'--length','3600','--report',req['report'],'--report-nonce',req['nonce'],*FOLDERS]
    return dict(source_head='a'*40,evidence_class='production bridge / controlled order',raw_refs=['SYNTHETIC'],adapter_ref='SYNTHETIC',actual_os_race=False,native_ui=False,real_child_executed=False,
                capabilities=dict(discovery=False,make=False,elevation=False,raw_device=False,shipping_fake_switch=False),delivery_rows={n:lifecycle.deliveries(e) for n,e in lifecycle.SEQUENCES.items()},state_rows={c['id']:lifecycle.expected(c) for c in lifecycle.CASES},
                mount_calls=['snapshot','subscribe'],mount_jobs=0,label_calls=['set_label'],label_jobs=0,details_calls=['raw_details'],details_text='raw\r\n<unsafe>& stderr',stderr_selected_outcome=False,
                valid_drop_workers=[[FOLDERS[0]],FOLDERS],accepted_folders=FOLDERS,invalid_payload_workers=[0]*len(INVALID),
                classified_drops={k:dict(new_workers=0,accepted_before=[FOLDERS[0]],accepted_after=[FOLDERS[0]],forwarded_to_ingest=True) for k in ['single_file','mixed','symlink','unknown_identity']},
                same_identity_duplicate=dict(new_workers=0,accepted_after=[FOLDERS[0]]),lock_probe=['worker-enter','coordinator-lock-acquired','completion-delivered'],
                cleanup_order=['cancel-request','old-worker-terminal','remove-old-owned-job','replacement-worker-start'],start_over_order=['invalidate-current','cancel-request','empty-view','worker-terminal','remove-owned-job'],
                stale_emissions=0,duplicate_emissions=0,auto_relaunches=0,ui_thread_waits_for_worker=False,foreign_sentinel_before='same',foreign_sentinel_after='same',source_before='same',source_after='same',external_cleanup_calls=[],request=req,
                linkage_refs=['SYNTHETIC'],unchanged_backend_blobs=['SYNTHETIC'],tauri_entry_refs=['SYNTHETIC'])

def controls():
    good=fixture();qualify(good,'a'*40)
    mutations=[lambda q:q['request'].update(shell=True),lambda q:q['request'].update(resolved_child=r'C:\foreign\ingest.exe'),lambda q:q['request'].update(report=q['request']['dest']+'\\report'),
               lambda q:q['request']['argv'].__setitem__(-1,'C & command'),lambda q:q['request'].update(binary_sha256='0'*64),lambda q:q['capabilities'].update(make=True),
               lambda q:q.update(stale_emissions=1),lambda q:q.update(duplicate_emissions=1),lambda q:q.update(lock_probe=['worker-enter','completion-delivered']),
               lambda q:q.update(cleanup_order=list(reversed(q['cleanup_order']))),lambda q:q.update(invalid_payload_workers=[1]*len(INVALID)),
               lambda q:q['delivery_rows']['start-over-supersedes'][-1]['visible'].update(view='Ready'),lambda q:q.update(stderr_selected_outcome=True),lambda q:q.update(external_cleanup_calls=['foreign'])]
    for change in mutations:
        bad=copy.deepcopy(good);change(bad)
        try:qualify(bad,'a'*40)
        except AssertionError:continue
        raise AssertionError('bridge causal control survived')
    print('PASS bridge/linkage/argv/ownership/ordering causal controls; ZERO Product/child/native execution')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--emit',action='store_true');p.add_argument('--input',type=Path);p.add_argument('--candidate');a=p.parse_args()
    if a.emit:print(json.dumps(dict(state_cases=lifecycle.CASES,sequences=lifecycle.SEQUENCES,folders=FOLDERS,invalid_payloads=INVALID),indent=2))
    elif a.input:print(qualify(json.loads(a.input.read_text(encoding='utf-8-sig')),a.candidate))
    else:controls()
