"""Synthetic NO-NATIVE controls for independently requested256 correction1.

Imports pure Software validation/sequencing only. No child, ctypes, target,
query, token, observer or capture call; fake callbacks are explicitly labelled.
"""
import argparse,copy,hashlib,json,sys,time
from pathlib import Path
import probe
def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(v):return (json.dumps(v,sort_keys=True)+'\n').encode()
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir()
 started=time.monotonic_ns();used=time.process_time_ns();facts=[]
 for clock_fail,close_failure,valid in [(False,None,True),(True,None,True),(False,'raise',True),(False,'return',True),(True,'raise',True),(True,None,False)]:
  events=[];count=dict(clock=0,close=0,operation=0)
  native=dict(handle_raw=123 if valid else (1<<64)-1,immediate_error=None if valid else 2,valid_owned_handle=valid)
  def operation():count['operation']+=1;return copy.deepcopy(native)
  def clock():
   count['clock']+=1
   if clock_fail and count['clock']==2:raise RuntimeError('SYNTHETIC postcall-clock failure')
   return dict(qpc=count['clock'],filetime=count['clock']*100)
  def close(handle):
   count['close']+=1;assert handle==123
   if close_failure=='raise':raise RuntimeError('SYNTHETIC close wrapper failure')
   return dict(success=close_failure!='return',immediate_error=6 if close_failure=='return' else None,attempts=1)
  result=probe.retain_call(operation,clock,close,lambda e:events.append(copy.deepcopy(e)),dict(synthetic=True,operation='NO-NATIVE fake callback'))
  assert events[0]['kind']=='native-original' and events[0]['native']==native
  assert count['operation']==1 and count['close']==int(valid)
  assert result['status']==('incomplete' if clock_fail or close_failure else 'complete')
  if clock_fail:assert any(e['kind']=='incomplete-clock' for e in events)
  if close_failure=='raise':assert any(e['kind']=='incomplete-close' for e in events)
  if close_failure=='return':assert any(e['kind']=='close-original' and not e['fact']['success'] for e in events)
  facts.append(dict(synthetic=True,clock_failure=clock_fail,close_failure=close_failure,valid=valid,counts=count,original_native_survives=True,events=events,result=result))
 nonce='a'*32
 receipt=dict(status='complete',identity=dict(operation='absence-query',nonce=nonce,session_instance='synthetic-session',source_sha256='b'*64,image_sha256='c'*64,qpc_frequency=1000),native=dict(name='DTVerify235_'+nonce,buffer_wchars=4096,returned=0,immediate_error=2),before=dict(qpc=110),after=dict(qpc=120))
 session=dict(nonce=nonce,query_receipt_sha256=sha(encoded(receipt)),session_instance='synthetic-session',payload_source_sha256='b'*64,probe_image_sha256='c'*64,session_start_qpc=100,capture_start_qpc=130,qpc_frequency=1000)
 assert probe.validate_query_receipt(receipt,session,nonce,sha(encoded(receipt)))==receipt
 mutants=[]
 for section,key,value in [('after','qpc',131),('before','qpc',99),('identity','session_instance','stale-session'),('identity','nonce','d'*32),('identity','source_sha256','0'*64),('native','name','OTHER_NAME'),('native','buffer_wchars',2048),('native','returned',1),('native','immediate_error',5),('identity','qpc_frequency',999)]:
  bad=copy.deepcopy(receipt);bad[section][key]=value
  # Repair the internal receipt hash to force the ordering/semantic predicate,
  # rather than let a generic stale checksum account for every rejection.
  bound=copy.deepcopy(session);bound['query_receipt_sha256']=sha(encoded(bad))
  try:probe.validate_query_receipt(bad,bound,nonce,sha(encoded(bad)))
  except ValueError as e:mutants.append(dict(synthetic=True,section=section,key=key,value=value,rehashed_receipt=bad,rejected=True,reason=str(e)))
  else:raise AssertionError('query mutant admitted: '+key)
 assert 'ctypes' not in sys.modules
 result=dict(scope='ACTUAL OFFLINE execution on EXPLICITLY SYNTHETIC callbacks/configurations',native_calls=0,query_calls=0,token_probes=0,capture_launches=0,child_launches=0,retention_controls=facts,query_positive=receipt,query_session=session,rehashed_query_rejections=mutants,source_sha256=sha(Path(probe.__file__).read_bytes()),control_source_sha256=sha(Path(__file__).read_bytes()),parent_cpu_ns=time.process_time_ns()-used,wall_ns=time.monotonic_ns()-started,ctypes_imported=False)
 (a.out/'CONTROLS.json').write_bytes(encoded(result))
 (a.out/'FILES.json').write_bytes(encoded({'CONTROLS.json':dict(bytes=len(encoded(result)),sha256=sha(encoded(result)))}))
 print('PASS synthetic only:6 retention/failure paths,10 rehashed query/order/stale rejections; ZERO native/query/child/capture')
if __name__=='__main__':main()
