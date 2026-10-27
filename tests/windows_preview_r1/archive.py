"""Bounded portable preview inventory/provenance predicates. No extraction or launch."""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import zipfile

MEMBERS={'digital-tape.exe','ingest.exe','tapectl.exe','BUILD.json','README.txt'}
HERE=Path(__file__).resolve().parent


def check(data,registry):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert len(z.infolist())==5 and set(z.namelist())==MEMBERS
        for entry in z.infolist():
            assert entry.filename==Path(entry.filename).name and not entry.is_dir()
            assert ((entry.external_attr>>16)&0o170000)!=0o120000, 'archive link refused'
        assert z.getinfo('BUILD.json').file_size<=65536 and z.getinfo('README.txt').file_size<=65536
        b=json.loads(z.read('BUILD.json').decode('utf-8-sig'));guide=z.read('README.txt').decode('utf-8-sig')
        p=b['preview'];assert p['kind']=='unsigned Windows11 x64 developer preview'
        assert p['unsigned'] and not p['make_enabled'] and not p['installer'] and not p['runtime_download']
        assert p['working_paths']=='per-user app private; children relative to executable'
        assert p['demonstrated'] and set(p['demonstrated'])<=set(registry['allowed_claims'])
        assert set(registry['required_exclusions'])<=set(p['exclusions'])
        assert p['ui_status']=='UNEXECUTED' or 'actual UI' not in registry['required_exclusions']
        assert p['startup_failure_guidance'] and p['raw_details_scope']
        assert guide.strip() and all(word in guide.lower() for word in ['unsigned','preview','webview2','make','disabled'])
        for name,known in registry['components'].items():
            entry=z.getinfo(name);assert entry.file_size==known['bytes']
            assert hashlib.sha256(z.read(name)).hexdigest()==known['sha256'],name
            assert p['component_publications'][name]==known['publication']
            actual=next(x for x in b['files'] if x['name']==name)
            assert actual['bytes']==known['bytes'] and actual['sha256']==known['sha256']
        assert len(b['files'])==3
        assert b['source_head']==registry['components']['digital-tape.exe']['source']
        assert b['s1_source']==registry['components']['ingest.exe']['source']
        assert b['tapectl_source']==registry['components']['tapectl.exe']['source']
        assert b['child_pin']==registry['components']['ingest.exe']['sha256']
        assert b['child_version']=='0.1.1 INGEST-1 arithmetic-profile INGEST1-AP4'
        assert b['s1_tree']=='835078995d4e9cc2424f9ea8d6f11304b45f783f'
    return 'ONLY registry-bound unsigned preview packaging; actual functions require independent original evidence'


def controls():
    # Synthetic archive-data qualification only; these bytes are never executable.
    blobs={name:b'SYNTHETIC archive data, not an executable: '+name.encode() for name in MEMBERS if name.endswith('.exe')}
    registry=dict(components={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),source='a'*40,publication='b'*40) for name,data in blobs.items()},
                  allowed_claims=['normal quit'],required_exclusions=['actual UI','shipping Make'])
    preview=dict(kind='unsigned Windows11 x64 developer preview',unsigned=True,make_enabled=False,installer=False,runtime_download=False,
                 working_paths='per-user app private; children relative to executable',demonstrated=['normal quit'],exclusions=['actual UI','shipping Make'],
                 ui_status='UNEXECUTED',startup_failure_guidance='retained failure details',raw_details_scope='raw stderr only',component_publications={name:'b'*40 for name in blobs})
    build=dict(preview=preview,files=[dict(name=name,bytes=known['bytes'],sha256=known['sha256']) for name,known in registry['components'].items()],
               source_head='a'*40,s1_source='a'*40,tapectl_source='a'*40,child_pin=registry['components']['ingest.exe']['sha256'],
               child_version='0.1.1 INGEST-1 arithmetic-profile INGEST1-AP4',s1_tree='835078995d4e9cc2424f9ea8d6f11304b45f783f')
    def archive(b,extra=None):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for name,data in blobs.items():z.writestr(name,data)
            z.writestr('BUILD.json',json.dumps(b));z.writestr('README.txt','Unsigned developer preview. Existing WebView2. Make disabled.')
            if extra:z.writestr(extra,b'no extra files')
        return out.getvalue()
    check(archive(build),registry)
    mutations=[]
    for key,value in [('make_enabled',True),('unsigned',False),('runtime_download',True),('demonstrated',['actual UI']),('exclusions',[])]:
        b=copy.deepcopy(build);b['preview'][key]=value;mutations.append(archive(b))
    b=copy.deepcopy(build);b['source_head']='c'*40;mutations.append(archive(b))
    mutations.append(archive(build,'../outside.exe'))
    for data in mutations:
        try:check(data,registry)
        except AssertionError:continue
        raise AssertionError('Unsafe/unproven preview control survived')
    print('PASS closed archive/source/claim/Make causal controls; ZERO Product/extraction/UI execution')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);p.add_argument('--clearances',type=Path,default=HERE/'clearances.json');a=p.parse_args()
    if a.archive:print(check(a.archive.read_bytes(),json.loads(a.clearances.read_text())))
    else:controls()
