"""Contract arithmetic/induction-premise oracle; no Product imports or audio DSP."""
import argparse,json
from pathlib import Path
U64=2**64-1
def uint(n):return type(n) is int and 0<=n<=U64
def expected(op,a):
 if op=='pcm_count':
  n,c,w=a['bytes'],a['channels'],a['width']
  return n//(c*w) if uint(n) and c in [1,2] and w in [1,2,3,4,8] and n%(c*w)==0 else None
 if op=='append':
  c=a['channels'];b=a['blocks'];p=a['planes']
  return c in [1,2] and len(p)==c and all(len(v)==c and all(uint(n) for n in v) and len(set(v))==1 for v in b) and uint(a['raw']) and sum(v[0] for v in b)==a['raw'] and all(n==a['raw'] for n in p)
 if op=='trim':
  n,h,t=a['raw'],a['head'],a['tail']
  return n-h-t if all(uint(v) for v in [n,h,t]) and h+t<=U64 and h+t<n else None
 if op=='frames':
  n,r=a['effective'],a['rate']
  if not uint(n) or type(r) is not int or r<=0:return None
  v=(n*44100+r//2)//r
  return v if uint(v) else None
 if op=='pass_premise':return a['same_bytes'] is True and a['same_metadata'] is True
 if op=='channels':
  l,r,o=a['left'],a['right'],a['output_samples']
  return uint(l) and (r is None or r==l) and 2*l<=U64 and o==2*l
 if op=='convergence':
  # A finite abstract trace cannot justify a global finite-precision claim.
  return False if a['claimed_global'] and not a['complete_rank_argument'] else 'REQUIRES_INDEPENDENT_PROOF_REVIEW'
 raise AssertionError('unissued operation')
def compare(cases,actual):
 assert len(actual)==len(cases)==25
 for c,r in zip(cases,actual):
  v=expected(c['op'],c['args'])
  assert r['name']==c['name'] and type(r['value']) is type(v) and r['value']==v==c['expected'],c['name']
 return dict(cases=25,scope='finite arithmetic and induction-premise discriminators only',global_internal_proved=False,actual_admitted_witness=False)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('actual',type=Path);a=p.parse_args();from cases import corpus
 print(json.dumps(compare(corpus(),json.loads(a.actual.read_text()))))
