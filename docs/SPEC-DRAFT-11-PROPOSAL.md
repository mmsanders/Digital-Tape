# Spec revision DRAFT-11 — proposal

**PROPOSED by PM, 2 November 2026 PDT ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)).
Not in force.**

Issuance needs:
1. Verification's preflight (P3-R1 Verification issue);
2. Hardware's speaker-limit research, which fills in S2's value;
3. Michael's authorization.

PM then edits `spec/acceptance.md`, the descriptive firmware-policy references in
`spec/engine-api.md`, and CLAUDE.md guardrail 11 in one commit, updates
`spec/VERSION.md` hashes and records the freeze change in docs/PHASE0-FREEZE.md.

**What it changes:** firmware behaviour and safety-limit rows only, from Michael's design
decisions (ADR-199, ADR-200). **No** TAPEFS byte, engine API, error code, crash outcome or
golden changes. The engine stays pinned.

**PM648 revision, 2 November:** applies the direction of Verification F374-1…4;
F374-5 is clarified in FW-1. This is still a proposal, not an issued bundle or a
closed independent preflight. Hashed DRAFT-10 files remain unchanged.

## Changes to `spec/acceptance.md` — "Firmware criteria referenced by the specs"

| Row | Current | Proposed |
|---|---|---|
| **End of tape** | `at_end` releases the play button within 50 ms | At `at_end`, audio stops within 50 ms and the LED ring shows the end state until Stop is pressed. Firmware never moves a key; Play stays latched |
| **Cartridge full mid-record** | On `TAPE_ERR_CARTRIDGE_FULL`, firmware stops the transport, releases the buttons, and commits. The recording up to that point is present on the next mount | On `TAPE_ERR_CARTRIDGE_FULL`, firmware stops the transport and commits; the LED ring shows red until Stop. Keys stay where they are. After successful commit, the recording up to that point is present on the next mount. Commit failure retains the existing `FAULTED`/I/O and remount outcomes; it does not promise preservation after failed commit |
| **Scrub ramp** → **Scrub** | Old text describes 4.0×→12.0× over 1.5 s; its claim that the goldens use that table is inaccurate | Rew/FF rate follows **press depth**: a monotonic mapping from the lightest detected press to full depth. Full depth gives 12.0×; the lightest press and curve are set in WP-20 with Michael. Reverse mirrors. Both pressed gives no scrub; works with Play latched or not. Preserve the actual `tests/golden/MANIFEST`: forward `0.25:32000,0.5:32000,1:32000,2:32000,4:16000`, reverse -1× and -2×. No golden bytes, rates or hashes change |
| **Output cap** | Codec output limited … 85 dB SPL on the specified reference headphones, re-asserted every boot, unreachable from any user control. Witnessed by Michael | **Two caps.** (H) Headphone/aux-out jack: unchanged, 85 dB SPL on the reference headphones. (S) Speaker: maximum **[S2 value, from Hardware's toy-safety research]** at the stated distance and weighting, enforced in the amplifier/codec configuration, re-asserted every boot, unreachable from any user control. Both measured with SPL meter and coupler or microphone as stated, witnessed by Michael, audited by Verification |
| *(new)* **Speaker mute** | — | Speaker is silent while headphones are inserted and while recording. Headphones continue to play during recording |
| *(new)* **Record source** | — | Aux in when a plug is detected, otherwise the microphone |
| **Record light** | Remaining-space indication includes “at 0 the record button does not hold” | Preserve the remaining-space indication, but remove the auto-release/non-holding claim. At full, recording stops/commits and the LED ring shows red; mechanical keys stay where they are until Stop |

## Descriptive corrections to `spec/engine-api.md`

- §11's Play-pop instruction becomes audio stop/end indication with no key actuation.
- §6.2's firmware rate-versus-time policy reference becomes the WP-20 depth policy.
  The engine still takes instantaneous Q16.16 rates. The frozen regression vectors
  remain those in the actual MANIFEST, separate from firmware input policy.
- Only descriptions and the bundle revision header change; no exported function,
  ABI, algorithm, state or crash outcome changes. Both descriptive changes need
  review as part of the exact DRAFT-11 bundle before issuance.

## Parameters still needed before their contracts can pass preflight

- Define reverse `at_start` indication/reset alongside forward `at_end`; no
  new reverse indication is silently issued here.
- WP-19 must give speaker-mute latency, measurable silence threshold/reference,
  and the intended headphone signal during recording (monitor input or tape playback).
- WP-19 must define source-selection behavior on plug transitions, including
  settling/debounce. Steady-state aux preference is already decided.
- S2 still needs an exact source-supported limit, distance/weighting, signal/duration,
  uncertainty and independent method review. Hardware's recommendation is an input,
  not an issued safety limit. Michael's authorization remains required.

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
cold instant-on, resume position, record-light remaining-space meaning, copy progress and
media atomicity stay as written, except for the explicitly proposed no-auto-release wording above.
