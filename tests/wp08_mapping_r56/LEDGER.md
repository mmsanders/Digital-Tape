# WP-08 criterion ledger against DRAFT-9 (Verification #129)

The machine-readable form is `wp08-ledger.json`; `audit.py` checks that the two agree with the package.

## Authorities

- **Acceptance WP-08 (DRAFT-9 `ae77d13c…`).** Its row is byte-identical to DRAFT-8 `7f78fba7…`.
- **engine-api §5, §6 and §8.** Unchanged from DRAFT-8 to DRAFT-9; V9-001 touches only §3 and invariant 15. So the DRAFT-8-era dispositions below still bind.

## Dispositions

| Key | Package (tree) | Accepted Product evidence |
|---|---|---|
| R15 | `playback_complete_draft8` (`467a34bb`) | The ten corrected-cadence families. P1-R15, Verification #12, verifier `392d6bb9`; PM ADR-150 |
| R25 | `transport_draft8` (`05aafde2`) | 16/16 set-side and warm observations. P1-R25, Verification #40, Product PR #171 |
| V95 | `crossrun_wp08_r44` (`9ed67a85`) | 33/33. Verification #95 on Product PR #287, at `abd8481` |
| V122 | `portability_wp08_r52` (`d803deef`) | 41/41 on GCC and Clang. Verification #122 on Product PR #327, at `523a7fd` |
| — | `playback_draft8` (`ff810814`) | **None.** Its three-family bundle (draft PR #64) was held unbound and never dispositioned (P1-R7) |

## Rows

| ID | WP-08 criterion | Status | Evidence |
|---|---|---|---|
| L01 | 1.0× bit-exact against `tests/golden/` | **listening-held** | Covered against the spec arithmetic by R15, V95 and V122. Listened goldens are WP-11. |
| L02 | Every ramp-table rate bit-exact | covered | R15 scrub, forward and reverse: all 16 rows, 698 serviced renders each way |
| L03 | seek(N) → render emits N first, at every run boundary ±1 (V4-010) | **partial + gap** | V95 and V122 cover 3 boundaries × ±1 × both directions, but only on `start_frame`-0, one-run-per-chunk, ascending, Side-B fixtures. → `WP08.seek_boundary.mapped_runs` |
| L04 | §6.2/§6.3/§8 are the only implementation of the arithmetic | **unreachable** (blind) | A source-structure claim. Behavioural equivalence is covered by V122's two toolchains. The full §8 domain is WP-11's portability gate. |
| L05 | One frame at `INT32_MAX` clamps at `max_pos` (V4-009) | covered | R15 `one_intmax`; V122 one-intmax, beyond-intmax and multirun-intmax |
| L06 | Zero-frame timeline | covered | R15 `empty_zero` and `empty_nonzero`; V122 empty-* |
| L07 | `rate_q16_16 = 0` | covered | R15 `nonempty_zero`; V122 one-zero |
| L08 | Reverse from 0 emits frame 0 once, then stops | covered | R15 `reverse_zero`; V122 start-reverse; V95 start-reverse |
| L09 | The most negative rate does not wrap | covered | R15 `intmin`; V122 one-intmin and multirun-intmin; V95 huge-reverse |
| L10 | Reverse-from-end multi-frame golden, grid-aligned (V5-005) | **partial + gap** | V122 has the literal `[0,1000,2000]` example; V95 has a 17-frame reverse over start-0 runs. Reverse over a mapped timeline is never exercised. → `WP08.reverse_end.mapped_timeline` |
| L11 | `set_side` (i), from Playing | covered | R15 `side_playing`; R25 SS-A01–A04 |
| L12 | `set_side` (ii), from idle | covered | R15 `side_idle`; R25 SS-A05 |
| L13 | Render makes zero block-device calls across playback | covered | R15 raw traversal; V95; V122 |
| L14 | Goldens listened to by a human | **listening-held** | Michael-held |

Result: 9 rows covered, 2 rows partial with a gap that this package closes, 2 rows listening-held, and 1 row unreachable to a blind verifier.

## Size

The package has 2 rows and 62 cases, which meets the "≥ 3 rows **or** ≥ 25 cases" floor on cases. Nothing was padded.

- **Fractional rates across mapped boundaries.** Considered and excluded, because V95 already exercises them over physically discontiguous runs.
- **playback_draft8.** A Product binding of it was considered and not proposed. The new rows strictly contain its mapping shapes, with chunk crossings, shared chunks and both sides added.
