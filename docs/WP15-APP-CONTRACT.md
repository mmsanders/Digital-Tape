# WP-15 one-window app — contract APP-1

**ISSUED by PM for independent preflight, 15 October 2026 PDT, ADR-182.** Package criteria are
[WP-15](PACKAGES/WP-15.md) G1–G5. This document controls where that wording is ambiguous. Changes
require PM issuance and paired issue updates. No engine, format or frozen-spec change is licensed.
**Michael's taste items** (§8) carry defaults. They may change wording or defaults without a new
round until Software starts the build. Build starts only after Verification's preflight and a
Software issue.

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
before the user touches the card. Each new drop reruns ingest over every folder; the previous
DEST is deleted first. The app deletes only directories it created.

**Label.** UTF-8, 1–32 bytes, as `tapectl provision --label` requires. The box stops accepting
input that would exceed 32 bytes, never truncates silently, and is never pre-filled. **Make
cartridge** is enabled only with a non-empty label, a successful check, and exactly one card.

**Card line.** The app runs `tapectl cards` (§3) every 2 s while not Making:
- 0 offered cards: "Put a card in."
- 1 card: "Card ready (64 GB)." The size uses the OS capacity in decimal GB, rounded.
- 2 or more: "Leave just one card in the computer."

There is no card picker: one-card-at-a-time replaces a list and removes wrong-card choices. A disk
that `tapectl` refuses is never offered.

## 3. Tool additions (host only, additive)

These are new host CLI surface. They need independent tests before acceptance, under the host-tool
parallel-authoring rule. Existing commands and outputs are unchanged when the new flags are absent,
so INGEST-1 Stage1 and accepted WP-14 evidence are unaffected.

**`tapectl cards`.** It enumerates whole disks and runs the shipping §5 probe and policy for each.
The erase-confirmation rule is excluded, because it is not a disk fact. It prints one JSON object
per line, only for disks with no refusal: `{"path","bytes","provisioned"}`. `provisioned` is §2's
exact layout recognition. Exit 0, even when there are no cards. It uses no write-mode opens and
makes zero writes. It never prints refused disks or their facts, and it adds no test seam to the
shipped binary. Verification covers each §5 refusal as "not printed", with a shipped-binary
negative control.

**`--report FILE`** on `ingest`, `tapectl provision`, `tapectl load` and `tapectl verify`. When
given, the tool appends JSON lines to FILE:
- progress: `{"t":"progress","step":S,"done":N,"total":M}`. Counts only, no rates or times
  (guardrail 09 spirit: the caller owns the clock).
- a refusal or failure: `{"t":"refusal","id":ID,"subject":P}`.

Refusal and failure IDs are a closed list per tool, issued with the tool's existing named
reasons: WP-14 §5/§7 IDs, `verify` findings, and an INGEST-1 refusal-reason list that Software
proposes and Verification checks against §2–§6. `subject` is the logical path (ingest) or the
device path (tapectl). Progress is monotonic and may be sparse. The app never parses free-text
stderr for decisions; stderr is kept for the details pane.

## 4. Make cartridge

The steps run in this order, and each step starts only after the previous one exits 0:

1. **Recheck.** Rerun `tapectl cards`. The same single card (same path and bytes) must still be the
   only one. Otherwise return to Ready with the card message.
2. **Confirm erase.** A modal box: "Everything on this card will be replaced with your music."
   Buttons: **Replace** / **Keep card**. This is the only confirmation.
3. **Provision.** Run `tapectl provision DEV --label L --length-s 3600 --erase DEV`. DEV is the
   path from step 1. It is never typed, edited or chosen by the user.
4. **Load.** Run `tapectl load` with the ingested `audio.wav` onto DEV, in the WP-14 form.
5. **Verify.** Run `tapectl verify DEV`. Only exit 0 and `OK` counts as success.
6. **Done.** "Your cartridge is ready. You can take the card out now." The app then deletes its
   temporary DEST.

Progress weights per step are Software's choice. They are recorded, and the bar never goes
backwards. **Cancel** is offered only before step 3. After the erase starts, interrupting is
the user's pull, which §6 covers. The app never re-runs a step automatically.

**Elevation.** Raw device access needs administrator rights: UAC on Windows; an authorization
prompt on macOS. Only the `tapectl` device children run elevated. The app process and `ingest`
never do. Aim for one prompt per Make. Software proposes the mechanism and records the exact
prompt text the user sees. Prompts are a G2 hesitation risk, not a failure in themselves.

## 5. Safety

- WP-14 §5 outranks the app. The app cannot widen what `tapectl` accepts.
- DEV passed to provision, load or verify is exactly a path `tapectl cards` printed for this Make.
- No step writes outside its temporary DEST and the confirmed card.
- If the card disappears or changes between steps, stop and show the pulled message. Never
  continue to the next step.
- Closing the window during Making is refused with "Wait until the cartridge is finished." The OS
  may still force it. The next launch does not resume a job or delete anything except its own
  stale temporary directories, which it identifies by an app-owned marker file.

## 6. Messages (G3 and the common path)

These are defaults; Michael may change the wording (§8). Each message comes from an exit code
plus a report ID, never from free text. Every Problem state also has **Show details**, which shows
the raw stderr as copyable text for a grown-up.

| When | Message |
|---|---|
| A file was dropped, not a folder | Drop a folder of music, not single songs. |
| ingest: overage | This music is 3 min 12 s too long for a 60-minute cartridge. Take some songs out and drop the folder again. (Uses ingest's exact overage, in WP-14 A7 phrasing.) |
| ingest: protected file | "NAME" is copy-protected, so it can't go on a cartridge. Take it out of the folder. |
| ingest: unreadable/corrupt/unsupported file | "NAME" can't be used. Take it out of the folder. |
| ingest: non-audio file, nested folder, symlink, empty folder | The folder "NAME" has something in it that isn't music. Use a folder with only songs in it. |
| ingest: source too short, name collision, other source-named refusal | "NAME" can't be used. Take it out of the folder. |
| Card too small (`GEOMETRY`/capacity) | This card is too small. Use a bigger card. |
| Not offered / refused card | (Never reached: refused disks are not offered.) |
| Card pulled or changed mid-Make, or device I/O error | The card was taken out before it was finished. Put it back in and press Make cartridge again. |
| `verify` finding | Something went wrong writing this card. Press Make cartridge to try again. |
| Elevation declined | The computer said no, so the card wasn't changed. Press Make cartridge to try again. (If declined before step 3; otherwise the pulled-message rule applies.) |
| Any other failure | Something went wrong. Nothing else on your computer was changed. |

NAME is the dropped folder's name or the file name. The app never shows full paths. Each G3 case
(too long, card too small, not a card, pulled mid-write, unreadable file, DRM file) is reachable
and independently tested. "Not a card" is satisfied by non-offering plus a refused-disk control.

## 7. Acceptance mapping

- **G1:** the §1 static check, plus a runtime trace showing no device opens by the app process.
- **G3:** every §6 row driven by real tool outcomes on images or loop devices in CI. The pulled case
  uses a device-removal fixture, with a WP-14 A4 zero-foreign-write observation.
- **G4:** screens are checked against §2. No element enumerates tracks, files, folders or cards.
- **G5:** install and run from the build artifact on each D2 platform. Unsigned is acceptable. Exact
  OS builds are recorded.
- **G2:** Michael's witnessed unaided run (D6) after G1/G3/G4/G5 pass on an exact head.
- **§3 additions:** Verification-authored tests, with negative controls, before the app's exact-head
  disposition.

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
