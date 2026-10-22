"""Original-byte review only; never execute the Software controller or helper."""
import argparse,hashlib,importlib.util,io,json,urllib.request,zipfile
from pathlib import Path
HEAD='0a0562629e4c2b99d53da62d8bb515e09ee6b72f'
BASE='https://raw.githubusercontent.com/mmsanders/Digital-Tape/'+HEAD+'/docs/REVIEW/software525/'
def sha(b):return hashlib.sha256(b).hexdigest()
def mod(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);p.add_argument('--outer',type=Path);p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 raw=a.archive.read_bytes() if a.archive else urllib.request.urlopen(BASE+'software525-exact-return.zip').read();assert len(raw)==356916 and sha(raw)=='2033b2292db4c9a4ae1ebf1873eb274b9319284459d1648b3883999009c1ef5d'
 z=zipfile.ZipFile(io.BytesIO(raw));ns=z.namelist();assert len(ns)==len(set(ns))==422 and all(not n.startswith('/') and '..' not in Path(n).parts and '\\' not in n for n in ns)
 f={n:z.read(n) for n in ns};j=lambda n:json.loads(f[n]);inv=j('FILES.json');assert set(inv)==set(f)-{'FILES.json'}
 for n,v in inv.items():assert len(f[n])==v['bytes'] and sha(f[n])==v['sha256']
 if a.outer:
  outer=a.outer.read_bytes();assert len(outer)==675826 and sha(outer)=='a0cb62fd68d47c62389cc187197c5b60e7b8aeb9cc0e6b15c117e9d945c07cc0'
  oz=zipfile.ZipFile(io.BytesIO(outer));assert oz.read('software525-exact-return.zip')==raw
  for n,b in f.items():assert oz.read('return/'+n)==b
 source=j('SOURCE.json');assert source['commit']=='f8080f2189bf7c8355adb81c4cfd2488fc955b4b' and source['method_tree']=='26ac65c74926f8b607f37412cc0ff026f231b76e'
 for n,v in source['files'].items():assert sha(f['source/'+n])==v['sha256'] and len(f['source/'+n])==v['bytes']
 pkg=a.root/'tests/budget_gate_r1'
 for n in ('cases.py','oracle.py','selftest.py','helper.py','README.md','PINS.json','SHA256SUMS'):assert f['source/tests/budget_gate_r1/'+n]==(pkg/n).read_bytes()
 sys_path=str(pkg.resolve());import sys;sys.path.insert(0,sys_path)
 cases=mod('frozen268cases',pkg/'cases.py');oracle=mod('frozen268oracle',pkg/'oracle.py');corpus=cases.corpus();rows=j('CORPUS.json');assert len(rows)==len(corpus)==38
 children=set();controllers=set()
 for row,case in zip(rows,corpus):
  oracle.check_actual(row,case);name=case['name'];pre=j(name+'-PRE.json');process=j(name+'-PROCESS.json');request=f[name+'-request.json']
  assert json.loads(request)==case['request'] and process['exit']==0 and process['pid']==row['gate']['pid'] and row['gate']['request_sha256']==sha(request)
  assert row['gate']['source_sha256']==source['files']['host/budget-controller/controller.py']['sha256'] and row['gate']['interpreter_sha256']==source['interpreter_sha256']
  assert pre['source']==source['commit'] and pre['request_sha256']==sha(request) and pre['parent']==process['parent']
  assert pre['start_ns']<=row['gate']['end_ns']<=process['end_ns'];controllers.add(process['pid'])
  prefix='cases/'+name+'/';assert j(prefix+'GATE.json')==row['gate'] and j(prefix+'RESULT.json')==row and f[prefix+'request.json']==request
  if case['expected']=='ALLOW':
   launch=j(prefix+'LAUNCH.json');assert row['launches']==[launch] and launch['parent']==process['pid'];children.add(launch['pid'])
   spy=[json.loads(x) for x in f[prefix+'spy.jsonl'].splitlines()];assert spy==[dict(pid=launch['pid'],nonce=case['request']['nonce'])]
   head,body=f[prefix+'stdout.bin'].split(b'\n',1);h=json.loads(head);assert h==dict(pid=launch['pid'],parent=process['pid'],nonce=case['request']['nonce']) and body==b'\x00\xffretained\n' and f[prefix+'stderr.bin']==b'\x80diagnostic\n'
   for n,v in row['raw'].items():assert len(f[prefix+n])==v['bytes'] and sha(f[prefix+n])==v['sha256']
   measurement=row['measurement'];assert measurement['pid']==launch['pid'] and measurement['child_cpu_ns']>=0
   if case['helper_mode']!='ok':
    assert row['session_stopped'] and row['second_command_spy_unchanged'] and row['second_command_refusal']
    if case['helper_mode']=='timeout':assert measurement['reason']=='timeout' and measurement['exit']<0
    elif case['helper_mode']=='incomplete':assert not measurement['accounting_complete'] and measurement['injected_final_sensor_failure']
    else:assert measurement['exit']==7
  else:assert not any(n in f for n in (prefix+'LAUNCH.json',prefix+'spy.jsonl',prefix+'stdout.bin'))
 assert len(children)==13 and len(controllers)==38
 for m in j('MUTATIONS.json'):
  data=f[m['name']+'-mutation.json'];assert sha(data)==m['sha256'];bad=json.loads(data);case=next(c for c in corpus if c['name']==m['external_original_name']);detected=False
  try:
   oracle.check_actual(bad,case)
   assert bad['measurement']['child_cpu_ns'] is not None
   for n,v in bad['raw'].items():assert sha(f['cases/'+bad['name']+'/'+n])==v['sha256']
  except (AssertionError,KeyError,TypeError):detected=True
  assert detected and m['detected']
 sensors=j('SENSORS.json');assert sensors['terminal'] and sensors['next_refused'] and sensors['failed_scan']
 for snap in sensors['snapshots']:
  scan=snap['scan'];assert scan['allocated_bytes']==sum(r['blocks']*512 for r in scan['rows']) and not scan['errors']
  assert len({r['path'] for r in scan['rows']})==len(scan['rows']) and all(r['allocated']==r['blocks']*512 for r in scan['rows'])
 last={r['path']:r for r in sensors['snapshots'][-1]['scan']['rows']};x=last['sensors/original.raw'];y=last['sensors/alias.raw'];assert x['inode']==y['inode'] and x['links']==y['links']==2 and x['allocated']==y['allocated']
 assert sensors['sparse']['logical']==1048576 and sensors['sparse']['allocated']==4096 and sha(f['sensors/original.raw'])==sensors['retained_original_sha256']
 cpu=j('CPU-SENSOR.json');assert cpu['after_ns']-cpu['before_ns']==cpu['increment_ns']>0
 controller=f['source/host/budget-controller/controller.py'].decode();readme=f['source/host/budget-controller/README.md'].decode()
 assert "if any(p['pid'] != proc.pid for p in live['processes'])" in controller and "reason = 'unexpected-descendant'" in controller
 assert 'production phase transition\nadapter is NOT implemented here' in readme
 assert controller.index('    final_scan = census(output)')>controller.index('        except BaseException as e:')
 assert "measurement['injected_final_sensor_failure'] = True" in controller
 result=dict(verdict='PARTIAL standalone helper facts PASS; C adapter and final-accounting dependency HELD, correction1/2',archive_members=422,controller_invocations=38,actual_helpers=13,corruptions_detected=6,real_sensor_snapshots=3,cpu_increment_ns=cpu['increment_ns'],product_invocations=0,correction='Source-bind C task/phase/whole-root/process-tree adapter with harmless mechanics. Also retain incomplete STOP on actual final census/measurement exception; current final_scan is outside handler and incomplete control only relabels a successful measurement.',limitations='No hard overshoot or arbitrary-descendant accounting. No generic native argv, production cost upper bound, C execution or Product integration clearance.')
 a.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
