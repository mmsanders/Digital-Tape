# firmware/prod/ — Stream 5

i.MX RT1062 — same silicon family as the bench build, so this is a port, not a rewrite.

The hard part is card bring-up on both USDHC controllers. **This is where the 30-second copy is
won or lost.** Board rev A runs both slots at **high-speed 4-bit, 3.3 V** (ADR-113,
`spec/hw/board-rev-a.md`); the 1.8 V switching circuit is on the schematic but unpopulated, so
UHS-I modes (SDR50/SDR104), with their voltage-switch sequence and delay-line tuning, are an
upside path only if that circuit is fitted later.

**Packages:** WP-28, and firmware support for WP-29, 30, 37
**Depends on:** Stream 4 proven; hardware rev A in hand from the Hardware Lead

**Done when** both slots pass the rev A entry gate (1 GB read and 1 GB write per slot at
high-speed 4-bit, 3.3 V, zero CRC retries) and a real C-60 cartridge (ADR-018) copies in under
30 seconds, measured, end to end on the target (guardrail 10).

## The fallback ladder is the only sanctioned retreat

Originally written for a 90-minute cartridge: SDR104 (14 s) → SDR50 (21 s) → high-speed 4-bit
(43 s). At C-60, high-speed 4-bit is the primary path and meets the requirement at about 29 s
(ADR-113), with little margin; SDR50 becomes a second, optional gate if the 1.8 V circuit is
populated.

Retreating below the requirement is a **PM escalation**, because it trades against tape length
and that is Michael's call, not an engineering one.
