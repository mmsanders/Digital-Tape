import hashlib,json,pathlib
from oracle import reserve,admit
p=pathlib.Path(__file__).resolve().parent;plan=json.loads((p/'PLAN.json').read_text())
base=p.parent/'wp10_missing_faults_r1'
assert hashlib.sha256((base/'BASELINE.json').read_bytes()).hexdigest()==plan['baseline_sha256']
b=json.loads((base/'BASELINE.json').read_text());old=json.loads((base/'PLAN.json').read_text())
accepted={(r['kind'],r['ordinal']) for r in old['previously_executed39']}|{('write',19),('write',63)}
assert [(r['kind'],r['ordinal']) for r in plan['rows']]==[('write',64),('write',346),('write',351),('barrier',50)]
active=[];found=[]
for r in b:
 if r['kind']=='write':active.append(r)
 for row in plan['rows']:
  if (r['kind'],r['ordinal'])==(row['kind'],row['ordinal']):
   assert (r['kind'],r['ordinal']) not in accepted
   for key in ('trace_index','successful_prefix_sha256','prior_successful_barriers','attempted_bytes'):
    assert row[key]==r[key]
   assert len(active)==1 and row['model_order_class_bound']==2
   assert reserve(2)==(row['reserved_cpu_seconds'],row['reserved_bytes']);found.append(row)
 if r['kind']=='barrier':active=[]
assert len(found)==4
cpu=660+sum(r['reserved_cpu_seconds'] for r in plan['rows'])
storage=144*1024**2+sum(r['reserved_bytes'] for r in plan['rows'])
assert cpu==1188 and storage==272*1024**2 and admit(0,0,cpu,storage)
for args in [(7200,0,1,0),(0,2*1024**3,0,1),(7199,0,1,0,1,0),(0,0,-1,0),(float('nan'),0,0,0)]:assert not admit(*args)
assert admit(7199,0,1,0) and not admit(7100,0,132,0)
try:reserve(3)
except AssertionError:pass
else:raise AssertionError('unreserved projection admitted')
print('PASS:4 unexecuted coordinates,2 classes each,1188CPU/272MiB reservations; no fault execution')
