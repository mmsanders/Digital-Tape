# WP-04 owner prototype record — FIT-01 / LADDER-01 / LADDER-02

**Filed by PM, 14 October 2026 PDT, intake [#431](https://github.com/mmsanders/Digital-Tape/issues/431), ADR-179. Disposition: RECORDED — PARKED.** Primary home: WP-04 Route A transport spike. Michael explicitly says these are brainstorming/notes and no further round is wanted now. This is owner-directed work outside PM-issued hardware rounds, as allowed by #309, consistent with the owner-directed hardware arrangement; it supplies no independent acceptance.

The [unaltered intake text](../archive/intake/431-slide-lock-owner-prototypes.md) preserves Michael's words, numeric observations and Hardware's proposed interpretation. It is a source snapshot, not new work directions. Derived mechanisms/friction/flex estimates there remain hypotheses; PM has not validated the CAD, dimensions, material, force or simulation claims.

## Where it lands

| Primary / downstream package | Relevant facts to carry on resumption |
|---|---|
| WP-04 Route A spike | Shared slide bar and pen/pencil springs; catch orientation; FIT-01 fits and blind overhang ranking; Stop release and mechanism failures |
| WP-22 production transport | P button baseline for further exploration; bar/tab strength, release force and consistent engagement across positions |
| WP-20 button matrix/interlock | Button travel/alignment and Stop-releases-all are interface inputs only; no electrical/button-matrix or solenoid qualification |
| WP-23 enclosure | Lid insert worked informally; removable pegs fractured twice; tape still needed; cap alignment/stem retention and shell assembly remain unresolved |
| WP-25 ruggedization | Informal drops released latches; broken stem/tab/pegs are failure observations, not a qualified abuse protocol or safety PASS |
| WP-24 shell/print-process context | Material/fit sensitivity is an input to future printed-part work, not proof that existing cartridge-shell tolerances or another filament are qualified |

## Owner observations, not acceptance

- A1 Mini; reported Bambu PLA Matte blue,0.4mm nozzle,0.20 Standard,4walls,seam Aligned,supports off. This supplements earlier white PLA Basic records; neither material/profile transfers qualification to the other.
- FIT-01: slide clearance0.15mm/side preferred; cap0.05mm held and0.10mm fell out. A forced0.00mm cap fit broke. Pen/pencil springs reported14mm free/~4mm solid; pegs/holes and material-sensitive lid fit are preserved in the source.
- LADDER-01: nominal h0.3/0.5 did not latch;0.7mm twins disagreed(6/10 versus1/10);0.9/1.2/1.5mm latched10/10 in that series. Owner ranking P>L>F; X rejected. P=1.2mm is a **prototype preference**, not a production choice. Printed loss/flex estimates are hypotheses.
- LADDER-02: L depended on slot position; P preferred; Stop too hard; stem and slide-bar tab fractured; caps could sit askew. Spring cups/lid insert were useful observations, while lid pegs broke and tape was still needed. No repeated broken part is silently classified as cosmetic.
- F generally stayed latched on informal drops except spring-end impact; L/P generally released. No calibrated drop height/orientation/count, injury screen or auditable method is claimed.

## Drop-release clarification

Record Michael's taste that a button may **unlatch to its normal raised state and stop playback** after a drop. This does not require latches to remain depressed through every impact. It does not approve detached/ejected keycaps, fractured hazardous parts, loss of control function, exposed/loose battery or conductors, cartridge ejection, or a silent functional failure. Guardrail13 is unchanged. A reusable, obvious Stop transition and the assembled product's retained controls must be demonstrated under the future issued abuse criteria before final enclosure acceptance. The informal results neither qualify WP25 nor select a final latch.

## Artifact preservation boundary

The issue reports that `latch-rig.zip`/chat downloads contain rig.py,kinematics.py,build.py,test_rig.py and FIT/LADDER STL/3MF/cards/manifests/blind map/analysis/results. **Those files were not supplied in this repo and were not recovered by this filing.** This document/source snapshot preserves the report, not absent generators or geometry. Retain the owner's ZIP; do not treat scratch availability as durable evidence or regenerate claimed identical files from prose.

When the packet becomes available, its archival home is `hardware/prototypes/slide-lock-2026-10/`: provenance README plus exact generators/tests/profile/cards/results/manifests and file SHA256 inventory; bulky original ZIP/STL/3MF should use a hash-pinned durable release asset where repository limits require it. Capture actual revision/provenance and preserve the blind mapping. These are archival directions for a future authorized delivery, not a new print/design/verification assignment. Do not splice this new rig into the historical WP04-01 generator or overwrite old packet hashes.

**Resume:** Phase3 opens or Michael explicitly resumes WP04/production transport; WP25 method/trials remain subject to their own phase/final-enclosure gate or explicit request. On resume, Hardware reconciles both the old reversed-hook failure and these new position/force/fracture results, recovers the exact packet and proposes an independently reviewable next method. Until then, no new hardware-lead issue, print, purchase, prototype iteration or diverted Phase2 Verification round is created. Filing can close #431 while its facts and missing-file limitation stay durable.
