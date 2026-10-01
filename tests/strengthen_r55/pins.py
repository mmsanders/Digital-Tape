"""Pinned, isolated loading of the published verifier modules this package builds on.

Every source file is pinned by Git blob identity (CRLF-normalised) and loaded under a private module
name, so packages that reuse bare names (`oracle`, `model`, `deps`) never collide with this one.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent
PINS = {
    # #118 publication 7c0410e (subtree 598ebcd8): coordinate-unique audio, C69-layout builders, and
    # dupmodel.py (#116's model, blob 53d0b75e) with its pinned R29-B builders.
    "wp10_final_r54/model.py": "2b1c8c8d93f56eac9e0d5ff16821d02058ccea6e",
    "wp10_final_r54/dupmodel.py": "53d0b75e83b7a76b539a4d895dc477366a5b3ea2",
    "wp10_final_r54/deps.py": "41d1e5ed265c87d523bceb312a7ac2f8e4fe23ab",
    # #99 capacity oracle (unchanged by #126 maintenance) and the maintained synthetic emitter.
    "capacity_wp09_r52/oracle.py": "df7f6095e367b1ad62aa550bfd1a46e3692d6d51",
    "capacity_wp09_r52/synthetic.py": "edf6d9b027c520b33d531276b694be4ec9673b1c",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _check(rel):
    actual = git_blob_sha(TESTS / rel)
    if actual != PINS[rel]:
        raise AssertionError(f"pinned verifier source drifted: {rel} {actual}")


def _load(name, path, alias=None):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    saved = sys.modules.get(alias[0]) if alias else None
    if alias:
        sys.modules[alias[0]] = alias[1]
    try:
        spec.loader.exec_module(mod)
    finally:
        if alias:
            if saved is None:
                sys.modules.pop(alias[0], None)
            else:
                sys.modules[alias[0]] = saved
    return mod


for _rel in PINS:
    _check(_rel)

# wp10_final_r54/model.py imports `deps` and `dupmodel` by bare name from its own directory.
_final = str(TESTS / "wp10_final_r54")
sys.path.insert(0, _final)
try:
    FINAL = _load("str55_final_model", TESTS / "wp10_final_r54/model.py")
finally:
    sys.path.remove(_final)
DM = FINAL.DM
R29B = DM.B
C69 = FINAL.F

# The capacity emitter imports its oracle as `oracle`; hand it the pinned capacity oracle under that name.
CAP = _load("str55_capacity_oracle", TESTS / "capacity_wp09_r52/oracle.py")
CAP_SYNTH = _load("str55_capacity_synthetic", TESTS / "capacity_wp09_r52/synthetic.py", alias=("oracle", CAP))
