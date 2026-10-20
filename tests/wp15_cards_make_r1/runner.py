"""Authenticate and judge actual returned per-command records; no Product import.
JSON bundle transport is adapter-owned; raw files are hash-bound and stay separate.
Trace provider/source/control qualification still needs independent manual audit.
"""
import argparse,hashlib,json
from pathlib import Path
import oracle

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()

def run(root):
 b=json.loads((root/'BUNDLE.json').read_text());assert b['source_sha'] and b['binary_sha256']
 def raw(n):
  assert n in b['files'];p=(root/n).resolve();assert p.is_relative_to(root.resolve()) and p.is_file()
  assert sha(p)==b['files'][n];return p
 for n in b['files']:raw(n)
 results=[]
 for row in b['rows']:
  r=json.loads(raw(row['record']).read_text())
  for kind in ['stdout','stderr','report']:
   if kind in row:r[kind+'_hex']=raw(row[kind]).read_bytes().hex()
  if 'equivalence' in row:
   e=row['equivalence'];p=[json.loads(raw(n).read_text()) for n in e['processes']]
   assert len(p)==4
   oracle.equivalence(raw(e['stdout'][0]).read_bytes(),[raw(n).read_bytes()for n in e['stdout'][1:]],p[0]['exit'],[x['exit']for x in p[1:]],sha(raw(e['make_image'])),sha(raw(e['separate_image'])))
   r['equivalent_pair']=True
  else:r['equivalent_pair']=False
  kind=row['kind'];assert kind in ('cards','session','parent')
  result=getattr(oracle,{'cards':'cards','session':'session','parent':'parent_binding'}[kind])(r)
  results.append(dict(name=row['name'],scope=row['scope'],result=result))
 return {'scope':'bounded actual observation judgments, not overall/native acceptance','source':b['source_sha'],'binary':b['binary_sha256'],'rows':results}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('packet',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.write_text(json.dumps(run(a.packet),indent=2)+'\n')
