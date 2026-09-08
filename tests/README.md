# Tests — independent acceptance and software scaffolding

Verification reports to PM and owns independent tests/oracles. Derive tests from the
spec before inspecting implementation for the behaviour. Do not relax assertions,
delete cases or skip failures to fit code; disagreements return to Verification/PM.

| Path | Provenance / boundary |
|---|---|
| mount_draft8/ | Verbatim independent package from verifier 4ee116fa040bb5ce040325e0076365abf8b0f8f9; 289 mount cases, exact coverage/adapter docs and source evidence |
| crash/ | Independent fault-device and crash-harness infrastructure; sample self-test is not a full product WP-10 run |
| golden/ | Independent audio fixture contract; fixtures/manifest still absent, golden CI remains red |
| harness/ | Software-owned build/assertion scaffolding and implementation self-tests; never independent acceptance |
| fuzz/ | Reserved for independent input/ownership trials; not a completed fuzz campaign |

Run make -C tests/mount_draft8 check for verifier package self-checks.
Build the engine then run make -C tests run for existing scaffolding/infrastructure.
The actual mount probe requires the real public header/archive and a conforming
implementation; the older main API does not satisfy that integration yet.

See [verification integration](../docs/VERIFICATION-INTEGRATION.md). Product source
and destination crash outcomes follow the per-operation spec oracles, not a generic
“always mounts” assertion. Keep torn-write/durability modes and physical card
qualification distinct. Golden regeneration requires logged PM approval and listening.
