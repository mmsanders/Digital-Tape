# Software C1 — `tapectl make` method note (#624)

**Software Lead, 28 October 2026.** Answers the five points of
`tests/wp15_cards_make_r1/FEASIBILITY.md` for the exact head on
[PR #626](https://github.com/mmsanders/Digital-Tape/pull/626), under APP-1 §3 and APP-1A §7 as
amended by ADR-195. Verification reviews this note with the head; it is not a prior gate.
**Revised 28 October for Verification364's Stage 2 findings F364-1..3** (§3, §5, §7), **and
again for its correction-1 and correction-2 reviews** (the Windows volume census and its
`ERROR_NOT_READY` exception, §3 and §5).

## 1. Who owns which handle, and when

Everything runs in the one elevated `tapectl make` process. Nothing else touches the card:
the app only starts that process (§6 below), and `tapectl cards` never opens a disk for writing.

- **Query handles (before the safety decision).** They are the accepted WP-14 `provision` probe,
  unchanged (`host/port/probe_*.c`). It opens zero-access or read-only handles on the disk or
  volumes to read OS facts. Where partition 1 is mounted, it reads LBA 0 read-only to
  establish the exact §3.1 layout. None of them can write.
- **The policy.** `target_safety_why` runs every WP-14 §5 rule in order (`safety_policy`). A
  refusal returns exit 3 before any write-mode open, with zero writes, and names the refusal in
  the report. An OS partition hint alone never earns an unmount. Partition 1 is "own" only if
  the probe read the exact layout bytes. The bare `55 AA` and byte-invalid rows show this.
- **The authorized open.** After the policy passes, the only own-p1 unmount happens (as for
  provision). Then `make_run` makes exactly one `hport_open(path, device, writable)`. That handle
  is kept until `finish()` closes it at the end. On a failed own-p1 unmount, make refuses with
  `REFUSE_FOREIGN_MOUNT` and `unmount_failed: true`, and touches no other partition.

## 2. How the decision is bound to the authorized object

ADR-195 withdrew "binding before authorized write-mode access". `make` uses `provision`'s
accepted sequence as it is: the policy judges the path's facts, then the same path is opened
once. A different disk could appear at that path between the query and the open. That window
is the same as WP-14 `provision`'s, and it is a stated limitation, not a detected case. The app
narrows it with its two pre-launch rechecks (APP-1 §4 steps 1 and 3). These must print the same
single card, path and bytes, that the person saw. Path and capacity are not claimed as identity.

## 3. One retained session; NULL-write verify; removal

`make_run` → `make_provision` (the existing `provision_existing` body, with generated uuid and
epoch) → `make_load` (`target_bind_write` binds partition 2 **on the already open handle**, then
the existing `load_existing_feed`, `commit_loaded` and promote). Then `make_verify`:
`target_bind_verify` binds a partview with a **NULL write callback** on the same handle, and the
existing `verify_existing` runs over it. Nothing in make reopens the path. In every row, the
trace shows one authorized `write_open` and no later open.

Outcomes, exits and stdout are the standalone commands', in their order of work. That includes
TOO_LONG, bad WAV and truncated WAV *after* provision, exactly as the separate sequence does.
Make's stdout is `uuid`/`epoch`, then verify's lines.

**Removal or change.** With `failstop` set (make only), `hport` classifies every failed OS read,
write or flush right after the call.
- **Counted as removal or change:** Windows `ERROR_DEV_NOT_EXIST`, `ERROR_MEDIA_CHANGED`,
  `ERROR_NOT_READY`, `ERROR_NO_MEDIA_IN_DRIVE`, `ERROR_DEVICE_NOT_CONNECTED` and
  `ERROR_NO_SUCH_DEVICE`; POSIX `ENOMEDIUM`, `ENODEV` and `ENXIO`. The port is then marked gone,
  and every later I/O fails without reaching the OS. At the step boundary, make reports
  `CARD_CHANGED`, with the phase and that OS error, and exits 1. Verify prints no further
  finding and no `OK`.
- **Not counted:** ordinary `EIO` stays I/O (`ENGINE`/`IO`).

**A required query that itself fails (correction for F364-1).** The probe now records the first
OS query it needed that failed, as `CALL: ERROR`, in `device_facts.query_error`; the fact keeps
its refusing value, so `provision` and every other command are unchanged. Make stops on it in
`target_safety_why`, before any rule is judged or anything is unmounted, with exit 1
`HOST_QUERY_FAILED` (`subject` null, `phase` "safety", `op` "media_query", `os_error`). The
queries are the ones the §5 facts come from.
- **Windows:** the query open of the disk, `IOCTL_STORAGE_GET_DEVICE_NUMBER`,
  `IOCTL_STORAGE_QUERY_PROPERTY`, `IOCTL_DISK_GET_LENGTH_INFO`, `GetSystemWindowsDirectoryW`, the
  system and page-file volume extents, `EnumPageFilesW`, `FindFirstVolumeW`, and the LBA 0 read.
- **Linux:** sysfs `removable` and `size`, `/proc/self/mountinfo`, `/proc/swaps`, and the LBA 0
  open/read.
- **The authorized open's own geometry query** (`IOCTL_DISK_GET_LENGTH_INFO` / `BLKGETSIZE64`)
  is kept in `hport.query_error` and reported the same way, phase "safety" (it is before
  provision). Before this, it was `DEVICE_OPEN_FAILED`, exit 2.

**The Windows mounted-volume census is a required query too (correction 2, V364 [P1]).**
Correction 1 still let a mounted volume drop out of the census without a query error. Now
each of these fails the census:
- **Mount paths:** a failed `GetVolumePathNamesForVolumeNameW`. `ERROR_MORE_DATA` is retried once,
  at the size the OS asked for. A successful empty path list still means "not mounted".
- **Extents:** a failed `IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS`, with two exceptions where the
  volume cannot be a mounted volume of this disk:
  - the OS answers `ERROR_NO_MEDIA_IN_DRIVE` (1112), its documented "no medium" (an empty
    reader slot or drive);
  - the volume's own `IOCTL_STORAGE_GET_DEVICE_NUMBER` proves it is on another device or is
    not a disk.

  `ERROR_NOT_READY` (21) only means "device not ready", not that there is no medium, so it is
  not an exception by itself (correction 3, Verification's correction-2 review). Like any other
  error, it is skipped only when the device number proves the volume is elsewhere. An empty
  slot on another reader is excluded that way; the target's own volume answering 21 fails the
  census. A failed or unknown device-number query is never an exclusion.
- **Enumeration:** `FindNextVolumeW` ending with anything but `ERROR_NO_MORE_FILES`.

A failed census sets `query_error`, so make reports `HOST_QUERY_FAILED`. It also leaves the
mount fact refusing (more mounts than the limit), so standalone `provision`, `load` and `verify`
refuse with `REFUSE_FOREIGN_MOUNT` instead of judging an incomplete list.

A known refusing fact stays a §5 exit-3 refusal. No other query is added, so there is no
monitoring cadence.

## 4. Elevated report and cleanup boundary

The report is opened before any device work, by `host/makereport.c`.
- **Windows.** The parent directory is opened itself (`FILE_FLAG_OPEN_REPARSE_POINT`) and held
  without `FILE_SHARE_DELETE` until the end. It must be a plain directory, and so must every
  ancestor. The leaf is `CREATE_NEW` with `FILE_FLAG_OPEN_REPARSE_POINT`.
- **POSIX.** An `openat` walk with `O_NOFOLLOW|O_DIRECTORY`, then the leaf with
  `O_CREAT|O_EXCL|O_NOFOLLOW`.

A failure exits 1 with stderr only and creates nothing. `report.c` stays byte-identical to the
accepted S2 cards source.

The app deletes only its own marked job directories (`jobdir::removal`: plain, not a reparse
point, carries the marker). The Windows hold relies on NTFS refusing to rename a directory that
has an open handle under it. That is an assumption, not tested here. The stderr of an elevated
child cannot be piped to the app, so make mirrors every stderr line into `stderr` records for
Show details.

## 5. Test route and its scope

Rows run `tapectl-test make` on real device nodes through the existing `TAPECTL_TEST` facts
seam. The nodes are Linux loop devices and device-mapper, and Windows Server VHDs. Raw I/O, OS
errors and flushes are real; only the "is this a card" facts are injected. Each kind of node
is paired with the shipped binary refusing it (`unjudged/shipped/*`).

The observer is the compiled-test trace, qualified by a positive control (a standalone
provision's open and writes). The trace maps one-to-one onto the oracle's journal.

Removal fixtures pause make at a phase boundary (`TAPECTL_TEST_PAUSE`), then detach, re-attach
or swap the VHD. Make's next real I/O meets the OS error: `ERROR_DEV_NOT_EXIST` on Windows
Server, at load, commit and verify.

The imported `runner.py` judges the bundle unchanged. A second bundle, with a write callback
during verify, must be refused by it, and is.

**Added by the correction.** `tools/wp15-cards/judge_c1.py` judges two more sections of the same
bundle with Verification's own predicates:
- **`queries`** (F364-1), on Linux loop devices and Windows Server VHDs, through
  `wp15_boundary_query_r1/oracle.check`:
  - the real probe's capacity query failed by the OS;
  - its neighbour on the same kind of node, with every query succeeding, giving the known
    refusal;
  - the authorized open's geometry query failed by the OS.
  - On Windows only, six census rows on a VHD holding a real mounted NTFS volume. The real
    probe runs, with the facts seam's `probe=1` overlaying only `removable=1`:
    - the neighbour with every query succeeding, giving the known `REFUSE_FOREIGN_MOUNT`/3;
    - `mount-paths`, `volume-extents` and `volume-enum` each really failed by the OS, giving
      `HOST_QUERY_FAILED`/1;
    - two TYPED rows, `typed-error:not-ready-target|not-ready-other`. A typed 21 replaces the
      extents answer, which is not an OS-generated error:
      - on the target's volume, the result is `HOST_QUERY_FAILED`/1;
      - on every other device's volume, the result is the known `REFUSE_FOREIGN_MOUNT`/3, with
        the target's mounted volume still counted.
    
    Each is paired with standalone `provision` on the same node and fault. It must refuse
    with `REFUSE_FOREIGN_MOUNT` and no write-mode open, write or unmount.
  - Verification's regressions run unchanged over the old and new builds:
    - `c1_volume_query_r1` over the `e36ea492` probe;
    - `c1_volume_query_r2` (prepare.py's typed-21 probe) over the `39636892` probe.
    
    Each must still reproduce its omission on the old build (the controls) and must record
    the failed query on this head.
  
  The test-only control `query-error:POINT` makes the real call fail in the OS: a zero-size
  result buffer on Windows, and a missing sysfs file or a NULL result pointer on Linux.
  `media_query` trace events say which query failed.
- **`supplement`** (F364-3), through `c1_closeout_r1/make_supplement.py`:
  - `own-p1-valid-exact`: partition 1 of an exact layout really mounted read-only (loopNp1),
    really unmounted by make, then one session, with an equivalence pair against the standalone
    sequence;
  - `label-33`, routed to `input_refusal`.
  Each section has a negative control (the own-p1 unmount marked failed; a HOST_QUERY_FAILED
  recorded as exit 3) that the same predicates must refuse.

**G3 (F364-2).** `tools/app/g3_624.py` and `host/app/tests/g3_component.rs` (test-only, compiled
inside the bridge module) run all 28 `c1_closeout_r1/g3.py` cases on a hosted Windows runner.
- **Real children** run through the production completion path:
  - the original INGEST child on real folders, through the production worker closure;
  - `tapectl-test make` on a VHD, with the argv the bridge built and its report read by
    `run_make`;
  - the shipping `tapectl cards`, through `discover`.
- The launcher runs the request unelevated (the runner is an administrator without UAC) instead
  of through `runas`.
- The child's original stdout, stderr and report are kept before the bridge removes its job.
- **Stderr changed, same exit and report.** For ingest and cards, a second bridge receives the
  same exit and original report with different stderr. For make, whose stderr reaches the app
  only as report `stderr` records, those records are reworded and the otherwise identical
  report is judged again.
- **How each make row gets its outcome:**
  - **removed:** VHD detached at the load pause;
  - **device-io:** the disk set read-only at the load pause, so writes fail with write-protect,
    not a removal;
  - **host-query:** `query-error:disk-length` with the real probe;
  - **verify-findings:** `read-error:2048@verify`;
  - **small:** a 64 MB VHD;
  - **safety-refusal:** the real probe on a VHD, which is never a card;
  - **wav-truncated:** a WAV shorter than its header says;
  - **generic-make:** a 33-byte label. The app's label box cannot produce one (`label.rs`), so
    the test sets `App.label` directly; the tool's exit and report are real.
- **Other fixtures:**
  - **protected:** `tone.m4a` with its sample entry renamed `drms`, which is how a
    FairPlay-protected track looks to ingest;
  - **discovery-unavailable:** more VHDs attached than `tapectl cards` lists (disk number ≥ 64),
    so its census fails in the OS.
- The twelve app-origin cases use the same bridge actions, with their typed launcher or recheck.

**Not shown by this route:** a real reader, Windows 11, the real UAC prompt and its decline, a
card swapped inside a reader, and an equal-size swap between `cards` and `make`. Those are C2,
or stated limitations.

## 6. Elevation and the app

The app starts only `tapectl make`, with `ShellExecuteExW` verb `runas`. The call is hidden
(`SW_HIDE`), owned by the app window so the prompt comes up in front, and uses
`SEE_MASK_NOCLOSEPROCESS`. A declined prompt is `ERROR_CANCELLED`: `ELEVATION_DECLINED`,
nothing started.

The app, `ingest` and `tapectl cards` stay `asInvoker`. The candidate's `BUILD.json` records
each member's manifest level.

**Expected prompt** (not yet seen on Windows 11):

> User Account Control — Do you want to allow this app from an unknown publisher to make
> changes to your device? `tapectl.exe` — Publisher: Unknown — File origin: Hard drive on this
> computer — [Yes] [No]

A standard (non-admin) account gets the credential form instead.

The app checks `tapectl.exe` against its compiled SHA-256 pin just before the launch. The
folder is the person's own and is writable by them, so the check and the elevated start are
not atomic. Another program running as that person could replace the file in between, and
that is a stated limitation. The UAC prompt names `tapectl.exe` and is the last gate.

**Bar weights**, recorded per APP-1A §4: safety 1, provision 4, load 60, commit 5, verify_a 15,
verify_b 15. The bar is a running maximum. Success is never inferred from 100%.

## 7. Findings on the imported package (returned, not edited)

- **F1, F2: resolved by Verification's supplement.** The own-p1 success and label-33 rows are
  now judged by `make_supplement.py` (§5).
- **F3: resolved.** `HOST_QUERY_FAILED` is now emitted and parsed through
  `wp15_boundary_query_r1`.
- **G3-D1: resolved by Verification** (correction-1 review, `g3.py` at `c8d137c6`). A zero-child
  rejected drop has no diagnostic to require. The native Show-details presentation remains
  G4/C2.
- **F4.** S2-era imported app contracts (`windows_interactions_r2`, `windows_discovery_r1`)
  assert "permanently disabled Make". They stay green because their fixtures hold no retained
  ingest audio. The WP-15 acceptance package should state the Make-era rule.
- **No independent test yet** for: a commit-phase engine failure (no lawful trigger without a
  new fault), query-handle access (probe opens are not in the compiled trace),
  cleanup-substitution of a junction, and the app's elevated launcher itself. The G3 rows run
  the bridge's own request unelevated; `runas`, the UAC prompt and its decline are C2.
