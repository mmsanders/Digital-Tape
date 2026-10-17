"""Check committed model evidence without executing or accepting Product."""
import hashlib
import json
from pathlib import Path
from selftest import run

root = Path(__file__).parent
actual = run()
expected = json.loads((root / 'selftest-result.json').read_text())
assert actual == expected, 'self-test evidence drift'
assert actual['engine_operations_executed'] == 0
assert actual['sampled_rows'] == 201
manifest = json.loads((root / 'SHA256SUMS.json').read_text())
for name, digest in manifest.items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
assert set(manifest) == {'model.py', 'selftest.py', 'audit.py', 'README.md', 'ADAPTER.md',
                         'selftest-result.json', 'sampled-masks.jsonl'}
print('PASS: model, controls, sampled evidence and publication hashes; engine execution BLOCKED')
