# Engine API

**Status: NOT WRITTEN.** Placeholder. Do not implement against this file.

**Package:** WP-03 · **Owner:** PM (drafted by Software Lead) · **Freezes at:** Phase 0 gate

Stream 2 writes tests against this document **before** Stream 1 writes code. That ordering is
the point of the document, so it has to be complete enough to test against.

## What goes here

- Every call: signature, preconditions, postconditions, and what it does on bad input
- Every error code, exhaustively. No `TAPE_ERR_OTHER`
- The static memory budget in bytes, per subsystem, summing under 200 KB
- The block-device interface exactly as it will be implemented — two function pointers, read
  and write, block index and buffer

## Constraints already fixed by the charter

- No allocation after init. No malloc, no recursion, no libc file I/O. Desktop build too
- No API returns a heap pointer
- No dependency beyond libc
- No `#ifdef` naming a board, chip or peripheral
- The source slot is constructed with a **null write pointer**. A write attempt is a crash in
  test, not a corruption in the field. Not a permission check, not an `if`
- The engine knows nothing about hardware. If a fourth concept has to cross the block-device
  boundary, that is an escalation, not a widening

## Surface, from charter §04

Mount, play, seek, variable-rate scrub, three record modes, copy-on-write Side B, atomic
commit, re-spool, whole-cartridge duplication.

## Blocked on

The plan document (Rev B).
