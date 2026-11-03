# Atomicity rig evidence schema and judge rules, revision 2 (declaration)

**Owner:** Hardware Lead · **Status:** PUBLIC INTERFACE DECLARATION. No judge code implements it yet.
**Drafted:** 2 November 2026 for [P3-R2-HW (#651)](https://github.com/mmsanders/Digital-Tape/issues/651),
answering findings R374-1, R374-2 and R374-5 (Verification `3d616c14`, `findings/P3-R1-374/RIG-METHOD.md`).

This declares what a revision-2 plan, row, manifest and verdict look like, and the rules the judge
will apply. It's published **before** any judge change, so that Verification can author its
regression tests independently ([V#380](https://github.com/mmsanders/digital-tape-verification/issues/380)).

**Status, 3 November:**
- **R374-1 (§1, and the damage fields in §6) is implemented.** It was implemented only after V380's
  independent regressions (`bab04466`, tree `1ca703a4`) were imported unchanged to
  `verification/rig_correction_r2/` (manifest `verification/IMPORT-rig_correction_r2.json`). The
  plan stays at revision 3.
- **The R374-2 and R374-5 rules (§2–5, and the other §6 fields) are not implemented.** Their
  independent cases (`EXPECTATIONS.md`) still have to be bound to this declaration in a new
  Verification publication. Nothing here
lowers the 1,000-qualifying-cut minimum or the zero-tear / zero-neighbour-damage requirement.

The circuit and procedure this schema records are in [ATOMICITY-RIG.md](ATOMICITY-RIG.md) revision 2.

## 1. What changes, in one paragraph each

**R374-1, damage can't hide behind non-qualification.** The revision-3 judge classifies the target
and neighbours only for qualifying rows, so a tear on a late-cut row vanished from a PASS. In revision 2,
every row that passes row validation (§4) has its target and all four neighbours classified,
**whether or not it qualifies**. Any TORN or CORRUPT target, or any changed neighbour, on any
validated row makes the verdict FAIL and is listed by iteration. Qualification only decides what
counts toward the 1,000. Rows that fail validation are run-integrity problems, as before. Missing,
duplicate, unplanned and identity-mismatched rows are unchanged problems.

**R374-2, qualification is decided from measured electrical events, not from software timestamps.**
- *Rail opening* is the first falling edge of comparator A, which trips when VCARD crosses a
  specified threshold that is **always below 2.70 V**, the bottom of the card's operating range.
- *Busy end* is any rising edge of comparator B on the card's DO line after busy entry.

Both edges are timestamped by hardware input capture on one timer. A trial qualifies only if no
busy end occurs at or before rail opening plus a fixed uncertainty U. A busy end inside
±U of rail opening is **ambiguous and non-qualifying**. The judge no longer accepts any older busy
sample, however stale. The GPIO write time is kept, but only as a diagnostic.

**R374-5, scope stays explicit.** Every row and the verdict carry the bus mode, the SPI clock and the
rig manifest hash. A run in SPI mode reports `qualification_scope: "spi-characterisation"`. That scope
is never SD 4-bit, SDR50 or card-system qualification. PM owns any wider scope.

## 2. Judge constants (code, not operator input)

These live in the judge's `Policy`, like `REQUIRED_QUALIFYING` (IR-018-06). They are never read from
the plan, the manifest or a row. The manifest *records* the rig's design values, so a reviewer can
check that the two agree.

| Constant | Value | Why |
|---|---|---|
| `REQUIRED_QUALIFYING` | 1000 | Unchanged |
| `U_US`, edge-alignment uncertainty | **1.0 µs** | The worst-case analysis gives 0.18 µs at a 150 MHz capture clock and 0.32 µs at 24 MHz (ATOMICITY-RIG §4). 1.0 µs is that, with more than 3× margin. Control E3 measures the actual skew before any campaign |
| `CUT_DELAY_MAX_US` | **500 µs** | Bound from the cut command to the measured rail opening. It catches a delayed or missing cut. The switch's typical turn-off time is about 2 µs, and its fall to the threshold depends on card load (§4 of the rig doc). 500 µs is a fault bound, not a timing claim |
| `METHOD` | `"rig-r2"` | Rows and plans from any other method are refused |

## 3. Plan, revision 4

The plan is as in revision 3, plus:

| Field | Type | Rule |
|---|---|---|
| `plan_version` | 4 | |
| `method` | `"rig-r2"` | Included in `plan_digest` |
| `rig_manifest_sha256` | 64 hex characters | SHA-256 of the committed manifest file (§5). Included in `plan_digest`, so a run can't be re-pointed at another rig build or calibration |

`plan --manifest FILE` computes the hash. A continuation plan (`--extend`) inherits `method` and
`rig_manifest_sha256` from the plan it extends. A different manifest needs a new run.

## 4. Row, revision 2

Every revision-3 field keeps its meaning: iteration, run_id, sku, revision, card_cid, plan_digest,
precondition_ok, precondition_readback_hex, readback_hex, neighbours, neighbour_baseline, bus_mode,
busy_line, payload_complete and data_response_accepted. The changes are below. All `_us` values are
microseconds from trial start, on the capture timer's timebase, and may be fractional.

### Row validation (failure is a run-integrity problem)

| Field | Type | Rule |
|---|---|---|
| `method` | string | Must equal `"rig-r2"` |
| `rig_manifest_sha256` | hex | Must equal the plan's value |
| `card_cid` | 32 hex characters | The CID read at **power-up before the cut** (step 2). Must equal the plan's value, as in revision 3 |
| `card_cid_after_cut` | 32 hex characters | The CID read at **power-up after the cut** (step 10). Missing or malformed counts as a problem. **Different from `card_cid` is a problem** ("CID after cut differs"). An initialisation failure after a cut is therefore a FAIL, never a skip |
| `sck_hz` | integer | Must be the same on every row. The verdict reports it |
| All revision-3 validation | — | Unchanged: identity, plan digest, precondition, a 512-byte readback, and exactly four neighbours with baselines |

### Qualification fields (failure is a non-qualifying reason)

| Field | Type | Meaning |
|---|---|---|
| `busy_entry_us` | number | Time of the first 0x00 byte after an accepted data-response token, from the SPI byte stream and timestamped on the capture timer |
| `capture_armed_us` | number | When edge capture on both comparators was armed. It must be ≤ `busy_entry_us` |
| `cut_command_us` | number | When the firmware drove the switch's ON pin low. Diagnostic and delay bound only |
| `rail_open_us` | number or null | First falling edge of comparator A after `capture_armed_us` (VCARD below the A threshold). Null if none was captured |
| `rail_edges_us` | list of numbers | Every comparator A edge captured, either direction. Shows chatter |
| `busy_end_edges_us` | list of numbers | Every rising edge of comparator B (DO above the B threshold) captured after `capture_armed_us` |
| `capture_end_us` | number | When capture stopped. Edges after this time aren't observed |

Qualification is evaluated in this order, and the first failure is the recorded reason:

1. The revision-3 protocol checks (bus mode and busy line, a complete payload, an accepted token).
   Unchanged.
2. Every qualification field is present and of the right type; otherwise "rig-r2 timing field
   missing or malformed". The lists may be empty.
3. `capture_armed_us ≤ busy_entry_us`. Otherwise "busy capture not armed at busy entry".
4. `rail_open_us` is a number and `rail_open_us > busy_entry_us`. Otherwise "rail opening not
   observed after busy entry". This is the no-cut case.
5. `0 ≤ rail_open_us − cut_command_us ≤ CUT_DELAY_MAX_US`. Otherwise "rail opening outside the cut
   delay bound". This is the delayed-cut case.
6. `capture_end_us ≥ rail_open_us + U_US`. Otherwise "capture did not cover the uncertainty window".
7. Let `E` be the edges in `busy_end_edges_us` greater than `busy_entry_us`:
   - any `e ≤ rail_open_us − U_US` gives "busy ended before the rail opened". The write completed;
     this is the late-cut case;
   - otherwise, any `e ≤ rail_open_us + U_US` gives "busy end within ±U of rail opening
     (ambiguous)". **Fail-closed.**
8. Otherwise the row qualifies.

Edges after `rail_open_us + U_US` are ignored for qualification. By then VCARD is below 2.70 V, so the
card is outside its operating range, and a later rising edge can be a brown-out artefact. They stay
in the row.

**The revision-3 fields `busy_sampled_us`, `cut_us` and `busy_deassert_us` are not used by a
revision-2 judge.** A revision-2 row may omit them. If it includes them, they're carried as
diagnostics.

### Optional evidence fields (never needed to qualify)

`trace_sha256` (the analyser capture for this trial, when one was taken), `vcard_mv_before_repower`
(ADC monitor), `init_ms`, `init_ms_after_cut`. The judge ignores unknown fields, as in revision 3.

## 5. Rig manifest (committed before the plan)

This is a JSON file whose SHA-256 the plan binds. It holds identities and declared design values;
the judge doesn't take thresholds from it.

| Field | Content |
|---|---|
| `method` | `"rig-r2"` |
| `rig_doc` | Repository path and git blob SHA of the ATOMICITY-RIG.md revision used |
| `firmware_sha256` | SHA-256 of the exact rig firmware binary flashed. Plus `firmware_source_commit` |
| `host_script_sha256` | SHA-256 of the host script that writes run.jsonl |
| `judge_sha256` | SHA-256 of the media_atomicity.py used |
| `bus` | `{"mode": "spi", "busy_line": "MISO", "sck_hz": …}` |
| `capture` | Timer, clock in Hz, and the two capture pins |
| `switch` | Circuit revision `"r2"`, the switch part, CT, R_EXT, bulk capacitance at the socket, and buffer and comparator part numbers |
| `thresholds_measured` | Control E0 results: A's falling trip voltage and B's rising trip voltage, as measured. Each with the instrument, its certificate or ID, and the raw-file hash |
| `skew_measured_ns` | Control E3 result: the maximum \|A − B\| capture difference for a common edge, with the raw-file hash |
| `controls` | For each pre-campaign control (§7 of the rig doc): result, date, witness, and raw-evidence hashes |
| `card` | Exact identity: photographed manufacturer part number and the photo hash, retail name, capacity from the CSD, raw CID, decoded MID/OID/PNM/PRV/PSN/MDT, and the plan `--revision` string (`PNM/PRV`) |

## 6. Verdict additions

| Field | Meaning |
|---|---|
| `method`, `rig_manifest_sha256` | From the plan, cross-checked against every row |
| `bus_mode`, `sck_hz` | From evidence: one value each across all rows, otherwise a problem |
| `qualification_scope` | `"spi-characterisation"` when the bus mode is spi. `"sd4"` is reserved for a native-mode rig. Neither is a card qualification by itself |
| `torn_iterations`, `corrupt_iterations`, `neighbour_damage` | Now over **all validated rows**, qualifying or not |
| `damage_on_non_qualifying` | The subset of the three lists above from non-qualifying rows. For visibility; they already force FAIL |
| `verdicts` | OLD/NEW/TORN/CORRUPT counts for **qualifying** rows. Unchanged meaning |
| `verdicts_non_qualifying` | The same counts for validated non-qualifying rows |
| `completed_write_reverted` | Iterations whose reason was "busy ended before the rail opened" and whose target reads OLD. **Reported, not verdict-changing.** See the question to PM in the rig doc §8 |

The verdict is PASS only if there are no problems, no tears, no corrupt blocks and no neighbour
damage on any validated row, at least 1,000 qualifying rows, and exactly one card identity.

## 7. Cases the independent tests are expected to cover

These are listed so the interface is testable. Verification authors the tests and owns their
assertions; this list doesn't replace or limit them.
- A positive production-threshold run.
- A tear, or neighbour damage, on a late-cut, ambiguous, no-cut or delayed-cut row.
- Stale busy evidence: the revision-3 counterexample of a sample at 120 µs and a cut at
  1,000,000 µs.
- Busy end at exactly `rail_open − U`, `rail_open`, `rail_open + U`, and just beyond.
- Capture armed after busy entry. A short capture window.
- A missing or mismatched `card_cid_after_cut`, manifest hash, method or SCK.
- Malformed timing types. Missing, duplicate and unplanned rows.
- Valid late misses that don't count toward the 1,000 and don't hide corruption.
