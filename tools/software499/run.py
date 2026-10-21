#!/usr/bin/env python3
"""Actual scalar/guard transport and explicitly conditional algebra certificates.

Never imports the independent expected-value function to construct an answer.
The independent comparator is called only after actual outputs are retained.
"""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PKG=ROOT/'tests/wp16_internal_invariants_r1'
sys.path.insert(0,str(PKG))
import cases

def model(c):
 a=c['args'];op=c['op']
 if op=='append':
  # Check the induction premise on each block before executing the recurrence.
  lengths=[0]*a['channels'];raw=0;valid=len(lengths) in (1,2)
  for b in a['blocks']:
   if len(b)!=len(lengths) or not b or any(x!=b[0] for x in b):valid=False;break
   lengths=[x+y for x,y in zip(lengths,b)];raw+=b[0]
  return dict(value=valid and raw==a['raw'] and lengths==a['planes'],label='proof-model only: block shape/append/raw recurrence',computed_raw=raw,computed_lengths=lengths)
 if op=='pass_premise':return dict(value=bool(a['same_bytes'] and a['same_metadata']),label='proof-model only: two explicit deterministic pass premises')
 if op=='convergence':return dict(value=False,label='proof-model only: 32 continuing steps are no ranking certificate',unresolved='No bound on finite-precision peak contraction/gated feedback for all admitted sources; abstract trace is not a production witness')
 raise AssertionError(op)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--binary',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 start=time.monotonic();rows=cases.corpus();actual=[];commands=[]
 for c in rows:
  p=c['args'];op=c['op']
  if op in ('append','pass_premise','convergence'):r=model(c)
  else:
   keys=dict(frames=['effective','rate'],trim=['raw','head','tail'],pcm_count=['bytes','channels','width'],channels=['left','right','output_samples'])[op]
   argv=[str(a.binary),op]+[str(p[k]) for k in keys]
   run=subprocess.run(argv,capture_output=True);assert run.returncode==0,(c['name'],run.stderr)
   commands.append(dict(name=c['name'],argv=argv,exit=run.returncode,stdout_hex=run.stdout.hex(),stderr_hex=run.stderr.hex()))
   r=json.loads(run.stdout)
   r['label']={'frames':'actual production dsp::output_frames','trim':'actual Decoded::finish guard, impossible empty-plane constructor; not production admission','pcm_count':'actual deinterleave on valid block plus extracted WAV caller divisibility discriminator','channels':'actual quantize plus explicit equal-plane/output-count premise discriminator'}[op]
  actual.append(dict(name=c['name'],**r))
 (a.out/'stdin.json').write_text(json.dumps(rows,indent=2)+'\n')
 (a.out/'actual.json').write_text(json.dumps(actual,indent=2)+'\n')
 (a.out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 # A small exact polynomial checker: after a complete channel/unit append,
 # (L+block)-(raw+block)=L-raw, and one/two output samples per frame.
 def sub(x,y):return tuple(i-j for i,j in zip(x,y))
 def invariant(dl,dr):return sub(dl,dr)==(0,0)
 assert invariant((1,0),(1,0))
 assert not invariant((0,0),(1,0)) # missing append control
 assert not invariant((1,0),(0,0)) # missing raw update control
 assert (2*(1)+0)==2
 # Check actual frozen adversarial discriminators, not answer corruption alone.
 by={r['name']:r for r in actual}
 assert by['missing-raw-update']['value'] is False and by['short-plane']['value'] is False
 assert by['stereo-zip-short']['actual_samples']==4 and by['stereo-zip-short']['value'] is False
 assert by['wide-intermediate-valid']['value'] is not None and by['output-overflow']['value'] is None
 assert by['changed-decode-state']['value'] is False and by['32-continues-no-ranking']['value'] is False
 pins=json.loads((PKG/'PINS.json').read_text());bound=[]
 for f in pins['files']:
  p=a.source/f['path'];b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==f['sha256'],f['path'];bound.append(dict(path=f['path'],sha256=f['sha256']))
 # Every proof refers to this authenticated source snapshot; no shipping behavior changed.
 import oracle
 verdict=oracle.compare(rows,actual)
 result=dict(**verdict,source_bindings=bound,actual_function_rows=sum(c['op']=='frames' for c in rows),guard_or_shape_discriminators=sum(c['op'] in ('trim','pcm_count','channels') for c in rows),model_rows=sum(c['op'] in ('append','pass_premise','convergence') for c in rows),induction_coefficient_checks=3,admitted_production_witness=False,global_theorem=False,wall_seconds=time.monotonic()-start,adapter_sha256=hashlib.sha256(a.binary.read_bytes()).hexdigest())
 (a.out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
 (a.out/'SHA256SUMS.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.out.iterdir() if p.is_file()},indent=2)+'\n')
if __name__=='__main__':main()
