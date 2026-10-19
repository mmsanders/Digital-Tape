"""Fetch/authenticate only retained narrow input ZIPs; no campaign execution."""
import argparse,hashlib,json,urllib.request
from pathlib import Path
import inventory
PINS=[('retained-small.zip',1468463,'a29c01b592604163b9c311a4638acd097aba407dfa2b14616b6393ced02baf97'),('retained-load0.zip',2234288,'2bfe1814312d622cb010d2571e6b977b5125fc07f7ead9301765d167a86bf6c9')]
def run(release,out):
 out.mkdir(parents=True,exist_ok=True)
 for n,size,sha in PINS:
  p=out/n
  if not p.exists():
   with urllib.request.urlopen(release.rstrip('/')+'/'+n,timeout=60)as r,p.open('wb')as f:
    while b:=r.read(1024*1024):f.write(b)
  assert p.stat().st_size==size and hashlib.sha256(p.read_bytes()).hexdigest()==sha
 actual=inventory.run(out/'retained-small.zip');expected=json.loads((Path(__file__).parent/'SELECTED-DESTINATIONS.json').read_text());assert actual==expected
 print('Authenticated both retained inputs and exact two-image/81-context selection; no engine run')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.release,a.out)
