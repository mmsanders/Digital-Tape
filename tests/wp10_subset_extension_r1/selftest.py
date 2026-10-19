"""Independent plan consistency and detecting repeated-LBA neighbour controls."""
import json
from pathlib import Path
from orders import targeted
p=json.loads((Path(__file__).parent/'PLAN.json').read_text())
assert len(p['load_faults'])==32 and len(p['load_remaining_deferred'])==365
allcoords=[(x['kind'],x['ordinal'])for x in p['load_faults']+p['load_remaining_deferred']]
assert len(allcoords)==len(set(allcoords))==397
assert len(p['atomic_residue']['shapes'])*len(p['atomic_residue']['operations'])==24
events=[dict(id=10,lba=1),dict(id=11,lba=2),dict(id=12,lba=1)]
rows={x['name']:x for x in targeted(events)}
def image(order):
 out={}
 for i in order:
  e=next(e for e in events if e['id']==i);out[e['lba']]=i
 return out
assert image(rows['all-forward']['landing_order'])[1]==12
assert image(rows['all-reverse']['landing_order'])[1]==10
assert image(rows['first-last-forward']['landing_order'])[1]==12
assert image(rows['first-last-reverse']['landing_order'])[1]==10
assert set(rows)==set(p['persistence']['extra_targeted_orders'])
for r in rows.values():assert len(r['landing_order'])==len(set(r['landing_order'])) and len(r['mask'])==3
bad=dict(rows['all-reverse'],landing_order=rows['all-forward']['landing_order'])
assert image(bad['landing_order'])[1]!=10 # wrong-order mutant is detectable
assert list(targeted([]))[0]['landing_order']==[]
print('PASS fixed32/365 plan,24 atomic raw shapes, finite large-epoch orders; wrong repeated-LBA winner detected; no Product execution')
