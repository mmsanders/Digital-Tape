import json,pathlib
from corpus import cases
from oracle import classify
rows=cases();assert len(rows)==16 and len({r['name'] for r in rows})==16
for r in rows:assert classify(r['input'])==r['expected'],r['name']
assert json.loads((pathlib.Path(__file__).parent/'CASES.json').read_text(encoding='utf-8'))==rows
print('PASS: 16 abstract controls; zero decoder executions; source derivations pending')
