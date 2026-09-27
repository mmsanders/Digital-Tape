#!/usr/bin/env python3
"""Negative controls for provenance.py: each check must be able to go red.

Runs in CI before either campaign job publishes evidence. A gate that never
fails has not shown what it detects (CLAUDE.md §1).
"""
from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import provenance as P  # noqa: E402

STALE_BASE = "8276d8f22da34a53f9f52dae8d3bd1acb3c763d9"
STALE_IMPORT = "895351d17de9332e0804140858049d3608eeecd4"


def expect_red(label: str, fn) -> None:
    try:
        fn()
    except P.ProvenanceError as exc:
        print(f"ok    red: {label} ({exc})")
        return
    raise SystemExit(f"FAIL  {label}: check stayed green")


def main() -> int:
    ids = P.verify()
    print(f"ok    green: real history {ids}")

    # The two identities Verification PR #79 found, each on its own.
    expect_red("stale product base", lambda: P.verify(base=STALE_BASE))
    expect_red("stale verifier import", lambda: P.verify(import_commit=STALE_IMPORT))

    # Structural checks against history, independent of the stale list.
    expect_red("base that is not the import's parent",
               lambda: P.verify(base="0" * 40))
    expect_red("import commit absent from history",
               lambda: P.verify(import_commit="1" * 40))
    expect_red("import not an ancestor of HEAD",
               lambda: P.verify(git_ok=lambda *a: a[0] != "merge-base"))
    expect_red("verifier tree differs from the import",
               lambda: P.verify(verifier_tree="2" * 40))

    # Publishing guard: a summary carrying either stale identity is refused.
    good = {"product_base": P.ISSUED_BASE, "verifier_import_commit": P.IMPORT_COMMIT,
            "verifier_tree": P.VERIFIER_TREE}
    P.check_emitted(good)
    print("ok    green: summary with verified identities")
    expect_red("summary with stale base",
               lambda: P.check_emitted({**good, "product_base": STALE_BASE}))
    expect_red("summary with stale import",
               lambda: P.check_emitted({**good, "verifier_import_commit": STALE_IMPORT}))

    # No binding source may carry a stale identity outside provenance.py's table.
    hits = []
    for path in sorted(HERE.iterdir()):
        if path.suffix not in (".py", ".c", ".h", ".md") or path.name in ("provenance.py", Path(__file__).name):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits += [f"{path.name}:{s}" for s in P.STALE if s in text]
    if hits:
        raise SystemExit(f"FAIL  stale identity in binding source: {hits}")
    print("ok    no stale identity in binding sources")

    print("PASS  provenance gate green on real history and red on every control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
