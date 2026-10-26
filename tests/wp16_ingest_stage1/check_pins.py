"""Authenticate complete Stage1 authority, census, controls and source availability."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent

def relative_name(path,root):
    return path.relative_to(root).as_posix()

def run():
    pins=json.loads((HERE/'PINS.json').read_text(encoding='utf-8'));assert pins['status']=='STAGE1_AUTHORED' and pins['pending_cells']==0
    for name,key in [('WP16-INGEST-CONTRACT.md','contract_blob'),('WP-16.md','wp16_blob')]:
        raw=(HERE/'authority'/name).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+bytes([0])+raw).hexdigest()==pins[key],name
    census=json.loads((HERE/'CENSUS.json').read_text(encoding='utf-8'));assert len(census['rows'])==6 and len(census['cases'])==pins['case_count']==1927
    assert len({c['id'] for c in census['cases']})==1927 and not any(c.get('ruling_required') for c in census['cases'])
    assert sum(c['id'].startswith('adr180/neighbour/sowt-') for c in census['cases'])==90
    validation=json.loads((HERE/'evidence/fixture-validation.json').read_text(encoding='utf-8'));assert len(validation)==pins['source_count']==1763
    assert not any(v['check']=='PENDING_CONTRACT_RULING' for v in validation)
    assert len(json.loads((HERE/'evidence/controls.json').read_text(encoding='utf-8')))==52
    assert len(json.loads((HERE/'evidence/completion-controls.json').read_text(encoding='utf-8')))==64
    assert len(json.loads((HERE/'evidence/formats.json').read_text(encoding='utf-8')))==37
    assert len(json.loads((HERE/'evidence/calibration.json').read_text(encoding='utf-8')))==162
    assert len(json.loads((HERE/'evidence/filter-bounds.json').read_text(encoding='utf-8')))==28
    assert json.loads((HERE/'evidence/large.json').read_text(encoding='utf-8'))['actual_wav_bytes']==4294967300
    assert json.loads((HERE/'evidence/integration.json').read_text(encoding='utf-8'))['reference_cases']==10
    asset=json.loads((HERE/'ASSET.json').read_text(encoding='utf-8'));assert asset['member_count']==1765
    files=json.loads((HERE/'FILES.json').read_text(encoding='utf-8'))
    actual={relative_name(p,HERE) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='FILES.json'}
    assert set(files)==actual,'unindexed/omitted package member'
    for name,sha in files.items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha,name
    print('Stage1 authority/census/closed-file pins PASS; zero Product acceptance')
if __name__=='__main__':run()
