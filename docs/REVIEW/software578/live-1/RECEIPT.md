# Software578 live-1: the one admitted metadata-only `tapectl cards` attempt

Admission: Verification318 correction1 disposition `fdffea5759c2cf48b37a6960c5ed36d09ab91b98`
(findings/P2-318-CORRECTION1-2026-10-25), single attempt, unexecuted until this run.
Michael's chat approval in this Software session: "Go ahead and run". Caller context:
Claude Code desktop, Opus 5.5, auto mode (a caller declaration, not an audited grant).

- Child: artifact 12610149859 from run 40225724763 (PR #580 head `f9306c2c`), downloaded to
  a fresh folder, SHA-256 `44ef26869ba2d01a8a183660a2c7a050d0e7e9ff37c40b727131512739ea6ded`,
  493712 bytes, version `tapectl-wp15-s2+f9306c2c5a42`. Rechecked immediately before launch.
- Exactly the admitted exe/cwd/argv (`invocation.json`). `live578` did not exist; the job was
  created empty and the report name was unused. User `mrtro`, not elevated
  (`IsUserAnAdmin()` false), Windows-11-10.0.26200.
- `run578.py` (this folder) is the launcher: one `subprocess.run`, no shell, 60 s guard,
  no retry. It ran once at 2026-10-25T21:12:13Z.
- Result (`terminal.json`): exit 0, stdout 41 bytes `{"t":"summary","offered":0,"unprobed":0}`,
  stderr empty, report written with the matching version and nonce, start/progress/end exit 0.
  No device path appears in any output. The app's judge would show "Put a card in."

Files are the original bytes: `stdout.bin`, `stderr.bin`, `report.jsonl` (byte-identical copy of
`job/cards-154abcdcabdabea5199b812735fbe464.jsonl`), `invocation.json`, `terminal.json`
(Python text mode, so CRLF). The originals remain in `C:\Users\mrtro\claude\software-only\live578`.

Limits: one inventory fact on this machine with no card inserted. Zero offered is a hint, not
proof that no process device access occurred, G1, safe-card authorization, native UI, Make or
any package acceptance. No app launch, card handling, raw read, write mode or unmount.
This needs its own Verification review.
