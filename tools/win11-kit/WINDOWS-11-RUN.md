# INGEST-1 Windows 11 collection: proposed one-run instructions (#461)

**NOT READY FOR MICHAEL pending exact-kit authentication.** Verification #204 must
first authenticate this exact kit, script and binaries, and then issue the run.
Until it does, nobody runs this. This document proposes; it accepts nothing. The
original 6126d04 kit, script pins, evidence and instructions are historical and
unchanged. Michael #447's old kit stays PAUSED.

## Exact pins

| Item | Value |
|---|---|
| Candidate (source of the binaries, the profile and the transport files `run_packet.py`, `observers.py`, `summarize_packet.py`) | `50bc4160f6da527da8c684d05264f99815aaa870` (#459, ingest 0.1.1), tree `ea0c9ae717a8478ca357fd01186f2a4d912a1193` |
| Collection script (its own source, **not** the candidate) | `tools/win11-kit/win11_packet.ps1` at Product commit `e1e06fc599177872b4f5d39d46f59c8952d1c108` (#463), SHA-256 `74e1af2cb91a3f9b418363941c48a60eee972481a32cbb9af22d8f3060318f9e`. It is the reviewed 6126d04/50bc416 script (`9d850667…`) with the two Verification #204 corrections only; every Process Monitor and transport pin is unchanged |
| Kit | `win11-kit.zip`, 2,604,482 bytes, SHA-256 `ffb0f78ac3980fa1bb130f0aff22d53ebb100ed3323a8e50ba62a6ee1819c865` |
| Shipping `ingest.exe` | 848,384 bytes, SHA-256 `d923613badda95baeb387d5415d5212a5dedb7c5c7144b21874479babd178f5b`, `ingest 0.1.1 INGEST-1 arithmetic-profile INGEST1-AP4` |
| Observation `observe/ingest.exe` | 956,928 bytes, SHA-256 `d544b6f5c82e653842625080a87ac63cb52353aaeca62494dd5d08eedb844d9a`, same version line, built with `--features observe` |
| Process Monitor (fetched by the script) | `ProcessMonitor.zip` SHA-256 `477754bf299c9e5b311c5666f7a4a48dfdb21265eaa8f0cca70ef9d9552e3a10`, valid Microsoft Authenticode signature |
| Built by | `win11-kit.yml` run 39104751447 attempt 1, job "build and publish the kit", `windows-latest`, Rust 1.97.0 (`rust-toolchain.toml`), `cargo build --release --locked` |

None of the old 6126d04 values apply: that kit was `32d6643c…`, with shipping
`0e1ef2cb…` and observation `97918d43…`. A run started with them stops at step 3.

**The Windows build is not byte-reproducible.** The same commit, toolchain and
workflow gave different exes in each Windows build:

| Build | Shipping | Observation |
|---|---|---|
| #459 CI | `eee301bb…` | (not recorded) |
| Superseded kit run 39103616467 | `84fa85e4…` | `542b91bb…` |
| This kit, run 39104751447 | `d923613b…` | `d544b6f5…` |

The profile files are identical across these runs. Nobody can rebuild these
pins from source, so they authenticate only the exact bytes in this kit. `KIT.json`
inside the zip records the same pins.

The prerelease `win11-kit-ingest-0.1.1-50bc4160f6da-r39103616467-1` is **superseded**.
Its kit is `d18b4655…`, and its rehearsal step failed on a harness exit-code bug, fixed
in `4bda3f5`. Do not use it.

## Transport and retention

- Kit: <https://github.com/mmsanders/Digital-Tape/releases/download/win11-kit-ingest-0.1.1-50bc4160f6da-r39104751447-1/win11-kit.zip>
  The release is <https://github.com/mmsanders/Digital-Tape/releases/tag/win11-kit-ingest-0.1.1-50bc4160f6da-r39104751447-1>,
  a prerelease tagged on the candidate, with `KIT-INVENTORY.json` (every member's
  name, size and SHA-256) and `SHA256SUMS`.
  Release assets do not expire. The run artifact `win11-kit-461` (ID 12127927028)
  is a backup copy only and expires on 2027-01-16.
- Script: <https://raw.githubusercontent.com/mmsanders/Digital-Tape/e1e06fc599177872b4f5d39d46f59c8952d1c108/tools/win11-kit/win11_packet.ps1>.
  The original `host/ingest/stage1/win11_packet.ps1` at the candidate (`9d850667…`) is historical
  and is not used.
- Both downloads are anonymous; no GitHub sign-in is needed.

## Prerequisites and host scope

- **Host:** one Windows 11 x64 client desktop or laptop (build 22000 or later).
  The script refuses Windows Server, other editions and non-x64 machines, unless the
  CI-only `-Rehearsal` switch is passed, and the Windows 11 run never passes it.
- **No card, no reader.** Remove every SD card and unplug every card reader before
  starting. The script opens no card or disk device itself. Its observer selftest
  makes one deliberate, read-nothing open of `\\.\PhysicalDrive0` to prove the
  observer sees forbidden opens.
- An Administrator PowerShell (Process Monitor needs it).
- Python 3.12. If it is missing, the script stops and names the
  `winget install -e --id Python.Python.3.12` command to install it, then you run the
  script again. The script installs nothing else outside its work folder.
- At least 25 GB free on the work drive (the census writes two 4 GiB WAVs).
- Internet access to github.com, codeload.github.com, raw.githubusercontent.com,
  download.sysinternals.com and PyPI.
- **Execution policy: the existing one, never overridden** (Verification #204).
  The command runs `powershell.exe -NoProfile -File` under whatever policy the
  machine already has. No `-ExecutionPolicy` flag, no policy change and no other
  way of running the file's contents. If PowerShell refuses to run the file because
  of the policy, stop there and report the exact error to Verification.

## Proposed run (NOT READY FOR MICHAEL pending exact-kit authentication)

In an Administrator PowerShell:

```powershell
$d = "$env:USERPROFILE\Downloads\DigitalTape-ingest"
New-Item -ItemType Directory -Path $d | Out-Null
$t = "win11-kit-ingest-0.1.1-50bc4160f6da-r39104751447-1"
Invoke-WebRequest -UseBasicParsing -OutFile "$d\win11-kit.zip" `
  -Uri "https://github.com/mmsanders/Digital-Tape/releases/download/$t/win11-kit.zip"
Invoke-WebRequest -UseBasicParsing -OutFile "$d\win11_packet.ps1" `
  -Uri "https://raw.githubusercontent.com/mmsanders/Digital-Tape/e1e06fc599177872b4f5d39d46f59c8952d1c108/tools/win11-kit/win11_packet.ps1"
(Get-FileHash "$d\win11-kit.zip" -Algorithm SHA256).Hash     # must be FFB0F78AC3980FA1BB130F0AFF22D53EBB100ED3323A8E50BA62A6EE1819C865
(Get-FileHash "$d\win11_packet.ps1" -Algorithm SHA256).Hash  # must be 74E1AF2CB91A3F9B418363941C48A60EEE972481A32CBB9AF22D8F3060318F9E
```

If either hash differs, stop and report it. Otherwise:

```powershell
powershell.exe -NoProfile -File "$d\win11_packet.ps1" `
  -Candidate 50bc4160f6da527da8c684d05264f99815aaa870 -Kit "$d\win11-kit.zip" `
  -ShippingSha256 d923613badda95baeb387d5415d5212a5dedb7c5c7144b21874479babd178f5b `
  -ObserveSha256 d544b6f5c82e653842625080a87ac63cb52353aaeca62494dd5d08eedb844d9a
```

`-Work` defaults to `C:\ingest-win11-work`, which must not exist yet. `-Out`
defaults to the Desktop.

## Stop behaviour and output

- **Guard stops** print `STOPPED: <reason>` in red and exit nonzero. In order:
  - Administrator, Windows 11 client, x64, and 25 GB free;
  - Python 3.12 present, and the work folder new;
  - the candidate's transport file hashes;
  - the shipping and observation hashes;
  - the Process Monitor hash and signature;
  - pip, `check_pins.py`, `asset.py` and `run_packet.py` (exit 1);
  - `summarize_packet.py` reporting a missing census record, an exit that differs
    from its descriptor, or a shipping/observation byte difference. The script
    then exits with the summarizer's own code, after its summary lines, and makes
    no zip; the packet stays under `-Work`.
- **Other failures do not all say `STOPPED`.** A policy refusal, a failed
  download or extraction, or another PowerShell error ends with PowerShell's own
  red error and a nonzero exit.
- **Only a run that ends with the three success lines below has produced a packet
  to send.** Anything else is a stop: report the whole output as printed, send no
  zip, and do not retry with changed values.
- **Success:** the last lines are `PACKET: <Desktop>\ingest-win11-packet-50bc4160f6da.zip`,
  `SHA256: <digest>`, and "Send this zip and its SHA256 to Verification. This run is
  an observation, not a PASS."
- **What comes back:** the packet is a ZIP64 archive written by .NET `ZipFile`. Its
  digest is computed from that run, so it cannot be known in advance. Return the zip
  and the printed SHA-256 to Verification. Verification judges it, and nothing in
  this run is acceptance.

## Hosted rehearsals (mechanics only, not Windows 11 qualification)

### Corrected script

`win11-kit-rehearsal.yml` run 39138302218, job 117707277552, on Windows Server 2025
Datacenter build 26100. It ran at head `e1e06fc`. The kit was **not** rebuilt; this is
the same authenticated release as above.

- It fetched the release zip (`ffb0f78a…`), the corrected script (`74e1af2c…`) and the
  original script (`9d850667…`) anonymously by URL, and checked all three hashes.
- **Pins unchanged:** the corrected script's Process Monitor and transport pins are
  byte-for-byte the original's, and it carries no execution-policy override.
- **Full run** with `powershell.exe -NoProfile -File`, no policy flag and `-Rehearsal`:
  - child exit 0;
  - census 1927 of 1927, 0 unavailable, 0 missing, 0 exits differing from their
    descriptors, 0 shipping/observation byte differences;
  - packet `ingest-win11-packet-50bc4160f6da.zip`, 212,991,256 bytes, SHA-256
    `9485590db66f953d9bb22290accb2d0ea332d5c6fd80827c1f4cc4117dc1bb30`.
- **Summary controls.** Each script's own tail (its `Fail`/`Sha` functions, then
  everything from the `summarize_packet.py` call to the end) was run on that packet
  as it stands, and on a copy with one census case
  (`adr180/neighbour/adts-crc-mismatch-1.aac`) dropped from `INDEX.json`:

  | Script | Packet | Summary | Exit | Zip | Send line |
  |---|---|---|---|---|---|
  | original `9d850667…` | complete | ran 1927, missing 0 | 0 | yes | yes |
  | original `9d850667…` | missing record | ran 1926, missing 1 | **0** | **yes** | **yes** (the defect) |
  | corrected `74e1af2c…` | complete | ran 1927, missing 0 | 0 | yes | yes |
  | corrected `74e1af2c…` | missing record | ran 1926, missing 1 | **1** | **no** | **no** |

  The corrected run printed `STOPPED: summarize_packet.py exited 1; no zip was made.`
  The original's pass-through is the negative control: it shows the control can
  see the defect.
- **Wrong-pin control** (green): `STOPPED: shipping ingest.exe is d923613b…, expected
  0000…`, exit 1, no packet.
- **Evidence:** the packet and `summary-controls.json` are in run artifact
  `win11-kit-461-corrected-rehearsal` (ID 12141536738, artifact zip
  `sha256:08fc23fdbf1c002ad5dc0406de2a2ea44308304de8b5880f5aa0f2aeca6f9716`,
  201,322,332 bytes), which expires on 2027-01-16. It is over 1 MiB, so it stays out
  of git.
- The packet is labelled `windows-server-serverdatacenter/x64`, so it can never stand
  in for the Windows 11 packet. The runner's policy is not Windows 11's.

The original script's rehearsal below is kept as history only.

### Original script, before the corrections (historical)

`win11-kit.yml` rehearsal job, run 39104751447, on Windows Server `windows-latest`:

- It fetched the published kit and the script anonymously from the URLs above and
  checked both hashes.
- It ran the original script (`9d850667…`) with `-Rehearsal` and no `-ExecutionPolicy` flag.
- It requires a wrong shipping pin to stop with `STOPPED: shipping ingest.exe is`
  before any case runs and to produce no packet.
- **Result** (green):
  - The script ran on `Windows Server 2025 Datacenter build 26100` and exited 0.
  - The packet carries the platform label `windows-server-serverdatacenter/x64`.
  - The census ran 1927 of 1927 cases, with 0 unavailable and 0 missing.
  - 0 exits differed from their descriptors.
  - There were 0 byte differences between the shipping and observation builds.
  - The observer selftest qualified, and all 4 false-pass controls were rejected.
- **Packet:** `ingest-win11-packet-50bc4160f6da.zip`, 212,596,344 bytes, SHA-256
  `cc51a76875c6564fee90801c2119f1f1750b3ddcc7193d53d94d59dd86ee7de9`.
  It is in run artifact `win11-kit-461-rehearsal-packet` (ID 12128173724, artifact zip
  `sha256:615c6fc86950e2e0dcd8030947eb403ad7809e6d11686fea482f26608545a9b8`), which
  expires on 2027-01-16.
- **Negative control** (green): `STOPPED: shipping ingest.exe is d923613b…, expected
  0000…`, exit 1, no packet.
- The packet carries Server's real edition, so it can never stand in for the
  Windows 11 packet. It is Software's observation, not a review or PASS.
