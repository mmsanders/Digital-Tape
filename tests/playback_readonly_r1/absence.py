#!/usr/bin/env python3
"""Preprocess/object/link observation-seam absence, with an actual leak control.

Covered-site and TU/build completeness still require the independent READ2 audit;
a successful symbol-only scan is deliberately insufficient for this gate.
"""
import argparse,json,re
from pathlib import Path
from oracle import require
from runner import file_sha
MARKER=re.compile(rb'TAPE_READ1_|tape_read1_')

def inspect(path,commit,tree,expect_leak=False):
    p=Path(path);m=json.loads(p.read_text());base=p.parent
    require(m['product_commit']==commit and m['engine_tree']==tree,'absence exact head/engine')
    require(m['kind']==('actual-deliberate-shipping-leak' if expect_leak else 'actual-shipping-absence'),
            'actual shipping absence/control evidence required')
    require(set(m['layers'])=={'preprocess','object','link'},'all three absence layers required')
    require(bool(m['translation_units']) and len(set(m['translation_units']))==len(m['translation_units']),
            'shipping engine translation-unit census')
    hits=[]
    for layer,files in m['layers'].items():
        require(bool(files),'missing absence layer '+layer)
        for f in files:
            target=base/f['file'];require(file_sha(target)==f['sha256'],'absence artifact SHA256')
            for i,line in enumerate(target.read_bytes().splitlines(),1):
                if MARKER.search(line):hits.append({'layer':layer,'file':f['file'],'line':i})
    if expect_leak:
        require({h['layer'] for h in hits}=={'preprocess','object','link'},'actual leak must be visible at all three layers')
    else:require(not hits,'shipping observation seam leak')
    return {'layers':3,'translation_units':len(m['translation_units']),'marker_hits':hits}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--shipping',required=True);p.add_argument('--leak-control',required=True)
    p.add_argument('--product-commit',required=True);p.add_argument('--engine-tree',required=True)
    a=p.parse_args()
    clean=inspect(a.shipping,a.product_commit,a.engine_tree)
    leak=inspect(a.leak_control,a.product_commit,a.engine_tree,True)
    print(json.dumps({'shipping':clean,'causal_leak_control':leak,
                      'disposition':'READ2 covered-site/build audit also required'},indent=2))
