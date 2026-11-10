"""Declared new-plan/continuation CLI expectations; no implementation imports."""
import copy,json,re
from fixtures import *

def cases():
 out=[]
 def add(name,edit=lambda w,c,b,args:None,positive=False):out.append((name,edit,positive))
 add('new-run-without-CID',positive=True)
 add('new-run-with-CID',lambda w,c,b,a:a.extend(['--cid',CIDA]),True)
 add('known-part-and-unit-back-print',lambda w,c,b,a:(c['card_model'].update(part_number='SYNTHETIC-PART'),c['card_unit'].update(back_print=['SIM-LOT'])),True)
 for name,v in [('zero','0'),('negative','-1'),('nan','NaN'),('infinite','inf'),('nonnumeric','bad')]:add('bad-t-sched-'+name,lambda w,c,b,a,v=v:a.__setitem__(a.index('--t-sched-us')+1,v))
 add('999-new-attempts',lambda w,c,b,a:a.__setitem__(a.index('--attempts')+1,'999'))
 for v in ['wrong','',CIDA.upper()]:add('malformed-CID-'+v[:5],lambda w,c,b,a,v=v:a.extend(['--cid',v]))
 add('unknown-card-key',lambda w,c,b,a:c.update(extra=1))
 for key in ('card_model','card_unit'):add('missing-'+key,lambda w,c,b,a,key=key:c.pop(key))
 for key in ('brand_line','capacity_label','photos'):
  add('missing-model-'+key,lambda w,c,b,a,key=key:c['card_model'].pop(key))
 for key in ('brand_line','capacity_label'):add('empty-model-'+key,lambda w,c,b,a,key=key:c['card_model'].update({key:''}))
 add('empty-photo-array',lambda w,c,b,a:c['card_model'].update(photos=[]))
 add('photo-missing',lambda w,c,b,a:(w/'photo.bin').unlink())
 add('photo-bytes-mismatch',lambda w,c,b,a:(w/'photo.bin').write_bytes(b'OTHER'))
 add('photo-unknown-key',lambda w,c,b,a:c['card_model']['photos'][0].update(extra=True))
 add('unit-empty-label',lambda w,c,b,a:c['card_unit'].update(label=''))
 add('unit-back-print-not-list',lambda w,c,b,a:c['card_unit'].update(back_print='SIM'))
 add('unit-back-print-number',lambda w,c,b,a:c['card_unit'].update(back_print=[1]))
 add('build-unknown-key',lambda w,c,b,a:b.update(extra=1))
 for key in ('firmware_build','hex_sha256'):
  add('build-missing-'+key,lambda w,c,b,a,key=key:b.pop(key))
  add('build-malformed-'+key,lambda w,c,b,a,key=key:b.update({key:'UPPER'}))
 for flag,val in [('--sku','S'),('--revision','R'),('--manifest','x'),('--evidence','x')]:add('legacy-flag-'+flag,lambda w,c,b,a,flag=flag,val=val:a.extend([flag,val]))
 return out

def run(judge,work,invoke,write_case):
 obs=[]
 for name,edit,positive in cases():
  p,r,c,b,_=fixture();write_case(work,p,r);args=['plan','--method','selfrun-r1','--card','card.json','--build-record','build.json','--t-sched-us','200','--attempts','1000','--seed','7','--out','created-plan.json']
  edit(work,c,b,args);(work/'card.json').write_text(json.dumps(c));(work/'build.json').write_text(json.dumps(b));q=invoke(judge,args,work);f=work/'created-plan.json';good=(q.returncode==0 and f.exists()) if positive else (q.returncode!=0 and not f.exists() and 'Traceback' not in q.stderr)
  if positive and good:
   d=json.loads(f.read_text());good=d.get('plan_version')==5 and d.get('method')=='selfrun-r1' and d.get('card_model')==c['card_model'] and d.get('card_unit')==c['card_unit'] and d.get('firmware_build')==b['firmware_build'] and d.get('hex_sha256')==b['hex_sha256'] and d.get('card_cid')==(CIDA if name=='new-run-with-CID' else None) and d.get('t_sched_us')==200 and len(d.get('trials',[]))==1000 and len({t['iteration'] for t in d['trials']})==1000 and d.get('plan_digest')==digest(d) and re.fullmatch('selfrun-'+re.escape(c['card_unit']['label'].replace(' ','-'))+'-[0-9a-f]{16}',d.get('run_id','')) is not None
  obs.append(dict(case='plan-'+name,passed=bool(good),exit=q.returncode))
 p,r,_,_,_=fixture();write_case(work,p,r)
 for extra in [[],['--card','card.json'],['--build-record','build.json'],['--cid',CIDA],['--t-sched-us','200']]:
  f=work/'extended-plan.json'
  if f.exists():f.unlink()
  q=invoke(judge,['plan','--extend','plan.json','--attempts','4','--out','extended-plan.json',*extra],work);good=q.returncode!=0 and not f.exists() and 'Traceback' not in q.stderr
  if not extra:
   good=q.returncode==0 and f.exists()
   if good:
    d=json.loads(f.read_text());good=all(d[k]==p[k] for k in ('run_id','method','card_model','card_unit','card_cid','firmware_build','hex_sha256','t_sched_us','block','neighbour_offsets')) and d['plan_digest']==digest(d) and [t['iteration'] for t in d['trials']]==[1002,1003,1004,1005]
  obs.append(dict(case='extend-'+(extra[0] if extra else 'same-run-inherited'),passed=bool(good),exit=q.returncode))
 return obs
