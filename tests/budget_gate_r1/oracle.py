"""Independent pre-invocation arithmetic, not a controller/measurement implementation."""
MAX=2**63-1
FIELDS=('task_cpu_ns','phase_cpu_ns','active_child_cpu_ns','build_reserve_ns','task_allocated_bytes','phase_allocated_bytes','next_cpu_ns','next_bytes','completion_cpu_ns','completion_bytes','task_limit_ns','phase_limit_ns','task_limit_bytes','phase_limit_bytes','cpu_baseline_ns','current_cpu_ns','sequence','expected_sequence')
def decision(r):
 if any(type(r.get(k)) is not int or not 0<=r[k]<=MAX for k in FIELDS):return 'REJECT_INVALID'
 if r.get('measurement_ok') is not True:return 'REJECT_MEASUREMENT'
 if r.get('nonce')!=r.get('expected_nonce') or not r.get('nonce') or r['sequence']!=r['expected_sequence']:return 'REJECT_STALE'
 if r['cpu_baseline_ns']>r['current_cpu_ns'] or r['phase_cpu_ns']!=r['current_cpu_ns']-r['cpu_baseline_ns']:return 'REJECT_BASELINE'
 if r['task_cpu_ns']<r['phase_cpu_ns'] or r['task_allocated_bytes']<r['phase_allocated_bytes']:return 'REJECT_BASELINE'
 sums=[r['task_cpu_ns']+r['active_child_cpu_ns']+r['build_reserve_ns']+r['next_cpu_ns']+r['completion_cpu_ns'],r['phase_cpu_ns']+r['active_child_cpu_ns']+r['next_cpu_ns']+r['completion_cpu_ns'],r['task_allocated_bytes']+r['next_bytes']+r['completion_bytes'],r['phase_allocated_bytes']+r['next_bytes']+r['completion_bytes']]
 if any(x>MAX for x in sums):return 'REJECT_OVERFLOW'
 for amount,limit,name in zip(sums,[r['task_limit_ns'],r['phase_limit_ns'],r['task_limit_bytes'],r['phase_limit_bytes']],['TASK_CPU','PHASE_CPU','TASK_BYTES','PHASE_BYTES']):
  if amount>limit:return 'REJECT_'+name
 return 'ALLOW'

def check_actual(row,case):
 """An externally bound request and actual launch/spy/raw facts are required."""
 assert row['name']==case['name'] and row['request']==case['request']
 expected=decision(case['request']);assert expected==case['expected']==row['decision']
 assert row['gate']['finalized'] is True and row['gate']['pid']>0
 assert row['gate']['snapshot_before_launch'] is True
 if expected!='ALLOW':
  assert row['launches']==[] and row['spy_after']==row['spy_before'] and row['next_invocation_count']==0
 else:
  assert len(row['launches'])==1 and row['next_invocation_count']==1 and row['spy_after']==row['spy_before']+1
  assert row['launches'][0]['pid']>0 and row['launches'][0]['start_ns']>=row['gate']['end_ns']
 assert row['raw_preserved'] is True and row['stop_record_finalized'] is True
 return True
