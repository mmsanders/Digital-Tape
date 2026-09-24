#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("wp10_run_product", HERE / "run_product.py")
if SPEC is None or SPEC.loader is None:
    raise SystemExit("cannot load run_product.py")
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)

A = "a" * 40
B = "b" * 40
C = "c" * 40
D = "d" * 40


def write_event(payload: object) -> str:
    f = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
    with f:
        json.dump(payload, f)
    return f.name


def clear_env() -> None:
    os.environ.pop("PRODUCT_BASE", None)
    os.environ.pop("GITHUB_EVENT_PATH", None)


def main() -> int:
    clear_env()

    pr_event = write_event({"pull_request": {"base": {"sha": B}}})
    os.environ["PRODUCT_BASE"] = A
    os.environ["GITHUB_EVENT_PATH"] = pr_event
    assert RUN.product_base_identity() == A, "explicit PRODUCT_BASE must win"

    os.environ.pop("PRODUCT_BASE")
    assert RUN.product_base_identity() == B, "PR base must be recorded dynamically"

    push_event = write_event({"before": C})
    os.environ["GITHUB_EVENT_PATH"] = push_event
    assert RUN.product_base_identity() == C, "push before SHA must be recorded"

    malformed = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
    with malformed as f:
        f.write("{not-json")
    os.environ["GITHUB_EVENT_PATH"] = malformed.name

    original_git = RUN.git
    RUN.git = lambda *args: D if args == ("rev-parse", "HEAD^") else A
    assert RUN.product_base_identity() == D, "malformed event must fall back to parent"

    clear_env()

    def shallow_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD^"):
            raise subprocess.CalledProcessError(128, ["git", *args])
        if args == ("rev-parse", "HEAD"):
            return A
        raise AssertionError(args)

    RUN.git = shallow_git
    assert RUN.product_base_identity() == A, "shallow fallback must use exercised HEAD"

    RUN.git = original_git
    clear_env()
    print("PASS WP-10 product-base provenance resolution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
