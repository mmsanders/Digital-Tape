"""Public hash-authenticated fallback transport only; never builds/replaces the executable."""
from pathlib import Path
import hashlib,urllib.request,zipfile
from runner import BASE
p=Path('baseline-packet-small.zip')
with urllib.request.urlopen('https://github.com/mmsanders/Digital-Tape/releases/download/win11-small-packet/packet-small.zip',timeout=60) as r,p.open('wb') as f:
 while b:=r.read(1024*1024):f.write(b)
assert hashlib.sha256(p.read_bytes()).hexdigest()=='9b44ebeb71e61978414791d8edbd5b9af1882696008bfd1a9b6baaae869b27c2'
with zipfile.ZipFile(p) as z:
 matches=[i for i in z.infolist() if i.filename.replace('\\','/').split('/')[-1]=='ingest.exe' and hashlib.sha256(z.read(i)).hexdigest()==BASE]
 assert len(matches)==1,'Public transport lacks exact original executable: capability stop'
 Path('baseline-kit').mkdir(exist_ok=True);Path('baseline-kit/ingest.exe').write_bytes(z.read(matches[0]))
print('Authenticated original shipping executable; public fallback archive pin verified')
