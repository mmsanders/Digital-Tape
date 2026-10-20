# Actual shipping exhaustion regression — Verification201 / ADR186

Authoring basis: existing INGEST-1 resource contract (frozen in
../wp15_app1a_r1/spec/WP16-INGEST-CONTRACT.md), authenticated original Windows6MiB
abort in Verification/main0c1eb39e6bd13c70de702f9e3926a9b7b39c03e6, PM456/ADR186.
No corrective implementation or Software-private tests inspected to author this
package. Existing APP tests and prior math/source/native receipts are unchanged.

This launches the actual executable, not an observation allocator, status wrapper,
or allocator-only probe. Windows uses CreateProcessW(CREATE_SUSPENDED), associates
the process with a JOB_OBJECT_LIMIT_PROCESS_MEMORY Job before ResumeThread, then
records the native DWORD GetExitCodeProcess value. Files capture actual child output.
Reference: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
and JOBOBJECT_EXTENDED_LIMIT_INFORMATION / AssignProcessToJobObject in Microsoft SDK.
Linux uses prlimit RLIMIT_AS. No enforceable Mac limit is claimed or silently skipped.

Fixed admitted source is Stage1 ordinary.wav, SHA256
`d36663d1e4f05abaac699a6c14e0fa86724db9b4decdb8c96abe0c9d1f645821`.
The whole source pack is fetched/authenticated by its existing independent asset.py.
Unlimited,3,4,6,8,12,64MiB each have a same-limit --version control and full
`ingest --out DEST --length60 f0` application invocation. The same absolute DEST
is reused and each successful pair moved into that row's retained snapshot.
Every success must equal the same executable's unlimited pair byte-for-byte.
Every nonzero tool failure must be exactly1, with a tool diagnostic, no DEST/stage
or unexpected output-parent entry and the foreign sentinel intact. Loader control
failure is incapable evidence, never a passing exhaustion row. Candidate PASS also
requires at least one actual limited exit1; pure success is no exhaustion evidence.

The separate `baseline-red` mode is restricted to the original Windows executable
SHA256 `0e1ef2cb4f283eb876f08019222da5d3ac744ec30d49f020a2e87323f31bcac1`.
It requires the real6MiB status0xC0000409, successful load control and clean failure,
at least one3/4MiB clean exit1 and one8/12/64MiB admitted success. The contract
judgment remains RED in RESULT.json. Green publication CI means this detecting
regression actually reproduced/rejected that known defect, not Product acceptance.

```sh
python3 -B tests/wp16_shipping_exhaustion_r1/selftest.py
python3 -B tests/wp16_shipping_exhaustion_r1/runner.py --binary EXACT_SHIPPING_BINARY --sha256 FULL_SHA256 --source AUTHENTICATED_ordinary.wav --out FRESH_PATH --mode candidate
```

Import this directory verbatim from its merged publication. Adapters stay outside.
Supply actual candidate head/build/version/hash and command/file census receipts;
no rerun of unchanged full audio campaigns. WindowsServer is supplementary only;
actual Windows11/ordinary security, macOS enforceable exhaustion, native failed-open
absence, physical and full package holds survive. New Windows kit readiness awaits
fresh pinned Software457 returns; old6126d04 instructions remain paused/preserved.

Original binary transport: Product run38948012087 artifact12067900169, ZIP SHA256
`32d6643c1cb782dcf6ac540f14b733be556a3b089b49fd53475076b9f5503eac`.
Normal CI uses official download-artifact across the public repository; optional
public small-packet fallback authenticates that archive and the exact executable.
No corrective binary rebuild can stand in for the original detecting control.
