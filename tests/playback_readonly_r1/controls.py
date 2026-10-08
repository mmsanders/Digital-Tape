#!/usr/bin/env python3
"""Execute actual candidate controls; synthetic traces never satisfy this census."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import cases
from runner import Bridge,run_case,Session,canonical,file_sha
from oracle import require,COUNTERS

TARGETS={
 'whole-window-reread':('cold-40001-b1024','payload reread ceiling'),
 'tiny-transfer':('cold-40001-b1024','tiny-transfer callback ceiling'),
 'full-index-rescan':('fragment-4096-long-b1024','mapping visit ceiling'),
 'retained-movement':('cold-40001-b1024','retained monotone movement'),
 'stale-side':('other-side','invalidated ring returned stale samples'),
 'stale-content':('overwrite','exact PCM'),
 'stale-warm':('warm-valid','exact PCM'),
 'missing-lookahead':('lookahead','exact PCM'),
 'budget-overrun':('cold-8193-b1','service budget'),
 'idle-nine-loops':('idle-playing','idle loop ceiling'),
 'idle-mapping':('idle-playing','idle PCM/mapping work'),
 'invented-zero-seam':('idle-playing','seam causal')}

def seam(adapter,root,writer,control=None):
    c=next(c for c in cases.cases() if c['id']=='idle-playing')
    bridge=Bridge(adapter,root,writer,'seam-'+str(control),control=control)
    session=Session(c,bridge,root)
    try:
        session.init()
        # The bridge invokes test-only genuine work, not a setter for counters.
        work=dict(zip(COUNTERS,(256,128,64,9,9)))
        obs,ev=bridge.call({'fn':'seam_work','work':work})
        require(not ev,'seam control device I/O')
        require(obs['result']==0 and obs['counters']==work,'seam causal nonzero work')
        obs,ev=bridge.call({'fn':'seam_work','work':dict.fromkeys(COUNTERS,0)})
        require(not ev and obs['counters']==dict.fromkeys(COUNTERS,0),'seam causal zero work')
        bridge.call({'fn':'tape_unmount'})
    finally:
        if bridge.proc.poll() is None:bridge.proc.stdin.close();bridge.proc.wait(timeout=30)
        bridge.stderr.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adapter',required=True)
    p.add_argument('--product-commit',required=True);p.add_argument('--engine-tree',required=True)
    p.add_argument('--out',required=True);a=p.parse_args();root=Path(a.out).resolve();root.mkdir(parents=True,exist_ok=True)
    adapter=str(Path(a.adapter).resolve());result=[]
    with gzip.open(root/'controls.jsonl.gz','wt') as writer:
        seam(adapter,root/'seam-positive',writer)
        for control,(id,reason) in TARGETS.items():
            c=next(c for c in cases.cases() if c['id']==id)
            try:
                if control=='invented-zero-seam':seam(adapter,root/control,writer,control)
                else:run_case(c,adapter,root/control,writer,control=control)
            except AssertionError as e:
                require(reason in str(e),'control failed for unrelated reason: '+control+': '+str(e))
                result.append({'control':control,'case':id,'detected_by':str(e)})
            else:raise AssertionError('required actual candidate control survived: '+control)
    m={'schema':'read1-controls-v1','kind':'actual-Product-control-run','product_commit':a.product_commit,
       'engine_tree':a.engine_tree,'adapter_sha256':file_sha(adapter),
       'seam_nonzero_and_zero_executed':True,'controls':result,
       'observations_sha256':file_sha(root/'controls.jsonl.gz')}
    (root/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(canonical(m))

if __name__=='__main__':main()
