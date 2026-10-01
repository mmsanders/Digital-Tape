# spec/VERSION.md — the spec bundle manifest

**Bundle:** DRAFT-10 · **Issued:** on Michael's authorization (below) · **Owner:** Program Manager

`Digital-Tape` `main` is the **single canonical publication point** for these documents. A copy anywhere else — a verification branch, a PM communiqué, a chat attachment, a surge branch — is a courtesy copy and is not authoritative. If a courtesy copy disagrees with `main`, `main` wins, and the disagreement is a finding.

## The bundle

| File | Revision | SHA-256 |
|---|---|---|
| `spec/tapefs-v1.md` | DRAFT-10 | `285410578ab6efd9e23a64ead8ace49973c6c048b36a627c97e0845d5560cde8` |
| `spec/engine-api.md` | DRAFT-10 | `aa042e41e35b02bf2bb6b3896e59340a947720c27dc5fc52a24d657ccd66b33a` |
| `spec/acceptance.md` | DRAFT-10 | `0a3488d9f77be47883721c75071fa4fa360ec2551f10ca18c9140f8e54b6f7a3` |

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

DRAFT-9 is the PM's narrow V9-001 correction authorized by Michael on 25 September 2026 Pacific time: it adds exactly one `dev_progress` → caller-supplied `tape_progress_fn` indirect-call funnel in `engine/src/dev.h`. It changes no media semantics, exported engine ABI, callback signature or numeric resource limit. Verification PR #82 independently reviewed the exact bytes and published the revised WP13-G5 package; PM issued the bundle through product PR #247 at main `7910ae3701fbfd94b5ea0558a69a29955da1dd5c`. The hashed documents retain their reviewed **NOT FROZEN** banners; `docs/PHASE0-FREEZE.md` supersedes those banners for exact V9-001. No implementation or acceptance follows from issuance alone.

DRAFT-10 is the PM's docket revision (Product #308), resumed at Michael's instruction on 1 October 2026 after every Phase 1 engine package was reconciled against DRAFT-9. It changes **no field, layout or CRC**. One item changes behaviour: **V10-001** (Verification finding V-R54-03) makes raw `tape_format`/`tape_dup` treat a destination with no structurally valid superblock as blank only when both blocks are entirely zero, and zero any residue first, closing a two-interruption path that could remount a copy under the previous UUID. The rest are clarifications already applied by PM rulings: **V10-002** drops two WP-06e examples unreachable under the §9.3.3 stage oracle; **V10-003** lets blank-media rows read `TAPE_ERR_BAD_MAGIC` or `TAPE_ERR_CRC`, matching §4.1; **V10-004** states the WP-06f re-spool floor as §9.4 does; **V10-005** scopes WP-12a's audio-continues clause to a Playing source. `engine-api.md` changes only its header. Issuance requires Verification's independent adversarial review of these exact bytes and Michael's authorization, recorded here when given. Embedded spec copies under `docs/` and `tests/` keep their declared DRAFT-8/DRAFT-9 roots (`tests/IMPORTS.json` `spec_bundle`). No implementation or acceptance follows from issuance alone.
