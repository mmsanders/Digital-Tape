# spec/VERSION.md — the spec bundle manifest

**Bundle:** DRAFT-8 · **Issued:** 6 Sep 2026 · **Owner:** Program Manager

`Digital-Tape` `main` is the **single canonical publication point** for these documents. A copy anywhere else — a verification branch, a PM communiqué, a chat attachment, a surge branch — is a courtesy copy and is not authoritative. If a courtesy copy disagrees with `main`, `main` wins, and the disagreement is a finding.

## The bundle

| File | Revision | SHA-256 |
|---|---|---|
| `spec/tapefs-v1.md` | DRAFT-8 | `a769c772ba9efd867badeaa6dbc4dd731913a31b01a5c296336686463093e792` |
| `spec/engine-api.md` | DRAFT-8 | `d19c8f2453c258c582622c3447a792215debd3ec68df81c306d47ae5b57da836` |
| `spec/acceptance.md` | DRAFT-8 | `d2cf1f620f582df46bbcd736eed589aefe04512ca7953f15601850210d51ca81` |

The three revisions must be identical. `spec/VERSION.md` is not itself hashed.

## Why this file exists

On **4 September 2026**, before this file existed, `main` published:

- `spec/tapefs-v1.md` at **DRAFT-3**
- `spec/engine-api.md` at **DRAFT-3**
- `spec/acceptance.md` at **DRAFT-1**

Each of those documents claimed in its own header to be versioned in step with the others. Two of them were two revisions apart. The claim was true when written and became false without anything noticing, because nothing was checking — the same failure mode as the unversioned charter and the stale spec on `main` before it. **Three silent desyncs, three catches by a human happening to look.**

A header that asserts consistency is not a mechanism. This file plus the gate below is.

## The gate

`tools/ci/verify-spec-bundle.sh`, run on every PR touching `spec/`:

```sh
#!/bin/sh
# Fails if any spec file's content or revision drifts from spec/VERSION.md.
set -eu
cd "$(dirname "$0")/../.."
fail=0

# 1. Content hashes match the manifest.
awk -F'|' '/^\| `spec\// {
    gsub(/[` ]/,"",$2); gsub(/[` ]/,"",$4); print $4"  "$2
}' spec/VERSION.md > /tmp/spec-bundle.sha256
sha256sum -c /tmp/spec-bundle.sha256 || fail=1

# 2. All three revision strings are identical, and match the manifest.
want=$(sed -n 's/.*\*\*Bundle:\*\* \([A-Z0-9-]*\).*/\1/p' spec/VERSION.md | head -1)
for f in spec/tapefs-v1.md spec/engine-api.md spec/acceptance.md; do
    got=$(sed -n 's/^\*\*Revision:\*\* \([A-Z0-9-]*\).*/\1/p' "$f" | head -1)
    [ "$got" = "$want" ] || { echo "FAIL: $f is $got, bundle is $want"; fail=1; }
done

exit $fail
```

**The gate must be proven able to go red** before it counts as green, per the rule already in `tools/ci/verify-gates.sh`: flip one byte in a spec file, confirm the gate fails, revert.

## Updating the bundle

Only the PM issues a new bundle. The Software Lead lands it mechanically:

1. Replace all three files with the PM's copies. **`cmp` them; change nothing, including the status banner** — the banner is inside the hashed content.
2. Replace `spec/VERSION.md` with the PM's copy.
3. Run the gate locally. If it is red, the bundle was mis-transcribed — do not adjust the hashes to match the files.
4. If a spec file is *wrong*, that is a `pm-decision` issue, not an edit in this PR.

This DRAFT-8 text was drafted by surge support on `surge/draft-8-freeze-candidate` (PR #25) for the PM to issue. The status banner inside the three hashed files remains **NOT FROZEN**. Merging this PR onto `main` is the issue of the bundle; it is not a freeze and it is not authorisation for anyone else to edit `spec/` on `main`.
