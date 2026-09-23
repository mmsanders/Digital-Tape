# WP-36 100,000-sequence coverage / assertion matrix

| ID | Assertion | Mechanism |
|---|---|---|
| F36-A01 | Exactly 100,000 generated sequences execute | Production runner count is fixed; summary validation rejects any other count |
| F36-A02 | Generator is reproducible | Verifier-owned SplitMix64-v1, fixed master seed, per-sequence seed derivation, canonical-plan SHA-256 |
| F36-A03 | Source capability is literal `write == NULL` | Product handshake + mandatory later source audit; non-NULL handshake rejected |
| F36-A04 | Debug NULL-write assertion is active | Adapter contract requires assertion-enabled clean engine build; assertion/crash/nonzero/EOF fails closed |
| F36-A05 | Every generated transport operation is executed | Per-sequence response must echo exact identity and full op count; result census must sum to op count |
| F36-A06 | Transport/state space is nontrivial | Census requires all 8 operations, A/B mounts, stopped/forward/reverse states, A/B side targets, side flips, same-side calls, seek classes and rate classes |
| F36-A07 | No attempted source `dev_write` occurs | With literal NULL capability, reaching frozen debug `dev_write` trap kills the process; normal completion of all 100,000 is the acceptance observation |
| F36-A08 | Failure is reproducible without huge logs | Runner retains exact failing sequence index, seed and operation list on process/protocol failure |
| F36-A09 | Harness itself goes red | Self-tests cover synthetic assertion/crash, short run, malformed provenance, and non-NULL binding |

## Alphabet / state assumptions

A sequence is a random series of public transport/state inputs on a valid mounted
read-only source cartridge. The alphabet is:

- seek
- tell
- set rate
- render
- service
- status
- get info
- set side

The fixture has valid non-empty A/B timelines. Each sequence independently mounts A or
B, begins with rate 0 (Mounted, idle), and may enter forward/reverse Playing through
`tape_set_rate`. `tape_set_side` is valid from both Mounted-idle and Playing in the
frozen state matrix. No recording or long-operation state is generated in this tranche.

The acceptance property is capability separation—transport must never reach a source
`dev_write` on a literal NULL-write device—not a new playback PCM golden or a re-test of
the deterministic mutator precursor.

## Explicit exclusions

- Deterministic five-case `slot_draft8` precursor re-acceptance.
- Recording/mutator correctness beyond the already-published precursor.
- Random edit sequences / WP-07 allocator fuzz.
- Crash injection / WP-10 durability.
- Long-operation continuation, re-entry, progress and FAULTED-state coverage.
- PCM/golden/listening acceptance.
- Product acceptance itself until the exact published package is imported, bound and
  run against the real product under Structural Rule 1, then independently dispositioned.
