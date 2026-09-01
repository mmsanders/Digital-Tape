# Acceptance criteria

**Status: NOT WRITTEN.** Placeholder.

The criterion for every work package. One place, so that the Verification Lead signs off
against a written standard rather than against a conversation.

A criterion is only a criterion if it is measurable and someone other than its author can
check it. "Works correctly" is not a criterion. "Wakes to first audio sample in under 100 ms,
measured at the DAC, worst case over 100 cold starts" is.

Missing a criterion by more than 20% is escalation trigger #4 — not a failure, a signal that
the criterion or the approach was wrong.

## Already fixed by the charter

| Criterion | Source |
|---|---|
| Wake to audio < 100 ms | Guardrail 04 |
| Engine static footprint < 200 KB, zero post-init allocation | Guardrail 08 |
| 90-minute cartridge copies in < 30 s on production hardware | Guardrail 10 |
| Output capped at 85 dB against specified headphones | Guardrail 11 |
| Firmware output bit-identical to golden WAVs at 1.0× playback | Contract 3 |
| Zero write transactions ever reach the source slot | Stream 2 |
| Cartridge mounts after power loss at *every* write boundary | Stream 2 |

Fallback ladder for the copy criterion (guardrail 10) — the only sanctioned retreat:
SDR104 (14 s) → SDR50 (21 s) → high-speed 4-bit (43 s). Dropping to the floor is a PM
escalation, because it trades against tape length and that is Michael's call.
