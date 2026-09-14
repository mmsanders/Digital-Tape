# P1-R11-SW return — clean split candidate for the accepted playback boundary

Issue [#75](https://github.com/mmsanders/Digital-Tape/issues/75) under the
[P1-R11 PM disposition](../P1-R11-PM-DISPOSITION.md).

**Status: Ready for PM review.** A fresh, clean, draft candidate exists at
`claude/bold-hypatia-zhrrzf-split`, built from published main **by file and
symbol** rather than by merging or cherry-picking any held branch. It passes the
ten corrected playback families byte-exactly and 289/289 independent mount cases,
and the new bundle replays from the repository. Not acceptance, and not a merge
request.

## Identity

| Item | Value |
|---|---|
| Input product main | `6a8b2fb481cf43a8d84aad6c74336fc4a2a50d96` |
| **Pre-run code commit (built and run)** | **`86eb3b77756042c365e2d0353018b981c39c99e8`** |
| Draft PR / head | see the issue return comment; branch `claude/bold-hypatia-zhrrzf-split` |
| Independently accepted evidence commit / tree | `c18aa42579ef7c5ea92a4d70972d6a2daa6698bb` / `34bad4611b6849ed586c7ec701fa7ddafef0cb12` |
| Accepted code-under-test (byte source) | `5f44b97fe9fb3342fce3b58236a75ea27b4898a6` |
| Held ancestors, untouched | PR #20 `2e0e8a4b7bff42797ac37901196e5ea348b2e392`, PR #64 `c18aa42579ef7c5ea92a4d70972d6a2daa6698bb` |
| Verifier publication / package tree | `62b18deb8b4fbe6e797b00d792ee9f46ac0a8059` / `6dbb23bb4626238b0f22427031a551d2ece454fd` |
| `play.c` / `mount.c` / `chunks.c` sha256 | `d2a904d4…` / `324ba896…` / `82b5d16b…` |
| libtape.a sha256 (as linked) | `ee75398163cbbe0d9e7674f1905b300773c317204d56b091207c6fcf17767cf9` |
| Adapter source / wrapper / binary sha256 | `2349aa3a…` / `ebe108d0…` / `599e5441…` |
| Immutable evidence | `docs/verification/runs/2026-09-13-r11/` |

Input main drifted while this round ran: `6a8b2fb` is now three commits behind
`f121343`, all of them PM documentation and dashboard, no code. The branch is
cut from the exact assigned input as instructed.

## The split map — path and symbol

Eleven files, every one **byte-identical to the accepted candidate** (same git
blob ids, verified by `git rev-parse 5f44b97:<path>` against the staged blob):

| Path | Blob | Why |
|---|---|---|
| `engine/include/tape.h` | `7d72fc13…` | the frozen DRAFT-8 public surface the accepted run used |
| `engine/include/tape_dev.h` | `57e59641…` | device contract |
| `engine/src/mount.c` | `af4f826e…` | dispositioned mount behaviour |
| `engine/src/play.c` | `721735b1…` | the ten accepted families, `tape_status`, side-switch reset |
| `engine/src/tape_internal.h` | `59a99863…` | shared instance state |
| `engine/src/tapefs.c` | `babbae3d…` | superblock/index parsing |
| `tests/harness/media.h` | `bc0fcf49…` | harness dependency |
| `tests/harness/test_mount.c` | `0c568d5a…` | hard dependency (below) |
| `tests/harness/test_play.c` | `df1b07f4…` | playback scaffolding for this slice |
| `tests/playback_adapter/complete_probe.c` | `f6e55779…` | hard dependency (below) |
| `tests/Makefile` | `9deb01f0…` | the one include path `test_mount.c` needs |

Plus one new file, `engine/src/chunks.c`, whose function body is accepted bytes.

**Excluded**, though present in the accepted candidate: `engine/src/alloc.c`
(`267c9ec4…`) and `tests/harness/test_alloc.c` (`66e7afd1…`) — the VT8-001
allocator and its scaffolding. Also excluded: every historical evidence bundle
(`2026-09-13-r6/`, `-r7/`, `-r9/`), which stays intact on the held PR #64 branch,
and all unrelated harness and documentation work.

Symbols left behind in `alloc.c`, each with **zero** references from this slice:
`tape_may_reference`, `tape_may_allocate`, `tape_alloc_run`. `tape_internal.h`
keeps its accepted bytes and still declares them; a declaration binds no
definition.

### Two files that look optional and are not

* `tests/harness/test_mount.c` — main's version does **not compile** against the
  frozen DRAFT-8 header: `too many arguments to function 'tape_mount'`,
  `too few arguments to function 'tape_tell'`. Changing the header forces it.
* `tests/playback_adapter/complete_probe.c` — main's version predates the P1-R7
  scalar fixture-parse fix. Without it the run repeats that defect
  (`long_side_a_frames` read as `262144`), so the accepted observations are not
  reproducible with main's copy.

### The one judgment call

Linking the slice without `alloc.c` leaves exactly one undefined symbol, at
exactly one call site:

```
engine/src/mount.c:401: undefined reference to `tape_chunks_for_frames'
```

That is TapeFS §9.3.3's promote-resume **row 3** shape check inside `tape_mount`
— a mount-time comparison of `a_high_water` against the chunk length of an
`n`-frame timeline. It is inside the independently landed mount package's own
coverage (`M-stage-row3`, `M-stage-row3-H-boundary`, and the unmatched
`row3-H-boundary` negative), all of which this candidate runs and passes.

I judged that importing this one pure arithmetic function is **not** importing
uncovered implementation — the landed package drives it through the accepted
mount path — and so proceeded rather than stopping. `engine/src/chunks.c`
carries its accepted body byte for byte and nothing else, with a header comment
stating exactly why it exists. The alternative readings are both one commit away:
drop `chunks.c` and `mount.c` will not link; take `alloc.c` whole and the
uncovered allocator lands. If PM wants either, it is a small change.

## Proof the held history did not land

`git merge-base --is-ancestor` reports **absent** for all four of PR #20 head
`2e0e8a4b…`, PR #64 head `c18aa42…`, accepted code-under-test `5f44b97…` and the
earlier PR #64 head `bc53076…`. The branch's only parent is input main
`6a8b2fb`, and its single commit is `86eb3b7`. No merge commit, no cherry-pick.

## Checks

| Check | Result |
|---|---|
| corrected complete playback package, product run | **PASS** — 10 families, 7 PCM byte-exact |
| offline replay of the committed bundle | `REPLAY PASS` |
| independent mount package | **289 cases; 0 failed**; seed `0xd8a607` |
| complete package self-test (synthetic) | PASS |
| earlier three-family package self-test | PASS |
| VT8-001 package self-test | PASS |
| frozen spec bundle | OK on all three hashes |
| allocation / libc file I/O | clean |
| `dev.h` indirect-call funnel | clean |
| stack | **35 functions** within 8,192 — three fewer than the accepted candidate, the excluded allocator |
| RAM / `.rodata` | 156,472 / 204,800 and 1,040 / 32,768 |
| meta-gate | 15/15 — every gate still goes red on a real violation |
| scaffolding | crc32 21, dev 37, mount 286, playback 114; **no allocator suite**, by design |
| `golden suite (awaiting WP-11 fixtures)` | **RED**, visible and unrequired |

Frame counts match the P1-R10 accepted observations exactly: 1, 1, 2, 88,200,
88,200, 2, 1.

## Exclusions

Not acceptance — not by this run, not by this issue closing. No WP-11 golden and
no human listening. No allocator, recording, crash/recovery, warm-start
descriptor negatives, long-operation or state-matrix behaviour, performance,
hardware or card qualification: `tape_arm`, `tape_feed`, `tape_commit`,
`tape_abort`, `tape_promote`, `tape_respool`, `tape_dup`, `tape_format` and
`tape_reset_side_b` are absent from this slice entirely. `tape_status` reports
`recording_armed` and `frames_owed` false because §7 recording is not implemented
here. No stubs were added.

## Holds observed

Draft and held; no implementation merge. PR #20 and PR #64 untouched — not
merged, not rebased, not retargeted, and their evidence bundles are unchanged on
their own branch. No verifier-owned file edited: `tests/playback_complete_draft8/`
is byte-identical to main at tree `6dbb23bb…`, and no oracle, runner, fixture,
candidate or retained evidence was touched. No test weakened, no frozen-spec
change, no listening or golden acceptance, no repository-setting change, no
purchase or card qualification, no fabrication or charging work. WP-11 stays red.
