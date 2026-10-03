#!/usr/bin/env python3
"""Paper ledger bijection + accepted-evidence identity audit; no new Product run."""
import collections
import hashlib
import json
import pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
j=json.loads((ROOT/'tests/wp11_ledgers_r63/ledger.json').read_text())
for p,h in j['pins'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
inputs=['tests/wp12_closure_r53/coverage-ledger.json','tests/wp08_mapping_r56/wp08-ledger.json','tests/wp09_gaps_r56/wp09-ledger.json']
expected=[x['id'] for p in inputs for x in json.loads((ROOT/p).read_text())['rows']]
assert collections.Counter(expected)==collections.Counter(x['id'] for x in j['rows'])
assert len(expected)==len(set(expected))==63
assert not any(x['status'] in ('gap','covered-partial+gap','uncovered: published here') for x in j['rows'])
assert sorted(x['id'] for x in j['rows'] if x['status']=='listening-held')==sorted(j['listening_held'])
wp12=[x for x in j['rows'] if x['id'].startswith(('WP12.','WP12a.'))]
assert len(wp12)==36
assert collections.Counter(x['status'] for x in wp12)=={'covered':31,'unreachable by spec':2,'vacuous by signature':3}
assert j['open_behaviour_gaps']==0
print(json.dumps({'rows':len(expected),'WP12':dict(collections.Counter(x['status'] for x in wp12)),'listening_held':j['listening_held'],'open_behaviour_gaps':0,'stage2_pending':j['stage2_pending']},sort_keys=True))
