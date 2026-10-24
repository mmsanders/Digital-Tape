# Software564 Windows 11 candidate: build return for Verification #307

**[Software Lead]** Issue #564, manual pickup (PM570). Local Windows Claude Code.
Inputs: Product main `266bdcaa760f702d6f685300cc9ca6e4491b6438`, Verification main
`fad2eac7b5aa375a788c8e3ce0a3f7c83374be6f`, #307 method `9a4afe6db99c955343449ae2537d457743af3db5`
(`tests/windows_candidate_r1`). **BUILD only. Nothing was launched, extracted to disk or invoked.**

## 1. Candidate source

| Fact | Value |
|---|---|
| Source head (main, #567 integration) | `266bdcaa760f702d6f685300cc9ca6e4491b6438` |
| Root tree | `d0d628f407acc10745b1d01196c6d07603cfbcee` |
| `host/app` tree (cleared) | `4e282664107e2635b72dec8801b76e06660fb892` |
| `tools/app` tree (cleared) | `cb842620ba709429ebfa284f1407b2c59a5d7c8a` |
| Screen (#305) and bridge (#306) disposition | `fad2eac7b5aa375a788c8e3ce0a3f7c83374be6f` (Verification PR #314) |

Source linkage on `266bdcaa`:
- `host/app/src/main.rs` registers only the five bridge commands `snapshot`, `set_label`, `drop_paths`, `start_over` and `raw_details`.
- Its setup prepares the per-user job directory and constructs `Bridge`.
- No child process starts at startup. `ingest` runs only after a folder drop, through `children::resolve`, which refuses any `ingest.exe` whose SHA-256 differs from the compiled-in pin.
- The app has no `tapectl` pin and no discovery, Make, elevation or raw-device route.
- There is no blanket #540 import.
- No test or shipping switch was added.

## 2. Build

| Fact | Value |
|---|---|
| Workflow | `.github/workflows/windows-candidate-build.yml` at PR #574 head `15aad634b688e188c0e8ca078eb79e9ecf96e2f2` |
| Run | [40141860952](https://github.com/mmsanders/Digital-Tape/actions/runs/40141860952), job 121015095487, attempt 1, SUCCESS |
| Toolchain (hosted `windows-latest`) | rustc 1.99.1 (`58cf8f9c3`, x86_64-pc-windows-msvc, LLVM 23.1.1); cargo 1.99.1 (`5f94df478`) |
| Command | `cargo build --release --locked --bin digital-tape` in `host/app`, with `DT_INGEST_SHA256`/`DT_INGEST_VERSION` set to the original pins |
| Lock | `host/app/Cargo.lock` as in tree `4e282664` (`--locked`) |
| Candidate artifact | `software564-windows-candidate`, id 12578829894, 2,431,819 bytes, digest `sha256:a19c47d7d474414cfb0c8cf992fd6e984bf9ff160c5e38efdd7e09a45b12aa94`, expires 2026-11-23 |
| Evidence artifact | `software564-build-evidence`, id 12579625329, digest `sha256:ecdadecf851a49760b9a9c0f2076b5d497d865af9891d87abe6d830f97c0249d` |

The original children are hash-checked and were not rebuilt or run:
- `ingest.exe` is taken from the #538 artifact 12471942204, whose ZIP is `d45b2e78…`.
- `tapectl.exe` is taken from release `wp14-tapectl-5e2df5aaf23e`.

Hosted compilation is BUILD evidence, not Windows 11 client proof.

## 3. Archive (#288 five-member layout)

ZIP `Digital-Tape-Windows11-x64-candidate.zip`: **2,438,637 bytes, SHA-256
`a4b11f750fb7e3d9fd77a0e6dc1009683496ef6881791c1947a03970310b190b`**. Entries are sorted, all
dated 2026-10-24 00:00:00, mode 0644. The packager is `tools/app/package_candidate.py`.

| Member | Bytes | SHA-256 |
|---|---:|---|
| `BUILD.json` | 2,274 | `0faf28103f4e76d75c392a22d7c8dbe7c33ac9732a7ff62a6a76738a358969f2` |
| `README.txt` | 1,263 | `839cf34dfccde339e78e2d595f9e3367ec62dea113a2176f05f25c0b1f5c9ee7` |
| `digital-tape.exe` (NEW) | 4,828,672 | `ee4c84acb03655c4fb1344db1548ab283054eabe9caea9c2482b0181b39fa250` |
| `ingest.exe` (original pin) | 889,856 | `3895f3f356c91b8a9fe870c33694da64bf2765df308bef118d657c1be4bb9a20` |
| `tapectl.exe` (original pin) | 435,533 | `82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9` |

`BUILD.json` and `README.txt` are retained byte-for-byte beside this file, as are the workflow's
`facts.json` and `INVENTORY.json`. I downloaded the artifact and re-hashed every member in
memory against the inventory.

Proposed clearance crosswalk, source-only before any startup:

| Member | Claim |
|---|---|
| `digital-tape.exe` | Built from source cleared by `fad2eac7` (#305/#306 component scope only). No runtime fact yet. #283 facts do NOT carry to this binary. |
| `ingest.exe` | Unchanged original. Its #283 DIRECT S1 facts (`81033e2a`) carry by identity, not invoked. |
| `tapectl.exe` | Unchanged original. Its #277 identity (`f715776b`) carries, not invoked. |

## 4. Proposed #307 manifest

`MANIFEST.json`: 1,232 bytes, **SHA-256 `d28082644506472050220fa7080ec59df726114b10050552dcf9a8e797c96c8e`**.
It passes the published `prepare.manifest()` schema check, which runs no Product or native code.
Its fields come from the downloaded archive, not from hand entry. The schema check does not by
itself clear anything.

Proposed owned paths and command, used only after a specific #307 admission:
- Verify the ZIP SHA-256 above, then extract it to `C:\Users\mrtro\claude\software-only\candidate564\Digital-Tape`, which is new, ordinary, non-reparse and owned.
- Prepare the method into a fresh `C:\Users\mrtro\claude\software-only\candidate564\method-307` with `prepare.py --manifest MANIFEST.json --expected-manifest-sha256 d2808264… --out …`.
- WorkDir: a fresh `C:\Users\mrtro\claude\software-only\candidate564\run-1`.

Proposed command:
`& C:\Users\mrtro\claude\software-only\candidate564\method-307\Start-App.ps1 -ArtifactDir C:\Users\mrtro\claude\software-only\candidate564\Digital-Tape -WorkDir C:\Users\mrtro\claude\software-only\candidate564\run-1 -Python "C:\Program Files\Inkscape\bin\python.exe" -ToolContext approved-exec-command-require-escalated`

Context facts read without launching anything:
- Token: Medium mandatory level (S-1-16-8192). Administrators is present only as a UAC-filtered (deny-only) group.
- Free space on C: about 27.5 GB, against the ≥256 MiB required.

## Items for Verification to rule on before admission

1. **Python path.** The default `python.exe` on this machine is a Microsoft Store App Execution Alias, which is a reparse point that `Ordinary-Path` would refuse. The proposal uses Inkscape's bundled CPython 3.10.8, an existing ordinary file. It was not installed for this purpose, and `context.py` needs only the standard library. Spyder 3.7.9 and LibreOffice 3.7.7 interpreters also exist.
2. **Tool-approval route.** `-ToolContext` accepts only `approved-exec-command-require-escalated`, which is the Codex route name. Under PM570 no Codex approval transfers to Claude Code. In Claude Code the equivalent is one exact PowerShell tool call approved by Michael at the per-command permission prompt. It is not OS elevation, and there is no broad prefix approval. I need Verification to rule whether that route is admitted under the existing literal or needs a method change.

## Holds

All remain held and unexecuted:
- Startup, native window and quit for the new binary, until specific #307 admission.
- Page readiness, actual UI, controls and OS gestures (#298), Tauri IPC, app-driven INGEST and the selected runtime.
- G1/G3/G4/G5, native session/S3/A6/INGEST/full-APP/G2, and physical/shipping Make.

No independent acceptance is claimed.
