# Phase 2 ledger — every exit criterion, one row each

**Opened 28 October 2026 PDT by PM622 ([ADR-195](DECISIONS.md#adr-195--phase-2-closeout-proportional-evidence-and-the-make-path)).**
This is the progress record for Phase 2 closeout. Each round must close named rows. Package
criteria are in [WP-14](PACKAGES/WP-14.md), [WP-16](PACKAGES/WP-16.md) and [WP-15](PACKAGES/WP-15.md).
The exit gate is in [the Phase 2 plan](PHASE2-PLAN.md#1-what-phase-2-delivers).

States: **PASSED** means independently passed by Verification on Windows 11 (or platform-independent
CI where the criterion allows). **EVIDENCE IN HAND** means evidence exists and needs a disposition
under ADR-195. **TO DO** means work is still needed. "PM reading" marks PM's reading of
the published record, which Verification confirms or corrects in round C1. PM does not accept.

## WP-14 — `tapectl` on real cards (rung 3/4)

| # | State | Evidence | Next |
|---|---|---|---|
| A1 Provision | PASSED (PM reading) | Verification #146 final Windows witness and README byte supplement, 14 Oct, PNY 64 GB | — |
| A2 Round trip | PASSED (PM reading) | #146 final witness: C-60 load, physical remove/reinsert, verify OK, dumps A and B byte-identical | — |
| A3 Durability | PASSED (PM reading) | Ten physical pulls on Windows 11, 10/10 (Verification PULLS, 14 Oct); flush negative control in `tests/wp14_r1` | — |
| A4 Disk safety | PASSED (PM reading) | `tests/wp14_r1` refusal rules with negative controls, exact head #390 | — |
| A5 `verify` read-only | PASSED (PM reading) | `tests/wp14_r1` NULL-write binding and five finding controls | — |
| A6 Large media | EVIDENCE IN HAND | 14 Oct: provision/verify/load/dump on 64 GB card; the mirror superblock is at byte 62,537,072,128. 19 Oct trace: two successful 512-byte reads there | Verification C1: point to (or add) a 32-bit-truncation negative control beside the existing sparse 64 GB image cases in `tests/wp14_r1`, then dispose (ADR-195 §2) |
| A7 Capacity | PASSED (PM reading) | `tests/wp14_r1` overage refusal, exit 2 | — |
| A8 Engine pin | PASSED | ADR-175; engine `d96b4245`; goldens green | Re-checked at exit |
| A9 Load time | RECORDED | 27 min 58 s for a C-60 on PNY 64 GB via USB reader, Windows 11 | — |

## WP-16 — Ingest (rung 3/4)

| # | State | Evidence | Next |
|---|---|---|---|
| I1 Formats | EVIDENCE IN HAND | Stage1/#192 census; #203; #230 Windows 11 observed bytes (Verification #333 table) | Verification C1: final disposition |
| I2 Conversion | EVIDENCE IN HAND | #192: 1,640 cases, calibration, quality, FIR certificates; #203 | Same |
| I3 Loudness | EVIDENCE IN HAND | #192 final PCM/manifest; #230 Windows 11 identities | Same |
| I4 Gapless | EVIDENCE IN HAND | #192 join predicates, exact zero gaps; #230 | Same |
| I5 Order | EVIDENCE IN HAND | #192 comparator policy; #230 | Same |
| I6 Determinism | EVIDENCE IN HAND | #192 cross-OS byte equality; #230 Windows 11 1,640 identities | Same |
| I7 Length | EVIDENCE IN HAND | #192/#203/#230; #234 Windows 11 resource rows | Same |
| I8 Fixtures | EVIDENCE IN HAND | Stage1 generated/CC0 census, tree `609a4c81` | Same |
| Own-host (no device access) | EVIDENCE IN HAND | Source review; app parent at Medium integrity (#361) | Verification C1: static check with negative control, plus unelevated launch (ADR-195 §2) |

The real-card use of ingest output is exercised end to end in WP-15's C2 run.

## WP-15 — the app (rung 1/4)

| # | State | Evidence | Next |
|---|---|---|---|
| Make path (S3) | TO DO | Not built. Make button hard-wired off. S3 tests `tests/wp15_cards_make_r1` on main; internal core `host/internal_make` | Software C1 builds; Verification C1 disposes |
| G1 No format logic | PARTIAL | Static/design rule; app at Medium integrity (#361) | Verification C1: confirm static check and its negative control; unelevated manifest on the candidate |
| G3 Plain errors | PARTIAL | Child-origin rows partly in `tests/wp15_app1a_r1` and report faults; † rows in bridge/interaction components (#314, #329) | Verification C1 authors the remaining rows and the C2 checklist; Michael runs C2 |
| G4 No lists | PARTIAL | Screen component PASS (#314); human visible rows (#331) | C2 screen capture of the final candidate |
| G5 Installs | PARTIAL | Earlier candidates started natively (#316, #361) | C2: Michael installs the final candidate ZIP |
| G2 Unaided test | TO DO | — | C3: Michael's wife, witnessed by Michael |

## Exit gate

| Item | State | Next |
|---|---|---|
| 1. WP-14/15/16 accepted | TO DO | Rows above |
| 2. G2 witnessed | TO DO | C3 |
| 3. Goldens and Phase 1 replays green on main | PASSING in CI | Re-checked at C4 |
| 4. Q-P2-1 decided | DONE | ADR-195 §4: port-level batching; Phase 3 entry conditions recorded |
| 5. Host scope frozen | TO DO | PM declares at C4 |
