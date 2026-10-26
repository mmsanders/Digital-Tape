"""Per-case reading of an interactions.json against the imported frozen obligations.

The imported qualifier (tests/windows_interactions_r1/contract.py --input) stops at the first
failed assertion; this lists every case so a baseline or gap is visible whole. It reads the
obligations from the imported module and adds none of its own.
"""
import importlib.util, json, sys

spec = importlib.util.spec_from_file_location('contract', sys.argv[1])
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
result = json.load(open(sys.argv[2], encoding='utf-8'))
rows, passed = {}, 0
for c in contract.CASES:
    x = result['cases'][c['id']]
    before, after, fails = x['before'], x['after'], []
    if x['event_order'] != c['steps']: fails.append('event_order')
    for o in (before, after):
        if o['make_enabled'] is not False or o['forbidden_nodes'] != []: fails.append('make_enabled/forbidden_nodes')
    fails += [f'eq {k}: {after.get(k)!r} != {w!r}' for k, w in c['eq'].items() if after.get(k, '<missing>') != w]
    fails += [f'same {k}: {before.get(k)!r} -> {after.get(k)!r}' for k in c['same'] if before.get(k) != after.get(k)]
    fails += [f'contains {k} {w}' for k, w in c['contains'].items() if not all(s in after.get(k, '') for s in w)]
    fails += [f'absent {k} {w}' for k, w in c['absent'].items() if any(s in after.get(k, '') for s in w)]
    rows[c['id']] = fails
    passed += not fails
json.dump({'source_head': result['source_head'], 'passed': passed, 'total': len(contract.CASES), 'failures': rows},
          sys.stdout, indent=1, ensure_ascii=False)
print()
