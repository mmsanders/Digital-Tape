# WP-15 one-window app — contract APP-1

**ISSUED by PM for host authoring/build, 17 October 2026 PDT, ADR-185, with
[closed interface annex APP-1A](WP15-APP-ANNEX.md).** Originally preflighted under
ADR-182/183; Software444's Q1–Q7 are resolved by APP-1A. Package criteria are
[WP-15](PACKAGES/WP-15.md) G1–G5. This document and its annex control ambiguities;
APP-1A controls the amended discovery/report interfaces. No engine, format or
frozen-spec change. Independent preflight/tests/disposition remain required.
**Michael's taste items** (§8) carry defaults. They may change wording or defaults without a new
round until Software starts the build. Build starts only within a fresh Software issue; S2/S3 discovery/make implementation
waits for independent feasibility preflight. Host report/app-shell work may overlap
independent authoring under the existing host-tool rule.

## 1. What the app is

One window that turns folders of music into a cartridge on one card. It runs the shipped `ingest`
(INGEST-1) and `tapectl` (WP-14) binaries as child processes, bundled at pinned hashes. It never
reimplements their behaviour. Guardrails 03 and 12 apply in full. It shows no list of tracks, files,
folders or cards. It has no playback, library, tag editing, search or history.

**G1, made checkable.** App code never opens a block device, raw disk or partition, for reading or
for writing. Every device access is a `tapectl` child process. A CI check fails on device-open APIs
in app code, with a negative control. The app holds no TAPEFS layout or engine knowledge.

Shell: Tauri is recommended (plan §3). Software confirms it or records an alternative before
building. Platforms (D2): Windows 11 x64 and current macOS arm64. Linux builds only for CI.

## 2. The window

One window with four states. The default copy is in §6.

| State | Shows | Can do |
|---|---|---|
| **Empty** | Drop area; a length bar at 0; label box; card line; disabled **Make cartridge** button | Drop folders; type label |
| **Ready** | Length bar filled to the music's length against 60 minutes; label; the one card found | Drop more folders (appended); **Start over**; **Make cartridge** |
| **Making** | One progress bar across the whole job, with one plain line naming the current step | **Cancel** before the erase confirmation only; afterwards none (see §4) |
| **Done / Problem** | One sentence and what to do next | **Make another** / **Start over** |

**Drops.** Folders only. Each dropped folder is one INGEST-1 FOLDER argument. Folder order is
drop order. Within one gesture, the order is the order the OS reports. A dropped file, or a mix of
files and folders, gets the "folders only" message and nothing is added.

**Length bar.** On each drop, the app runs `ingest` in the background into an app-owned temporary
DEST, using `--length 3600` and all folders dropped so far. While it runs, the bar says "Checking
the music…". The bar comes from `ingest`'s exact `total_frames`, so overage and refusals appear
before the user touches the card. On an overage refusal, the bar is drawn full in its "too long" style
and the §6 sentence uses the exact excess from the refusal record (§3). Each new drop reruns ingest over every folder; the previous
DEST is deleted first. The app deletes only directories it created. App-owned directories are the per-job **control
directory** (reports) and the DEST parent. Both live under the app's own per-user data folder, never
beside a source or on a card.

**Label.** UTF-8, 1–32 bytes, as `tapectl provision --label` requires. The box stops accepting
input that would exceed 32 bytes, never truncates silently, and is never pre-filled. **Make
cartridge** is enabled only with a non-empty label, a successful check, and exactly one card.

**Card line.** The app runs `tapectl cards` (§3) every 2 s while not Making:
- 0 offered cards: "Put a card in."
- 1 card: "Card ready (64 GB)." The size uses the OS capacity in decimal GB, rounded.
- 2 or more: "Leave just one card in the computer."

There is no card picker: one-card-at-a-time replaces a list and removes wrong-card choices. A disk refused by the discovery policy is never offered; a candidate may still be
refused by make's exact elevated preflight, with zero writes.

## 3. Tool additions (host only, additive)

These are new host CLI surface. They need independent tests before acceptance, under the host-tool
parallel-authoring rule. Existing commands and outputs are unchanged when the new flags and commands
are absent, so INGEST-1 Stage1 and accepted WP-14 evidence are unaffected.

**`tapectl cards`.** Unelevated, read-only candidate discovery under APP-1A §5;
zero writes, zero write-mode opens, no unmount. It prints one JSON line per
candidate, `{"t":"card","path":PATH,"bytes":N}`, then
`{"t":"summary","offered":N,"unprobed":M}`. No `provisioned` field: exact on-disk
recognition is unavailable unelevated and the app does not need that field.
The OS partition-view candidate exception is discovery only; elevated make still
requires exact WP14 checks before writes. Refused disk names are never printed.
Exit0 means enumeration completed (including no candidates); exit1 means
unavailable, exit2 usage. Unknown safety facts count unprobed, never safe.
When none is offered the app keeps polling and records unprobed for Show details.

**`tapectl make DEV --label L --length-s S --wav FILE --erase DEV`** (ADR-183, P2V15-003). One
process runs `provision`, then `load` of FILE, then `verify`, with exactly their existing outcomes,
order of work and exit meanings. It holds **one authorized device session** across the whole sequence; preliminary
read-only/zero-access safety query handles are permitted (APP-1A §5). The verify
phase uses a NULL-write binding over the same open device; it does not reopen it. §5 safety runs
first on that open, as for `provision`. **Continuity:** if the OS reports media removal or change
on that open device, `make` stops with ID `CARD_CHANGED` and exit 1, and never continues on a
reopened path. This covers Windows media-change/removal errors and macOS disk disappearance.
Software demonstrates detection on Windows 11 and macOS arm64 with an equal-size swap, a
remove/reinsert, and a no-change positive. A reader or platform that cannot report a change is
recorded as a stated limitation, never claimed. A change between `cards` and the start of `make`
is covered by the app's pre-launch recheck (§4) only. A deliberate equal-size swap inside that gap
is not detectable from published facts, and the app does not claim otherwise. Separate
`provision`, `load` and `verify` remain available and unchanged.

**`--report FILE --report-nonce N`** on `ingest`, `tapectl cards` and `tapectl make`. This is a
narrow, opt-in **diagnostic exception** to INGEST-1 §6's no-output-before-preflight rule (ADR-183,
P2V15-002). FILE is not ingest output: it never sits inside DEST or its stage, and its existence
says nothing about success. The rules:
- **Ownership.** The tool creates FILE exclusively at start, refusing if it exists, and never
  follows a symlink at FILE. One file per invocation; nothing is appended across invocations.
- **First line.** `{"t":"start","tool","version","nonce":N}`. The app ignores any file whose nonce
  is not the one it passed.
- **Records.**
  - progress: `{"t":"progress","step","done","total"}`;
  - make diagnostic stderr: `{"t":"stderr","text":S}`, never an outcome selector;
  - refusal or failure: `{"t":"refusal","id","subject",...}`;
  - for an ingest overage, also integer `total_frames`, `capacity_frames` and `excess_frames`,
    including folder gaps (P2V15-001);
  - a final `{"t":"end","exit":E}`.
- **Progress.** `step` names come from a closed per-tool list. `done` and `total` are integers in
  that step's own unit. Values are monotonic within a step within one invocation. `total`=0 means
  unknown. Progress may be sparse or absent on success.
- **Failure to write.** If FILE cannot be created, the tool exits 1 before any other work, with the
  reason on stderr only. If a later write fails, the tool keeps its existing exit semantics: an
  ingest publication that already succeeded stays exit 0. It puts a stderr warning, and the app
  then decides from the exit code and the DEST state alone.
- **Partial lines.** A final unterminated line is ignored.

With no `--report`, no file is created and every existing transaction is unchanged. On a
preflight refusal, the report is the only file the invocation may create: no DEST, stage, WAV or
manifest.

**Closed IDs, payloads, precedence and progress** are issued in [APP-1A](WP15-APP-ANNEX.md),
including:
- per command: WP-14 §5/§7 categories, split into stable IDs for usage, label, capacity, WAV,
  `NOT_PROVISIONED` and OS I/O;
- `verify` findings with their payload, where `READ_ERROR` carries side and frame, and the stated
  precedence when one event is both I/O and a finding;
- INGEST-1 reasons;
- the closed progress-step names.

APP-1A also defines source/folder/boundary subjects and app fallback rules. `subject` is the INGEST-1 logical path `ordinal/name` or a
boundary named by both neighbours. The app displays the file's basename, or for folder-level and
gap-boundary refusals the dropped folder's own name, which it maps from the ordinal.

## 4. Make cartridge

The steps run in this order:

1. **Recheck.** Rerun `tapectl cards`. The same single card (same path and bytes) must still be the
   only one. Otherwise return to Ready with the card message.
2. **Confirm erase.** A modal box: "Everything on this card will be replaced with your music."
   Buttons: **Replace** / **Keep card**. This is the only confirmation.
3. **Recheck again, then make.** Immediately before launching, repeat step 1, then run one
   elevated child: `tapectl make DEV --label L --length-s 3600 --wav <ingested audio.wav> --erase
   DEV`. DEV is the path from the recheck. It is never typed, edited or chosen by the user.
4. **Done**, only on exit 0. "Your cartridge is ready. You can take the card out now." The app then
   deletes its temporary DEST and control directory.

Progress weights per `make` step are Software's choice. They are recorded, and the bar never goes
backwards. **Cancel** is offered only before step 3. After `make` starts, interrupting is the
user's pull, which §6 covers. The app never re-runs a step automatically.

**Elevation.** Raw device access needs administrator rights: UAC on Windows; an authorization
prompt on macOS. Only the one `tapectl make` child runs elevated, so there is one prompt per Make. The app
process, `ingest` and `tapectl cards` never run elevated. Software proposes the mechanism and records the exact
prompt text the user sees. Prompts are a G2 hesitation risk, not a failure in themselves.

## 5. Safety

- WP-14 §5 outranks the app. The app cannot widen what `tapectl` accepts.
- DEV passed to `make` is exactly the path the step-3 recheck printed.
- The app writes only inside its control directory and DEST parent. Tools write only DEST (ingest),
  their own report FILE, and the confirmed card (`make`).
- A `CARD_CHANGED` or I/O failure from `make` shows the pulled message. The app never relaunches
  `make` by itself.
- Closing the window during Making is refused with "Wait until the cartridge is finished." The OS
  may still force it. The next launch does not resume a job or delete anything except its own
  stale temporary directories, which it identifies by an app-owned marker file.

## 6. Messages (G3 and the common path)

These are defaults; Michael may change the wording (§8). A **child-origin** row comes from a real
child exit code plus a report ID, never from free text. An **app-origin** row (marked †) comes
from a named app event (P2V15-004): `DROP_NOT_FOLDER`, `SPAWN_FAILED`, `ELEVATION_DECLINED` or
`CARD_RECHECK_MISMATCH`. App-origin events are tested with real OS/UI controls. No shipping switch
fakes either kind. Every Problem state also has **Show details**, which shows
the raw stderr as copyable text for a grown-up.

| When | Message |
|---|---|
| † A file was dropped, or a mix of files and folders (all additions rejected, zero child calls) | Drop a folder of music, not single songs. |
| ingest: overage | This music is 3 min 12 s too long for a 60-minute cartridge. Take some songs out and drop the folder again. (Uses ingest's exact overage, in WP-14 A7 phrasing.) |
| ingest: protected file | "NAME" is copy-protected, so it can't go on a cartridge. Take it out of the folder. |
| ingest: unreadable/corrupt/unsupported file | "NAME" can't be used. Take it out of the folder. |
| ingest: non-audio file, nested folder, symlink, empty folder | The folder "NAME" has something in it that isn't music. Use a folder with only songs in it. |
| ingest: source too short, name collision, other source-named refusal | "NAME" can't be used. Take it out of the folder. |
| Card too small (`GEOMETRY`/capacity) | This card is too small. Use a bigger card. |
| Not offered / refused card | (Never reached: refused disks are not offered.) |
| `make`: `CARD_CHANGED` or device I/O error | The card was taken out before it was finished. Put it back in and press Make cartridge again. |
| `verify` finding | Something went wrong writing this card. Press Make cartridge to try again. |
| † Elevation declined (no `make` child started) | The computer said no, so the card wasn't changed. Press Make cartridge to try again. |
| † Card recheck mismatch (steps 1/3) | Back to Ready, with the card-line message (§2). |
| † A tool could not be started | Something went wrong. Nothing else on your computer was changed. |
| make: WAV_TRUNCATED after start | The music file changed while the cartridge was being made. Start over and drop the folder again. |
| make: exit3 safety refusal | This card can't be used right now. Check the card and try again. |
| Any other make failure | The cartridge wasn't finished. Start over and try again. |
| Any other ingest/discovery failure | Something went wrong. Nothing else on your computer was changed. |

NAME is the dropped folder's name or the file name. The app never shows full paths. Each G3 case
(too long, card too small, not a card, pulled mid-write, unreadable file, DRM file) is reachable
and independently tested. "Not a card" is satisfied by non-offering plus a refused-disk control.

## 7. Acceptance mapping

- **G1:** the §1 static check, plus a runtime trace showing no device opens by the app process.
- **G3:** every child-origin §6 row is driven by real tool outcomes on images or loop devices in CI,
  and every † row by a real OS/UI event. The pulled case uses a device-removal fixture, with a
  WP-14 A4 zero-foreign-write observation. `make` continuity uses the §3 swap/reinsert controls.
- **G4:** screens are checked against §2. No element enumerates tracks, files, folders or cards.
- **G5:** install and run from the build artifact on each D2 platform. Unsigned is acceptable. Exact
  OS builds are recorded.
- **G2:** Michael's witnessed unaided run (D6) after G1/G3/G4/G5 pass on an exact head.
- **§3 additions:** Verification-authored tests, with negative controls, before the app's exact-head
  disposition. Required controls include:
  - `make` is byte- and outcome-equivalent to separate provision/load/verify;
  - one device open;
  - report exclusivity, nonce, and no-follow;
  - a preflight refusal creates only the report;
  - an overage exact fit vs one frame over, and equal IDs with different excesses;
  - `cards` OS-view candidate recognition versus make exact safety recognition, including
    byte-invalid candidates and a bare CRC ending `55 AA`;
  - stderr wording changes leave the app result unchanged.

Real-card G2 waits on WP-14 physical A6 and WP-16 acceptance. App authoring and implementation may
overlap them under the host-tool rule.

## 8. Michael's taste items (defaults stand unless changed)

1. **Cartridge length is fixed at 60 minutes**, with no length choice. Alternative: a C-30/C-60/C-90
   chooser. That adds a choice, and a choice moves toward a list.
2. **Folders only.** Single dropped songs are refused (§2).
3. **The §6 wording.**
4. **One card at a time** instead of a picker.

## 9. Out of scope

Playback or preview; track, file or card lists; editing order after a drop; tags or artwork;
label art; `dup`, `promote`, `respool` or `record` in the app; resuming an interrupted Make; any
network use; signing or notarization; an installer beyond the build artifact; firmware, hardware
or engine changes; WP-38.
