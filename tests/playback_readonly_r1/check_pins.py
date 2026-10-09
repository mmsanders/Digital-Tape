#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
m=json.loads((root/'INPUTS.json').read_text())
assert m['contract_source']=='26d3cb320ac6ce76dd2e26e22e1af4d4e7c0adbf'
assert m['product_main']=='5e6d5fd6cfce64031ba12b37fc367145b5fe18dd'
assert m['historical_authority']['preflight_merge']=='f02f9b625acf72f762dfde5d2838cb4805b75938'
assert m['sha256']['authority/engine-api.md']=='aa042e41e35b02bf2bb6b3896e59340a947720c27dc5fc52a24d657ccd66b33a'
assert m['sha256']['authority/tapefs-v1.md']=='2a6a9f7b6fe1e5f9e3fe068b3c6460a81256276082bb7e336c01dbf1e9c17eba'
for p,h in m['sha256'].items():assert hashlib.sha256((root/p).read_bytes()).hexdigest()==h,p
print(json.dumps({'authenticated_inputs':len(m['sha256']),'contract_source':m['contract_source']}))
