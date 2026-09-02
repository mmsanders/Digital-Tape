# tests/ — Stream 2

**Owned outright by the Verification Lead, who reports to the PM, not to the Software Lead.**

Adversarial by design. Read CLAUDE.md §2 for why this reporting line exists before proposing
to simplify it.

**Packages:** WP-10, WP-11
**Depends on:** the API spec **only** — write the tests against the spec, before or alongside
the implementation, never after reading it.

**Done when** one command runs everything, failures produce an audible diff, and crash
injection is exhaustive over write boundaries rather than sampled.

## Standing instruction

**If a test is hard to pass, that is a finding, not a reason to relax the test.** Report it
up. Do not negotiate it sideways with Stream 1.

## Layout — and one directory that is not the Verification Lead's

`tests/harness/` is Software Lead scaffolding: the assertion macros, the build, and self-tests
for the block-device ports and CRC-32. It is the thing tests run *in*, not tests. Nothing in it
is acceptance, and it must never be cited as sign-off — its only job is that when a Verification
Lead test fails, it is failing on the engine rather than on the plumbing.

Test source arriving from the Verification Lead should need only `engine/include/` and
`tests/harness/harness.h` — no framework dependency. If a returned test needs a shape this
harness cannot express, that is a finding, not a reason to edit the test.

## Layout

| Path | |
|---|---|
| `golden/` | Reference WAVs. **The cross-target contract**, not desktop tests firmware also runs. Firmware must be bit-identical at 1.0× playback; a divergence is a release blocker, not a platform difference |
| `crash/` | Power loss simulated at *every single write boundary* in a full editing session, asserting the cartridge still mounts |
| `fuzz/` | Transport input sequences, asserting zero write transactions ever reach the source slot |

The fault-injection capability `crash/` needs already exists: `engine/port/dev_sim.c` wraps any
device and can cut power after N block-writes, or tear a single write so only part of a block
lands. The harness that drives it exhaustively over every write boundary — and decides what
"still mounts" means — is WP-10, and is the Verification Lead's to write.
