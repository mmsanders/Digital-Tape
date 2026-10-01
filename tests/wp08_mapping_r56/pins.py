"""Pinned, isolated loading of the published verifier modules this package builds on.

Only the #118 C69-layout builders are reused: the superblock/index byte layout and the coordinate-unique
audio pattern (`wp10_final_r54/model.py`, which itself pins `dupmodel.py` and `deps.py`). Each file is pinned
by Git blob identity (CRLF-normalised) and loaded under a private module name.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent
PINS = {
    # #118 publication 7c0410e (subtree 598ebcd8).
    "wp10_final_r54/model.py": "2b1c8c8d93f56eac9e0d5ff16821d02058ccea6e",
    "wp10_final_r54/dupmodel.py": "53d0b75e83b7a76b539a4d895dc477366a5b3ea2",
    "wp10_final_r54/deps.py": "41d1e5ed265c87d523bceb312a7ac2f8e4fe23ab",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


for _rel, _blob in PINS.items():
    if git_blob_sha(TESTS / _rel) != _blob:
        raise AssertionError(f"pinned verifier source drifted: {_rel}")

_final = str(TESTS / "wp10_final_r54")
sys.path.insert(0, _final)
try:
    _spec = importlib.util.spec_from_file_location("wp08m56_final_model", TESTS / "wp10_final_r54/model.py")
    FINAL = importlib.util.module_from_spec(_spec)
    sys.modules["wp08m56_final_model"] = FINAL
    _spec.loader.exec_module(FINAL)
finally:
    sys.path.remove(_final)
C69 = FINAL.F
