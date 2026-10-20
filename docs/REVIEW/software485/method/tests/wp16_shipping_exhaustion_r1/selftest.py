"""Causal oracle controls, distinct from actual shipping execution."""
import copy
from runner import judge
pair={'audio.wav':'a','manifest.json':'b'}
good=dict(load=dict(exit=0,timed_out=False,stdout='ingest pinned'),case=dict(exit=1,timed_out=False,stderr='ingest: error: out of memory'),foreign_unchanged=True,unexpected_entries=[],pair=None,dest_exists=False)
assert not judge(good,pair)
controls=[]
for field,value in [('exit',0xC0000409),('exit',-6),('exit',2),('timed_out',True),('stderr','allocator abort')]:
 r=copy.deepcopy(good);r['case'][field]=value;assert judge(r,pair);controls.append('case:'+field)
for field,value in [('exit',1),('timed_out',True),('stdout','not ingest')]:
 r=copy.deepcopy(good);r['load'][field]=value;assert judge(r,pair)[0].startswith('LOAD_CONTROL_FAILED');controls.append('load:'+field)
for field,value in [('foreign_unchanged',False),('unexpected_entries',['.DEST.ingest-stage-123']),('dest_exists',True)]:
 r=copy.deepcopy(good);r[field]=value;assert judge(r,pair);controls.append(field)
r=copy.deepcopy(good);r['case']['exit']=0;r['dest_exists']=True;r['pair']=pair;assert not judge(r,pair)
r['pair']={'audio.wav':'changed','manifest.json':'b'};assert judge(r,pair);controls.append('success bytes')
print('PASS contract controls: bounded exit1 and success neighbours; detected',len(controls),'mutations. Not actual execution evidence.')
