"""Build/fetch/authenticate the immutable generated source pack. No Product code."""
import argparse,gzip,hashlib,json,tarfile,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while block:=f.read(1024*1024):h.update(block)
    return h.hexdigest()

def build(root,archive):
    root=Path(root)
    names=['ENCODER.json','SOURCES.json']+sorted(f['path'] for f in json.loads((root/'SOURCES.json').read_text(encoding='utf-8')).values())
    with Path(archive).open('wb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=9) as z,tarfile.open(fileobj=z,mode='w|',format=tarfile.USTAR_FORMAT) as t:
        for name in names:
            p=root/name;e=tarfile.TarInfo(name);e.size=p.stat().st_size;e.mode=0o644
            with p.open('rb') as f:t.addfile(e,f)
    return {'repository':'mmsanders/Digital-Tape-Verification','tag':'evidence-ingest1-stage1-adr180','file':'INGEST1-STAGE1-SOURCES.tar.gz','bytes':Path(archive).stat().st_size,'sha256':sha_file(archive),'member_count':len(names),'sources_sha256':sha_file(root/'SOURCES.json')}

def extract(archive,destination,pin):
    assert Path(archive).stat().st_size==pin['bytes'] and sha_file(archive)==pin['sha256'],'source pack identity'
    root=Path(destination);root.mkdir(parents=True,exist_ok=True)
    with tarfile.open(archive,'r:gz') as t:
        entries=t.getmembers();assert len(entries)==pin['member_count'] and len({e.name for e in entries})==len(entries)
        for e in entries:assert e.isfile() and not Path(e.name).is_absolute() and '..' not in Path(e.name).parts
        t.extractall(root,filter='data')
    assert sha_file(root/'SOURCES.json')==pin['sources_sha256']
    facts=json.loads((root/'SOURCES.json').read_text(encoding='utf-8'));assert len(facts)+2==pin['member_count']
    for name,f in facts.items():
        p=root/f['path'];assert f['licence']=='CC0-1.0' and p.stat().st_size==f['bytes'] and sha_file(p)==f['sha256'],name
    return facts

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--build');ap.add_argument('--archive',type=Path);ap.add_argument('--destination',type=Path);ap.add_argument('--write-pin',type=Path);a=ap.parse_args()
    if a.build:
        pin=build(a.build,a.archive)
        if a.write_pin:a.write_pin.write_text(json.dumps(pin,indent=2)+'\n')
        print(json.dumps(pin));raise SystemExit
    pin=json.loads((HERE/'ASSET.json').read_text(encoding='utf-8'))
    path=a.archive or a.destination.parent/pin['file']
    if not a.archive:
        url='https://github.com/'+pin['repository']+'/releases/download/'+pin['tag']+'/'+pin['file']
        with urllib.request.urlopen(url,timeout=60) as r,path.open('wb') as f:
            while block:=r.read(1024*1024):f.write(block)
    facts=extract(path,a.destination,pin);print('Authenticated',len(facts),'CC0 source assets',pin['sha256'])
