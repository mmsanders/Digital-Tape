# INGEST-1 Windows 11 collection: proposed one-run instructions (#461)

**NOT READY FOR MICHAEL pending exact-kit authentication.** Verification #204 must
first authenticate this exact kit, script and binaries, and then issue the run.
Until it does, nobody runs this. This document proposes; it accepts nothing. The
original 6126d04 kit, script pins, evidence and instructions are historical and
unchanged. Michael #447's old kit stays PAUSED.

## Exact pins

| Item | Value |
|---|---|
| Candidate (source of the binaries and the transport) | `50bc4160f6da527da8c684d05264f99815aaa870` (#459, ingest 0.1.1), tree `ea0c9ae717a8478ca357fd01186f2a4d912a1193` |
| Collection script | `host/ingest/stage1/win11_packet.ps1` at the candidate, SHA-256 `9d8506670df30bbbc547c6c5757d9370e152ed55cfa4cd8378bd9e1f1337f502` (byte-identical to the 6126d04 script) |
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
- Script: <https://raw.githubusercontent.com/mmsanders/Digital-Tape/50bc4160f6da527da8c684d05264f99815aaa870/host/ingest/stage1/win11_packet.ps1>
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
- **Open for Verification: execution policy.**
  - #461 asks for ordinary policy and no bypasses.
  - The script's reviewed header (unchanged since 6126d04) invokes it with
    `-ExecutionPolicy Bypass`. That flag is scoped to that one process and changes
    no persisted setting.
  - The Windows 11 client default policy is `Restricted`, which refuses every
    script file, so without the flag or a policy change the script cannot start.
  - The hosted rehearsal ran under the runner's ordinary policy with no flag.
  - The command below keeps the header's form, pending Verification's decision.
    Software proposes no persisted policy change.

## Proposed run (NOT READY FOR MICHAEL pending exact-kit authentication)

In an Administrator PowerShell:

```powershell
$d = "$env:USERPROFILE\Downloads\DigitalTape-ingest"
New-Item -ItemType Directory -Path $d | Out-Null
$t = "win11-kit-ingest-0.1.1-50bc4160f6da-r39104751447-1"
Invoke-WebRequest -UseBasicParsing -OutFile "$d\win11-kit.zip" `
  -Uri "https://github.com/mmsanders/Digital-Tape/releases/download/$t/win11-kit.zip"
Invoke-WebRequest -UseBasicParsing -OutFile "$d\win11_packet.ps1" `
  -Uri "https://raw.githubusercontent.com/mmsanders/Digital-Tape/50bc4160f6da527da8c684d05264f99815aaa870/host/ingest/stage1/win11_packet.ps1"
(Get-FileHash "$d\win11-kit.zip" -Algorithm SHA256).Hash     # must be FFB0F78AC3980FA1BB130F0AFF22D53EBB100ED3323A8E50BA62A6EE1819C865
(Get-FileHash "$d\win11_packet.ps1" -Algorithm SHA256).Hash  # must be 9D8506670DF30BBBC547C6C5757D9370E152ED55CFA4CD8378BD9E1F1337F502
```

If either hash differs, stop and report it. Otherwise:

```powershell
powershell -ExecutionPolicy Bypass -File "$d\win11_packet.ps1" `
  -Candidate 50bc4160f6da527da8c684d05264f99815aaa870 -Kit "$d\win11-kit.zip" `
  -ShippingSha256 d923613badda95baeb387d5415d5212a5dedb7c5c7144b21874479babd178f5b `
  -ObserveSha256 d544b6f5c82e653842625080a87ac63cb52353aaeca62494dd5d08eedb844d9a
```

`-Work` defaults to `C:\ingest-win11-work`, which must not exist yet. `-Out`
defaults to the Desktop.

## Stop behaviour and output

- **Stops:** any check that fails prints `STOPPED: <reason>` in red and exits 1.
  The checks are, in order:
  - Administrator, Windows 11 client, x64, and 25 GB free;
  - Python 3.12 present, and the work folder new;
  - the candidate's transport file hashes;
  - the shipping and observation hashes;
  - the Process Monitor hash and signature;
  - pip, `check_pins.py`, `asset.py` and `run_packet.py`.

  A stop produces no packet. Report the red line as printed and do not retry with
  changed values.
- **Success:** the last lines are `PACKET: <Desktop>\ingest-win11-packet-50bc4160f6da.zip`,
  `SHA256: <digest>`, and "Send this zip and its SHA256 to Verification. This run is
  an observation, not a PASS."
- **What comes back:** the packet is a ZIP64 archive written by .NET `ZipFile`. Its
  digest is computed from that run, so it cannot be known in advance. Return the zip
  and the printed SHA-256 to Verification. Verification judges it, and nothing in
  this run is acceptance.

## Hosted rehearsal (mechanics only, not Windows 11 qualification)

`win11-kit.yml` rehearsal job, run 39104751447, on Windows Server `windows-latest`:

- It fetched the published kit and the script anonymously from the URLs above and
  checked both hashes.
- It ran the unchanged script with `-Rehearsal` and no `-ExecutionPolicy` flag.
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
