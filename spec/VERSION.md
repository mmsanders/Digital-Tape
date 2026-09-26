# spec/VERSION.md — the spec bundle manifest

**Bundle:** DRAFT-9 · **Issued:** 26 Sep 2026 · **Owner:** Program Manager

`Digital-Tape` `main` is the **single canonical publication point** for these documents. A copy anywhere else — a verification branch, a PM communiqué, a chat attachment, a surge branch — is a courtesy copy and is not authoritative. If a courtesy copy disagrees with `main`, `main` wins, and the disagreement is a finding.

## The bundle

| File | Revision | SHA-256 |
|---|---|---|
| `spec/tapefs-v1.md` | DRAFT-9 | `3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d` |
| `spec/engine-api.md` | DRAFT-9 | `383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6` |
| `spec/acceptance.md` | DRAFT-9 | `ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d` |

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

DRAFT-8 was drafted by surge support on `surge/draft-8-freeze-candidate` (PR #25), issued by the PM, independently reviewed, and frozen by Michael's recorded 8 September 2026 signature.

DRAFT-9 is the PM's narrow V9-001 correction authorized by Michael on 25 September 2026 Pacific time: it adds exactly one `dev_progress` → caller-supplied `tape_progress_fn` indirect-call funnel in `engine/src/dev.h`. It changes no media semantics, exported engine ABI, callback signature or numeric resource limit. Its **NOT FROZEN** banners remain until the candidate bytes and revised WP13-G5 gate receive independent review and the PM records issuance. Merging an unreviewed candidate branch is not authorization to implement against it.
