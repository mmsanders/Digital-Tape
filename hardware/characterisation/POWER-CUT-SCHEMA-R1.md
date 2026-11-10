# Power-cut self-run evidence schema, revision 1 (declaration, correction 2)

**Owner:** Hardware Lead · **Status:** PUBLIC INTERFACE DECLARATION. **Not implemented.**
- **First declared** 9 November 2026 at PR #673 head `c32f1a56`, after Verification's V398 stage 3
  review (disposition at Verification `321c5236`, package `tests/power_cut_selfrun_r1` tree
  `20dde468`).
- **Correction 2**, 10 November 2026, for [#675](https://github.com/mmsanders/Digital-Tape/issues/675).
  Base: main `21b2da3`. It does two things:
  - it puts PM's settled P3, P4, P1/P2 and SPI decisions into the text
    ([ADR-209](../../docs/DECISIONS.md#adr-209--finish-pre-parts-interfaces-and-put-the-first-board-on-the-critical-path));
  - it adds the exact plan/judge CLI, serial normalisation and build-record boundaries (§2, §7)
    that V405 lane A binds.

It's published **before** any judge code:
1. Verification (V405) authors tests from it.
2. Those tests are imported unchanged.
3. Only then does `media_atomicity.py` change.

The method it records is [POWER-CUT-SELFRUN.md](POWER-CUT-SELFRUN.md).

## 0. PM decisions in force (ADR-209, 8 November 2026)

| Item | Decision | Where |
|---|---|---|
| **P3**, CID | **Option B.** The CID is optional and diagnostic-only. A missing CID or a CID disagreement is kept and reported, never a problem, never a qualification gate, and never a fabricated value. One-card-per-run identity comes from the model, photos, unit label, back print, plan, run and build | §3.2 V6, §6 |
| **P4**, completed write reads OLD | A non-empty `completed_before_old` **fails the run**, under the exact predicate in §5. No qualifying credit. Never relabelled TORN, never called a proven card defect. NEW after completion is a retained late miss | §5, §6 |
| **P1**, sample-to-cut gap | ≤ 5.0 µs qualifies; equality qualifies; greater is a retained miss | §3.3 |
| **P2**, card-off voltage | ≤ 200 mV is lawful; equality is lawful; greater is a run problem | §3.2 V7 |
| **SPI scope** | SPI at 4 MHz `selfrun-r1` is the ADR-208 Phase 3 **card-model** atomicity evidence route. `qualification_scope: "spi-characterisation"` stays. The bus, the speed and one-unit-per-model are mandatory residual limits in every verdict. A complete, independently reviewed ≥ 1,000-cut run with its MICHAEL-CHECKS entry may satisfy WP-05 A-6. It proves nothing about SD 4-bit equivalence, production copy speed, other modes or other cards | §6 |

These are logical checks on the firmware's own observations, not calibrated electrical proof.
Plan v3, plan v4, rig-r2 and every imported Verification package stay byte-identical. The new route
sits beside them.

## 1. What changes, in one paragraph each

**Identity without a CID (H398-1).** Plan v3 needs `--cid` and refuses rows without one. The
`selfrun-r1` route (plan version 5) binds the **card model** and the **card unit** into the plan
digest instead:
- **Card model:** brand/line, capacity, part number or `null`, and photo hashes.
- **Card unit:** the label Michael gives the physical card, plus its back print.

The CID is an optional observation, kept on every row and reported. Nobody types a fake CID.

**P1, P2 and the build (H398-2).** These are enforced, with exact types and an exact
miss-or-problem class for each failure:
- **Build:** the plan binds the firmware build and the hex image's hash. Every row and the serial
  `BUILD` line must carry the same build.
- **P1:** a busy sample more than 5.0 µs before the cut is a miss.
- **P2:** a card that read above 200 mV during the off-time fails the run.

**Completed write that reads OLD (H398-3).** This is listed by its exact self-observed predicate,
and it fails the run (P4).

## 2. Plan, version 5, and the CLI

```
media_atomicity.py plan  --method selfrun-r1 --card CARD.json --build-record build.json
                         --t-sched-us T [--cid HEX32] [--attempts N] [--seed S] [--block B] --out plan.json
media_atomicity.py plan  --extend plan.json [--attempts N] [--seed S] --out ext.json
media_atomicity.py judge --plan plan.json [--plan ext.json ...] --serial serial.log
                         --build-record build.json --hex firmware.hex [--run-jsonl OUT] [--json OUT]
```

- **`plan`, new run.**
  - Refuses with a non-zero exit and writes no file if any of these is wrong: `--method` isn't
    `selfrun-r1`; CARD.json or build.json fail their grammar (below); a photo file is missing or its
    SHA-256 differs; `--cid` is given but isn't 32 lowercase hex; T isn't a finite number > 0;
    `--attempts` < 1000.
  - `--sku`, `--revision`, `--manifest` and `--evidence` are refused together with `--method
    selfrun-r1`.
  - Photo paths are relative to the current directory.
- **`plan --extend`.** Continues the run under the same `run_id`. It inherits every identity field,
  the build, `hex_sha256` and `t_sched_us`. Passing `--card`, `--build-record`, `--cid` or
  `--t-sched-us` with `--extend` is refused. A new card unit or build needs a new run.
- **`judge` with any plan-v5 plan.**
  - It takes the raw serial capture, never a pre-made `run.jsonl`; `--results` is refused. It runs
    the normalisation of §7 itself, so normalisation can't be bypassed.
  - `--run-jsonl OUT` writes the normalised rows for the record.
  - Mixing a v5 plan with a v3 or v4 plan in one run is a problem.
- **`judge` exit codes**, as today:
  - **0**: verdict PASS;
  - **2**: verdict FAIL;
  - **2**: input refused (unreadable file, not strict JSON, a missing required argument).

**CARD.json**: exactly the keys `card_model` and `card_unit`, shaped as in the table below. An
unknown key, a missing key or a wrong type is refused.

**build.json**: exactly `{"firmware_build": 40 lowercase hex, "hex_sha256": 64 lowercase hex}`.

| Field | Type | Rule |
|---|---|---|
| `plan_version` | `5` | |
| `method` | `"selfrun-r1"` | |
| `run_id` | string | `selfrun-` + `card_unit.label` with spaces replaced by `-` + `-` + 16 random lowercase hex |
| `card_model` | object | Exactly these keys: `brand_line` (non-empty string), `capacity_label` (non-empty string as printed), `part_number` (non-empty string or `null`; Michael's PNY packaging is gone, so `null` is lawful and nothing is invented) and `photos` (one or more `{"path": non-empty string, "sha256": 64 lowercase hex}`) |
| `card_unit` | object | Exactly these keys: `label` (non-empty string Michael assigns, e.g. `"PNY-1"`) and `back_print` (list of strings as printed; may be empty) |
| `card_cid` | 32 lowercase hex or `null` | Optional; diagnostic only (P3) |
| `firmware_build` | 40 lowercase hex | From build.json |
| `hex_sha256` | 64 lowercase hex | From build.json |
| `t_sched_us` | finite number > 0 | Median busy time from 100 uncut writes on this unit and build |
| `block`, `neighbour_offsets`, `planned_attempts`, `required_qualifying`, `note`, `extends`, `created`, `trials` | | As plan v3 |
| `plan_digest` | 64 hex | SHA-256 of the existing canonical JSON form (sorted keys, `(",", ":")` separators) over: `run_id`, `method`, `card_model`, `card_unit`, `card_cid`, `firmware_build`, `hex_sha256`, `t_sched_us`, `block`, `neighbour_offsets` and the trial schedule `[[iteration, cut_offset_fraction], …]` |

For Michael's cards the record is:
- `brand_line "PNY Elite-X"`;
- `capacity_label "64 GB microSDXC"`;
- `part_number null`;
- the two photos and their hashes from `docs/evidence/cards/README.md`;
- `back_print ["2549W120306", "BSTPRAY16J1"]` for the photographed unit.

## 3. Row, `selfrun-r1`

### 3.1 Fields

The row is a JSON object with exactly these keys. An unknown key is a problem: the row is the
firmware's record, and an extra key means a firmware/schema mismatch.

| Field | Type |
|---|---|
| `method` | `"selfrun-r1"` |
| `iteration` | positive integer |
| `run_id`, `plan_digest` | strings, as plan v3 |
| `card_unit` | string, the plan's `card_unit.label`, echoed from the host's run header |
| `firmware_build` | 40 lowercase hex, compiled into the firmware |
| `card_cid` | 32 lowercase hex or `null`: the CID read before the cut (step 2) |
| `card_cid_after_cut` | 32 lowercase hex or `null`: the CID read after re-power (step 10) |
| `bus_mode` | `"spi"` |
| `busy_line` | `"MISO"` |
| `sck_hz` | positive integer |
| `precondition_ok` | boolean |
| `precondition_readback_hex`, `readback_hex` | 1024 lowercase hex characters (512 bytes) |
| `neighbour_baseline`, `neighbours` | objects with exactly the keys `"-2"`, `"-1"`, `"+1"`, `"+2"`, each 1024 lowercase hex characters |
| `payload_complete`, `data_response_accepted` | boolean |
| `busy_entry_us`, `busy_sampled_us`, `busy_deassert_us` | time or `null` (§3.2 V9) |
| `cut_us` | time |
| `vcard_off_mv` | integer |
| `init_ms` | finite number ≥ 0, or `null`; diagnostic only |

A **time** is a JSON number, integer or float, finite and ≥ 0, in microseconds from trial start on
one timer. A boolean is not a number, and nor is a string. The strict reader refuses `NaN`,
`Infinity` and duplicate keys.

### 3.2 Validation: failure is a run **problem**

| # | Rule |
|---|---|
| V1 | `method` is `"selfrun-r1"` on the row and the plan. `iteration` is in a committed plan; `run_id` and `plan_digest` match that plan. A missing, duplicate or extra iteration is a problem (as plan v3) |
| V2 | `card_unit` equals the plan's `card_unit.label` |
| V3 | `firmware_build` equals the plan's `firmware_build` (so a mixed or missing build is a problem on that row) |
| V4 | `precondition_ok` is true. `precondition_readback_hex` is exactly `pattern(N−1)`. `readback_hex` is 512 bytes. Exactly four neighbours, each with a baseline (plan v3 rules) |
| V5 | `bus_mode` is `"spi"`, `busy_line` is `"MISO"`, `sck_hz` is a positive integer and not a boolean |
| V6 | `card_cid` and `card_cid_after_cut` are each `null` or 32 lowercase hex. A malformed value is a problem. **P3 option B:** no CID value or disagreement is ever a problem. Disagreements are reported (§6) |
| V7 | `vcard_off_mv` is an integer, not a boolean, with 0 ≤ v ≤ 4000; otherwise it's malformed. **P2:** v > 200 is a problem: "card not unpowered during the off-time". 200 is lawful |
| V8 | Every field has the type in §3.1. A missing field or an unknown key is a problem |
| V9 | Record integrity: `busy_sampled_us` is `null` iff `busy_entry_us` is `null`. When both are non-null, `busy_entry_us ≤ busy_sampled_us ≤ cut_us`. When `busy_deassert_us` is non-null, `busy_entry_us` is non-null and `busy_sampled_us < busy_deassert_us`. When `data_response_accepted` is false, `busy_entry_us` is `null` |

### 3.3 Qualification: failure is a **miss**

A miss earns no credit. The row is still classified, and damage on it still fails the run (R374-1,
unchanged). The checks run in this order, and the first failure is the recorded reason, with
exactly this text:

1. `payload_complete` true. Otherwise `"single-block payload not proven complete"`.
2. `data_response_accepted` true. Otherwise `"data-response token not accepted"`.
3. `busy_entry_us` non-null. Otherwise `"busy entry not observed"`.
4. `busy_deassert_us` is `null` or `> cut_us`. Otherwise **`"busy ended before the cut"`**. This is
   the only completed-before reason (§5).
5. **P1:** `cut_us − busy_sampled_us ≤ 5.0`. Otherwise `"busy sample older than 5 us at the cut"`.
6. Otherwise the row qualifies.

`busy_deassert_us > cut_us` can't happen with this firmware, because it stops reading at the cut.
If it appears, it's ignored for qualification and kept in the row.

### 3.4 Boundary table (`busy_entry_us = 100.0`, `busy_sampled_us = 180.0`)

| Case | Outcome |
|---|---|
| `cut_us = 185.0` (gap 5.0) | Qualifies |
| `cut_us = 185.000001` | Miss, `"busy sample older than 5 us at the cut"` |
| `cut_us = 50180.0` (the V398 probe) | Miss, same reason |
| `busy_deassert_us = 181.0`, `cut_us = 181.0` | Miss, `"busy ended before the cut"` (equality counts as ended) |
| `busy_deassert_us = 181.0`, `cut_us = 181.5` | Miss, `"busy ended before the cut"` |
| `busy_deassert_us = 180.0` | Problem, V9 (deassert not after the last busy sample) |
| `vcard_off_mv` = 200 / 201 / 3300 / 4001 / `200.0` / `true` | Lawful / problem / problem / problem / problem (not an integer) / problem |
| `firmware_build` missing, or different from the plan | Problem (V3) |
| Both CIDs `null` on every row, plan `card_cid` `null` | Lawful; verdict `card_cid` is `null`, `cid_disagreements` is empty |
| `card_cid` ≠ `card_cid_after_cut`, both non-null | Lawful row; reported in `cid_disagreements`; credit unaffected |

## 4. Policy constants (code, not operator input)

These sit beside the existing `Policy` fields and are never read from a plan, a row or the command
line.

| Constant | Value |
|---|---|
| `REQUIRED_QUALIFYING` | 1000 (unchanged) |
| `METHOD_SELFRUN` | `"selfrun-r1"` |
| `SAMPLE_TO_CUT_MAX_US` | 5.0 |
| `VCARD_OFF_MAX_MV` | 200 |
| `VCARD_OFF_RANGE_MV` | 0 to 4000 inclusive |

## 5. Completed write that reads OLD (P4)

**Predicate.** A row is listed in `completed_before_old` when all of these hold:
- it passes all of §3.2;
- its §3.3 reason is `"busy ended before the cut"`, which already implies an accepted complete
  payload, an observed busy entry and `busy_deassert_us ≤ cut_us`;
- its target classifies **OLD**.

**Why it counts as completed.** The firmware stamps `busy_deassert_us` at the end of the byte in
which DO was seen high. So the card's real deassert came no later than that stamp, and the stamp
is ≤ `cut_us`: on the firmware's own observation, the card reported the write finished before
power was cut.

**Outcome.** A non-empty `completed_before_old` **fails the run** as run integrity:
- each listed iteration adds the problem `"trial N: completed write reads OLD (busy ended before the
  cut)"`;
- the row earns no credit and its readbacks are kept;
- it is never relabelled TORN, never called a proven card defect, and never proven against an
  external U.

A completed-before row that reads **NEW** is a lawful late miss.

## 6. Verdict

| Field | Meaning |
|---|---|
| `method`, `run_id`, `plan_digest` | From the head plan |
| `card_model`, `card_unit`, `firmware_build`, `hex_sha256`, `t_sched_us` | From the plan, confirmed by rows, the `BUILD` line and build.json (§7) |
| `cids_seen` | Sorted list of the distinct non-null values of plan `card_cid`, row `card_cid` and row `card_cid_after_cut` over validated rows |
| `card_cid` | The single element of `cids_seen` when it has exactly one, else `null` |
| `cid_disagreements` | List of `{"iteration": N, "kind": K, "values": [a, b]}`, in iteration order, then kind order: `"before_after"` when the row's two CIDs are both non-null and differ; `"vs_plan"` when the plan's `card_cid` is non-null and a non-null row CID differs from it (one entry per differing field, `a` the plan's value). Diagnostic only |
| `bus_mode`, `sck_hz` | One value each across validated rows, else a problem |
| `qualification_scope` | `"spi-characterisation"` |
| `residual_limits` | Exactly `["bus: SPI at the logged sck_hz, not SD 4-bit", "busy timing and card-off voltage are self-observed", "one card unit per model"]` |
| `planned_attempts`, `reported`, `qualifying`, `required_qualifying`, `non_qualifying` | As today |
| `verdicts`, `verdicts_non_qualifying`, `torn_iterations`, `corrupt_iterations`, `neighbour_damage`, `damage_on_non_qualifying` | As today, over all validated rows |
| `completed_before_old` | §5 |
| `vcard_off_mv_max`, `sample_to_cut_us_max` | Largest values over validated rows. `sample_to_cut_us_max` covers rows with non-null `busy_sampled_us`; `null` if there are none |
| `serial_sha256`, `run_jsonl_sha256`, `build_record_sha256` | SHA-256 of the exact input bytes, and of the normalised rows (§7) |
| `problems`, `verdict` | |

**PASS** only if all of these hold:
- no problems;
- no TORN, no CORRUPT, no neighbour damage;
- `completed_before_old` empty;
- at least 1,000 qualifying rows.

A CID disagreement never changes the verdict.

## 7. Serial log, build record and MICHAEL-CHECKS

**Build record.** For each build the host writes `build.json` (§2). The `.hex` file is the exact
image given to the Teensy loader. The firmware can't hash its own image, so the binary is linked by
`hex_sha256`. The source commit is compiled in.

**Serial grammar.** The input is the raw bytes of `serial.log`.
1. It must decode as UTF-8; otherwise the input is refused.
2. Split on `\n`. A final segment with no `\n` after it is a truncated line:
   - if it begins with `ATOM` or `BUILD`, that's a problem `"truncated tagged line"`;
   - otherwise it's ignored.
3. Strip one trailing `\r` from each line.
4. A line that begins with exactly `BUILD ` (six bytes) is a build line. The rest must be one
   strict JSON object with exactly the keys `firmware_build` (40 lowercase hex), `timer` (non-empty
   string) and `timer_hz` (positive integer).
5. A line that begins with exactly `ATOM ` (five bytes) is a row line. The rest must be one strict
   JSON object.
6. A line that begins with `ATOM` or `BUILD` but isn't followed by exactly one space and an object
   is a problem `"malformed tagged line"`. Every other line is ignored (boot banners, debug prints)
   and stays in `serial.log`.
7. There must be **exactly one** build line, and it must come before the first row line. Zero
   build lines, more than one, or one after a row line is a problem.

**Normalisation (the only transformation).** `run.jsonl` is, in order, the text after `ATOM ` of
every row line, each followed by one `\n`. `run_jsonl_sha256` is over those bytes. Re-running the
judge on the same `serial.log` gives the same bytes.

**Build linkage.** These must all be equal, and any mismatch is a problem:
- the `BUILD` line's `firmware_build`;
- every row's `firmware_build` (V3);
- the plan's `firmware_build`;
- build.json's `firmware_build`.

In addition, SHA-256 of the `--hex` file's bytes must equal build.json's `hex_sha256` and the plan's
`hex_sha256`.

**MICHAEL-CHECKS entry** (one per run, read by Verification, not by the judge):
- date and card unit label;
- `firmware_build`, `hex_sha256` and `plan_digest`;
- `serial_sha256`, `run_jsonl_sha256` and the SHA-256 of `verdict.json`;
- the verdict's `qualifying`, `vcard_off_mv_max` and `sample_to_cut_us_max`;
- Michael's note.

Verification checks that the entry's hashes match the files and that the build matches.

**Separation.** This firmware is a characterisation tool under `hardware/characterisation/`, not
product firmware. Software's F3/F4 serial declaration (#674, V405 lane B) is separate and isn't
constrained by this. The self-run firmware that actually drives cuts needs its own public interface
and independently bound tests before it's written (#675 Stage 2).

## 8. What stays the same

- Plan v3 and v4, the rig-r2 predicate, the manifest loader and `completed_write_reverted`.
- Every imported package and its byte identity: V380, V382, rig_records_r1, V388, V390, V392 and
  V398 `power_cut_selfrun_r1`.
- The fixed 1,000 minimum, keep-every-row, classification of every validated row, and torn as a
  format blocker.
- No retired requirement comes back: no rail traces, calibrated instruments, external timebase,
  U, manifest or mandatory CID.

## 9. Order from here

1. V405 publishes bound tests for this declaration on Verification main.
2. They are imported unchanged into `hardware/characterisation/verification/`, in one commit with
   no other change. Software owns any shared `tests/IMPORTS.json` or workflow plumbing.
3. The v5 route goes into `media_atomicity.py`, plus `atomicity-test` wiring, in a later commit.
4. V405 reviews the exact head.
