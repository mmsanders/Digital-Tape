# Spec revision DRAFT-11 — proposal

**PROPOSED by PM, 2 November 2026 PDT ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)).
Not in force.**

Issuance needs:
1. Verification's preflight (P3-R1 Verification issue);
2. Hardware's speaker-limit research, which fills in S2's value;
3. Michael's authorization.

PM then edits `spec/acceptance.md` and CLAUDE.md guardrail 11 in one commit, updates
`spec/VERSION.md` hashes and records the freeze change in docs/PHASE0-FREEZE.md.

**What it changes:** firmware behaviour and safety-limit rows only, from Michael's design
decisions (ADR-199, ADR-200). **No** TAPEFS byte, engine API, error code, crash outcome or
golden changes. The engine stays pinned.

## Changes to `spec/acceptance.md` — "Firmware criteria referenced by the specs"

| Row | Current | Proposed |
|---|---|---|
| **End of tape** | `at_end` releases the play button within 50 ms | At `at_end`, audio stops within 50 ms and the LED ring shows the end state until Stop is pressed. Firmware never moves a key; Play stays latched |
| **Cartridge full mid-record** | On `TAPE_ERR_CARTRIDGE_FULL`, firmware stops the transport, releases the buttons, and commits. The recording up to that point is present on the next mount | On `TAPE_ERR_CARTRIDGE_FULL`, firmware stops the transport and commits; the LED ring shows red until Stop. Keys stay where they are. The recording up to that point is present on the next mount |
| **Scrub ramp** → **Scrub** | Rate schedule driven into `tape_set_rate`: 4.0× at t=0, linear to 12.0× at t=1.5 s, hold. Reverse mirrors with negative rates. Scrub goldens drive this exact table | Rew/FF rate follows **press depth**: a monotonic mapping from the lightest detected press to full depth. Full depth gives 12.0×; the lightest press and the curve are set in WP-20 with Michael. Reverse mirrors. Rew/FF work with Play latched or not; both pressed together gives no scrub. **The existing time table stays the scrub golden test vector** driven through `tapectl` and the engine; golden bytes are unchanged |
| **Output cap** | Codec output limited … 85 dB SPL on the specified reference headphones, re-asserted every boot, unreachable from any user control. Witnessed by Michael | **Two caps.** (H) Headphone/aux-out jack: unchanged, 85 dB SPL on the reference headphones. (S) Speaker: maximum **[S2 value, from Hardware's toy-safety research]** at the stated distance and weighting, enforced in the amplifier/codec configuration, re-asserted every boot, unreachable from any user control. Both measured with SPL meter and coupler or microphone as stated, witnessed by Michael, audited by Verification |
| *(new)* **Speaker mute** | — | Speaker is silent while headphones are inserted and while recording. Headphones continue to play during recording |
| *(new)* **Record source** | — | Aux in when a plug is detected, otherwise the microphone |

## Changes to "Hardware safety limits"

| Row | Proposed |
|---|---|
| **Solenoid — single pulse** | **Removed.** The device has no solenoid (ADR-199) |
| **Solenoid — sustained power** | **Removed**, same reason |
| Other rows (charge window, thermal, deep-discharge latch) | Unchanged |

## Change to guardrail 11 (CLAUDE.md §1)

> 11 — Output caps, enforced in the codec/amplifier and re-asserted at boot, unreachable from
> user controls: 85 dB on the specified reference headphones; the speaker cap in
> spec/acceptance.md.

## Not changed

Guardrail 02 (scrub without filtering or pitch preservation), the play ring, warm instant-on,
cold instant-on, resume position, record light, copy progress and media atomicity all stay as
written.
