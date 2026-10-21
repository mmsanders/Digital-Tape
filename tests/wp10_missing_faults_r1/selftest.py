"""Synthetic provenance controls; never executed faults/coverage."""
import copy,json
from oracle import PLAN,check,Budget
rows=PLAN['rows'];old={(r['kind'],r['ordinal']) for r in PLAN['previously_executed39']}
assert len(rows)==len({(r['kind'],r['ordinal']) for r in rows})==25
assert not old.intersection((r['kind'],r['ordinal']) for r in rows) and len(old)==39
assert len(PLAN['remaining_after_selected'])==340 and PLAN['baseline_remaining']==365
controls=0
for row in rows:
 r=dict(requested=dict(kind=row['kind'],ordinal=row['ordinal']),fault_fired=True,exit=1,initial_sha256=PLAN['initial_sha256'],source_wav_sha256=PLAN['source_wav_sha256'],successful_prefix_sha256=row['successful_prefix_sha256'],prior_successful_barriers=row['prior_successful_barriers'],history_complete=True,setup_preserved=True,failure_actual_return_bytes=0,failure_os_error='synthetic-only',attempted_bytes=row['attempted_bytes'],raw_bound=True,carried199_state_pass=True,source_before_sha256=PLAN['source_wav_sha256'],source_after_sha256=PLAN['source_wav_sha256'])
 check(r,row)
 for key,value in [('fault_fired',False),('exit',0),('successful_prefix_sha256','0'*64),('setup_preserved',False),('failure_actual_return_bytes',1),('raw_bound',False),('carried199_state_pass',False),('source_after_sha256','0'*64)]:
  bad=copy.deepcopy(r);bad[key]=value
  try:check(bad,row)
  except AssertionError:controls+=1
  else:raise AssertionError(key)
 b=copy.deepcopy(r);b['requested']['ordinal']+=1
 try:check(b,row)
 except AssertionError:controls+=1
 else:raise AssertionError('wrong operation-relative coordinate')
b=Budget();b.charge(600,128*1024**2);b.charge(60,16*1024**2)
for row in rows:b.charge(row['estimated_cpu_seconds'],row['estimated_compressed_bytes'])
assert (b.cpu,b.compressed)==(3660,544*1024**2)
assert not Budget(7199,0).admit(2,0) and not Budget(0,2*1024**3).admit(0,1)
print(f'PASS25 authored rows/{controls} provenance corruptions +2 budget stops; zero newly executed faults')
