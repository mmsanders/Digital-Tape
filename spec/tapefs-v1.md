# TAPEFS v1 — cartridge format

**Status: NOT WRITTEN.** Placeholder. Do not implement against this file.

**Package:** WP-02 · **Owner:** PM (drafted by Software Lead) · **Freezes at:** Phase 0 gate

## What goes here

Byte-exact. Three streams implement against this without asking a question.

- Region layout — every offset, every size, in bytes
- Chunk map entry format — field by field, with widths and endianness
- The atomic commit sequence — write order, flush points, the single-block index write
  carrying sequence number and CRC
- Mount rules — what a valid cartridge looks like, and how the newer of two index blocks wins
- Recovery rules — what happens on every partial-write state the commit sequence can leave
- Failure modes, enumerated. Not sampled

## Constraints already fixed by the charter

These are not open questions and do not need PM sign-off; they are guardrails.

- 44.1 kHz / 16-bit stereo raw PCM, uncompressed. Byte offset maps linearly to time
- Side A immutability is structural — enforced by allocation below a high-water mark, not a
  runtime flag
- Every card change is one atomic commit. No intermediate state is acceptable and there is no
  journaling in v2
- Side B is copy-on-write

## Blocked on

The plan document (Rev B) carries the numbers. Inferring them and freezing them at Phase 0 is
the most expensive mistake available right now.
