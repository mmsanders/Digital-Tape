# Owner layout reference — 24 October 2026

**Source:** [intake #569](https://github.com/mmsanders/Digital-Tape/issues/569), filed by Hardware from Michael's design conversation. **Disposition: RECORDED — PARKED.** This is the current owner design reference, not released CAD, a manufactured fit, independent qualification or a new hardware assignment. PM570 updates documents at Michael's explicit request; implementation/trials remain parked.

The private “Digital Tape Layout Sketch” canvas is linked in #569. PM has not inspected that private canvas or the original paper sketch; the facts below come from the filed written intake. Preserve the original design files with the owner.

## Current owner choices and provisional layout

| Area | Reference and status |
|---|---|
| Player envelope | **68 × 110 × about 29 mm**. Narrow/tall, chunky edges/corners; two equal-depth halves. This supersedes the old sizing-study target, not an issued manufacturing drawing. |
| Cartridge envelope | **GameCube class, about 36 × 40 × 7 mm.** The old 86 × 54 × 12 mm target is withdrawn. Exact fit/tolerances/carrier/contact/clasp geometry need redesign and review; do not scale the old clasp analysis or claim its force/strain proves this cartridge. |
| Slots | Two centred top slots, one behind the other. Front play/record slot has orange write rim and label window; rear copy-source slot is read-only with gray rim. Tops stand about 3 mm proud with grip ridges. Seam through the proposed 2 mm divider is a layout concept, not validated geometry. |
| Front | About Ø46 grille over an estimated Ø40 speaker; 16-LED ring for playback position and copy progress; front cartridge label window. Speaker is proposed scope and has no adopted loudness/power/thermal limit yet. |
| Left side | **Provisional:** Record (orange), gap, Play, Stop, Rew, FF; five keys about 12 × 8.5 mm and 1.5 mm proud. Record must be next to Play. Michael is still considering face keys. |
| Right side | About Ø16 volume wheel, 2 mm proud, under the top bumper; orange-rimmed aux-in. Wheel remains subject to the existing headphone 85 dB cap; no new speaker limit is inferred. |
| Bottom | Headphone jack through bottom-left bumper, USB-C charge/data under ADR-105, battery LEDs. |
| Microphone | Top-left bumper is perforated over a MEMS mic in a sealed boot, close to Record. This is a location preference, not acoustic/sealing validation. |
| Bumpers/materials | Four corner caps, about 2 mm proud of every face. Blue shell; gray marks candidate structural parts; orange means record/write. PLA/PETG choices are candidates, not approved process/material/safety results; TPU remains unproved. |
| Internal estimates | Battery about 48 × 34 × 8 mm / 1,200 mAh behind speaker, about 4.5 mm back volume; PCB about 46 × 62 mm low/back. All are **EST**, not layout, sourcing, thermal or clearance measurements. |
| Key catch | Keep the P-catch's 1.2 mm hook/business end; extend its root full-width through the key body for strength. This is a new geometry preference, not qualification of the earlier prototype. |

## Product/mechanical decisions still open

**A solenoid-free layout is a proposal, not an adopted firmware behavior change.** Michael considered dropping it and Hardware recommends doing so. The intake's title is not proof that end-of-tape behavior was decided. Existing acceptance requirements for releasing Play/end-of-tape, Record at zero, and full-mid-record button release remain unchanged until PM issues a specific alternative on Michael's decision. Stop-and-show versus looping is unresolved. Do not remove coil safety/fabrication blockers merely because the sketch omits the coil.

Record must not latch unless Play is down, without releasing unrelated transport keys. Proposed mechanism: Record catches a ledge on Play, so releasing Play releases Record. Simultaneous presses are contemplated; pressing Record after Play needs an unresolved flex arm/ramp. The earlier shared-bar solenoid interlock was rejected for this purpose because it could pop the other keys. No working interlock or new print ladder is claimed.

A speaker, microphone and aux-in add gain/source-selection, speaker mute during recording, power/thermal and loudness questions. Aux-in-if-plugged/otherwise-mic is a proposal. The headphone-only cap does not establish a speaker safety limit. No electrical design/BOM/pin or firmware interface is silently issued here.

The drawing has **no copy button**. A physical copy control or defined gesture still needs an explicit product decision. Old documents' copy-button assumption is not a settled current layout.

Other unresolved interfaces: side versus face keys; seam-guided keys versus a separate transport sub-frame; proud cartridge grip versus drop retention; accidental side-key presses; actual board/battery/speaker clearance; sealing, battery access and Guardrail13. Nothing here qualifies drop/retention/charging safety or authorizes fabrication/charging/purchases.

## Resume condition and consumers

Resume engineering on an explicit Michael hardware request or the relevant Phase3/Phase4 WP-04, WP-19/20, WP-23/24/25 resumption. Before CAD/trials, reconcile end-of-tape/Record/copy/audio-source behavior and speaker safety scope, then publish independent criteria and interface changes. PM-issued hardware work remains parked through Phase2; Michael's separate owner design conversations are preserved, not converted into an unattended hardware stream.

Read with [the earlier latch prototype record](WP04-OWNER-PROTOTYPES-2026-10.md). Update consumers: [WP-04](WP-04.md), [WP-24](WP-24.md), [hardware status](../STATUS-HARDWARE.md), [package index](README.md), and the versioned [cartridge](../../spec/hw/cartridge-shell.md), [board](../../spec/hw/board-rev-a.md) and [thermal](../../spec/hw/thermal-budget.md) restart notices. Legacy dimensions/models remain historical evidence, not new-layout acceptance.
