"""Pinned, isolated loading of the DRAFT-10 WP-10 model (wp10_backlog_r54/model.py, Verification #138).

That model imports its own `deps` (which pins the accepted R29-B builders). Both packages use bare
module names, so the model is imported with its own directory on sys.path and then detached from
sys.modules. Every file is pinned by Git blob identity (CRLF-normalised).
"""
from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent
PACKAGE = "wp10_backlog_r54"
PINS = {
    "model": "0981d10051b4401fab84d30b9f8d06bd504c2048",   # DRAFT-10 step-1 planner (V10-001)
    "deps": "64d27b8d7e49adb0493518fc0156bd0309e29ca5",    # pins R29-B fixture/media/planner/oracle
}
NAMES = ("model", "deps", "fixture", "media", "planner", "oracle")


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _load():
    root = TESTS / PACKAGE
    for name, pin in PINS.items():
        actual = git_blob_sha(root / f"{name}.py")
        if actual != pin:
            raise AssertionError(f"pinned model drifted: {PACKAGE}/{name}.py {actual}")
    saved = {n: sys.modules.pop(n) for n in NAMES if n in sys.modules}
    sys.path.insert(0, str(root))
    try:
        model = importlib.import_module("model")
    finally:
        sys.path.remove(str(root))
        for n in NAMES:
            sys.modules.pop(n, None)
        sys.modules.update(saved)
    return model


M = _load()
