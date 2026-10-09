#!/usr/bin/env python3
"""One-time release bootstrap from issued pins; no live engine expected values."""
import argparse,gzip,io,json,subprocess,tarfile,zipfile
from pathlib import Path
from check import load,require,sha

def build(product, downloads, output):
    m=load();product=Path(product);downloads=Path(downloads);downloads.mkdir(parents=True,exist_ok=True);files={}
    require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=product,text=True).strip()==m['audited_execution_commit'],'bootstrap source head')
    for suite,p in m['suites'].items():
        for name,h in p['old']['files'].items():
            b=(product/p['old']['path']/name).read_bytes();require(sha(b)==h,'old source '+name);files[suite+'/old/'+name]=b
        aid=p['new']['original_artifact_id']
        if aid:
            zp=downloads/(str(aid)+'.zip')
            if not zp.exists():
                with zp.open('wb') as f:subprocess.run(['gh','api','repos/mmsanders/Digital-Tape/actions/artifacts/'+str(aid)+'/zip'],stdout=f,check=True)
            b=zp.read_bytes();require(sha(b)==p['new']['original_zip_sha256'],'original CI ZIP');files['original-artifacts/'+zp.name]=b
            with zipfile.ZipFile(io.BytesIO(b)) as z:
                for name,h in p['new']['files'].items():
                    matches=[n for n in z.namelist() if n=='product/'+name or n.endswith('/product/'+name)]
                    require(len(matches)==1,'original CI member');files[suite+'/new/'+name]=z.read(matches[0])
        else:
            files[suite+'/new/observations.jsonl']=gzip.decompress((Path(__file__).parent/'record-source.jsonl.gz').read_bytes())
            files[suite+'/new/build-identity.json']=(json.dumps(p['new']['build_identity'],indent=2)+'\n').encode()
    for name,p in m['mutation_patches'].items():files['mutation-patches/'+name+'.patch']=(product/p['path']).read_bytes()
    require(set(files)==set(m['asset']['files']),'bootstrap member census')
    for name,b in files.items():require(sha(b)==m['asset']['files'][name],'bootstrap member identity '+name)
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w',format=tarfile.USTAR_FORMAT) as t:
        for name,b in sorted(files.items()):
            ti=tarfile.TarInfo(name);ti.size=len(b);ti.mtime=0;ti.uid=ti.gid=0;ti.mode=0o644;t.addfile(ti,io.BytesIO(b))
    b=buf.getvalue();require(len(b)==m['asset']['bytes'] and sha(b)==m['asset']['sha256'],'bootstrap whole asset');Path(output).write_bytes(b)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--product',required=True);p.add_argument('--downloads',required=True);p.add_argument('--output',required=True);a=p.parse_args();build(a.product,a.downloads,a.output)
