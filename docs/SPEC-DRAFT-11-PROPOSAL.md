# Spec revision DRAFT-11 — proposal

**PROPOSED by PM, 2 November 2026 PDT ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)).
Not in force.** ADR-208 (6 Nov) adds hands-on method changes, below; until issuance ADR-208 governs those methods for Phase 3.

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
| **Output cap** | Codec output limited … 85 dB SPL on the specified reference headphones, re-asserted every boot, unreachable from any user control. Witnessed by Michael | **Two caps.** (H) Headphone/aux-out jack: unchanged, 85 dB SPL on the headphones actually in use (identity recorded). (S) Speaker: maximum **[S2 value, from Hardware's toy-safety research]** at the stated distance and weighting, enforced in the amplifier/codec configuration, re-asserted every boot, unreachable from any user control. Both checked by the ADR-208 method: a phone sound-level app at maximum volume (headphones: phone mic sealed to the ear cup of the headphones in use; speaker: at the stated distance), reading ≤ limit − 5 dB, recorded by Michael in MICHAEL-CHECKS; never raised above the measured reading. Verification checks the record and that the codec/amplifier configuration and boot path set the cap |
| *(new)* **Speaker mute** | — | Speaker is silent while headphones are inserted and while recording. Headphones continue to play during recording |
| *(new)* **Record source** | — | Aux in when a plug is detected, otherwise the microphone |
| **Record light** | Remaining-space indication includes “at 0 the record button does not hold” | Preserve the remaining-space indication, but remove the auto-release/non-holding claim. At full, recording stops/commits and the LED ring shows red; mechanical keys stay where they are until Stop |

## ADR-208 hands-on method — further `spec/acceptance.md` row changes

Added 6 November 2026 PST on Michael's direction ([ADR-208](DECISIONS.md#adr-208--hands-on-acceptance-for-physical-and-timing-criteria)).
Timing/feel rows keep their numeric targets. The firmware times itself on the MCU
timer and logs the values; Michael's matched verdict decides those judgments.
A miss greater than20% requires recorded PM disposition BEFORE acceptance. Strict
counted/structural facts remain requirements: zero commit underruns, inclusive resume
window against the last logged live position, callback-derived progress, >=1000
distinct qualifying cuts with no torn/corrupt/neighbour damage, valid build/log
records, and the cap's5dB margin. An acceptable verdict cannot erase their failure.

| Row | Current method | Proposed method |
|---|---|---|
| **Commit latency** | Measured on the bench build against the slowest candidate card | Firmware-timed `tape_commit` at `TAPE_MAX_ENTRIES` on Michael's cards, logged; **zero ring underruns during commit** stays strict (firmware-counted); Michael judges no audible dropout |
| **Instant-on, warm** | Measured with a logic analyser on I²S | Firmware-timed wake → first non-silent frame handed to I²S, logged; Michael's verdict |
| **Instant-on, cold** | 20 ms / 100 ms, method unstated | Firmware-timed detect → card init and Play → first frame, logged; Michael's verdict |
| **Resume position** | `[T − 12 s, T − 2 s]` against true position T | Unchanged window; T is the last position the firmware logged over serial before removal |
| **End of tape** (as revised above) | 50 ms | Firmware-timed, logged; Michael's verdict |
| **Output cap** | SPL meter and coupler | As in the revised row above |
| **Media atomicity** | Switched supply, ≥ 1,000 cuts per SKU with revision | Teensy self-run: firmware switches card power through a small load switch, observes card busy on its own bus, cuts, re-powers, reads target and neighbours; ≥ 1,000 cuts per card model in which firmware saw busy at the cut; zero torn. Identity = brand, part number, capacity, photo; CID logged by firmware when available. Torn block remains a format blocker |
| **Hardware safety limits — independent audit paragraph** | Procedure, instrument model, calibration, ambient, raw data, derivation, uncertainty | Michael witnesses; evidence is design review, the protection part's datasheet, and multimeter/thermometer spot checks. Limits unchanged |
| **Worst-case thermal** | Junction temperatures of charger, regulator and MCU reported individually | Surface and cell temperature by thermometer/touch, plus protection-part datasheet/design evidence. No individual junction-report prerequisite. Any optional thermal-rise design estimate uses applicable thermal resistance and dissipated POWER with stated conditions, not current alone. Limits unchanged |
| **Charge window / deep-discharge latch** | Verified by sweeping cell temperature | Met by a protected cell and a charger/protection part whose datasheet guarantees the window and cutoff; spot-checked. Phase 5; charging gate stays CLOSED |

These are method changes to rows already in this proposal's scope (firmware criteria and
safety limits). No TAPEFS byte, engine API, error code, crash outcome or golden changes.

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
  source-backed research/design review under the phone method (threshold S2 minus5dB), not a retired uncertainty audit. Hardware's recommendation is an input,
  not an issued safety limit. Michael's authorization remains required.

## Changes to "Hardware safety limits"

| Row | Proposed |
|---|---|
| **Solenoid — single pulse** | **Removed.** The device has no solenoid (ADR-199) |
| **Solenoid — sustained power** | **Removed**, same reason |
| Other rows (charge window, thermal, deep-discharge latch) | Unchanged |

## Change to guardrail 11 (CLAUDE.md §1)

> 11 — Output caps, enforced in the codec/amplifier and re-asserted at boot, unreachable from
> user controls:85dB on the headphones actually in use, checked at <=80dB by the
> ADR-208 phone-app method; speaker limit S2 checked at <=S2-5dB and its stated
> distance. Values/identity/method are recorded; no subjective increase beyond the
> measured cap. Speaker value still awaits issue in spec/acceptance.md.

## Not changed

Engine/format semantics, guardrail02, play-ring requirements, actual golden bytes
and numeric targets remain unchanged. The explicitly proposed firmware policies
and ADR-208 timing/feel/cap/thermal/card methods change as described above; resume
window/callback progress/zero-underrun/atomicity facts remain strict. No new engine
API/error/crash behavior or automatic physical acceptance is issued here.

**8 November PM revision (ADR-209):** applies V398 F398-1..4 wording findings.
Optional CID/legacy examples are delimited in WP-05; new selfrun-r1/plan5 follows
the issued method decision and independent binding, not a quiet edit of old tests.
DRAFT-10 remains byte-identical; this proposal is not in force.
