"""Frozen arithmetic snapshots are deliberately injected fixture counters, not host usage."""
import copy
def corpus():
 b=dict(task_cpu_ns=20,phase_cpu_ns=10,active_child_cpu_ns=2,build_reserve_ns=5,task_allocated_bytes=20,phase_allocated_bytes=10,next_cpu_ns=3,next_bytes=3,completion_cpu_ns=4,completion_bytes=4,task_limit_ns=100,phase_limit_ns=100,task_limit_bytes=100,phase_limit_bytes=100,cpu_baseline_ns=10,current_cpu_ns=20,sequence=1,expected_sequence=1,nonce='fixture268',expected_nonce='fixture268',measurement_ok=True)
 rows=[]
 def add(name,changes,expected):
  r=copy.deepcopy(b);r.update(changes);rows.append(dict(name=name,request=r,expected=expected,fixture_counters=True,helper_mode='ok'))
 # Four independent inclusive thresholds; one-unit granularity is frozen.
 for key,amount,reason in [('task_limit_ns',34,'TASK_CPU'),('phase_limit_ns',19,'PHASE_CPU'),('task_limit_bytes',27,'TASK_BYTES'),('phase_limit_bytes',17,'PHASE_BYTES')]:
  for delta,label in [(1,'below'),(0,'equal'),(-1,'above')]:add(reason.lower()+'-'+label,{key:amount+delta},'ALLOW' if delta>=0 else 'REJECT_'+reason)
 add('255-phase-exceeded-global-slack',dict(task_allocated_bytes=181616640,phase_allocated_bytes=171397120,phase_limit_bytes=16777216,task_limit_bytes=2147483648),'REJECT_PHASE_BYTES')
 add('cumulative-task-cpu',dict(task_cpu_ns=90,active_child_cpu_ns=9),'REJECT_TASK_CPU')
 add('active-child-phase-cpu',dict(active_child_cpu_ns=90,task_limit_ns=200),'REJECT_PHASE_CPU')
 add('completed-storage-exhausted',dict(task_allocated_bytes=100),'REJECT_TASK_BYTES')
 add('completion-cpu-required',dict(completion_cpu_ns=80),'REJECT_TASK_CPU')
 add('completion-storage-required',dict(completion_bytes=90),'REJECT_TASK_BYTES')
 add('build-charged-once',dict(task_limit_ns=34),'ALLOW')
 add('negative-baseline',dict(cpu_baseline_ns=-1),'REJECT_INVALID')
 add('baseline-in-future',dict(cpu_baseline_ns=21),'REJECT_BASELINE')
 add('wrong-phase-difference',dict(phase_cpu_ns=11),'REJECT_BASELINE')
 add('phase-above-task',dict(phase_cpu_ns=21,current_cpu_ns=31),'REJECT_BASELINE')
 add('phase-bytes-above-task',dict(phase_allocated_bytes=21),'REJECT_BASELINE')
 add('stale-sequence',dict(sequence=0),'REJECT_STALE')
 add('stale-session',dict(nonce='old'),'REJECT_STALE')
 add('failed-measurement',dict(measurement_ok=False),'REJECT_MEASUREMENT')
 add('missing-measurement',dict(measurement_ok=None),'REJECT_MEASUREMENT')
 add('missing-counter',dict(task_cpu_ns=None),'REJECT_INVALID')
 add('boolean-counter',dict(task_cpu_ns=True),'REJECT_INVALID')
 add('float-counter',dict(task_cpu_ns=20.0),'REJECT_INVALID')
 add('negative-reservation',dict(next_bytes=-1),'REJECT_INVALID')
 add('integer-field-overflow',dict(next_bytes=2**63),'REJECT_INVALID')
 add('sum-overflow',dict(next_bytes=2**63-1),'REJECT_OVERFLOW')
 for mode in ('nonzero','timeout','incomplete','after-raw-failure'):
  add('child-'+mode,{},'ALLOW');rows[-1]['helper_mode']=mode
 return rows
