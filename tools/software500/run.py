#!/usr/bin/env python3
"""Once-only fixed ordinary-file shipping experiment; never generates a verdict ID."""
import argparse,hashlib,json,os,resource,struct,subprocess,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PKG=ROOT/'tests/wp16_join_boundary_r1';sys.path.insert(0,str(PKG))
import cases
S1='b9f430c8c9b33532abf07eea0ed2653310639f2d'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def census(p):return {x.relative_to(p).as_posix():dict(bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(p.rglob('*')) if x.is_file()}
def cpu():
 r=resource.getrusage(resource.RUSAGE_CHILDREN);s=resource.getrusage(resource.RUSAGE_SELF);return r.ru_utime+r.ru_stime+s.ru_utime+s.ru_stime
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--binary',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists(),'refuse repeat/overwrite';a.out.mkdir(parents=True)
 rows=cases.corpus();frozen=json.loads((PKG/'MANIFEST.json').read_text());assert [cases.facts(c) for c in rows]==frozen
 version=subprocess.run([str(a.binary),'--version'],capture_output=True,check=True);(a.out/'version.stdout').write_bytes(version.stdout);(a.out/'version.stderr').write_bytes(version.stderr)
 input_pcm=sum(s['frames']*s['channels']*2 for c in rows for f in c['folders'] for s in f);assert input_pcm==634228
 ledger=[];failures=[];start=time.monotonic();used0=cpu()
 for c,facts in zip(rows,frozen):
  # Upper bound remaining single-thread execution by wall timeout; total workflow
  # timeout also bounds the four-core runner under the two-CPU-hour cap.
  if cpu()-used0+180>7200:break
  d=a.out/c['name'];d.mkdir();folders=[]
  for i,folder in enumerate(c['folders']):
   p=d/('folder'+str(i));p.mkdir();folders.append(str(p.resolve()))
   for j,s in enumerate(folder):(p/f'source{j+1:02d}.wav').write_bytes(cases.wav(s))
  for s in facts['sources']:
   ordinal,name=s['path'].split('/');p=d/('folder'+ordinal)/name;assert sha(p)==s['sha256'] and p.stat().st_size==s['bytes']
  sentinel=d/'foreign-sentinel.txt';sentinel.write_bytes(b'Software500 foreign ordinary file; preserve exactly\n');before=census(d)
  nonce=os.urandom(16).hex();report=d/'report.jsonl';dest=d/'published';argv=[str(a.binary),'--report',str(report.resolve()),'--report-nonce',nonce,'--out',str(dest.resolve()),'--length',str(c['target_seconds']),*folders]
  t=time.monotonic();u=cpu();p=subprocess.run(argv,capture_output=True,timeout=180)
  (d/'stdout.bin').write_bytes(p.stdout);(d/'stderr.bin').write_bytes(p.stderr)
  after=census(d);checks=[]
  for n,h in before.items():assert after[n]==h,(c['name'],'foreign/input changed',n)
  rr=[json.loads(l) for l in report.read_bytes().splitlines()];assert rr[0]['nonce']==nonce and rr[0]['tool']=='ingest';assert rr[-1]==dict(t='end',exit=p.returncode)
  terminal=[x for x in rr if x['t']=='refusal'];assert len(terminal)<=1
  stages=[x.name for x in d.iterdir() if x.is_dir() and '.ingest-stage-' in x.name];assert not stages
  row=dict(name=c['name'],argv=argv,nonce=nonce,exit=p.returncode,reported_version=rr[0]['version'],refusal=terminal[0] if terminal else None,wall_seconds=time.monotonic()-t,cpu_seconds=cpu()-u,before=before,after=after,stages=stages)
  try:
   if c['expect_success']:assert p.returncode==0,'wide-margin low neighbour must succeed'
   if p.returncode==0:
    assert not terminal and set(x.name for x in dest.iterdir())=={'audio.wav','manifest.json'}
    m=json.loads((dest/'manifest.json').read_bytes());wav=(dest/'audio.wav').read_bytes();pcm=wav[44:]
    header=struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',36+len(pcm),b'WAVE',b'fmt ',16,1,2,44100,176400,4,16,b'data',len(pcm))
    assert wav[:44]==header and len(pcm)==facts['total_frames']*4
    assert m['total_frames']==facts['total_frames'] and m['capacity_frames']==facts['capacity_frames'] and m['gaps']==facts['gaps']
    assert m['build_profile']=='INGEST1-AP4' and m['wav_sha256']==hashlib.sha256(wav).hexdigest()
    assert len(m['sources'])==len(facts['sources'])
    for s,o in zip(facts['sources'],m['sources']):
     assert o['logical_path']==s['path'] and o['source_sha256']==s['sha256'] and o['input_rate']==44100 and o['input_channels']==s['channels']
     assert o['raw_frames']==o['effective_frames']==o['output_frames']==s['frames'] and o['trim_head']==o['trim_tail']==0 and o['start_frame']==s['start_frame']
     assert o['applied_gain_db']<=0 and o['loudness_status']=='unmeasurable' and o['loudness_reason']=='too_short'
     block=pcm[s['start_frame']*4:(s['start_frame']+s['frames'])*4];(d/('converted-'+s['path'].replace('/','-')+'.pcm')).write_bytes(block)
     if s['channels']==1:assert all(block[i:i+2]==block[i+2:i+4] for i in range(0,len(block),4))
    for g in m['gaps']:assert not any(pcm[g['start_frame']*4:(g['start_frame']+g['frames'])*4])
    row['success_checks']='canonical pair/header/hash/source order/trim/count/gap/mono/manifest no-boost and unmeasurable fields bound'
    row['limits']='No instrumented full-precision gain/local/global meter receipt; source guard order plus actual shipping success only. Rounded manifest gain does not certify sample-exact gain reproduction or a global meter theorem.'
   else:
    assert p.returncode==2 and len(terminal)==1 and not dest.exists()
    assert terminal[0]['id'] in ('JOIN_PEAK','JOINED_PEAK','SOURCE_LEVEL')
    row['limits']='Original earlier guard/refusal retained; no source-safe global witness invented. Exact meter qualification remains independent.'
  except AssertionError as e:failures.append(dict(name=c['name'],error=str(e)))
  ledger.append(row);(d/'PROCESS.json').write_text(json.dumps(row,indent=2)+'\n')
  (a.out/'LEDGER.json').write_text(json.dumps(ledger,indent=2)+'\n')
  if failures:break # stop affected fixed experiment on first discrepancy; no tuning/retry
 result=dict(source=S1,source_ingest_tree='835078995d4e9cc2424f9ea8d6f11304b45f783f',shipping_binary_sha256=sha(a.binary),input_pcm_bytes=input_pcm,scheduled=18,executed=len(ledger),remaining=[c['name'] for c in rows[len(ledger):]],failures=failures,cpu_seconds=cpu()-used0,wall_seconds=time.monotonic()-start,outcomes={str(k):sum(r['exit']==k for r in ledger) for k in {r['exit'] for r in ledger}},global_internal_or_joined_absence_proved=False,global_witness_claimed=False)
 (a.out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');(a.out/'MANIFEST.json').write_bytes((PKG/'MANIFEST.json').read_bytes());(a.out/'REFERENCE.json').write_bytes((PKG/'REFERENCE.json').read_bytes())
 (a.out/'FILES.json').write_text(json.dumps(census(a.out),indent=2)+'\n')
 archive=a.out.parent/'software500-exact-return.zip'
 with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for f in sorted(a.out.rglob('*')):
   if f.is_file():z.write(f,f.relative_to(a.out).as_posix())
 assert archive.stat().st_size<512*1024*1024
 print(json.dumps(result,indent=2));print('ARCHIVE',archive.stat().st_size,sha(archive))
if __name__=='__main__':main()
