# Atomicity rig evidence schema and judge rules, revision 2 (declaration, correction 1)

**Owner:** Hardware Lead · **Status:** PUBLIC INTERFACE DECLARATION, partly implemented (below).
**Drafted:** 2 November 2026 for [P3-R2-HW (#651)](https://github.com/mmsanders/Digital-Tape/issues/651),
answering findings R374-1, R374-2 and R374-5 (Verification `3d616c14`, `findings/P3-R1-374/RIG-METHOD.md`).
**Correction 1:** 4 November 2026. It answers V382's four declaration findings on #651 and adopts
[ADR-204](../../docs/DECISIONS.md) (Product `51d0f8f`).

This declares what a revision-2 plan, row, manifest and verdict look like, and the rules the judge
applies. It's published **before** the judge code it covers, so that Verification can author its
regression tests independently.

**Implementation status, 4 November:**

| Part | State | Independent tests |
|---|---|---|
| R374-1 aggregation (§1, the damage fields in §6) | **Implemented** at `dc38a4d` | V380 `bab04466`, tree `1ca703a4`, imported unchanged; disposed PASS on `2faa1180` by V382 |
| Row predicate `qualifies(row)` for rig-r2 rows (§4.2–4.5) | **Implemented** after this correction | V382 `8879dbac`, `tests/rig_timing_r1` tree `ccf9bd21`, imported unchanged before the code |
| Plan v4 (§3), manifest loading and authentication (§5), rig-r2 row validation (§4.1), `completed_write_reverted` and the scope fields (§6) | **Declared, not implemented** | Unbound. V382 has authored the cases (`rig_timing_r1/README.md`) and binds them to this correction |

Until plan v4 is implemented, the plan-v3 judge **refuses any row that carries `method`** as a run
problem ("rig-r2 rows need the plan-v4 judge"). A rig-r2 row can't earn credit through the
revision-3 judge. Nothing here lowers the 1,000-qualifying-cut minimum or the zero-tear /
zero-neighbour-damage requirement.

The circuit and procedure this schema records are in [ATOMICITY-RIG.md](ATOMICITY-RIG.md) revision 2.

## 1. What changes, in one paragraph each

**R374-1, damage can't hide behind non-qualification.** Every row that passes row validation (§4.1)
has its target and all four neighbours classified, **whether or not it qualifies**. Any TORN or
CORRUPT target, or any changed neighbour, on any validated row makes the verdict FAIL and is listed by
iteration. Qualification only decides what counts toward the 1,000.

**R374-2, qualification is decided from measured electrical events, not from software timestamps.**
- *Rail opening* is the first falling edge of comparator A, which trips when VCARD falls through a
  threshold that is **always below 2.70 V**, the bottom of the card's operating range.
- *Busy end* is a rising edge of comparator B on the card's DO line at or after busy entry.

Both edges are timestamped by hardware input capture on one timer. A trial qualifies only if no busy
end occurs at or before rail opening plus U. The GPIO write time is a delay bound and a diagnostic.

**ADR-204, completed-before and rollback.** Completed-before means **`busy_end < rail_open − U`,
strictly**. A busy end equal to either `rail_open − U` or `rail_open + U` is ambiguous. If a
validated row's only reason for not qualifying is completed-before, and its target reads OLD, the run
fails integrity as `completed_write_reverted`. That row earns no credit, and it isn't relabelled TORN
or called a media defect. Ambiguous, incomplete or record-invalid rows are never completion proof.

**R374-5, scope stays explicit.** Every row and the verdict carry the bus mode, the SPI clock and the
rig manifest hash. A run in SPI mode reports `qualification_scope: "spi-characterisation"`. That scope
is never SD 4-bit, SDR50 or card-system qualification. PM owns any wider scope.

## 2. Judge constants (code, not operator input)

These live in the judge's `Policy`, like `REQUIRED_QUALIFYING` (IR-018-06). They're never read from
the plan, the manifest or a row. A row field with the same name (`U_US`, `CUT_DELAY_MAX_US`) is
ignored. The manifest *records* the rig's measured values, and the judge checks them against these
windows (§5.3).

| Constant | Value | Why |
|---|---|---|
| `REQUIRED_QUALIFYING` | 1000 | Unchanged |
| `U_US`, edge-alignment uncertainty | **1.0 µs** | Bounds the busy-edge path and any early A edge (ATOMICITY-RIG §4.3). It's a **model value**: controls E3 and E4 must confirm it before any campaign |
| `CUT_DELAY_MAX_US` | **500 µs** | Bound from the cut command to the measured rail opening. It catches a delayed or missing cut. A fault bound, not a timing claim |
| `METHOD` | `"rig-r2"` | Rows, plans and manifests from any other method are refused |
| `A_FALL_V` | 2.570 – 2.610 V | Window for E0's measured falling trip of A (design 2.575–2.606 V) |
| `B_RISE_V` | 1.010 – 1.040 V | Window for E0's measured rising trip of B (design 1.015–1.033 V) |
| `SKEW_MAX_NS` | 300 | E3 limit |

## 3. Plan, revision 4

The plan is as in revision 3, plus:

| Field | Type | Rule |
|---|---|---|
| `plan_version` | 4 | |
| `method` | `"rig-r2"` | Included in `plan_digest` |
| `rig_manifest_sha256` | 64 lowercase hex | SHA-256 of the manifest file's exact bytes (§5). Included in `plan_digest`, so a run can't be re-pointed at another rig build or calibration |

The `sku`, `revision` and `card_cid` the plan is made with must equal the manifest's `card.mpn`,
`card.revision` and `card.cid`. `plan` checks that, and the judge checks it again. A continuation plan
(`--extend`) inherits `method` and `rig_manifest_sha256`. A different manifest needs a new run.

## 4. Row, revision 2

Every revision-3 field keeps its meaning: iteration, run_id, sku, revision, card_cid, plan_digest,
precondition_ok, precondition_readback_hex, readback_hex, neighbours, neighbour_baseline, bus_mode,
busy_line, payload_complete and data_response_accepted.

**Times.** Every `_us` value is microseconds from trial start on the capture timer's timebase. A time
is a JSON number: an integer or a float that is **finite and ≥ 0**. A boolean is not a number, and
neither is a string. Wire JSON with `NaN` or `Infinity` is refused by the complete judge's reader
(§5.1); the predicate also refuses non-finite values given to it directly.

### 4.1 Row validation (complete judge; failure is a run problem). Not implemented

| Field | Type | Rule |
|---|---|---|
| `method` | string | Must equal `"rig-r2"` |
| `rig_manifest_sha256` | hex | Must equal the plan's value |
| `card_cid` | 32 hex | The CID read at power-up **before** the cut. Must equal the plan's and the manifest's `card.cid` |
| `card_cid_after_cut` | 32 hex | The CID read at power-up **after** the cut. Missing, malformed or different from `card_cid` is a problem. An initialisation failure after a cut is therefore a FAIL, never a skip |
| `bus_mode`, `busy_line`, `sck_hz` | | Must equal the manifest's `bus.mode`, `bus.busy_line` and `bus.sck_hz` |
| `firmware_source_commit` | 40 hex | Built into the rig firmware and printed in every row. Must equal the manifest's `firmware.source_commit` |
| `switch_revision` | string | Built into the firmware. Must equal the manifest's `switch.revision` (`"r2"`) |
| `rail_high_at_arm` | `true` | A's output read high when capture was armed (§4.2). Any other value is a problem |
| Record integrity (§4.3) | | A row that breaks a record-integrity rule is a **run problem**, not a miss. A recorder that writes contradictions can't be trusted on its other rows |
| All revision-3 validation | | Unchanged: identity, plan digest, precondition, a 512-byte readback, and exactly four neighbours with baselines |

### 4.2 Timing fields and their meaning

| Field | Type | Meaning |
|---|---|---|
| `capture_armed_us` | time | When edge capture on both comparators was armed. The firmware arms only while A's output reads high (VCARD above the A threshold), and records `rail_high_at_arm: true` |
| `busy_entry_us` | time | Capture-timer time at which the first 0x00 byte after an accepted data-response token **finished** transferring. DO was low for that whole byte |
| `cut_command_us` | time | Capture-timer time read **immediately before** the firmware drives the switch's ON pin low, so the pin edge is no earlier than this. Delay bound and diagnostic only |
| `rail_edges_us` | list of times | **Every** comparator A edge captured between arming and `capture_end_us`, in strictly increasing order. Because A is high at arming, the polarity is fixed by position: index 0, 2, 4… are falling edges (VCARD went below the threshold) and index 1, 3, 5… are rising edges |
| `rail_open_us` | time or `null` | The first falling edge of A after arming, which is `rail_edges_us[0]`. `null` exactly when `rail_edges_us` is empty |
| `busy_end_edges_us` | list of times | **Every** rising edge of comparator B (DO above the B threshold) captured between arming and `capture_end_us`, strictly increasing. Edges before `busy_entry_us` come from the response token and the bytes before busy, and are kept but don't count (§4.4) |
| `capture_end_us` | time | When capture stopped. Edges after it aren't observed |

The revision-3 fields `busy_sampled_us`, `cut_us` and `busy_deassert_us` are **not used** by any
rig-r2 rule. A rig-r2 row may omit them. If it includes them, they're carried as diagnostics and
can't replace a missing edge.

### 4.3 Record integrity (contradictions, out-of-window edges)

The predicate returns `(False, "rig-r2 record invalid: …")` for any of these. In the complete judge
each is a run problem (§4.1).

| # | Rule |
|---|---|
| R1 | Every field in §4.2 is present. `rail_open_us` may be `null`; the others may not |
| R2 | `capture_armed_us`, `busy_entry_us`, `cut_command_us` and `capture_end_us` are times. `rail_open_us` is a time or `null` |
| R3 | `rail_edges_us` and `busy_end_edges_us` are lists whose elements are times, in strictly increasing order |
| R4 | `capture_armed_us ≤ capture_end_us` |
| R5 | Every edge in both lists lies in `[capture_armed_us, capture_end_us]` |
| R6 | `rail_open_us` is `null` if and only if `rail_edges_us` is empty, and otherwise equals `rail_edges_us[0]`. A claimed opening that wasn't recorded, or a recorded edge that isn't the claimed opening, is a contradiction |
| R7 | If `rail_high_at_arm` is present it must be `true` (the complete judge requires it, §4.1) |

### 4.4 Qualification (failure is a non-qualifying miss)

The judge evaluates these in order, and the first failure is the recorded reason:

1. The revision-3 protocol checks: a valid bus mode and busy line, `payload_complete` true and
   `data_response_accepted` true.
2. Record integrity (§4.3).
3. `capture_armed_us ≤ busy_entry_us`. Otherwise "busy capture not armed at busy entry".
4. `rail_open_us` is not `null` and `rail_open_us > busy_entry_us`. Otherwise "rail opening not
   observed after busy entry". This is the no-cut case.
5. `0 ≤ rail_open_us − cut_command_us ≤ CUT_DELAY_MAX_US`. Otherwise "rail opening outside the cut
   delay bound". This is the delayed-cut case, and also an opening before the command.
6. `capture_end_us ≥ rail_open_us + U_US`. Otherwise "capture did not cover the uncertainty window".
7. Let `E` be the edges in `busy_end_edges_us` that are **≥ `busy_entry_us`**:
   - any `e < rail_open_us − U_US`: **"busy ended before the rail opened"**. The write completed.
     This is the only completed-before reason (ADR-204);
   - otherwise, any `e ≤ rail_open_us + U_US`: **"busy end within ±U of rail opening
     (ambiguous)"**. Fail-closed, and never completion proof.
8. `rail_edges_us` has exactly one edge. Otherwise "rail chatter after opening": A went back above
   its threshold inside the capture window, so the opening isn't clean. The design adds 15 mV of
   hysteresis so that a monotonic fall gives one edge (ATOMICITY-RIG §4.1).
9. Otherwise the row qualifies.

Busy-end edges after `rail_open_us + U_US` are ignored for qualification. By then VCARD is below
2.70 V and the card is outside its operating range, so a later rising edge can be a brown-out
artefact. They stay in the row.

### 4.5 Boundary table (U = 1.0 µs, rail opening at 150 µs)

| Busy-end edge | Outcome | Reason |
|---|---|---|
| 148.999 | Miss, completed-before | "busy ended before the rail opened" |
| 149.000 (= rail_open − U) | Miss, ambiguous | "… (ambiguous)" |
| 150.000 | Miss, ambiguous | "… (ambiguous)" |
| 151.000 (= rail_open + U) | Miss, ambiguous | "… (ambiguous)" |
| 151.001 | Qualifies | |
| equal to `busy_entry_us`, below 149 | Miss, completed-before | Counted, because `E` includes equality (busy that ended at once) |

## 5. Rig manifest (committed before the plan). Not implemented

### 5.1 Interface

```
media_atomicity.py plan  --sku S --revision R --cid C --attempts N --manifest MANIFEST.json --evidence DIR --out plan.json
media_atomicity.py judge --plan plan.json [--plan ext.json] --results run.jsonl --manifest MANIFEST.json --evidence DIR [--json OUT]
```

Python API (what the binding imports, besides `qualifies(row)`):

- `load_manifest(path, evidence_dir) -> (manifest: dict, sha256: str, problems: list[str])`. It reads
  the file's bytes, hashes them, parses them and runs §5.2 and §5.3. It never raises on bad input:
  everything wrong is a problem string. An empty problem list is the only success.
- `judge(plans, rows, policy=PRODUCTION, manifest=None)`, where `manifest` is the result of
  `load_manifest`. For a plan-v4 run, `manifest=None` is a problem.

The judge reads `run.jsonl` and the manifest with a strict reader. It rejects `NaN`, `Infinity`,
`-Infinity` and duplicate keys, and the manifest must be UTF-8.

### 5.2 Manifest grammar

The manifest is one JSON object with exactly these keys. An unknown key, a missing key or a wrong
type is a problem. A *ref* is `{"path": P, "sha256": H}`: `P` is a relative path with `/` separators
inside the evidence directory (no `..`, no absolute path, no drive letter), and `H` is 64 lowercase hex.

| Key | Content |
|---|---|
| `method` | `"rig-r2"` |
| `rig_doc` | `{"path": "hardware/characterisation/ATOMICITY-RIG.md", "git_blob": 40 hex}` |
| `firmware` | `{"source_commit": 40 hex, "binary": ref}`. The binary is the exact image flashed |
| `host_script` | ref to the exact `atomicity_host.py` used |
| `judge_sha256` | 64 hex. SHA-256 of the `media_atomicity.py` that judges the run |
| `bus` | `{"mode": "spi", "busy_line": "MISO", "sck_hz": positive integer}` |
| `capture` | `{"timer": string, "clock_hz": positive integer, "pin_a": integer, "pin_b": integer}` |
| `switch` | `{"revision": "r2", "part": "TPS22918", "ct_nf": number, "r_ext_ohm": number, "bulk_uf": number, "hysteresis_ohm": number, "buffer_part": "SN74LVC1G125", "comparator_part": "TLV3202"}` |
| `thresholds_measured` | `{"a_falling_v": [5 numbers], "b_rising_v": [5 numbers], "instrument": {"model": string, "serial": string, "calibration": ref}, "raw": ref}` (control E0) |
| `skew_measured_ns` | `{"max_abs": number, "edges": integer, "raw": ref}` (control E3) |
| `controls` | An object with exactly the keys `E0`, `E1`, `E2`, `E3`, `E4`, `A`, `B`, `B2`, `C`, `D`, `E`, `F`, `G`. Each is `{"result": "pass" or "fail", "date": "YYYY-MM-DD", "witness": non-empty string, "evidence": [one or more refs]}` |
| `card` | `{"mpn": string, "mpn_photo": ref, "retail_name": string, "capacity_bytes": positive integer, "cid": 32 hex, "decoded": {"mid", "oid", "pnm", "prv", "psn", "mdt"}, "revision": "PNM/PRV"}` |

### 5.3 What `load_manifest` and the judge check

1. **Bytes.** SHA-256 of the manifest bytes equals the plan's `rig_manifest_sha256`.
2. **Evidence bytes.** For every ref: the file exists under the evidence directory and the SHA-256 of
   its bytes equals the ref. A missing or changed file is a problem.
3. **Judge identity.** `judge_sha256` equals the SHA-256 of the judge's own source file (`__file__`).
4. **Measured values within Policy.** All five `a_falling_v` are within `A_FALL_V`, all five
   `b_rising_v` are within `B_RISE_V`, and `skew_measured_ns.max_abs ≤ SKEW_MAX_NS` with
   `edges ≥ 1000`.
5. **Controls.** Every control is present with `result: "pass"`. A recorded `"fail"` stays in the
   manifest as evidence, and it makes the judge refuse the run. Failed prerequisites are recorded,
   never dropped. A re-run gets a new manifest and a new plan.
6. **Plan agreement.** `card.mpn`, `card.revision` and `card.cid` equal the plan's `sku`,
   `revision` and `card_cid`. `method` agrees across plan, manifest and rows.
7. **Row agreement** (§4.1): bus mode, busy line, SCK, firmware commit, switch revision, both CIDs.
8. **Verdict.** It reports the manifest hash, the bus mode, SCK and `qualification_scope`.

**What the judge can't establish.** It proves that the evidence files are present, unchanged and
within the declared windows, and that every recorded control passed. It can't prove that a
calibration certificate is genuine, that a measurement was taken as described, or which binary
actually ran on the Teensy (the row's commit is self-reported). Those come from Verification's
review of the raw files, Michael's witness, and dry-run control A (wire truth). Equal hash strings
alone are not treated as calibrated evidence.

## 6. Verdict additions

| Field | Meaning | State |
|---|---|---|
| `torn_iterations`, `corrupt_iterations`, `neighbour_damage` | Over **all validated rows**, qualifying or not | Implemented |
| `damage_on_non_qualifying` | The subset of those lists from non-qualifying rows | Implemented |
| `verdicts` / `verdicts_non_qualifying` | OLD/NEW/TORN/CORRUPT counts for qualifying / validated non-qualifying rows | Implemented |
| `completed_write_reverted` | Iterations of validated rows whose reason is "busy ended before the rail opened" and whose target reads OLD. **Each one is a run-integrity problem (FAIL)** under ADR-204. No credit. Not counted as TORN or as a media defect. A completed-before row that reads NEW is a lawful late miss (no credit, no problem) | Declared |
| `method`, `rig_manifest_sha256`, `bus_mode`, `sck_hz` | From evidence, cross-checked (§5.3). One value each, or a problem | Declared |
| `qualification_scope` | `"spi-characterisation"` when the bus mode is spi. `"sd4"` is reserved for a native-mode rig. Neither is a card qualification by itself | Declared |

The verdict is PASS only if there are no problems, no tears, no corrupt blocks, no neighbour damage
and no `completed_write_reverted` on any validated row, at least 1,000 qualifying rows, and exactly
one card identity.

**Note on the rollback rule.** A's timestamp is no earlier than the moment VCARD left the operating
range, and with a slow fall it can be tens of µs later (ATOMICITY-RIG §4.3). So `rail_open − U` can
treat as "completed before" a busy end that came after VCARD had already dropped below 2.70 V. That
over-reports `completed_write_reverted`; it never under-reports it. The rule fails closed, and a
reported rollback needs its trace reviewed before anyone calls it a card behaviour.

## 7. Independent test binding

Verification authors the tests and owns their assertions; this list doesn't replace or limit them.

- **Bound:** V380 `rig_correction_r2` (R374-1 aggregation, 27 cases) and V382 `rig_timing_r1` (71
  row-predicate cases: boundaries, arming, opening, delay, legacy diagnostics, operator overrides,
  protocol, missing fields, typing, and contradictory or out-of-window records).
- **Still to bind, against this correction:** plan v4 and `load_manifest` (positive production run
  with an authenticated manifest and controls; 999 short and operator override; row identity, CID,
  method, SCK, firmware and switch conflicts; changed or missing manifest, calibration or control
  bytes; a recorded failed control), the complete judge's record-invalid run problems,
  `completed_write_reverted` (OLD strictly before fails; boundary OLD doesn't; NEW adds no credit),
  chatter, and damage on any otherwise valid miss.
