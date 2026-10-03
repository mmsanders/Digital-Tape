# Tests — independent acceptance and software scaffolding

Verification reports to PM and owns independent tests and oracles. Derive tests from the
spec before inspecting implementation for the behaviour. Do not relax assertions,
delete cases or skip failures to fit code; disagreements return to Verification/PM.

| Path | Provenance / boundary |
|---|---|
| `*_draft8/`, `*_r4x/`…`*_r6x/`, `wp10_*/`, `wp11_*/`, `golden/` | Verbatim independent verifier packages, **37 declared in [IMPORTS.json](IMPORTS.json)** with source commit, tree and attestation. Verification-owned; never edited here. The first was `mount_draft8/` (289 mount cases) |
| `*_adapter/` | Software-owned product bindings and retained product evidence for those packages |
| crash/ | Independent fault-device and crash-harness infrastructure; sample self-test is not a full product WP-10 run |
| golden/ | Independent WP-11 golden references (10) and `MANIFEST`, approved by ear by Michael (#367); green in CI. Regeneration needs a logged PM decision and a new listen |
| harness/ | Software-owned build/assertion scaffolding and implementation self-tests; never independent acceptance |
| fuzz/ | Empty placeholder. The accepted WP-36 fuzz campaign is the imported `wp36_fuzz_draft8/` package |

Run make -C tests/mount_draft8 check for verifier package self-checks.
Build the engine then run make -C tests run for existing scaffolding/infrastructure.
Each imported package's product run is wired in CI through its `*_adapter/`; see the
package's COVERAGE/ADAPTER files and `.github/workflows/ci.yml`.

See [verification integration](../docs/VERIFICATION-INTEGRATION.md). Product source
and destination crash outcomes follow the per-operation spec oracles, not a generic
“always mounts” assertion. Keep torn-write/durability modes and physical card
qualification distinct. Golden regeneration requires logged PM approval and listening.
