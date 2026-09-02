# STATUS

**Updated:** 2026-09-02 · **Phase:** 0→1 · **Updated by:** Software Lead
**PR #1 is out of draft and ready for PM review.**

---

## What changed since last time

**PM Decisions 001 and 002 absorbed.** All five open escalations are decided; `ESCALATIONS.md`
is deleted (the PM confirmed it reads issues directly, so mirroring was redundant).

**Stream 1 has started.** Everything Decisions 002 clears for work is built, and every gate is
verified against deliberately violating code:

| Landed | |
|---|---|
| `engine/include/tape_dev.h` | Block device interface. Provisional pending DRAFT-3; carries only what Decisions 001/002 state |
| `engine/src/dev.h` | The three `static inline` wrappers — the only sanctioned indirect calls |
| `engine/src/crc32.c` | CRC-32/ISO-HDLC. 1 KiB table in `.rodata`, exactly the PM's estimate |
| `engine/port/dev_file.c` | File-backed device |
| `engine/port/dev_sim.c` | Fault injection: power loss after N writes, and torn writes |
| `engine/port/dev_sd.c` | SD seam, honest stub — fails loudly rather than reading zeroes |
| `tests/harness/` | Scaffolding, 64 self-test checks passing |
| `tests/harness/run-golden.sh` | **Golden runner** — manifest-driven, byte-exact, writes an audible diff. Proven end-to-end against synthetic fixtures |
| `tests/golden/MANIFEST.md` | The contract for returned test source. Answers my own open question rather than leaving it open |

**CI is 6 of 7 green.** Only the golden suite is red, awaiting Verification Lead fixtures — which
is the correct state, and it resolves the "red forever stops being read" risk I flagged: the
build gate now goes green independently of the fixtures.

**WP-02 and WP-03 close as PM-delivered** (ADR-010). Spec authorship is the PM's; I land text
mechanically and do not edit it.

## In flight

| Work | Owner | State |
|---|---|---|
| Block device + three ports | Software Lead | **Done**, unconfirmed |
| CI gates rebuilt (#11, #12) | Software Lead | **Done**, verified both directions |
| CRC-32 + vectors | Software Lead | **Done**, pinned against zlib |
| WP-06 block device layer | Software Lead | Device layer done; superblock and index commit **held for DRAFT-3** |
| WP-07 allocator, copy-on-write B | Software Lead | Held for DRAFT-3 |

## Blocked

Nothing is blocked. **Held by instruction**, per Decisions 002: index layout, the commit
protocol, mount, promote, re-spool, duplicate, and the record path all wait for DRAFT-3 (2–3 days
out). Building the commit path twice would cost more than waiting.

**`main` branch protection is still not verified.** Plan §03 says nothing merges without
Michael's review. Repository settings are not the Software Lead's to change.

## Acceptance criteria flipped to passing

**None.** The 64 self-test checks are the Software Lead's own claims about its own scaffolding
and are explicitly not acceptance. Nothing can flip until the Verification Lead signs it off.

## What will hurt in three weeks

- **The Verification Lead has reviewed a spec but has not yet written a test.** Its DRAFT-1
  review found 22 issues including two that destroy a cartridge, so the arrangement is
  demonstrably working. But `tests/golden/` is still empty, and WP-06 lands code the moment
  DRAFT-3 arrives. The charter's ordering — tests written against the spec *before or alongside*
  the implementation — is about to be tested for real, and it cannot be recovered retroactively.
  **The shape of returned test source is no longer a question** — `tests/golden/MANIFEST.md`
  states it, and the runner behind it is proven. What remains is that nobody has agreed to it.
- **The seam still has no stated transport.** Decisions 001 §0 says Michael hands me spec text,
  which covers one direction. Nothing says how findings and test source come back, at what
  cadence, or what happens when Stream 2 is mid-review and Stream 1 is ready. Raised as issue #13
  together with rule 1's enforceability and the definition of "mechanically" — they are one
  topic, and it is now the critical path.
- **No Hardware Lead.** WP-34 (thermal and safety budget) is a Phase 0 package and is not
  started. The plan is explicit that it is written before the schematic, not after.
- **The fourth caller-owned thing.** The PM asked me to look for where the engine next reaches
  for something it should have been handed. Two candidates from building the device layer, both
  logged for when DRAFT-3 lands: the engine has no clock, so anything wanting elapsed time during
  a long `tape_dup` or re-spool must take it as a parameter; and `tape_dev.block_count` is
  currently the device's claim about itself, which mount must validate rather than trust.
