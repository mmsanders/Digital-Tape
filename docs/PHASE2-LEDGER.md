# Phase 2 ledger — every exit criterion, one row each

**Opened by PM622 (ADR-195); updated PM630, 30 October 2026 PDT ([ADR-197](DECISIONS.md#adr-197--c2-disposed-rejected-drop-notice-needs-no-show-details-g2-issued)).**
This is the progress record for Phase 2 closeout. Each round must close named rows. Package
criteria are in [WP-14](PACKAGES/WP-14.md), [WP-16](PACKAGES/WP-16.md) and [WP-15](PACKAGES/WP-15.md).
The exit gate is in [the Phase 2 plan](PHASE2-PLAN.md#1-what-phase-2-delivers).

States:
- **PASSED:** independently passed by Verification on Windows 11, or in platform-independent CI
  where the criterion allows.
- **READY FOR C2:** tests pass in CI; Michael's real-card observations are still needed.
- **TO DO:** work is still needed.

PM does not accept.

## WP-14 — `tapectl` on real cards: ACCEPTED (4/4)

Verification #364 Stage 1, [disposition](https://github.com/mmsanders/digital-tape-verification/blob/48489cf9a53f390de4ded216dc1f293c15e830ee/findings/P2-364-STAGE1-2026-10-28/DISPOSITION.md) `48489cf9`.
A4 was briefly qualified at a Windows volume-census failure path that Stage 2 found. It was
restored when the corrected probe merged at `ea54a41` ([clearance](https://github.com/mmsanders/digital-tape-verification/blob/3ff22aaea8a19b874ea65cea06056e99b3fd0b66/findings/P2-364-CLEARANCE-2026-10-29/DISPOSITION.md)).

| # | State | Basis |
|---|---|---|
| A1 Provision | PASSED | #146 final witness and README bytes |
| A2 Round trip | PASSED | #146: C-60 load, physical reinsert, verify OK, dumps A/B identical |
| A3 Durability | PASSED | Ten physical pulls, 10/10 |
| A4 Disk safety | PASSED | `tests/wp14_r1`; census fails closed at `ea54a41` (r1/r2 regressions) |
| A5 `verify` read-only | PASSED | `tests/wp14_r1` NULL-write and finding controls |
| A6 Large media | PASSED | 64 GB PNY run plus 19 Oct last-sector reads; compiled 32-bit read-offset mutant turns verify OK/0 into NEEDS_REPAIR/1 |
| A7 Capacity | PASSED | `tests/wp14_r1` |
| A8 Engine pin | PASSED | `d96b4245`; re-checked at exit |
| A9 Load time | RECORDED | 1677.7 s for a C-60 on PNY 64 GB |

## WP-16 — Ingest: ACCEPTED (4/4)

Verification #364 Stage 1 `48489cf9`. I1–I8 PASS on the integrated ingest tree `83507899`.
Own-host PASS: an integrated-source static gate with detecting mutants, plus default-invoker
(unelevated) launch from #361's Medium-integrity parent.

## WP-15 — the app (3/4)

| # | State | Evidence | Next |
|---|---|---|---|
| Make path (S3) | DONE | Cleared exact `5101e3f3` (#364 final), merged `ea54a41`, 130 checks. S3 runner 31 Linux plus 10 Windows rows; query, census and own-p1 supplements | — |
| G1 No format logic | PASSED | Static check and controls; C2: unelevated app, one UAC prompt per Make (#370) | — |
| G3 Plain errors | PASSED | 28 bridge rows; C2: file drop, too long, non-music, UAC decline, mid-make pull and remake (#370). F370-1 exempted (ADR-197) | — |
| G4 No lists | PASSED | C2 screens: four states, no lists; label/details stay usable under polling (#370 addendum) | — |
| G5 Installs | PASSED | C2: exact ZIP on Windows 11 Home 25H2 build 26200.9711; real cartridge verify OK, dumps identical | — |
| G2 Unaided test | TO DO | [Protocol](WP15-G2-PROTOCOL.md); same ZIP `b8a689cf` | Michael [#631](https://github.com/mmsanders/Digital-Tape/issues/631) |

**Live issue:** Michael [#631](https://github.com/mmsanders/Digital-Tape/issues/631) (G2). C2 is
complete (#370).

**Accepted Phase 2 limitations (ADR-196):**
- The elevated launch of `tapectl.exe` from a user-writable folder can race its hash check
  (same-user only).
- Stale job folders are not cleaned after a crash.
- The `ERROR_NOT_READY` census rows are typed, not OS-generated.
- An undetected equal-size card swap is a stated limit.

## Exit gate

| Item | State | Next |
|---|---|---|
| 1. WP-14/15/16 accepted | WP-14, WP-16 DONE; WP-15 needs only G2 | G2 |
| 2. G2 witnessed | TO DO | #631 |
| 3. Goldens and Phase 1 replays green on main | PASSING in CI | Re-checked at C4 |
| 4. Q-P2-1 decided | DONE | ADR-195 §4 |
| 5. Host scope frozen | TO DO | PM, at C4 |
