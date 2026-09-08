# For the PM — DRAFT-8 candidate, third cut (V8R2 dispositions)

From: surge support
Date: 6 Sep 2026 (late)
Branch: `surge/draft-8-freeze-candidate`
PR: https://github.com/mmsanders/Digital-Tape/pull/25
Canonical today: `main` is still DRAFT-7. I will not merge.

This is a handoff, not a freeze request. Spec authorship stays yours.

---

## What happened

The independent Verification Lead pass on the second-cut bytes
(`22dca615` / `537eadc4` / `3c764724`) is
`findings/surge-draft8-second-cut-review.md` on
`mmsanders/digital-tape-verification/main`
(`14b386f1424b98237fb32bf7d2221aa130d9543b`).

**0 blockers, 1 major, 1 documentation/coverage question.**
V8C-001 and V8C-002 stayed fixed. V8C-003's ordinary-headroom path stayed
fixed. V7-001 did not reopen. The remaining major, **V8R2-001**, is the
generation-exhausted equal-generation-divergent fallback: §4.6 claimed a
durable first write is always `INCOMPLETE`, while the required zeroing
fallback after `sb_generation = 0xFFFFFFFD` leaves the surviving primary's
own mount result.

I treated V8R2-001 and V8R2-002 as mine to disposition. Partner-first and
the two-interruption closure test are unchanged. Engine-api bytes are
unchanged this cut.

---

## This cut's hashes

Proven locally with `sha256sum`. Banner inside the hash is still
**DRAFT-8. NOT FROZEN.**

```
3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb  spec/tapefs-v1.md
537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1  spec/engine-api.md
7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7  spec/acceptance.md
```

Files: `draft-8/` in this project folder. Issue by `cmp`-landing these
three files plus the DRAFT-8 `VERSION.md` in one commit.

---

## Dispositions

| ID | Sev. | Where | What I wrote |
|---|---|---|---|
| **V8R2-001** | major, candidate | `tapefs` §4.6, §9.5/§9.6 step 1 and crash tables; WP-10 oracle and allowed-state sets | Qualified the equal-generation-divergent template claim with headroom. Ordinary path unchanged (v1 WIP template, durable first write = `INCOMPLETE`). Exhaustion path (`sb_generation ≥ 0xFFFFFFFD`) stays the §4.5 zero-both fallback, mirror first. First durable or torn zero = **mount result of the surviving primary**, not `INCOMPLETE` and not "old cartridge unchanged." Both zeros = `BAD_MAGIC`. New crash-table rows and a mandatory WP-10 shape at `0xFFFFFFFD`. |
| **V8R2-002** | doc / coverage | WP-06, WP-06d; format/dup allowed-state geometry sentences | Phase-0 refusals at `block_count ∈ {0, 1, LBA_CHUNK_BASE}` now require **zero callbacks of any kind**, not only zero out-of-range callbacks. WP-06 parenthetical is "phase 0 plus phases 1–4." |

V7-001 partner-first, V8C-001 phase 0, V8C-002 identity boundary, and
V8C-003's ordinary template path were not touched.

---

## What I recommend

**Do not flip the banner.** Hand the new bytes and
`FOR-VERIFICATION-LEAD.md` to the lead. The lead already said that fixing
this one edge without introducing a new candidate major would make the
next exact-byte pass a genuine zero-blocker/zero-major Phase-0 signature
candidate, still subject to your issuance.

**Do not treat a land as WP-10.** Paper-clean is not a green WP-10.

**If you reject the text,** leave `main` at DRAFT-7.

Landing order if you accept: your edit pass → re-hash only if you
changed a hashed file → gate green and proven-red → `cmp`-land three
files + `VERSION.md` together.

---

## What this does not do

- Does not freeze. Does not flip the banner.
- Does not touch `engine/` implementation. PR #20 stays parked.
- Does not merge hardware PR #18.
- Does not publish findings onto `digital-tape-verification` `main`.
