# Software C1 — `tapectl make` method note (#624)

**Software Lead, 28 October 2026.** Answers the five points of
`tests/wp15_cards_make_r1/FEASIBILITY.md` for the exact head on
[PR #626](https://github.com/mmsanders/Digital-Tape/pull/626), under APP-1 §3 and APP-1A §7 as
amended by ADR-195. Verification reviews this note with the head; it is not a prior gate.

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

No other media query is made, so make never emits `HOST_QUERY_FAILED`: an unknown fact is a §5
refusal, as for provision.

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

- **F1.** `oracle.session()`'s success branch applies `no_device_mutation` to every event before
  the authorized open, and that rule counts `unmount` as a mutation. So the WP-14-lawful
  own-p1-valid-exact positive (unmount own p1, then provision) cannot pass as written. It is not
  in the judged bundle. The failed-unmount refusal row is.
- **F2.** `label-33-UTF8-bytes` exits 2 before any device open. `session()` requires either a
  policy refusal or one authorized open, so the row is kept unjudged, with an unchanged-bytes
  check.
- **F3.** The prior `wp15_app1a_r1` closed make IDs (M1) predate `HOST_QUERY_FAILED` (ADR-189).
  Make never emits it, so there is no conflict today.
- **F4.** S2-era imported app contracts (`windows_interactions_r2`, `windows_discovery_r1`)
  assert "permanently disabled Make". They stay green because their fixtures hold no retained
  ingest audio. The WP-15 acceptance package should state the Make-era rule.
- **No independent test yet** for: a commit-phase engine failure (no lawful trigger without a
  new fault), query-handle access (probe opens are not in the compiled trace),
  cleanup-substitution of a junction, stderr-record capture, and the app's elevated launcher
  itself. The launcher is covered by the component tests through a typed launcher only.
