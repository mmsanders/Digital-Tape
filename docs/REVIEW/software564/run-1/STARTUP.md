# Software564 candidate: the one admitted startup attempt (Verification #307)

**[Software Lead]** Issue #564. Local Windows Claude Code. Admission: Verification
`cba3433b9e67a219de04ac77150053e843f7f862` (`findings/P2-307-ADMISSION564-2026-10-25`)
and the #307 specific prelaunch admission comment of 2026-10-25T02:36:08Z.
**One attempt, no retry. Result: native window readiness and normal quit observed;
page readiness, UI and everything else UNEXECUTED.**

## Approval record

- Michael, in this Claude Code chat (2026-10-25, after the admission was posted):
  "Okay, you have the permission you need from verification, and I approve".
- The launch was then issued as ONE PowerShell tool call whose command text was
  exactly the admitted invocation below, with no other command in the call.
  No saved prefix rule, settings or permissions change, execution-policy change,
  elevation or alternate provider was used. Honest limit: this session was in the
  Claude Code desktop app's auto permission mode, so the record of the exact
  per-command grant is Michael's chat approval plus the tool call itself; I cannot
  produce a separate prompt-dialog transcript. Verification rules on whether that suffices.

```powershell
& 'C:\Users\mrtro\claude\software-only\candidate564\method-307\Start-App.ps1' -ArtifactDir 'C:\Users\mrtro\claude\software-only\candidate564\Digital-Tape' -WorkDir 'C:\Users\mrtro\claude\software-only\candidate564\run-1' -Python 'C:\Program Files\Inkscape\bin\python.exe' -ToolContext approved-claude-code-exact-command
```

## Preparation (before the launch)

- Artifact 12578829894 downloaded: `a19c47d7d474414cfb0c8cf992fd6e984bf9ff160c5e38efdd7e09a45b12aa94`.
  Nested ZIP `a4b11f750fb7e3d9fd77a0e6dc1009683496ef6881791c1947a03970310b190b`.
- `candidate564` did not exist beforehand. The five members were extracted into the fresh
  `candidate564\Digital-Tape` and each matches the admitted hash (BUILD `0faf2810…`,
  README `839cf34d…`, app `ee4c84ac…`, ingest `3895f3f3…`, tapectl `82798af2…`).
- Python `C:\Program Files\Inkscape\bin\python.exe` SHA-256 `fbaff2f3…a745` (matches the pin).
- Prepared with Verification `cba3433b` `tests/windows_candidate_r1/claude.py` and manifest
  `d2808264…` into the fresh `candidate564\method-307`. All five generated helpers match
  RESULT.json: Start-App `9c13a32b…`, context `5a35a766…`, window_gate `a8af2eb0…`,
  WindowNative `868c11c4…`, judge `01ae9208…`. `PREPARED.json` is in `method-307/` here.

## Result (from the original receipt)

| Fact | Value |
|---|---|
| PID / start ticks | 21552 / 639284927220048923 |
| argv / cwd | `…\candidate564\Digital-Tape\digital-tape.exe` / `…\candidate564\Digital-Tape` |
| Context | Python 3.10.8 at the pinned path; token_elevated false; effective_admin false; Windows 25H2 build 26200.9711 |
| Ready samples | seq1–3 at 865/1397/1943 ms, same PID/start/handle 1246546, visible, top-level, unowned, responding, title "Digital Tape" (span 1078 ms) |
| Close | WM_CLOSE posted at 2096 ms; exit 0; graceful; no forced cleanup; capture complete |
| stdout / stderr | 0 bytes each (`e3b0c442…`) |
| Own WebView2 module | EmbeddedBrowserWebView.dll 155.0.4283.62 (`4c0d799a…`); recorder still reports selected runtime UNAVAILABLE |
| Offline judge (`judge.ps1`) | passes: "ONLY exact new-binary native-window readiness/normal quit; page/input/G1/G2 UNEXECUTED" |

Original receipts here, byte-for-byte (`-text`):

| File | Bytes | SHA-256 |
|---|---:|---|
| `launch.private.json` | 17,009 | `4d0697bc66c9d599d7e1e86d0f58b4123dfd2a0b42a1d2d299abfff190ab3da2` |
| `context.private.json` | 829 | `765bc22d5a673d5326a04f100b9608ad68664e158f6ff22dbc120a5915b6e19b` |
| `stdout.bin` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `stderr.bin` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

## Holds

Not executed and not claimed: page readiness, actual UI, controls, input or OS gestures,
Tauri IPC/JS, app-driven INGEST, selected runtime, discovery/card/Make/elevation,
G1/G3/G4/G5, native/session/S3/A6/INGEST/full APP/G2. The children were not invoked.
No independent acceptance is claimed; Verification #307 judges the original receipt.
