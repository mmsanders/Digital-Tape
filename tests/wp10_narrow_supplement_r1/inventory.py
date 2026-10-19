"""Select exact missing duplication PCM observations from already-disposed raw packets.
No campaign replay, engine import or generated new crash scenario.
"""
import hashlib,json,zipfile
from pathlib import Path
PIN='a29c01b592604163b9c311a4638acd097aba407dfa2b14616b6393ced02baf97'
FRESH='b0b1b2b3b4b5b6b7b8b9babbbcbdbebf'
def run(archive):
 b=archive.read_bytes();assert hashlib.sha256(b).hexdigest()==PIN and len(b)==1468463
 z=zipfile.ZipFile(archive);selected={};total=0
 for n in sorted(z.namelist()):
  if not n.startswith('dup/')or not n.endswith('/runs.jsonl'):continue
  part=n.rsplit('/',1)[0];rem={r['projection_sha256']:r for r in map(json.loads,z.read(part+'/remounts.jsonl').splitlines())}
  for r in map(json.loads,z.read(n).splitlines()):
   if r['scenario'][0]!='dup':continue
   for p in r['projections']:
    obs=rem[p['image_sha256']]
    if obs.get('actual_selected_uuid')!=FRESH or obs.get('actual_remount_result')!='TAPE_OK':continue
    k=p['image_sha256'];v=selected.setdefault(k,{'projection_sha256':k,'contexts':[]})
    v['contexts'].append(dict(part=part,scenario=r['scenario'],base=r['base'],initial_sha256=r['initial_sha256'],coordinate=r['coordinate'],label=r['label'],mask=p['mask'],landing_order=p['landing_order']))
    total+=1
 return dict(retained_artifact=12083282421,retained_sha256=PIN,selected_unique_destinations=len(selected),selected_contexts=total,source_image_present=False,source_callback_trace_present=False,destinations=[selected[k]for k in sorted(selected)])
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.write_text(json.dumps(run(a.archive),indent=2)+'\n')
