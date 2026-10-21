"""Authenticate retained baseline and frozen new coordinates, no Product run."""
import argparse,pathlib,urllib.request,hashlib,json,zipfile,gzip
from oracle import PLAN
sha=lambda b:hashlib.sha256(b).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--inputs',type=pathlib.Path,required=True);a=p.parse_args();a.inputs.mkdir(parents=True,exist_ok=True)
base='https://github.com/mmsanders/digital-tape-verification/releases/download/evidence-210-stage3-2026-10-19-55552ad/'
for name,size,digest in [('return.zip',5548911,'8a5ba21d3b0b970b8201e47048332452072d9de7dfcdaf6b6f8355738fc438de'),('load1.zip',1611126,'ad5b62a702d5e3b1fd61ca3671492abd24a032aa76fea845e1de8a5e5309afbf')]:
 f=a.inputs/name
 if not f.exists():f.write_bytes(urllib.request.urlopen(base+name,timeout=60).read())
 b=f.read_bytes();assert len(b)==size and sha(b)==digest
with zipfile.ZipFile(a.inputs/'load1.zip') as z:raw=gzip.decompress(z.read('load/part-001-02/traces/'+PLAN['original_complete_trace_sha256']+'.jsonl.gz'))
assert sha(raw)==PLAN['original_complete_trace_sha256']
trace=[json.loads(l) for l in raw.splitlines()]
with zipfile.ZipFile(a.inputs/'return.zip') as z:
 rawseam=z.read('stage3/faults/none/seam-trace.json');assert sha(rawseam)==PLAN['stage3_complete_seam_sha256']
 seam=json.loads(rawseam);record=json.loads(z.read('stage3/faults/none/record.json'))
 assert record['actual_input_sha256']==PLAN['initial_sha256'] and record['source_wav_sha256']==PLAN['source_wav_sha256']
 assert record['op_calls']==353 and record['op_barriers']==52
op=[e for e in seam['events'] if e['kind'] in ('write','flush')]
assert len(trace)==len(op)==405
catalog=json.loads(pathlib.Path(__file__).with_name('BASELINE.json').read_text());prefix=b'';barriers=[]
for i,(e,actual,c) in enumerate(zip(trace,op,catalog)):
 assert c['trace_index']==i and c['successful_prefix_sha256']==sha(prefix) and c['prior_successful_barriers']==barriers
 assert (e['t']=='W')==(actual['kind']=='write')
 if e['t']=='W':assert c['kind']=='write' and c['ordinal']==e['call'] and c['lba']==e['lba']==actual['offset']//512 and c['payload_sha256']==sha(bytes.fromhex(e['hex'])) and e['hex']==actual['data_hex']
 else:assert c['kind']=='barrier' and c['ordinal']==e['ord'];barriers.append(e['ord'])
 prefix+=json.dumps(e,sort_keys=True).encode()+b'\n'
for row in PLAN['rows']:
 c=catalog[row['trace_index']]
 assert all(row[k]==v for k,v in c.items())
print('PASS authenticated405-event baseline, exact history prefixes and25 frozen pending coordinates; no new execution')
