# Software480 dependency and integration return

20 October 2026 PDT. **Dependency map complete; no implementation integrated at
this checkpoint.** Final S2 correction PASS is published, but expressly withholds
Product merge clearance. Other candidate acceptance gaps remain.
This is a Software integration inventory, not independent acceptance or a new brief.
Assignment: [Product480](https://github.com/mmsanders/Digital-Tape/issues/480),
updated 2026-10-20T15:40:30Z. Single temporary Software context, no subworkers.

## Authenticated inputs

Product main `5c17314af51ac22e8729d474f2a4d2edd756daef` contains issued input
`6130c8f826e3586dab149e3d4484edb18c04689a`. Verification main is
`32c6f245eaced5db063e80faf172090b2e7825f1` at intake, refreshed to final S2
publication `929c02f35aed6bad05d708d33ebff0cfb35ccc37`. Required four documents and live480,
APP-1/APP-1A including ADR-189 §7 and WP14 safety/session boundaries were read.
Frozen DRAFT-10 remains unchanged; exact normative blob IDs, candidate trees,
relevant imported-package trees and publication ancestry are in
[authentication.json](authentication.json). All five candidates retain engine
tree `d96b4245e04d74078f8938744b1394c3018516f7`.

The saved `pr-*.json` files are GitHub PR metadata/check snapshots retrieved at
approximately 09:03–09:04 PDT, not new runs or proof of current-main CI. GitHub's
legacy commit-status endpoint returned no statuses; check-run rollups were read
separately using `gh pr view --json ...statusCheckRollup`.

## Five candidates and concrete dependencies

| PR / exact head | Actual base / dependency | Carried disposition and remaining gate |
|---|---|---|
| [459](https://github.com/mmsanders/Digital-Tape/pull/459) `50bc4160f6da527da8c684d05264f99815aaa870` | PR base is obsolete436 branch at `6126d04050133cacb9a1960a0bc13c9ee93130e5`; its full history is already included | Verification203 bounded exhaustion/source correction PASS; Windows11 receipt225 received. Overall corrected-candidate disposition226 pending; native failed-open visibility and Mac enforceable exhaustion remain explicit. Retarget the complete corrected candidate to current main only when preparing authorized integration; never merge436 first or take only the one-commit correction diff. |
| [454](https://github.com/mmsanders/Digital-Tape/pull/454) `b9f430c8c9b33532abf07eea0ed2653310639f2d` | Base459; authenticated459 ancestor |203 process/report PASS,214 Linux start/middle/end PASS carry. Wait for accepted corrected INGEST, Windows exact-position/Mac start-write qualification, and independent INTERNAL/global JOINED_PEAK judgment. Closed470 is evidence, not a merge prerequisite. |
| [455](https://github.com/mmsanders/Digital-Tape/pull/455) `ecca8c1304ba9511d78791e92ed35fac494f2a27` | Main; runtime/acceptance depends on S1 and downstream S2/S3 |203 bounded parser/static PASS only. CI child source pin `35b23cacae886d9b3693b7104f581d8646ea5667` has exactly S1's `host/ingest` tree `835078995d4e9cc2424f9ea8d6f11304b45f783f`; this is source identity, not equality of platform binaries. Native installs/security/elevation, S3 and full G2 remain absent. |
| [469](https://github.com/mmsanders/Digital-Tape/pull/469) `1ad813d86d094a3702a03e3b2e602c221855a9ca` | Main at historical `7c6df21f62bd59fbc63226e35804dcac8ed05d2d`; no ancestry dependency on459/454/455/443 | Final return3/3 correction PASS published by [Verification227](https://github.com/mmsanders/digital-tape-verification/pull/227), merged09:08 PDT at `929c02f35aed6bad05d708d33ebff0cfb35ccc37`, CI39454305870 SUCCESS. The finding says **do not merge469 solely on this correction**; no Product merge clearance. This is an explicit clearance stop, not a remaining demonstrated Software defect or another correction loop. |
| [443](https://github.com/mmsanders/Digital-Tape/pull/443) `85b7c3fd0b123ae7e5d54cb9f7bb424fbc613542` | Main; separate coverage/architecture branch |199/216/218 bounded operation/source/PCM/fault/residue/long-copy judgments carry. Overall443 HELD:365 deferred faults,6 absent long coordinates, no repeated-LBA or arbitrary-large completeness. PM owns next scope/Q-P2-1(b); no new broad execution or batching permission. |

Git-object graph: `obsolete436 -> corrected459 -> S1/454 -> S4 child/runtime`;
`accepted main -> S2/469 -> future S3 -> later complete app/G2`;
`accepted main -> subset443` is a separate held route. S4's child dependency is
not Git ancestry. S2 can be integrated independently if its own exact clearance
and current-main checks permit; unimplemented S3/G2 must not hold bounded S2 open.

## Published evidence carried by identity

These commits were authenticated as ancestors of Verification main. Reports were
read; no original numerical/audio/crash/native campaign was re-executed.

| Publication | Immutable finding / exact carried boundary |
|---|---|
|199 `42f169f1b5448bc646a2b181ced51c14e385017c` | [Selected-state operation rows](https://github.com/mmsanders/digital-tape-verification/blob/42f169f1b5448bc646a2b181ced51c14e385017c/findings/P2-SUBSET-ROWS-2026-10-17/README.md); overall443 held |
|203 `9997bc1c388796283dc138d8bf6e6200e02cc390` | [459/454/455 bounded correction return](https://github.com/mmsanders/digital-tape-verification/blob/9997bc1c388796283dc138d8bf6e6200e02cc390/findings/P2-201-DISPOSITION-2026-10-18/RETURN.md); no overall merge permission |
|214 `e1f4bd72f2a6be75cfd8ebe8edb93ed534cfca1e` | [Linux positional report faults and S3 method blockers](https://github.com/mmsanders/digital-tape-verification/blob/e1f4bd72f2a6be75cfd8ebe8edb93ed534cfca1e/findings/P2-208-209-RETURNS-2026-10-19/README.md); two actual ID witnesses carry, INTERNAL/global JOINED_PEAK still unproved |
|216 `937dee3c3e98a9e04cb08d1166423104d7c62ece` | [Exact743f829 narrow source/PCM/seven-pilot return](https://github.com/mmsanders/digital-tape-verification/blob/937dee3c3e98a9e04cb08d1166423104d7c62ece/findings/P2-210-RETURN-2026-10-19/README.md) |
|218 `99df7f8c67627c13b33d0d55b5ba74ae2d43d699` | [Exact55552ad Stage3](https://github.com/mmsanders/digital-tape-verification/blob/99df7f8c67627c13b33d0d55b5ba74ae2d43d699/findings/P2-210-STAGE3-2026-10-19/README.md);39/404 executed,365 deferred,6 long cuts absent |
|217 `c5e28b80a0e505a295fa71daaef7a6d2c6f411c6` | [Previous S2 return](https://github.com/mmsanders/digital-tape-verification/blob/c5e28b80a0e505a295fa71daaef7a6d2c6f411c6/findings/P2-208-R3-2026-10-19/README.md); final fresh-head disposition still required |
|225 `32c6f245eaced5db063e80faf172090b2e7825f1` | [Windows11 receipt](https://github.com/mmsanders/digital-tape-verification/blob/32c6f245eaced5db063e80faf172090b2e7825f1/findings/P2-222-POLICY-2026-10-19/windows11-return-2026-10-20/README.md);1927/1927 received, not full independent payload/native/equivalence acceptance |
|227 `929c02f35aed6bad05d708d33ebff0cfb35ccc37` | [Final S2 correction PASS](https://github.com/mmsanders/digital-tape-verification/blob/929c02f35aed6bad05d708d33ebff0cfb35ccc37/findings/P2-208-FINAL-2026-10-20/README.md); source8f51ddf0 and eight carried fixtures/three returned archives, regression detected; expressly no Product merge clearance |

Package authentication compares actual Product tree, IMPORTS declaration, actual
Verification publication tree and publication ancestry. Relevant trees are APP
`bdd861b693516db2e5244660b3e99ee400d506de`, cards/make
`81b627b7149458c0037dda5e69eac337f40fb8bd`, subset
`c6cb573d654d337fef2f616f11cce0cee74e8968` and INGEST Stage1
`609a4c819076a2b85b26cc4f3cd254b92caef6de`. No imported oracle was edited.
Closed453/463/470/471 and466/467/209/210 remain completed evidence envelopes.

## Merge sequence and runnable-next-slice decision

1. **S2 first, conditionally.** Consumed208's merged final exact-head result. If it
   is bounded overall S2 PASS with integration permission, refresh its base against
   current main, preserve accepted source/test/evidence identities, and run the
   required PR integration checks. If there is a blocker, park under3/3 and route
   the precise blocker to PM; do not send a fourth correction. No current source
   change, another producer run or duplicate verifier request is necessary.
   **Actual final result:**227 grants bounded producer-correction PASS, explicitly
   withholds Product merge clearance and retains459/454/base holds. The Git graph
   shows469 is based on main, not459/454; no missing implementation dependency on
   those branches was found. Return this distinction to PM: reconcile the standalone
   S2 integration boundary with the published hold, preserving the independent
   finding and requiring current-main CI. Do not infer overall permission, invent
   a fourth correction or require unimplemented S3/G2 to finish S2.
2. **459 then454.**226 supplies the corrected-candidate criterion map. On explicit
   applicable clearance, integrate the entire corrected459 ancestry directly to
   main, preserving the correction in history. Then retarget454 to the accepted
   main/base and carry identity-equivalent source/evidence. Do not restore defective
   436 or merge evidence-only463/470 as prerequisites. Any necessary clean split
   happens before fresh disposition; a post-disposition carry needs the explicit
   PM identity-carry treatment required by the issue workflow, not a silent rebase.
3. **S3 has no runnable enabled platform.** Published Stage1 FEASIBILITY plus
   APP-1A §7 require successful safety/authorization/object binding before a
   write-mode open. Windows/macOS access upgrade or post-open comparison does not
   establish that. Linux retained inode/diskseq does not prove the successful
   upgrade cannot reach changed media.208 must publish the §7 oracle extension and
   explicit platform method clearance before Software imports/implements an enabled
   slice. Known refusal stays exit3/zero writes/zero write-mode opens; ordinary
   query failure is HOST_QUERY_FAILED, actual change CARD_CHANGED, no reopen.
4. **S4 and443 stay scoped.** Carry203 parser/static acceptance without rebuilding
   it. Full app/native/G2 await accepted dependencies and separately issued work;
   S5 is not licensed.443 requires a fresh bounded PM coverage decision, not a new
   exhaustive campaign or inferred clearance from its supporting publications.

Current saved checks:443 **118 SUCCESS/3 SKIPPED**,454 **124/2**,455 **117/0**,
459 **121/2**,469 **118/0**; no saved failure/pending. All remain drafts.443/455/469
are BEHIND current main;454/459 are CLEAN only against their stacked bases.
Read-only `git merge-tree $(git merge-base MAIN HEAD) MAIN HEAD` previews showed
no conflict markers for any candidate. This is not a merge or tested integration.

[Live-rule snapshot](main-rules.json), ruleset22084355, requires current-base strict
checks: `evidence gate can go red`, `evidence integrity`, `docs size and line budgets`,
`hygiene gate can go red`, `cheap`, `regression`, `qualification`; code-owner review
and resolved review threads also apply. Do not bypass the rules or count historical
exact-head success as a fresh tested merge. Preserve native/full-package holds.

## Executed checks and bounded stop

Cloned Product and published Verification history; authenticated five head pins,
all relevant declared package tree identities, eight inherited main publications,
engine identity, corrected436/459/454 ancestry and S4/S1 source equivalence using:

```powershell
./docs/REVIEW/software480/authenticate.ps1 -VerificationRepository ../Verification-publications
```

Result: PASS, recorded in authentication.json. Saved actual GitHub rollups/rules;
read-only merge previews were clean. No Product build, shipping replacement,
collector/kit/card/security action, original campaign replay or independent
acceptance was performed. This docs-only return uses normal PR hygiene/cheap CI;
skipped engine jobs would supply no Product execution evidence.

**Blocked implementation stop:** S2 final correction is published/PASS; PM must
resolve the explicit standalone-integration clearance boundary, not send correction4;
INGEST/S1 disposition with226; S3 §7 extension/platform method with208; broader443
scope with PM. No fact request requiring a new Software return was found in the
live paired issues. The dependency map is the completed480 deliverable; PM can
schedule the cleared next slice from these exact identities. Phase2 remains6/12.
