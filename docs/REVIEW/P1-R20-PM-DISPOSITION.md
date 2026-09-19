# P1-R20 PM disposition — VT8 product evidence and hardware-method audits

**Date:** 19 September 2026 UTC  
**Input product main:** `48cc23fdbe6273dfe73f17fbdddf8e9fcc5ab3d9`  
**Input verifier main:** `d6c8c99c06e84705ffdb340554f407027e05419b`

## Decision

PM authenticates Software #102's exact corrected-verifier import and the structure of
its two-case PR #96 evidence return. The evidence is ready for a blind, case-bounded
independent Verification disposition; PR #96 is not accepted or mergeable.

PM also authenticates Verification #15's sustained-write method audit. The audit
correctly blocks a new physical card run because schema 2 does not retain and enforce
the complete ordered primitive write record it claims. PM corrects one routing typo:
the authenticated legacy ancestor is
`c0e6a83ae44c2370288594b75915a214ba25deb7`, not the nonexistent
`c0e6a83a474a0b01134ea64ea02a80c420979003`. The correction resolves provenance
identity only; findings V01 and V02 remain open.

Hardware #103's internal sharp-point/sharp-edge controls pass, but the method is not
yet fully source-bound. Hardware must replace secondary-source gaps with the official
current eCFR text and figures before the screen can be treated as executable. These
are routing decisions, not product, card, ruggedization, regulatory, safety or package
acceptance. No physical rerun, print, destructive test, fabrication, charging,
listening or golden promotion is authorized.

## Corrected VT8 import and product evidence

Product main `48cc23fdbe6273dfe73f17fbdddf8e9fcc5ab3d9` contains the verifier's
complete `tests/ops_draft8` tree `3667a2830ba80dbcedad03b97870d1127001ab59`
byte-for-byte and makes no product-code change. PM reproduced its self-test. This
satisfies the ordered test-first import step only.

Held PR #96 evidence head is
`088226a3c324a97fe19d4a4285a80af037b097d5`; its sole parent is pre-run code
commit `e1aaf5f3f441e5126e821a0bd2cfa54a98894294`. The pre-run merge preserves the
previous held engine and adapter trees exactly while adding current main. The evidence
commit changes no engine or adapter path. Its retained packet tree is
`27edc792ee80dda7e4684e949783791e93a3a490`; manifest, run log and adapter-binary
SHA-256 values are respectively:

- `8166e9d35103ea205e741691b889db4db61d48c5bee3249ce659ee9470a356eb`
- `1604cedc5582bc14fb208b0580b16a5177af258c343b0cd54aeb913db6e4ab16`
- `9dc0522ea21fb6a16943a206aa309984b0f783b00a07d4495d024ecdbb158fac`

Both retained cases exit zero and replay PASS under the unmodified corrected verifier.
`VT8-001-RB-ALLSLOT` records only its exact reset-side-B operation and
`VT8-001-REC-ALLOCSEQ` records only its exact recording/allocation operation. PM
reproduced the replay, but did not independently accept either observation.
Verification must remain blind to product and adapter source and disposition only
the raw evidence against those two public case contracts.

Coverage remains deliberately narrow. It does not cover other arm modes, interior or
entry-boundary splice behavior, partial drain, multi-chunk allocation, short accepts,
refusals, injected faults, warm start, abort, zero-frame behavior, crash/recovery,
quarantine, promote, re-spool, duplicate, format, performance, atomicity, PCM,
goldens or listening. PR #20, #64 and #96 remain held.

## Sustained-write audit

Verification published its one-file audit at verifier main
`d6c8c99c06e84705ffdb340554f407027e05419b`; PM authenticated its identity and
reproduced the full verifier suite. The audit disposition is **BLOCKED**:

- V01: schema 2 aggregates write requests instead of retaining every request,
  return value and offset in order.
- V02: the analyzer accepts thirteen missing or corrupted primitive mutations,
  including offset, call-count, short-write, fsync, timing, totals, post-state,
  target-kind and false-schema-summary defects. It does not enforce a closed schema,
  index/order, arithmetic or raw-device branch.
- V03: the PM route named a nonexistent ancestor. The actual authenticated ancestor
  is `c0e6a83ae44c2370288594b75915a214ba25deb7`, tree
  `4421e11258690936f02734c176589ff0c3dad826`; all five legacy JSON files are
  byte-identical from that ancestor to audited PR #87 head
  `da97a8534ef6940f1cb8337e9c9fb7b403dc4804`.

Hardware must repair V01 and V02 and add retained positive and negative controls,
without running cards. Independent Verification must re-audit the corrected exact
head before any new physical acquisition. No prior stored-rate result is revoked,
but none qualifies a card or completes WP-05 A-2.

## Ruggedization source and owned-printer boundary

Hardware PR #92 head `faf8ed4ee3cd83b74f09ed2cf8e5963c0c6ac541` adds a
ten-control internal sharp screen, and PM reproduced all 21 rugged protocol and sharp
controls. The return changes six paths, not the four stated in its summary. The real
fabrication gate remains closed on the same five blockers.

The remaining method work must use official primary sources. At PM review time,
[16 CFR 1500.48](https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/part-1500/section-1500.48)
and [16 CFR 1500.49](https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/part-1500/section-1500.49)
were current through 17 September 2026. The official figures are the
[point-test probes](https://img.federalregister.gov/EC03OC91.056/EC03OC91.056_large.png),
[sharp-edge tester](https://img.federalregister.gov/EC03OC91.057/EC03OC91.057_large.png)
and [access probe / hemmed-edge details](https://img.federalregister.gov/EC03OC91.058/EC03OC91.058_large.png).
For the product's seven-year intended age, Figure 2 Probe B has dimensions in inches
`a=0.170`, `b=0.340`, `c=1.510`, `d=0.760`, `e=2.280`, `f=1 1/2`, and
`g=27 25/32`. Hardware must independently transcribe and test the applicable access,
force, motion, apparatus, tape, exclusion and before/after-use-abuse rules rather
than citing this PM summary as normative authority.

The internal rough-play method must also state how it relates to current
[16 CFR 1500.50](https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/part-1500/section-1500.50)
and the applicable over-36-through-96-month methods in
[16 CFR 1500.53](https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/part-1500/section-1500.53).
Differences remain explicit gaps; the project does not claim regulatory compliance.

Michael confirms the advertised A1 Mini nominal build envelope is
`180 x 180 x 180 mm`. Hardware may therefore regenerate the previously approved
two-plate, source-built packet with a stated conservative edge margin and automated
bounds controls. This owner fact is not machine characterization, proof that every
edge is usable, or permission to print. Matching bases and lids, blindness, full
sweeps, controls and supports-off instructions must be preserved.

Available tools are a sensitive food-preparation scale, normal screwdrivers and
sockets, and a likely soldering iron. Hardware must record the minimum published
resolution, accuracy/calibration and capacity needed before assigning the scale a
measurement. Those tools do not implicitly substitute for a torque driver, dial
indicator, force gauge, compliant sharp-point/edge apparatus, audio interface,
gauge blocks or reference masses. Tool gaps do not block source, software-control or
print-packet work this round.

## Preserved boundary

- Structural Rule 1 remains mandatory; a green product run does not accept source or
  a package.
- DRAFT-8 and WP-08 remain frozen. WP-11 stays red and listening-held.
- Card identity, reader/card attribution, atomicity, filled-condition qualification
  and end-to-end copy remain open.
- Fabrication and charging remain closed. Ruggedized, child-resistant design remains
  an explicit input before final enclosure CAD.
- Verification retains sole independent disposition authority and receives product
  evidence without product/adapter source or implementer interpretation.

The dashboard remains at 13 of 36 fully reached Phase 1 rungs. This round activates
Verification for the exact blind PR #96 evidence disposition and Hardware for the
two still-bounded method/packet repairs. Software, Surge and Michael receive no issue
because they have no bounded work or blocking owner action in this round.
