# WP-14 native A6 capture, #423 load diagnosis and reload wording — Software #425

**Status:** Software method and proposal, 14 October 2026 UTC. **Not normative, not acceptance.**
Verification #146 decides whether the capture method is adequate and owns every
physical disposition; PM #384 decides the diagnosis follow-ups. Input main
`b0d0847b85cee6eac4b2624f9835052a950b902e`; tested release
[`wp14-tapectl-5e2df5aaf23e`](https://github.com/mmsanders/Digital-Tape/releases/tag/wp14-tapectl-5e2df5aaf23e)
(Product `5e2df5aaf23e9ed0e230c444a40650da9459ddb2`, engine `d96b4245…`). Tooling:
[`tools/wp14-capture/`](../tools/wp14-capture/). Nothing here changes `engine/`, `host/`, a
verifier tree, a workflow or the contract.

| Shipped binary (unchanged, from the release) | SHA-256 |
|---|---|
| `tapectl-macos` (arm64, macOS ≥ 26) | `e7550d8bedbb0c784fd528c387a87cca2bad8d1b411c39217d25377329bb0beb` |
| `tapectl-windows.exe` (x64) | `82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9` |
| `tapectl-linux` (rehearsal only) | `4d8c97a44f163bcd513c98c0903db6a01418001f169cfd6aa126823f6f7a785c` |

## 1. What the A6 capture shows, and what it does not

`verify` mounts both sides. Mounting reads the TAPEFS mirror superblock, the last block
of partition 2, which §3.1 ends at the card's last sector: absolute byte offset
**capacity − 512**. On the owned card (62,537,072,640 bytes on both machines,
`card-info.txt` in the [Mac bundle](https://github.com/mmsanders/digital-tape-verification/tree/6899cf7b56decfbb9bf8fef6c5f2825513697c37/findings/P2-R1-WP14-MAC-2026-10-12-evidence)
and PULL01 `disks-before.txt`) that is **62,537,072,128**, above 4,294,967,295.

A capture PASSes `a6check.py verify` only if, **for tapectl's own PID**: the target is opened,
never for writing; no write reaches it; and a read covering capacity − 512 at an offset
above 4,294,967,295 completes with its full length. The record carries the
offset/length/result, PID, executable SHA-256, OS build and device geometry.

It does **not** show the physical card's writes above 4 GiB. A read-only witness cannot
observe them. Per-command software A6 coverage (Verification #158) stays as it is.
CI virtual-device captures and PowerShell helper reads are not this evidence. A capture
taken by tapectl-test, or with test facts, is invalid and must not be attempted on a card.

## 2. Recipes

Run each recipe in two stages. The **rehearsal** checks the tracer on this exact machine
against a sparse image file. It is mechanics only, never physical evidence. The **card**
stage is one read-only `verify` of the card already provisioned for #386. Neither stage
loads, provisions, erases or pulls the card. Never disable System Integrity Protection,
Defender or any other OS protection, rebuild or replace the executable, or use test facts.

**Clean stop:** if the tracer refuses to start, prints an error, reports drops, or
`a6check.py` returns `INPUT-ERROR`/`FAIL`, stop. Keep every file and the exact message
and send them to #146. A6 stays held. Do not try another way on the card.

### 2.1 macOS (arm64, macOS ≥ 26): DTrace, in-box

The tracer is the in-box `/usr/sbin/dtrace` syscall provider. It needs `sudo`. It watches
from the kernel side and injects nothing into tapectl. `-c` makes dtrace start tapectl
itself, so `$target` is exactly tapectl's PID and no call happens before tracing.
`a6-macos.d` also records tapectl's own exit status. Use `-c` only for this read-only
verify, because dtrace kills a process it started if dtrace is interrupted.

From the folder holding the verified `tapectl` plus `a6-macos.d` and `a6check.py`
(from this commit):

```sh
shasum -a 256 tapectl a6-macos.d a6check.py > a6-hashes.txt
sw_vers > a6-macos-build.txt; uname -m >> a6-macos-build.txt
# Rehearsal: a sparse 62,537,072,640-byte image on the internal disk (a few MB used).
./tapectl provision a6-rehearsal.img --label A6-REHEARSAL --uuid 00112233445566778899aabbccddeeff \
    --epoch 1760000000 --image-bytes 62537072640
sudo dtrace -q -s a6-macos.d -o a6-rehearsal.trace -c './tapectl verify a6-rehearsal.img' \
    > a6-rehearsal-out.txt 2> a6-rehearsal-dtrace-err.txt
head -1 a6-rehearsal.trace            # A6 trace tool=dtrace target=<PID>
python3 a6check.py verify --format dtrace --trace a6-rehearsal.trace --pid <PID> \
    --capacity 62537072640 --target a6-rehearsal.img --exe tapectl --sha256 e7550d8bedbb0c784fd528c387a87cca2bad8d1b411c39217d25377329bb0beb
rm a6-rehearsal.img
```

Continue only if that PASSes. Then insert the card and re-identify it as #386 does:

```sh
diskutil list external physical > a6-disks.txt
diskutil info /dev/diskN > a6-card-info.txt     # Disk Size bytes, Device Block Size 512, Removable, USB
sudo dtrace -q -s a6-macos.d -o a6-verify.trace -c './tapectl verify /dev/diskN' \
    > a6-verify-out.txt 2> a6-verify-dtrace-err.txt
python3 a6check.py verify --format dtrace --trace a6-verify.trace --pid <PID from line 1> \
    --capacity <Disk Size bytes> --target /dev/rdiskN --exe tapectl --sha256 e7550d8bedbb0c784fd528c387a87cca2bad8d1b411c39217d25377329bb0beb > a6-verify-check.json
```

tapectl opens `/dev/rdiskN` when given `/dev/diskN` (contract §2), so `--target` names the
raw node. `a6-verify-out.txt` must read `OK`; the trace's `op=exit status=0` line is
tapectl's exit. `python3` is only for convenience: Verification can run `a6check.py` on the
returned files instead.

**If DTrace is unavailable** (for example `dtrace: failed to initialize` or syscall probes
refused under SIP), that is a clean stop. One alternative exists for Verification to
choose, not for the operator to improvise. The CI capture transport `iocap.dylib` was built
in the same run as the shipped binary (SHA-256
`eff62a9ec63359be7a42476a5842fdcf465738f7d06319d3bef4197b7d2fd503`, `build-info-macos.json`).
It is an *injected* user-space interposer (`DYLD_INSERT_LIBRARIES`), not a kernel
observation, and it is not a release asset. Running it would be
`DYLD_INSERT_LIBRARIES=$PWD/iocap.dylib IOCAP_LOG=$PWD/a6-iocap.jsonl ./tapectl verify /dev/diskN`,
checked with `--format iocap`. Whether an injected transport satisfies "bound to tapectl
rather than a test shim" is #146's call.

### 2.2 Windows 11 x64: WPR + tracerpt, in-box

The tracer is in-box Windows Performance Recorder kernel tracing (`wpr.exe`), exported by the
in-box `tracerpt.exe`, from the Administrator PowerShell the procedure already uses. Nothing
is installed and no policy changes. The `DiskIo` records come from the disk stack below
tapectl; `Process`/`Thread` rundown binds the issuing thread to tapectl's PID and image.

```powershell
Get-FileHash .\tapectl.exe, .\a6check.py -Algorithm SHA256 | Format-List | Out-File a6-hashes.txt
Get-ComputerInfo -Property OsName, OsVersion, OsBuildNumber | Out-File a6-windows-build.txt
Get-Command wpr, tracerpt | Out-File a6-tools.txt
# Rehearsal: sparse image on the internal disk.
.\tapectl.exe provision a6-rehearsal.img --label A6-REHEARSAL --uuid 00112233445566778899aabbccddeeff --epoch 1760000000 --image-bytes 62537072640
wpr -start FileIO -filemode
$p = Start-Process .\tapectl.exe -ArgumentList 'verify', 'a6-rehearsal.img' -NoNewWindow -Wait -PassThru `
     -RedirectStandardOutput a6-rehearsal-out.txt -RedirectStandardError a6-rehearsal-err.txt
wpr -stop a6-rehearsal.etl
"pid $($p.Id) exit $($p.ExitCode)" | Out-File a6-rehearsal-pid.txt
tracerpt a6-rehearsal.etl -o a6-rehearsal.xml -of XML -y
Remove-Item a6-rehearsal.img
```

Judge the rehearsal with `a6check.py verify --format etw-xml --trace a6-rehearsal.xml
--pid <pid> --capacity 62537072640 --target a6-rehearsal.img --stdout a6-rehearsal-out.txt
--exit-code <exit> --exe tapectl.exe --sha256 82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9`. Its FileIo records show file offsets. Then, with the card inserted and
re-identified as #386 does:

```powershell
Get-Disk -Number N | Format-List Number, FriendlyName, SerialNumber, BusType, Size, LogicalSectorSize, PhysicalSectorSize, PartitionStyle | Out-File a6-card-info.txt
wpr -start DiskIO -start FileIO -filemode
$p = Start-Process .\tapectl.exe -ArgumentList 'verify', '\\.\PhysicalDriveN' -NoNewWindow -Wait -PassThru `
     -RedirectStandardOutput a6-verify-out.txt -RedirectStandardError a6-verify-err.txt
wpr -stop a6-verify.etl
"pid $($p.Id) exit $($p.ExitCode)" | Out-File a6-verify-pid.txt
tracerpt a6-verify.etl -o a6-verify.xml -of XML -y
```

Check: `a6check.py verify --format etw-xml --trace a6-verify.xml --pid <pid> --capacity <Size>
--disk N --stdout a6-verify-out.txt --exit-code <exit> --exe tapectl.exe --sha256 82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9`. Kernel `DiskIo` read records carry
`ByteOffset`, `TransferSize`, `DiskNumber` and the issuing thread, but **no status field**.
The result is therefore the completion record plus `verify` printing exactly `OK` with exit 0.
That is only possible if both superblock copies were read valid: a failed or wrong mirror
read raises `NEEDS_REPAIR` or `MOUNT`. `a6check.py` requires those two inputs for a status-less record.

The ETL holds every process's disk and file activity during the short window: close other
applications first. Return the ETL as well as the XML.

## 3. Validation actually performed (this container: Linux x86_64 only)

| Check | Kind | Result |
|---|---|---|
| Released `tapectl-linux`, hash-checked against `SHA256SUMS`, `verify` of a provisioned sparse 62,537,072,640-byte image under `strace -f -T` | Real capture of the exact shipped Linux binary; **image, not physical** | PASS. Two 512-byte reads at 62,537,072,128 (mount A, mount B), read-only open, zero writes. Kept as `fixtures/linux-shipped-verify.strace` (SHA-256 `c49765d0…ffe2`) |
| `selftest.sh` controls on that capture: wrong PID, missing mirror read, offset truncated to 32 bits (2,397,498,880), failed call (`-1 EIO`), short read, write-mode open, read on another file, capacity ≤ 4 GiB, executable hash mismatch | Negative controls | each FAILs (exit 1) |
| Same parser on `synthetic-*` fixtures in the DTrace, iocap and tracerpt-XML shapes, each with wrong-PID, failed-call, truncated-offset, wrong-disk, helper-process, foreign-thread, missing-`OK`, exit-status-disagreement and unreadable-input controls | **Synthetic format checks**, not captures | good cases PASS; controls FAIL (1) or INPUT-ERROR (2) |
| `TAPECTL=… selftest.sh` live rehearsal: provision + strace + judge in one run | Image rehearsal | PASS |

**Not validated here:** `a6-macos.d` has not been run, because no Mac is available. Its D
syntax, probe names (covered with `zdefs`) and output have not been compiled or observed.
`tracerpt`'s XML has not been seen either, because no Windows host is available. The
parser targets the documented kernel MOF field names. The first real rehearsal on each
machine is therefore the format check: a mismatch reads `INPUT-ERROR` or `FAIL`, never
PASS. Run `tools/wp14-capture/selftest.sh` to repeat everything above.

## 4. #423 bounded diagnosis

### 4.1 Authenticated facts

| Fact | Source |
|---|---|
| Mac C60 load: `real 1619.06`, `user 1.25`, `sys 35.46`; `155048 flushes via DKIOCSYNCHRONIZECACHE`, exit 0 | Verification-preserved `load-time.txt`, SHA-256 `8eeb00bbfdd318792932c62395d54f26196af8c3bac64ca6bd075a914f051439` (Mac bundle INVENTORY) |
| Mac provision: `real 0.14`, `9 flushes` | same bundle, `provision-time.txt` |
| Card/reader: 62,537,072,640 B, 512-byte blocks, USB, "SD Transcend" (macOS); Windows PhysicalDrive1 behind a TS-RDF5 reader | Mac `card-info.txt`; Verification #164 |
| Windows interrupted pulls: 495 … 141,678 `FlushFileBuffers` in 5.94 … 1530.58 s (automatic Invoke-Tape timing). Provisions take 0.137–0.381 s for 9 flushes; quiet baselines take 1.81–3.18 s for 202 | `observations.json.gz` in [#164's bundle](https://github.com/mmsanders/digital-tape-verification/tree/6899cf7b56decfbb9bf8fef6c5f2825513697c37/findings/P2-R1-WP14-PULLS-2026-10-14-evidence), SHA-256 `eaed0732…b229` |

The **corrected capacity method** is Verification's
[P2V-006 method B](https://github.com/mmsanders/Digital-Tape-Verification/blob/7f19fc20247e87754dcb28c2d7b5e68b1bf9a2ed/findings/P2-R1-WP14-PULL-METHOD-2026-10-12.md).
It provisions a fresh 5400 s label per trial: 1817 chunks against the 2 + 1212 needed. That
removes the original 3600 s baseline + C60 infeasibility. The earlier Windows full-load
figure (2352 s) was stopped by hand late and is not used. Interrupted pulls are used below
only as a *rate per cycle*, never as a successful load time or A9.

### 4.2 Call shape: deterministic, the same on every platform

The released `tapectl-linux` loaded the canonical C60 (SHA-256 `c7369c6f…495d`) onto a
62,537,072,640-byte image under `strace -c`. It made exactly **1,240,321 `pwrite`, all 512
bytes, and 155,048 `fsync`**, plus 155,042 WAV-input `read` calls. That is the same 155,048
barriers macOS and Windows reported. Source explains the shape. tapectl feeds 1024
frames, then services until done (contract §4, Q1). `engine/src/record.c` writes one
512-byte block per `dev_write` and puts one barrier behind each drained batch. So every
feed is **8 single-block writes + 1 barrier**: 155,040 feed cycles + 8 commit/promote
barriers.

### 4.3 Where the time goes

- **CPU is ~2 % of the Mac load.** 1.25 s user + 35.46 s sys out of 1619.06 s is 2.27 %.
  For about 97.7 % of the wall time tapectl was off-CPU, waiting inside OS calls. Almost
  all of those are card writes and barriers; the 155k internal-SSD WAV reads were not
  timed separately.
- **One write + barrier cycle costs ~10.5 ms, on both OSes, the whole way through.**
  Mac: 1619.06 s / 155,048 = 10.44 ms. Windows: the ten pulls fit
  `seconds = −0.71 + 10.74 ms × flushes`, 10.55–11.99 ms per cycle, from 495 to 141,678
  cycles. There is no slowdown late in the card. Projected from the rate (an estimate, not
  A9): a full Windows C60 load is about 155,048 × 10.74 ms ≈ 28 min.
- **Host work is small.** Same binary, same C60 on images in this container: tmpfs 3.21 s
  real (0.29 user, 2.90 sys); disk-backed virtio 43.0 s real (0.37 user, 12.6 sys). These
  are host-image numbers. An image `fsync` says nothing about a card's cache-flush latency.
- **Not yet known: how each ~10.5 ms cycle splits between the eight 512-byte writes and the
  barrier.** The existing data cannot separate them, because every load cycle has the same
  8:1 ratio. A two-point model from the provision (≈111 writes + 9 barriers in 0.14 s)
  suggests ≈1.2 ms per synchronous 512-byte write and ≈1 ms per barrier, i.e. writes
  dominate. **That is a model estimate only.** The provision's access pattern differs and
  0.14 s has two significant figures. It matters, because it decides which change pays off.

### 4.4 Optional capture alongside the required final Windows success load

These steps leave the required witness unchanged: same load command, Invoke-Tape timing
and outputs. They need no extra load. If either step interferes, skip it.

1. **CPU vs wall** (read-only, does not touch the card or the process). Start a second
   PowerShell soon after the load begins. Run it once, wait 60 s, run it again:
   `Get-Process tapectl | Select-Object Id, StartTime, TotalProcessorTime, @{n='t';e={Get-Date -Format o}} | Out-File -Append a6-load-cpu.txt`
2. **A 60-second kernel latency window.** In that second window:
   `wpr -start DiskIO -filemode`, wait about 60 s, then `wpr -stop a6-load-window.etl` and
   `tracerpt a6-load-window.etl -o a6-load-window.xml -of XML -y`. Stopping WPR does not
   affect tapectl. `a6check.py profile --format etw-xml --trace a6-load-window.xml --pid <Id>
   --disk N` then gives the card-side service-time distribution for writes and flushes
   across about 5,600 cycles. That is the write/barrier split §4.3 lacks.

macOS needs no new load. If a load is required there in future anyway, `load-profile-macos.d`
records the same split from a second Terminal (never with `-c`/`-p`). It has not been run in #425.

### 4.5 Next optimization: recommendation

Measure first (§4.4 item 2, optional, rides the required witness). Then:

- **If the barrier dominates:** make a **host-only record-cadence change**. tapectl keeps
  calling `tape_feed` until the caller-owned ring is full before it services, and gives the
  engine a larger ring. One 512 KiB chunk would cut C60 barriers from 155,048 to roughly
  1,200; the 64 KiB minimum ring alone cuts them about 16×. There is no engine or format
  change and no write coalescing. It **does change contract §4 (Q1, the 1024-frame
  cadence)**, which is a PM decision, and needs **Verification tests first**: identical
  media bytes and A2 round trip across cadences, the unchanged pull/crash outcome mapping,
  and a barrier-count bound.
- **If the 512-byte synchronous writes dominate:** cadence alone leaves 1.24M writes, about
  25 min at ≈1.2 ms each. Then the necessary step is **multi-block device writes from the
  engine record path**. The `tape_dev` callback already takes a block count. That is engine
  behaviour under Q-P2-1/ADR-168, and needs a **spec delta (engine-api §7 / tapefs §8 as
  PERFORMANCE-PLAN lists) and independent tests first**. Port-level coalescing stays
  forbidden by contract §6.

Neither change is licensed by #425, and neither is the target-system <30 s copy, which is
a separate duplicate path that remains mandatory.

## 5. Reload refusal and recovery: proposed wording (design only)

**Reproduced here** with the released Linux binary on an image. A full C60 on a 3600 s
label occupies all 1212 chunks. A later `load` of `quiet.wav`, or of C60 again, exits 1:

```
tapectl: tape_feed(g_t, g_pcm + (size_t)done * 2u, n - done, &acc): TAPE_ERR_CARTRIDGE_FULL
```

The image's SHA-256 was identical before and after, and `verify` was still `OK`: no write,
old data intact. The cause is by design. `load` records Side B into **fresh** chunks and
publishes only at commit, so the old recording stays whole until the new one is complete.
A replacement therefore needs free room for the whole new source *while* the old one
exists. A full card has none, however short the new source. That is different from A7
overlength, where the source is longer than the label, which already refuses before any
write with exit 2. The message above is also a raw C expression (`CHECK(#call)`).

Proposal (exact text and exit codes are PM's to issue; Verification tests first):

| Case | When | Proposed message | Exit |
|---|---|---|---|
| Too long (A7, unchanged) | source frames > label × 44,100 | `Too long by 3 min 12 s for a 60-minute cartridge` | 2 |
| **Not enough room to replace** (new) | before any write: `tape_status().free_chunks` < ⌈source frames / 131,072⌉ | `Not enough free room to load this and keep the old music safe until it finishes. Free now: 0 s. Needed: 4 s. To start over, erase the card with: tapectl provision <card> --erase <card>` | 2 |
| Ran out part-way (residual) | engine `TAPE_ERR_CARTRIDGE_FULL` mid-feed | `The card ran out of room part-way. Nothing was changed: the old recording is still there. (engine: TAPE_ERR_CARTRIDGE_FULL)` | 1 |

Design rules:
- Keep old data. Never add automatic erase, `--replace`, or any path that frees the old
  recording before the new one commits.
- The only recovery command is today's explicit, confirmed `provision --erase`, named in
  the message. `reset-b`/`respool` cannot free room on a just-loaded card, because Sides A
  and B share its chunks.
- The precheck uses only public engine counts. The same refusal moves earlier, before any
  write, with no engine change; the mid-feed path stays as the backstop.
- Changing engine-failure lines from a C expression to an operation name affects stderr
  that tests may read. Verification confirms what its oracles match before any wording
  change.

This needs a WP-14 contract amendment (new refusal row and message) and tests. No
implementation is done or licensed by #425.
