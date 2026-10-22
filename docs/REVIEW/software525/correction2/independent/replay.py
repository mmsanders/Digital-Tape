"""Read both original byte sets as data; never import or run Software helpers."""
import argparse,hashlib,importlib.util,io,json,urllib.request,zipfile
from pathlib import Path
HEAD='ab3373188eddc6ba38b4fa3a95239ae4bbe346fd'
BASE='https://raw.githubusercontent.com/mmsanders/Digital-Tape/'+HEAD+'/docs/REVIEW/software525/correction1/'
def sha(b):return hashlib.sha256(b).hexdigest()
def unpack(b):
 z=zipfile.ZipFile(io.BytesIO(b));ns=z.namelist()
 assert len(ns)==len(set(ns)) and all(not n.startswith('/') and '..' not in Path(n).parts and '\\' not in n for n in ns)
 return {n:z.read(n) for n in ns}
def main():
 p=argparse.ArgumentParser();p.add_argument('--pass-archive',type=Path);p.add_argument('--fail-archive',type=Path);p.add_argument('--provider',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 good=a.pass_archive.read_bytes() if a.pass_archive else urllib.request.urlopen(BASE+'software525-correction1.zip').read()
 bad=a.fail_archive.read_bytes() if a.fail_archive else urllib.request.urlopen(BASE+'unintended-run39708908912-provider.zip').read()
 assert len(good)==106395 and sha(good)=='bfd7e10d31c5b3bdd39d3a71c4d556d325ec354fab6f9d88aee22f51e874c8bd'
 assert len(bad)==25924 and sha(bad)=='00bdcb86865e2a34c830eaf6211b17a4c484aad59d7b11c3b695e39e87ebe941'
 f=unpack(good);g=unpack(bad);assert len(f)==149 and len(g)==24
 j=lambda n:json.loads(f[n]);inv=j('FILES.json');assert len(inv)==148 and set(inv)==set(f)-{'FILES.json'}
 for n,v in inv.items():assert len(f[n])==v['bytes'] and sha(f[n])==v['sha256']
 source=j('SOURCE.json');assert source['commit']=='d5ae96d3002b751813d14a80d557b26153e8b7d6' and source['correction']=='7b4d09591753ad78841bb8da772fc2abc9d5772b'
 assert source['Product_calls']==0 and source['original38_replayed'] is False
 for n,v in source['files'].items():
  b=f['producer-source/'+n];assert len(b)==v['bytes'] and sha(b)==v['sha256']
  assert g['return/producer-source/'+n]==b
 if a.provider:
  b=a.provider.read_bytes();assert len(b)==204297 and sha(b)=='c17a600305f3b616328c41cac5b189b7a2fb28b4e52ee293feb64a097b30aa14'
  outer=unpack(b);assert outer['software525-correction1.zip']==good
  for n,b in f.items():assert outer['return/'+n]==b
  final=json.loads(outer['FINAL.json']);assert final['scan']['allocated_bytes']==1470464 and final['cpu_ns']==2707705000
 rows=j('RESULT.json')['outcomes'];assert len(rows)==10
 assert sum(n.endswith('/LAUNCH.json') and '/raw/' in n for n in f)==8
 assert sum(len(b.splitlines()) for n,b in f.items() if n.endswith('/spy.jsonl'))==20
 for name in ('before-failure','final-failure','monitor-failure'):
  prefix=name+'/raw/0001/';m=j(prefix+'RESULT.json')['measurement'];stop=j(prefix+'ACCOUNTING-STOP.json')
  assert not m['accounting_complete'] and stop['status']=='INCOMPLETE STOP'
  assert any('FileNotFoundError' in e['exception'] for e in m['errors'])
  assert j(prefix+'STOP.json')['no_further_command'] is True and not any(n.startswith(name+'/raw/0002/') for n in f)
  if name=='before-failure':assert m['pid'] is None and not any(n.startswith(prefix+'LAUNCH') for n in f)
  else:assert m['child_reaped']
  if name=='final-failure':
   assert m['allocation_after'] is None and f[prefix+'stdout.bin']==b'original\0\xffraw\n' and f[prefix+'stderr.bin']==b'original\x80diagnostic\n'
 stderr=g['stderr.bin'];assert b'AssertionError:' in stderr and b'None' in stderr and b'line 114' in stderr
 m=json.loads(g['return/handoffs/raw/0001/RESULT.json'])['measurement']
 spy=[json.loads(x) for x in g['return/handoffs/spy.jsonl'].splitlines()]
 assert {r['role'] for r in spy}=={'adapter','tracer','leaf'} and len(spy)==3
 zombies=[r for scan in m['monitor'] for r in scan['live']['rows'] if r['state']=='Z']
 assert len(zombies)==1 and zombies[0]['pid']==m['pid']==2314 and zombies[0]['role'] is None
 assert next(r for r in spy if r['role']=='adapter')['pid']==2314
 assert m['accounting_complete'] and m['child_reaped'] and m['exit']==0 and not m['errors']
 assert not any(n.endswith('/FINAL.json') or n.endswith('/FILES.json') or n.endswith('/CLOSE-build.json') for n in g)
 s=importlib.util.spec_from_file_location('independent268correction2',Path(__file__).with_name('protocol.py'));protocol=importlib.util.module_from_spec(s);s.loader.exec_module(protocol);assert protocol.selftest().startswith('PASS')
 result=dict(evidence_head=HEAD,tested_source=source['commit'],initial_run=39708669955,initial_members=149,initial_scenarios=10,initial_root_launches=8,initial_spies=20,failed_run=39708908912,failed_members=24,failed_run_disposition='FAILED producer assertion; final accounting MISSING',zombie_pid=2314,changed_A2='BOUNDED_PASS',prelaunch_cpu_binding='HELD',sampled_highwater_binding='HELD',controller_adapter='HELD',C270_dependency='NOT_SATISFIED',substantive_correction=2,max_corrections=2,Product_calls_by_review=0,logical_protocol='PASS expectations only',byte_authentication='PASS')
 a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS both original byte sets and independent logical expectations; integration HELD')
if __name__=='__main__':main()
