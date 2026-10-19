import copy,json
import oracle

def reject(fn,r):
 try:fn(r)
 except (AssertionError,KeyError,ValueError):return
 raise AssertionError('mutant escaped')
def run():
 a=b'\x01\x00\x02\x00'*100;b=b'\x03\x00\x04\x00'*10
 r=dict(source_raw_before='same',source_raw_after='same',source_write_callback_null=True,source_write_events=[],source_trace_complete=True,source_positive_read_seen=True,source_ctx='src',destination_ctx='dst',source_A_sha256=oracle.digest(a),source_B_sha256=oracle.digest(b),source_A_frames=100,source_B_frames=10,source_A_mount='TAPE_OK',destination_A_mount='TAPE_OK',destination_B_mount='TAPE_OK',source_label_hex=(b'L'+bytes(31)).hex(),destination_label_hex=(b'L'+bytes(31)).hex(),destination_identity='fresh',restored_sha256='selected',selected_projection_sha256='selected')
 fn=lambda x:oracle.duplicate(x,a,b,a,a);fn(r);count=0
 for k,v in [('source_raw_after','changed'),('source_write_callback_null',False),('source_write_events',['write']),('source_trace_complete',False),('destination_ctx','src'),('destination_label_hex',bytes(32).hex()),('restored_sha256','other'),('destination_A_mount','TAPE_ERR_CRC')]:
  reject(fn,dict(r,**{k:v}));count+=1
 for da,db in [(b,a),(a,b),(a[:-4],a),(bytes(len(a)),a)]:reject(lambda x:oracle.duplicate(x,a,b,da,db),r);count+=1
 f=dict(kind='actual-fault-execution',requested=dict(kind='write',ordinal=7),fault_fired=True,exit=1,load_events=[dict(t='W',ordinal=7,failed=True)],working_effects_known=True,actual_input_sha256='pristine',pristine_input_sha256='pristine',source_wav_sha256='voice',expected_source_wav_sha256='voice',remaining_coordinate_status='executed');oracle.host_fault(f)
 for k,v in [('kind','complete-history-projection'),('fault_fired',False),('exit',0),('working_effects_known',False),('load_events',[dict(t='W',ordinal=8,failed=True)]),('actual_input_sha256','changed'),('source_wav_sha256','other')]:reject(oracle.host_fault,dict(f,**{k:v}));count+=1
 c=dict(projection_sha256='p',carried_state_judge_pass=True,commands={n:dict(input_before_sha256='p',fresh_process=True,cold_mount=True,full_seam_retained=True,write_callback_null=True,write_events=[],input_after_sha256='p')for n in ['verify','dump_A','dump_B']});oracle.command_detail(c)
 for k,v in [('input_before_sha256','changed'),('fresh_process',False),('cold_mount',False),('full_seam_retained',False),('write_callback_null',False),('write_events',['write']),('input_after_sha256','changed')]:
  x=copy.deepcopy(c);x['commands']['verify'][k]=v;reject(oracle.command_detail,x);count+=1
 budget=oracle.Budget();assert budget.admit(7200,2*1024**3);budget.charge(7200,2*1024**3);assert not budget.admit(.01,0)and not budget.admit(0,1)
 print(json.dumps(dict(scope='AUTHORED narrow supplement controls; no actual engine run',detecting_mutants=count,cap_cpu_seconds=7200,cap_compressed_bytes=2*1024**3),indent=2))
if __name__=='__main__':run()
