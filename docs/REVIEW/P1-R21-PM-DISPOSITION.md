# P1-R21 PM disposition — accepted VT8 observations and repaired hardware methods

**Date:** 19 September 2026 UTC  
**Input product main:** `2193eafdcd9feb831e551ffe37f0c8a7590f5ab3`  
**Input verifier main:** `e77b61fe420e48444cf0791c74fc7e296ef0ccf6`

## Decision

PM authenticates Verification #16 and accepts its independent disposition narrowly:
the exact `VT8-001-RB-ALLSLOT` and `VT8-001-REC-ALLOCSEQ` recorded observations are
accepted. This does not accept PR #96, product or adapter source, WP-07, the verifier
package or any excluded behavior. Software may prepare a new clean held split from
current main for only this accepted behavior and must produce fresh bound evidence;
PR #96 remains held and unmergeable.

PM authenticates both Hardware #107 returns. PR #87 now has a materially stronger
schema-2 acquisition/audit method and is ready for a new independent method audit,
not a card run. PR #92 has a reproducible two-plate A1 Mini packet and stronger
internal screens, but its source record honestly remains incomplete. PM supplies the
official primary-source note needed for one source-only correction before independent
audit. Neither Hardware PR is accepted or mergeable yet.

Michael intentionally closed stale issue #49, will retain the existing branches and
accepts the current branch protection. PM creates no Michael issue, deletes no branch,
publishes no KEEP list and changes no ruleset.

## Independent VT8 disposition

Verification main `e77b61fe420e48444cf0791c74fc7e296ef0ccf6` has root tree
`2e96e8d4e30357944ed4a3efbffacd7356a94cb2`, sole parent
`d6c8c99c06e84705ffdb340554f407027e05419b` and exactly one added findings file:

- blob `3c2ae6f87eed2edf6dd438615eaf061f6fa47f0f`
- SHA-256 `288a5ef3f3a14b52ab847835b1d90a90b7f4e6c81c93407a13992a68f61ff938`

PM reproduced the full verifier suite. Verification stayed inside the assigned blind
boundary, authenticated the exact evidence commit/parent and unchanged engine/adapter
tree identities, replayed the unmodified packet and traversed the raw calls, I/O and
media transitions independently.

The accepted reset-side-B observation contains the exact B0 entry-write, flush,
header-write, flush order; consumes all-slot sequence 901; preserves superblocks and
audio; copies the live A entry; and leaves Side B selectable with `free_next == H == 3`.
The accepted recording observation contains one chunk-3 write at LBA 5120, a durability
flush before metadata, the exact B1 entry-write/flush/header-write/flush order, sequence
701, the exact two-entry index and `free_next` advance from 3 to 4. Both adapter exits
are zero, replay closes, and neither trace has an unexpected call/write, forbidden
range, callback error or overflow.

These are two observation acceptances only. Other arm and splice modes, partial drain,
multi-chunk allocation, short accepts, refusals, injected faults, warm start, abort,
zero-frame behavior, crash/recovery, quarantine, promote/re-spool/duplicate/format,
performance, atomicity, PCM, goldens, listening and complete WP-07 remain excluded.

## PR #87 sustained-write method repair

Hardware PR #87 head `10471f37f432c44d6f5beac59d25b3771e057c38`, tree
`3d8e134e4673a2fffa4cd7df9763d7541383c8a8`, has sole parent merge
`fb937b163b1f6fece3b6e0bd8c67d229196e85d8`. The method commit changes exactly
three characterization programs and the measurement README. PM confirmed the five
legacy JSON records are byte-identical from actual ancestor
`c0e6a83ae44c2370288594b75915a214ba25deb7` through this head.

Schema 2 now retains an ordered, digest-bound write-call trace with sequence/window,
absolute offset, requested and returned bytes; each window retains start/end offsets
and the closing fsync remains inside the measured span. The auditor reconstructs
window totals and continuity, rejects unknown/missing fields and stored summaries,
checks target-specific final size and capacity arithmetic, and handles pre-existing
failures without suppressing trace validation.

PM reproduced the 15 retained control families, legacy audit, fabrication-gate tests
and the real gate's same five-blocker exit 2. This is implementer-owned method evidence.
Independent Verification must replay the previous mutation corpus plus the new trace
controls and disposition readiness before any new card acquisition. No schema-2
physical record exists; no A-2, identity, reader/card attribution, atomicity,
production-copy or qualification result follows.

## PR #92 packet and source boundary

Hardware PR #92 head `2b004b5cfc4b7751941af013afa8f5371474682d`, tree
`e176539245d866e8051ad5435176d4fc47dbc10f`, has sole parent merge
`6852a0be5ada85900159ae39d14e8b19a358a32f`. Its method commit changes 18 paths.
PM reproduced 11 protocol plus 14 sharp controls, source/packet identity, two-plate
bounds validation, duplicate controls, fabrication-gate controls and the real gate's
same five-blocker exit 2.

Packet rev 6 places all four WP-24 bases with their matching lids on a 128 by 124 by
8.6 mm plate and the full WP-04 button/hook/frame experiment on a 156 by 41 by 26 mm
plate. Every vertex is at least 5.0 mm from nominal XY edges and below 175 mm; generated
bounds fail closed. Blindness, full sweeps, controls, labels and supports-off remain.
This accepts reproducibility only—not usable-area proof, process characterization or
permission to print.

Hardware correctly left CS-1 through CS-5 open when its environment could not reach
the official sources. PM has now retrieved the current official pages and visually
checked all three official drawings. The
[P1-R21 primary-source note](P1-R21-CPSC-PRIMARY-SOURCE-NOTE.md) records the exact
Probe B drawing, edge-test tape/apparatus, current-through date, exemptions and
applicable use-and-abuse rules. Hardware may use that PM-authenticated note to replace
gateway/secondary provenance and add retained semantic controls. Independent
Verification, not PM or Hardware, decides whether the later exact method closes the
source findings.

The kitchen scale and ordinary tools remain availability facts only. Specialized
torque, displacement, force, sharp-test, audio and reference instruments are still
unowned. No owner action or purchase is blocking source, software or audit work.

## Preserved boundary and next work

- Structural Rule 1, frozen DRAFT-8/WP-08, PR #20/#64/#96 and WP-11's red/listening
  hold remain.
- Software receives only a clean held split/fresh-evidence task for the two accepted
  observations; it may not import the broad held branch or merge implementation.
- Verification receives only PR #87's independent method audit. PR #92 audit waits
  for Hardware's source-only correction.
- Hardware receives only that PR #92 correction. No printing or physical test.
- Surge and Michael receive no issue because neither has useful bounded work.

The dashboard remains at 13 of 36 fully reached Phase 1 rungs: no complete package's
implementation-and-green gate advanced. Fabrication and charging remain closed; all
card and physical qualification holds remain.
