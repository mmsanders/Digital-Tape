# WP-14 native A6 capture, #423 load diagnosis and reload wording — Software #425/#428

**Status:** corrected Software method (#428, fourth correction after Verification #173), 14 October 2026 UTC. **Not normative, not acceptance,
not ready for a card until Verification #146 passes the corrected method.** Verification #167
(`df637f7`) found four false passes in #426's first head `1fbe762`. Verification #171 (`112557e`)
then found three more in `f5b4f1c`: an ended process, a closed and reused FileObject, and a
duplicate tracer step. Verification #172 (`ad3dae7`) found one more in `0dd869a`: a read and an
OpEnd that both lacked `IrpPtr` were joined through an empty key. Verification #173 (`7afc98f`) found
one more in `418138e`: one completion of two overlapping requests reset the ambiguity, so a reused
`IrpPtr` took the leftover completion. §3 shows all nine now rejected.
Final Windows provision/load/reinsert/verify/A+B/A9 and README are **complete** (#167, #168);
nothing here asks for another load, dump, pull or README. WP-14 is held only on physical native A6.
Input main `56bfdc5ad17dcfcdb97960a9dabe112beb8cf992`; tested release
[`wp14-tapectl-5e2df5aaf23e`](https://github.com/mmsanders/Digital-Tape/releases/tag/wp14-tapectl-5e2df5aaf23e).
Tooling: [`tools/wp14-capture/`](../tools/wp14-capture/). No `engine/`, `host/`, port, verifier
tree, oracle, workflow, ruleset or gate change.

| Shipped binary (unchanged, from the release) | SHA-256 |
|---|---|
| `tapectl-macos` (arm64, macOS ≥ 26) | `e7550d8bedbb0c784fd528c387a87cca2bad8d1b411c39217d25377329bb0beb` |
| `tapectl-windows.exe` (x64) | `82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9` |
| `tapectl-linux` (rehearsal only) | `4d8c97a44f163bcd513c98c0903db6a01418001f169cfd6aa126823f6f7a785c` |

## 1. What a capture can show

`verify` mounts both sides, and mounting reads the TAPEFS mirror superblock in the card's
last sector: bytes **[capacity − 512, capacity)**, i.e. [62,537,072,128, 62,537,072,640) on
the owned card. `a6check.py` returns PASS 0, FAIL 1, INPUT-ERROR 2 or HELD 3, reports
every reason, and is PASS only when all of the following hold for the bound process:

| Property | How it is bound | Missing → | Contradicted → |
|---|---|---|---|
| Executable | `--exe` hashes to `--sha256`; the traced process is `tapectl` (DTrace `execname`, strace `execve`, ETW Process image) and not `tapectl-test` | HELD | FAIL |
| Process | every record is for `--pid`; DTrace `-c` target equals it. ETW reads are attributed only through `IssuingThreadId`/`TTID` while that thread **and** its process are both alive (Process/Thread Start…End replayed in time order). A record from a thread outside that observed life is unattributed and FAILs | — | FAIL |
| Result join (ETW) | a FileIo read gets a native result only from the OpEnd with the **same valid, nonzero `IrpPtr`**, only if it was the sole request pending on that `IrpPtr`, and only if the OpEnd carries both `NtStatus` and `ExtraInfo`. Missing, empty, zero or non-numeric identities never join. A request of any type that arrives while another is outstanding on the same `IrpPtr` makes that lifecycle ambiguous, and it stays ambiguous until **every** outstanding request has completed; requests added meanwhile are ambiguous too. Reuse only after the lifecycle fully resolves is legitimate | HELD | — |
| Object (ETW) | a FileIo read's path is what its FileObject names **at that read** (Create until Cleanup/Close). A closed, reused or foreign object never counts as the target, whatever an earlier mapping said | — | FAIL |
| Device | `--geometry` (diskutil info / Get-Disk / byte count) equals `--capacity`, shows 512-byte sectors and names `--target` (and `--disk`); ETW command line names `\\.\PhysicalDriveN` | HELD | FAIL |
| Full last sector | the union of bytes that successful reads **returned**, from calls whose offset is above 4,294,967,295, covers all 512 bytes contiguously; each call's **native result** is captured | HELD (no native result) | FAIL (one byte, short, failed, gap, below 2³²) |
| No writes | no write of any kind by the process reaches the target | — | FAIL |
| Result | saved stdout exactly `OK`; exit 0 wherever recorded (`--exit-code`, traced exit), and consistent | HELD | FAIL; disagreement → INPUT-ERROR |
| Tracer complete | every occurrence of every tracer step exits 0 (a failed attempt is never hidden by a later success; a step recorded twice is HELD as ambiguous); DTrace stderr has no drop/error and the trace ends `A6 end`; ETW header `EventsLost` = `BuffersLost` = 0; strace ends `+++ exited with` | HELD | FAIL |

**Honest limits.**
- **Opening.** DTrace and strace record the open flags, so a read-only open is shown. Kernel
  ETW `FileIo_Create` has no DesiredAccess. On Windows the claim is therefore limited to
  *observed reads and no observed writes*; the open mode is not shown.
- **Result on Windows.** `DiskIo` records carry offset, size, disk and issuing thread but no
  status. A native result exists only if `FileIo` Read + OpEnd (`NtStatus`, `ExtraInfo`)
  records appear for the device handle. Whether kernel FileIo covers a `\\.\PhysicalDriveN`
  handle is **unknown until a real Windows trace is seen**. If only DiskIo appears, the
  verdict is **HELD**. "Completion plus verify OK" is an indirect argument for independent
  review, not a captured `ReadFile` result.
- **Writes.** A read-only witness cannot show physical writes above 4 GiB. #158's per-command
  software A6 coverage is unchanged.
- **Not authorized.** An injected interposer (`iocap`) is not authorized and is no longer
  supported. Test facts, `tapectl-test`, rebuilt binaries and OS-protection changes are
  never used.

## 2. Recipes: off-card rehearsal first, then one read-only card verify

Verification #146 decides whether and when Michael runs any of this and supplies the exact
commands. Every stage keeps all raw files. **Clean stop:** if a tracer refuses, errors or
reports loss, or `a6check.py` returns anything but PASS, stop, keep everything, send it to
#146, and A6 stays held. Never retry on the card a different way.

**Image size and space.** The rehearsal image is **4,296,015,872 bytes** (4 GiB + 1 MiB).
Its last sector, at 4,296,015,360, is already above 2³², and the worst case if it is not
sparse is about 4.3 GB. Check free space first, then record apparent and allocated size.
Do not assume a 62.5 GB file is sparse.

### 2.1 macOS (arm64, macOS ≥ 26): in-box DTrace — not yet run on any Mac

From the folder with the verified `tapectl`, `a6-macos.d` and `a6check.py` from this commit:

```sh
shasum -a 256 tapectl a6-macos.d a6check.py > a6-hashes.txt
{ sw_vers; uname -a; csrutil status; } > a6-versions.txt 2>&1    # csrutil status only reads
df -k . > a6-space.txt                                              # need > 4.3 GB free
./tapectl provision a6-rehearsal.img --label A6-REHEARSAL --uuid 00112233445566778899aabbccddeeff \
    --epoch 1760000000 --image-bytes 4296015872 > a6-rh-provision.txt 2>&1; echo "provision $?" >> a6-rh-provision.txt
stat -f '%z' a6-rehearsal.img > a6-rh-geometry.txt
{ ls -ls a6-rehearsal.img; du -k a6-rehearsal.img; } > a6-rh-allocation.txt
sudo dtrace -q -s a6-macos.d -o a6-rh.trace -c './tapectl verify a6-rehearsal.img' \
    > a6-rh-out.txt 2> a6-rh-dtrace-err.txt; echo "dtrace $?" > a6-rh-tracer-exits.txt
rm a6-rehearsal.img
python3 a6check.py --format dtrace --trace a6-rh.trace --pid <target= in line 1> \
    --capacity 4296015872 --geometry a6-rh-geometry.txt --target a6-rehearsal.img \
    --exe tapectl --sha256 e7550d8bedbb0c784fd528c387a87cca2bad8d1b411c39217d25377329bb0beb \
    --stdout a6-rh-out.txt --diagnostics a6-rh-dtrace-err.txt --tracer-log a6-rh-tracer-exits.txt
```

Card stage, only after Verification accepts the rehearsal output. Identify the card as
#386 does, then run:

```sh
diskutil info /dev/diskN > a6-card-info.txt
sudo dtrace -q -s a6-macos.d -o a6-verify.trace -c './tapectl verify /dev/diskN' \
    > a6-verify-out.txt 2> a6-verify-dtrace-err.txt; echo "dtrace $?" > a6-verify-tracer-exits.txt
python3 a6check.py --format dtrace --trace a6-verify.trace --pid <target=> --capacity <Disk Size bytes> \
    --geometry a6-card-info.txt --target /dev/rdiskN --exe tapectl --sha256 e7550d8b…(as above) \
    --stdout a6-verify-out.txt --diagnostics a6-verify-dtrace-err.txt --tracer-log a6-verify-tracer-exits.txt
```

Notes on these commands:
- `-c` starts tapectl under dtrace, so the `target=` PID is tapectl's and no call precedes
  tracing. Use it only for this read-only verify: dtrace kills a process it started if
  dtrace itself is interrupted.
- `dtrace $?` is dtrace's exit status. Tapectl's own exit comes from the traced `exit`
  record, so the Mac has no separate `--exit-code`.
- tapectl opens `/dev/rdiskN` for `/dev/diskN`.
- If DTrace is unavailable under SIP, that is a clean stop: report it, and A6 on macOS stays
  held.

### 2.2 Windows 11 x64: in-box WPR + tracerpt — not yet run on any Windows host

Administrator PowerShell, in the folder with the verified `tapectl.exe` and `a6check.py`:

```powershell
Get-FileHash .\tapectl.exe, .\a6check.py -Algorithm SHA256 | Format-List | Out-File a6-hashes.txt
Get-ComputerInfo -Property OsName, OsVersion, OsBuildNumber | Out-File a6-versions.txt
(Get-Item C:\Windows\System32\wpr.exe, C:\Windows\System32\tracerpt.exe).VersionInfo | Format-List | Out-File -Append a6-versions.txt
wpr -profiles | Out-File a6-wpr-profiles.txt
Get-PSDrive -PSProvider FileSystem | Out-File a6-space.txt                 # need > 4.3 GB free
.\tapectl.exe provision a6-rehearsal.img --label A6-REHEARSAL --uuid 00112233445566778899aabbccddeeff --epoch 1760000000 --image-bytes 4296015872
(Get-Item a6-rehearsal.img).Length | Out-File -Encoding ascii a6-rh-geometry.txt
fsutil sparse queryflag a6-rehearsal.img | Out-File a6-rh-allocation.txt
wpr -start FileIO -start DiskIO -filemode;   "wpr-start $LASTEXITCODE" | Out-File -Encoding ascii a6-rh-tracer-exits.txt
$p = Start-Process .\tapectl.exe -ArgumentList 'verify', 'a6-rehearsal.img' -NoNewWindow -Wait -PassThru `
     -RedirectStandardOutput a6-rh-out.txt -RedirectStandardError a6-rh-err.txt
wpr -stop a6-rh.etl *> a6-rh-wpr-stop.txt;   "wpr-stop $LASTEXITCODE" | Out-File -Append -Encoding ascii a6-rh-tracer-exits.txt
tracerpt a6-rh.etl -o a6-rh.xml -of XML -y *> a6-rh-tracerpt.txt; "tracerpt $LASTEXITCODE" | Out-File -Append -Encoding ascii a6-rh-tracer-exits.txt
"pid $($p.Id) exit $($p.ExitCode)" | Out-File a6-rh-pid.txt
Remove-Item a6-rehearsal.img
```

Check the rehearsal with `--format etw-xml --target a6-rehearsal.img --disk <the internal
disk's number> --geometry a6-rh-geometry.txt --exit-code <exit>`. The other arguments are as
on the Mac. Keep `a6-rh-wpr-stop.txt` and `a6-rh-tracerpt.txt` as diagnostics.

**What the rehearsal settles first:**
1. Whether tracerpt XML has the field names the parser expects. A mismatch reads
   INPUT-ERROR or HELD, never PASS.
2. Whether the header loss counters are present.
3. Whether FileIo reads are attributed to tapectl's thread.

The card stage repeats the same steps with `Get-Disk -Number N | Format-List Number,
FriendlyName, SerialNumber, BusType, Size, LogicalSectorSize, PhysicalSectorSize,
PartitionStyle` as geometry and `'verify', '\\.\PhysicalDriveN'`. The ETL holds every
process's file and disk activity during the window: close other applications first, and
keep the ETL beside the XML.

## 3. Validation actually performed: Linux x86_64 container only

No Mac and no Windows host was available, so this round validates **no native macOS or
Windows format**. `a6-macos.d` has not been compiled or run, and real tracerpt XML has not
been seen. The synthetic fixtures check the parser's logic only.
`python3 tools/wp14-capture/selftest.py` (97 cases; 91 without `TAPECTL`) repeats everything below. Add
`TAPECTL=<released tapectl-linux>` to include the real captures.

| Input | Kind | Result |
|---|---|---|
| `rehearse-linux.sh` with the released `tapectl-linux` (hash-checked first), 4,296,015,872-byte image | **Real** strace capture; image mechanics | PASS. 86,016 bytes allocated (`allocation.txt`); full raw set in `fixtures/linux-4g1m/` |
| Same script at 62,537,072,640 bytes | Space guard | **Refused before provisioning**: 30.7 GB free < 62 GB worst case (`fixtures/linux-62g/space.txt`) |
| `fixtures/linux-shipped-verify.strace` (#425's 62.5 GB capture, no `execve` traced) | Real, kept unchanged | Now **HELD**: the image cannot be bound |
| Verification #167's six files, byte-identical with their published SHA-256 (`fixtures/verification-167/`) | Verification's controls | one-byte → FAIL (coverage); nonzero-exit → FAIL (traced exit 1); tracer-error → FAIL (drops); etw-lost → FAIL (EventsLost 17); both good shapes → HELD (no end marker; no loss counters / DiskIo-only) |
| Verification #171's files, byte-identical with their own side files (`fixtures/verification-171/`) | Verification's controls | their baseline → PASS; process-ended → FAIL (outside observed life); foreign FileObject reuse → FAIL (object names `C:\helper.img`); `wpr-start 1` then `0` → FAIL (occurrence 1 of 2) |
| Verification #172's files, byte-identical with their own side files (`fixtures/verification-172/`) | Verification's controls | their baseline → PASS; `IrpPtr` removed from Read and OpEnd → HELD (no valid `IrpPtr` on the request) |
| Verification #173's files, byte-identical with their own side files (`fixtures/verification-173/`) | Verification's controls | their baseline → PASS; reuse after one of two completions → HELD (overlapping requests in one unresolved lifecycle); missing `IrpPtr` → HELD |
| `fixtures/dtrace-good`, `fixtures/etw-good`: 76 cases (10 positives, 66 single-property faults) | **Synthetic** shapes | Each gives its stated verdict *and* its stated reason. The variants cover range, result, exit, stdout, tracer occurrences, loss, PID, process/thread lifetime, FileObject close/cleanup/reuse/reopen, IRP correlation (missing, empty, zero, invalid, orphan, competing, overlapping lifecycles with partial and full completion, reuse before and after resolution), process image, device, geometry, writes and timestamp order |

## 4. #423 bounded diagnosis

### 4.1 Authenticated facts

| Fact | Source |
|---|---|
| Mac C60 load: `real 1619.06`, `user 1.25`, `sys 35.46`; `155048 flushes via DKIOCSYNCHRONIZECACHE`, exit 0 | Verification-preserved `load-time.txt`, SHA-256 `8eeb00bbfdd318792932c62395d54f26196af8c3bac64ca6bd075a914f051439` (Mac bundle INVENTORY) |
| Mac provision: `real 0.14`, `9 flushes` | same bundle, `provision-time.txt` |
| Card/reader: 62,537,072,640 B, 512-byte blocks, USB, "SD Transcend" (macOS); Windows PhysicalDrive1 behind a TS-RDF5 reader | Mac `card-info.txt`; Verification #164 |
| Windows final uninterrupted C60 load: exit 0, **1677.7328603 s**, 155,048 `FlushFileBuffers`; reinsert, verify, A+B and README complete | Verification #167 [`P2-R1-WP14-FINAL-WIN-2026-10-14.md`](https://github.com/mmsanders/digital-tape-verification/blob/df637f7fb962a98b8698d16a531ceb0e8365c2a6/findings/P2-R1-WP14-FINAL-WIN-2026-10-14.md), #168 |
| Windows interrupted pulls: 495 … 141,678 `FlushFileBuffers` in 5.94 … 1530.58 s (automatic Invoke-Tape timing). Provisions take 0.137–0.381 s for 9 flushes; quiet baselines take 1.81–3.18 s for 202 | `observations.json.gz` in [#164's bundle](https://github.com/mmsanders/digital-tape-verification/tree/6899cf7b56decfbb9bf8fef6c5f2825513697c37/findings/P2-R1-WP14-PULLS-2026-10-14-evidence), SHA-256 `eaed0732…b229` |

The **corrected capacity method** is Verification's
[P2V-006 method B](https://github.com/mmsanders/Digital-Tape-Verification/blob/7f19fc20247e87754dcb28c2d7b5e68b1bf9a2ed/findings/P2-R1-WP14-PULL-METHOD-2026-10-12.md).
It provisions a fresh 5400 s label per trial: 1817 chunks against the 2 + 1212 needed. That
removes the original 3600 s baseline + C60 infeasibility. The earlier hand-stopped Windows
figure (2352 s) is superseded by the final automatic 1677.73 s. Interrupted pulls are used
below only as a *rate per cycle*, never as a successful load time or A9.

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
- **One write + barrier cycle averages ~10.5–10.8 ms on both OSes (observation).**
  Mac: 1619.06 s / 155,048 = 10.44 ms. Windows final load: 1677.73 s / 155,048 = 10.82 ms.
  The ten interrupted pulls fit `seconds = −0.71 + 10.74 ms × flushes` (10.55–11.99 ms per
  cycle, 495–141,678 cycles), so there is no late-card slowdown. The pull-based projection
  (≈28 min) matched the final 27.96 min.
- **Host work is small.** Same binary, same C60 on images in this container: tmpfs 3.21 s
  real (0.29 user, 2.90 sys); disk-backed virtio 43.0 s real (0.37 user, 12.6 sys). These
  are host-image numbers. An image `fsync` says nothing about a card's cache-flush latency.
- **Not known: how each cycle splits between the eight 512-byte writes and the barrier.**
  Every load cycle has the same 8:1 ratio, so no existing measurement separates them. A
  two-point *model* from the provision (≈111 writes + 9 barriers in 0.14 s) would put
  ≈1.2 ms on each write and ≈1 ms on each barrier. That is an estimate, not a measurement:
  the provision's access pattern differs and 0.14 s has two significant figures. This round
  claims no write/barrier split and no latency distribution.

### 4.4 Measuring the split (not requested)

The final Windows load is complete, so no capture can ride it now, and #428 requests no extra
full-C60 profiling run. #426's `profile` mode and `load-profile-macos.d` are withdrawn. Their
latency fields came from unvalidated ETW decoding and an unrun D script. If PM later wants
the split, it needs its own scoped, independently reviewed measurement. A short partial load
on a fresh provision would probably do, with a validated tracer.

### 4.5 Next optimization: recommendation

The split decides the order. Until a measurement is scoped (§4.4), both options stay
proposals:

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

Neither change is licensed by #425 or #428, and neither is the target-system <30 s copy, which is
a separate duplicate path that remains mandatory.

## 5. Reload refusal and recovery: proposed wording (proposal only; no allocation or wording change licensed)

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
