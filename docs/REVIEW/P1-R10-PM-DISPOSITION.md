# P1-R10 PM disposition — corrected product run and main ruleset

**Date:** 13 September 2026 UTC  
**PM issue:** [#72](https://github.com/mmsanders/Digital-Tape/issues/72)  
**Input product main:** `d52730ffb4c9d8e634eded9caca208dcacb0d046`  
**Input verifier main:** `62b18deb8b4fbe6e797b00d792ee9f46ac0a8059`  
**Held PR #64 head:** `c18aa42579ef7c5ea92a4d70972d6a2daa6698bb`

## Corrected product bundle is ready for independent disposition

Software #70 completed the ordered test-first sequence. PR #71 merged the exact
corrected `tests/playback_complete_draft8/` publication onto main at the input
commit. Its tree is `6dbb23bb4626238b0f22427031a551d2ece454fd`, retained P1-R8
synthetic evidence is `d867fc68c80a2217508868c4b339d160b55ec2cc`, retained P1-R6
synthetic evidence is `c67ea8fa128e06393839f968ae3cc949d84e5f2a`, and the earlier
playback subtree remains `ff810814dbc8079c6903e6f85ed7ee312abd3076`. The import
changed only the verifier subtree and changed no engine or firmware file.

PM independently reproduced deterministic regeneration, the corrected package
self-test and saved synthetic replay on clean main. All ten families and twenty
behavioral controls pass, including F-1/F-2/F-3, and the retained earlier-package
tests remain green.

The held PR #64 product bundle at
`docs/verification/runs/2026-09-13-r9/product-evidence/` is bound to pre-run
code commit `5f44b97fe9fb3342fce3b58236a75ea27b4898a6`. That commit contains the
exact corrected package and is an ancestor of the final PR head. The engine,
firmware, Software adapter and harness delta between the prior failing candidate
head and this pre-run commit is empty; `engine/src/play.c` remains SHA-256
`d2a904d4f4b15595094d18f52ef3b4aeea30ce11320c2561e09b6ac82a7a49f1`.
The evidence manifest identifies a product adapter, exit zero, empty stderr, the
exact verifier source/tree and one consistent engine/archive/adapter build string.
The package's unmodified replay passes from the committed bytes.

The bundle reports byte-exact PCM for `one_intmax` (1 frame), `reverse_zero`
(1), `intmin` (2), `scrub_forward` (88,200), `scrub_reverse` (88,200),
`side_playing` (2) and `side_idle` (1), plus passing call/state assertions for
the three no-PCM empty/nonempty-zero families. This authenticates a product result
ready for independent review. It does **not** accept the implementation, product
behavior, PCM, a WP-11 golden or listening, and PR #64 remains draft and held.
Independent Verification issue
[#9](https://github.com/mmsanders/digital-tape-verification/issues/9) owns the
narrow raw-bundle disposition without access to product or adapter source.

## Main ruleset assessment

Ruleset `22084355`, **Branch protection on main**, is active on the default branch.
It requires pull requests, resolved review threads and eleven Actions contexts; it
blocks deletion and force-push, has no bypass actor, and requires zero approvals.
Those choices fit the current single-lead workflow and restore the previously missing
main protection. `strict_required_status_checks_policy` is false, so a PR is not
required to be tested against the latest main; enabling it would be useful hardening,
but is not required to preserve current authority.

One required context is misconfigured: `print packet is printable` belongs to the
path-filtered `hardware` workflow. That workflow does not start for docs, software,
test or dashboard-only pull requests, so GitHub leaves the required check pending and
blocks those merges. PR #71 merged one second before the ruleset's recorded update,
so it did not exercise the new list. Michael must either remove this context from the
required list, or change the workflow so a stable check with that exact name reports
on every pull request. The narrower fix is to remove it: hardware changes still run
all hardware jobs, while cross-stream work is not coupled to a job deliberately scoped
to hardware paths. No repository setting was changed by PM.

Because the defect blocks this round's durable PM/dashboard PR and future ordinary
merges, PM reported the changed blocker once on Michael #49. Routine Michael comments
and branch KEEP lists are retired: PM comments there only when his work changes or a
blocking dependency appears, and no longer publishes a retention list.

## Holds and next owner

Verification is the only newly ready lead. Software, Hardware and Surge receive no
issue this round. PR #20 and PR #64 remain draft and held; no product implementation
merge is authorized. WP-11 stays red and listening remains held until Verification
dispositions the exact product bundle and PM separately routes it. The frozen DRAFT-8
hashes, independent test ownership, test-first order, uncovered recording/crash/
warm-start/state/operation work, purchases, card qualification, fabrication and
charging holds all remain unchanged.
