"""Six finite observer controls. Normalized facts require independent raw binding.

No native calls, captures, Product imports or inference from an empty trace.
"""
import argparse, json, re
from pathlib import Path
OBSERVER='28495e642b2a465474a4edc58380eaf8b7ee580f3fbcb4141061deadafe9b885'
CONFIG='6bc51ab36ed855ef86a903808d899ab349827122db04b7e0bb13fe285adc2f74'
ROWS=[('file-read','owned',0x80000000,True),('file-zero','owned',0,True),
 ('missing-read','missing',0x80000000,False),('nul-zero','nul',0,True),
 ('nul-read','nul',0x80000000,True),('absent-dos-zero','absent_dos',0,False)]
FAIL_RESULTS={2:{'NAME NOT FOUND','NO SUCH FILE'},3:{'PATH NOT FOUND'},5:{'ACCESS DENIED'},
 32:{'SHARING VIOLATION'},123:{'NAME INVALID','INVALID NAME'}}
def digest(s): return isinstance(s,str) and bool(re.fullmatch('[0-9a-f]{64}',s))

def judge(bundle):
 assert bundle['schema']==1 and re.fullmatch('[0-9a-f]{32}',bundle['nonce'])
 cap=bundle['capture']; assert digest(cap['csv_sha256']) and digest(cap['pml_sha256'])
 assert digest(bundle['helper_sha256']) and digest(bundle['helper_source_sha256'])
 assert [c['id'] for c in bundle['cases']]==[r[0] for r in ROWS], 'fixed six-case census'
 assert len({c['instance'] for c in bundle['cases']})==6, 'six unique process instances'
 assert len({c['pid'] for c in bundle['cases']})==6, 'no PID reuse in this short run'
 assert bundle['fixture_unchanged'] is True and bundle['foreign_unchanged'] is True
 assert bundle['dos_name_verified_absent'] is True, 'one exact-name metadata check required'
 assert bundle['dos_query_enumerated'] is False
 # Capture loss is a capability blocker, never evidence that calls were absent.
 global_hold=[]
 if cap['observer_sha256']!=OBSERVER or cap['config_sha256']!=CONFIG: global_hold.append('observer/config identity changed; old capture unqualified')
 if cap['loss_status']!='accounted_no_loss':global_hold.append('loss absent/unknown/detected')
 if not cap['loss_evidence_refs']:global_hold.append('missing loss-accounting evidence')
 if not cap['complete_process_row_census']:global_hold.append('incomplete process-row census')
 assert cap['rows_total']>=len(cap['selected_indices'])
 assert len(set(cap['selected_indices']))==len(cap['selected_indices']), 'duplicate native record index'
 all_indices=[]; outcomes=[]
 for c,(name,target,access,expect_success) in zip(bundle['cases'],ROWS):
  bad=list(global_hold); n=c['native']; p=c['process']; events=c['events']
  assert n['target']==target and n['desired_access']==access, 'wrong native target/access'
  assert n['share_mode']==7 and n['disposition']==3 and n['flags']==128
  assert n['security_null'] is True and n['template_null'] is True and n['attempts']==1
  assert n['pid']==c['pid'] and n['tid']>0 and n['instance']==c['instance']
  assert n['before']<=n['after'] and digest(n['raw_record_sha256']), 'missing native call facts'
  assert n['handle_bits'] in [32,64] and 0<=n['handle']<(1<<n['handle_bits'])
  success=n['handle']!=(1<<n['handle_bits'])-1
  assert n['outcome']==('success' if success else 'refusal'), 'forged native outcome label'
  if success: assert n['closed'] is True and n['close_result']!=0
  else: assert n['closed'] is False and 0<n['last_error']<2**32 and n['error_captured_immediately'] is True
  if success!=expect_success:bad.append('actual OS outcome differs from intended neighbour; retain actual facts')
  if not success and target in ['missing','absent_dos'] and n['last_error'] not in [2,3]:bad.append('refusal does not establish expected absent-name outcome')
  starts=[e for e in events if e['operation']=='Process Start']; exits=[e for e in events if e['operation']=='Process Exit']
  if len(starts)!=1 or len(exits)!=1:bad.append('required process start/exit absent')
  if p['image_name']!='probe-235.exe':bad.append('helper image excluded from unchanged reviewed filter')
  if len(exits)==1 and not re.search(r'Exit Status: (?:0|0x0)(?:,|$)',exits[0]['detail']):bad.append('raw process exit does not establish helper completion')
  if not p['start']<=n['before']<=n['after']<=p['end'] or p['exit']!=0:bad.append('process/call lifetime mismatch')
  marker=bundle['nonce']+':'+name
  if len(starts)==1 and marker not in starts[0]['detail']:bad.append('missing exact command nonce/case marker')
  terminal=[]
  for e in events:
   assert digest(e['raw_row_sha256']), 'missing raw event binding'
   all_indices.append(e['index'])
   if e['pid']!=c['pid'] or e['instance']!=c['instance']:bad.append('misattributed process/open')
   if e['image_name']!=p['image_name']:bad.append('misattributed image')
   end=p['end'] if e['operation'] in ['Process Start','CreateFile','Process Exit'] else p['ownership_end']
   if not p['start']<=e['time_lo']<=e['time_hi']<=end:bad.append('event outside bound process lifetime/cleanup ownership')
   if e['operation']=='CreateFile' and e['target']==target and e['result']!='REPARSE':terminal.append(e)
  if len(terminal)!=1:bad.append('open not uniquely observed; INCAPABLE, never absent')
  else:
   e=terminal[0]
   if e['time_hi']<n['before'] or e['time_lo']>n['after']:bad.append('native/open timestamp intervals do not intersect')
   if (success and e['result']!='SUCCESS') or (not success and e['result'] not in FAIL_RESULTS.get(n['last_error'],set())):bad.append('native handle/error and raw observer result disagree or mapping unknown')
   m=re.search(r'Desired Access:\s*(.*?)(?:, Disposition:|$)',e['detail'])
   if not m:bad.append('desired-access detail not observable')
   else:
    words=m.group(1).casefold()
    data_read=('generic read' in words or 'read data' in words)
    data_write=('generic write' in words or 'write data' in words)
    if data_write or (access and not data_read) or (not access and data_read):bad.append('observed desired access inconsistent with issued primitive')
   if 'Disposition: Open,' not in e['detail']:bad.append('observer open disposition missing/mismatched')
  outcomes.append(dict(id=name,actual_outcome='success' if success else 'refusal',desired_access=access,status='OBSERVED' if not bad else 'INCAPABLE_HELD',reasons=sorted(set(bad))))
 assert len(all_indices)==len(set(all_indices)), 'dropped/duplicate/aliased selected event binding'
 assert set(all_indices)==set(cap['selected_indices']), 'selected event census mismatch'
 return dict(scope='finite normalized six-control capability only; independent raw/native/source authentication required',rows=outcomes,all_primitives_observed=all(r['status']=='OBSERVED' for r in outcomes),retained_candidate_absence_cleared=False,physical_device_absence_cleared=False,pml_binary_csv_correspondence_proved=False)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 r=judge(json.loads(a.evidence.read_text(encoding='utf-8')));a.out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
