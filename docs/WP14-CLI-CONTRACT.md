# WP-14 `tapectl` on real cards — contract (PM-issued, P2-R1)

**Status:** ISSUED 5 October 2026 (ADR-163) for the P2-R1 Software and Verification issues. Normative
for both. One item, **E-1** (§3.2), waits on Michael's approval of a `tapefs` §3 erratum; everything
else is settled. Changing this file after issue is a PM decision recorded here, in `docs/DECISIONS.md`
and on both issues. Package criteria: [WP-14](PACKAGES/WP-14.md). This contract **extends**
[the WP-11 contract](WP11-CLI-CONTRACT.md); every WP-11 rule and command holds unless a line below
changes it.

## 1. Scope and what does not change

- `tapectl` stays one C99 binary in `host/`. It composes the public engine API and reimplements no
  engine behaviour (guardrail 12).
- **`engine/` is byte-identical to main** (WP-14 A8). New port code lives in `host/port/`, not
  `engine/port/`. `engine/port/dev_file.c` stays as it is for the Phase 1 suites.
- **`tapectl` never parses TAPEFS structures.** Superblock, index and chunk judgments come from engine
  calls only. `tapectl` owns, and parses, only what the engine never sees: the MBR and partition 1.
- Every WP-11 golden and Phase 1 replay stays green. Bare WP-11 images keep working unchanged.

## 2. Targets and naming

A **target** is one of:

| Target | What it is | How `tapectl` recognises it |
|---|---|---|
| Bare image | A WP-11 image: a regular file that *is* the TAPEFS partition, no MBR | Regular file whose LBA 0 is not a §3.1 layout |
| Provisioned image | A regular file holding a whole card: MBR, partition 1, partition 2 | Regular file whose LBA 0 is a §3.1 layout |
| Device | A whole removable disk the user named | A path in the platform form below |

**Layout recognition is exact.** LBA 0 is a §3.1 layout only if bytes 510–511 are `55 AA`, partition
entries 1 and 2 match §3.1 field for field, and entries 3 and 4 are all zero. A bare image's LBA 0 is a
TAPEFS superblock, whose bytes 446–507 are reserved zero, so it can never match.

**Device paths.** The user always names the device; `tapectl` never selects one.

| Platform | Accepted | Refused (exit 3, `REFUSE_NOT_WHOLE_DEVICE`) |
|---|---|---|
| Linux (CI only) | `/dev/sdX`, `/dev/mmcblkN` | partitions (`/dev/sdX1`, `/dev/mmcblkNp1`), anything else |
| macOS | `/dev/diskN` or `/dev/rdiskN` (raw I/O always uses `rdiskN`) | `diskNsM` slices, APFS synthesized disks |
| Windows 10 | `\\.\PhysicalDriveN` | drive letters, volume GUID paths |

A device that is not a provisioned layout is refused by every command except `provision`
(exit 2, `NOT_PROVISIONED`). `tapectl` never infers that a card should be provisioned.

## 3. `provision`

```
tapectl provision TARGET --label L [--length-s S] [--uuid HEX32 --epoch E] [--image-bytes N] [--erase DEV]
```

- `--label`: UTF-8, 1–32 bytes, no NUL. Longer is exit 2, never truncated.
- `--length-s`: default 3600 (C-60).
- `--uuid` and `--epoch` are given together or not at all. Given, output is byte-deterministic (the
  WP-11 rule). Omitted, `tapectl` is the caller that owns entropy: UUID from the OS CSPRNG
  (`getrandom` / `SecRandomCopyBytes` / `BCryptGenRandom`), epoch from the wall clock as u32 seconds.
  Both are printed on stdout. This is the only place WP-14 uses a clock or randomness.
- `--image-bytes N` creates or truncates an image file to N bytes; required for an image, refused for a
  device.
- `--erase DEV` is **required for a device** and must repeat the device path exactly. A mismatch is
  exit 3, `REFUSE_ERASE_NOT_CONFIRMED`, before any write.

**Order of work:** every §5 safety rule first (zero writes on refusal); then `GEOMETRY_OK` for the
partition-2 block count (exit 1, `TAPE_ERR_GEOMETRY`, zero writes); then zero LBA 0 if it is not
already zero; then partition 2 via `tape_format`; then partition 1; then the MBR last, flushing after
each. **The MBR is the identity of
the card and is written last**, so an interrupted `provision` has the phase-dependent outcomes in §9; writing the final MBR before its flush can already leave a complete card. A re-run completes provisioning.

### 3.1 MBR layout

| Field | Value |
|---|---|
| Bootstrap 0–439 | zero |
| Disk signature 440–443 | first 4 bytes of the cartridge UUID |
| 444–445 | zero |
| Entry 1 | status 0x00; CHS start/end `FE FF FF`; type per §3.2; start LBA 2048; sectors 32 768 (16 MiB) |
| Entry 2 | status 0x00; CHS `FE FF FF`; type **0xDA**; start LBA 34 816; sectors = device sectors − 34 816 |
| Entries 3, 4 | zero |
| 510–511 | `55 AA` |

Both starts are 1 MiB aligned. Partition 2's block count must be at most 2³²−1; the §5 size ceiling
already guarantees it.

### 3.2 Partition 1 and approved erratum E-1

Partition 1 is **FAT16, type 0x0E (FAT16 LBA), 16 MiB, 2 KiB clusters**.
Michael approved E-1 on 5 October Pacific after Verification's paper review.
[The additive erratum](../spec/ERRATUM-E1.md) supersedes the frozen §3 filesystem
row; DRAFT-10 engine-visible bytes and partition 2's LBA 34816 stay unchanged.
FAT32 at 16 MiB cannot conform; the earlier universal OS-response claim is withdrawn.

Partition 1 contents:
- Volume label `DIGITALTAPE`. FAT timestamps from `--epoch`: UTC, clamp dates before 1980-01-01 to that date at 00:00:00, then round seconds down to the preceding even second. The engine's u32 epoch stays exactly the supplied value; clamping applies only to FAT fields.
- One file, `README.TXT`, CRLF line endings, exactly:

```
This is a Digital Tape cartridge.
Label: <label>
Please do not format or erase this card on a computer.
Use the Digital Tape app to load music onto it.
```

## 4. Other commands on any target

`load`, `dump`, `play`, `promote`, `reset-b`, `respool`, `record`, `scrub` behave exactly as WP-11 on
every target. On a provisioned target the engine sees partition 2 only. `format` stays bare-image only;
on a device or provisioned image it is exit 2, use `provision`.

**`load` capacity (A7).** Before any write, if the source has more frames than
`nominal_length_s × 44 100`, exit 2 with the overage in plain words, e.g.
`Too long by 3 min 12 s for a 60-minute cartridge`.

### 4.1 `verify TARGET`

Read-only. The engine binding has a **NULL write callback** (the WP-36 pattern), and `tapectl` opens the
target read-only. It runs:
1. Provisioned targets: §3.1 layout and partition 1 type, start and size. Partition 2 must extend to
   the device's last sector.
2. `tape_mount` Side A and Side B, cold, then `tape_get_info`.
3. `dump` both sides to nowhere, so every referenced block is read through the engine.

Exit 0 and `OK` if clean. Otherwise exit 1, one line per finding, from this closed list:

| Finding | Raised when |
|---|---|
| `MBR_LAYOUT` | §3.1 mismatch other than the next two |
| `PARTITION_TYPE` | Entry 1 or 2 has the wrong type byte |
| `PARTITION_TRUNCATED` | The device is shorter than entry 2 says |
| `MOUNT <TAPE_ERR_…>` | Either mount returns other than `TAPE_OK`, with the result name |
| `NEEDS_REPAIR` | `needs_repair` is true: one superblock copy is invalid |
| `SIDE_B_DEGRADED` | `side_b_valid` is false |
| `READ_ERROR SIDE <A\|B> FRAME <n>` | A device read fails during the full read |

`verify` reports only what the engine and the MBR can show. It does not judge standby index slots,
which are legitimately invalid after format and after a torn commit (`tapefs` §8.1).

## 5. Disk safety (A4) — outranks everything else

Every command that opens a **device** evaluates these rules first, in this order, and refuses with
**exit 3, zero writes and zero write-mode opens**. Each refusal prints its ID and one plain sentence.

| ID | Refuse when |
|---|---|
| `REFUSE_NOT_WHOLE_DEVICE` | The path is not a whole disk in §2's platform form |
| `REFUSE_NOT_REMOVABLE` | The OS reports the disk as neither removable media nor an SD-class bus |
| `REFUSE_TOO_LARGE` | Capacity exceeds **128 GiB** (2³⁷ bytes) |
| `REFUSE_SYSTEM_DISK` | Any partition on the disk holds the running OS, a boot volume or swap |
| `REFUSE_FOREIGN_MOUNT` | Any volume on the disk is mounted, unless it is a §3.2 partition 1 (exact layout match). `tapectl` may unmount that one, and only that one, before raw access |
| `REFUSE_ERASE_NOT_CONFIRMED` | `provision` without a matching `--erase` |

**Facts, then policy.** The implementation splits into a probe that gathers a `device_facts` record
(whole-device, removable, bus, size, holds-OS, mounted volumes) and a pure policy function over that
record. **A test seam** may inject facts from a file, **compiled only when `TAPECTL_TEST` is defined**.
The shipped binary must not contain it; Verification checks the symbol is absent, with a negative control.

## 6. Port requirements

`host/port/` provides one port for images and devices:
- **64-bit byte offsets** everywhere (`pread`/`pwrite`, or `ReadFile`/`WriteFile` with `OVERLAPPED`).
- **Durable flush:** `fsync` (Linux), `fcntl(F_FULLFSYNC)` (macOS), `FlushFileBuffers` (Windows).
  Flush returns success only after the OS call does.
- **A partition view** presenting partition 2 as the engine's `tape_dev`, `block_count` from entry 2.
- **No write coalescing in WP-14.** Each engine write call is issued in order before it returns.
  Batching waits on Q-P2-1 (plan §5); this keeps A3's evidence clean.

## 7. Exit status

| Code | Meaning |
|---|---|
| 0 | Success; `verify` clean |
| 1 | An engine result other than `TAPE_OK` (name on stderr), or a `verify` finding |
| 2 | Usage, WAV format, label, capacity, or `NOT_PROVISIONED` |
| 3 | Disk-safety refusal, zero writes |

## 8. Out of scope

GUI (WP-15), ingest (WP-16), `dup` on the desktop, warm start, write batching (Q-P2-1), label art in
partition 1, and any engine change. Adding a command or a finding is a PM change.

## 9. P2-R1 contract rulings (ADR-164, 6 October 2026 UTC)

These rulings supersede conflicting sentences above and in WP-14. They resolve
P2V-001…004 and Software Q1…Q11 as one issued delta.

### 9.1 Recognition and finding precedence (P2V-001, Q3/Q9)

All §5 disk-safety rules run first, including on read-only commands. Every command
except `verify` retains §2's exact recognition. For `verify` only, an LBA 0 is a
**candidate whole-card layout** if **any byte 446–507 is nonzero OR bytes 510–511
are 55 AA**. Thus a damaged signature with surviving partition entries still
reaches MBR validation, as does a signed MBR with a damaged/empty table. A bare
TAPEFS superblock has these reserved bytes zero and cannot match.

On images and devices alike, candidate recognition precedes `NOT_PROVISIONED`.
A candidate is validated against §3.1 and emits exit-1 findings:
- `PARTITION_TYPE` for each wrong entry-1/2 type;
- `PARTITION_TRUNCATED` if entry 2 extends past the actual end;
- `MBR_LAYOUT` for every other §3.1 mismatch, including signature, status, CHS,
  starts, unused entries or entry 2 ending before the actual end.
Report each applicable finding ID once in that order. Mount/read checks may proceed
only when the declared partition-2 extent is nonempty and fully in range; no
out-of-range callback is permitted. Missing or unsafe extents do not hide MBR findings.
A device with no candidate layout returns `NOT_PROVISIONED`, exit 2; an image
with no candidate layout takes the bare-image path.

For a safe partition view, report each failed cold mount in A-then-B order.
A degraded B may produce both `MOUNT TAPE_ERR_NO_VALID_INDEX` and
`SIDE_B_DEGRADED`. This is an engine judgment, not a host index parser.

### 9.2 Test devices and observations (P2V-002, Q2)

The shipped Linux binary still refuses `/dev/loopN`. The `TAPECTL_TEST` binary
may use exactly `/dev/loopN` as a whole-device test path with injected facts; no
production naming or disk-safety rule is weakened. Bind facts and observations to
the exact target path, candidate binary hash, build configuration and run ID.
Mounted-image/VHD test devices may use injected test facts on other CI platforms;
the shipped binary must refuse the real virtual-device probe result.

The agreed facts interface is the global test-only `tapectl_test_facts_seam`,
reading `TAPECTL_TEST_FACTS`: newline-separated `key=value`, keys `whole`,
`removable`, `sd_bus`, `bytes`, `holds_os`, `layout_ok` and repeatable
`mounted=<partition 1..4, or 0 for unknown>:<where>`. Missing fields default to
refusal (`holds_os=1`, others zero). The shipped binary has neither this symbol
nor the environment-variable string; the same absence check must reject the
test binary. `tapectl-test probe DEV` may print real facts plus `refusal=<ID>`.
A test facts file is not evidence that a real OS probe is correct.

Software supplies authenticated observations of real policy evaluation,
write-mode opens, writes, OS flush calls/results, NULL bindings and injected read
errors in Verification's published trace schema. Verification owns assertions
and causal controls. Synthetic traces establish only oracle self-tests; a
cached round trip establishes no medium durability.

### 9.3 Epoch, exact output and geometry (P2V-003, Q4/Q5/Q8)

All four README lines end with CRLF, including the last line. When identity is
generated, stdout contains `uuid <32 lowercase hex>` and `epoch <decimal>`,
one line each; when supplied, those identity lines are omitted.

There is no separately issued “WP-11 tail rule” permitting lost or padded frames.
A2 requires the same frame count and PCM bytes as the source; compare canonical
44-byte-header WAV outputs against canonicalized source WAVs. Unknown input WAV
chunks do not become output chunks. Preserve WP-11's accepted 1× render cadence
and final-frame behavior; no new tolerance or golden regeneration is authorized.
Any demonstrated conflict with the accepted WP-11 behavior is a finding to PM.

A7 overage is rounded up to whole seconds. Omit zero minute/second components;
describe a whole-minute length as `N-minute`, otherwise `N-second`.
Image geometry is checked before creating/truncating an existing image:
invalid geometry leaves its bytes and size unchanged.

### 9.4 Provision interruption outcomes (P2V-004)

| Interruption phase | Permitted visible result |
|---|---|
| Before initial MBR invalidation is durable | Old card intact, or unprovisioned if invalidation landed |
| After durable invalidation, before the final MBR write | Unprovisioned; a re-run may provision it |
| During/after the final MBR write, before its flush returns | Unprovisioned if identity did not land, or complete new card if it did |
| After successful final flush | Complete new card |

The engine's partition-2 interruption oracle remains DRAFT-10. A complete new
identity is allowed before the final flush because prior successful barriers
already made both partitions durable. No old identity may survive *after*
durable invalidation. Erroring writes/flushes have unknown persistence; report
failure and judge remount from durable bytes, never from cached state.
This does not qualify physical atomicity or allow MBR identity before data.

### 9.5 Port behavior and timing (Q1/Q6/Q7/Q10/Q11)

- Keep WP-11's 1024-frame feed/service cadence for this round. A9 is measured,
  not gated; 155,042 record flushes is a Software count, not a time measurement.
  No feed-until-full optimization or write coalescing is authorized here.
- On macOS images use `F_FULLFSYNC`. On raw devices try it, then only on
  `ENOTTY`/`ENOTSUP` use `DKIOCSYNCHRONIZECACHE`. Any other error fails;
  fallback success is required before flush returns success. Observe actual
  calls/results and kill a no-op-flush and a suppressed-error control.
- Linux may unmount only the exact matching README partition using `umount2`;
  failure returns `REFUSE_FOREIGN_MOUNT`, exit 3, before a write-mode open.
  macOS/Windows use the OS's unmount/dismount operation with the same boundary.
- Virtual block devices are not production removable media, even if an OS
  removable flag says otherwise. Refuse them with `REFUSE_NOT_REMOVABLE`
  unless an earlier §5 rule applies. Regular image-file use remains supported.
- On devices, `verify`, `play`, `scrub` and `dump` open read-only and bind
  a literal NULL write callback. Read-only commands need not unmount the matching
  README partition. Images preserve WP-11 opens except `verify`, which is
  read-only everywhere. Other disk-safety checks remain mandatory.

Windows Server CI is supporting port evidence; it is not Windows 10 acceptance.
The witnessed real-card script supplies Windows 10 and physical-card evidence.
