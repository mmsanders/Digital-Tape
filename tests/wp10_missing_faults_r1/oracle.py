"""New241 provenance/budget checks, delegating original host/state expectations."""
import json,hashlib
from pathlib import Path
PLAN=json.loads(Path(__file__).with_name('PLAN.json').read_text())
def check(r,row):
 assert r['requested']==dict(kind=row['kind'],ordinal=row['ordinal'])
 assert r['fault_fired'] is True and r['exit']==1
 assert r['initial_sha256']==PLAN['initial_sha256'] and r['source_wav_sha256']==PLAN['source_wav_sha256']
 assert r['successful_prefix_sha256']==row['successful_prefix_sha256']
 assert r['prior_successful_barriers']==row['prior_successful_barriers']
 assert r['history_complete'] is True and r['setup_preserved'] is True
 assert r['failure_actual_return_bytes']==0 and r['failure_os_error']
 assert r['attempted_bytes']==row['attempted_bytes']
 assert r['raw_bound'] is True and r['carried199_state_pass'] is True
 assert r['source_before_sha256']==r['source_after_sha256']==PLAN['source_wav_sha256']
 return 'new actual coordinate provenance only; raw reconstruction/original state predicate also mandatory'
class Budget:
 def __init__(self,cpu=0,compressed=0):self.cpu=cpu;self.compressed=compressed
 def admit(self,cpu,compressed):return min(cpu,compressed)>=0 and self.cpu+cpu<=7200 and self.compressed+compressed<=2*1024**3
 def charge(self,cpu,compressed):
  assert self.admit(cpu,compressed),'stop before exceeding cap'
  self.cpu+=cpu;self.compressed+=compressed
