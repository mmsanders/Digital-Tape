"""Authoring controls only; does not call a Software controller or Product."""
import copy,json
from cases import corpus
from oracle import decision,check_actual
rows=corpus();assert len(rows)>=25 and len({r['name'] for r in rows})==len(rows)
for c in rows:assert decision(c['request'])==c['expected'],c['name']
c=rows[0];good=dict(name=c['name'],request=c['request'],decision=c['expected'],gate=dict(finalized=True,pid=1,snapshot_before_launch=True,end_ns=1),launches=[dict(pid=2,start_ns=2)],spy_before=0,spy_after=1,next_invocation_count=1,raw_preserved=True,stop_record_finalized=True);check_actual(good,c)
for key,value in [('raw_preserved',False),('spy_after',0),('next_invocation_count',2)]:
 b=copy.deepcopy(good);b[key]=value
 try:check_actual(b,c)
 except AssertionError:pass
 else:raise AssertionError(key)
c=next(r for r in rows if r['expected'].startswith('REJECT_'));bad=copy.deepcopy(good);bad.update(name=c['name'],request=c['request'],decision=c['expected'])
try:check_actual(bad,c)
except AssertionError:pass
else:raise AssertionError('post-hoc rejection with child launch admitted')
print(json.dumps(dict(frozen_cases=len(rows),authoring_only=True,software_or_product_calls=0)))
