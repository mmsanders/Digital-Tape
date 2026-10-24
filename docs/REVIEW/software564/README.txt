Digital Tape - unsigned Windows11 x64 candidate (#564)

This is a NEW build of digital-tape.exe from the integrated production screen and
worker bridge (main 266bdcaa). ingest.exe and tapectl.exe are the original,
unchanged binaries; their hashes are pinned in BUILD.json.

Extract all five members into an ordinary writable folder and keep them together.
It needs the Windows WebView2 runtime that is already installed. There is no
installer, runtime download, signing step or security change.

Nothing has been demonstrated on THIS binary yet. Its startup, native window and
normal close are pending a specific Verification #307 admission. Earlier window
and quit results belong to the older app binary only and do not carry to this one.
Page readiness, label input, folder dropping, Checking, Start over, Problem/Show
details and app-driven ingest remain UNEXECUTED.

Make is disabled. Card writing and discovery are unavailable in this build. Do not
use the bundled tapectl for card work. There is no safe-to-remove claim.

If no usable window appears, close the attempt and keep any error text. Do not
change security settings to run it. This is a candidate for a bounded startup
check, not a qualified family release. Full APP/INGEST/CLI A6/G2 remain held.
