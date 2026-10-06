#!/usr/bin/env python3
"""Check authenticated input copies without changing authoritative manifest bytes."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
pins=json.loads((root/'INPUTS.json').read_text())
assert pins['product_commit']=='437283291c944d24a3d574dee0e3f44ba97e1896'
assert pins['sha256']['spec/tapefs-v1.md']=='2a6a9f7b6fe1e5f9e3fe068b3c6460a81256276082bb7e336c01dbf1e9c17eba'
assert pins['sha256']['spec/engine-api.md']=='aa042e41e35b02bf2bb6b3896e59340a947720c27dc5fc52a24d657ccd66b33a'
for path,sha in pins['sha256'].items():
    assert hashlib.sha256((root/path).read_bytes()).hexdigest()==sha,path
amended=json.loads((root/'ADR164-INPUTS.json').read_text())
assert amended['product_commit']=='25b6439019396a54ce12e8298dd58f8a5d8a17e9'
for path,sha in amended['sha256'].items():
    assert hashlib.sha256((root/path).read_bytes()).hexdigest()==sha,path
overlay=json.loads((root/'spec/adr164/SPEC-ERRATA.manifest.json').read_text())
assert overlay['base_sha256']==pins['sha256']['spec/tapefs-v1.md']
assert overlay['overlay_sha256']==amended['sha256']['spec/adr164/SPEC-ERRATA.md']
assert overlay['independent_paper_commit']==amended['verification_base']
assert overlay['overlay_sha256']=='0cd814527f1c2a2e2d54de0f7a34e7195cb918262632e07d0b194831bade02a1'
latest=json.loads((root/'ADR165-INPUTS.json').read_text())
assert latest['product_commit']=='6f362f093435ab1a1501055b3bb1cdbe37a5b04c'
for path,sha in latest['sha256'].items():
    assert hashlib.sha256((root/path).read_bytes()).hexdigest()==sha,path
print(json.dumps({'original_hashes_verified':len(pins['sha256']),
                  'amended_hashes_verified':len(amended['sha256']),
                  'ADR165_hashes_verified':len(latest['sha256']),
                  'product_commit':latest['product_commit'],'E1_exact_overlay_confirmed':True}))
