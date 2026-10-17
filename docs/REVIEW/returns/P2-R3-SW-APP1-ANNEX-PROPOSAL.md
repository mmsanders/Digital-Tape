# P2-R3 Software return (#444): APP-1 §3 annex proposal, capability facts, slice plan

**Status: PROPOSAL from Software. This is not issued spec.** PM issues the annex (APP-1 §3,
ADR-183/184). Nothing here licenses app or §3 implementation. Dated 17 October 2026; like
every file under `docs/REVIEW/`, this is a snapshot.

**Bound inputs.**
- Product main `7b722dc`: APP-1 is `docs/WP15-APP-CONTRACT.md`, WP-14 is
  `docs/WP14-CLI-CONTRACT.md`, INGEST-1 is `docs/WP16-INGEST-CONTRACT.md`.
- Verification preflight `fe8f3bdf`: `findings/P2-R3-WP15-PREFLIGHT-2026-10-15.md` (P2V15-001…004).
- Ingest reason sites are read from the held INGEST-1 candidate `6126d04` (PR #436). This is the
  only ingest source; it is not on main. Appendix A is generated from it by
  `tools/app-annex/reason_map.py`. That script exits 1 on any unmapped site or unused ID, so a
  later candidate re-runs it, and it must stay green.

**Invariants the annex keeps.** With no `--report` and no new command:
- every existing command's stdout, stderr, exit code, audio bytes and manifest bytes are
  byte-unchanged;
- exit meanings never change: ingest 0/2/1, `tapectl` 0/1/2/3;
- an ID in a report is additive information keyed to an exit code, and it never overrides one.

stderr wording stays diagnostic. The app never parses it (APP §6, and the §7 control "stderr
wording changes leave the app result unchanged").

## Part 1. Annex proposal

### 1.1 Report file (common to `ingest`, `tapectl cards`, `tapectl make`)

**Flags.** `--report FILE --report-nonce N` are given together or not at all. Each may appear at
most once. N is exactly 32 lowercase hex digits; the app supplies 128 random bits. Any violation
is the tool's existing usage outcome: exit 2 for both tools, stderr only, and no file is created.

**Creation.** This is the first act after the command line parses, before any other validation or
I/O, so usage refusals of the *rest* of the command line are reported too.
- POSIX: `open(FILE, O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC, 0600)`.
- Windows: `CreateFileW(FILE, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL |
  FILE_FLAG_OPEN_REPARSE_POINT, NULL)`.
- An existing name of any kind fails, including a dangling symlink or a reparse point, and is never
  followed.
- On failure the tool exits 1 with `<tool>: report: cannot create FILE (<os error>)` on stderr and
  does no other work. That holds for ingest, cards and make alike.

**Lines.**
- Each record is one JSON object on one line, UTF-8, `\n`-terminated, with no insignificant
  whitespace and keys in the order shown below, so goldens are byte-stable.
- Integers are JSON integers; 64-bit values fit because no total exceeds 2⁵³.
- Each line is written with one `write`/`WriteFile` call and no flush requirement, because the
  file is diagnostic.

**Record order.** Exactly one `start` first. Then zero or more `progress`, then at most one
`refusal`, then exactly one `end` when the tool reaches its normal exit path. A crash or forced
kill may leave no `end`.

| `t` | Keys, in order | Notes |
|---|---|---|
| `start` | `t, tool, version, nonce` | `tool` ∈ `ingest`, `tapectl cards`, `tapectl make`; `version` is the binary's existing `--version` string (ingest) or build head (tapectl) |
| `progress` | `t, step, done, total` | §1.4 |
| `refusal` | `t, id, subject, …payload` | §1.2/§1.3; written immediately before `end` |
| `end` | `t, exit` | equals the process exit code |

**Later write failure.** If any write after `start` fails, the tool stops writing the report and
prints one stderr line, `<tool>: warning: report: cannot write FILE (<os error>)`. Its stdout,
outputs and exit code are what they would have been without `--report`; a published ingest stays
exit 0. The report then simply lacks `end`.

**App reading rules (closed).** The row choice is a function of (tool, exit code, report state,
ID).

| Report state | App uses |
|---|---|
| Absent, unreadable, empty | exit code only |
| First line not a complete `start`, or `tool` ≠ the tool launched, or `nonce` ≠ the nonce passed (**stale/foreign**) | exit code only; the file is ignored entirely |
| Any complete line that is not a JSON object, or has an unknown `t` (**malformed**) | exit code only |
| A final line without `\n` | that line is ignored; the rest is judged normally |
| `end` missing, or `end.exit` ≠ process exit (**inconsistent**) | exit code only |
| Well-formed, with a `refusal` whose `id` is not in the closed list for that tool and exit | exit code only |
| Well-formed, with a known `id` | the §1.5 row for (tool, exit, id) |

"Exit code only" means:
- ingest 0, or `make` 0, is success as today;
- every other exit is **Any other failure**;
- a `make` exit 1 without a usable report is therefore **not** shown as "pulled", because only the
  ID earns that row.

**Show details** always shows the child's raw stderr. For `make`, which runs elevated, see §2.4
F4: stdio of an elevated child is not capturable on Windows, so this proposal adds the record
`{"t":"stderr","text":S}` to `make` reports only. S is each complete stderr line as written, in
order, without its `\n`. It is diagnostic and never selects a row. **PM decision Q1.**

### 1.2 ingest IDs and subjects

**Subjects.**

| Kind | `subject` value | App displays |
|---|---|---|
| source | the INGEST-1 logical path, string `"<ordinal>/<NFC name>"` | the basename after the first `/` |
| folder | the ordinal as a decimal string, `"<ordinal>"` | the dropped folder's own name for that ordinal |
| boundary | a two-element array of the neighbouring source logical paths, `["0/a.flac","1/b.flac"]`; a gap boundary names the last source of one folder and the first of the next | the dropped folder name(s) of the ordinals |
| none | `null` | — |

INGEST-1 file names cannot contain `/` (check_name refuses `<>:"/\|?*` and controls), so the
first `/` splits ordinal from name unambiguously. When a raw entry name is not valid Unicode, there
is no NFC logical path and the subject is the folder (`FOLDER_NAME_NOT_UNICODE`).

**Closed list, exit 2 (refusals):**
- request: `INGEST_USAGE`, `INGEST_LENGTH_INVALID`, `INGEST_TOO_LONG`, `INGEST_RIFF_LIMIT`
- folder: `FOLDER_SYMLINK`, `FOLDER_UNREADABLE`, `FOLDER_NOT_FOLDER`, `FOLDER_DUPLICATE`,
  `FOLDER_EMPTY`, `FOLDER_NAME_COLLISION`, `FOLDER_NAME_NOT_UNICODE`
- entry: `ENTRY_SYMLINK`, `ENTRY_NESTED_FOLDER`, `ENTRY_NOT_REGULAR`, `ENTRY_NAME_INVALID`
- source: `SOURCE_PROTECTED`, `SOURCE_NOT_AUDIO`, `SOURCE_TOO_SHORT`, `SOURCE_CHANGED`,
  `SOURCE_NON_FINITE`, `SOURCE_LEVEL`, `SOURCE_TRIM_UNSUPPORTED`, `SOURCE_OUTSIDE_INGEST1`,
  `SOURCE_CORRUPT`
- boundary/whole: `JOIN_PEAK`, `JOINED_PEAK`
- destination: `DEST_EXISTS`, `DEST_APPEARED`, `DEST_NAME_INVALID`

**Closed list, exit 1 (I/O and internal):** `IO_SOURCE`, `IO_FOLDER`, `IO_DEST`, `IO_MEMORY`,
`INTERNAL`.

Appendix A maps every one of the 240 refusal/failure sites at `6126d04` to exactly one ID. A source
site refused for two reasons cannot occur: ingest stops at its first refusal, in INGEST-1 order.

**Payloads (closed).**
- `INGEST_TOO_LONG`: `total_frames, capacity_frames, excess_frames`, integers, gaps included
  (88 200 frames between folders), with `excess_frames = total_frames − capacity_frames ≥ 1`.
  The app shows `ceil(excess_frames / 44100)` seconds in WP-14 A7 phrasing: `M min S s`, omitting
  a zero part, and `S s` under a minute. Exact fit is not a refusal.
- `FOLDER_DUPLICATE`: `same_as`, the earlier ordinal as a decimal string. The subject is the later
  folder.
- `JOIN_PEAK`, `JOINED_PEAK`: `dbtp`, the existing six-decimal string.
- Every other ID has no payload keys.

### 1.3 `tapectl` IDs

**`tapectl cards`** (stdout grammar as APP §3; report for diagnosis only):

| Exit | `id` | When |
|---|---|---|
| 0 | — | enumeration ran (N ≥ 0); no refusal record |
| 1 | `CARDS_ENUM_UNAVAILABLE` | the OS disk enumeration itself failed; payload `os_error` (string) |
| 2 | `USAGE` | bad arguments |

Per-disk refusals and unprobed reasons are never recorded in the report: APP forbids listing
refused disks. Only the `unprobed` count leaves the tool.

**`tapectl make`.** The ID is the existing outcome, named by phase:

| Exit | `id` | Payload | Existing outcome it names |
|---|---|---|---|
| 2 | `USAGE` | — | `usage()` paths (bad/duplicate flags) |
| 2 | `LABEL_INVALID` | — | `--label must be 1 to 32 bytes of UTF-8` |
| 2 | `LENGTH_INVALID` | — | `bad --length-s` |
| 2 | `WAV_INVALID` | `reason` (closed: `open`, `riff`, `fmt`, `pcm`, `channels`, `rate`, `bits`, `align`, `data`, `chunk`) | `wav_open_read` failure, before any device open |
| 2 | `DEVICE_OPEN_FAILED` | `os_error` | `cannot open device … for writing` |
| 2 | `TOO_LONG` | `total_frames, capacity_frames, excess_frames` | load's capacity check (A7) |
| 2 | `WAV_TRUNCATED` | `phase:"load"` | truncated WAV data mid-feed (**after destructive start**) |
| 2 | `NOT_PROVISIONED` | — | WP-14 §2, for the load/verify phase (unreachable after a successful provision; listed for closure) |
| 2 | `P2_TOO_LARGE` | — | `target too large for partition 2` (unreachable under §5's 128 GiB cap; listed for closure) |
| 3 | `REFUSE_NOT_WHOLE_DEVICE` … `REFUSE_ERASE_NOT_CONFIRMED` | `unmount_failed:true` only on `REFUSE_FOREIGN_MOUNT` from a failed own-p1 unmount | WP-14 §5, the six IDs verbatim |
| 1 | `ENGINE` | `phase`, `result` | `engine_fail`: `phase` ∈ `provision`, `capacity`, `load`, `commit`; `result` is the `TAPE_ERR_*` name |
| 1 | `IO` | `phase`, `op` | provision `io_fail`: `op` ∈ `entropy`, `read_lba0`, `clear_lba0`, `write_p1`, `build_mbr`, `write_mbr`; verify `read_lba0` |
| 1 | `VERIFY_FINDINGS` | `findings` | verify printed ≥ 1 finding |
| 1 | `CARD_CHANGED` | `phase`, `os_error` | APP §3 continuity |

**Verify findings payload.** An array in exactly the WP-14 §4.1 stdout order, one element per
stdout line:
- `{"f":"MBR_LAYOUT"}`, `{"f":"PARTITION_TYPE"}`, `{"f":"PARTITION_TRUNCATED"}`;
- `{"f":"MOUNT","side":"A","result":"TAPE_ERR_…"}`, A before B;
- `{"f":"NEEDS_REPAIR"}`, `{"f":"SIDE_B_DEGRADED"}`;
- `{"f":"READ_ERROR","side":"A","frame":n}` by side, then frame.

**I/O precedence (one event that is both I/O and a finding).** These apply in order, and the first
that matches decides:
1. **CARD_CHANGED.** The failing native call returned a media-removal or media-change error from
   the platform list in §2.4 F3, or the phase-boundary continuity check (§2.4 F3) reports a
   change.
   - `make` stops at once and prints nothing further on stdout.
   - A verify already in progress prints no findings, so a pulled card never shows as
     `READ_ERROR`.
2. **Verify full read.** Any other non-OK result while reading frames is the `READ_ERROR SIDE x
   FRAME n` finding, exactly as `verify` does today.
3. **Verify mount.** A failing mount is the `MOUNT <TAPE_ERR_…>` finding, so an I/O failure while
   mounting is `MOUNT TAPE_ERR_IO`.
4. **Verify LBA 0.** A failed read of LBA 0 is `IO` `phase:"verify"` `op:"read_lba0"`, not a
   finding, as today.
5. **Provision.** `IO` with its `op`.
6. **Load/commit.** `ENGINE` with `result:"TAPE_ERR_IO"`.

Exit is 1 in every case, so the precedence only chooses the ID.

**`make` stdout.** The concatenation of the existing outputs in order: provision's
`uuid`/`epoch` lines, then load's (none), then verify's `OK` or findings. Report records are
additional and do not alter it.

### 1.4 Progress steps (closed)

| Tool | `step`, in order | Unit | `total` |
|---|---|---|---|
| ingest | `list` | folders listed | number of FOLDER arguments |
| ingest | `decode` | sources decoded (pass 1) | number of sources |
| ingest | `convert` | sources converted (pass 2) | number of sources |
| ingest | `write` | output bytes written to the stage WAV | 44 + 4·total_frames |
| ingest | `publish` | 0 → 1 | 1 |
| tapectl cards | `enumerate` | whole disks probed | disks found (0 until known) |
| tapectl make | `safety` | 0 → 1 | 1 |
| tapectl make | `provision` | WP-14 §3 stages done: clear LBA 0, partition 2, partition 1, MBR | 4 |
| tapectl make | `load` | frames fed | WAV frames (from its header) |
| tapectl make | `commit` | 0 → 1 | 0 (unknown) until done, then a final record `1/1` |
| tapectl make | `verify_a`, `verify_b` | frames rendered on that side | that side's `total_frames` once mounted, else 0 |

**Rules.**
- Steps appear in table order and each at most once per run of records.
- Within a step, `done` never decreases. `total` is either constant, or goes from 0 to one fixed
  value once.
- `0 ≤ done ≤ total` whenever `total > 0`.
- Emission is count-based, never clock-based: at step start, then whenever `done` crosses another
  1/64 of `total` (every 2²⁰ units when `total` = 0), and at step end.
- Any step, or all progress, may be absent. The app never infers success from progress.

**App bar weights for Making (Software's choice under APP §4).** `safety` 1, `provision` 4, `load`
60, `commit` 5, `verify_a` 15, `verify_b` 15. The bar is the running maximum and never goes
backwards. The length bar during "Checking the music…" is indeterminate, because its value comes
only from `total_frames` at exit 0.

### 1.5 Every §6 row → a child outcome or an app event

| §6 row | Source |
|---|---|
| † files or a mix dropped | app event `DROP_NOT_FOLDER` (zero child calls) |
| ingest: overage | ingest exit 2 `INGEST_TOO_LONG` (payload) |
| ingest: protected file | ingest exit 2 `SOURCE_PROTECTED` |
| ingest: unreadable/corrupt/unsupported | ingest exit 2 `SOURCE_CORRUPT`, `SOURCE_OUTSIDE_INGEST1`, `SOURCE_TRIM_UNSUPPORTED`, `SOURCE_LEVEL`, `SOURCE_NON_FINITE`; exit 1 `IO_SOURCE` |
| ingest: non-audio, nested, symlink, empty folder | ingest exit 2 `SOURCE_NOT_AUDIO`, `ENTRY_NOT_REGULAR`, `ENTRY_NESTED_FOLDER`, `ENTRY_SYMLINK`, `FOLDER_SYMLINK`, `FOLDER_EMPTY` (NAME is the subject's folder) |
| ingest: too short, collision, other source-named | ingest exit 2 `SOURCE_TOO_SHORT`, `SOURCE_CHANGED`, `ENTRY_NAME_INVALID`, `FOLDER_NAME_COLLISION`, `FOLDER_NAME_NOT_UNICODE` |
| Card too small | make exit 1 `ENGINE` `phase:"provision"` `result:"TAPE_ERR_GEOMETRY"`; make exit 2 `TOO_LONG` |
| Not offered / refused card | never reached: `cards` does not print refused disks |
| make: CARD_CHANGED or device I/O | make exit 1 `CARD_CHANGED`, `IO` (any op), `ENGINE` `result:"TAPE_ERR_IO"`; exit 2 `DEVICE_OPEN_FAILED`, `WAV_TRUNCATED`… see Q2 |
| verify finding | make exit 1 `VERIFY_FINDINGS` |
| † elevation declined | app event `ELEVATION_DECLINED` (no `make` child exists) |
| † card recheck mismatch | app event `CARD_RECHECK_MISMATCH` (steps 1 and 3) |
| † tool could not start | app event `SPAWN_FAILED` |
| Any other failure | everything else, including: `INGEST_USAGE`, `INGEST_LENGTH_INVALID`, `INGEST_RIFF_LIMIT`, `FOLDER_UNREADABLE`, `FOLDER_NOT_FOLDER`, `FOLDER_DUPLICATE`, `JOIN_PEAK`, `JOINED_PEAK`, `DEST_*`, `IO_FOLDER`, `IO_DEST`, `IO_MEMORY`, `INTERNAL`, `cards` exit 1, make `USAGE`, `LABEL_INVALID`, `LENGTH_INVALID`, `WAV_INVALID`, `NOT_PROVISIONED`, `P2_TOO_LARGE`, `ENGINE` with any other result, every make exit 3, an unknown ID, a stale, malformed or inconsistent report, and any exit outside the tool's set (crash or signal) |

**PM decisions this proposal needs.**
- **Q1.** The `stderr` record for `make` (§1.1). The safe default is to adopt it, because without
  it Show details is empty for the elevated child on Windows.
- **Q2.** `WAV_TRUNCATED` after the destructive start. The safe default is "Any other failure",
  since the card was not pulled. A different default would need a new §6 sentence.
- **Q3.** `JOIN_PEAK`/`JOINED_PEAK` have no §6 row; the default is "Any other failure". A row such
  as "These songs are too loud together" would be a taste item for Michael.
- **Q4.** `FOLDER_DUPLICATE` is reachable only if the app passes the same folder twice. The default
  is for the app to dedupe drops by OS identity before ingest; the row stays "Any other".
- **Q5.** make exit 3 after a passing recheck (a mount appeared, etc.); the default is "Any other
  failure". Zero writes holds per WP-14 §5.

### 1.6 Examples

All nonces below are `0123456789abcdef0123456789abcdef`; versions are elided as `V`.

**Exact fit** (one folder, total = 158 760 000 frames = 3600 s): exit 0, DEST published.
```
{"t":"start","tool":"ingest","version":"V","nonce":"0123456789abcdef0123456789abcdef"}
{"t":"progress","step":"list","done":1,"total":1}
{"t":"progress","step":"decode","done":12,"total":12}
{"t":"progress","step":"convert","done":12,"total":12}
{"t":"progress","step":"write","done":635040044,"total":635040044}
{"t":"progress","step":"publish","done":1,"total":1}
{"t":"end","exit":0}
```
**One frame over** (158 760 001): exit 2, no DEST or stage; the report is the only file created.
The app shows "1 s too long".
```
{"t":"start","tool":"ingest","version":"V","nonce":"0123456789abcdef0123456789abcdef"}
{"t":"progress","step":"list","done":1,"total":1}
{"t":"progress","step":"decode","done":12,"total":12}
{"t":"refusal","id":"INGEST_TOO_LONG","subject":null,"total_frames":158760001,"capacity_frames":158760000,"excess_frames":1}
{"t":"end","exit":2}
```
The same ID with excess 8 467 200 frames (two folders: 190 s of music over, plus their 2 s gap of
88 200 frames) shows "3 min 12 s too long". The equal-ID/different-excess control is these two lines.

**Source-named and boundary refusals.**
```
{"t":"refusal","id":"SOURCE_PROTECTED","subject":"1/Song 3.m4a"}
{"t":"refusal","id":"FOLDER_EMPTY","subject":"2"}
{"t":"refusal","id":"FOLDER_DUPLICATE","subject":"2","same_as":"0"}
{"t":"refusal","id":"JOIN_PEAK","subject":["0/10 End.flac","1/01 Start.flac"],"dbtp":"-0.412345"}
```
**Report-create failure** (FILE exists): no report is written, nothing else happens, exit 1, and
stderr is `ingest: report: cannot create /…/r.jsonl (File exists)`. The app has no usable report,
so it uses the exit code: **Any other failure**.

**Later write failure** (the disk fills after `start`): the ingest publication succeeds, exit 0,
stderr `ingest: warning: report: cannot write /…/r.jsonl (No space left on device)`. The report
ends without `end`, so it is *inconsistent*. The app uses exit 0 and DEST state: **success**.

**Unknown, malformed and stale reports.**
```
{"t":"start","tool":"tapectl make","version":"V","nonce":"ffffffffffffffffffffffffffffffff"}   <- stale: nonce ≠ passed; ignored
{"t":"start","tool":"tapectl make","version":"V","nonce":"0123…"}\n{"t":"refusal","id":"CARD_CHANGED"   <- unterminated last line ignored; no end → inconsistent → exit only
{"t":"start",…}\nnot json\n{"t":"end","exit":1}   <- malformed → exit only → Any other failure
{"t":"start",…}\n{"t":"refusal","id":"FUTURE_THING","subject":null}\n{"t":"end","exit":1}   <- unknown ID → Any other failure
```
**Native I/O failure after the destructive start** (the card is pulled during load). Stdout is the
provision lines only, and the exit is 1:
```
{"t":"start","tool":"tapectl make","version":"V","nonce":"0123456789abcdef0123456789abcdef"}
{"t":"progress","step":"safety","done":1,"total":1}
{"t":"progress","step":"provision","done":4,"total":4}
{"t":"progress","step":"load","done":2752512,"total":158760000}
{"t":"stderr","text":"tapectl: make: the card was removed or changed (ENXIO); stopping"}
{"t":"refusal","id":"CARD_CHANGED","subject":null,"phase":"load","os_error":"ENXIO"}
{"t":"end","exit":1}
```
If the same native call fails *without* a removal/change error (e.g. `EIO` on a present card), the
refusal is `{"t":"refusal","id":"ENGINE","subject":null,"phase":"load","result":"TAPE_ERR_IO"}`.
§6 shows the same pulled message, because the row covers both.

`subject` is always present: `null` for every `tapectl` ID, since disks are never named in a report.

<!-- CAPABILITY -->

## Appendix A. INGEST-1 site → ID map (generated, `6126d04`)

Generated by `python3 tools/app-annex/reason_map.py <6126d04>/host/ingest/src --markdown` (source tree `7ca28217827a2a139c97ec7d67bbdc0328eaf097`).
The stderr text is diagnostic and is shown only to make each site findable. Subject kinds and
§6 rows are the defaults in §1.2 and §1.5.

| ID | Exit | Subject | §6 row | Site | Current stderr text (diagnostic only) |
|---|---|---|---|---|---|
| `INGEST_LENGTH_INVALID` | 2 | none | other | `main.rs:143` | --length is too large |
| `INGEST_LENGTH_INVALID` | 2 | none | other | `main.rs:211` | total length overflows |
| `INGEST_LENGTH_INVALID` | 2 | none | other | `main.rs:215` | total length overflows |
| `FOLDER_SYMLINK` | 2 | folder | not-music | `order.rs:145` | {}: the folder is a symbolic link; symbolic links are not followed |
| `FOLDER_UNREADABLE` | 2 | folder | other | `order.rs:147` | {}: folder does not exist or cannot be read ({e}) |
| `FOLDER_NOT_FOLDER` | 2 | folder | other | `order.rs:149` | {}: not a folder |
| `FOLDER_DUPLICATE` | 2 | folder | other | `main.rs:152` | {}: folder {i} is the same folder as folder {j}; folders must be distinct |
| `FOLDER_EMPTY` | 2 | folder | not-music | `order.rs:119` | {disp}: the folder is empty |
| `FOLDER_NAME_COLLISION` | 2 | folder | source-named | `order.rs:127` | {disp}: '{}' and '{}' collide after Unicode normalization or case folding |
| `FOLDER_NAME_NOT_UNICODE` | 2 | folder | source-named | `order.rs:96` | {disp}: a file name is not valid Unicode ({}) |
| `ENTRY_SYMLINK` | 2 | source | not-music | `order.rs:104` | {disp}/{raw}: symbolic links are not followed; refusing |
| `ENTRY_NESTED_FOLDER` | 2 | source | not-music | `order.rs:107` | {disp}/{raw}: nested folders are not allowed; a source folder must hold only audio files |
| `ENTRY_NOT_REGULAR` | 2 | source | not-music | `order.rs:110` | {disp}/{raw}: not a regular file |
| `ENTRY_NAME_INVALID` | 2 | source | source-named | `order.rs:114` | {disp}/{raw}: the name {why} |
| `INTERNAL` | 1 | none | other | `common.rs:98` | internal: decoded plane length disagrees |
| `INTERNAL` | 1 | none | other | `convert.rs:133` | gain refinement did not converge in {MAX_ATTEMPTS} attempts |
| `INTERNAL` | 1 | none | other | `main.rs:249` | {}: internal: output length disagrees |
| `INTERNAL` | 1 | none | other | `mpeg.rs:322` | MP3 decoder init failed: {e} |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:34` | AAC AudioSpecificConfig is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:72` | AAC sampling-frequency index is reserved |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:146` | AAC decoder refused the stream configuration ({e}) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:160` | AAC access unit {i} does not decode ({s}) (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:164` | AAC access unit {i} decoded to an unexpected length or layout |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:169` | ADTS frame {i} CRC mismatch (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:188` | ADTS header is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:192` | ADTS sync lost (corrupt data or junk between frames) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:195` | ADTS layer field is not zero (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:208` | ADTS frame length is invalid or the last frame is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:229` | ADTS sampling-frequency index is reserved |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:259` | MP4 box header is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:267` | MP4 box header is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:272` | MP4 nested box with size 0 is invalid |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:276` | MP4 box '{}' runs past its parent (truncated) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:288` | MP4 has more than one '{}' box where one is allowed |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:294` | MP4 is missing its '{}' box |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:299` | MP4 box is too short (truncated) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:321` | MP4 esds descriptor runs past its box |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:330` | MP4 esds lacks an ES_Descriptor |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:348` | MP4 esds lacks a DecoderConfigDescriptor |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:362` | MP4 esds lacks a DecoderSpecificInfo (AudioSpecificConfig) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:416` | MP4 does not begin with an 'ftyp' box |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:474` | MP4 sample description is empty |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:538` | MP4 audio track has no 'stsz' sample-size table |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:541` | MP4 sample-size and time-to-sample tables disagree |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:556` | MP4 audio track has no chunk-offset table |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:570` | MP4 sample-to-chunk table names more samples than exist |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:572` | MP4 sample data runs past the end of the file (truncated) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `aac.rs:579` | MP4 sample-to-chunk table does not cover every sample |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:19` | FLAC frame is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:28` | FLAC frame is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:57` | FLAC frame is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:75` | FLAC frame padding bits are not zero |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:118` | FLAC reserved residual coding method |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:123` | FLAC residual partition order is invalid for the block |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:139` | FLAC residual is out of range |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:151` | FLAC subframe padding bit is not zero |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:158` | FLAC wasted-bits count is invalid |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:176` | FLAC predictor order exceeds the block size |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:192` | FLAC sample overflow |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:198` | FLAC predictor order exceeds the block size |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:205` | FLAC invalid LPC precision |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:210` | FLAC negative LPC shift |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:225` | FLAC sample overflow |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:229` | FLAC reserved subframe type |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:233` | FLAC decoded sample exceeds its bit depth |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:249` | FLAC invalid coded frame number |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:254` | FLAC invalid coded frame number |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:267` | FLAC metadata is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:274` | FLAC metadata block runs past the end of the file |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:278` | FLAC STREAMINFO is not the first metadata block |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:283` | FLAC has more than one STREAMINFO |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:286` | FLAC STREAMINFO has the wrong length |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:303` | FLAC metadata block type 127 is invalid |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:333` | FLAC frame sync not found (corrupt or trailing data) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:336` | FLAC frame reserved bit is set |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:347` | FLAC frame reserved bit is set |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:351` | FLAC reserved block size |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:374` | FLAC invalid frame sample rate |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:384` | FLAC reserved sample size |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:389` | FLAC frame header CRC-8 mismatch (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:395` | FLAC frame block exceeds the STREAMINFO maximum |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:400` | FLAC reserved channel assignment |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:407` | FLAC frame numbering is discontinuous (missing or duplicated frame) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:418` | FLAC frame CRC-16 mismatch (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:449` | FLAC STREAMINFO declares {} samples but the stream holds {} (truncated or corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `flac.rs:469` | FLAC audio MD5 does not match STREAMINFO (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `main.rs:197` | {}: frame count overflows |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:35` | MPEG audio frame header is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:39` | MPEG audio frame sync lost (corrupt data or junk between frames) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:45` | MPEG audio version is reserved (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:51` | MPEG audio layer is reserved (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:59` | MP3 bitrate index is invalid (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:64` | MP3 sample-rate index is reserved (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:75` | MP3 emphasis value is reserved (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:121` | ID3v2 tag size is invalid |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:127` | ID3v2 tag runs past the end of the file |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:144` | APEv2 tag size is invalid |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:196` | the last MP3 frame is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:209` | MP3 frame is too short for its side information |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:215` | MP3 frame CRC mismatch (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:241` | Xing/Info header is truncated |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:333` | MP3 frame {i} does not decode ({e}) (corrupt) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `mpeg.rs:335` | MP3 frame {i} decoded to an unexpected length |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:19` | truncated chunk header |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:27` | chunk '{}' runs past the end of the file (truncated) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:36` | missing chunk pad byte (truncated) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:46` | truncated RIFF header |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:63` | more than one 'fmt ' chunk |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:66` | 'data' precedes 'fmt ' |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:72` | more than one 'data' chunk |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:79` | no 'fmt ' chunk |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:80` | no 'data' chunk |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:82` | 'fmt ' chunk is too short |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:94` | WAVE_FORMAT_EXTENSIBLE 'fmt ' chunk is too short |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:131` | 'fmt ' block align or byte rate disagrees with channels and bits |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:135` | 'data' ends inside a sample frame (truncated) |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:178` | truncated FORM header |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:196` | more than one COMM chunk |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:201` | more than one SSND chunk |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:207` | no COMM chunk |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:209` | COMM chunk is too short |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:253` | no SSND chunk |
| `SOURCE_CORRUPT` | 2 | source | unusable | `wav.rs:255` | SSND chunk is too short |
| `SOURCE_LEVEL` | 2 | source | unusable | `convert.rs:78` | no valid true-peak measurement for a source that is not digital silence |
| `SOURCE_LEVEL` | 2 | source | unusable | `convert.rs:92` | 16-bit quantization would overflow |
| `SOURCE_PROTECTED` | 2 | source | protected | `aac.rs:424` | protected (encrypted) MP4 is refused |
| `SOURCE_PROTECTED` | 2 | source | protected | `aac.rs:477` | protected (encrypted) AAC is refused |
| `SOURCE_PROTECTED` | 2 | source | protected | `aac.rs:497` | protected (encrypted) AAC is refused |
| `SOURCE_NOT_AUDIO` | 2 | source | not-music | `sniff.rs:50` | the file is empty |
| `SOURCE_NOT_AUDIO` | 2 | source | not-music | `sniff.rs:52` | not a supported audio format (unrecognised bytes) |
| `SOURCE_TOO_SHORT` | 2 | source | source-named | `aac.rs:227` | the ADTS stream holds no frames |
| `SOURCE_TOO_SHORT` | 2 | source | source-named | `aac.rs:582` | MP4 audio track holds zero samples |
| `SOURCE_TOO_SHORT` | 2 | source | source-named | `common.rs:94` | the stream decodes to zero frames |
| `SOURCE_TOO_SHORT` | 2 | source | source-named | `main.rs:199` | {}: too short to produce one 44.1 kHz frame ({} frames at {} Hz); the whole request is refused |
| `SOURCE_TOO_SHORT` | 2 | source | source-named | `mpeg.rs:222` | the MPEG stream holds no audio frames |
| `SOURCE_TOO_SHORT` | 2 | source | source-named | `mpeg.rs:309` | the MPEG stream holds no audio frames after its Xing/Info frame |
| `SOURCE_TOO_SHORT` | 2 | source | source-named | `wav.rs:251` | COMM declares zero sample frames |
| `SOURCE_CHANGED` | 2 | source | source-named | `main.rs:239` | {}: the file changed while ingest was running |
| `SOURCE_CHANGED` | 2 | source | source-named | `main.rs:464` | {}: the file changed while ingest was running |
| `SOURCE_NON_FINITE` | 2 | source | unusable | `common.rs:101` | the stream contains non-finite (NaN or infinite) samples |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:389` | iTunSMPB has no data (invalid metadata) |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:392` | iTunSMPB is not text (invalid metadata) |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:397` | iTunSMPB is malformed (invalid metadata) |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:408` | {what} is not a whole number of source frames (fractional trim interval) |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:410` | {what} is out of range |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:520` | MP4 sample durations do not describe whole 1024-frame AAC access units (unsupported trim signalling) |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:598` | MP4 edit list has {cnt} entries; only one contiguous presentation interval is admitted |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:606` | MP4 edit with a media rate other than 1 is unsupported |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:609` | MP4 empty edit (inserted delay) is not an admitted presentation interval |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:612` | MP4 edit with zero duration is ambiguous |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:617` | MP4 edit list extends past the decoded stream (out of range) |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:620` | the MP4 shortened final sample contradicts the edit list end |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:626` | an MP4 shortened final sample without an edit list is unsupported trim signalling |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:629` | iTunSMPB alone is not an admitted trim interval in INGEST-1 |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `aac.rs:632` | iTunSMPB contradicts the MP4 edit list |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `common.rs:107` | declared trim (head {}, tail {}) leaves no frames of the {} decoded |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `mpeg.rs:175` | iTunSMPB in an ID3 tag is an MP3 trim declaration INGEST-1 does not admit |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `mpeg.rs:232` | VBRI (Fraunhofer) gapless/duration metadata is unsupported in INGEST-1 |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `mpeg.rs:285` | LAME tag CRC mismatch (invalid gapless metadata) |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `mpeg.rs:291` | LAME delay/padding without a Xing frame count cannot be validated |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `mpeg.rs:294` | Xing frame count {} disagrees with the {} audio frames in the stream |
| `SOURCE_TRIM_UNSUPPORTED` | 2 | source | unusable | `mpeg.rs:301` | LAME padding {padding} is smaller than the {DECODER_DELAY}-frame decoder delay (out of range) |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:66` | {} is outside INGEST-1 (AAC-LC only) |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:76` | AAC with a program config element (channel config 0) is unsupported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:78` | AAC channel configuration {n} is not mono or stereo |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:82` | AAC 960-sample frames are unsupported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:85` | AAC dependsOnCoreCoder is unsupported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:88` | AAC GASpecificConfig extension flag is unsupported for AAC-LC |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:96` | HE-AAC (explicit SBR signalling) is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:158` | HE-AAC (SBR data in the stream) is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:204` | {} is outside INGEST-1 (AAC-LC only) |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:211` | ADTS frames with more than one raw data block are unsupported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:216` | ADTS sample rate or channel configuration changes mid-stream |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:355` | MPEG-2 AAC Main is outside INGEST-1 (AAC-LC only) |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:356` | MPEG-2 AAC SSR is outside INGEST-1 (AAC-LC only) |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:357` | MP3 inside MP4 is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:358` | MP4 audio object type indication 0x{n:02X} is unsupported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:419` | fragmented MP4 is unsupported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:427` | fragmented MP4 is unsupported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:447` | MP4 holds more than one audio stream |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:450` | MP4 holds a video stream; INGEST-1 accepts audio-only M4A |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:454` | MP4 holds no audio stream |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:471` | MP4 audio track has more than one sample description |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:478` | ALAC is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:479` | MP4 audio codec '{}' is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `aac.rs:488` | MP4 sound description version is unsupported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `common.rs:39` | sample rate {rate} Hz is not supported by INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `common.rs:46` | the stream declares zero channels |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `common.rs:47` | {n} channels; INGEST-1 accepts only mono or stereo |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `flac.rs:299` | FLAC STREAMINFO sample rate is zero |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `flac.rs:314` | {}-bit FLAC is outside INGEST-1 (8–32 bits) |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `flac.rs:340` | FLAC blocking strategy changes mid-stream |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `flac.rs:392` | FLAC sample rate or bit depth changes mid-stream |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `flac.rs:403` | FLAC channel count changes mid-stream |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `mpeg.rs:49` | MPEG Layer II audio is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `mpeg.rs:50` | MPEG Layer I audio is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `mpeg.rs:56` | free-format MP3 is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `mpeg.rs:200` | MP3 sample rate changes mid-stream |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `mpeg.rs:203` | MP3 channel count changes mid-stream |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `sniff.rs:12` | RF64/BW64 WAV is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `sniff.rs:15` | Wave64 is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `sniff.rs:24` | Ogg streams (including Ogg-FLAC, Vorbis and Opus) are outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `sniff.rs:27` | Core Audio Format (CAF) is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `sniff.rs:33` | ADIF AAC is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `sniff.rs:36` | LATM/LOAS AAC is outside INGEST-1 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `sniff.rs:41` | FLAC preceded by an ID3v2 tag is not native FLAC |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:99` | WAVE_FORMAT_EXTENSIBLE sub-format GUID is not a WAVE format code |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:103` | {valid} valid bits in a {bits}-bit container |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:111` | ambiguous channel mask 0x{mask:X} for {ch} channel(s); INGEST-1 accepts mono 0x4 or stereo 0x3 |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:125` | {b}-bit integer PCM WAV is not supported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:126` | {b}-bit float WAV is not supported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:127` | MP3 inside WAV (format tag 0x0055) is not supported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:128` | compressed or unknown WAV format tag 0x{t:04X} |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:157` | AIFF sample rate is zero or negative |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:161` | AIFF sample rate is out of range |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:166` | AIFF sample rate is not an integer |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:169` | AIFF sample rate is not an integer |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:173` | AIFF sample rate is out of range |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:226` | compressed AIFC (compression type '{}') is not supported |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:239` | AIFC 'sowt' with {b}-bit samples is outside INGEST-1 ('sowt' is 16-bit only) |
| `SOURCE_OUTSIDE_INGEST1` | 2 | source | unusable | `wav.rs:247` | {b}-bit AIFF samples are not supported |
| `INGEST_TOO_LONG` | 2 | none | overage | `main.rs:219` | the sources and folder gaps total {} ({} frames), over the {} label by {} frames (rounded up {}); nothing was written |
| `INGEST_RIFF_LIMIT` | 2 | none | other | `main.rs:230` | the output would exceed the canonical RIFF size limit (4 GiB) |
| `JOIN_PEAK` | 2 | boundary | other | `main.rs:327` | the join between {} and {} reaches {} dBTP, over the {} dBTP ceiling with its {} dB guard; refusing without changing gains |
| `JOINED_PEAK` | 2 | none | other | `main.rs:340` | the joined output reaches {} dBTP, over the {} dBTP ceiling with its {} dB guard; refusing without changing gains |
| `DEST_EXISTS` | 2 | none | other | `publish.rs:85` | {}: already exists; ingest never overwrites |
| `DEST_APPEARED` | 2 | none | other | `publish.rs:132` | {}: appeared while ingest ran; not overwritten |
| `DEST_NAME_INVALID` | 2 | none | other | `publish.rs:103` | {}: not a usable destination name |
| `IO_SOURCE` | 1 | source | unusable | `main.rs:116` | {logical}: cannot open: {e} |
| `IO_SOURCE` | 1 | source | unusable | `main.rs:121` | {logical}: cannot read: {e} |
| `IO_FOLDER` | 1 | folder | other | `order.rs:90` | cannot read folder {disp}: {e} |
| `IO_FOLDER` | 1 | folder | other | `order.rs:93` | cannot read folder {disp}: {e} |
| `IO_FOLDER` | 1 | folder | other | `order.rs:102` | {disp}/{raw}: {e} |
| `IO_FOLDER` | 1 | folder | other | `order.rs:158` | {}: {e} |
| `IO_DEST` | 1 | none | other | `publish.rs:14` | {what} {}: {e} |
| `IO_DEST` | 1 | none | other | `publish.rs:90` | {}: the parent folder does not exist |
| `IO_DEST` | 1 | none | other | `publish.rs:118` | cannot create stage {}: {e} |
| `IO_DEST` | 1 | none | other | `publish.rs:121` | cannot create a fresh stage folder |
| `IO_DEST` | 1 | none | other | `publish.rs:134` | cannot publish {}: {e} |
| `IO_MEMORY` | 1 | none | other | `common.rs:199` | out of memory (needed {n} elements); nothing was written |
