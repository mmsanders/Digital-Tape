# PM541 — Windows app test failure and focused correction

Reviewed22October2026 PDT. Product mainaa81d98985d7a4af0d30a3b12d8be7dba761a8a9;
Verification mainf2b904d62305874d90522ec0c9608fa55937ba69.
Michael requests failure review/new work, under Windows-only app-first ADR191.

## What actually exists

Software built the real portable app and real report-capable S1 child. Hosted
build39883700812 passed; artifact12471942204 is staged on the actual Windows
client. Transfer was resolved by a documented scoped tool-network approval,
without Windows/UAC elevation. No further download or rebuild is needed for
the unchanged original artifact/source45695aa0.

Portable SHA256d45b2e78d5fd3017a1a3427201605fa0d9ff747527fac37e5c3847ec346fb0fd;
app05bc85626bfeaaa904f9ec52b2208f18e584d5808916a5e561be762eebac02dc;
S13895f3f356c91b8a9fe870c33694da64bf2765df308bef118d657c1be4bb9a20.
Current draft540 head328ac2884a5ef6eba82299e5e2bcfeea25868446 changes compiled
source only by build-return documentation. No component source integration
clearance exists; draft540 stays unmerged.

## Actual failure and diagnosis limits

| Row | Evidence / correct interpretation |
|---|---|
| A0 app launch | Process started; first responsive main-window sample had nonzero handle, blank title, about0.18s after process start. Recorder requested close about1.22s after start; no exit within10s, then owned forced cleanup/exit-1. No successful normal quit or usable UI established |
| V280-001 | Verification-owned recorder closes at first responsive handle without establishing actual configured window/page readiness. This is a test observation gap; timeout does not yet prove a fully loaded app quit defect |
| P0 real child | Exact pinned S1 exit1; authentic start/current nonce/version, IO_FOLDER subject0, end1; no output pair. Error shape matches non-Unix folder canonicalization/oserror5, not established decode/enumeration |
| Root cause | Unclassified between execution restrictions/runtime/source. Existing ordinary directory/no-reparse/read-execute ACL and PowerShell Resolve-Path facts do not prove the separately launched Rust child can canonicalize |
| Other rows | P1 and all U/N UI interaction rows unexecuted. Existing-oracle generic fallback projection is not observed displayed UI |

Independent280/PR282 mergef2b904d6, exact author5aca12a39f669fdef6ec0d5ee6aca6413fc242b7,
normal CI39894341134 SUCCESS authenticated. Read-only local review checked23
original entries,26 app/157 child source entries, immutable method/helpers and
both artifact ZIPs. Public CI checks consistency/controls, not private runtime.
[Independent actual report](https://github.com/mmsanders/digital-tape-verification/blob/f2b904d62305874d90522ec0c9608fa55937ba69/findings/P2-280-RETURN-2026-10-22/README.md).

Original inventory document4354bytes/SHA256
157055c1d72b9965e773c0a26efb93c6c5a26c7af17cbb72eb310c3a586ee734
describes23 files;4354 is not their combined payload size. Original private
receipts, streams, current report and post-return read-only ACL inspection remain
in place. No rerun, raw upload, Product fix or fake success was made in PM review.

## Focused next work issued

Software542 / independent Verification283 is ONE fresh consolidated correction.
Full execution directions live in those issues.

- Verification fixes readiness recording before another app launch, preserving
  original20s startup/10s close bounds, distinguishing owned window readiness,
  page/control usability, actual selected WebView2 runtime and normal quit.
  Original281 method and STOP remain immutable; no premature close or timeout
  extension to turn the same recorder green.
- Software may REQUEST documented normal tool approval for the exact owned-file
  test in an ordinary non-admin context outside task filesystem sandbox, if
  necessary. This permission is distinct from Windows account elevation. No
  UAC/runas/credentials/ACL/AV/policy/security changes or rejected-approval bypass.
- After independent context/admission predicates, one fresh changed-context exact
  S1 P0 and conditional P1; one corrected A0. Approved context/fixture admits the
  test, not a promised positive result. A remaining failure is recorded before
  any independently specified Product source correction.
- Keep current source/artifact/child pins. No redownload/rebuild absent a real
  source delta; no denied-root or alternate-provider retry, fake child, generic
  resource supervisor, card/native/VHD/sparse/404/global-proof campaign.
- Actual eligible UI rows require a permitted real UI tool and appropriate
  positive child prerequisites. Direct CLI results cannot become app UI evidence.
  PhysicalMake remains disabled; source integration still needs exact independent
  clearance and normal required CI/reviews/protections.

The purpose is a valid real-client app test and decisive child context result,
not a new capability inventory or a claimed app bug unsupported by the recording.
If normal tool approval is rejected, stop and return the exact stated reason;
it is not authority to evade policy. No new user installation/admin/physical action
is requested by PM541. Phase1 complete36/36;Phase2 remains6/12. Existing CLIA6,
INGEST native visibility, Windows S3/fullAPP/G2 and sparse-suspension holds survive.
