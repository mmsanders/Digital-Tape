"""APP-1A report-write failure oracle, independent of Product writer implementation.
Raw actual byte attempts, process outputs and filesystem inventories are mandatory.
"""
import json

def decode(hex):return bytes.fromhex(hex)
def same_ordinary(r):
 assert r['exit']==r['baseline_exit'],'changed ordinary outcome'
 assert r['stdout_hex']==r['baseline_stdout_hex']
 assert r['pair']==r['baseline_pair'],'changed publication bytes/presence'
 assert r['foreign_before']==r['foreign_after']
 assert r['sources_before']==r['sources_after']
 assert not r['unpublished_stage_after'],'ordinary report fault left a stage'

def warning_difference(before,after):
 """Exactly one inserted diagnostic line; no fixed implementation wording."""
 b=decode(before);a=decode(after);lines=a.splitlines(keepends=True)
 matches=[i for i,l in enumerate(lines)if l.strip() and b''.join(lines[:i]+lines[i+1:])==b]
 assert matches,'missing/extra warning or changed ordinary stderr'
 return [lines[i].decode('utf-8',errors='replace')for i in matches]

def writes(r):
 assert r['mechanism'] in ('actual-filesystem','compiled-writer-fault')
 if r['claim']=='shipping-native':assert r['mechanism']=='actual-filesystem' and r['shipping'] is True
 assert r['attempt_capture_complete'] is True
 same_ordinary(r);warning_difference(r['baseline_stderr_hex'],r['stderr_hex'])
 attempted=r['attempts'];assert attempted and r['leaf_created_exclusive'] is True
 report=b'';failed=None;types=[]
 for i,a in enumerate(attempted):
  assert failed is None,'continued report writes after first failed/short write'
  req=decode(a['requested_hex']);assert req.endswith(b'\n')
  line=json.loads(req);types.append(line['t'])
  count=a['written'];assert type(count)is int and 0<=count<=len(req)
  assert not a['error'] or count==0
  report+=req[:count]
  if a['error'] or count<len(req):failed=i
 assert failed is not None and report==decode(r['report_hex'])
 assert types[0]=='start'
 kind=r['fault_position'];assert kind in ('start','middle','end')
 if kind=='start':assert failed==0 and types[failed]=='start'
 elif kind=='middle':assert failed>0 and types[failed] not in ('start','end')
 else:
  assert failed>0 and types[failed]=='end','generic truncation is not end-record-specific'
  assert json.loads(decode(attempted[failed]['requested_hex']))['exit']==r['exit']
 return {'kind':kind,'mechanism':r['mechanism'],'failed_attempt':failed,'retained_bytes':len(report)}

def create(r):
 assert r['exit']==1 and not r['leaf_created_exclusive']
 assert r['attempts']==[] and not r['report_hex']
 assert not r['pair'] and not r['unpublished_stage_after']
 assert r['foreign_before']==r['foreign_after'] and r['sources_before']==r['sources_after']
 assert r['device_work'] is False and r['ordinary_work_started'] is False
 assert decode(r['stderr_hex']).strip(),'creation error absent'

def baseline(r):
 assert r['exit']==0 and set(r['pair'])=={'audio.wav','manifest.json'}
 raw=decode(r['report_hex']);assert raw.endswith(b'\n')
 rows=[json.loads(l)for l in raw.splitlines()];assert rows[0]['t']=='start'
 assert rows[-1]=={'t':'end','exit':0}
 assert r['foreign_before']==r['foreign_after']
