# Speaker loudness limit — toy-safety research for S2 (DRAFT-11)

**Owner:** Hardware Lead (research) · **Decides:** PM folds S2 into [DRAFT-11](../../docs/SPEC-DRAFT-11-PROPOSAL.md);
Michael authorises. **Drafted:** 1 November 2026 for [P3-R1-HW (#641)](https://github.com/mmsanders/Digital-Tape/issues/641),
input main `3826018`.

This is research and a recommendation, not a safety acceptance. Hardware can't accept its own
safety response (CLAUDE.md §2).

## S2 proposal under the ADR-208 phone method (10 November 2026, [#675](https://github.com/mmsanders/Digital-Tape/issues/675))

This finishes the S2 gap named in the DRAFT-11 proposal: the limit, distance, weighting, signal,
duration and method. It is a **proposal**. PM folds it into DRAFT-11, Verification reviews the
method, and Michael authorises issuance. Hardware doesn't issue or accept a safety limit.

| Parameter | Proposed value | Source / reason |
|---|---|---|
| **Limit (S2)** | **LpA ≤ 80 dB**, A-weighted, time-averaged | EN 71-1 §4.20.2.4 hand-held and §4.20.2.3 table-top, exposure category 1 (§1 below). Stricter than ASTM F963-23's 85 dB |
| **Check threshold** | Phone app reads **≤ 75 dB** | 80 dB minus ADR-208's 5 dB margin for an uncalibrated phone. Replaces the 77 dB Class 2 bench target in §4 |
| **Distance** | **50 cm** from the nearest surface of the player | EN 71-1 §8.28.1.5 (50 cm from the reference box); F963-23 also measures at 50 cm |
| **Position** | Move the phone at 50 cm over the front, sides and top; measure fully at the loudest | Simplified from EN 71-1's six positions on the box surface |
| **Weighting and averaging** | A-weighting, Leq (LAeq) | EN 71-1 §4.20.2; F963 LAeq |
| **Duration** | 15 s per measurement | EN 71-1 §8.28.1.3 (15 ± 1 s) |
| **Mode and signals** | Maximum volume, speaker path (no headphones). Three runs, report the maximum: (a) the loudest golden fixture; (b) the same at full-depth FF scrub; (c) a full-scale 1 kHz tone cartridge made with the desktop app | §8.28.1.3: "the mode … which produces the highest sound pressure level". Scrub is foreseeable use |
| **Setup** | Player held at an adult's arm's length, or on a stand ≥ 1 m up, away from walls. Room background ≥ 10 dB below the reading (≤ 65 dB on the app) | §8.28.2.3.1 mounting; background rule from §4 |
| **Instrument** | Phone sound-level app with A-weighting and Leq (NIOSH SLM on iOS, or similar) | ADR-208 §2 |
| **Peak** | LCpeak ≤ 110 dB is **not measured by phone**. It is met by design | EN 71-1 §4.20.2.4. A phone app's peak reading isn't credible. The amplifier's maximum output at the cap is about 75–80 dB(A) at 50 cm, which leaves about 30 dB to the peak limit even for a full-scale square wave (crest factor 0 dB). That is analysis, not a measurement. Verification checks the codec/amplifier configuration, as for the headphone cap |
| **Record** | One MICHAEL-CHECKS entry: date, firmware build, gain register and trim setting, distance, position, the three readings and background | ADR-208 §7 |
| **Enforcement** | SGTL5000 line-out level set and re-asserted at boot; volume range clamped under it; PAM8302 gain trim set during the check, then sealed. Michael may lower it by ear, never raise it above the measured reading | ADR-208 §2; §4 below |

**Standards status, checked 10 November 2026 (secondary sources only; the texts are paywalled):**
- **EN 71-1:2014+A1:2018.** The amendment summaries from SGS and STC list projectile, cord and
  flying-toy changes, and no acoustics change. So §4.20 is probably unchanged from the 2014 text I
  read, but that's **not confirmed against the text**.
- **EU Toy Safety Regulation (EU) 2025/2509.** Published in the Official Journal on 12 December
  2025; it repeals Directive 2009/48/EC. Most sources say it applies from 2030; one says August
  2026. Summaries mention sound-level provisions, but **its numbers aren't confirmed**.
- **EN 71-1:2026.** Reported as published; its acoustics clause is **not confirmed**.

PM should treat the 80 dB value as resting on the 2014 text until one of these is read. It is the
strictest value in every source I have seen, and the residual risk is a stricter future number.

**Unchanged risk notes (§5):**
- close-to-the-ear misuse, where a 60 dB limit would apply if PM classifies the device that way;
- the shared headphone/aux jack.

## Recommendation (1 November, Class 2 bench method; superseded for method by the section above)

> **S2 (speaker): LpA ≤ 80 dB** (A-weighted, time-averaged over 15 s) at **50 cm** from the
> player's reference box, at the microphone position giving the highest level, in the loudest
> foreseeable operating mode. This includes maximum volume, the loudest golden fixture and Rew/FF
> scrub at full depth. Also **LpCpeak ≤ 110 dB** at 50 cm. Method per EN 71-1 §8.28.2.3 (hand-held
> toys) and §8.28.1.

- **Basis:** EN 71-1 §4.20.2.4 (hand-held toys) and §4.20.2.3 (table-top or floor toys), **exposure
  category 1**, which give the same values. This is the strictest limit that applies to a speaker
  meant to be heard at a distance.
- **Design target on the bench: 77 dB** at the same geometry. That is a 3 dB guard band for bench
  measurement uncertainty (§4), so a later lab measurement doesn't fail on instrument and room
  differences.
- **Safe default** if PM wants a single number now: 80 dB LpA at 50 cm. It is stricter than ASTM
  F963's 85 dB, so it satisfies both.

## 1. EN 71-1 (Europe): the controlling standard

**Text read:** EN 71-1:2011+A3:2014, the public-resource copy at
<https://law.resource.org/pub/eu/toys/en.71.1.2014.html>. The acoustics clauses (§4.20, §8.28,
Annex A.25) were inserted by A2:2013.

**Not read:** the current harmonised consolidation, EN 71-1:2014+A1:2018. I couldn't obtain its text,
so **I can't confirm §4.20 is unchanged in it.** I also haven't verified the status of the EU Toy
Safety Regulation replacing Directive 2009/48/EC, or anything it changes about acoustics. PM should
treat both as open until checked against the purchased text.

### Which category the player falls in

| Question | Clause | Answer for this player |
|---|---|---|
| Clearly designed to emit sound? | A.25 | Yes: electronic sound-producing feature |
| Close-to-the-ear toy? "intended to be used within 2,5 cm of the ear" | §3 def. 3.10 | **No** by design: the speaker is for listening at a distance, and headphones are the near-ear path. See the risk note below |
| Hand-held toy? "intended to be held in the hand" | §3 def. 3.31 | Yes, when carried and played (68 × 110 × 29 mm) |
| Table-top toy? | §4.20.2.3 | Also yes, when set down to play. Same limits as hand-held |
| Exposure category | §4.20.1 | **Category 1**: "Toys emitting sound during time periods typically longer than 30 s after each initiation". One Play press plays a whole side |

### The limits that apply

| Clause | Toy type | Category 1 | Category 2 | Category 3 | Peak |
|---|---|---:|---:|---:|---:|
| §4.20.2.4 | Hand-held, LpA at 50 cm | **80 dB** | 85 dB | 90 dB | LpCpeak 110 dB |
| §4.20.2.3 | Table-top or floor, LpA at 50 cm | **80 dB** | 85 dB | 90 dB | LpCpeak 110 dB |
| §4.20.2.2 | Close-to-the-ear, LpA at 50 cm | 60 dB | 65 dB | 70 dB | LpCpeak 110 dB |
| §4.20.2.5 | **Toys using headphones**, LpA in an ear simulator, corrected to equivalent free field (EN 50332-1) | **85 dB** | — | — | LpCpeak 135 dB |

LpA is the A-weighted time-averaged emission sound pressure level (§4.20.2.x). Annex A.25 says the
limits rest on the lower action values of the noise-at-work Directive 2003/10/EC (LEX,8h 80 dB(A)),
referred to an ear 25 cm from a non-close-to-the-ear toy. So 80 dB at 50 cm is about 86 dB at the
child's ear.

### Measurement method (§8.28)

- **Standard:** EN ISO 11201 or 11202, aiming for grade 2 (engineering). Grade 1 of ISO 11201 applies
  in a dispute (§8.28.1.2).
- **Instrument:** **Class 1** to EN 61672-1, including microphone and cable (§8.28.1.2).
- **Mounting, hand-held:** in a test rig at least 100 cm above the reflecting plane, or held at arm's
  length by an adult (§8.28.2.3.1).
- **Microphone:** six positions on a box-shaped surface 50 ± 1 cm from the toy's reference box. The
  highest position is measured fully (§8.28.1.5, Figure 33).
- **Duration:** (15 ± 1) s (§8.28.1.3).
- **Mode:** "the mode of its intended or foreseeable use which produces the highest sound pressure
  level" (§8.28.1.3). For this player that means maximum volume, the loudest content, *and* scrub,
  since Rew/FF at full depth is foreseeable use.
- **Battery:** fully charged rechargeable or new primary, whichever is least favourable (§8.28.1.3).
  For the bench (USB power) this is an open point, noted in §4.
- **Uncertainty guidance (§8.28.1.6):** σR0 = 1.2 dB (grade 2 room) and σomc ≈ 2.0 dB, so σtot ≈ 2.3 dB.

### What this says about the headphone cap (H)

EN 71-1 §4.20.2.5 has the same **85 dB** number as guardrail 11. But it states the method: an ear
simulator, the result **corrected to an equivalent free-field level**, per EN 50332-1. Today's
acceptance row only says "85 dB SPL on the specified reference headphones, SPL meter and coupler".

**Observation for PM, no change proposed by Hardware:** if DRAFT-11 restates the H row, it could
name EN 50332-1 and the free-field correction, so the H and S caps both point at a published
method. A raw coupler SPL and a free-field-corrected level can differ by several dB, depending on
frequency.

## 2. ASTM F963 (United States)

**Text read:**
- ASTM F963-11, the incorporated-by-reference public copy at
  <https://law.resource.org/pub/us/cfr/ibr/003/astm.f963.2011.html> (§4.5, §8.19);
- CPSC's direct final rule adopting **F963-23** (mandatory under 16 CFR 1250 since 20 April 2024),
  89 FR (18 Jan 2024), document 2024-00741:
  <https://www.federalregister.gov/documents/2024/01/18/2024-00741/safety-standard-mandating-astm-f963-for-toys>,
  "Sound-producing toys" and Table 1.

**Not read:** the F963-23 text itself, which is paywalled.

### Limits

| Source | Toy category | Limit | Measured at | Exposure distance |
|---|---|---|---|---|
| F963-23 via CPSC Table 1 | Hand-held | 85 dB LAeq | 50 cm | 25 cm |
| F963-23 via CPSC Table 1 | Tabletop, floor or crib (stationary/self-propelled) | 85 dB LAeq | 50 cm | 25 cm |
| F963-23 via CPSC Table 1 | Close-to-the-ear | 65 dB LAeq | 50 cm | 2.5 cm |
| F963-11 §4.5.1.4 | Impulsive, any non-explosive toy | LCpeak 115 dB | — | — |

Method (F963-11 §8.19):
- environment qualified to ISO 3746 Annex A (a normally furnished room over 30 m³ qualifies at 50 cm);
- hand-held toys in a rig at least 100 cm up, or at an adult's arm's length;
- the loudest mode.

### A scope exemption that may cover this product

F963-11 §4.5 says the sound requirements **"do not apply to … (3) radios, tape players, CD players,
and other similar electronic toys and toys where the sound output is dependent on the content of
removable media (for example, game cartridge…)"** and **"(5) sound emitted from earphones/headphones."**

A cartridge player plausibly falls under (3). I **couldn't confirm** whether F963-23 keeps that
exemption, because I haven't read its text. **It doesn't change the recommendation:** EN 71-1 has no
such exemption in the text I read, and the design should be safe for children regardless of a US
exemption. It matters to PM because it means ASTM may impose no speaker limit at all, so EN 71-1 is
the binding reference.

## 3. IEC 62115 (electric toys)

**Not read.** IEC 62115:2017 (EN IEC 62115:2020 + A11:2020) is the electrical-safety standard for
electric toys. In the sources I could read, I found no acoustic limit in it, and I'm **not relying on
it for S2.** It will matter for the battery, charging and thermal side when that gate opens; that's
outside this task. If PM wants it confirmed, it needs the purchased text.

## 4. Measuring S on the bench

The full kit is lines M1–M3 of [PHASE3-BENCH.md](../sourcing/PHASE3-BENCH.md). Michael witnesses;
Verification audits.

1. **Calibrate:** M2 (94 dB, 1 kHz) on M1, before and after the session. Record both readings. A
   drift over 0.5 dB voids the session.
2. **Room:** a furnished room over 30 m³ (the ISO 3746 condition F963 cites). Background at least
   10 dB below the measured level. Estimate the environmental correction K2 per EN 71-1 §8.28.1.4 and
   record it. **This is survey grade, not EN 71-1's grade 2.**
3. **Mount:** the bench rig with its speaker at least 100 cm above the floor, on a stand without flat
   reflecting surfaces near it (§8.28.1.3 note 3).
4. **Positions:** six positions at 50 ± 1 cm from the reference box. Find the loudest, then measure
   fully there.
5. **Signals:** at the boot-asserted maximum volume, three runs of 15 s LAeq each, plus LCpeak:
   - (a) a full-scale 1 kHz sine;
   - (b) pink noise at the loudest golden fixture's level;
   - (c) the loudest golden fixture during full-depth FF scrub.

   Report the maximum.
6. **Pass on the bench:** ≤ 77 dB LpA, which is the 80 dB limit minus the guard band.

**Bench uncertainty estimate:**
- Class 2 meter at about ±1.4 dB;
- survey room and K2 estimate, 1–2 dB;
- operating conditions, about 2 dB.

Combined, about ±3 dB. Hence the 3 dB guard band. A Class 1 meter in a qualified room (a test lab,
Phase 5) is what compliance needs; the bench number is design evidence.

**Enforcement on the bench:** the SGTL5000 line-out level register is set and re-asserted at boot, and
the volume wheel's range is clamped under it in firmware. The PAM8302's gain trim is set during the
witnessed measurement and then sealed (a paint dot). That gives a hardware ceiling under the
register. Whether the production speaker cap is a register, an amplifier gain strap or both is a
WP-19 design decision.

## 5. Risk notes for PM

1. **Close-to-the-ear misuse.** A child may hold the speaker to their ear. If PM classified the
   device as close-to-the-ear, the category 1 limit would be **60 dB at 50 cm**, which is barely
   audible across a room. I recommend against that classification, because the design gives a
   headphone path for near-ear listening. But it's a judgement PM should record, not a fact.
2. **The shared headphone and aux-out jack** is a WP-19 risk. Not part of this task, but it bears
   on the H cap. The SGTL5000 drives headphones capless, against a virtual ground (HP_VGND), not
   true ground. Using the same jack as a line out to grounded equipment can short that virtual
   ground. The bench will show it; the production audio design must handle it.
3. **Standards versions.** The EN 71-1 text I read is the 2014 consolidation; the 2018 consolidation
   and the new EU regulation are unverified. Confirm before DRAFT-11 is issued.
