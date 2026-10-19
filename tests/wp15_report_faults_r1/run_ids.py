"""Four narrow actual-shipping host commands, no device or full census campaign."""
import argparse,hashlib,json,subprocess,platform,sys
from pathlib import Path
import id_inputs

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(binary,out):
 assert binary.is_file() and not out.exists();out.mkdir(parents=True)
 (out/'ingest').write_bytes(binary.read_bytes()) # preserve exact independently built bytes outside git
 version=subprocess.check_output([str(binary),'--version']).decode().strip()
 rows=id_inputs.generate(out/'sources');rows.append(dict(name='empty-dest',folder=str(out/'sources/quiet64'),expected_exit=2))
 result=[]
 for row in rows:
  d=out/row['name'];d.mkdir();control=d/'control';control.mkdir();report=control/'report.jsonl';dest=d/'DEST'
  sentinel=d/'foreign';sentinel.write_bytes(b'foreign unchanged\n');before=sha(sentinel)
  argv=[str(binary),'--out',''if row['name']=='empty-dest' else str(dest),'--length','1','--report',str(report),'--report-nonce','0'*32,row['folder']]
  p=subprocess.run(argv,cwd=d,capture_output=True)
  (d/'stdout').write_bytes(p.stdout);(d/'stderr').write_bytes(p.stderr)
  assert p.returncode==row['expected_exit'],(row,p.returncode,p.stderr)
  lines=[json.loads(s)for s in report.read_text().splitlines()];assert lines[0]['t']=='start'and lines[-1]==dict(t='end',exit=p.returncode)
  refusal=next((r for r in lines if r['t']=='refusal'),None)
  if row['name']=='tiny64':assert refusal and refusal['id']=='SOURCE_LEVEL' and refusal['subject']=='0/x.wav'
  elif row['name']=='empty-dest':assert refusal and refusal['id']=='DEST_NAME_INVALID' and refusal['subject']is None
  else:assert refusal is None and {v.name for v in dest.iterdir()}=={'audio.wav','manifest.json'}
  if p.returncode:assert not dest.exists()
  assert sha(sentinel)==before and not list(d.glob('.*.ingest-stage-*'))
  entry=dict(name=row['name'],argv=argv,binary_sha256=sha(binary),version=version,exit=p.returncode,refusal=refusal,stdout_sha256=sha(d/'stdout'),stderr_sha256=sha(d/'stderr'),report_sha256=sha(report),pair={n:sha(dest/n)for n in ['audio.wav','manifest.json']}if dest.exists()else{},source_sha256=sha(Path(row['folder'])/'x.wav'),foreign_before=before,foreign_after=sha(sentinel))
  (d/'process.json').write_text(json.dumps(entry,indent=2)+'\n');result.append(entry)
 (out/'RESULT.json').write_text(json.dumps(dict(scope='four actual narrow shipping-ID/valid neighbours; not numerical/native/full acceptance',source='b9f430c8c9b33532abf07eea0ed2653310639f2d',platform=platform.platform(),binary_sha256=sha(binary),rows=result),indent=2)+'\n')
 print(json.dumps([{k:r[k]for k in ['name','exit','refusal']}for r in result],indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.binary.resolve(),a.out.resolve())
