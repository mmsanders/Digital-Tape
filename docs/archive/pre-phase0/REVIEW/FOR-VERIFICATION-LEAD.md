# For the Verification Lead — DRAFT-8 third-cut review brief

From: surge support (not the PM, not a lead)
Date: 6 Sep 2026
Target if the PM issues it: the DRAFT-8 bundle on `mmsanders/Digital-Tape`
(`spec/VERSION.md` on the issued commit)
Courtesy copies: do not review a chat attachment against `main` if they
disagree. `main` wins.

This note is optional context. The PM may ask you to ignore it and review
the issued files only. That is the better experiment.

Your second-cut pass on `22dca615` / `537eadc4` / `3c764724` is the baseline.
This cut is a new exact-byte candidate.

---

## Hashes of this cut

```
3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb  spec/tapefs-v1.md
537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1  spec/engine-api.md
7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7  spec/acceptance.md
```

Re-check them against the issued `spec/VERSION.md`. Do not trust this
table if `main` disagrees.

Banner still **NOT FROZEN**. Partner-first and the two-interruption
closure test are unchanged. Engine-api bytes are unchanged this cut.

---

## Where the new sentences live

| ID | Disposition in the text |
|---|---|
| V8R2-001 | `tapefs` §4.6 item 4 now branches on headroom. §9.5 item 5 / step 1 and §9.6 step 1 name the exhaustion fallback. Both crash tables split "candidate exists" vs equal-generation-divergent first-zero rows. WP-10 mandates the `sb_generation = 0xFFFFFFFD` divergent pair and splits the oracle. |
| V8R2-002 | WP-06 says "phase 0 plus phases 1–4." WP-06d and the format/dup geometry sentences require zero callbacks of any kind for `block_count ∈ {0, 1, LBA_CHUNK_BASE}`. |

I am not asking you to accept those dispositions. I am telling you where
the new sentences live.

---

## Attack first

1. **Exhaustion × equal-generation-divergent.** Craft both copies valid,
   byte-divergent, `sb_generation = 0xFFFFFFFD`. Confirm step 1 zeroes
   the mirror first and does not write a generation-wrapped template.
   After a durable first zero, remount must be allowed to return that
   primary's own admission result — including `VERSION`,
   `UNSUPPORTED_STATE`, an index error, or a successful mount — and
   must not be forced to `INCOMPLETE`.
2. **Ordinary headroom still V8C-003.** Same shape at a generation that
   can increment must still take the v1 WIP template. A durable first
   template write must still be `INCOMPLETE`.
3. **"Old cartridge unchanged" scope.** The candidate-exists fallback
   row must still hold for one-valid-copy and unequal-generation
   destinations. It must not be the named result for the divergent
   exhausted pair.
4. **Unchanged on purpose.** §4.6 partner-first. Phase-4 stale-partner
   repair. Zero-needed. `tape_service` except Faulted. Source-label copy.
   Identity boundary. Phase 0 `DEVICE_ADDRESSABLE`. Two-interruption
   promote path.

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
