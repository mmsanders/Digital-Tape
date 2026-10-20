"""Synthetic admitted neighbours and real detecting mutations of the independent judges."""
import copy,hashlib,json
from pathlib import Path
import cases,oracle

def rejected(fn,r):
 try:fn(r)
 except (AssertionError,KeyError,ValueError):return
 raise AssertionError('undetected control')

def run():
 root=Path(__file__).parent
 for n,h in json.loads((root/'pins.json').read_text())['files'].items():assert hashlib.sha256((root/'spec'/n).read_bytes()).hexdigest()==h
 ds=cases.discovery();probes=[dict(path='fixture-'+str(i),facts=c['facts']) for i,c in enumerate(ds)]
 expected={p['path']:p['facts']['bytes'] for p in probes if oracle.prior.candidate(p['facts'])=='candidate'}
 unknown=sum(oracle.prior.candidate(p['facts'])=='unprobed' for p in probes)
 rows=[dict(t='card',path=p,bytes=b) for p,b in expected.items()]+[dict(t='summary',offered=len(expected),unprobed=unknown)]
 r=dict(exit=0,elevated=False,trace_complete=True,observer='compiled-test',positive_control_seen=True,events=[dict(op='open',device=True,access='none',role='query')],probes=probes,stdout_hex=('\n'.join(json.dumps(x)for x in rows)+'\n').encode().hex())
 oracle.cards(r);controls=0
 for edit in ['leak','provisioned','wrong-count','unknown-offered','missing-summary','write','write-open','unmount','unqualified']:
  x=copy.deepcopy(r);rr=copy.deepcopy(rows)
  if edit=='leak':rr.insert(0,dict(t='card',path='refused-device',bytes=100))
  elif edit=='provisioned':rr[0]['provisioned']=True
  elif edit=='wrong-count':rr[-1]['offered']+=1
  elif edit=='unknown-offered':rr[0]['path']=next(p['path']for p in probes if oracle.prior.candidate(p['facts'])=='unprobed')
  elif edit=='missing-summary':rr.pop()
  elif edit=='unqualified':x['positive_control_seen']=False
  else:x['events'].append(dict(op='open' if edit=='write-open' else edit,access='readwrite',device=True))
  x['stdout_hex']=('\n'.join(json.dumps(v)for v in rr)+'\n').encode().hex();rejected(oracle.cards,x);controls+=1
 f=dict(whole=True,removable=True,sd_bus=False,bytes=64000000000,holds_os=False,mounted=[],exact_layout=False,erase_matches=True)
 def report(exit,terminal=None):
  rr=[dict(t='start',tool='tapectl make',version='test-only',nonce='0'*32)]
  if terminal:rr.append(dict(t='refusal',subject=None,**terminal)) # required key order fixed below
  if terminal:rr[1]=dict(t='refusal',id=terminal['id'],subject=None,**{k:v for k,v in terminal.items()if k!='id'})
  rr.append(dict(t='end',exit=exit));return (''.join(json.dumps(v,separators=(',',':'))+'\n'for v in rr)).encode().hex()
 ev=[dict(op='safety_pass',session='q',device=True),dict(op='open',role='authorized',session='s',access='readwrite',device=True)]
 ev += [dict(op='phase',session='s',device=True,phase=p,write_callback_null=p=='verify') for p in ['provision','load','commit','verify']]
 good=dict(trace_complete=True,observer='compiled-test',positive_control_seen=True,events=ev,facts=f,exit=0,version='test-only',nonce='0'*32,report_hex=report(0),equivalent_pair=True,foreign_before='x',foreign_after='x',stdout_after_change_hex='')
 oracle.session(good)
 for edit in ['reopen','different-session','write-verify','non-null','before-safety','false-equivalence','missing-phase']:
  x=copy.deepcopy(good)
  if edit=='reopen':x['events'].append(dict(op='open',role='authorized',device=True,session='s',access='readwrite'))
  elif edit=='different-session':x['events'][-1]['session']='other'
  elif edit=='write-verify':x['events'].append(dict(op='write',device=True,session='s'))
  elif edit=='non-null':x['events'][-1]['write_callback_null']=False
  elif edit=='before-safety':x['events'].pop(0)
  elif edit=='false-equivalence':x['equivalent_pair']=False
  elif edit=='missing-phase':x['events'].pop(3)
  rejected(oracle.session,x);controls+=1
 for phase in ['provision','load','commit','verify']:
  x=copy.deepcopy(good);x.update(exit=1,report_hex=report(1,dict(id='CARD_CHANGED',phase=phase,os_error='observed-removal')))
  x['events']=ev[:2]+[dict(op='media_change',device=True,session='s',reason='removed',phase=phase,os_error='observed-removal')]
  oracle.session(x)
  for edit in ['continued','false-OK','false-id']:
   y=copy.deepcopy(x)
   if edit=='continued':y['events'].append(dict(op='read',device=True,session='s'))
   elif edit=='false-OK':y['stdout_after_change_hex']=b'OK\n'.hex()
   else:y['report_hex']=report(1,dict(id='ENGINE',phase='load',result='TAPE_ERR_IO'))
   rejected(oracle.session,y);controls+=1
 for key,v in [('whole',False),('removable',False),('bytes',2**37+1),('holds_os',True),('mounted',[2]),('erase_matches',False)]:
  x=copy.deepcopy(good);x['facts'][key]=v;id=oracle.make_policy(x['facts']);x.update(exit=3,report_hex=report(3,dict(id=id)),events=[dict(op='open',device=True,access='read',role='query')]);oracle.session(x)
  for op in ['write','unmount','open']:
   y=copy.deepcopy(x);y['events'].append(dict(op=op,device=True,access='readwrite',role='authorized'));rejected(oracle.session,y);controls+=1
 # Discovery's OS hint does not allow a mounted byte-invalid layout through make.
 assert oracle.make_policy(dict(f,mounted=[1],exact_layout=False))=='REFUSE_FOREIGN_MOUNT'
 assert oracle.make_policy(dict(f,mounted=[1],exact_layout=True)) is None
 assert oracle.make_policy(dict(f,mounted=[],exact_layout=False)) is None
 x=copy.deepcopy(good);x['facts'].update(mounted=[1],exact_layout=True,unmount_failed=True);x.update(exit=3,report_hex=report(3,dict(id='REFUSE_FOREIGN_MOUNT',unmount_failed=True)),events=[dict(op='unmount',device=True,partition=1)]);oracle.session(x)
 y=copy.deepcopy(x);y['events'][0]['partition']=2;rejected(oracle.session,y);controls+=1
 b=dict(substituted=False,foreign_before='sentinel',foreign_after='sentinel',exclusive_leaf=True,parent_identity_bound=True)
 oracle.parent_binding(b)
 for k in ['exclusive_leaf','parent_identity_bound']:
  x=dict(b,**{k:False});rejected(oracle.parent_binding,x);controls+=1
 badparent=dict(b,substituted=True,exit=1,device_work=False,foreign_leaf_created=False,foreign_deleted=False);oracle.parent_binding(badparent)
 for k,v in [('exit',0),('device_work',True),('foreign_leaf_created',True),('foreign_deleted',True),('foreign_after','changed')]:
  rejected(oracle.parent_binding,dict(badparent,**{k:v}));controls+=1
 prefix=b'uuid '+b'0'*32+b'\nepoch 1\n'
 pair=[prefix+b'p\nl\nOK\n',[b'p\n',b'l\n',b'OK\n'],0,[0,0,0],'same','same']
 oracle.equivalence(*pair)
 for i,v in [(0,prefix+b'OK\n'),(2,1),(4,'different'),(3,[0,1,0])]:
  q=copy.deepcopy(pair);q[i]=v;rejected(lambda v:oracle.equivalence(*v),q);controls+=1
 out=dict(scope='AUTHORED synthetic judges; no Product acceptance',discovery_fact_cases=len(ds),detecting_mutations=controls,fixed_plan=cases.plan())
 print(json.dumps(out,indent=2));return out
if __name__=='__main__':run()
