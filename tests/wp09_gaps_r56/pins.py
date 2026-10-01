"""Pinned, isolated loading of the published verifier sources this package builds on.

- #118 `wp10_final_r54` (publication 7c0410e, subtree 598ebcd8): the C69-layout builders (`model.py`, which
  pins `dupmodel.py` and `deps.py`), the accepted row-3 oracle (`oracle.py`) that V-R55-01 strengthens, and the
  committed synthetic evidence whose row-3 records feed this package's self-test.

Every file is pinned by Git blob (CRLF-normalised) and loaded under a private module name, so this package's
own `oracle` never collides with the #118 one.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent
PINS = {
    "wp10_final_r54/model.py": "2b1c8c8d93f56eac9e0d5ff16821d02058ccea6e",
    "wp10_final_r54/dupmodel.py": "53d0b75e83b7a76b539a4d895dc477366a5b3ea2",
    "wp10_final_r54/deps.py": "41d1e5ed265c87d523bceb312a7ac2f8e4fe23ab",
    "wp10_final_r54/oracle.py": "db7509a99b6d408ecbfd831930d701cc65e2f0dd",
    "wp10_final_r54/evidence/synthetic/observations.jsonl.gz": "faf6d4861ccfcfb005bf51364f3bc5b68f2894d5",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix == ".py":
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


for _rel, _blob in PINS.items():
    if git_blob_sha(TESTS / _rel) != _blob:
        raise AssertionError(f"pinned verifier source drifted: {_rel}")


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, TESTS / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_final = str(TESTS / "wp10_final_r54")
_saved = {k: sys.modules.pop(k) for k in ("model", "dupmodel", "deps") if k in sys.modules}
sys.path.insert(0, _final)
try:
    FINAL = _load("wp09g56_final_model", "wp10_final_r54/model.py")
    sys.modules["model"] = FINAL                       # the #118 oracle imports `model` by bare name
    W10 = _load("wp09g56_final_oracle", "wp10_final_r54/oracle.py")
finally:
    sys.path.remove(_final)
    for k in ("model", "dupmodel", "deps"):
        sys.modules.pop(k, None)
    sys.modules.update(_saved)
C69 = FINAL.F
W10_SYNTHETIC = TESTS / "wp10_final_r54/evidence/synthetic/observations.jsonl.gz"
