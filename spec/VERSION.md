# spec/VERSION.md — the spec bundle manifest

**Bundle:** DRAFT-10 · **Issued:** on Michael's authorization (below) · **Owner:** Program Manager

`Digital-Tape` `main` is the **single canonical publication point** for these documents. A copy anywhere else — a verification branch, a PM communiqué, a chat attachment, a surge branch — is a courtesy copy and is not authoritative. If a courtesy copy disagrees with `main`, `main` wins, and the disagreement is a finding.

## The bundle

| File | Revision | SHA-256 |
|---|---|---|
| `spec/tapefs-v1.md` | DRAFT-10 | `2a6a9f7b6fe1e5f9e3fe068b3c6460a81256276082bb7e336c01dbf1e9c17eba` |
| `spec/engine-api.md` | DRAFT-10 | `aa042e41e35b02bf2bb6b3896e59340a947720c27dc5fc52a24d657ccd66b33a` |
| `spec/acceptance.md` | DRAFT-10 | `50aa63bd751fdc6b4636de0eb48253887be19b7ec2841768449217b4e9b9e547` |

The three revisions must be identical. `spec/VERSION.md` is not itself hashed.

## Additive host-layout erratum

Michael approved E-1 on 5 October 2026 Pacific (ADR-164). The effective host media
layout is this byte-identical DRAFT-10 bundle **plus** [ERRATUM-E1.md](ERRATUM-E1.md),
authenticated by [ERRATA.sha256](ERRATA.sha256). Only partition 1 changes from
0x0C FAT32 to 0x0E FAT16 at the same 16 MiB; engine-visible partition 2 is unchanged.
Verification #146 authenticates the exact additive text in its existing preflight.
Historical evidence retains its declared original bundle; no historical spec copy is rewritten.

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

DRAFT-10 is the PM's docket revision (Product #308), resumed at Michael's instruction on 1 October 2026 after every Phase 1 engine package was reconciled against DRAFT-9. It changes **no field, layout or CRC**. One item changes behaviour: **V10-001** (Verification finding V-R54-03) makes raw `tape_format`/`tape_dup` treat a destination with no structurally valid superblock as blank only when both blocks are entirely zero, and zero any residue first, closing a two-interruption path that could remount a copy under the previous UUID. The rest are clarifications already applied by PM rulings: **V10-002** drops two WP-06e examples unreachable under the §9.3.3 stage oracle; **V10-003** lets blank-media rows read `TAPE_ERR_BAD_MAGIC` or `TAPE_ERR_CRC`, matching §4.1; **V10-004** states the WP-06f re-spool floor as §9.4 does; **V10-005** scopes WP-12a's audio-continues clause to a Playing source. `engine-api.md` changes only its header. Verification #133 reviewed the first candidate (`27c7e331`), verified V10-001 exhaustively (528 DRAFT-9 resurrections, 0 under DRAFT-10 over 16.9M two-interruption images on 14 shapes) and returned READY AFTER NAMED FIXES. This revision applies V10R-001…V10R-008: the torn-last-zero row covers every exhaustion shape and either copy, the residue criterion adds the two mirror-candidate exhaustion shapes and tears both fresh superblock writes, and the WP-06f re-spool clause reads against the live set at the time of each write. Verification #136 re-reviewed that delta (finding `cc3ba4a`): every crash-table state reached by the #133 enumeration (264,626 one-interruption and 12,563,940 re-run states) has exactly one permitted row and stays inside it, and the recommendation was READY. Its one minor note, V10R2-001, is applied in the exact wording #136 proposed: the "no structurally valid superblock" sentence in acceptance Format-blank and the §9.6 row is scoped to `BAD_MAGIC`/`CRC` outcomes. **Michael authorized issuance on 1 October 2026 UTC:** “I authorize DRAFT-10 amendments V10-001…V10-005 as in PR #352. Please continue”. PM issued the bundle by merging Product PR #352 at head `ec6b9813af60202eed322e14d320cfaa8546484e`; the freeze record is in `docs/PHASE0-FREEZE.md`. Embedded spec copies under `docs/` and `tests/` keep their declared DRAFT-8/DRAFT-9 roots (`tests/IMPORTS.json` `spec_bundle`). No implementation or acceptance follows from issuance alone.
