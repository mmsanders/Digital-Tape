# Software590: passive receipt feasibility and owned kit for Michael's 564 rows

PM588 Stage A. This declares a passive evidence interface; it is not an expected-result
trace. Nothing was launched to write it: no app, child, collector, browser, native input
or trial. Verification328 decides admitted versus HELD rows. Michael alone operates the
app (#589).

## Candidate (authenticated, unchanged)

`C:\Users\mrtro\claude\software-only\candidate564\Digital-Tape`, retained since 24 Oct.
Bytes re-hashed on 26 Oct and equal to `docs/REVIEW/software564/MANIFEST.json`
(`d2808264…`): digital-tape.exe `ee4c84ac…0b1fa250`, ingest.exe `3895f3f3…bb9a20`,
tapectl.exe `82798af2…b7a9`, BUILD.json `0faf2810…`, README.txt `839cf34d…`. Source
266bdcaa. The distributed ZIP (`a4b11f75…`) is not retained here; the extracted members
are. Not rebuilt or replaced.

## Context and existing primitives (read-only checks)

Windows 11 25H2 build 26200.9711, x64. Michael's ordinary session, effective admin
**false**. Windows PowerShell 5.1.26100.9711 with .NET Framework CLR 4.0.30319.42000
(Add-Type C#, as the 307 method's WindowNative.cs). Python 3.12.10; the 307-pinned
Inkscape Python is still present. No install, driver, ETW/Sysmon, audit-policy change,
elevation or new provider is proposed. Screen recording uses whatever built-in tool
Michael already chooses (for example Snipping Tool), named in his receipt.

## What 564 itself keeps: nothing

From the accepted 564 source (266bdcaa):

- `main.rs`: data root is Tauri `app_local_data_dir`, which is
  `%LOCALAPPDATA%\org.digitaltape.app`. Today it holds only `EBWebView\` from the 307
  run, and there is no `jobs\`. `clean_stale` is not called at startup.
- `bridge.rs` `drop_using` → `begin`: an admitted drop creates Work `ingest-<32hex>`. The
  serial worker's `execute` creates `jobs\ingest-<32hex>\` (marker, `control\`, `out\`),
  runs the child, delivers, then **removes the job directory immediately**, before or as
  Ready shows.
- `ingest_job.rs` `command`: argv is `ingest.exe --report <control>\ingest-<nonce>.jsonl
  --report-nonce <nonce> --out <out>\DEST --length 3600 -- <folders…>`, cwd the job dir,
  stdin null, stdout/stderr piped into memory. Production calls `run`, not
  `run_recorded`, so **no RunReceipt, PID, argv or stdout is persisted or logged.** stderr
  survives only as `App.details`, which Show details displays (Problem only).
- ingest (s1 35b23cac): the report is created `create_new` with **share mode 0** and held
  exclusively for the whole run. Output is written into `.DEST<mark><pid>-<i>` beside
  DEST, then renamed no-replace to DEST.
- The app polls `try_wait` every 50 ms, then reads the report and the DEST listing, then
  deletes. So after the child exits, the report and pair exist for about 0–50 ms plus
  read time.

## Feasibility per fact

| Fact | Passive method (proposed collector, below) | Lossless? | Perturbs app/child? |
|---|---|---|---|
| Child exists, PID, parent | Job object on the running app: `JOB_OBJECT_MSG_NEW_PROCESS` + handle → image path, creation time, `InheritedFromUniqueProcessId` | Yes for every process the app creates after assignment | No limits set; see risk 1 |
| Child image identity | `QueryFullProcessImageName` on the held handle + SHA-256 of that file before/after | Yes | No |
| OS exit code / exit time | Held handle → `GetExitCodeProcess`, `GetProcessTimes` | Yes once the handle is held. The app's own Child handle keeps the object alive until after it reads the report | No |
| Full argv (incl. `--length 3600`, folder, report, DEST, nonce) | `NtQueryInformationProcess(ProcessCommandLineInformation)` on NEW_PROCESS | **No**: readable only while the child lives; a very fast child can be missed. Recorded as missed, never reconstructed | No |
| Job / request boundary | FileSystemWatcher (names only, no file opens) on `%LOCALAPPDATA%\org.digitaltape.app`, subtree, with overflow errors recorded | Yes unless an overflow is recorded | Holds one handle on the data root only; the app never deletes the root |
| Zero new requests for file/mixed drops | No `jobs\ingest-*` creation and no new job-member process between that gesture and the next, both from the complete streams above | Yes, by the accepted source: every admitted request creates its job directory before spawning, and every app-spawned process joins the job | No |
| Report nonce | Report filename (FSW) and `--report-nonce` (argv, if captured) | Filename yes | No |
| Report bytes (tool/version/nonce records) | None passively: exclusive share-0 open during the run, then deletion 0–50 ms after exit | **No** → propose HELD | Any open/link attempt races the app's read/delete |
| Published audio/manifest bytes and hashes | None passively. A hard link on stage-file creation would keep final bytes, but its momentary open can overlap the stage→DEST directory rename and fail the child's publish | **No** → propose HELD | Possibly; untested, and testing it needs a trial outside scope |
| Positive stdout | Piped to app memory, never shown | **Unobtainable** | n/a |
| Empty-folder stderr | Michael selects all in Show details and copies into `receipts\raw` (the app's own original text, real UI copy) | Yes for that text | No |
| Displayed state, label edits, Checking, Ready 2 s / 88200 frames, Start over | Screen recording and Michael's signed row notes; collector console visible in the recording for UTC alignment | Visual only; a missed Checking is UNEXECUTED | No |
| Owned cleanup | FSW delete events for `jobs\ingest-*` after the child's exit time | Yes (names) | No |
| Source/foreign sentinels | `native590_kit.py hash` before and after | Yes | No |

**Event/IPC/worker crosswalk (for V328 to judge, not claimed):** the Explorer drop time
(recording) is followed by `jobs\ingest-<id>` creation. Only `Bridge::execute` creates
these directories, so this is the production event → `drop_paths` → worker path. Next
comes the NEW_PROCESS of an image hashing to the pin, child of the app PID, with argv
naming that job's control/out. Then come the report filename and nonce, the OS exit code,
DEST and stage names, job directory deletion, and the displayed Ready/Problem. No packet
capture. Direct CLI or test injection would show a parent other than the app, or an image
or job directory that doesn't match.

## Proposed collector interface (NOT written; for V328 to qualify first)

`tools/app/native590_collect.ps1`: Windows PowerShell 5.1 plus one Add-Type C# file, in
the 307 style. Started by Claude Code (auto mode, ordinary user) only after admission.
Michael starts the app himself.

1. Wait for a new `digital-tape.exe` whose image path is the candidate path above and
   whose SHA-256 is `ee4c84ac…`. Record PID, creation time, parent and `IsProcessInJob`.
   Print READY. Michael makes no drop before READY.
2. `CreateJobObject` with no limits (no kill-on-close, no breakaway changes), then
   `AssignProcessToJobObject(app)`, completion port, and record every message with UTC
   and QPC. Processes the app created before assignment (WebView2) are not members, and
   are recorded as such.
3. On NEW_PROCESS: open `QUERY_LIMITED_INFORMATION|SYNCHRONIZE`, read image, creation
   time, parent and argv if still alive, and hash the image; on exit, read the exit code
   and times. Close the handle after the exit.
4. FileSystemWatcher as above. At end, record `JOBOBJECT_BASIC_ACCOUNTING_INFORMATION`
   (TotalProcesses) and close the job handle; the app keeps running unaffected.
5. Write `receipts\raw\collector.jsonl` and `collector.stderr`; never touch files inside
   `jobs\`, never read, copy or link app or child files, never send input.

Risk 1: job membership changes nothing the 564 source does (it never requests
breakaway). WebView2's own sandbox jobs belong to processes created before assignment.
Risk 2: a child faster than the argv read leaves argv missing, recorded as missing.

## Owned kit (prepared now)

`python -B tools/app/native590_kit.py prepare --root C:\Users\mrtro\DigitalTape-590-kit
--candidate <candidate564>` refuses a mismatched candidate or an existing root. It wrote:

- `fixtures\Music\two-seconds.wav` from imported 317 `wav()`: 352844 B,
  `48f1b3c7ce7fe27a90469364f841803087a9d274a4af9a4ec8ee195a2846ac18`.
- `fixtures\Empty\`, empty.
- `fixtures\Not a song.txt`, 58 B, `6c632e41…f6`. For the file drop, then the mixed drop
  with `Music`.
- `foreign-sentinel\keep`. Proposed: copy it to `%LOCALAPPDATA%\org.digitaltape.app\jobs\
  foreign-590\keep` before launch, only if V328 admits that placement.
- `labels.txt` and `labels\1..7.txt`: the 8 frozen windows_screen_r1 LABELS for paste.
  Row 8 (NUL) cannot be pasted naturally and is recorded as unsupported.
- `receipts\INDEX.json`: the 317 index shape with every row UNEXECUTED and empty refs, and
  `receipts\raw\` for private originals.
- `MANIFEST.before.json`, sha256 `2c13cc74b178925ae46d09d100fd356fecec22b964f0a6218ac8594bd8d05ef2`.
  `hash` produces the after-session sentinel record.

Originals stay private in `receipts\raw`. Published returns carry hashes and redacted refs
only.
