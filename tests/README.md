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

## Layout

| Path | |
|---|---|
| `golden/` | Reference WAVs. **The cross-target contract**, not desktop tests firmware also runs. Firmware must be bit-identical at 1.0× playback; a divergence is a release blocker, not a platform difference |
| `crash/` | Power loss simulated at *every single write boundary* in a full editing session, asserting the cartridge still mounts |
| `fuzz/` | Transport input sequences, asserting zero write transactions ever reach the source slot |
