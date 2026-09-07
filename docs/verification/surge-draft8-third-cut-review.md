# Surge DRAFT-8 third-cut — independent adversarial review

Review target: the user-supplied third-cut surge candidate associated with `mmsanders/Digital-Tape` PR #25. The supplied three-file spec bundle hashes exactly to the supplied DRAFT-8 manifest and to the hashes advertised by the current PR packet:

- TapeFS `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- engine API `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- acceptance `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

**Status boundary:** these are authenticated surge-candidate bytes, not a claim that the Program Manager has issued DRAFT-8 on canonical `Digital-Tape/main`. This file is therefore surge-labelled rather than `spec-review-draft8.md`. If the PM issues byte-identical files, this review applies mechanically to those bytes; any changed hashed file requires re-authentication and review.

Method: authenticate the exact files; independently re-trace V8R2-001 and V8R2-002 from the actual spec text; compare only afterward with the optional surge verifier note and PR packet; then re-check the unchanged high-risk areas: partner-first repeated-interruption closure, stale-partner repair, branch-exact/zero-needed counters, running index sequence, stage clearing, degraded-B recovery, raw format/duplicate crash rows, generation identity boundary, FAULTED/re-entry rules, and the acceptance oracles. No `engine/` implementation source, implementation branch/diff/issue, PR #20 implementation detail, or unlanded implementation artifact was inspected.

## Summary

**0 blockers, 0 majors, 1 documentation question.**

For the first time in the surge DRAFT-8 sequence, the exact candidate bytes meet the standing mechanical Phase-0 defect threshold of **zero blocker and zero major in the candidate sections**. I therefore regard these exact hashes as a legitimate **verification-side Phase-0 signature candidate**, contingent on byte-identical PM issuance and PM signoff. This is not an official freeze: the candidate banner remains NOT FROZEN, canonical `Digital-Tape/main` has not been replaced by this review, and operations/state still freeze only after the actual WP-10 run is green.

**WP-10 is mechanically testable as written. WP-11 is testable as written. WP-12a is testable as written.** A clean paper review is not a green WP-10 and does not authorize the operations/state freeze.

---

FINDING: V8R3-001
SEVERITY: documentation question
AREA: `tapefs-v1.md` §4.6; cross-reference to §9.5/§9.6 generation-exhausted fallback
CLAIM: §4.6 item 4 now correctly distinguishes the equal-generation-divergent WIP-template path from the generation-exhausted zeroing fallback, but the generic paragraph immediately after the classification still says unqualifiedly: “Then: write the new superblock bytes to the partner; ... candidate,” even though the just-described exhaustion branch writes zero blocks and has no §4.1-selected candidate.
REPRO: Enter §4.6 item 4 with two structurally valid, equal-generation, byte-divergent copies at `sb_generation = 0xFFFFFFFD`. Item 4 correctly says the raw operation takes the generation-exhausted fallback and zeroes mirror then primary; §9.5/§9.6 and WP-10 all agree. Reading the following “Then” literally, however, again directs a write of new superblock bytes to partner and candidate and asserts that the new generation is strictly greater. That cannot hold on the exhaustion branch. The detailed raw-operation sections remove the behavioral ambiguity, and no mounted ordinary update can reach this shape.
IMPACT: No incompatible crash oracle remains and no implementation needs to guess the actual raw-operation behavior if it follows §9.5/§9.6. I therefore do **not** grade this as a major or freeze blocker. It is a local scope/wording defect inside candidate §4.6 that should be cleaned before final publication if convenient.
FIX: Scope the post-classification algorithm explicitly, e.g. “For branches that write a new higher-generation superblock, then:” before the two write steps, and state that the generation-exhausted zeroing branch stops there and follows §9.5/§9.6. No algorithmic change is requested.

---

## Disposition of second-cut findings

- **V8R2-001 — fixed.** Equal-generation-divergent raw media now splits on generation headroom. With headroom, the higher-generation v1 WIP template makes a durable first write select `TAPE_ERR_INCOMPLETE`. Without headroom, the fallback zeroes mirror first and explicitly permits the surviving primary's own mount result after the first durable/torn zero. Both §9.5 and §9.6 crash tables and WP-10 enumerate the same states. No wrapped generation is written.
- **V8R2-002 — fixed.** WP-06 now names “phase 0 plus phases 1–4,” and WP-06d requires zero block-device callbacks of any kind for `block_count` 0, 1, and `LBA_CHUNK_BASE`. TapeFS phase 0 and engine API agree.

## Prior high-risk findings remain closed

- **V7-001 remains fixed:** partner-first/candidate-last ordinary logical superblock updates plus stale-partner repair preserve the current candidate until a newer generation is durable. The two-interruption closure criterion remains in WP-10; no rollback-to-stale-water-line path reproduced.
- **V7-002 remains fixed:** zero-needed branches do not consult exhausted counter values.
- **V7-003 / V8C-003 remain fixed on the ordinary raw path:** canonical v1 WIP template, deterministic tie-break, and refusal-before-write ordering are singular.
- **V7-004 remains fixed:** duplicate copies the source label byte-for-byte.
- **V7-005 remains fixed:** `tape_service` is allowed in mounted states except Faulted.
- **V8C-001 remains fixed:** `DEVICE_ADDRESSABLE` prevents pre-read mirror underflow/out-of-range access; format/duplicate geometry precedes destination superblock reads.
- **V8C-002 remains fixed:** step-1 WIP is inside the existing-cartridge generation-increase domain; final format/duplicate identity assignment establishes a new cartridge at generation 1 and is outside that monotonicity span.

## Clean-pass notes

No new blocker or major was found in the unchanged running-`next_sequence` rules, promote/re-spool branch counts, stage-clearing order, degraded-B recovery, phase-4 stale-partner repair, FAULTED override, callback re-entry/BUSY persistence, duplicate source/destination separation, or transport/interpolation arithmetic.

The TapeFS §4.1 heading still says “four phases” while the body describes a phase-0 guard plus phases 1–4. Engine API and acceptance use the clearer “phase 0 plus phases 1–4” formulation. This is editorial only and is not filed separately.

## Verification recommendation

**Phase 0:** these exact candidate bytes satisfy the Verification Lead's standing zero-blocker/zero-major paper gate. If the PM issues these exact hashes, I recommend proceeding to PM Phase-0 signature/freeze review rather than another speculative spec revision solely to search for defects. `V8R3-001` is worth a wording cleanup but is not grounds to withhold the candidate on safety or mechanical-testability grounds.

**Operations/state:** not frozen. Run WP-10 against the issued bytes. The operations/state sections freeze only on an actual green WP-10, including the V7-001 two-interruption closure and the raw generation-exhaustion/equal-generation-divergent cases.

**Implementation blindness:** preserved throughout this pass.