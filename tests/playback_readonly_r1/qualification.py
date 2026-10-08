#!/usr/bin/env python3
"""Strict census/provenance gate; independent disposition also needs READ2 audit.

No synthetic observation, skipped case/control or different Product identity can
satisfy this gate. Phase1 CI, Rule1, resource/seam source audit are separate duties
in READ2.md and never inferred from the existence of these manifests.
"""
import argparse,hashlib,json
from pathlib import Path
import cases
from oracle import require
from runner import file_sha

def checked(root,name,sha):
    p=root/name;require(file_sha(p)==sha,'artifact SHA256 '+str(p))

def qualify(run_root,control_root,commit,tree):
    require(all(len(x)==40 and all(c in '0123456789abcdef' for c in x) for x in (commit,tree)),
            'exact Git SHA syntax')
    rr,cr=Path(run_root),Path(control_root)
    run=json.loads((rr/'manifest.json').read_text());ctrl=json.loads((cr/'manifest.json').read_text())
    require(run['schema']=='read1-run-v1' and run['kind']=='actual-Product-observations','actual Product run required')
    require(ctrl['schema']=='read1-controls-v1' and ctrl['kind']=='actual-Product-control-run','actual Product controls required')
    for m in (run,ctrl):
        require(m['product_commit']==commit and m['engine_tree']==tree,'exact candidate/engine binding')
    require(run['adapter_sha256']==ctrl['adapter_sha256'],'adapter controls identity')
    require(run['complete_case_census'] is True and run['shipping_equivalence_executed'] is True,'full census and shipping execution required')
    require([c['id'] for c in run['cases']]==[c['id'] for c in cases.cases()],'canonical case order/census')
    baseline=run['baseline_budget_zero']
    require(baseline is not None and baseline['product_commit']=='9e902cf04b6d0c02363870fb9bc201e40239b509',
            'issued accepted zero-budget baseline required')
    require(baseline['budget_zero_result']==next(c['budget_zero_result'] for c in run['cases'] if c['id']=='budget-zero'),
            'zero-budget result regression')
    checked(rr,'budget-zero-baseline.jsonl.gz',baseline['observation_sha256'])
    require([c['id'] for c in run['shipping_observations']]==[c['id'] for c in cases.cases()],
            'shipping artifact case census')
    require(len(run['shipping_adapter_sha256'])==64,'shipping binary identity')
    for c in run['shipping_observations']:
        require(c['file']==c['id']+'-shipping.jsonl.gz','canonical shipping artifact name')
        checked(rr,c['file'],c['sha256'])
    require(set(x['control'] for x in ctrl['controls'])==set(cases.CONTROLS) and
            len(ctrl['controls'])==len(cases.CONTROLS),'missing/duplicate Product controls')
    require(ctrl['seam_nonzero_and_zero_executed'] is True,'actual seam causal controls required')
    checked(rr,'observations.jsonl.gz',run['observation_sha256'])
    checked(cr,'controls.jsonl.gz',ctrl['observations_sha256'])
    return {'candidate':commit,'engine_tree':tree,'cases':len(run['cases']),
            'actual_controls':len(ctrl['controls']),'independent_disposition':'still requires READ2 audit'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for x in ('run','controls','product-commit','engine-tree'):p.add_argument('--'+x,required=True)
    a=p.parse_args();print(json.dumps(qualify(a.run,a.controls,a.product_commit,a.engine_tree),indent=2))
