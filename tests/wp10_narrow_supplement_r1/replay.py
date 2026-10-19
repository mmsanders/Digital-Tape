"""Hash-bound narrow supplement replay. All engines are prior independent Python models."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
import oracle
ROOT=Path(__file__).resolve().parents[2]
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
M=load(ROOT/'tests/wp10_residue_d10/pins.py','independent_residue_pins').M

def digest(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def bind_image(raw,pcm_a,pcm_b):
 assert len(raw)==(M.MIRROR+1)*512,'outside carried fixed fixture geometry'
 img={k:raw[l*512:(l+1)*512]for k,l in M.TRACKED.items()}
 for side,pcm in [('A',pcm_a),('B',pcm_b)]:
  c=M.classify(img,side,False);assert c['result']==('TAPE_OK',),c
  assert M.rendered_sha256(img,c['layout'])==oracle.digest(pcm),'raw image/PCM mismatch'
 chosen=max([img[k]for k in ['P','M']if M.sb_valid(img[k])],key=M.gen)
 return chosen[M.LABEL_OFFSET:M.LABEL_OFFSET+M.LABEL_BYTES]

def run(root):
 b=json.loads((root/'BUNDLE.json').read_text());files=b['files']
 def raw(n):
  assert n in files;p=(root/n).resolve();assert p.is_relative_to(root.resolve())and p.is_file();assert digest(p)==files[n];return p
 for n in files:raw(n)
 out=[]
 for row in b['duplicate_rows']:
  r=json.loads(raw(row['record']).read_text());sa,sb,da,db=[raw(row[k]).read_bytes()for k in ['source_A_pcm','source_B_pcm','dest_A_pcm','dest_B_pcm']]
  src=raw(row['source_before']);dst=raw(row['destination']);r['source_raw_before']=digest(src);r['source_raw_after']=digest(raw(row['source_after']))
  r['source_label_hex']=bind_image(src.read_bytes(),sa,sb).hex()
  r['destination_label_hex']=bind_image(dst.read_bytes(),da,db).hex()
  r['source_A_sha256']=oracle.digest(sa);r['source_B_sha256']=oracle.digest(sb)
  r['restored_sha256']=digest(dst)
  allowed={x['projection_sha256']for x in json.loads((Path(__file__).parent/'SELECTED-DESTINATIONS.json').read_text())['destinations']}
  assert r['selected_projection_sha256']in allowed
  out.append(dict(name=row['name'],result=oracle.duplicate(r,sa,sb,da,db)))
 for row in b['fault_rows']:out.append(dict(name=row['name'],result=oracle.host_fault(json.loads(raw(row['record']).read_text()))))
 # Full original observation rows must be independently replayed by199 load_rows.check;
 # no candidate-provided 'carried_state_judge_pass' is accepted here.
 saved=list(sys.path);sys.path.insert(0,str(ROOT/'findings/P2-SUBSET-ROWS-2026-10-17'))
 try:legacy=load(ROOT/'findings/P2-SUBSET-ROWS-2026-10-17/load_rows.py','carried_load_rows')
 finally:sys.path[:]=saved
 for row in b['command_rows']:
  r=json.loads(raw(row['record']).read_text());old=json.loads(raw(row['original_observation']).read_text());legacy.check(old);r['carried_state_judge_pass']=True
  for name,paths in row['raw_inputs'].items():
   r['commands'][name]['input_before_sha256']=digest(raw(paths['before']))
   r['commands'][name]['input_after_sha256']=digest(raw(paths['after']))
  out.append(dict(name=row['name'],result=oracle.command_detail(r)))
 return dict(scope='bounded narrow raw replay; provider/source qualification and native/full acceptance separate',rows=out)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('packet',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.write_text(json.dumps(run(a.packet),indent=2)+'\n')
