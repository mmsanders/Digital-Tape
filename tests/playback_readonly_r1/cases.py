"""Meaningful boundaries; emitted census is the canonical candidate case list."""
import json

def cases():
    out=[]
    def add(id,row,fixture,**kw):out.append(dict(id=id,row=row,fixture=fixture,**kw))
    for b in (1,2,7,64,1024):
        for n in (1,8193,40001):
            add(f'cold-{n}-b{b}','R1-volume-work',f'contiguous-{n}',mode='traverse',budget=b,side='A')
    add('full-C60-b1024','R1-volume-work','contiguous-158760000',mode='traverse',budget=1024,side='A')
    for e,kind in ((3,'long'),(128,'short'),(4096,'short'),(4096,'long')):
        for b in (1,1024):
            add(f'fragment-{e}-{kind}-b{b}','R1-volume-work',f'fragment-{e}-{kind}',
                mode='traverse',budget=b,side='A')
    for r in (65536,-65536,32768,-32768,786432,-786432,2147483647,-2147483648,0):
        add(f'rate-{r}','R2-PCM-invalidation','edges',mode='rate',budget=7,rate=r,side='B')
    for mode in ('seek-covered','seek-uncovered','same-side','other-side','remount-changed',
                 'overwrite','splice','read-fail','partial-read-fail','faulted-drain',
                 'empty','budget-zero','lookahead','wrap','beyond-end','idle-playing','idle-stopped'):
        add(mode,'R2-PCM-invalidation' if not mode.startswith('idle') else 'R3-idle-seam',
            'empty' if mode=='empty' else 'behavior',mode=mode,budget=1,side='B')
    for warm in ('valid','null-data','zero-frames','short-bytes','past-end','overflow',
                 'outside','uuid','side'):
        add('warm-'+warm,'R2-PCM-invalidation','behavior',mode='warm',warm=warm,budget=2,side='B')
    return out

CONTROLS={
 'whole-window-reread':'R1-volume-work','tiny-transfer':'R1-volume-work',
 'full-index-rescan':'R1-volume-work','retained-movement':'R1-volume-work',
 'stale-side':'R2-PCM-invalidation','stale-content':'R2-PCM-invalidation',
 'stale-warm':'R2-PCM-invalidation','missing-lookahead':'R2-PCM-invalidation',
 'budget-overrun':'R1-volume-work','idle-nine-loops':'R3-idle-seam',
 'idle-mapping':'R3-idle-seam','invented-zero-seam':'R3-idle-seam'}

if __name__=='__main__':
    cs=cases();print(json.dumps({'schema':'read1-census-v1','cases':cs,
      'case_count':len(cs),'rows':sorted(set(c['row'] for c in cs)),
      'required_product_controls':CONTROLS,'product_runs':0},indent=2))
