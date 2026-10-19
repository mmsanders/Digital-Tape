"""Additional fixed, finite landing-order classes for large epochs.
Actual event IDs/LBAs come from retained observations. No Product implementation.
"""
def targeted(events):
 events=list(events);ids=[e['id']for e in events]
 assert len(ids)==len(set(ids)) and all(type(i)is int for i in ids)
 groups={}
 for e in events:groups.setdefault(e['lba'],[]).append(e['id'])
 first=[g[0]for g in groups.values()];last=[g[-1]for g in groups.values()]
 ends=[]
 for g in groups.values():ends.extend([g[0]]if len(g)==1 else[g[0],g[-1]])
 rows=[('none',[]),('all-forward',ids),('all-reverse',ids[::-1]),('first-per-LBA',first),('last-per-LBA',last),('first-last-forward',ends),('first-last-reverse',ends[::-1]),('even-event-position',ids[::2]),('odd-event-position',ids[1::2])]
 for name,order in rows:
  selected=set(order);yield dict(name=name,mask=''.join('1'if i in selected else'0'for i in ids),landing_order=order)
