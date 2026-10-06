# WP-14 `tapectl` on real cards — contract (PM-issued, P2-R1)

**Status:** ISSUED 5 October 2026 (ADR-163); amended 6 October (ADR-164), resolving Q1–Q11 and
P2V-001…004; ADR-165 corrects the P2V-005 bare-image CRC/signature collision. Normative for both leads. Michael approved E-1's FAT16 default on 5 October Pacific time;
see the exact supplemental erratum and integrity manifest in [SPEC-ERRATA.md](SPEC-ERRATA.md). Changing this file after issue is a PM decision recorded here, in `docs/DECISIONS.md`
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

**Verify-only candidate recognition (P2V-001/Q3; P2V-005/ADR-165).** Let
`entries_nonzero` mean any nonzero byte in LBA 0 bytes 446–507, and
`signature` mean bytes 510–511 equal `55 AA`. Use this target-kind table:

| Target | Candidate MBR predicate | If false |
|---|---|---|
| Regular file (image) | `entries_nonzero` | Bare TAPEFS image, judged only by the engine |
| Whole device | `entries_nonzero OR signature` | `NOT_PROVISIONED`, exit 2 |

A bare superblock's CRC occupies 508–511 and **can** end in `55 AA`.
A signature alone therefore does not classify a regular file as an MBR.
Zero partition entries plus `55 AA` in a file take the bare path even if those
bytes came from an empty/destroyed MBR: a failed engine mount reports the normal
`MOUNT <TAPE_ERR_…>` finding, exit 1, rather than `MBR_LAYOUT`. This is the
explicit ambiguity rule, not a new acceptance of a whole-card layout.
The corresponding whole device still reaches `MBR_LAYOUT`, with no partition
view/mount for zero entries; bare-device operation is not supported.

Any nonzero partition-entry byte routes either target to §4.1 even with a
damaged signature. This preserves required type, extent and signature findings
on layouts with surviving entries. A regular file whose partition entries have
all been destroyed cannot be distinguished from a bare image by the MBR signature
alone; its engine findings remain visible. Host code does not parse TAPEFS magic,
CRC, validity or engine structures to make this classification.

Recognition is read-only, never permission to write. Other commands retain
exact recognition. §5 safety still runs first on devices; after it passes, a
candidate goes to §4.1 rather than `NOT_PROVISIONED`. Unreadable LBA 0 is an
I/O failure, not bare fallback.

**Device paths.** The user always names the device; `tapectl` never selects one.

| Platform | Accepted | Refused (exit 3, `REFUSE_NOT_WHOLE_DEVICE`) |
|---|---|---|
| Linux (CI only) | `/dev/sdX`, `/dev/mmcblkN` | partitions (`/dev/sdX1`, `/dev/mmcblkNp1`), anything else |
| macOS | `/dev/diskN` or `/dev/rdiskN` (raw I/O always uses `rdiskN`) | `diskNsM` slices, APFS synthesized disks |
| Windows 10 | `\\.\PhysicalDriveN` | drive letters, volume GUID paths |

A device that is not a provisioned layout is refused by every command except `provision` and
candidate-layout `verify` below (exit 2, `NOT_PROVISIONED`). `tapectl` never infers that a card should be provisioned.

## 3. `provision`

```
tapectl provision TARGET --label L [--length-s S] [--uuid HEX32 --epoch E] [--image-bytes N] [--erase DEV]
```

- `--label`: UTF-8, 1–32 bytes, no NUL. Longer is exit 2, never truncated.
- `--length-s`: default 3600 (C-60).
- `--uuid` and `--epoch` are given together or not at all. Given, output is byte-deterministic (the
  WP-11 rule). Omitted, `tapectl` is the caller that owns entropy: UUID from the OS CSPRNG
  (`getrandom` / `SecRandomCopyBytes` / `BCryptGenRandom`), epoch from the wall clock as u32 seconds.
  Both are printed on stdout as exactly two lines: `uuid <32 lowercase hex>` and
  `epoch <decimal>`, in that order. Neither line is printed when supplied. This is the only place
  WP-14 uses a clock or randomness.
- `--image-bytes N` creates or truncates an image file to N bytes; required for an image, refused for a
  device.
- `--erase DEV` is **required for a device** and must repeat the device path exactly. A mismatch is
  exit 3, `REFUSE_ERASE_NOT_CONFIRMED`, before any write.

**Order of work:** every §5 safety rule first (zero writes on refusal); then `GEOMETRY_OK` for the
partition-2 block count (exit 1, `TAPE_ERR_GEOMETRY`, zero writes); then zero LBA 0 if it is not
already zero; then partition 2 via `tape_format`; then partition 1; then the MBR last, flushing after
each. **The MBR is the identity of
the card and is written last**. Interrupted outcomes (P2V-004):

| Cut | Permitted result |
|---|---|
| Before the zero-MBR invalidation is durable | Old card, or not provisioned if zero landed |
| After durable invalidation, before final MBR lands | Not provisioned |
| Final MBR landed, including before its flush returns | Complete new card: earlier barriers made both partitions durable |
| Successful final flush | Complete new card |

A failed OS write/flush never reports success; unknown durability is evaluated against the same
outcomes. A re-run may complete an unprovisioned card. No old-card-preservation oracle applies
after destructive provisioning begins.

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

Partition 1 is **FAT16, type 0x0E (FAT16 LBA), 16 MiB, 2 KiB clusters**. Verification's published
paper review `6837102` confirms the geometry; Michael approved the default. Partition 2 remains at
LBA 34816. No engine-visible offset, structure, CRC or API changes. FAT32 at 16 MiB cannot conform;
paper compatibility is not witnessed OS readability. See [the erratum](SPEC-ERRATA.md) for the
frozen-bundle overlay and exact-byte independent confirmation required before Product integration.

Partition 1 contents:
- Volume label `DIGITALTAPE`. FAT timestamps use `--epoch` interpreted as UTC. Clamp values below
  1980-01-01 00:00:00 UTC to that instant; encode other u32 epochs as UTC calendar fields, flooring
  seconds to the FAT 2-second resolution. Preserve the original u32 epoch in TAPEFS; no rejection
  or host-timezone-dependent bytes (P2V-003).
- One file, `README.TXT`, CRLF line endings, including after the fourth line, exactly:

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

**Read-only commands on devices (Q11).** `play`, `scrub` and `dump` open devices read-only
and bind NULL write; bare and provisioned images retain their WP-11 access behavior. `verify` is
read-only on every target. Our exact partition 1 may remain mounted for read-only access if the OS
allows it. Any required unmount applies only to that partition; an unmount/dismount failure refuses
with `REFUSE_FOREIGN_MOUNT`, exit 3. No command bypasses §5.

**A2 round-trip bytes (P2V-003).** “WP-11 tail rule” means the accepted render semantics, not a
new tolerance: canonical 44-byte WAV header, exact frame count and exact samples at 1×, including
the last frame. No added silence, missing last frame or padding allowance. Use the ten unchanged
WP-11 references and generated full C-60. Record cadence remains WP-11's 1024-frame feed with
service-until-done before each feed (Q1); changing cadence is deferred to the Q-P2-1 decision.
A9 measures the resulting time; it does not gate it.

**`load` capacity (A7).** Before any write, if the source has more frames than
`nominal_length_s × 44 100`, exit 2 with the overage in plain words, e.g.
`Too long by 3 min 12 s for a 60-minute cartridge`. Round the excess up to whole seconds;
omit zero minutes/seconds parts. Describe whole-minute lengths as `N-minute`, otherwise `N-second`.

### 4.1 `verify TARGET`

Read-only. The engine binding has a **NULL write callback** (the WP-36 pattern), and `tapectl` opens the
target read-only. It runs:
1. Candidate/provisioned targets: §3.1 layout and partition 1 type, start and size. Partition 2 must extend to
   the device's last sector.
   Emit each applicable layout finding once, in table order: `MBR_LAYOUT`, `PARTITION_TYPE`,
   `PARTITION_TRUNCATED`. Type-byte and past-end mismatches are excluded from `MBR_LAYOUT`;
   all other §3.1 mismatches (including signature or ending short) raise it. Multiple independent
   defects may raise multiple findings. Mount only if entry 2 starts at 34816, has a nonzero count,
   and its entire 64-bit extent is in the target; otherwise stop after layout findings, exit 1.
   Never shrink a truncated view or issue an out-of-range read. Wrong type alone does not prevent
   a safe mount. No `NOT_PROVISIONED` replaces a reached candidate finding.
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
Emit a `MOUNT` line for each failed side, A before B; a degraded B may also emit
`SIDE_B_DEGRADED`. Remaining engine findings follow the table order; full-read errors are in
side A/B and frame order. A failing mount is not subsequently read.

## 5. Disk safety (A4) — outranks everything else

Every command that opens a **device** evaluates these rules first, in this order, and refuses with
**exit 3, zero writes and zero write-mode opens**. Each refusal prints its ID and one plain sentence.

| ID | Refuse when |
|---|---|
| `REFUSE_NOT_WHOLE_DEVICE` | The path is not a whole disk in §2's platform form |
| `REFUSE_NOT_REMOVABLE` | The OS reports the disk as neither removable media nor an SD-class bus, or it is virtual media (loop, VHD, disk-image/virtual-interface device) |
| `REFUSE_TOO_LARGE` | Capacity exceeds **128 GiB** (2³⁷ bytes) |
| `REFUSE_SYSTEM_DISK` | Any partition on the disk holds the running OS, a boot volume or swap |
| `REFUSE_FOREIGN_MOUNT` | Any volume on the disk is mounted, unless it is a §3.2 partition 1 (exact layout match). `tapectl` may unmount that one, and only that one, before raw access |
| `REFUSE_ERASE_NOT_CONFIRMED` | `provision` without a matching `--erase` |

**Facts, then policy.** The implementation splits into a probe that gathers a `device_facts` record
(whole-device, removable, bus, size, holds-OS, mounted volumes) and a pure policy function over that
record. **A test seam** may inject facts from a file, **compiled only when `TAPECTL_TEST` is defined**.
The shipped binary must not contain it; Verification checks symbol and configuration-string absence,
with the test build as its negative control.

**Test-only route (P2V-002/Q2).** `tapectl-test` accepts Linux `/dev/loopN` only through the
facts seam. Shipped `tapectl` still refuses the same loop path as `REFUSE_NOT_WHOLE_DEVICE`.
Test-only injected virtual media must be paired with a shipped-binary virtual refusal control.
The symbol is `tapectl_test_facts_seam`; `TAPECTL_TEST_FACTS` names the file. One `key=value`
per line: `whole`, `removable`, `sd_bus`, `bytes`, `holds_os`, `layout_ok`, plus repeatable
`mounted=<partition 1..4, or 0 unknown>:<where>`. Missing facts are refusing: `holds_os=1`,
others 0. The seam applies only to device paths, never ordinary images. `tapectl-test probe DEV`
prints actual platform facts in this format plus `refusal=<ID>`. Binaries are
`build/host/tapectl` and `build/host/tapectl-test` (Windows: `.exe`).
Observation adapters must capture actual candidate policy, opens, binding, writes and native flush
results. Synthetic traces only self-test the oracle; they do not dispose a candidate. Fault-injection
controls (no-op flush, non-NULL binding, referenced-chunk read failure) remain test-only and absent
from the shipped binary. Their expectations belong to Verification; transport belongs to Software.

## 6. Port requirements

`host/port/` provides one port for images and devices:
- **64-bit byte offsets** everywhere (`pread`/`pwrite`, or `ReadFile`/`WriteFile` with `OVERLAPPED`).
- **Durable flush:** `fsync` (Linux), `fcntl(F_FULLFSYNC)` (macOS), `FlushFileBuffers` (Windows).
  On macOS image files require `F_FULLFSYNC`. On raw devices try `F_FULLFSYNC`; only an
  explicit unsupported-descriptor result (`ENOTTY`/`ENOTSUP`) permits fallback to
  `ioctl(DKIOCSYNCHRONIZECACHE)`. No plain `fsync`/cache-only fallback there. Flush returns
  success only after the chosen OS barrier succeeds; log which barrier ran. Any other failure
  propagates. Native calls and failure/no-op controls must be observed on each platform (Q6).
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
