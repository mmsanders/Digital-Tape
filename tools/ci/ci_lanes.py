"""CI execution lanes (roadmap R1, P2-R1 #385): shared by the classifier, the lane
verdict and their negative controls.

ci.yml groups its jobs into three lanes. Each lane ends in one aggregate job,
whose check name is the lane name, and whose `needs:` list IS the lane:

  cheap          docs, spec, build and guardrails.   Runs on every change.
  regression     current-engine replays, goldens,    Runs on every change that
                 package self-checks, tapectl.       is not docs-only.
  qualification  full campaigns, mutation, the WP-10 Runs on the daily schedule,
                 crash backlogs, the re-spool crash  workflow_dispatch, a PR
                 matrix.                             labelled `qualification`
                                                     (phase gates), and any change
                                                     that could move an engine
                                                     result. A job also runs when
                                                     one of its own test
                                                     directories changed.

Every rule here fails toward running more. The classifier says a lane is NOT
needed only when every changed path is positively known not to matter to it; an
empty, unreadable or unrecognised path selects everything.

Standard library only: the classifier must not depend on an installed YAML
module, because a missing module would otherwise fail toward running less.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
TESTS = ROOT / "tests"

LANES = ("cheap", "regression", "qualification")
PHASE_GATE_LABEL = "qualification"
FULL_EVENTS = ("schedule", "workflow_dispatch")

DOCS_GATE = "needs.changes.outputs.docs_only != 'true'"
QUALIFY_GATE = "needs.changes.outputs.qualify != 'false'"


def qualify_job_gate(job: str) -> str:
    """The per-job clause a qualification job carries in its `if:`."""
    return f"contains(needs.changes.outputs.qualify_jobs, ',{job},')"


# Paths positively known not to move any qualification result. Everything
# not listed here (engine/, spec/ outside spec/hw/, tools/, ci.yml, any file
# directly under tests/, any root file, anything unrecognised) selects the
# whole qualification lane.
#
# host/ is deliberately inert: tapectl is not linked by any qualification
# campaign. The mutation gate's `golden` suite does run through tapectl, so
# that one dependency is covered by `regression` (golden, tapectl) on every
# change and by the daily qualification run, not per PR (#385 inventory).
QUALIFICATION_INERT_PREFIXES = (
    "host/",
    "site/",
    "hardware/",
    "spec/hw/",
)
QUALIFICATION_INERT_FILES = (
    ".github/CODEOWNERS",
)


def canonical(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path:
        return False
    return not any(p in ("", ".", "..") for p in path.split("/"))


def docs_path(path: str) -> bool:
    """docs/** except docs/verification/**, site/**, and root *.md (#347)."""
    if not canonical(path):
        return False
    parts = path.split("/")
    if len(parts) == 1:
        return path.endswith(".md")
    if parts[0] == "docs":
        return parts[1] != "verification"
    return parts[0] == "site"


# --- reading ci.yml without a YAML module --------------------------------


def workflow_jobs(text: str) -> dict[str, str]:
    """Top-level ci.yml job blocks keyed by job id."""
    lines = text.splitlines()
    try:
        start = lines.index("jobs:") + 1
    except ValueError:
        return {}
    jobs: dict[str, str] = {}
    current = None
    block: list[str] = []
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


def job_needs(block: str) -> list[str]:
    """Job ids in a job-level needs: entry, in order."""
    lines = block.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^    needs:\s*(.*)$", line)
        if not m:
            continue
        tail = m.group(1).strip()
        if tail:
            return re.findall(r"[A-Za-z0-9_-]+", tail)
        result = []
        for continuation in lines[i + 1:]:
            m2 = re.match(r"^      -\s*([A-Za-z0-9_-]+)\s*$", continuation)
            if m2:
                result.append(m2.group(1))
                continue
            if continuation.startswith("      ") or not continuation.strip() \
                    or continuation.lstrip().startswith("#"):
                continue
            break
        return result
    return []


def job_if(block: str) -> str:
    """The job-level if: expression, possibly folded over several lines."""
    lines = block.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^    if:\s*(.*)$", line)
        if not m:
            continue
        expr = [m.group(1).strip()]
        for continuation in lines[i + 1:]:
            if continuation.startswith("      "):
                expr.append(continuation.strip())
                continue
            break
        return " ".join(e for e in expr if e and e not in (">", ">-", "|"))
    return ""


def lanes(text: str) -> dict[str, list[str]]:
    """Lane name -> member job ids, read from each aggregate job's needs.

    `changes` is listed in every aggregate so the verdict can read the
    classifier's outputs; it is a cheap-lane member only.
    """
    jobs = workflow_jobs(text)
    result = {}
    for lane in LANES:
        block = jobs.get(lane)
        members = job_needs(block) if block else []
        if lane != "cheap":
            members = [m for m in members if m != "changes"]
        result[lane] = members
    return result


def upstream_member(jobs: dict[str, str], job: str, members: list[str]) -> str | None:
    """A lane member a transitively gated job inherits its selection from.

    A job without its own lane gate (the respool crash matrix and its
    aggregate) runs only when this upstream member ran.
    """
    for need in job_needs(jobs[job]):
        if need in members and need != job:
            return need
    return None


# --- which test directories each qualification job depends on --------------

_TEST_REF = re.compile(r"tests/([A-Za-z0-9_]+)")
_REL_REF = re.compile(r"\.\./([A-Za-z0-9_]+)")
_SOURCE_SUFFIXES = {".py", ".c", ".h", ".sh", ".mk", ".cjs", ".js"}


def _test_dirs() -> set[str]:
    return {p.name for p in TESTS.iterdir() if p.is_dir()} if TESTS.is_dir() else set()


def _referenced(text: str, known: set[str]) -> set[str]:
    found = set(_TEST_REF.findall(text)) | set(_REL_REF.findall(text))
    return found & known


def _dir_references(name: str, known: set[str]) -> set[str]:
    refs: set[str] = set()
    for f in (TESTS / name).rglob("*"):
        if not f.is_file():
            continue
        if f.suffix not in _SOURCE_SUFFIXES and f.name not in ("Makefile", "GNUmakefile"):
            continue
        try:
            if f.stat().st_size > 1 << 20:
                continue
            refs |= _referenced(f.read_text(errors="replace"), known)
        except OSError:
            continue
    return refs


def job_test_dirs(text: str, job: str) -> set[str]:
    """tests/<dir> names a job's steps reach, closed over source references.

    A directory is included when the job's own block names it, or when a
    source file in an included directory names it (tests/x or ../x). This
    over-includes rather than under-includes: a wrong inclusion costs one
    extra run; a missing one would skip a changed package.
    """
    jobs = workflow_jobs(text)
    known = _test_dirs()
    pending = _referenced(jobs.get(job, ""), known)
    seen: set[str] = set()
    while pending:
        d = pending.pop()
        if d in seen:
            continue
        seen.add(d)
        pending |= _dir_references(d, known) - seen
    return seen


def mutation_suite_dirs(text: str) -> set[str]:
    """The mutation gate depends on every suite it runs."""
    suites_file = ROOT / "tools/ci/mutation-suites.txt"
    if not suites_file.is_file():
        return set()
    out: set[str] = set()
    for line in suites_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out |= job_test_dirs(text, line)
    return out


def qualification_deps(text: str) -> dict[str, set[str]]:
    """Qualification job id -> the tests/<dir> names that select it."""
    jobs = workflow_jobs(text)
    members = lanes(text)["qualification"]
    deps = {}
    for job in members:
        if upstream_member(jobs, job, members) and not has_qualify_gate(jobs[job], job):
            continue  # inherits its upstream's selection
        d = job_test_dirs(text, job)
        if job == "wp11-mutation-gate":
            d |= mutation_suite_dirs(text)
        deps[job] = d
    return deps


def has_docs_gate(block: str) -> bool:
    return DOCS_GATE in job_if(block)


def has_qualify_gate(block: str, job: str) -> bool:
    expr = job_if(block)
    return QUALIFY_GATE in expr and qualify_job_gate(job) in expr


# --- classification -------------------------------------------------------


def classify_paths(paths, event: str, labels, deps: dict[str, set[str]]):
    """Return (docs_only, qualify, qualify_jobs, reasons).

    docs_only: every path is a docs path (and the event is a PR or push).
    qualify:   the whole qualification lane must run.
    qualify_jobs: qualification jobs selected by their own changed test dirs.
    """
    paths = list(paths)
    reasons: list[str] = []
    labels = {l.strip() for l in (labels or []) if l.strip()}

    if event not in ("pull_request", "push"):
        return False, True, set(), [f"{event or 'unknown event'}: everything runs"]

    docs_only = bool(paths) and all(docs_path(p) for p in paths)
    if not paths:
        reasons.append("no changed paths read: everything runs")
        return False, True, set(), reasons

    qualify = False
    if PHASE_GATE_LABEL in labels:
        qualify = True
        reasons.append(f"label '{PHASE_GATE_LABEL}': phase-gate qualification")

    selected: set[str] = set()
    for p in paths:
        if docs_path(p):
            continue
        if not canonical(p):
            qualify = True
            reasons.append(f"non-canonical path {p!r}: qualification")
            continue
        if p.startswith(QUALIFICATION_INERT_PREFIXES) or p in QUALIFICATION_INERT_FILES:
            continue
        if p.startswith(".github/workflows/") and p != ".github/workflows/ci.yml":
            continue
        parts = p.split("/")
        if parts[0] == "tests" and len(parts) > 2:
            hit = {job for job, dirs in deps.items() if parts[1] in dirs}
            if hit:
                selected |= hit
                reasons.append(f"{p}: package of {', '.join(sorted(hit))}")
            continue
        qualify = True
        reasons.append(f"{p}: may move an engine result: qualification")
    return docs_only, qualify, selected, reasons


# --- lane verdict ---------------------------------------------------------


def format_qualify_jobs(jobs) -> str:
    """",a,b," -- comma-delimited so contains(',a,') is exact and never trimmed."""
    return "," + "".join(f"{j}," for j in sorted(jobs))


def qualify_jobs_set(value: str) -> set[str]:
    return {j for j in (value or "").split(",") if j.strip()}


def lane_verdict(lane: str, results: dict[str, str], docs_only: str, qualify: str,
                 qualify_jobs: str, upstream: dict[str, str]):
    """Return (ok, lines) for one lane aggregate.

    results: member job id -> needs.<id>.result (success, failure, cancelled,
    skipped). docs_only/qualify/qualify_jobs are the classifier's raw outputs;
    an empty value (the classifier failed) means "run everything", so every
    member is then expected to succeed.
    """
    padded = qualify_jobs_set(qualify_jobs)

    def expected(job: str) -> bool:
        if lane == "cheap":
            return True
        if docs_only == "true":
            return False
        if lane == "regression":
            return True
        up = upstream.get(job)
        if up:
            return expected(up)
        return qualify != "false" or job in padded

    ok = True
    lines = []
    for job, result in results.items():
        want = expected(job)
        if result in ("failure", "cancelled"):
            good = False
        elif want:
            good = result == "success"
        else:
            good = result == "skipped"
        ok &= good
        lines.append(f"{'ok  ' if good else 'FAIL'}  {result:<9} "
                     f"{'selected' if want else 'not selected'}  {job}")
    if not results:
        ok = False
        lines.append("FAIL  lane has no members")
    return ok, lines
