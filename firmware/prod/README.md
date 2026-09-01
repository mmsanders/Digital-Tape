# firmware/prod/ — Stream 5

i.MX RT1062 — same silicon family as the bench build, so this is a port, not a rewrite.

The hard part is UHS-I bring-up on both USDHC controllers: 1.8 V switching, the voltage-switch
sequence, delay-line tuning. **This is where the 30-second copy is won or lost.**

**Packages:** WP-28, and firmware support for WP-29, 30, 37
**Depends on:** Stream 4 proven; hardware rev A in hand from the Hardware Lead

**Done when** both slots negotiate at least SDR50 and a real 90-minute cartridge copies in
under 30 seconds, measured.

## The fallback ladder is the only sanctioned retreat

SDR104 (14 s) → SDR50 (21 s) → high-speed 4-bit (43 s).

Dropping to the floor is a **PM escalation**, because it trades against tape length and that
is Michael's call, not an engineering one.
