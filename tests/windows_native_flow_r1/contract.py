"""317 real-flow evidence index predicates, not an interaction simulator or UI proof."""
import argparse,copy,hashlib,json,struct
from pathlib import Path
APP='ee4c84acb03655c4fb1344db1548ab283054eabe9caea9c2482b0181b39fa250'
CHILD='3895f3f356c91b8a9fe870c33694da64bf2765df308bef118d657c1be4bb9a20'
ROWS=['page','label','file-drop','mixed-drop','positive','empty-refusal','reset']
def wav():
    pattern=b''.join(struct.pack('<hh',i*251-16000,15000-i*239) for i in range(128))
    data=(pattern*((88200*4+len(pattern)-1)//len(pattern)))[:88200*4]
    return struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',36+len(data),b'WAVE',b'fmt ',16,1,2,44100,176400,4,16,b'data',len(data))+data
def qualify(r):
    assert r['app_sha256']==APP and r['child_sha256']==CHILD
    assert r['scope']=='actual native controls/live IPC/app-driven child' and r['actor'] and r['provider'] and r['permission_mode']
    assert r['user_task_authorization_ref'] and r['raw_refs'] and r['genuine_folder_gesture_ref']
    assert not r['injection'] and not r['fake_child'] and not r['direct_cli_substitute']
    assert r['session_seconds']<=600 and r['no_card_make_elevation']
    assert set(r['rows'])==set(ROWS)
    for name,row in r['rows'].items():
        assert row['status'] in ['observed','UNEXECUTED','failed'] and row['raw_refs']
        if row['status']!='observed':continue
        assert row['actual_control_ref'] and row['actual_app_state_ref']
    for name in ['file-drop','mixed-drop']:
        row=r['rows'][name]
        if row['status']=='observed':assert row['new_child_requests']==0 and row['accepted_before']==row['accepted_after']
    for name,exit in [('positive',0),('empty-refusal',2)]:
        row=r['rows'][name]
        if row['status']=='observed':
            assert row['real_app_driven_child'] and row['exit']==exit
            assert all(row[k] for k in ['event_ipc_ref','worker_ref','child_pid_argv_ref','nonce_version_report_ref'])
    pos=r['rows']['positive']
    if pos['status']=='observed':assert pos['total_frames']==88200 and pos['published_pair_ref'] and pos['fixture_sha256']==hashlib.sha256(wav()).hexdigest()
    reset=r['rows']['reset']
    if reset['status']=='observed':assert reset['label']==reset['details']=='' and reset['folders']==[] and reset['state']=='Empty' and reset['frames']==0 and reset['make_disabled']
    assert r['source_before']==r['source_after'] and r['foreign_before']==r['foreign_after']
    return 'Evidence index only; independently inspect originals; no full/native package acceptance'
def controls():
    r=dict(app_sha256=APP,child_sha256=CHILD,scope='actual native controls/live IPC/app-driven child',actor='SYNTHETIC',provider='SYNTHETIC',permission_mode='SYNTHETIC',user_task_authorization_ref='SYNTHETIC',raw_refs=['SYNTHETIC'],genuine_folder_gesture_ref='SYNTHETIC',injection=False,fake_child=False,direct_cli_substitute=False,session_seconds=500,no_card_make_elevation=True,rows={n:dict(status='UNEXECUTED',raw_refs=['SYNTHETIC']) for n in ROWS},source_before='s',source_after='s',foreign_before='f',foreign_after='f')
    qualify(r)
    for key,value in [('app_sha256','0'*64),('genuine_folder_gesture_ref',''),('injection',True),('fake_child',True),('direct_cli_substitute',True),('session_seconds',601),('source_after','changed')]:
        bad=copy.deepcopy(r);bad[key]=value
        try:qualify(bad)
        except AssertionError:continue
        raise AssertionError('native evidence negative control survived: '+key)
    print('PASS native-flow evidence-index controls; ZERO Product/UI/child execution')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--emit',action='store_true');p.add_argument('--input',type=Path);a=p.parse_args()
    if a.emit:print(json.dumps(dict(rows=ROWS,app_sha256=APP,child_sha256=CHILD,positive_wav=dict(bytes=len(wav()),sha256=hashlib.sha256(wav()).hexdigest(),frames=88200),runtime_admission='NONE; capability/consent/genuine gesture prerequisite blocked'),indent=2))
    elif a.input:print(qualify(json.loads(a.input.read_text(encoding='utf-8-sig'))))
    else:controls()
