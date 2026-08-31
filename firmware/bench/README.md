# firmware/bench/ — Stream 4

Teensy 4.1 with the audio shield. Audio graph, engine integration, wake-to-audio via the
preroll cache, dual-card handling with hot-swap detection, line-in and mic capture with gain
staging, the output cap, the LED banks, and the transport state machine driving the solenoid.

**Packages:** WP-17, 18, 19, 20, 21
**Depends on:** Stream 1 substantially complete; hardware from WP-05; the transport spike
outcome from WP-04

**Note.** Its second slot is on SPI, so copy takes ~10 minutes here. **That is expected.**
This build proves function, not speed. Do not optimise it and do not report it as a miss
against guardrail 10 — that criterion is Stream 5's.

**Done when** the full loop runs on the bench: dub from a phone, overdub a voice, splice, copy
to a second cartridge, play it back.
