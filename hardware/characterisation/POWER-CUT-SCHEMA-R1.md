# Power-cut self-run evidence schema, revision 1 (declaration)

**Owner:** Hardware Lead · **Status:** PUBLIC INTERFACE DECLARATION. **Not implemented.** Drafted
9 November 2026 on Michael's direction ("do what you can") after Verification's V398 stage 3
review of PR #673 head `1d6a13db` (disposition at Verification `321c5236`, package
`tests/power_cut_selfrun_r1` tree `20dde468`). Base: main `978efb2`.

This answers holds H398-1 and H398-2 and declares the hooks H398-3 needs. It's published **before**
any judge code. Verification authors its tests from it, they are imported unchanged, and only then
does `media_atomicity.py` change. The method it records is
[POWER-CUT-SELFRUN.md](POWER-CUT-SELFRUN.md).

**Waiting on PM. The declaration can't bind those parts until PM rules:**

| Item | What PM decides | Placeholder here |
|---|---|---|
| **P3** (H398-1) | Whether two CIDs that were both read and disagree fail the run, given ADR-208's "CID gates nothing" | §3.2 V6 declares both options; recommended **A** |
| **P4** (H398-3) | Whether a self-observed completed write that reads back OLD fails the run | §5 always reports it; the PASS rule has a slot (§6) |
| **SPI scope** (H398-4) | Whether an SPI-mode PASS counts toward product qualification | Verdict reports `qualification_scope: "spi-characterisation"`, unchanged |

Nothing here changes plan v3, plan v4, rig-r2 or any imported Verification package. The new route
sits beside them.

## 1. What changes, in one paragraph each

**H398-1: identity without a CID.** Plan v3 needs `--cid` and refuses rows without one, so a run
on a card whose CID wasn't read gets no credit. ADR-208 §5 says identity is brand, model or part
number, capacity and a photo, with the CID logged when available. The new route, `selfrun-r1`
with plan version 5, binds the **card model** (brand/line, capacity, optional part number, photo
hashes) and the **card unit** (a label Michael gives the physical card, plus its back print) into
the plan digest. The CID becomes an optional observation that is kept on every row. Nobody types
a fake CID to satisfy old code.

**H398-2: P1, P2 and the build, enforced.** The plan names the firmware build, and every row must
carry the same build. A row's busy sample must be at most 5.0 µs before its cut to qualify (P1). A
row whose card read above 200 mV while it was supposedly off fails the run (P2). Every field has
a type, and each failure is declared as either a **miss** (no credit, row still audited) or a
**problem** (the run fails).

**H398-3: the completed-write-reads-OLD case.** The judge always lists it, under its exact
self-observed predicate (§5). Whether the list fails the run is PM's P4.

## 2. Plan, version 5

`media_atomicity.py plan --method selfrun-r1 --card CARD.json --build HEX40 --t-sched-us T
[--cid HEX32] [--attempts N] [--seed S] --out plan.json`, and `plan --extend plan.json` as today.

| Field | Type | Rule |
|---|---|---|
| `plan_version` | `5` | |
| `method` | `"selfrun-r1"` | |
| `run_id` | string | As plan v3: built from the model and a random 8-byte token |
| `card_model` | object | Exactly `brand_line` (non-empty string), `capacity_label` (non-empty string, as printed, e.g. `"64 GB microSDXC"`), `part_number` (non-empty string or `null`; Michael's PNY packaging is gone, so `null` is lawful) and `photos` (a list of one or more `{"path": string, "sha256": 64 lowercase hex}`) |
| `card_unit` | object | Exactly `label` (non-empty string Michael assigns to the physical card, e.g. `"PNY-1"`) and `back_print` (a list of strings as printed, which may be empty) |
| `card_cid` | 32 lowercase hex or `null` | The CID if Michael or the firmware read one before the plan; otherwise `null`. Never required |
| `firmware_build` | 40 lowercase hex | Source commit of the self-run firmware that will run. One build per run; a new build needs a new run |
| `t_sched_us` | finite number > 0 | Median busy time from 100 uncut writes on this card and build. It only spreads the cuts |
| `block`, `neighbour_offsets`, `planned_attempts`, `required_qualifying`, `note`, `extends`, `created`, `trials` | | As plan v3 |
| `plan_digest` | 64 hex | SHA-256 over `run_id`, `method`, `card_model`, `card_unit`, `card_cid`, `firmware_build`, `t_sched_us`, `block`, `neighbour_offsets` and the trial schedule, in the existing canonical JSON form |

**CARD.json** is `{"card_model": …, "card_unit": …}` exactly as above. `plan` checks that each
photo file exists, relative to the current directory, and that its SHA-256 matches. The judge
doesn't re-read photos. They are bound by hash in the digest, and Verification checks them
against `docs/evidence/cards/`. A `--extend` continuation inherits every identity field and the
build. Changing any of them needs a new run.

For Michael's cards today, the record is: `brand_line "PNY Elite-X"`, `capacity_label "64 GB
microSDXC"`, `part_number null`, with the two photos and hashes in `docs/evidence/cards/README.md`.

## 3. Row, `selfrun-r1`

One row per planned attempt. The firmware prints it as `ATOM ` followed by one JSON object (§7).

### 3.1 Fields

| Field | Type |
|---|---|
| `method` | `"selfrun-r1"` |
| `iteration`, `run_id`, `plan_digest` | As plan v3 |
| `card_unit` | string, the plan's `card_unit.label`, echoed by the firmware from the host's run header |
| `firmware_build` | 40 lowercase hex, compiled into the firmware |
| `card_cid` | 32 lowercase hex or `null`: the CID read before the cut (step 2), `null` if the read failed |
| `card_cid_after_cut` | 32 lowercase hex or `null`: the CID read after re-power (step 10) |
| `bus_mode`, `busy_line` | `"spi"`, `"MISO"` |
| `sck_hz` | positive integer |
| `precondition_ok`, `precondition_readback_hex`, `neighbour_baseline`, `readback_hex`, `neighbours` | As plan v3 |
| `payload_complete`, `data_response_accepted` | boolean |
| `busy_entry_us` | time or `null`: end of the first 0x00 byte after an accepted token; `null` if no 0x00 byte arrived before the cut |
| `busy_sampled_us` | time or `null`: end of the **last** 0x00 byte read before the cut; `null` exactly when `busy_entry_us` is `null` |
| `busy_deassert_us` | time or `null`: end of the first byte after busy entry that was not 0x00; `null` if none was read before the cut |
| `cut_us` | time: read immediately after the switch pin and the bus lines were driven low |
| `vcard_off_mv` | integer: the VMON reading at the end of the off-time |
| `init_ms` | finite number ≥ 0 or `null`; diagnostic only |

A **time** is a JSON number, integer or float, finite and ≥ 0, in microseconds from trial start on
one timer. A boolean is not a number, and nor is a string. The strict reader already refuses
`NaN`, `Infinity` and duplicate keys.

### 3.2 Validation: failure is a run **problem**

Every rule here is a problem when broken. A recorder that writes a contradiction or a missing field
can't be trusted on its other rows.

| # | Rule |
|---|---|
| V1 | Plan v3 identity rules, without `sku`/`revision`/`card_cid` equality: `iteration`, `run_id` and `plan_digest` match, and `method` is `"selfrun-r1"` on both the row and the plan. A `selfrun-r1` row under a v3 or v4 plan, or a v3/v4 row under a v5 plan, is a problem |
| V2 | `card_unit` equals the plan's `card_unit.label` |
| V3 | `firmware_build` is present, 40 lowercase hex, and equals the plan's `firmware_build`. So a mixed or missing build is a problem on that row |
| V4 | Plan v3 precondition, readback and neighbour rules, unchanged |
| V5 | `bus_mode` is `"spi"`, `busy_line` is `"MISO"`, `sck_hz` is a positive integer (not a boolean) |
| V6 | `card_cid` and `card_cid_after_cut` are each `null` or 32 lowercase hex. **P3, pending PM:** **Option A (recommended):** when two non-null CIDs disagree, it's a problem. That covers the row's two reads, a row against the plan's non-null `card_cid`, or two rows in the run. A `null` never causes a problem. **Option B:** disagreements are only reported in the verdict. Either way an absent CID gates nothing; option A fails only on a recorded contradiction |
| V7 | `vcard_off_mv` is an integer (not a boolean) with 0 ≤ v ≤ 4000. **P2:** v > `VCARD_OFF_MAX_MV` (200) is a problem: "card not unpowered during the off-time". 200 is lawful; 201 is a problem |
| V8 | Types per §3.1. `payload_complete` and `data_response_accepted` are booleans; a missing one is a problem, not a miss |
| V9 | Record integrity: `busy_sampled_us` is `null` iff `busy_entry_us` is `null`. When non-null, `busy_entry_us ≤ busy_sampled_us ≤ cut_us`. When `busy_deassert_us` is non-null, then `busy_entry_us` is non-null and `busy_sampled_us < busy_deassert_us`. If `data_response_accepted` is false, `busy_entry_us` is `null` |

### 3.3 Qualification: failure is a **miss**

A miss earns no credit, but the row is still classified and its damage still fails the run (R374-1,
unchanged). The checks run in this order, and the first failure is the recorded reason:

1. `payload_complete` true. Otherwise "single-block payload not proven complete".
2. `data_response_accepted` true. Otherwise "data-response token not accepted".
3. `busy_entry_us` non-null. Otherwise "busy entry not observed".
4. `busy_deassert_us` is `null` or `> cut_us`. Otherwise **"busy ended before the cut"**. This is
   the only completed-before reason (§5).
5. **P1:** `cut_us − busy_sampled_us ≤ SAMPLE_TO_CUT_MAX_US` (5.0). Otherwise "busy sample older
   than 5 µs at the cut".
6. Otherwise the row qualifies.

`busy_deassert_us > cut_us` can't happen with this firmware, because it stops reading at the cut.
If it appears, it's ignored for qualification (as rig-r2 ignores post-opening edges) and kept in
the row.

### 3.4 Boundary table (`busy_sampled_us = 180.0`)

| Case | Outcome |
|---|---|
| `cut_us = 185.0` (gap 5.0) | Qualifies |
| `cut_us = 185.000001` | Miss, "busy sample older than 5 µs at the cut" |
| `cut_us = 50180.0` (the V398 probe) | Miss, same reason |
| `busy_deassert_us = 181.0`, `cut_us = 181.0` | Miss, "busy ended before the cut" (equality counts as ended) |
| `busy_deassert_us = 181.0`, `cut_us = 181.5` | Miss, "busy ended before the cut" |
| `busy_deassert_us = 179.0` | Problem, V9 (deassert not after the last busy sample) |
| `vcard_off_mv = 200` / `201` / `3300` | Lawful / problem / problem (V7, the V398 probe) |
| `firmware_build` missing, or different from the plan | Problem (V3) |
| `card_cid: null`, `card_cid_after_cut: null` | Lawful, no effect |
| `card_cid` ≠ `card_cid_after_cut`, both non-null | Problem under option A; reported under option B |

## 4. Policy constants (code, not operator input)

These sit beside the existing `Policy` fields. They are never read from a plan, a row or the
command line.

| Constant | Value | Why |
|---|---|---|
| `REQUIRED_QUALIFYING` | 1000 | Unchanged |
| `METHOD_SELFRUN` | `"selfrun-r1"` | |
| `SAMPLE_TO_CUT_MAX_US` | 5.0 | One 2 µs busy byte at 4 MHz plus instruction slack; expected < 1 µs (POWER-CUT-SELFRUN §2) |
| `VCARD_OFF_MAX_MV` | 200 | Well below the 0.5 V SD reset level, above ADC noise |
| `VCARD_OFF_RANGE_MV` | 0–4000 | Type sanity; outside it is a malformed row |

## 5. Completed write that reads OLD (P4 hook)

**Self-observed predicate:** a validated row whose qualification reason is "busy ended before the
cut" (§3.3 step 4) and whose target classifies OLD.

The firmware stamps `busy_deassert_us` at the end of the byte in which DO was seen high, so the
card's real deassert came no later than that stamp, and the stamp is ≤ `cut_us`. The card
therefore reported the write finished before power was cut, on the firmware's own observation.
This doesn't borrow rig-r2's independent-edge proof, and a matching row is never relabelled TORN or
called a card defect.

The verdict **always** lists these iterations in `completed_before_old`. A completed-before row
that reads NEW is a lawful late miss. **PM's P4** decides whether a non-empty
`completed_before_old` fails the run. Hardware recommends **fail closed**: report every case as a
run-integrity FAIL and have its row reviewed before anyone draws a card conclusion. Until PM rules,
Verification can bind everything else and leave the PASS consequence of this one list unbound.

## 6. Verdict

| Field | Meaning |
|---|---|
| `method`, `run_id`, `plan_digest` | From the plan |
| `card_model`, `card_unit`, `firmware_build`, `t_sched_us` | From the plan, confirmed by the rows (V2, V3) |
| `card_cid` | The single non-null CID seen on validated rows, or `null` if none was read. Under option B, `cid_disagreements` lists the conflicts |
| `bus_mode`, `sck_hz` | One value each across validated rows, else a problem |
| `qualification_scope` | `"spi-characterisation"` |
| `planned_attempts`, `reported`, `qualifying`, `required_qualifying`, `non_qualifying` | As today |
| `verdicts`, `verdicts_non_qualifying`, `torn_iterations`, `corrupt_iterations`, `neighbour_damage`, `damage_on_non_qualifying` | As today, over all validated rows |
| `completed_before_old` | §5 |
| `vcard_off_mv_max`, `sample_to_cut_us_max` | Largest values over validated rows, for the MICHAEL-CHECKS entry |
| `problems`, `verdict` | |

**PASS** only if there are no problems, no TORN, no CORRUPT, no neighbour damage, at least 1,000
qualifying rows, one card unit, one build, and **[P4]** `completed_before_old` empty if PM adopts
fail-closed.

## 7. Serial log, build and MICHAEL-CHECKS linkage

- **Build record.** For each build, the host writes `build.json`:
  `{"firmware_build": 40 hex, "hex_sha256": 64 hex of the exact .hex flashed}`. The firmware
  can't hash its own image, so the binary is linked by this file. The source commit is compiled in.
- **Serial grammar.** UTF-8 lines ending in `\n`. A capture may add `\r` before the `\n`; the host
  strips one trailing `\r`.
  - At boot the firmware prints exactly one line `BUILD {"firmware_build": …, "timer": string,
    "timer_hz": positive integer}`.
  - Then one `ATOM {row}` line per attempt.
  - No other line may begin with `BUILD ` or `ATOM `.
- **Normalisation, the only transformation allowed.** `run.jsonl` is every line of `serial.log`
  that begins with exactly `ATOM `, in order, with those five bytes removed and `\n` endings. The
  `firmware_build` in the `BUILD` line, in every row, in the plan and in `build.json` must all be
  equal. Verification can recompute `run.jsonl` from `serial.log` byte for byte.
- **MICHAEL-CHECKS entry.** Date, `firmware_build`, `hex_sha256`, card unit label, `plan_digest`,
  SHA-256 of `serial.log`, `run.jsonl` and `verdict.json`, the verdict's `qualifying`,
  `vcard_off_mv_max` and `sample_to_cut_us_max`, and Michael's note. The judge doesn't read
  MICHAEL-CHECKS. Verification checks that the entry's hashes match the files and that the files'
  build matches the entry.

This firmware is a characterisation tool under `hardware/characterisation/`, not product firmware.
Software's F3/F4 serial declaration (`tests/wp17_hands_on_r1` binding) is separate and isn't
constrained by this.

## 8. What stays the same

- Plan v3 and v4, the rig-r2 predicate, manifest loader and `completed_write_reverted`.
- Every imported package (V380, V382, rig_records_r1, V388, V390, V392) and their byte identity.
- The fixed 1,000 minimum, keep-every-row, classification of every validated row, and torn as a
  format blocker.
- No retired requirement is reinstated: rail traces, calibrated instruments, an external timebase,
  U, a manifest or a mandatory CID.

## 9. Order from here

1. PM disposes P3, P4 and the SPI scope (PM #669).
2. Verification publishes bound tests for this declaration, with the P3/P4 parts per PM's ruling.
3. Software or Hardware imports them unchanged, then implements the v5 route in
   `media_atomicity.py` in a separate later commit.
4. Verification reviews the exact head.

The self-run firmware and the host script are written after step 4. N3–N5 run on the bench only
after Michael approves the parts.
