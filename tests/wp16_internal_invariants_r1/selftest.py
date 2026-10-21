"""Frozen challenge controls; no decoder/build/helper is executed."""
import copy,json
from pathlib import Path
from cases import corpus
from oracle import expected,compare
c=corpus()
assert c==json.loads(Path(__file__).with_name('CASES.json').read_text())
answers=[dict(name=r['name'],value=expected(r['op'],r['args'])) for r in c];compare(c,answers)
assert sum(r['expected'] is False or r['expected'] is None for r in c)>=10
for i in range(len(c)):
 bad=copy.deepcopy(answers);v=bad[i]['value'];bad[i]['value']=False if v is True else True if v is False or v is None else v+1
 try:compare(c,bad)
 except AssertionError:pass
 else:raise AssertionError('changed answer escaped')
print('PASS25 frozen challenges and25 answer-corruption controls; proof-model authoring only')
