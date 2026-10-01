#!/usr/bin/env python3
"""Negative controls for the docs-only change classifier (#347).

ci.yml skips the engine suite when tools/ci/classify-changes.py says a pull
request is docs-only, so a classifier that wrongly says docs-only silently
removes coverage. This script shows:

1. the real classifier returns FULL for every code-bearing path class and for
   mixed docs+code diffs, and docs-only only for the allowed paths;
2. the same table goes red against deliberately broken classifiers, so a
   classifier that never says "full" (or that admits one forbidden class)
   cannot pass it;
3. the CLI, fed NUL-separated paths as ci.yml feeds it, writes the GitHub
   output the workflow reads;
4. every ci.yml job is directly docs-only gated unless it is the classifier
   itself or is on the explicit transitively-gated allow-list. The allow-list
   dependency is checked too, and an ungated-job mutant must be rejected.

Exit status 1 if any expectation fails, any broken classifier survives, or the
workflow gate invariant/negative control fails.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/ci/classify-changes.py"
WORKFLOW = ROOT / ".github/workflows/ci.yml"

spec = importlib.util.spec_from_file_location("classify_changes", SCRIPT)
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
D, F = C.DOCS_ONLY, C.FULL

# (paths, expected verdict, label)
CASES = [
    (["docs/STATUS.md"], D, "docs/ file"),
    (["docs/archive/old.md", "docs/ROLES/README.md"], D, "nested docs/"),
    (["site/index.html"], D, "site/"),
    (["README.md"], D, "root *.md"),
    (["CLAUDE.md", "AGENTS.md", "docs/DECISIONS.md", "site/a.css"], D, "all three allowed classes"),
    ([], F, "empty diff"),
    (["engine/src/tape.c"], F, "engine/"),
    (["engine/README.md"], F, "*.md under engine/"),
    (["tests/IMPORTS.json"], F, "tests/"),
    (["tests/wp10_backlog_r54/README.md"], F, "*.md under tests/"),
    (["spec/tapefs-v1.md"], F, "spec/"),
    (["docs/verification/runs/x/manifest.json"], F, "docs/verification/"),
    (["docs/verification/README.md"], F, "*.md under docs/verification/"),
    (["docs/verification"], F, "docs/verification as a file"),
    ([".github/workflows/ci.yml"], F, ".github/"),
    ([".github/CODEOWNERS"], F, ".github/CODEOWNERS"),
    (["tools/ci/classify-changes.py"], F, "tools/"),
    (["firmware/main.c"], F, "firmware/"),
    (["hardware/board/notes.md"], F, "hardware/"),
    (["Makefile"], F, "root non-markdown file"),
    (["README.md.txt"], F, "root file that only contains .md"),
    (["docs/STATUS.md", "engine/src/tape.c"], F, "mixed docs + engine"),
    (["docs/STATUS.md", "tests/IMPORTS.json"], F, "mixed docs + tests"),
    (["README.md", "spec/VERSION.md"], F, "mixed root md + spec"),
    (["site/index.html", ".github/workflows/ci.yml"], F, "mixed site + .github"),
    (["docs/STATUS.md", "docs/verification/x.md"], F, "mixed docs + docs/verification"),
    (["docs/../engine/src/tape.c"], F, "dot-dot escape"),
    (["./docs/STATUS.md"], F, "non-canonical ./ path"),
    (["docs"], F, "bare docs as a file"),
]


def table(classify):
    """Failures of `classify` against CASES."""
    return [(label, want, classify(paths)) for paths, want, label in CASES if classify(paths) != want]


# Broken classifiers the table must reject.
def never_full(paths):
    return D


def any_instead_of_all(paths):
    return D if any(C.docs_path(p) for p in paths) else F


def empty_is_docs(paths):
    return D if all(C.docs_path(p) for p in paths) else F


def admits_docs_verification(paths):
    ok = lambda p: C.docs_path(p) or p.startswith("docs/verification/")  # noqa: E731
    return D if paths and all(ok(p) for p in paths) else F


def admits_any_markdown(paths):
    ok = lambda p: C.docs_path(p) or p.endswith(".md")  # noqa: E731
    return D if paths and all(ok(p) for p in paths) else F


def admits_github(paths):
    ok = lambda p: C.docs_path(p) or p.startswith(".github/")  # noqa: E731
    return D if paths and all(ok(p) for p in paths) else F


def prefix_without_slash(paths):
    ok = lambda p: (p.startswith("docs") and not p.startswith("docs/verification")) \
        or p.startswith("site") or ("/" not in p and p.endswith(".md"))  # noqa: E731
    return D if paths and all(ok(p) for p in paths) else F


MUTANTS = [never_full, any_instead_of_all, empty_is_docs, admits_docs_verification,
           admits_any_markdown, admits_github, prefix_without_slash]


GATE_NEEDLE = "needs.changes.outputs.docs_only != 'true'"

# These jobs are already transitively docs-only gated and have dependency/result
# semantics worth preserving. Each exemption names a directly gated prerequisite;
# the audit below verifies both the dependency and the prerequisite's direct gate.
TRANSITIVE_GATE_ALLOWLIST = {
    "respool-full-crash": "respool-full-functional",
    "respool-full-aggregate": "respool-full-functional",
    "gates": "build",
    "meta": "build",
    "unit": "build",
    "golden": "build",
}


def workflow_jobs(text):
    """Return top-level ci.yml job blocks keyed by job id."""
    lines = text.splitlines()
    try:
        start = lines.index("jobs:") + 1
    except ValueError:
        return {}
    jobs = {}
    current = None
    block = []
    for line in lines[start:]:
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if m:
            if current is not None:
                jobs[current] = "\n".join(block)
            current = m.group(1)
            block = [line]
        elif current is not None:
            block.append(line)
    if current is not None:
        jobs[current] = "\n".join(block)
    return jobs


def job_needs(block):
    """Return job ids listed by a job-level needs: entry."""
    lines = block.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^    needs:\s*(.*)$", line)
        if not m:
            continue
        tail = m.group(1).strip()
        if tail:
            return set(re.findall(r"[A-Za-z0-9_-]+", tail))
        result = set()
        for continuation in lines[i + 1:]:
            m2 = re.match(r"^      -\s*([A-Za-z0-9_-]+)\s*$", continuation)
            if m2:
                result.add(m2.group(1))
                continue
            if continuation.startswith("      "):
                continue
            break
        return result
    return set()


def has_direct_docs_gate(block):
    """True only for a job-level if: that reads the changes job output."""
    m = re.search(r"^    if:\s*(.*)$", block, flags=re.MULTILINE)
    return bool(m and GATE_NEEDLE in m.group(1))


def workflow_gate_failures(text):
    """Audit direct gates plus the explicit, dependency-checked exemptions."""
    jobs = workflow_jobs(text)
    failures = []
    if "changes" not in jobs:
        return ["missing classifier job 'changes'"]

    for job, block in jobs.items():
        if job == "changes" or job in TRANSITIVE_GATE_ALLOWLIST:
            continue
        needs = job_needs(block)
        if "changes" not in needs:
            failures.append(f"{job}: missing job-level needs: changes")
        if not has_direct_docs_gate(block):
            failures.append(f"{job}: missing job-level docs-only if gate")

    for job, upstream in TRANSITIVE_GATE_ALLOWLIST.items():
        block = jobs.get(job)
        if block is None:
            failures.append(f"{job}: stale allow-list entry; job missing")
            continue
        if upstream not in job_needs(block):
            failures.append(f"{job}: allow-list prerequisite {upstream!r} is not in needs")
            continue
        upstream_block = jobs.get(upstream)
        if upstream_block is None or "changes" not in job_needs(upstream_block) or not has_direct_docs_gate(upstream_block):
            failures.append(f"{job}: allow-list prerequisite {upstream!r} is not directly docs-only gated")
    return failures


def remove_job_docs_gate(text, job):
    """Negative-control mutation: remove one job's job-level docs-only if."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line == f"  {job}:"), None)
    if start is None:
        raise AssertionError(f"negative-control job missing: {job}")
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^  [A-Za-z0-9_-]+:\s*$", lines[i])), len(lines))
    removed = False
    out = []
    for i, line in enumerate(lines):
        if start < i < end and re.match(r"^    if:\s*", line) and GATE_NEEDLE in line:
            removed = True
            continue
        out.append(line)
    if not removed:
        raise AssertionError(f"negative-control gate missing: {job}")
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def cli(paths):
    with tempfile.TemporaryDirectory() as t:
        out = pathlib.Path(t) / "out"
        r = subprocess.run([sys.executable, "-B", str(SCRIPT)], input="\0".join(paths).encode(),
                           capture_output=True, env={**os.environ, "GITHUB_OUTPUT": str(out)})
        return r.returncode, r.stdout.decode().splitlines()[0], out.read_text()


def main() -> int:
    bad = 0
    real = table(C.classify)
    for paths, want, label in CASES:
        got = C.classify(paths)
        print(f"{'ok  ' if got == want else 'FAIL'}  {want:<9} {label}: {paths}")
    if real:
        bad += 1
    for m in MUTANTS:
        caught = table(m)
        print(("killed   " if caught else "SURVIVED ") + f"{m.__name__}: {len(caught)} case(s) differ"
              + (f", e.g. {caught[0][0]} -> {caught[0][2]}" if caught else ""))
        if not caught:
            bad += 1
    workflow = WORKFLOW.read_text()
    gate_failures = workflow_gate_failures(workflow)
    if gate_failures:
        bad += 1
        for failure in gate_failures:
            print("FAIL workflow gate: " + failure)
    else:
        jobs = workflow_jobs(workflow)
        direct = len(jobs) - 1 - len(TRANSITIVE_GATE_ALLOWLIST)
        print(f"ok    workflow gate audit: {direct} direct, "
              f"{len(TRANSITIVE_GATE_ALLOWLIST)} dependency-checked exemptions, 1 classifier")

    ungated = remove_job_docs_gate(workflow, "wp08-mapping-r56-package")
    ungated_failures = workflow_gate_failures(ungated)
    caught = any(f.startswith("wp08-mapping-r56-package:") for f in ungated_failures)
    print(("killed   " if caught else "SURVIVED ") +
          "ungated-job negative control: wp08-mapping-r56-package" +
          (f" -> {ungated_failures[0]}" if caught else ""))
    if not caught:
        bad += 1
    for paths, want_out in ((["docs/STATUS.md", "README.md"], "docs_only=true\n"),
                            (["docs/STATUS.md", "engine/src/tape.c"], "docs_only=false\n"),
                            ([], "docs_only=false\n")):
        rc, line, out = cli(paths)
        good = rc == 0 and out == want_out
        print(f"{'ok  ' if good else 'FAIL'}  cli {paths} -> {line!r}, GITHUB_OUTPUT {out.strip()!r}")
        if not good:
            bad += 1
    full = sum(w == F for _, w, _ in CASES)
    print(f"{len(CASES) - len(real)}/{len(CASES)} cases ({full} full, {len(CASES) - full} docs-only); "
          f"{sum(1 for m in MUTANTS if table(m))}/{len(MUTANTS)} broken classifiers killed")
    print("== change classifier: " + ("PASS" if not bad else "FAIL") + " ==")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
