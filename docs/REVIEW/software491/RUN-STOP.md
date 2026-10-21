# Software491 / PM494 — pre-capture privilege capability stop

20 October2026 PDT. Input Product main968b6d37d5508e7a9bd10dfb9e44a1431b1d6dbe.
**The independent method is ready and imported. The existing authorized capture
context lacks the privilege required by the authenticated observer. No capture or
six target native calls ran.** This supersedes the earlier authored-stage wait.

## Exact method carried before implementation

Verification236 publication `9991eded2ca2892f436088241848a55de4d31b88`, author
`e0eeb0d6b98b13a1ad7d98ef42dca92729ceb91a`, package tree
`944df7d2fc9946c62214829d8c67d7f7c4b0b62e`. All six files are imported under
`method/tests/wp16_observer_visibility_r1` with byte-identical SHA256SUMS and an
exact Git subtree match. Product import commit
`b92f6f8e4ce0274c0b78762ab0a8135609b99333` precedes this stop report; no helper
implementation followed it. [METHOD-IMPORT.json](METHOD-IMPORT.json) records modes,
source blobs and file hashes. Six synthetic neighbours/27 detecting controls
passed using the unchanged package; this is not actual observer capability.

## Existing execution context and primary tool requirement

An ordinary sandboxed PowerShell process reported Administrator role=false.
The separate **existing unsandboxed** process reported the same result, pointer
width64, PID16492. It requested no Windows elevation/UAC or group/policy change:

```powershell
$principal=[Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
```

The unchanged installed Procmon64.exe remains4.12,2237720bytes,SHA256
`28495e642b2a465474a4edc58380eaf8b7ee580f3fbcb4141061deadafe9b885`.
Read-only UTF16 resource/string extraction from those exact bytes found:

- `Capture requires Administrators group membership`
- `Process Monitor must be run from an administrator account.`

[RUN-STOP.json](RUN-STOP.json) binds each exact encoded message to its byte offset,
length and SHA256, plus actual token/host/preflight facts. The embedded execution
manifest is asInvoker; it does not grant Administrator membership. The existing
ordinary process token therefore does not meet the tool's declared capture
requirement. Procmon was **not launched to solicit elevation or test a workaround**.
This is a prerequisite stop, not a measured failed capture-start exit or an
observer visibility result.

## Python route and untouched experiment

PM494 conditionally permits an isolated existing Python3.12.14/native-FFI helper
named probe-235.exe. That authorization is preserved. The Python route is **not
declared incapable**: its helper source/image/dependencies, native bindings and
plain-launch preflight were not implemented or tested after the independent
observer-privilege prerequisite failed. A working named helper would not supply
the missing capture privilege. The stop rests on that separate prerequisite,
not on the earlier GCC failure. No GCC retry, alternate tool/provider hunt,
package installation, filter modification, elevation or security change occurred.

Counts are all zero: helper builds/launches; six target CreateFileW calls;
exact-name QueryDosDeviceW calls; capture-start attempts; observer launches;
new trace bytes. Ordinary token/PE/file metadata checks are separate preparation,
not the issued six-case experiment. No native handles/outcomes, nonce/process
lifetimes, raw events, loss counters or normalized actual evidence were fabricated.
The synthetic selftest fixture was not used as an actual return and the actual
oracle was not run on nonexistent capture facts. Old raw traces were not replayed
or used to infer current absence.

The prior isolated ordinary fixture/sentinel and retained kit/collector/observer/
config receipts remain preserved. Current host metadata still records local
Windows11 Client/Core26200.9457, AMD64, Python3.12.14; original metadata's missing
UBR still prevents exact old/new OS carry. Full-machine traces/paths/environment
remain private; this publication has no capture or binary archive.

## Direct return and bounded stop

Verification235 owns independent disposition of this prerequisite blocker;
PM494 owns any later task scoped against an **already available authorized
administrator capture context**. No new human elevation/security/install task,
bypass, alternate capture provider, or unchanged retry is requested. No observer
launch is needed to establish a preferred failure in the current context.

Software491 closes at its explicit precise-capability-blocker stop. The authored
method and earlier preparation remain durable, not reset or reauthored. Its
one-capture/six-case/twoCPU-hour/512MiB/one-correction limits remain cumulative;
no capture or target-case budget was consumed. Normal docs CI checks publication,
not observer capability. S2/exact-shipping/230 results carry unchanged; PML,
failed/zero-access visibility, physical/A6/Mac/S1/S3/G2/full-package holds survive.
