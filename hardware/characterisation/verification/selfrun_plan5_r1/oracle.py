"""Independent fixture oracle for declared rows, never a Product implementation."""
import math,re
from collections import Counter
from fixtures import *
def num(v):return type(v) is int and v>=0 or type(v) is float and math.isfinite(v) and v>=0
def integer(v):return type(v) is int and v>=0
def hx(v,n):return isinstance(v,str) and re.fullmatch('[0-9a-f]{'+str(n)+'}',v) is not None
ROW_KEYS=set(fixture()[1][0])

def row(r,p):
 problem=False
 problem|=set(r)!=ROW_KEYS
 problem|=type(r.get('iteration')) is not int or r.get('iteration',0)<=0
 for k,v in [('method','selfrun-r1'),('run_id',p['run_id']),('plan_digest',p['plan_digest']),('card_unit',p['card_unit']['label']),('firmware_build',p['firmware_build']),('bus_mode','spi'),('busy_line','MISO')]:problem|=r.get(k)!=v
 problem|=not integer(r.get('sck_hz')) or r.get('sck_hz',0)<=0
 for k in ('card_cid','card_cid_after_cut'):problem|=r.get(k) is not None and not hx(r[k],32)
 v=r.get('vcard_off_mv');problem|=not integer(v) or v>200
 for k in ('payload_complete','data_response_accepted','precondition_ok'):problem|=type(r.get(k)) is not bool
 n=r.get('iteration');problem|=r.get('precondition_ok') is not True
 problem|=not integer(n) or n>1000000
 if integer(n) and n<=1000000:problem|=r.get('precondition_readback_hex')!=pattern(n-1).hex()
 for k in ('precondition_readback_hex','readback_hex'):problem|=not hx(r.get(k),1024)
 for k in ('neighbours','neighbour_baseline'):
  d=r.get(k);problem|=not isinstance(d,dict) or set(d)!=set(OFFSETS)
  if isinstance(d,dict):problem|=not all(hx(v,1024) for v in d.values())
 be,bs,de,cut=[r.get(k) for k in ('busy_entry_us','busy_sampled_us','busy_deassert_us','cut_us')]
 problem|=not num(cut)
 for v in (be,bs,de):problem|=v is not None and not num(v)
 problem|=(be is None)!=(bs is None)
 init=r.get('init_ms');problem|=init is not None and not num(init)
 if not problem:
  problem|=be is not None and not (be<=bs<=cut)
  problem|=de is not None and (be is None or bs>=de)
  problem|=r['data_response_accepted'] is False and be is not None
 if problem:return False,True,None,None,False
 reason=None
 if not r['payload_complete']:reason='single-block payload not proven complete'
 elif not r['data_response_accepted']:reason='data-response token not accepted'
 elif be is None:reason='busy entry not observed'
 elif de is not None and de<=cut:reason='busy ended before the cut'
 elif cut-bs>5:reason='busy sample older than 5 us at the cut'
 data=bytes.fromhex(r['readback_hex']);old,new=pattern(n-1),pattern(n)
 if data==old:kind='OLD'
 elif data==new:kind='NEW'
 elif all(data[i:i+4] in (old[:4],new[:4]) for i in range(0,512,4)):kind='TORN'
 else:kind='CORRUPT'
 return reason is None,False,reason,kind,reason=='busy ended before the cut' and kind=='OLD'

def evaluate(p,rows):
 problems=[];q=0;seen=set();counts=Counter();miss=Counter();tears=[];corrupt=[];neigh=[];damage=[];completed=[];cids=set();cid_diff=[];maxv=0;gaps=[];speeds=set()
 planned={t['iteration'] for t in p['trials']}
 for r in rows:
  n=r.get('iteration')
  if type(n) is not int or n not in planned or n in seen:problems.append('duplicate, malformed or unplanned iteration');continue
  seen.add(n);qual,bad,why,kind,old=row(r,p)
  if bad:problems.append('invalid row');continue
  q+=qual
  if why:miss[why]+=1
  maxv=max(maxv,r['vcard_off_mv']);speeds.add(r['sck_hz'])
  if r['busy_sampled_us'] is not None:gaps.append(r['cut_us']-r['busy_sampled_us'])
  vals=[p['card_cid'],r['card_cid'],r['card_cid_after_cut']];cids.update(x for x in vals if x is not None)
  a,b=r['card_cid'],r['card_cid_after_cut']
  if a is not None and b is not None and a!=b:cid_diff.append(dict(iteration=n,kind='before_after',values=[a,b]))
  for v in (a,b):
   if p['card_cid'] is not None and v is not None and p['card_cid']!=v:cid_diff.append(dict(iteration=n,kind='vs_plan',values=[p['card_cid'],v]))
  if kind=='TORN':tears.append(n)
  if kind=='CORRUPT':corrupt.append(n)
  if old:completed.append(n);problems.append('trial '+str(n)+': completed write reads OLD (busy ended before the cut)')
  damaged=kind in ('TORN','CORRUPT')
  for off in OFFSETS:
   if r['neighbours'][off]!=r['neighbour_baseline'][off]:neigh.append([n,off]);damaged=True
  if damaged and not qual:damage.append(n)
 if seen!=planned:problems.append('missing attempt')
 if len(speeds)>1:problems.append('mixed clock')
 ok=not problems and not tears and not corrupt and not neigh and not completed and q>=1000
 return dict(verdict='PASS' if ok else 'FAIL',qualifying=q,required_qualifying=1000,problems=problems,non_qualifying=dict(miss),torn_iterations=tears,corrupt_iterations=corrupt,neighbour_damage=neigh,damage_on_non_qualifying=damage,completed_before_old=completed,cids_seen=sorted(cids),card_cid=next(iter(cids)) if len(cids)==1 else None,cid_disagreements=cid_diff,vcard_off_mv_max=maxv,sample_to_cut_us_max=max(gaps) if gaps else None)

def agrees(result,want):
 for k,v in want.items():
  if k=='problem':
   if bool(result.get('problems'))!=v:return False
  elif k=='problem_text':
   if not any(v in x for x in result.get('problems',[])):return False
  elif result.get(k)!=v:return False
 return True
