#!/usr/bin/env python3
"""Structural Rule 1 ordering, with the narrow ADR-206 review-regression route.

Rule 1 (audit-evidence-integrity.py, check 6): on a branch carrying both, every
commit touching a verifier package tree comes strictly before every commit
touching engine/ or firmware/, and no commit does both. ADR-206 (PM662) admits
exactly one exception: an independent regression package published AFTER
Verification reviewed a held implementation, imported on that branch before
the corresponding correction. Contract: tests/review_order_r1/CONTRACT.md.

A package change after implementation is excused only when all of these hold,
and anything missing, malformed or unreachable refuses (fails closed):

  - its final protected tests/IMPORTS.json entry carries full 40-hex
    `review_of`, `review_fix`, `source_commit` and `review_attestation`
    {source_commit, path, entry};
  - the path is NEW: absent at the base, and touched by exactly one commit on
    the branch (the first import), whose manifest already declares the final
    source_commit and tree; that tree, the head's tree and the verifier's tree
    at source_commit are the same;
  - no commit combines a package change with implementation;
  - review_of is on the branch, a strict ancestor of the import, and every
    implementation commit before the import is an ancestor of it (a stale
    reviewed SHA cannot excuse newer unreviewed code);
  - review_fix is an implementation commit on the branch, a strict descendant
    of the import, changing an attested covered path;
  - source_commit and the attestation's source_commit are reachable from the
    authenticated verifier main, and the attestation record, read from there,
    agrees exactly with the entry, the import and the fix, and states
    publication_before_import_and_fix: true.

Git proves lineage and identities only. That the correction fixes the defect
and that the publication preceded it are facts the independent attestation
supplies; no Product-side boolean or timestamp is read for them.

Usage (the contract's entry point):
  review_order_gate.py --repo PRODUCT --base SHA --head SHA \
      --verification-repo VERIFIER --verification-main SHA --manifest tests/IMPORTS.json
Exit 0 compliant, 1 refused.
"""
import argparse
import json
import re
import subprocess
import sys

IMPL_PREFIXES = ("engine/", "firmware/")
IMPL_EXEMPT = ("engine/test/",)  # ADR-158
DRAFT8_RE = re.compile(r"^(tests/[^/]+_draft8)(?:/|$)")
FULL = re.compile(r"^[0-9a-f]{40}$")
VERIFIER_REPO = "mmsanders/digital-tape-verification"
SCHEMA = "verification/review-lineage/1"
REVIEW_FIELDS = ("review_of", "review_fix", "review_attestation")


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def is_ancestor(repo, a, b):
    """a is an ancestor of (or equal to) b."""
    return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", a, b],
                          capture_output=True).returncode == 0


def is_commit(repo, sha):
    return isinstance(sha, str) and git(repo, "rev-parse", "--verify", "--quiet", sha + "^{commit}") == sha


def is_impl(path):
    return path.startswith(IMPL_PREFIXES) and not path.startswith(IMPL_EXEMPT)


def manifest_at(repo, rev, path):
    text = git(repo, "show", f"{rev}:{path}")
    if text is None:
        return None
    try:
        doc = json.loads(text)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def packages(doc):
    out = {}
    for p in (doc or {}).get("packages", []) or []:
        if isinstance(p, dict) and isinstance(p.get("path"), str):
            out[p["path"].rstrip("/")] = p
    return out


def evaluate(repo, base, head, vrepo, vmain, manifest="tests/IMPORTS.json"):
    """Return (failures, notes). An empty failure list means Rule 1 holds."""
    failures, notes = [], []
    if not (is_commit(repo, git(repo, "rev-parse", base) or "") and is_commit(repo, git(repo, "rev-parse", head) or "")):
        return ["base or head is not a commit"], notes
    base, head = git(repo, "rev-parse", base), git(repo, "rev-parse", head)
    commits = (git(repo, "rev-list", "--reverse", "--topo-order", f"{base}..{head}") or "").split()
    final = manifest_at(repo, head, manifest)
    if final is None:
        return [f"{manifest} unreadable at head"], notes
    entries = packages(final)
    declared = set(entries) | set(packages(manifest_at(repo, base, manifest)))

    def pkgs_of(files):
        out = set()
        for f in files:
            m = DRAFT8_RE.match(f)
            if m:
                out.add(m.group(1))
            out |= {d for d in declared if f == d or f.startswith(d + "/")}
        return out

    touched, impl_at = {}, {}
    for c in commits:
        # Same file listing as audit-evidence-integrity.py's Rule 1 (merges: combined diff).
        files = [f for f in (git(repo, "show", "--pretty=", "--name-only", c) or "").split("\n") if f]
        touched[c] = (pkgs_of(files), files)
        impl_at[c] = any(is_impl(f) for f in files)

    first_impl = next((i for i, c in enumerate(commits) if impl_at[c]), None)
    late = {}
    for i, c in enumerate(commits):
        pkgs, _ = touched[c]
        if pkgs and impl_at[c]:
            failures.append(f"commit {c[:12]} changes a verifier package tree AND implementation")
        elif pkgs and first_impl is not None and i > first_impl:
            for p in pkgs:
                late.setdefault(p, []).append(c)
    if failures or not late:
        return failures, notes

    vmain_ok = bool(vrepo) and is_commit(vrepo, vmain or "")
    if not vmain_ok:
        return [f"late change to {p}: no authenticated verifier main to check a review-regression route"
                for p in sorted(late)], notes

    for p in sorted(late):
        why = review_route(repo, base, head, vrepo, vmain, manifest, commits, touched, impl_at, p, entries.get(p))
        if why:
            failures.append(f"{p} changes after implementation ({late[p][0][:12]}) and is not an attested "
                            f"review-regression import: {why}")
        else:
            notes.append(f"{p}: attested review-regression import (ADR-206)")
    return failures, notes


def review_route(repo, base, head, vrepo, vmain, manifest, commits, touched, impl_at, path, e):
    if e is None:
        return "no entry in the head manifest"
    missing = [k for k in REVIEW_FIELDS if k not in e]
    if missing:
        return "missing " + ", ".join(missing)
    for k in ("review_of", "review_fix", "source_commit"):
        if not (isinstance(e.get(k), str) and FULL.match(e[k])):
            return f"{k} is not a full 40-hex SHA"
    if str(e.get("source_repo", "")).lower() != VERIFIER_REPO:
        return "source_repo is not the independent verifier repository"
    if git(repo, "cat-file", "-t", f"{base}:{path}") is not None:
        return "path existed at the base: a preexisting tree edit, not a new package"
    hits = [c for c in commits if path in touched[c][0]]
    if len(hits) != 1:
        return f"{len(hits)} commits touch the package; only its single first import may"
    imp = hits[0]
    tree = git(repo, "rev-parse", f"{imp}:{path}")
    if not tree or tree != e.get("tree") or git(repo, "rev-parse", f"{head}:{path}") != tree:
        return "import/head tree does not equal the declared tree"
    at_import = packages(manifest_at(repo, imp, manifest)).get(path)
    if not at_import or at_import.get("source_commit") != e["source_commit"] or at_import.get("tree") != tree:
        return "the import commit's manifest does not already declare the final source_commit and tree"
    if not is_commit(vrepo, e["source_commit"]) or not is_ancestor(vrepo, e["source_commit"], vmain):
        return "source_commit is not reachable from verifier main"
    if git(vrepo, "rev-parse", f"{e['source_commit']}:{path}") != tree:
        return "verifier tree at source_commit differs"

    rev = e["review_of"]
    if not is_commit(repo, rev) or rev == imp or not is_ancestor(repo, rev, imp) or is_ancestor(repo, rev, base):
        return "review_of is not a held branch commit strictly before the import"
    for c in commits:
        if c == imp:
            break
        if impl_at[c] and not is_ancestor(repo, c, rev):
            return f"implementation {c[:12]} before the import is not covered by review_of (stale review)"

    fix = e["review_fix"]
    if fix not in touched or fix == imp or not is_ancestor(repo, imp, fix) or not impl_at[fix]:
        return "review_fix is not an implementation commit on the branch after the import"

    att = e["review_attestation"]
    if not (isinstance(att, dict) and all(isinstance(att.get(k), str) and att[k] for k in ("source_commit", "path", "entry"))):
        return "review_attestation needs source_commit, path and entry"
    if not FULL.match(att["source_commit"]) or not is_commit(vrepo, att["source_commit"]) \
            or not is_ancestor(vrepo, att["source_commit"], vmain):
        return "attestation source_commit is not reachable from verifier main"
    text = git(vrepo, "show", f"{att['source_commit']}:{att['path']}")
    try:
        reg = json.loads(text) if text is not None else None
    except ValueError:
        reg = None
    if not isinstance(reg, dict) or reg.get("schema") != SCHEMA or not isinstance(reg.get("entries"), dict):
        return "attestation registry missing or malformed on verifier main"
    rec = reg["entries"].get(att["entry"])
    if not isinstance(rec, dict):
        return "attestation entry absent"
    expect = {"source_repo": e.get("source_repo"), "source_commit": e["source_commit"], "source_path": path,
              "tree": tree, "review_of": rev, "import_commit": imp, "fix_commit": fix}
    for k, v in expect.items():
        if rec.get(k) != v:
            return f"attestation {k} does not match"
    if rec.get("publication_before_import_and_fix") is not True:
        return "attestation does not state publication before import and fix"
    covered = rec.get("covered_paths")
    if not (isinstance(covered, list) and covered and all(isinstance(x, str) for x in covered)):
        return "attestation covered_paths missing"
    if not set(touched[fix][1]) & set(covered):
        return "review_fix changes no attested covered path"
    rh = rec.get("reviewed_head")
    if not (isinstance(rh, str) and FULL.match(rh) and is_commit(repo, rh)
            and is_ancestor(repo, fix, rh) and is_ancestor(repo, rh, head)):
        return "attested reviewed_head is not on this lineage after the fix"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--verification-repo", required=True)
    ap.add_argument("--verification-main", required=True)
    ap.add_argument("--manifest", default="tests/IMPORTS.json")
    a = ap.parse_args()
    failures, notes = evaluate(a.repo, a.base, a.head, a.verification_repo, a.verification_main, a.manifest)
    for n in notes:
        print("  ok    " + n)
    for f in failures:
        print("  FAIL  " + f, file=sys.stderr)
    print("rule-1 ordering: " + ("REFUSED" if failures else "PASS"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
