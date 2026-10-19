"""Narrow raw source/PCM and actual host-fault predicates. No engine implementation.
Earlier199/model/source fixtures remain authoritative; no universal unchanged-card oracle.
"""
import hashlib

def digest(b):return hashlib.sha256(b).hexdigest()

def duplicate(r,source_a,source_b,dest_a,dest_b):
 assert r['source_raw_before']==r['source_raw_after'],'source raw mutation'
 assert r['source_write_callback_null']is True and r['source_write_events']==[]
 assert r['source_trace_complete']is True and r['source_positive_read_seen']is True
 assert r['source_ctx']!=r['destination_ctx'],'alias'
 assert r['source_A_sha256']==digest(source_a) and r['source_B_sha256']==digest(source_b)
 assert r['source_A_frames']*4==len(source_a) and r['source_B_frames']*4==len(source_b)
 assert r['source_A_mount']=='TAPE_OK' and r['destination_A_mount']==r['destination_B_mount']=='TAPE_OK'
 # A fresh duplicate copies source A, never whichever source side happens to be current.
 assert dest_a==dest_b==source_a,'wrong complete PCM/count or selected source side'
 label=bytes.fromhex(r['source_label_hex']);assert len(label)==32
 assert bytes.fromhex(r['destination_label_hex'])==label,'label copy'
 assert r['destination_identity']=='fresh' and r['restored_sha256']==r['selected_projection_sha256']
 return 'PASS exact retained source/label/PCM binding'

def host_fault(r):
 assert r['kind']=='actual-fault-execution','projection is not interruption execution'
 assert r['requested']['kind']in ('write','barrier') and type(r['requested']['ordinal'])is int
 assert r['fault_fired']is True and r['exit']==1
 events=r['load_events'];key='W'if r['requested']['kind']=='write'else'F'
 matches=[e for e in events if e['t']==key and e['ordinal']==r['requested']['ordinal']]
 assert len(matches)==1 and matches[0]['failed']is True,'wrong/no actual callback failure'
 assert r['working_effects_known']is True,'resolve actual failed-write effects before projection'
 assert r['actual_input_sha256']==r['pristine_input_sha256']
 assert r['source_wav_sha256']==r['expected_source_wav_sha256']
 assert r['remaining_coordinate_status']in ('executed','unexecuted','proved-unavailable')
 return 'PASS actual requested fault provenance; state judged separately by carried model'

def command_detail(r):
 assert set(r['commands'])=={'verify','dump_A','dump_B'}
 for name,c in r['commands'].items():
  assert c['input_before_sha256']==r['projection_sha256']
  assert c['fresh_process']is True and c['cold_mount']is True
  assert c['full_seam_retained']is True
  if name=='verify':
   assert c['write_callback_null']is True and c['write_events']==[]
   assert c['input_after_sha256']==r['projection_sha256']
 # Existing199 allowed audio/state predicate is required separately, not replaced by provenance.
 assert r['carried_state_judge_pass']is True
 return 'PASS per-command fresh-input/seam facts'

class Budget:
 def __init__(self):self.cpu=0.0;self.compressed=0
 def admit(self,estimated_cpu,estimated_bytes):
  assert estimated_cpu>=0 and estimated_bytes>=0
  return self.cpu+estimated_cpu<=7200 and self.compressed+estimated_bytes<=2*1024**3
 def charge(self,cpu,compressed):
  assert cpu>=0 and compressed>=0
  self.cpu+=cpu;self.compressed+=compressed
  assert self.cpu<=7200 and self.compressed<=2*1024**3,'cap reached: stop execution, retain partial map'
