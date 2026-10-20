"""Authenticate Software485 transport/raw facts and reapply the unchanged judge.

No executable is launched. This checks a Software return, not independent acceptance.
"""
import argparse,hashlib,importlib.util,json,sys,zipfile
from pathlib import Path

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--archive',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    v=a.parse_args()
    here=Path(__file__).resolve().parent
    pin=json.loads((here/'ARTIFACT.json').read_text())
    assert v.archive.stat().st_size==pin['bytes'] and sha(v.archive)==pin['sha256']
    assert not v.out.exists(),'fresh extraction required'
    with zipfile.ZipFile(v.archive) as z:
        names=z.namelist();assert len(names)==len(set(names))
        for name in names:
            path=Path(name)
            assert not path.is_absolute() and '..' not in path.parts and ':' not in name and '\\' not in name
        z.extractall(v.out)
    root=v.out
    inventory=json.loads((root/'INVENTORY.json').read_text())
    actual={f.relative_to(root).as_posix() for f in root.rglob('*') if f.is_file()}
    assert actual==set(inventory)|{'INVENTORY.json'}
    for name,p in inventory.items():
        f=root/name;assert f.stat().st_size==p['bytes'] and sha(f)==p['sha256'],name
    method=root/'method';deps=method/'tests/wp16_shipping_exhaustion_r1'
    sys.path.insert(0,str(deps))
    import runner
    spec=importlib.util.spec_from_file_location('external232',method/'findings/P2-232-METHOD-2026-10-20/external.py')
    external=importlib.util.module_from_spec(spec);spec.loader.exec_module(external)
    identity=external.authenticate(root/'inputs/approved-kit.zip',root/'inputs/ingest.exe',root/'inputs/ordinary.wav',deps)
    candidate=root/'candidate-result'
    assert json.loads((candidate/'BINDING.json').read_text())['identity']==identity
    for name,p in json.loads((candidate/'FILES.json').read_text()).items():
        f=candidate/name;assert f.stat().st_size==p['bytes'] and sha(f)==p['sha256'],name
    result=json.loads((candidate/'RESULT.json').read_text())
    assert [r['limit_mib'] for r in result['rows']]==[None,3,4,6,8,12,64]
    positive=result['rows'][0]['pair']
    for n,row in enumerate(result['rows']):
        folder=candidate/f'row-{n}'
        for kind in ('load','case'):
            for stream in ('stdout','stderr'):
                f=folder/f'{kind}.{stream}'
                assert sha(f)==row[kind][stream+'_sha256']
                assert f.read_text(errors='replace')==row[kind][stream]
        published=folder/'published-DEST'
        pair={f.name:sha(f) for f in published.iterdir()} if published.is_dir() else None
        assert pair==row['pair'] and published.exists()==row['dest_exists']
        assert runner.judge(row,positive)==row['violations']==[]
    assert (candidate/'output/foreign').read_bytes()==b'FOREIGN SENTINEL - DO NOT MODIFY\n'
    assert result['contract_pass'] and any(r['case']['exit']==1 for r in result['rows'])
    baseline=json.loads((root/'BASELINE-ACCESS.json').read_text())
    assert baseline['actual_baseline_executed'] is False
    print('PASS: archive/inner inventory, exact kit/executable/input/judge, raw rows/pairs, unchanged seven-row judgment; fresh original RED unavailable; no executable launched')

if __name__=='__main__': main()
