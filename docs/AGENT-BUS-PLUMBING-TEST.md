# Agent Bus plumbing test

Michael authorized this test on 9 September 2026. The protected `michael-round-gate`
was verified from GitHub: sole reviewer mmsanders, admin bypass disabled, self-review allowed.
This supersedes the earlier missing-environment deployment note.

The `Agent Bus plumbing test` workflow pauses before creating any test resources.
Review its preflight summary and approve `michael-round-gate` using the dashboard link.
Approval covers this fixed test script at the run commit, not any product work.

After approval it runs the production Controller with eight explicitly simulated role
identities. It uses actual GitHub issues, native sub-issue relationships, label projection
and Contents SHA writes to `plumbing-RUN_ID.json` on agent-bus-state. Production state.json
and runtime bindings are not changed. All simulated model attestations use a test OpenAI
mapping; no provider/model is invoked, and this does not certify Grok capability.

Coverage: four lead roots; three worker roles; queued/working/waiting/blocked/review/closed;
wrong-role rejection; exclusive and duplicate claims; actual stale-SHA 409; lead fan-in;
blocked-child disposition; one PM final claim; closed round without automatic restart.
Existing controller regressions additionally cover budget, scope and invocation fuses.

Watch the isolated state at `https://mmsanders.github.io/Digital-Tape/?plumbing=RUN_ID`.
It is prominently marked as simulated. Refresh is 60 seconds; rapid intermediate states
may be missed. Every successful command snapshot is preserved in the workflow artifact,
with trace and cleanup results. An unavailable test ledger after completion is expected.
The ordinary dashboard remains on production state. Browser tests cover actual rendering
with fixtures; the live transcript additionally exercises the dashboard model for every snapshot.

The exercise closes its eight issues and removes its temporary ledger file on success or
caught failure. An always-run recovery step retries cleanup. Hard runner loss or cancellation
can still interrupt cleanup: use the artifact issue manifest / `[PLUMBING RUN_ID]` issue titles
to close only that run's issues and remove only `plumbing-RUN_ID.json`. Closed issues and Git
history retain the test evidence. Do not delete production state.json or alter product issues.

Limits: role identity strings are simulated inside a trusted test job, not eight separately
authenticated GitHub actors. Per-agent workflow dispatch, live chat wakeups, model calls and
optional PR doorbells require the eventual real adapters and remain unverified by this test.
No product acceptance or independent Verification sign-off is created.
