"""Prove the32-case r2 catalog changes only six Windows platform constants."""
import copy,importlib.util
from pathlib import Path
import contract
p=Path(__file__).resolve().parents[1]/'windows_interactions_r1/contract.py'
s=importlib.util.spec_from_file_location('frozen_r1',p);old=importlib.util.module_from_spec(s);s.loader.exec_module(old)
IDS={'E-ascii-caret','E-astral-caret','E-paste-exact-limit','E-reject-nul','E-delete-to-empty','E-two-edits-reversed-acks'}
assert len(old.CASES)==len(contract.CASES)==32
changed=set()
for before,after in zip(old.CASES,contract.CASES):
    wanted=copy.deepcopy(before)
    if before['id'] in IDS:
        assert wanted['eq']['label_selection'][2]=='none'
        wanted['eq']['label_selection']=[*wanted['eq']['label_selection'][:2],'forward'];changed.add(before['id'])
    assert wanted==after,before['id']
    if before['family']=='editing':assert 'label_selection' in after['same']
assert changed==IDS
r=contract.fixture();r['cases']['E-ascii-caret']['after']['label_selection'][2]='backward'
try:contract.qualify(r,'a'*40)
except AssertionError:pass
else:raise AssertionError('actual direction loss survived corrected gate')
print('PASS all32 cases/order/offsets/limits preserved; exactly6 Windows direction constants corrected; actual selection drift still rejected')
