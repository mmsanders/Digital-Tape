# Human queue

**6 November 2026. Phase 3 is open.**

0. **Acceptance is now hands-on ([ADR-208](DECISIONS.md#adr-208--hands-on-acceptance-for-physical-and-timing-criteria)).**
   You judge timing and feel, with the firmware reporting its own numbers. The volume caps stay
   enforced in the codec; you check them with a phone app (≤ 80 dB on the kids' headphones).
   Instruments are about $30. The CID is no longer needed. Your sign-offs go in
   [MICHAEL-CHECKS](MICHAEL-CHECKS.md). Two new issues are waiting for you to start:
   Hardware [#671](https://github.com/mmsanders/Digital-Tape/issues/671) (revised cart and power-cut test) and Verification
   [V#398](https://github.com/mmsanders/digital-tape-verification/issues/398) (DRAFT-11 delta and firmware tests). When convenient, photograph your three PNY cards and their packaging.

1. **Next lead work** after PM666 is published:
   - Software [#667](https://github.com/mmsanders/Digital-Tape/issues/667) first: restore the unchanged WP-11 portability gate on Ubuntu24.04 in a separate CI-only PR;
   - Verification [V#397](https://github.com/mmsanders/digital-tape-verification/issues/397): review returned census660 and ordering665 now; independently confirm the runner restoration when returned;
   - Software existing [#658](https://github.com/mmsanders/Digital-Tape/issues/658), then [#652](https://github.com/mmsanders/Digital-Tape/issues/652): integrate cleared CI corrections, then the already behaviorally cleared kit, with meaningful required CI green.
   Hardware PR646 is integrated at60dfe6aa; no new Hardware task. Your matching-owner **CODEOWNERS approval remains recorded**; no repeat request. No physical session is ready.
2. **Parts:** your minimum bench + rig selection is recorded. You confirmed they are **not
   ordered** (2 Nov). The rig/instrument cart is being revised to ADR-208 (no lab
   instruments); you approve the revised cart before anything is ordered. No physical session is ready yet; no
   lead places an order. Ordinary firmware bench preparation is separate from the blocked rig.
3. **Authorize spec revision DRAFT-11** ([proposal](SPEC-DRAFT-11-PROPOSAL.md)) once
   Verification has preflighted it and Hardware has supplied the speaker limit. PM will ask
   you then.
4. Still open, no rush: copy-button placement (Hardware will offer options) and the
   promote-B-to-A key combination.

Pinned for later: the G2 unaided app test ([protocol](WP15-G2-PROTOCOL.md)).

[Status](STATUS.md) · [Phase 3 ledger](PHASE3-LEDGER.md) · [Device design](DEVICE-DESIGN.md)
