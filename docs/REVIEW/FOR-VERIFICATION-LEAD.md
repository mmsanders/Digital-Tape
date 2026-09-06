# For the Verification Lead — DRAFT-8 second-cut review brief

From: surge support (not the PM, not a lead)
Date: 6 Sep 2026
Target if the PM issues it: the DRAFT-8 bundle on `mmsanders/Digital-Tape`
(`spec/VERSION.md` on the issued commit)
Courtesy copies: do not review a chat attachment against `main` if they
disagree. `main` wins.

This note is optional context. The PM may ask you to ignore it and review
the issued files only. That is the better experiment.

Your first-cut pass on `a769c772` / `d19c8f24` / `d2cf1f62` is the baseline.
This cut is a new exact-byte candidate.

---

## Hashes of this cut

```
22dca61503dbfda40abee53a5ab5eeb968cb887da67b4611ae0adcd67e7835a7  spec/tapefs-v1.md
537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1  spec/engine-api.md
3c7647247b6780be6fa68c6f7649d5bedda10219b2231bd470318e11d0890d53  spec/acceptance.md
```

Re-check them against the issued `spec/VERSION.md`. Do not trust this
table if `main` disagrees.

Banner still **NOT FROZEN**. Partner-first and the two-interruption
closure test are unchanged.

---

## Where the new sentences live

| ID | Disposition in the text |
|---|---|
| V8C-001 | `tapefs` §2.1 names `DEVICE_ADDRESSABLE`. §4.1 phase 0 evaluates it before any callback. `tape_dup` geometry/capacity now precede classification. Format already had geometry first. WP-06d names `block_count` 0, 1, and `LBA_CHUNK_BASE`. |
| V8C-002 | One identity-boundary sentence in `tapefs` §4.6, §5, and the identity-assignment commit notes; `engine-api` invariant 7; WP-10 counter assertions. Step 1 stays in the increase domain. The final commit writes `sb_generation = 1` and is outside it. |
| V8C-003 | Equal-generation-divergent takes the v1 WIP template path with the healthy-pair tie-break. Crash tables and WP-10 allowed-state sets list `INCONSISTENT` / surviving-copy mount result / `INCOMPLETE` / completed. Zero-both is only the generation-exhausted fallback. |

I am not asking you to accept those dispositions. I am telling you where
the new sentences live.

---

## Attack first

1. **Phase 0.** Confirm `block_count = 0` cannot produce a `dev_read` at
   `0xFFFFFFFF` or at LBA 0. Confirm duplicate no longer classifies before
   `GEOMETRY_OK`. Confirm a destination that fails both geometry and
   capacity still writes nothing and now also reads nothing.
2. **Identity boundary.** A literal invariant-7 checker must accept a
   completed reusable-media format/dup (`sb_generation` 100 → step-1 101
   → final 1) and must still reject a promote that does not increment.
   If any remaining sentence puts the identity commit inside the
   strict-increase list, that is the finding.
3. **Equal-generation-divergent.** Durable first template write must be
   `INCOMPLETE`, not the old primary. Torn first write must be either
   still-`INCONSISTENT` or the surviving primary's own mount result.
   WP-10's allowed-state set must admit every row of the TapeFS tables
   for that shape. The two-interruption promote path must still be the
   V7-001 test; do not let this change touch it.
4. **Unchanged on purpose.** §4.6 partner-first. Phase-4 stale-partner
   repair. Zero-needed. `tape_service` except Faulted. Source-label copy.

---

## What I am not asking you to do

- Do not review engine implementation, PR #20, or any unlanded `engine/`
  diff.
- Do not treat this note as a disposition record. If the PM issues
  DRAFT-8, your findings are against that issued bundle.
- Do not flip the banner.
- Do not publish a "surge said it was fine" sentence. I did not.

WP-10 is still the operations freeze gate. I have not run it. A clean
paper pass is not a green WP-10.
