# firmware/

Two builds, same silicon family, so `prod/` is a port rather than a rewrite.

| | |
|---|---|
| `bench/` | Stream 4 — Teensy 4.1 + audio shield |
| `prod/` | Stream 5 — i.MX RT1062 custom board |

## Watch for, in both

Firmware quietly reimplementing seek or mixing because calling the engine felt awkward from an
interrupt context. **Fix the integration; do not fork the behaviour.** One engine, three
consumers — if firmware reimplements something the engine already has, that is a bug even when
it works (guardrail 12).
