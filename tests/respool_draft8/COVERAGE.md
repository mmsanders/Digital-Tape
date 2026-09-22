# WP-12 re-spool assertion matrix

This is an independent, pre-product verifier tranche. “Covered” means the
package has a concrete public-observation assertion; it does **not** imply
product acceptance, listened/golden PCM acceptance, WP-10 crash closure, or
WP-12a continuation/state-matrix acceptance.

| ID | Assertion | Basis | Control |
|---|---|---|---|
| WP12-A01 | Empty B returns `TAPE_OK`, `more_work=false`, zero writes/flushes, unchanged media | TapeFS §9.4 V4-005 | write + flush mutations |
| WP12-A02 | On the same empty fixture, `tape_promote` returns `TAPE_ERR_INVALID_ARG`, `more_work=false`, zero writes | TapeFS §9.3.0; acceptance WP-12 | more_work mutation |
| WP12-A03 | Empty zero-consumption branch succeeds even with structurally-valid `sequence=0xFFFFFFFF` elsewhere on the cartridge | TapeFS §4.5; Engine API invariant 33 | fixture premise + conforming synthetic |
| WP12-A04 | V3-003 pass 1 copies the full two-chunk timeline to `[12,14)` and commits B1 at sequence 701 before pass 2 begins | TapeFS §8, §9.4; acceptance WP-12 | one-block fake-copy + unsafe-reorder mutations |
| WP12-A05 | Only after pass-1 B1/701 is committed may pass 2 reuse the now-dead old B range `[10,12)`; pass 2 commits B0 at 702 | TapeFS §8, §9.4, §5.5; invariant 10 | pre-commit pass-2 write + wrong-final-slot mutations |
| WP12-A06 | Every chunk write is at/above `a_high_water`, inside the independently expected pass destination, and disjoint from both live sides at that moment | TapeFS §7, §9.4; Engine API invariant 10 | unrelated-chunk mutation |
| WP12-A07 | Mandatory decline case has exactly one initial one-chunk destination at H; after pass 1 no strictly-lower run exists, so pass 2 is skipped | TapeFS §9.4; acceptance WP-12 | unexpected-second-pass mutation |
| WP12-A08 | No pass-1 destination returns `TAPE_ERR_CARTRIDGE_FULL`, `more_work=false`, zero writes/flushes, unchanged media | TapeFS §9.4 | accepted-refusal mutation |
| WP12-A09 | Equal-sequence divergent B slots are exercised through a **Side-A mount** entering degraded-B; `tape_respool` returns `TAPE_ERR_NO_VALID_INDEX`, zero writes | TapeFS §4.2/§4.4/§9.4; acceptance WP-06f | wrong-Side-B-mount mutation |
| WP12-A10 | Non-empty sequence exhaustion refuses before any write with `TAPE_ERR_SEQUENCE_EXHAUSTED` | TapeFS §4.5, §9.4 | refusal-write mutation |
| WP12-A11 | With exactly one sequence remaining, required pass 1 commits at `0xFFFFFFFD` and optional pass 2 is skipped | TapeFS §4.5, §9.4 | attempted-second-pass mutation |
| WP12-A12 | Ordinary stage-0 re-spool issues no superblock write callback, even if final bytes would be unchanged | TapeFS §8–§9.4; Engine API invariant 7 | same-byte superblock-write mutation |
| WP12-A13 | A mountable §9.3.3 row-1 stage state clears stage **partner → flush → candidate → flush**, generation +1 and H unchanged before the first copy/index write | TapeFS §4.6, §8; invariant 25a/32 | candidate-before-partner-flush mutation |
| WP12-A14 | Semantic cases use one deliberately generous `block_budget=65535` call and require terminal `more_work=false`; WP-12a small-budget continuation is not conflated with this tranche | Engine API §9.1 | false budget-64 completion mutation |
| WP12-A15 | Successful terminal cases and refusals leave the instance unmountable only if the implementation is wrong; scripted unmount must return `TAPE_OK` | Engine API §9.1/§10 | terminal-unmount mutation |

## Deliberate exclusions / later gates

Still outside this tranche:

- product adapter observations against the real engine;
- bit-exact rendered-audio preservation before/after re-spool and listened/golden PCM;
- WP-10 write/flush crash injection and both durability modes;
- the full WP-12a small-budget continuation, BUSY, re-entry and FAULTED matrix;
- broad randomized/property histories beyond these deterministic semantic fixtures.

The semantic tranche deliberately uses a generous budget so a two-pass re-spool
can complete in one public call without pretending that two calls at budget 64
could copy two full chunks twice. Small-budget progress/termination belongs to
WP-12a and remains a separate gate.

Synthetic green proves the verifier package only, not product acceptance.
