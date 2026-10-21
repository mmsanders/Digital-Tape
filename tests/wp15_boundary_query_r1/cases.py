"""Finite issued §7 boundary matrix, not executed Product observations."""
import copy,json
from oracle import PHASES
def case(phase,kind,report_failure=False):
 initial=kind=='required-initial-failure';failure=kind not in ('query-success','monitor-omitted')
 changed=kind in ('positive-change','changed-plus-query-error')
 qerr='OS_QUERY_ERROR' if kind in ('required-initial-failure','monitor-failure','changed-plus-query-error') else None
 id='CARD_CHANGED' if changed else 'HOST_QUERY_FAILED' if qerr else 'REFUSE_SYSTEM_DISK' if kind=='known-policy-refusal' else None
 exit=3 if kind=='known-policy-refusal' else 1 if id else 0
 before=[] if phase=='safety' else ['earlier-committed-phase']
 error=None if id is None else dict(t='refusal',id=id,subject=None)
 if error and exit==1:
  error['phase']=phase
  if id=='HOST_QUERY_FAILED':error['op']='media_query'
  error['os_error']=qerr or 'POSITIVE_MEDIA_CHANGE'
 rows=[dict(t='start',tool='tapectl make',version='fixture',nonce='0'*32)]
 if error:rows.append(error)
 rows.append(dict(t='end',exit=exit))
 report=''.join(json.dumps(x,separators=(',',':'))+'\n' for x in rows).encode()
 return dict(id=phase+'/'+kind+('/report-write-failed' if report_failure else ''),phase=phase,initial=initial,
  required_query=initial,query_performed=kind!='monitor-omitted',query_error=qerr,positive_change=changed,
  policy_refusal='REFUSE_SYSTEM_DISK' if kind=='known-policy-refusal' else None,required_facts_known=True,
  write_mode_opens_before_query=0,destructive_ops_before_query=0,total_write_mode_opens=0,total_destructive_ops=0,
  continued_device_work=False,session_reopened=False,stdout_before_hex='75',stdout_after_hex='75',
  publication_before=before,publication_after=list(before),claimed_card_unchanged=False,
  ordinary_error=error,exit=exit,engine_error_synthesized=False,report_write_failed=report_failure,
  report_warning_count=int(report_failure),report_writes_after_failure=False,
  report_hex=('7b' if report_failure else report.hex()),version='fixture',nonce='0'*32,
  observer='compiled-test',trace_complete=True,positive_control_seen=True,raw_artifact_sha256='0'*64)
def matrix():
 rows=[]
 for phase in PHASES:
  for rf in (False,True):rows.append(case(phase,'query-success',rf))
  rows.append(case(phase,'monitor-omitted'))
  for kind in ('monitor-failure','positive-change','changed-plus-query-error'):
   for rf in (False,True):rows.append(case(phase,kind,rf))
 for kind in ('required-initial-failure','known-policy-refusal'):
  for rf in (False,True):rows.append(case('safety',kind,rf))
 return rows
