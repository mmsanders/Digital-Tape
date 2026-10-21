"""Independent ADR189 §7 extension; synthetic rows are not native acceptance."""
import importlib.util
from pathlib import Path
SPEC=Path(__file__).resolve().parents[1]/'wp15_app1a_r1/oracle.py'
s=importlib.util.spec_from_file_location('annex7_prior_immutable',SPEC)
prior=importlib.util.module_from_spec(s);s.loader.exec_module(prior)
PHASES=('safety','provision','load','commit','verify')
original_refusal=prior.refusal
prior.IDS['tapectl make'][1]=list(prior.IDS['tapectl make'][1])+['HOST_QUERY_FAILED']
def extended_refusal(r,tool,exit,folders):
 if tool=='tapectl make' and r.get('id')=='HOST_QUERY_FAILED':
  assert exit==1 and r.get('subject') is None
  assert r.get('phase') in PHASES and r.get('op')=='media_query' and isinstance(r.get('os_error'),str)
  prior.exact_keys(r,['t','id','subject','phase','op','os_error'])
 else:original_refusal(r,tool,exit,folders)
prior.refusal=extended_refusal

def check(r):
 assert r['phase'] in PHASES
 assert r['observer'] in ('compiled-test','qualified-native') and r['trace_complete'] and r['positive_control_seen']
 assert len(r['raw_artifact_sha256'])==64
 if r['initial']:
  assert r['phase']=='safety' and r['required_query'] and r['query_performed']
  assert r['write_mode_opens_before_query']==r['destructive_ops_before_query']==0
 if r['positive_change']:
  expected=('CARD_CHANGED',1)
 elif r['query_performed'] and r['query_error'] is not None:
  expected=('HOST_QUERY_FAILED',1)
 elif r['policy_refusal']:
  assert r['required_facts_known'] and r['query_error'] is None
  expected=(r['policy_refusal'],3)
 else:
  assert not r['required_query'] or r['query_performed']
  expected=(None,0)
 assert (r['ordinary_error']['id'] if r['ordinary_error'] else None,r['exit'])==expected
 if expected[0]:
  assert not r['continued_device_work'] and not r['session_reopened']
  assert r['stdout_after_hex']==r['stdout_before_hex'],'later failure must preserve earlier stdout exactly'
  assert r['publication_after']==r['publication_before'],'no rollback/claimed unchanged card'
  assert not r['claimed_card_unchanged']
  if r['initial'] or expected[1]==3:
   assert r['total_write_mode_opens']==r['total_destructive_ops']==0
  if expected[1]==1:
   e=r['ordinary_error'];assert e['subject'] is None and e['phase']==r['phase'] and isinstance(e['os_error'],str)
   assert not r['engine_error_synthesized']
   if expected[0]=='HOST_QUERY_FAILED':assert e['op']=='media_query'
 if r['report_write_failed']:
  assert r['report_warning_count']==1 and not r['report_writes_after_failure']
  # A damaged report is not required to carry a terminal ID. Actual child outcome remains above.
 else:
  assert r['report_warning_count']==0
  p=prior.parse(bytes.fromhex(r['report_hex']),'tapectl make',r['version'],r['nonce'],r['exit'])
  assert p is not None
  assert (p['refusal']['id'] if p['refusal'] else None)==expected[0]
  if expected[0]=='HOST_QUERY_FAILED':assert message(r['exit'],p)==('card-interrupted',None)
 return {'id':expected[0],'exit':expected[1],
         'app_category':'card-interrupted' if expected[0] in ('HOST_QUERY_FAILED','CARD_CHANGED') else 'card-refused' if expected[1]==3 else 'success'}

def message(exit,parsed):
 if parsed and parsed['refusal'] and parsed['refusal']['id']=='HOST_QUERY_FAILED':
  return ('card-interrupted',None)
 return prior.message('tapectl make',exit,parsed)
def parse_report(raw,version,nonce,exit):
 return prior.parse(raw,'tapectl make',version,nonce,exit)
