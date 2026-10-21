"""Synthetic detecting controls only. No Win32 call/helper/capture is executed."""
import copy
from oracle import judge,ROWS,OBSERVER,CONFIG
H='a'*64
def positive():
 b=dict(schema=1,nonce='1'*32,helper_sha256=H,helper_source_sha256=H,fixture_unchanged=True,foreign_unchanged=True,dos_name_verified_absent=True,dos_query_enumerated=False,capture=dict(observer_sha256=OBSERVER,config_sha256=CONFIG,csv_sha256=H,pml_sha256=H,loss_status='accounted_no_loss',loss_evidence_refs=['synthetic'],complete_process_row_census=True,rows_total=18,selected_indices=list(range(18))),cases=[])
 for i,(name,target,access,success) in enumerate(ROWS):
  pid=100+i;instance=f'{pid}:unique';lo=1000*i
  native=dict(target=target,desired_access=access,share_mode=7,disposition=3,flags=128,security_null=True,template_null=True,attempts=1,pid=pid,tid=1,instance=instance,before=lo+20,after=lo+40,handle_bits=64,handle=123 if success else 2**64-1,outcome='success' if success else 'refusal',closed=success,close_result=1 if success else 0,last_error=0 if success else 2,error_captured_immediately=True,raw_record_sha256=H)
  events=[]
  for k,op in enumerate(['Process Start','CreateFile','Process Exit']):
   events.append(dict(index=3*i+k,pid=pid,instance=instance,image_name='probe-235.exe',time_lo=lo+[1,30,90][k],time_hi=lo+[1,30,90][k],operation=op,target=target if k==1 else '',result='SUCCESS' if success or k!=1 else 'NAME NOT FOUND',detail=b['nonce']+':'+name if k==0 else 'Exit Status: 0' if k==2 else 'Desired Access: '+('Generic Read' if access else 'Read Attributes, Synchronize')+', Disposition: Open, Options: ',raw_row_sha256=H))
  b['cases'].append(dict(id=name,pid=pid,instance=instance,native=native,process=dict(start=lo,end=lo+100,ownership_end=lo+110,exit=0,image_name='probe-235.exe'),events=events))
 return b
b=positive();assert judge(b)['all_primitives_observed']
controls=[]
def detects(name,mutate):
 x=copy.deepcopy(b);mutate(x)
 try: r=judge(x)
 except (AssertionError,KeyError):controls.append(name);return
 assert not r['all_primitives_observed'],name;controls.append(name)
detects('dropped open',lambda x:x['cases'][0]['events'].pop(1))
detects('wrong pid',lambda x:x['cases'][0]['events'][1].update(pid=999))
detects('wrong process instance',lambda x:x['cases'][0]['events'][1].update(instance='stale'))
detects('wrong desired mask',lambda x:x['cases'][1]['native'].update(desired_access=0x80000000))
detects('wrong observed desired access',lambda x:x['cases'][1]['events'][1].update(detail='Desired Access: Generic Read, Disposition: Open, Options: '))
detects('forged success label',lambda x:x['cases'][2]['native'].update(outcome='success'))
detects('forged refusal label',lambda x:x['cases'][0]['native'].update(outcome='refusal'))
detects('wrong observer outcome',lambda x:x['cases'][0]['events'][1].update(result='ACCESS DENIED'))
detects('missing native fact',lambda x:x['cases'][0]['native'].pop('handle'))
detects('missing process start',lambda x:x['cases'][0]['events'].pop(0))
detects('missing process exit',lambda x:x['cases'][0]['events'].pop(2))
detects('trace loss',lambda x:x['capture'].update(loss_status='detected'))
detects('unknown loss',lambda x:x['capture'].update(loss_status='unknown'))
detects('absent loss evidence',lambda x:x['capture'].update(loss_evidence_refs=[]))
detects('census incomplete',lambda x:x['capture'].update(complete_process_row_census=False))
detects('wrong nonce',lambda x:x['cases'][0]['events'][0].update(detail='other'))
detects('wrong time window',lambda x:x['cases'][0]['events'][1].update(time_lo=80,time_hi=80))
detects('duplicate event',lambda x:x['cases'][0]['events'][1].update(index=0))
detects('changed filter',lambda x:x['capture'].update(config_sha256='b'*64))
detects('changed observer',lambda x:x['capture'].update(observer_sha256='b'*64))
detects('wrong open flags',lambda x:x['cases'][0]['native'].update(disposition=4))
detects('unclosed owned handle',lambda x:x['cases'][0]['native'].update(closed=False))
detects('no exact-name absence proof',lambda x:x.update(dos_name_verified_absent=False))
detects('fixture damage',lambda x:x.update(fixture_unchanged=False))
detects('wrong helper image',lambda x:x['cases'][0]['process'].update(image_name='other.exe'))
detects('wrong raw image',lambda x:x['cases'][0]['events'][1].update(image_name='other.exe'))
detects('forged process exit',lambda x:x['cases'][0]['events'][2].update(detail='Exit Status: 1'))
assert len(controls)==27
assert not judge(b)['retained_candidate_absence_cleared'] and not judge(b)['pml_binary_csv_correspondence_proved']
print('PASS six synthetic neighbours and',len(controls),'detecting mutations; authoring only, no native execution')
