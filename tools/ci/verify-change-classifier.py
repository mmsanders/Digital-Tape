#!/usr/bin/env python3
"""Negative controls for the change classifier and the CI lanes (#347, #385 R1).

ci.yml runs three lanes: cheap (always), regression (any non-docs change) and
qualification (schedule, dispatch, the `qualification` label, any change that
could move an engine result, or a change to a job's own test directories).
A classifier or lane wiring that says "not needed" wrongly removes coverage
silently, so this script shows, each against deliberately broken versions:

1. docs-only: the #347 table (unchanged) and its seven broken classifiers;
2. qualification selection: a code change to engine/, spec/, tools/, ci.yml or
   any unrecognised path still selects the whole qualification lane; schedule,
   dispatch and the phase-gate label do too; a changed package selects its own
   jobs through the source-reference closure; host/ and new test packages do
   not. Broken selectors must be rejected;
3. the CLI writes the three GitHub outputs ci.yml reads;
4. lane wiring in ci.yml: every job is in exactly one lane aggregate; cheap jobs
   are ungated; regression and qualification jobs carry the docs-only gate;
   qualification jobs carry the qualify gate naming themselves, or inherit from
   a gated upstream member. Mutated workflows must be rejected;
5. the lane verdict: unexpected skips, failures, cancellations and runs that
   should not have happened turn a lane red. Broken verdicts must be rejected.

Exit status 1 if any expectation fails or any broken variant survives.
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
sys.path.insert(0, str(ROOT / "tools/ci"))
import ci_lanes as L  # noqa: E402
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




# --- 2. qualification selection -------------------------------------------

WORKFLOW_TEXT = WORKFLOW.read_text()
DEPS = L.qualification_deps(WORKFLOW_TEXT)
ALL = "ALL"

# (paths, event, labels, expected docs_only, expected qualification, label)
# expected qualification: ALL, or the exact set of per-package jobs selected.
QCASES = [
    (["docs/STATUS.md"], "pull_request", [], True, set(), "docs-only PR"),
    (["docs/STATUS.md", "README.md"], "push", [], True, set(), "docs-only main push"),
    (["site/index.html"], "push", [], True, set(), "site-only main push"),
    (["engine/src/tape.c"], "pull_request", [], False, ALL, "engine change"),
    (["engine/src/tape.c"], "push", [], False, ALL, "engine change on main"),
    (["docs/STATUS.md", "engine/src/tape.c"], "pull_request", [], False, ALL, "docs + engine"),
    (["spec/tapefs-v1.md"], "pull_request", [], False, ALL, "spec change"),
    (["tools/ci/run-golden.sh"], "pull_request", [], False, ALL, "tools/ci change"),
    (["tools/fetch-evidence.sh"], "pull_request", [], False, ALL, "tools change"),
    ([".github/workflows/ci.yml"], "pull_request", [], False, ALL, "ci.yml change"),
    (["tests/IMPORTS.json"], "pull_request", [], False, ALL, "file directly under tests/"),
    (["Makefile"], "pull_request", [], False, ALL, "root file"),
    (["firmware/bench/x.c"], "pull_request", [], False, ALL, "firmware (not known inert)"),
    (["docs/verification/x.json"], "pull_request", [], False, ALL, "docs/verification"),
    (["newtop/x"], "pull_request", [], False, ALL, "unrecognised top-level directory"),
    (["./engine/x.c"], "pull_request", [], False, ALL, "non-canonical path"),
    ([], "pull_request", [], False, ALL, "empty diff"),
    ([], "push", [], False, ALL, "push with unknown base"),
    (["docs/STATUS.md"], "schedule", [], False, ALL, "schedule"),
    (["docs/STATUS.md"], "workflow_dispatch", [], False, ALL, "workflow_dispatch"),
    (["host/tapectl.c"], "pull_request", ["qualification"], False, ALL, "phase-gate label"),
    (["host/tapectl.c"], "pull_request", ["software-lead"], False, set(), "unrelated label"),
    (["host/tapectl.c", "host/Makefile"], "pull_request", [], False, set(), "host only"),
    (["hardware/board/x.kicad_pcb", "spec/hw/a.md"], "pull_request", [], False, set(), "hardware only"),
    ([".github/workflows/evidence-integrity.yml"], "pull_request", [], False, set(), "other workflow"),
    (["tests/wp14_new_package/x.py"], "pull_request", [], False, set(), "new test package"),
    (["tests/promote_adapter/run_product.py"], "pull_request", [], False,
     {"promote-package", "wp11-mutation-gate"}, "changed promote package"),
    (["tests/wp10_backlog_adapter/x.py"], "pull_request", [], False,
     {"wp10-backlog-package", "wp10-backlog-r54-package", "wp10-final-package",
      "wp10-residue-package", "wp11-mutation-gate"}, "package reached by source references"),
    (["tests/record_adapter/x.c"], "pull_request", [], False, {"wp11-mutation-gate"},
     "regression package that is a mutation suite"),
    (["tests/respool_adapter/x.c"], "pull_request", [], False,
     {"respool-full-functional", "wp11-mutation-gate"}, "package the full re-spool builds"),
    (["tests/promote_adapter/x.py", "engine/src/tape.c"], "pull_request", [], False, ALL,
     "package + engine"),
]


def qtable(select):
    bad = []
    for paths, event, labels, want_docs, want_q, label in QCASES:
        docs, q, jobs, _ = select(paths, event, labels, DEPS)
        got = ALL if q else jobs
        if docs != want_docs or (not want_docs and got != want_q):
            bad.append((label, (want_docs, want_q), (docs, got)))
    return bad


def _strip(prefixes):
    def select(paths, event, labels, deps):
        saved = L.QUALIFICATION_INERT_PREFIXES
        L.QUALIFICATION_INERT_PREFIXES = saved + tuple(prefixes)
        try:
            return L.classify_paths(paths, event, labels, deps)
        finally:
            L.QUALIFICATION_INERT_PREFIXES = saved
    select.__name__ = "treats_" + "_".join(p.strip("/").replace("/", "_") for p in prefixes) + "_as_inert"
    return select


def schedule_not_full(paths, event, labels, deps):
    return L.classify_paths(paths, "pull_request" if event == "schedule" else event, labels, deps)


def ignores_label(paths, event, labels, deps):
    return L.classify_paths(paths, event, [], deps)


def no_closure(paths, event, labels, deps):
    text = WORKFLOW_TEXT
    jobs = L.workflow_jobs(text)
    known = L._test_dirs()
    shallow = {j: L._referenced(jobs[j], known) for j in deps}
    return L.classify_paths(paths, event, labels, shallow)


def any_test_dir_inert(paths, event, labels, deps):
    return L.classify_paths(paths, event, labels, {j: set() for j in deps})


def unknown_is_inert(paths, event, labels, deps):
    docs, q, jobs, r = L.classify_paths(paths, event, labels, deps)
    if q and paths and event in ("pull_request", "push") and \
            not any(p.startswith(("engine/", "spec/", "tools/", ".github/")) for p in paths):
        q = False
    return docs, q, jobs, r


def empty_is_nothing(paths, event, labels, deps):
    if not paths and event in ("pull_request", "push"):
        return False, False, set(), []
    return L.classify_paths(paths, event, labels, deps)


QMUTANTS = [_strip(["engine/"]), _strip(["spec/"]), _strip(["tools/"]), _strip([".github/"]),
            _strip(["tests/"]), schedule_not_full, ignores_label, no_closure,
            any_test_dir_inert, unknown_is_inert, empty_is_nothing]


# --- 4. lane wiring in ci.yml ---------------------------------------------


def lane_failures(text):
    jobs = L.workflow_jobs(text)
    lanes = L.lanes(text)
    failures = []
    for lane in L.LANES:
        block = jobs.get(lane)
        if block is None:
            failures.append(f"missing lane aggregate {lane!r}")
            continue
        if not __import__("re").search(rf"^    name: {lane}\s*$", block, flags=__import__("re").M):
            failures.append(f"{lane}: aggregate check name is not exactly {lane!r}")
        if "always()" not in L.job_if(block):
            failures.append(f"{lane}: aggregate must run with always()")
        if f"LANE: {lane}" not in block or "lane-verdict.py" not in block:
            failures.append(f"{lane}: aggregate does not run lane-verdict.py for its own lane")
        if lane != "cheap" and "changes" not in L.job_needs(block):
            failures.append(f"{lane}: aggregate cannot read the classifier outputs")
    seen = {}
    for lane, members in lanes.items():
        for m in members:
            if m not in jobs:
                failures.append(f"{lane}: member {m!r} is not a job")
            if m in seen:
                failures.append(f"{m}: in two lanes ({seen[m]}, {lane})")
            seen[m] = lane
    for job in jobs:
        if job in L.LANES:
            continue
        if job not in seen:
            failures.append(f"{job}: in no lane")
    if "changes" not in lanes.get("cheap", []):
        failures.append("classifier job 'changes' is not in the cheap lane")
    for job in lanes.get("cheap", []):
        if job in jobs and L.has_docs_gate(jobs[job]):
            failures.append(f"{job}: cheap job is docs-only gated")
    for lane in ("regression", "qualification"):
        members = lanes.get(lane, [])
        for job in members:
            block = jobs.get(job)
            if block is None:
                continue
            up = L.upstream_member(jobs, job, members)
            direct = L.has_docs_gate(block)
            if not direct:
                if up is None:
                    failures.append(f"{job}: {lane} job is not docs-only gated")
                    continue
                if L.job_if(block) and "always()" not in L.job_if(block):
                    failures.append(f"{job}: inherits from {up} but has its own if:")
                continue
            if "changes" not in L.job_needs(block):
                failures.append(f"{job}: gated on the classifier without needs: changes")
            if lane == "qualification" and not L.has_qualify_gate(block, job):
                failures.append(f"{job}: qualification job lacks the qualify gate naming itself")
            if lane == "regression" and "qualify" in L.job_if(block).replace("docs_only", ""):
                failures.append(f"{job}: regression job is qualification gated")
    return failures


def _job_span(text, job):
    lines = text.splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if l == f"  {job}:\n")
    end = next((i for i in range(start + 1, len(lines))
                if __import__("re").match(r"^  [A-Za-z0-9_-]+:\s*$", lines[i])), len(lines))
    return lines, start, end


def drop_from_lane(text, job):
    return text.replace(f"      - {job}\n", "", 1)


def drop_qualify_gate(text, job):
    lines, s, e = _job_span(text, job)
    for i in range(s, e):
        if lines[i].startswith("    if:"):
            lines[i] = "    if: ${{ !cancelled() && needs.changes.outputs.docs_only != 'true' }}\n"
    return "".join(lines)


def misname_qualify_gate(text, job):
    return text.replace(f"qualify_jobs, ',{job},')", "qualify_jobs, ',promote-package,')", 1)


def drop_docs_gate(text, job):
    lines, s, e = _job_span(text, job)
    return "".join(l for i, l in enumerate(lines) if not (s < i < e and l.startswith("    if:")))


def gate_cheap_job(text, job):
    lines, s, e = _job_span(text, job)
    lines.insert(s + 2, "    needs: changes\n    if: ${{ !cancelled() && needs.changes.outputs.docs_only != 'true' }}\n")
    return "".join(lines)


def rename_aggregate(text, lane):
    return text.replace(f"    name: {lane}\n", f"    name: {lane} lane\n", 1)


def add_unlaned_job(text, _):
    return text + "\n  sneaky:\n    name: sneaky\n    runs-on: ubuntu-latest\n    steps:\n      - run: true\n"


WMUTANTS = [
    (drop_from_lane, "wp08-mapping-r56-package", "wp08-mapping-r56-package: in no lane"),
    (drop_from_lane, "promote-package", "promote-package: in no lane"),
    (drop_qualify_gate, "wp10-residue-package", "wp10-residue-package: qualification job lacks"),
    (misname_qualify_gate, "crash-core-package", "crash-core-package: qualification job lacks"),
    (drop_docs_gate, "golden", "golden: regression job is not docs-only gated"),
    (gate_cheap_job, "spec", "spec: cheap job is docs-only gated"),
    (rename_aggregate, "regression", "regression: aggregate check name"),
    (add_unlaned_job, None, "sneaky: in no lane"),
]


# --- 5. lane verdict --------------------------------------------------------

S, F_, X, K = "success", "failure", "cancelled", "skipped"
UP = {"respool-full-crash": "respool-full-functional"}

# (lane, results, docs_only, qualify, qualify_jobs, expected ok, label)
VCASES = [
    ("cheap", {"changes": S, "build": S}, "true", "false", ",", True, "cheap all green"),
    ("cheap", {"changes": S, "build": K}, "true", "false", ",", False, "cheap skip is red"),
    ("cheap", {"changes": F_, "build": S}, "", "", "", False, "classifier failure is red"),
    ("regression", {"golden": K, "tapectl": K}, "true", "false", ",", True, "docs-only skips regression"),
    ("regression", {"golden": S, "tapectl": S}, "false", "false", ",", True, "code change runs regression"),
    ("regression", {"golden": K, "tapectl": S}, "false", "false", ",", False, "unexpected regression skip"),
    ("regression", {"golden": S, "tapectl": F_}, "false", "false", ",", False, "regression failure"),
    ("regression", {"golden": S, "tapectl": X}, "false", "false", ",", False, "regression cancelled"),
    ("regression", {"golden": S, "tapectl": S}, "", "", "", True, "classifier empty: runs"),
    ("regression", {"golden": K, "tapectl": K}, "", "", "", False, "classifier empty: skip is red"),
    ("qualification", {"promote-package": K, "respool-full-functional": K, "respool-full-crash": K},
     "false", "false", ",", True, "qualification not selected"),
    ("qualification", {"promote-package": S, "respool-full-functional": K, "respool-full-crash": K},
     "false", "false", ",promote-package,", True, "changed package selected"),
    ("qualification", {"promote-package": K, "respool-full-functional": K, "respool-full-crash": K},
     "false", "false", ",promote-package,", False, "selected package skipped"),
    ("qualification", {"promote-package": S, "respool-full-functional": K, "respool-full-crash": K},
     "false", "false", ",", False, "unselected job ran"),
    ("qualification", {"promote-package": S, "respool-full-functional": S, "respool-full-crash": S},
     "false", "true", ",", True, "full qualification"),
    ("qualification", {"promote-package": S, "respool-full-functional": S, "respool-full-crash": K},
     "false", "true", ",", False, "matrix skipped under a selected upstream"),
    ("qualification", {"promote-package": S, "respool-full-functional": S, "respool-full-crash": S},
     "", "", "", True, "classifier empty: qualification runs"),
    ("qualification", {"promote-package": K, "respool-full-functional": K, "respool-full-crash": K},
     "", "", "", False, "classifier empty: qualification skip is red"),
    ("qualification", {"promote-package": K, "respool-full-functional": K, "respool-full-crash": K},
     "true", "true", ",", True, "docs-only beats a stale qualify"),
    ("qualification", {"promote-package": K, "respool-full-functional": S, "respool-full-crash": S},
     "false", "false", ",respool-full-functional,", True, "matrix follows its changed upstream"),
    ("qualification", {}, "false", "true", ",", False, "empty lane"),
]


def vtable(verdict):
    return [label for lane, res, d, q, qj, want, label in VCASES
            if verdict(lane, res, d, q, qj, UP)[0] != want]


def skip_always_ok(lane, res, d, q, qj, up):
    return L.lane_verdict(lane, {k: (S if v == K else v) for k, v in res.items()}, d, q, qj, up)


def ignores_cancelled(lane, res, d, q, qj, up):
    return L.lane_verdict(lane, {k: (S if v == X else v) for k, v in res.items()}, d, q, qj, up)


def empty_means_not_selected(lane, res, d, q, qj, up):
    return L.lane_verdict(lane, res, d or "true", q or "false", qj, up)


def ran_when_unselected_ok(lane, res, d, q, qj, up):
    ok, lines = L.lane_verdict(lane, res, d, q, qj, up)
    if not ok and all("not selected" in l and "success" in l or l.startswith("ok") for l in lines):
        return True, lines
    return ok, lines


def no_upstream(lane, res, d, q, qj, up):
    return L.lane_verdict(lane, res, d, q, qj, {})


VMUTANTS = [skip_always_ok, ignores_cancelled, empty_means_not_selected,
            ran_when_unselected_ok, no_upstream]


# --- 3. CLI ------------------------------------------------------------------


def cli(paths, event="pull_request", labels=""):
    with tempfile.TemporaryDirectory() as t:
        out = pathlib.Path(t) / "out"
        r = subprocess.run([sys.executable, "-B", str(SCRIPT)], input="\0".join(paths).encode(),
                           capture_output=True,
                           env={**os.environ, "GITHUB_OUTPUT": str(out), "EVENT": event, "LABELS": labels})
        return r.returncode, r.stdout.decode().splitlines()[0], out.read_text()


CLI_CASES = [
    (["docs/STATUS.md", "README.md"], "pull_request", "",
     "docs_only=true\nqualify=false\nqualify_jobs=,\n"),
    (["docs/STATUS.md", "engine/src/tape.c"], "pull_request", "",
     "docs_only=false\nqualify=true\nqualify_jobs=,\n"),
    ([], "pull_request", "", "docs_only=false\nqualify=true\nqualify_jobs=,\n"),
    (["host/tapectl.c"], "pull_request", "", "docs_only=false\nqualify=false\nqualify_jobs=,\n"),
    (["host/tapectl.c"], "pull_request", "software-lead,qualification",
     "docs_only=false\nqualify=true\nqualify_jobs=,\n"),
    (["tests/promote_adapter/run_product.py"], "pull_request", "",
     "docs_only=false\nqualify=false\nqualify_jobs=,promote-package,wp11-mutation-gate,\n"),
    (["docs/STATUS.md"], "schedule", "", "docs_only=false\nqualify=true\nqualify_jobs=,\n"),
]


def report(kind, mutants, table_fn):
    bad = 0
    for m in mutants:
        caught = table_fn(m)
        print(("killed   " if caught else "SURVIVED ") + f"{kind} {m.__name__}: {len(caught)} case(s) differ"
              + (f", e.g. {caught[0] if isinstance(caught[0], str) else caught[0][0]}" if caught else ""))
        bad += not caught
    return bad


def main() -> int:
    bad = 0
    # 1. docs-only
    real = table(C.classify)
    for paths, want, label in CASES:
        got = C.classify(paths)
        print(f"{'ok  ' if got == want else 'FAIL'}  {want:<9} {label}: {paths}")
    bad += bool(real)
    bad += report("docs-only", MUTANTS, table)

    # 2. qualification selection
    qreal = qtable(L.classify_paths)
    for paths, event, labels, wd, wq, label in QCASES:
        docs, q, jobs, _ = L.classify_paths(paths, event, labels, DEPS)
        good = docs == wd and (wd or (ALL if q else jobs) == wq)
        shown = "docs-only" if wd else (wq if wq == ALL else (" ".join(sorted(wq)) or "none"))
        print(f"{'ok  ' if good else 'FAIL'}  qualification {shown:<12.60} {label}")
    bad += bool(qreal)
    bad += report("selector", QMUTANTS, qtable)

    # 3. CLI
    for paths, event, labels, want in CLI_CASES:
        rc, line, out = cli(paths, event, labels)
        good = rc == 0 and out == want
        print(f"{'ok  ' if good else 'FAIL'}  cli {event} {paths} {labels!r} -> {out.strip()!r}")
        bad += not good

    # 4. lane wiring
    wf = lane_failures(WORKFLOW_TEXT)
    for f in wf:
        print("FAIL lane wiring: " + f)
    if not wf:
        sizes = {k: len(v) for k, v in L.lanes(WORKFLOW_TEXT).items()}
        print(f"ok    lane wiring: {sizes}; every job in exactly one lane")
    bad += bool(wf)
    for fn, job, needle in WMUTANTS:
        got = lane_failures(fn(WORKFLOW_TEXT, job))
        caught = any(needle in g for g in got)
        print(("killed   " if caught else "SURVIVED ") + f"workflow {fn.__name__}({job})"
              + (f" -> {next(g for g in got if needle in g)}" if caught else f"; got {got[:2]}"))
        bad += not caught

    # 5. lane verdict
    vreal = vtable(L.lane_verdict)
    for lane, res, d, q, qj, want, label in VCASES:
        ok, _ = L.lane_verdict(lane, res, d, q, qj, UP)
        print(f"{'ok  ' if ok == want else 'FAIL'}  verdict {lane:<13} {'PASS' if want else 'RED ':<4} {label}")
    bad += bool(vreal)
    bad += report("verdict", VMUTANTS, vtable)

    print(f"{len(CASES)} docs-only, {len(QCASES)} selection, {len(CLI_CASES)} CLI, "
          f"{len(VCASES)} verdict cases; {len(MUTANTS) + len(QMUTANTS) + len(WMUTANTS) + len(VMUTANTS)} "
          "broken variants")
    print("== change classifier and lanes: " + ("PASS" if not bad else "FAIL") + " ==")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
