# For the PM — DRAFT-8 candidate, second cut (V8C dispositions)

From: surge support
Date: 6 Sep 2026 (evening)
Branch: `surge/draft-8-freeze-candidate`
PR: https://github.com/mmsanders/Digital-Tape/pull/25
Canonical today: `main` is still DRAFT-7. I will not merge.

This is a handoff, not a freeze request. Spec authorship stays yours.

---

## What happened

An independent Verification Lead pass on the first DRAFT-8 candidate bytes
(`a769c772` / `d19c8f24` / `d2cf1f62`) returned **0 blockers, 3 majors**.
V7-001 (the cartridge-survival blocker) did not reproduce. Two majors sit
in the Phase-0 candidate (`V8C-001`, `V8C-002`); one sits in WP-10 scope
(`V8C-003`). The lead's recommendation: do not sign Phase 0 on those
bytes; produce another candidate.

That pass is also on `mmsanders/digital-tape-verification/main` as
`findings/surge-draft8-candidate-review.md`
(`432e4675102244dfb22636e11676dcbd411d9bd4`).

I treated the three findings as mine to disposition, same as V7-001/003.
Partner-first and the two-interruption closure test are unchanged.

---

## This cut's hashes

Proven locally with `sha256sum`. Banner inside the hash is still
**DRAFT-8. NOT FROZEN.**

```
22dca61503dbfda40abee53a5ab5eeb968cb887da67b4611ae0adcd67e7835a7  spec/tapefs-v1.md
537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1  spec/engine-api.md
3c7647247b6780be6fa68c6f7649d5bedda10219b2231bd470318e11d0890d53  spec/acceptance.md
```

Files: `draft-8/` in this project folder. The GitHub branch still carries
DRAFT-7 spec files plus the review packet so a packet-only merge cannot
red the gate. Issue by `cmp`-landing these three files plus the DRAFT-8
`VERSION.md` in one commit.

---

## Dispositions

| ID | Sev. | Where | What I wrote |
|---|---|---|---|
| **V8C-001** | major, candidate | `tapefs` §2.1, §4.1 phase 0, §9.5 order; `engine-api` §3 / `tape_mount`; WP-06d | Named `DEVICE_ADDRESSABLE(block_count) := block_count > LBA_CHUNK_BASE`. Mount evaluates it as phase 0, before any callback. Duplicate now refuses geometry and capacity *before* raw classification. `block_count ∈ {0, 1, LBA_CHUNK_BASE}` → `TAPE_ERR_GEOMETRY`, zero writes, zero out-of-range callbacks. Format already had geometry first; the same floor now sits in the named predicate. |
| **V8C-002** | major, candidate | `tapefs` §4.6 / §5 / identity commits; invariant 7; WP-10 counters | One identity-boundary sentence, copied: `sb_generation` strictly increases on ordinary updates of an *existing* cartridge, including format/dup **step 1**. The identity-assignment commit is a new cartridge and writes `sb_generation = 1`; monotonicity does not span it. Removed "format's and duplicate's commits" from the strict-increase list. |
| **V8C-003** | major, WP-10 | `tapefs` §9.5/§9.6; WP-10 oracle | Chose the lead's option B, then aligned the oracle. Equal-generation-divergent now takes the v1 WIP template path with the healthy-pair tie-break (mirror = partner, primary = candidate). A durable first write is `INCOMPLETE`, not an arbitrary surviving admission. Zero-both remains only as the generation-exhausted fallback. Crash tables and WP-10 allowed-state sets now name: `INCONSISTENT` if nothing landed; surviving-copy mount result if the first write tore; `INCOMPLETE` once any template write is durable; completed cartridge. |

V7-001 partner-first and the two-interruption closure test were not
touched.

---

## What I recommend

**Do not flip the banner.** Hand the new bytes and
`FOR-VERIFICATION-LEAD.md` to the lead. The lead already said that if the
two candidate majors land without creating another, the next exact-byte
pass is a legitimate Phase-0 signature candidate.

**Do not treat a land as WP-10.** V8C-003 is now in the oracle; WP-10
still has to run green.

**If you reject the text,** leave `main` at DRAFT-7.

Landing order if you accept: your edit pass → re-hash only if you
changed a hashed file → gate green and proven-red → `cmp`-land three
files + `VERSION.md` together.

---

## What this does not do

- Does not freeze. Does not flip the banner.
- Does not touch `engine/` or `tests/`.
- Does not merge #18 or #20.
- Does not publish onto `digital-tape-verification` `main`.
- Does not decide Q-001.
