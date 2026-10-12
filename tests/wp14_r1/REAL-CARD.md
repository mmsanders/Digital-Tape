# Michael's WP-14 real-card checklist — delivery for Product #386

**Awaiting tested release, not script-ready:** E-1 is approved and ADR-164 issued.
Software must still supply the exact tested binary release and SHA-256 for each
platform; those values are not available in #146. Fill them before execution.
P2V-005 is resolved by ADR165; the CRC witness is a package regression.
This is one owned PNY card, not media qualification. Provision erases that card.
No WP-05 acquisition is authorized.

Record before running:

- Exact tested Product commit, binary SHA-256 and compiler/build configuration.
  Software must supply immutable release URLs/asset names for both platform
  binaries at the final independently disposed head. Match those hashes locally
  using `shasum -a 256 ./tapectl` (macOS) and
  `Get-FileHash .\tapectl.exe -Algorithm SHA256` (Windows). Do not proceed on a
  mismatch or substitute an unqualified informational-head build.
- macOS `sw_vers`; Windows `winver` version/build. Save output, not "latest".
- Card manufacturer part number, printed capacity, revision and CID, plus photos
  of the card/packaging. If the reader cannot expose CID, record unavailable;
  do not substitute its USB reader serial or claim qualification.
- Reader model/connection, device number, reported capacity. Remove other external
  disks and verify the selected number against the card inserted/removed.
- SHA-256 and frame count of canonical `C60.wav` (44.1 kHz, signed 16-bit stereo,
  158,760,000 frames) and a different short baseline `quiet.wav` from the published
  WP-11 source. Keep both off the card.

Optional reproducible non-musical C-60 fixture, from this repository's root:

```sh
python3 -c "import sys; sys.path.insert(0,'tests/wp14_r1'); from runner import make_c60; make_c60('C60.wav')"
shasum -a 256 C60.wav tests/golden/src/quiet.wav
```

## macOS: successful round trip

Use Terminal in the folder containing the tested `tapectl` and C60.wav.
Replace `diskN` only after identifying **your test card**:

```sh
sw_vers > macos-build.txt
diskutil list external physical > macos-disks.txt
diskutil info /dev/diskN > card-info.txt
```

If a foreign filesystem on your card is mounted, `tapectl` must refuse it.
Save that refusal. Use macOS's Disk Utility to unmount only your test card's
volumes before the intentionally destructive provision. A safety refusal is a
stop to recheck identity, never a reason to bypass the guard in the binary.

```sh
/usr/bin/time -p ./tapectl provision /dev/rdiskN --label PNY-C60 --length-s 3600 --erase /dev/rdiskN > provision.txt 2> provision-time.txt
echo $? > provision-exit.txt
/usr/bin/time -p ./tapectl load /dev/rdiskN C60.wav > load.txt 2> load-time.txt
echo $? > load-exit.txt
diskutil eject /dev/diskN
```

Both commands must return 0. Record printed UUID/epoch. Record wall times for A9;
they are measurements, not a pass/fail timing gate. Physically remove and reinsert,
recheck `diskutil list external physical` and update N if it changed. Close Finder
windows on the card. Allow the tool to unmount only its own recognized partition 1.

```sh
./tapectl verify /dev/rdiskN > verify.txt 2>&1
echo $? > verify-exit.txt
./tapectl dump /dev/rdiskN --side A -o A.wav
./tapectl dump /dev/rdiskN --side B -o B.wav
cmp C60.wav A.wav
cmp C60.wav B.wav
shasum -a 256 C60.wav A.wav B.wav > roundtrip-hashes.txt
```

Require verify 0/OK and exact canonical WAV bytes/length including the final frame,
with no tail tolerance. Check Finder shows `README.TXT`, its label and the exact four lines.
Save its bytes and a screenshot. `verify` is read-only; it must not repair the card.

## macOS: ten deliberate pulls mid-load

Make folders pull-01 through pull-10. For **each** attempt:

1. Reinsert, identify N again. Save pre-run outputs/card identity. Load the short
   baseline first so old/new audio are distinguishable; verify and dump both sides:

   ```sh
   ./tapectl load /dev/rdiskN tests/golden/src/quiet.wav
   ./tapectl verify /dev/rdiskN > before-verify.txt 2>&1
   ./tapectl dump /dev/rdiskN --side A -o before-A.wav
   ./tapectl dump /dev/rdiskN --side B -o before-B.wav
   ```

2. Start the C-60 load with `/usr/bin/time -p` as above, saving output/error/exit
   in that attempt's folder. Physically pull at ten different elapsed times spread
   across the previously measured load duration. Record the actual elapsed time
   and any printed progress. A pull after completion is **not** a mid-load trial;
   repeat that numbered trial. Do not infer an exact write/flush boundary from time.
3. Reinsert, recheck N, run verify with output and exit captured. Attempt both dumps
   with each exit captured; hash any produced WAV. Save these observations **before**
   any load, provision, reset or promote repairs/changes the state.
4. Record clean/NEEDS_REPAIR/degraded/mount/read findings exactly. Exit 1 by itself
   is not a crash-safety failure: WP-10 permits some recoverable intermediate states.
   Do not approve just because verify returns 0 either. Verification will map the
   observed state/audio to the published WP-10 permitted outcomes for record plus
   promote (including resumed stage states). An unreadable or unclassified result
   remains held. Retain the card unchanged for a failed/unclassified trial until
   Verification says which evidence to collect; do not overwrite it for the next.

Record one row per trial: attempt, prior/input hashes, pull elapsed/progress,
load exit, reinserted device, verify output/exit, A/B dump exits/hashes,
permitted-outcome mapping (filled by Verification), exclusions/notes.

After ten recorded trials, perform the successful C-60 round trip again and eject
the card for the Windows check. Timed manual pulls do not qualify atomicity or
exhaustively exercise all crash boundaries.

## Windows 10: verify the macOS card, then fresh provision/load

Use an elevated PowerShell in the tested executable's folder. Identify the card
by capacity/model/removal and confirm it is not the OS disk:

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber | Out-File windows-build.txt
Get-Disk | Format-List Number,FriendlyName,SerialNumber,Size,BusType,IsBoot,IsSystem | Out-File windows-disks.txt
$card = '\\.\PhysicalDriveN'
.\tapectl.exe verify $card *> windows-verify.txt
$LASTEXITCODE | Out-File windows-verify-exit.txt
.\tapectl.exe dump $card --side A -o windows-A.wav
$LASTEXITCODE | Out-File windows-A-exit.txt
.\tapectl.exe dump $card --side B -o windows-B.wav
$LASTEXITCODE | Out-File windows-B-exit.txt
Get-FileHash C60.wav,windows-A.wav,windows-B.wav -Algorithm SHA256 | Out-File windows-hashes.txt
```

Replace N before invoking. Require verify 0/OK, both dump exits 0 and identical
hashes/lengths against the **same input**. Confirm Explorer shows `README.TXT` and
save a screenshot/its contents. Do not format when Windows offers to format an
unknown partition. Preserve these cross-platform outputs before reprovisioning.

Then explicitly erase and provision this same identified test card using the
tested Windows 10 binary. If a foreign volume is mounted, save the refusal and
unmount only that card using Windows disk tools before retrying. Recheck N.

```powershell
$timer = [Diagnostics.Stopwatch]::StartNew()
.\tapectl.exe provision $card --label PNY-C60 --length-s 3600 --erase $card *> windows-provision.txt
$LASTEXITCODE | Out-File windows-provision-exit.txt
$timer.Stop(); $timer.Elapsed.TotalSeconds | Out-File windows-provision-seconds.txt
$timer.Restart()
.\tapectl.exe load $card C60.wav *> windows-load.txt
$LASTEXITCODE | Out-File windows-load-exit.txt
$timer.Stop(); $timer.Elapsed.TotalSeconds | Out-File windows-load-seconds.txt
```

Require both exits 0; save UUID/epoch. Use Windows **Safely Remove Hardware**,
physically remove/reinsert, identify N again, update `$card`, and run the same
verify/dump/hash commands above with fresh output filenames. Require exact input
hashes and lengths, verify 0/OK, and readable Explorer `README.TXT` with the exact
four CRLF lines. Save README bytes and screenshot for this new Windows cartridge.

For both OS runs, retain the tested native capture/trace artifact demonstrating
the TAPEFS mirror access at the reported card size minus 512 bytes, beyond
4,294,967,295. Card capacity alone is not evidence that this access occurred.
Record the binary hash, platform build and native call in that artifact; if
capture is unavailable, A6 remains held. Never enable test facts on a real card.

Save all records for Verification #146; Michael can also place the witness on
Product #386. Server 2025 CI is supplemental, not Windows 10 acceptance. Native
flush negative controls are separate requirements; this physical witness does
not by itself prove that they pass.
