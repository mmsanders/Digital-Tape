"""Pinned, isolated loading of the accepted C69 and R29-B verifier models.

Both packages use bare module names (planner, oracle, media, fixture), so each is
imported with its own directory on sys.path and then detached from sys.modules.
Every file is pinned by Git blob identity (CRLF-normalised).
"""
from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

TESTS = Path(__file__).resolve().parent.parent
NAMES = ("fixture", "media", "planner", "oracle")
PINS = {
    "crash_core_draft8": {
        "planner": "2bef5fac8091cf03b37d244cb360a37d7ef9ec46",
        "oracle": "5d7ba48ba65fb49bd055e96790bc5083b752ccac",
        "media": "47c8929753cecac08b03a0d7cdb3a3979737e412",
        "fixture": "4e56bac71a8d2d0714c29e72b7071fc59399d2c1",
    },
    "format_dup_identity_draft8": {
        "planner": "55994ea977d2c034d76e8a0e735dbaba22d58594",
        "oracle": "cb95cd41d69a843fa59e00f57b06ccd579418b4a",
        "media": "7cebb2be2d68af8014881cb147d079a3a2d5bf89",
        "fixture": "86df43a254479464559e299855e900d5637836a9",
    },
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _load(package: str) -> SimpleNamespace:
    root = TESTS / package
    for name, pin in PINS[package].items():
        actual = git_blob_sha(root / f"{name}.py")
        if actual != pin:
            raise AssertionError(f"pinned accepted model drifted: {package}/{name}.py {actual}")
    saved = {n: sys.modules.pop(n) for n in NAMES if n in sys.modules}
    sys.path.insert(0, str(root))
    try:
        mods = {n: importlib.import_module(n) for n in NAMES}
    finally:
        sys.path.remove(str(root))
        for n in NAMES:
            sys.modules.pop(n, None)
        sys.modules.update(saved)
    return SimpleNamespace(**mods)


C69 = _load("crash_core_draft8")
R29B = _load("format_dup_identity_draft8")
