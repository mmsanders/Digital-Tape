# WP-17 bench evidence: interface declaration (BE1-IF/2)

**Software Lead declaration for #652 (P3-R2-SW), 2 November 2026.** This is the public
schema, transcript grammar, CLI and report contract that
[BE-1](WP17-BENCH-EVIDENCE.md) asks Software to declare before implementing the
offline checker. Verification may author expectations from this document and BE-1. No
checker code, private test or fixture comes with it. Normative authority stays with
BE-1 and FW-1; where this declaration is narrower, it narrows the kit's behaviour,
not those documents. A change after Verification publishes is a new version
(`BE1-IF/3`), returned to the pair issue, not a silent edit.

**Version history.** `BE1-IF/1` (5808fddf) refused a physical session that held
`simulated` observations. `BE1-IF/2` admits that mixed bundle so that each
observation keeps its own provenance, matching V380 `BE1-EXPECTATIONS.md`
(d23a90f7). Simulation can still never make `physical_run` or `complete` true.
It also states when the already-listed `simulated_not_physical` code is reported.

Firmware behaviour is unchanged. The grammar below is exactly what the integrated FW-1
firmware (`aa472667`, `firmware/bench/src/main.cpp`) prints today. No new serial hook is declared.

## 1. Command line

```
python firmware/bench/tools/bench_evidence.py --offline BUNDLE --out REPORT.json [--golden DIR]
```

| Argument | Meaning |
|---|---|
| `--offline BUNDLE` | Required. A directory holding `manifest.json` and the files it declares. The only mode; there is no online mode. |
| `--out REPORT.json` | Required. The report path. It must not be inside `BUNDLE`. |
| `--golden DIR` | The WP-11 reference package. Default: `tests/golden` of the repository containing the script. `DIR/SHA256SUMS` is authenticated against `DIR/MANIFEST` and `DIR/ref/*.wav` before use. |

**Side effects:** none besides writing `--out`.
- The checker never opens a serial port, USB, block device or network socket, and never flashes or provisions.
- It never imports `serial`.
- It opens bundle files read-only and never writes, renames or deletes anything in `BUNDLE`.

**Exit status:**

| Code | When |
|---|---|
| 0 | No `INVALID` or `MISMATCH` anywhere in the report, including incomplete `NOT_RUN` results |
| 1 | At least one `MISMATCH` and no `INVALID` |
| 2 | At least one `INVALID` |
| 64 | Usage error: missing or unknown argument, `BUNDLE` not a directory, `--out` inside `BUNDLE`, or an unreadable `--golden`. No report is written. |

A bundle that exists but has a missing or unparseable `manifest.json` is not a usage
error. It gets a report with overall `INVALID` and exit 2.

## 2. Bundle and manifest (`digital-tape/be1-session/1`)

`BUNDLE/manifest.json` is UTF-8 JSON. Unknown top-level or object keys are `INVALID`
(`field_unknown`), so a misspelt field cannot silently drop a check.

```json
{
  "schema": "digital-tape/be1-session/1",
  "session": {
    "id": "string",
    "kind": "physical | simulation",
    "timestamp": "RFC 3339 with offset",
    "operator": "string",
    "witness": "string | null",
    "capture_tool": {"name": "string", "version": "string"}
  },
  "candidate": {
    "product_commit": "40 lowercase hex",
    "engine_tree": "40 lowercase hex",
    "firmware_hex_sha256": "64 lowercase hex",
    "toolchain": {
      "platformio": "6.1.19",
      "platform": "platformio/teensy@6.0.0",
      "framework": "platformio/framework-arduinoteensy@1.162.0",
      "uploader": "platformio/tool-teensy@1.162.0",
      "compiler": "platformio/toolchain-gccarmnoneeabi-teensy@1.150201.0"
    }
  },
  "target": {"board": "string", "board_revision": "string | null", "audio_board": "string | null"},
  "requested": ["F1", "F2", "F5"],
  "files": [{"path": "relative/posix", "sha256": "64 lowercase hex", "bytes": 0, "release_asset": "URL | absent"}],
  "observations": []
}
```

### Candidate rules
- `engine_tree` must be `d96b4245e04d74078f8938744b1394c3018516f7`.
- `toolchain` must equal the five pins above, which are this kit version's copy of `firmware/bench/platformio.ini` and `tools/requirements.txt`.
- Either difference is a `MISMATCH` (`engine_tree_mismatch`, `toolchain_mismatch`).
- The manifest has exactly one candidate. Every other identity in the bundle must agree with it:
  - a file with role `firmware_hex`;
  - the `firmware.hex` line of an F2 `sha256sums` file.
- Disagreement is a `MISMATCH` (`candidate_conflict`).

### File rules
- **Paths:** each `path` is relative and POSIX, with no `..`, no leading `/`, no drive letter and no backslash. A violation is `INVALID` (`path_unsafe`).
- **Must be declared:** every regular file under `BUNDLE` other than `manifest.json` must be listed. An undeclared file is `INVALID` (`file_unlisted`): a raw attempt may not sit in the bundle unaccounted for.
- **Must exist:** a listed file that is absent is `INVALID` (`file_missing`).
- **Must match:** a SHA-256 that differs is `MISMATCH` (`file_digest_mismatch`), as is a byte count that differs (`file_size_mismatch`).
- **Release assets:** `release_asset` records the evidence-policy location of a file over 1 MiB. The checker still requires the bytes locally and never fetches them.
- **References:** every file named by an observation must be listed.

**`requested`** is a non-empty subset of `F1`…`F5` with no duplicates; otherwise `INVALID`. The first-session set is `F1`, `F2`, `F5`. A request that omits any of them can never be `complete` (`requested_missing_first_session`). F3 and F4 can be requested, but they always remain `NOT_RUN` (§4).

### Observations
Every observation has:

| Field | Rule |
|---|---|
| `id` | Unique string |
| `criterion` | `F1`…`F5` |
| `provenance` | `actual`, `simulated` or `not_run` |
| `sequence` | Integer, unique in the session, in capture order |
| `superseded_by` | Optional id of a later observation of the same criterion (and, for F1, the same `case`), with a larger `sequence` |
| `supersede_reason` | Required when `superseded_by` is present |
| `note` | Optional free text, never evaluated |

**Provenance rules.** Each violation is `INVALID` (`provenance_conflict`), except a witness on a simulation, which is `witness_on_simulation`.
- A `simulation` session holds only `simulated` and `not_run` observations.
- A `physical` session may hold `actual`, `simulated` and `not_run` observations. Each keeps its own provenance in the report, and only `actual` observations can decide `complete`.
- A `simulated` observation, and every observation in a simulation session, carries no witness. That means a `null` session witness and no F5 `witness` object.
- A `not_run` observation has exactly `id`, `criterion`, `provenance`, `sequence` and `reason`, and references no file.

**Bad links.** A broken `superseded_by` is `INVALID` (`supersede_invalid`): a dangling id, a different criterion or case, a smaller sequence, or a cycle. So is a duplicate id or sequence (`sequence_invalid`).

#### F1 observation
| Field | Rule |
|---|---|
| `case` | One of the seven: `play-1x-quiet`, `play-1x-fortissimo`, `splice`, `overdub`, `overwrite`, `reset-b`, `promote`. Anything else is `INVALID` (`f1_case_unknown`). Scrub cases are not F1. |
| `mode` | `golden`, `stream` or `live` |
| `command` | The exact line sent, without the line terminator |
| `reference_wav_sha256` | SHA-256 of the whole reference WAV used |
| `transcript` | Bundle path: every byte received from the device after the command was sent, unmodified |

#### F2 observation
| Field | Rule |
|---|---|
| `size_gate` | Bundle path: the `size-gate.txt` from the CI artifact `wp17-firmware-teensy41` for the candidate |
| `sha256sums` | Bundle path: that artifact's `SHA256SUMS` |
| `transcript` | Bundle path, or `null`: every byte received after sending `info` |

A `null` transcript leaves the target half `NOT_RUN`.

#### F5 observation
| Field | Rule |
|---|---|
| `transcript` | Bundle path: every byte received over the Play/Stop/removal session, with no command sent |
| `witness` | `{"name": "string", "statement": "string", "present_for": ["play_stop", "removal", "verify"]}`, or `null` |
| `card_before`, `card_after` | `{"manufacturer", "part_number", "capacity_bytes", "revision", "cid"}`. `cid` is `null` when unknown; other values are strings, except `capacity_bytes`, an integer. Or the whole object is `null`. |
| `verify_command` | The exact `tapectl verify` command line run by hand |
| `verify_stdout` | Bundle path: its standard output |
| `verify_exit` | Its integer exit status |

The three `verify_*` fields may all be `null`; if one is `null`, all must be.

#### F3 and F4 observations
F3 and F4 observations may appear with any schema-valid provenance. They are
reported but never evaluated (§4).

## 3. Serial transcript grammar

A transcript is the device's raw output. It is text lines, plus one binary region in
`stream` mode.

- **Line ends:** each text line ends in `\r\n` (Arduino `println`); a bare `\n` is also accepted.
- **Bytes:** ASCII only.
- **Incomplete last line:** a final line without a terminator is `INVALID` (`transcript_truncated`).
- **Unknown lines:** a line that matches none of the forms below is `INVALID` (`line_unknown`).

`<u>` is an unsigned decimal, `<i>` a signed decimal and `<hex64>` 64 lowercase hex digits. Separators are single spaces.

| Line | Printed when |
|---|---|
| `DIGITAL-TAPE BENCH WP-17` | Boot banner |
| `FATAL instance <u> > reserve <u>` | Boot refusal: the actual instance exceeds the reserve |
| `CARD MOUNTED side <A\|B> frames <u> label <text>` | Card admitted and mounted; `<text>` is the rest of the line and may be empty |
| `CARD REFUSED IO` / `CARD REFUSED NOT_PROVISIONED` / `CARD REFUSED MOUNT <i>` | Card not admitted, or mount failed |
| `UNMOUNT <i>` | Best-effort unmount while dropping a card |
| `CARD GONE removed` / `CARD GONE service failed` / `CARD GONE refused card` | Card dropped |
| `PLAY <i>` / `PLAY FAILED <i>` | Play button result |
| `STOP <i>` then `POSITION <u>` | Stop button result and the kept frame position |
| `END OF SIDE` | Play reached the end of the side |
| `RENDER FAILED` | The audio-interrupt render reported an error |
| `INFO state <i> instance <u> reserve <u> card_blocks <u> p2_base <u> p2_blocks <u> stack_high_water <u> underruns <u>` | `info` reply. `instance` is the actual `tape_instance_size()`; `stack_high_water` is in bytes. |
| `ERR usage or no mounted card` / `ERR side <i>` / `ERR unknown command` | Command refused |
| `PCM` | Start of the stream binary region (below) |
| `UNDERRUNS <u>` | `live` reply, before its digest line |
| `SHA256 <hex64> FRAMES <u> RESULT <i>` | Digest line ending a `golden`, `stream` or `live` reply |

**Stream binary region.** It follows `PCM\r\n` and is a sequence of runs:
- Each run is a little-endian u32 frame count `n`, followed by `n × 4` bytes of interleaved stereo s16le PCM.
- A run with `n = 0`, and no data, ends the region.
- The digest line follows it.
- Bytes that end inside a run or before the terminator are `INVALID` (`transcript_truncated`).

`<i>` result values are engine `tape_result` codes; 0 is `TAPE_OK`.

## 4. Judgements

Each observation and each criterion gets a state, and each carries a list of reason codes from §5.

### State definitions
| State | Meaning |
|---|---|
| `INVALID` | The evidence does not conform to the schema, the grammar or the capture protocol: it is malformed, truncated, unsafe, undeclared, out of order, or carries contradictory provenance markers |
| `MISMATCH` | The evidence conforms, but its values contradict the reference, a limit, the candidate, a file digest, or other evidence |
| `NOT_RUN` | No observation, a declared `not_run`, or an observation missing data the criterion needs |
| `CONSISTENT` | Every check of the criterion holds. This is artifact consistency, never target acceptance or PASS. |

A `simulated` observation is judged by the same checks and always carries
`simulated_not_physical`. It never makes `physical_run` or `complete` true, and in a
mixed physical session it cannot stand in for an `actual` observation.

### F1 target
The checker reads the reference first:
- It reads `--golden` `MANIFEST` and `SHA256SUMS`.
- The case's reference is `ref/<case>.wav`, authenticated by `SHA256SUMS`.
- The reference payload is that WAV's `data` chunk bytes, never the whole file.
- The expected frame count is the payload length ÷ 4.

The case's last MANIFEST step gives the expected command:

| Last step | `golden` / `stream` command | `live` command |
|---|---|---|
| `play --side S --from F --frames N --rate 1` | `golden\|stream S F N` | `live S F` |
| `dump --side S` | `golden\|stream S 0 0` | `live S 0` |

One observation is `CONSISTENT` only if all of these hold:

| Check | Otherwise |
|---|---|
| `reference_wav_sha256` equals the `SHA256SUMS` entry for `ref/<case>.wav` | `MISMATCH` `f1_reference_mismatch` |
| `command` equals the expected line, byte for byte | `MISMATCH` `f1_command_mismatch` |
| The transcript parses (§3) and holds exactly one digest line, which is its last line; `stream` has exactly one binary region; `live` has exactly one `UNDERRUNS` line, immediately before the digest | `INVALID` `transcript_malformed`, or `transcript_truncated` (as §3 defines it) |
| `RESULT 0` | `MISMATCH` `f1_result_error` |
| `FRAMES` equals the expected frame count | `MISMATCH` `f1_frames_mismatch` |
| The digest equals SHA-256 of the reference payload | `MISMATCH` `f1_digest_mismatch` |
| `stream`: the concatenated run bytes equal the reference payload | `MISMATCH` `f1_stream_mismatch`, and the report gives the first differing frame |
| `stream`: SHA-256 of the run bytes equals the device's own digest | `MISMATCH` `f1_stream_digest_conflict` |
| `stream`: total run frames equal `FRAMES` | `MISMATCH` `f1_stream_digest_conflict` |
| `live`: `UNDERRUNS 0` | `MISMATCH` `f1_underruns` |

**Criterion state:** `CONSISTENT` when each of the seven cases has at least one observation that is not superseded and is `CONSISTENT`, and no observation that is not superseded is `INVALID` or `MISMATCH`.
- A case with no observation gives `NOT_RUN` (`f1_case_missing`).
- Otherwise the worst state among the observations that are not superseded applies.
- A digest result does not observe I²S or analogue output; the report says so in a fixed `scope` string.

### F2 target
- **`size_gate`:**
  - Must contain the `engine .data`, `engine .bss`, `engine COMMON`, `instance`, `RAM` and `engine .rodata` lines exactly as `tools/size_gate.py` prints them, and `PASS  both budgets`. Otherwise it is `INVALID` (`f2_static_malformed`) or `MISMATCH` (`f2_static_fail`).
  - RAM must equal .data + .bss + COMMON + instance; otherwise `MISMATCH` (`f2_ram_sum_mismatch`).
  - RAM must be ≤ 204800 and .rodata ≤ 32768; otherwise `MISMATCH` (`f2_static_fail`).
- **`sha256sums`:** its `firmware.hex` entry must equal `candidate.firmware_hex_sha256`; otherwise `MISMATCH` (`candidate_conflict`).
- **Target transcript:** `null` gives `NOT_RUN` (`f2_stack_missing`). Otherwise the last `INFO` line is used:

  | Check | Otherwise |
  |---|---|
  | An `INFO` line is present | `INVALID` `transcript_malformed` |
  | No `FATAL` line | `MISMATCH` `f2_fatal` |
  | `reserve` equals the static `instance` term | `MISMATCH` `f2_reserve_mismatch` |
  | `instance` ≤ `reserve` | `MISMATCH` `f2_instance_exceeds_reserve` |
  | `stack_high_water` is greater than 0 and a multiple of 4 | `INVALID` `f2_stack_invalid`. Zero is impossible on a running target; it is never a default. |
  | `stack_high_water` ≤ 8192 | `MISMATCH` `f2_stack_exceeds` |
  | The F2 `sequence` is greater than every `actual` or `simulated` F1 and F5 observation in the session, so the stack was sampled after the workloads | `INVALID` `f2_stack_before_workload` |

- **Measured values:** the report gives `instance`, `reserve`, `stack_high_water`, `ram` and `rodata`. A value that was not observed is `null`, never 0 and never inferred from the map.

### F5
Each F5 observation is checked in this order. The first problem decides its state.

1. **Missing data.** `transcript` must be present. Otherwise `NOT_RUN` (`f5_transcript_missing`).
2. **Required sequence of lines.** Other lines of the §3 vocabulary may sit between them. A missing line gives `NOT_RUN` (`f5_sequence_missing`).
   1. `CARD MOUNTED side A …`
   2. `PLAY 0`
   3. `STOP 0`, then `POSITION p1`
   4. `PLAY 0`
   5. `STOP 0`, then `POSITION p2`
   6. `PLAY 0`
   7. Optionally `UNMOUNT <i>`, then `CARD GONE removed` or `CARD GONE service failed`
3. **Line values:**
   - `0 < p1 < p2` is required. Otherwise `MISMATCH` (`f5_position_not_increasing`): the position was not kept across Stop/Play.
   - No `STOP` or `END OF SIDE` may come between the last `PLAY 0` and `CARD GONE`. Otherwise `MISMATCH` (`f5_removal_not_mid_play`).
   - No `PLAY FAILED` or `RENDER FAILED` may appear anywhere. Otherwise `MISMATCH` (`f5_play_failed`).
4. **Witness:** it must be non-null, and `present_for` must contain all three entries. Otherwise `NOT_RUN` (`f5_witness_missing`). On a simulation it is `INVALID` (§2).
5. **Card identity:** `card_before` and `card_after` must both be non-null; otherwise `NOT_RUN` (`f5_card_identity_missing`). They must be field-for-field equal; otherwise `MISMATCH` (`f5_card_identity_changed`). A `null` CID on both sides is allowed and reported (`f5_cid_unknown`); it never claims WP-05 identity.
6. **Manual verify:**
   - The `verify_*` fields must be non-null; otherwise `NOT_RUN` (`f5_verify_missing`).
   - `verify_stdout` must consist only of `tapectl verify` lines:
     - `OK`
     - `MBR_LAYOUT`
     - `PARTITION_TYPE`
     - `PARTITION_TRUNCATED`
     - `MOUNT <NAME>`
     - `NEEDS_REPAIR`
     - `SIDE_B_DEGRADED`
     - `READ_ERROR SIDE <A|B> FRAME <u>`

     Otherwise `INVALID` (`f5_verify_malformed`).
   - `CONSISTENT` requires stdout to be exactly `OK` and `verify_exit` to be 0. Any finding, or a nonzero exit, is `MISMATCH` (`f5_verify_findings`).
   - An `OK` stdout with a nonzero exit, or findings with exit 0, is also `MISMATCH` (`f5_verify_findings`).

**Criterion state:** the worst state among the observations that are not superseded, or `NOT_RUN` when there are none.
- The report states that a transcript check does not establish a safe physical removal or card preservation.

### F3 and F4
- **F3:** always `NOT_RUN` (`f3_method_pending`): there is no dedicated witnessed timing method yet.
- **F4:** always `NOT_RUN` (`f4_deferred`): it belongs to WP-18/19.
- Observations of either are listed but not evaluated, and never change the exit status.

### Precedence and summary flags
- **Precedence:** `INVALID` > `MISMATCH` > `NOT_RUN` > `CONSISTENT`.
- **Superseded observations:** still checked and listed, but they do not decide their criterion. Their failures appear in `criteria.Fx.superseded_failures`.
- **What exit status counts** (§1), whether or not the criterion is requested:
  - manifest problems;
  - file problems;
  - candidate and identity problems;
  - provenance problems;
  - the state of any criterion evaluated.
- **`overall`:** the worst of manifest, file and candidate checks and the requested criteria's states.
- **`physical_run`:** true only when `session.kind` is `physical` and at least one observation is `actual`.
- **`complete`:** true only when all of these hold:
  - `physical_run` is true;
  - `requested` contains F1, F2 and F5 and nothing else;
  - every requested criterion is `CONSISTENT`, and is decided only by `actual` observations;
  - `overall` is `CONSISTENT`.

  `complete` describes the requested observation set only. It never means package acceptance.

## 5. Report (`digital-tape/be1-report/1`)

```json
{
  "schema": "digital-tape/be1-report/1",
  "tool": {"name": "bench_evidence.py", "version": "BE1-IF/2", "sha256": "<script bytes>"},
  "bundle": {"path": "<as given>", "manifest_sha256": "<hex>"},
  "golden": {"sha256sums_sha256": "<hex>", "manifest_sha256": "<hex>"},
  "candidate": {"…": "copied from the manifest"},
  "session": {"id": "…", "kind": "physical | simulation"},
  "requested": ["F1", "F2", "F5"],
  "overall": "CONSISTENT | MISMATCH | INVALID | NOT_RUN",
  "physical_run": false,
  "complete": false,
  "reasons": ["manifest-, file- and candidate-level codes"],
  "files": [{"path": "…", "sha256": "<measured>", "declared_sha256": "…", "state": "…", "reasons": []}],
  "observations": [{"id": "…", "criterion": "F1", "provenance": "…", "state": "…", "reasons": [], "superseded_by": null}],
  "criteria": {
    "F1": {"state": "…", "reasons": [], "observations": [], "superseded_failures": [], "cases": {"play-1x-quiet": "…"}, "scope": "…"},
    "F2": {"state": "…", "reasons": [], "observations": [], "superseded_failures": [], "measured": {"instance": null, "reserve": null, "stack_high_water": null, "ram": null, "rodata": null}},
    "F3": {"state": "NOT_RUN", "reasons": ["f3_method_pending"]},
    "F4": {"state": "NOT_RUN", "reasons": ["f4_deferred"]},
    "F5": {"state": "…", "reasons": [], "observations": [], "superseded_failures": [], "scope": "…"}
  }
}
```

**Report format:**
- The report is UTF-8 JSON with sorted keys.
- Apart from `bundle.path` it is a pure function of the bundle bytes, the `--golden` bytes and the tool bytes. It contains no wall-clock time.
- All five criteria are always present.
- Reasons are listed in the order the checks run. Tests may assert any listed code; codes are never removed within a declaration version.

**Reason codes:**

| Group | Codes |
|---|---|
| Manifest | `manifest_missing`, `manifest_unreadable`, `schema_unknown`, `field_missing`, `field_type`, `field_unknown`, `requested_invalid`, `requested_missing_first_session` |
| Files | `path_unsafe`, `file_missing`, `file_unlisted`, `file_digest_mismatch`, `file_size_mismatch` |
| Identity | `candidate_conflict`, `toolchain_mismatch`, `engine_tree_mismatch` |
| Provenance and ordering | `provenance_conflict`, `witness_on_simulation`, `sequence_invalid`, `supersede_invalid`, `not_run_declared`, `observation_absent`, `simulated_not_physical` |
| Transcript | `transcript_malformed`, `transcript_truncated`, `line_unknown` |
| F1 | `f1_case_unknown`, `f1_case_missing`, `f1_reference_mismatch`, `f1_command_mismatch`, `f1_result_error`, `f1_frames_mismatch`, `f1_digest_mismatch`, `f1_stream_mismatch`, `f1_stream_digest_conflict`, `f1_underruns` |
| F2 | `f2_static_malformed`, `f2_static_fail`, `f2_ram_sum_mismatch`, `f2_reserve_mismatch`, `f2_instance_exceeds_reserve`, `f2_fatal`, `f2_stack_missing`, `f2_stack_invalid`, `f2_stack_exceeds`, `f2_stack_before_workload` |
| F5 | `f5_transcript_missing`, `f5_sequence_missing`, `f5_position_not_increasing`, `f5_removal_not_mid_play`, `f5_play_failed`, `f5_witness_missing`, `f5_card_identity_missing`, `f5_card_identity_changed`, `f5_cid_unknown`, `f5_verify_missing`, `f5_verify_malformed`, `f5_verify_findings` |
| F3 and F4 | `f3_method_pending`, `f4_deferred` |

## 6. Capture side (declared for the packet; not run in this task)

**`firmware/bench/tools/bench_capture.py`** is the raw capture tool the packet will use.

```
bench_capture.py --port PORT --out FILE [--send LINE] [--until-digest | --until-interrupt] [--timeout S]
```

- **Behaviour:** it writes every byte received after `--send` to `FILE`, unmodified, and prints the exact sent line for the manifest's `command`.
- **Name and version:** it records its own name and version for `session.capture_tool`.
- **Stopping:** `--until-digest` stops after the first `SHA256 …` line, so it works for F1 and is harmless for `info`. `--until-interrupt` runs until the operator stops it, for the F5 session.
- **Safety:** it never writes a card, flashes or provisions.

It needs pyserial and the bench, and is not part of the offline checker.

**`tools/golden_serial.py`** keeps its interface and stays a bench convenience. Its output is not evidence; only `bench_capture.py` files are.
