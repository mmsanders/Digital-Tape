# WP-17 F3 warm wake: additions F3-IF/2

**Software Lead declaration for [#674](https://github.com/mmsanders/Digital-Tape/issues/674),
10 November 2026.** F3-IF/2 is [F3-IF/1](WP17-F3-INTERFACE.md) plus the four slots that
V405's
[BINDING-GAPS.md](https://github.com/mmsanders/digital-tape-verification/blob/bff7453b73e2803e47d2e7535f1202650fac8fba/tests/f3_wake_if1_r1/BINDING-GAPS.md)
reserves (imported unchanged as `tests/f3_wake_if1_r1`, tree `9a42b494`).
- Nothing V405 already bound changes: the 22 wake-sim scenarios, the 43 single-build CLI
  vectors and the helper reuse keep their exact meaning.
- Each section below answers one gap, adds only what that gap needs, and names the
  F3-IF/1 rule it extends.
- No code comes with it. The F3-IF/1 text is unchanged.

## G1. Builds in a bundle (extends F3-IF/1 §4, §6)

**Root build.** The bound single-build layout stays exactly as it is:
- `BUNDLE/firmware.hex` and `BUNDLE/build.json` are required;
- `BUNDLE/firmware.elf` is optional;
- the manifest's `candidate` (`build_id`, `firmware_hex_sha256`) names this root build;
- the root build's `env` decides what it may hold:
  - root env `teensy41`: holds candidate observations;
  - root env `teensy41_ctl_wake150` (a control-only bundle): holds only `control_wake150`
    observations. A `candidate` observation on it is `MISMATCH control_build_as_candidate`,
    as bound.

**Additional builds.** Only for controls:
- An observation may carry one new optional key, `build`: a directory
  `builds/<name>/`, where `<name>` matches `[a-z0-9-]{1,32}`.
- That directory must hold `firmware.hex` and `build.json`, and may hold `firmware.elf`.
- An observation without `build` uses the root build.

**Rules.** Each violation is `INVALID` with the named reason, except where `MISMATCH` is
stated.
- `build` is allowed only on `kind: control_wake150`. On a `candidate` it is
  `build_not_root`: **a bundle has exactly one candidate build, the root.**
  - A rebuild of the same commit has a new `id` (F3-IF/1 §4), so it is a different
    candidate and goes in its own bundle.
- Every directory under `builds/` must be cited by at least one observation
  (`build_unused`), and must contain `build.json` and `firmware.hex` (`build_incomplete`).
- No two builds in the bundle, the root included, may share an `id` (`build_duplicate`).
- Every file in `builds/` is a normal `files` entry under the existing closed file rules.
- F3-IF/1 §4 linkage applies to each build separately:
  - `firmware.hex` hash equals its `build.json`;
  - its decoded marker appears once and equals its `build.json`;
  - every `BUILD`/`WAKE` id in the capture equals **its** build's `id`.
  - A capture whose ids name a different build than the observation cites is
    `MISMATCH build_id_mismatch`.
- A `control_wake150` observation must cite a build with env `teensy41_ctl_wake150` and
  `inject_us 150000`, whether root or under `builds/`. Otherwise it is
  `MISMATCH control_env_mismatch`.

## G2. Report, states and precedence (extends F3-IF/1 §6)

The manifest has **no `requested` key**. Its closed key set stays exactly `schema`,
`session`, `candidate`, `files` and `observations`. F3 is always the subject, and F4 is
always reported `NOT_RUN f4_deferred`.

**`not_run` observation shape.** Exactly `id`, `sequence`, `kind`, `provenance: "not_run"`
and `reason` (a non-empty string). It has no `capture`, `michael_check` or `build`.
Extra or missing keys are `INVALID field_unknown`/`field_missing`.

**Observation state.** Every check runs, and the state is the worst outcome, in this
precedence, worst first:

`INVALID` > `MISMATCH` > `NOT_ACCEPTABLE` > `PENDING_PM` > `NOT_RUN` > `CONTROL_DETECTED` > `CONSISTENT`

- `CONTROL_DETECTED` applies only to a `control_wake150` whose checks all hold.
- A candidate whose checks all hold is `CONSISTENT`. That includes a `simulated` candidate,
  which needs no record and carries `simulated_not_physical`.
- An `actual` candidate without a record is `NOT_RUN michael_check_absent`.

**F3 criterion state.**
- It is the worst state among non-superseded `candidate` observations.
- With none, it is `NOT_RUN no_candidate_observation`.
- Controls never decide it.

**`overall`.** The worst state across every observation, superseded ones included, and the
F3 criterion. A superseded `INVALID`/`MISMATCH` still counts (BE1-IF/3 §4 rule, unchanged).

**Exit status** (unchanged from F3-IF/1):
- 2: `overall` is `INVALID`/`MISMATCH`;
- 1: `overall` is `NOT_ACCEPTABLE`/`PENDING_PM`;
- 0: otherwise;
- 64: usage.

**`physical_run`.** True only when `session.kind` is `physical` and at least one
observation has `provenance: actual`.

**Report** `REPORT.json`, schema `digital-tape/f3-report/1`. Closed keys:

```json
{
  "schema": "digital-tape/f3-report/1",
  "checker": {"name": "f3_evidence.py", "interface": "F3-IF/2"},
  "manifest_sha256": "64 lowercase hex",
  "accepted": false,
  "physical_run": false,
  "overall": "STATE",
  "criteria": {
    "F3": {"state": "STATE", "reasons": ["code"], "target_met": true},
    "F4": {"state": "NOT_RUN", "reasons": ["f4_deferred"], "target_met": null}
  },
  "observations": [
    {"id": "string", "sequence": 1, "kind": "candidate | control_wake150",
     "provenance": "actual | simulated | not_run", "build_id": "hex32 | null",
     "state": "STATE", "reasons": ["code"], "elapsed_us": 0, "target_met": true,
     "superseded_by": null}
  ]
}
```

- `reasons` lists every failing check's code, sorted and unique. A `CONSISTENT` result
  lists only informational codes: `simulated_not_physical`, `cold_wake`.
- `elapsed_us` is the `WAKE` integer, or `null` when the capture has none.
- `target_met` is `elapsed_us < 100000`, or `null` when the capture has none. The criterion
  value is that of the observation that decided the state, or `null`.
- Observations are listed in `sequence` order.
- The BE-1 report (`digital-tape/be1-report/1`) is unchanged and still says F3
  `f3_method_pending`: this is a separate route.

## G3. Clock-change and fault input for `fwhost wake-sim` (extends F3-IF/1 §2, §10)

**New input.** Each `blocks` element may carry one optional key, `cpu_hz`: the clock the
firmware observes at that block. Absent means unchanged. A scenario with
`nonzero: true` and `engine_frames: 0`, an unknown key, or a non-integer value is a
usage error: exit 64, nothing printed.

**Evaluation.** Blocks are evaluated in order. For each block, with `dms` the modular
32-bit difference `ms − t0_ms`, the first rule that applies closes the measurement:
1. `mount != 0`: `mount_failed`. This is decided before any block is read.
2. The block's `cpu_hz` differs from the scenario's: `clock_changed`.
3. `dms ≥ 7000`: `wrap`.
4. `dms ≥ 2000`: `timeout`.
5. `nonzero` is true: `ok`.

If the blocks run out without closing, the result is `timeout`. Precedence when several
coincide is therefore:

`mount_failed` > `clock_changed` > `wrap` > `timeout` > `ok`

**Fields on a non-`ok` status:**
- `elapsed_us` and `cycles` print `-`;
- `cpu_hz` prints the scenario (`t0`) clock;
- `millis` prints `dms` of the closing block, or `0` for `mount_failed` and for running
  out of blocks;
- `engine_us` prints the first-engine-block value if one was seen before closing,
  otherwise `-`.
- `trigger`, `warm`, `mount`, `position`, `inject_us` and `id` always print their scenario
  values.

The firmware applies the same rules with real `F_CPU_ACTUAL`, `DWT->CYCCNT` and
`millis()`.

## G4. Build and ELF inspection boundary (extends F3-IF/1 §4, §5)

Three host tools, offline and pure Python. None opens a port or network, or flashes. Each
writes only its `--out` file, created exclusively (an existing file exits 64 untouched).

### `firmware/bench/tools/build_id.py`

The PlatformIO `pre:` script. It is also a CLI:

```
python build_id.py --describe --repo DIR --out FILE.json
```

- Writes `{"commit": "<hex40>", "dirty": 0|1}`.
- Computes them as in F3-IF/1 §4.1 (`git rev-parse HEAD`; `git status --porcelain`,
  ignoring `firmware/bench/.pio/`). These two `git` calls are its only subprocesses.
- Exit 0, or 3 if `DIR` is not a git work tree.
- The random `id` is generated only in the PlatformIO context, from `os.urandom(16)`.
  It is never derived from the describe output.

### `firmware/bench/tools/build_record.py`

The post-build step that writes `build.json`:

```
python build_record.py --hex FILE --elf FILE --id HEX32 --commit HEX40 --dirty 0|1 \
    --env NAME --inject-us N --engine-tree HEX40 --toolchain FILE.json --out build.json
```

- Writes exactly the F3-IF/1 §4.3 object (schema `digital-tape/fw-build/1`), with
  `firmware_hex_sha256`/`firmware_elf_sha256` computed from the given files.
- `--toolchain` is a JSON object holding the five BE1-IF/3 pins.
- Malformed values exit 64 without writing.
- It does not read the marker or the symbols; that is the inspector's job.

### `firmware/bench/tools/fw_build_inspect.py`

```
python fw_build_inspect.py --hex FILE --elf FILE --build-json FILE --out REPORT.json
```

**What it reads:**
- `firmware.hex`, decoded from Intel HEX (record types 00, 01, 02 and 04);
- the ELF symbol table, parsed directly: ELF32 little-endian, `.symtab` with its linked
  `.strtab`. It runs no `nm` or other subprocess.

**Checks**, all run:
- `sha256(hex)` and `sha256(elf)` equal `build.json`;
- the decoded image holds the `DTBUILD` marker exactly once, equal to `build.json`;
- `env`/`inject_us`/seam symbol agree:
  - `teensy41` requires `inject_us 0` and **no** symbol named `fw_wake_inject`;
  - `teensy41_ctl_wake150` requires `inject_us 150000` and that symbol present;
  - any other env is `unknown_env`.

**Report** `digital-tape/fw-build-inspect/1`:

```json
{"schema": "digital-tape/fw-build-inspect/1", "state": "CONSISTENT | MISMATCH | INVALID",
 "reasons": ["code"], "env": "string", "inject_us": 0, "hex_sha256": "hex64",
 "elf_sha256": "hex64", "marker": {"id": "hex32", "commit": "hex40", "dirty": 0, "env": "string",
 "inject_us": 0}, "seam_symbol_present": false, "accepted": false}
```

- `marker` is `null` when the marker is absent or duplicated.
- Exit 0 `CONSISTENT`, 2 `MISMATCH`/`INVALID`, 64 usage.
- Reasons:
  - `hex_hash_mismatch`, `elf_hash_mismatch`;
  - `marker_missing`, `marker_duplicate`, `marker_mismatch`;
  - `seam_present_in_production`, `seam_absent_in_control`;
  - `inject_mismatch`, `unknown_env`;
  - `hex_malformed`, `elf_malformed`.

**CI (firmware-bench).**
- Build `teensy41` and `teensy41_ctl_wake150`, and run the inspector on each; both must
  exit 0.
- **Negative control:** the production ELF and hex inspected with a `build.json` edited to
  claim `teensy41_ctl_wake150`/`150000` must exit 2 with `seam_absent_in_control` and
  `marker_mismatch`.
- No artifact is flashed.

## What stays reserved and held

- F4 stays reserved (F3-IF/1 §8).
- PM questions Q1–Q3 (F3-IF/1 §9) keep their safe defaults until PM decides.
- That a real target backend behaves like the host module still needs build evidence and
  actual target checks after parts arrive.
- No implementation lands until the binding of these slots is imported unchanged, before
  any `firmware/` change on this branch.
