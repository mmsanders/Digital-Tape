#!/usr/bin/env python3
"""Retained controls for the spec/hw version-manifest gate.

`spec_manifest.py` is the gate that stops a versioned hardware spec's content
moving while its revision does not. It has never had a control of its own, and
it has two fail-open modes that a green run cannot distinguish from a correct
one:

  1. A spec file is dropped from TRACKED, or a new one is never added. The gate
     then reports OK while watching nothing in that file. This is the mode that
     matters: `ruggedization.md` was added to TRACKED by hand, and one deletion
     puts it back outside the gate silently.
  2. The drift comparison itself stops failing.

P1-R3-HW established that demonstrating a control in a shell and not committing
it is the same as not having one, so both are checked here and run by
`make -C hardware spec-check`.

    python3 test_spec_manifest.py
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import shutil
import sys
import tempfile
from pathlib import Path

import spec_manifest as sm

REAL_HW = Path(__file__).resolve().parents[1] / "spec" / "hw"
# Files in spec/hw that are prose about the manifest rather than versioned spec.
NOT_A_SPEC = {"VERSION.md", "README.md"}


def run_gate() -> tuple[int, str]:
    """Call the gate, capturing both streams. Returns (exit code, output)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = sm.main()
    return rc, out.getvalue() + err.getvalue()


@contextlib.contextmanager
def sandbox(specs: dict[str, str], rows: dict[str, tuple[str, str]], tracked=None):
    """A throwaway spec/hw with the given files and manifest rows.

    The real spec/hw is never written to by these controls -- injecting drift
    into a file the project depends on and relying on restore is exactly the
    kind of cleverness that loses a document to a failed test run.
    """
    tmp = Path(tempfile.mkdtemp())
    try:
        for name, body in specs.items():
            (tmp / name).write_text(body)
        lines = ["# manifest", "", "| File | Revision | SHA-256 |", "|---|---|---|"]
        lines += [f"| `{n}` | {rev} | `{sha}` |" for n, (rev, sha) in rows.items()]
        (tmp / "VERSION.md").write_text("\n".join(lines) + "\n")
        saved = (sm.HW, sm.MANIFEST, sm.TRACKED)
        sm.HW, sm.MANIFEST = tmp, tmp / "VERSION.md"
        sm.TRACKED = tuple(specs) if tracked is None else tuple(tracked)
        try:
            yield tmp
        finally:
            sm.HW, sm.MANIFEST, sm.TRACKED = saved
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def spec(revision: str, body: str = "body") -> str:
    return f"# a spec\n\n**Revision:** {revision}\n\n{body}\n"


def sha_of(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# --- the controls -----------------------------------------------------------

def every_spec_file_is_tracked() -> list[str]:
    """The fail-open that a green gate cannot show you.

    A file sitting in spec/hw that TRACKED does not name is not being checked
    at all, and the gate still prints OK. This is the check that goes red if
    someone deletes a TRACKED entry.
    """
    on_disk = {p.name for p in REAL_HW.glob("*.md")} - NOT_A_SPEC
    missing = sorted(on_disk - set(sm.TRACKED))
    ghosts = sorted(set(sm.TRACKED) - on_disk)
    bad = []
    if missing:
        bad.append(f"in spec/hw but not TRACKED, so unchecked: {', '.join(missing)}")
    if ghosts:
        bad.append(f"TRACKED but not on disk: {', '.join(ghosts)}")
    return bad


def drift_without_revision_is_caught() -> list[str]:
    """Content moves, revision does not. The gate's whole purpose."""
    clean = spec("0.1")
    with sandbox({"a.md": clean}, {"a.md": ("0.1", sha_of(clean))}):
        rc, first = run_gate()
        if rc != 0:
            return [f"a clean sandbox should pass, got rc={rc}: {first.strip()}"]
        (sm.HW / "a.md").write_text(clean + "\nsilently added\n")
        rc, out = run_gate()
        if rc == 0:
            return ["content changed with the revision unmoved and the gate stayed green"]
        if "a.md" not in out or "Revision" not in out:
            return [f"failure does not name the file and its revision: {out.strip()}"]
    return []


def blessing_is_required_after_a_bump() -> list[str]:
    """Revision moves with the content: still red until the bump is recorded."""
    clean = spec("0.1")
    with sandbox({"a.md": clean}, {"a.md": ("0.1", sha_of(clean))}):
        (sm.HW / "a.md").write_text(spec("0.2", "new body"))
        rc, out = run_gate()
        if rc == 0:
            return ["a revision bump passed while the manifest still held the old hash"]
        if "0.1 -> 0.2" not in out:
            return [f"failure does not name the revision move: {out.strip()}"]
    return []


def an_unblessed_row_is_caught() -> list[str]:
    """An AUTO row means the file was added and never actually blessed."""
    clean = spec("0.1")
    with sandbox({"a.md": clean}, {"a.md": ("0.1", "AUTO")}):
        rc, out = run_gate()
        if rc == 0:
            return ["an AUTO row passed, so a new spec could be added and never checked"]
        if "AUTO" not in out:
            return [f"failure does not name the AUTO row: {out.strip()}"]
    return []


def a_dropped_tracked_entry_goes_unnoticed_by_the_gate() -> list[str]:
    """The reason `every_spec_file_is_tracked` exists, demonstrated.

    Drift a file and remove it from TRACKED: the gate reports OK. If this ever
    starts failing the gate has grown a defence of its own and this control can
    be retired -- but until then, the file-list check above is the only thing
    standing between a deleted line and an unwatched spec.
    """
    clean = spec("0.1")
    with sandbox({"a.md": clean, "b.md": clean},
                 {"a.md": ("0.1", sha_of(clean))}, tracked=["a.md"]):
        (sm.HW / "b.md").write_text(clean + "\nsilently added\n")
        rc, _ = run_gate()
        if rc != 0:
            return ["the gate now catches an untracked file by itself; retire this control "
                    "and the file-list check can be reconsidered"]
    return []


def the_control_is_specific() -> list[str]:
    """Drifting one file must add exactly one failure, and name that file."""
    clean = spec("0.1")
    rows = {"a.md": ("0.1", sha_of(clean)), "b.md": ("0.1", sha_of(clean))}
    with sandbox({"a.md": clean, "b.md": clean}, rows):
        (sm.HW / "b.md").write_text(clean + "\ndrifted\n")
        _, out = run_gate()
        fails = [ln for ln in out.splitlines() if ln.startswith("FAIL")]
        if len(fails) != 1:
            return [f"expected exactly one failure, got {len(fails)}: {fails}"]
        if "b.md" not in fails[0] or "a.md" in fails[0]:
            return [f"the failure names the wrong file: {fails[0]}"]
    return []


CONTROLS = (
    every_spec_file_is_tracked,
    drift_without_revision_is_caught,
    blessing_is_required_after_a_bump,
    an_unblessed_row_is_caught,
    a_dropped_tracked_entry_goes_unnoticed_by_the_gate,
    the_control_is_specific,
)


def main() -> int:
    failures = []
    for control in CONTROLS:
        for problem in control():
            failures.append(f"{control.__name__}: {problem}")
    if failures:
        for f in failures:
            print(f"FAIL spec-manifest control: {f}", file=sys.stderr)
        return 1
    print(f"OK  spec/hw manifest gate: {len(CONTROLS)} retained controls, "
          f"{len(sm.TRACKED)} files tracked and all present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
