# For the Verification Lead — DRAFT-8 review brief

From: surge support (not the PM, not a lead)
Date: 6 Sep 2026
Target if the PM issues it: the DRAFT-8 bundle on `mmsanders/Digital-Tape` (`spec/VERSION.md` on the issued commit)
Courtesy copies: do not review a chat attachment against `main` if they disagree. `main` wins.

This note is optional context. The PM may ask you to ignore it and review the issued files only. That is the better experiment.

---

## What changed relative to the DRAFT-7 you reviewed

Dispositions of V7-001…V7-005, drafted on `surge/draft-8-freeze-candidate`. Banner still **NOT FROZEN**.

| ID | Disposition in the text |
|---|---|
| V7-001 | `tapefs` §4.6 partner-first / candidate-last on ordinary logical superblock updates. Phase 4 repairs a stale lower-generation partner as well as an invalid one. WP-10 two-interruption closure |
| V7-002 | §4.5 consults a counter only when that counter's `needed != 0` |
| V7-003 | Raw format/dup classify; they do not refuse household cards. Step 1 writes a specified v1 WIP template, or zeros both copies on equal-generation-divergent after refusal preconditions |
| V7-004 | Duplicate destination `label` is a byte copy of the source `label` |
| V7-005 | `tape_service` allowed in every mounted row except Faulted |

I am not asking you to accept those dispositions. I am telling you where the new sentences live.

---

## Attack first

Same rule the format already prints.

1. **`tapefs` §4.6** — partner-first. Confirm the two-interruption promote path that was V7-001 cannot roll selection back to a generation older than one this operation already made durable. Confirm format/dup identity-assignment commits (dup step 4, format steps 4–5) are correctly excluded: they write `sb_generation = 1` after a higher-generation WIP copy may exist.
2. **`tapefs` §9.3.1 step 4 and §9.3.2 steps 5-decline / 9** — the step *bodies* must match §4.6. A reading note in §9.3.4 is not enough; that was a defect in an earlier cut of this draft.
3. **`tapefs` §4.1 phase 4** — stale-partner repair. `needs_repair` true when the partner is still invalid or stale after phase 4. Repair does not increment `sb_generation`. Mutators remain allowed when `needs_repair` is true; the claim is that partner-first makes that safe. If you disagree, that is a finding, not a documentation nit.
4. **`tapefs` §4.5** — zero-needed. Empty re-spool and NOTHING-TO-DO at `sequence` / `sb_generation` ∈ {`0xFFFFFFFE`,`0xFFFFFFFF`}. RESUME-at-step-5 decline still has `generation_needed = 1` and must still refuse when generation headroom is short.
5. **`tapefs` §9.5 item 3 and step 1** — classification is a plan. Writes start at step 1. Foreign-major remount after the barrier is `INCOMPLETE`, not `VERSION`. Equal-generation-divergent mid-zero: surviving primary is the old cartridge; re-run takes the template path. A destination that is both divergent and too small must be refused with zero writes.
6. **Crash tables** under §8.1's two durability models, now also under §4.6 for ordinary updates.

`engine-api` invariants 32 and 33 restate 1 and 4. WP-10 names the new shapes. If the prose and the acceptance oracle disagree, that is the finding.

---

## What I already caught in my own draft (so you do not have to re-discover those)

Listed so you can verify the fixes rather than spend the first hour on them. They are not a claim that nothing else is wrong.

- §4.6 originally claimed to cover every write that produces a new `sb_generation`, including format/dup identity commits. False: those write generation 1.
- Classification originally wrote during the precondition list. A too-small inconsistent destination would have been erased, then refused.
- Step 1 originally said "write it" after the template was specified. Two implementations could disagree on `version_major` of the WIP barrier.
- Promote step bodies lagged §4.6 (mirror-first sentences).
- Zero-both had no mid-write row.

---

## What I am not asking you to do

- Do not review engine implementation, PR #20, or any unlanded `engine/` diff. Same rule as your DRAFT-7 pass.
- Do not treat this note as a disposition record. If the PM issues DRAFT-8, your findings are against that issued bundle.
- Do not flip the banner. That is the PM, after your verdict.
- Do not publish a "surge said it was fine" sentence. I did not.

WP-10 is still the operations freeze gate. I have not run it. A clean paper pass is not a green WP-10.
