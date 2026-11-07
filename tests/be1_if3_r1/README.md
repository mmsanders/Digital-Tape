# BE1-IF/3 independent binding r1 — Software652

Michael directly requested this software-only continuation on 4 November2026:
"Please bind the IF/3 cases for software". V382 remains closed; no other role or
physical scope is inferred. Required Product authority is unchanged at51d0f8f.

Declaration: f9db5832194f95d886ad19a9855348c00f5a2da9,
docs/WP17-BE1-INTERFACE.md blob20ddc4448f532725b64db639f1b7a98faa8696c4,
SHA256 e572cb1f72ae591980c2345fa16f06f6494fa0b595659048227ae460174619de.
The docs/import-only head586abc12652a5bd64901e68a017e3f35bed3eb6c has the unchanged
previous package treeb094d319e184bd6c410d93604e9ec784c60ba490. That package is a
runtime dependency and remains byte-unchanged. Import both trees unchanged, with
source identities, before any corresponding new Product implementation commit.

## Commands

Python3.10+; canonical frozen LF references, never regenerated:

```
python -B tests/be1_if3_r1/run.py --selftest --golden tests/golden --out build/if3-checker-harness
python -B tests/be1_if3_r1/capture.py --selftest --out build/if3-capture-harness
python -B tests/be1_if3_r1/run.py --checker PRODUCT/firmware/bench/tools/bench_evidence.py --golden tests/golden --out build/if3-checker
python -B tests/be1_if3_r1/capture.py --helper PRODUCT/firmware/bench/tools/bench_capture.py --out build/if3-capture
```

Output directories must be new. Candidate commands require the actual implemented
input; they are not run for this binding publication. Expectations are authored
from BE1/FW1 and IF/3. No held local implementation/private tests were accessed.
Use this delta **and** the earlier109 checker/four capture cases for the later
complete kit disposition. Passing this delta alone does not clear the whole kit.

## Checker delta: 53 cases

- F5 supplied errors survive missing witness, transcript, sequence, identity or
  manual-verify data. All failing reason codes remain observable, with INVALID >
  MISMATCH > NOT_RUN; truncation/malformed evidence dominates a supplied verify
  failure, and verify failure dominates missing witness/transcript.
- Exact card-field changes and unknown CID, supported verify findings with both
  zero/nonzero exits, inconsistent OK/nonzero, missing and incomplete witness
  markers, and a supplied complete marker record.
- Retried F1/F2/F5 failures and a two-failure retry chain. Current criterion may
  improve, but earlier observation/state and superseded_failures membership,
  worst overall, nonzero exit and complete:false remain. Unrequested failed
  criteria cannot bypass the exit rule.
- Exact firmware.hex path; both declared and measured hashes agree with the
  candidate; mismatch on either side is detected. Other names/subdirectories are
  ordinary declared files. The forbidden role key is rejected by the closed schema.
- Report tool/bundle/reference identities, all criterion states, diagnostic
  retention and sorted keys are checked under the unchanged offline IO guard.

All fixture bytes and card identities are synthetic. Several explicitly labeled
**self-reported marker probes** claim actual/physical in their input to test IF/3's
flag and witness-field parsing. Their witness is `SIMULATED-NOT-MICHAEL`, explicitly
stating no witnessing occurred; their F1 observations remain simulated and their
session is always incomplete. The parser may set physical_run:true for those input
markers as IF/3 requires; the **publication/run result stays physical_run:false**.
Those flags are artifact consistency, never proof of a real physical session or
Michael's witness. No complete target-positive or independent acceptance is asserted.

## Capture delta: 47 cases

Only the declared fake serial interface is supplied; no pyserial or real device is
opened. A controlled clock replaces wall time in the child, so default600/10-second
deadlines and the no-default interrupt mode run without waiting. Independent input
spans constrain read requests to each text/count/PCM element. Exact partial bytes
must be flushed before the next read; terminal lines cannot be over-read.

Cases cover all three stop modes, ERR/FATAL/INFO completion, mode-specific ignored
lines, fragmented/empty/short reads, digest/ERR/INFO bytes embedded in framed PCM,
partial lines/counts/payloads/missing terminators, timeout defaults and retention,
Ctrl+C130/0, port open/read/write/flush errors4, send1/63-byte boundaries, reset/write/
flush order, one LF terminator, deadline beginning after send, stale-before-send
discard, invalid ASCII/length/control bytes/timeouts/mode/arguments, exclusive output
and no prevalidation serial import. Every nonusage exit must emit exact JSON
identity/hash/count/stop/exit; usage64 opens no port or file and preserves old output.

## Harness qualification and limits

Ten checker predicate controls and eleven capture mutations are detected. Capture
doubles use the independently catalogued lengths/spans, not a general Product
helper/parser. They exist to qualify transport, confinement, expected-byte and
result checks. They are never passed as a Product candidate or treated as evidence
that the unimplemented code passes. Generated raw fixtures remain outside the tree;
only small reproducible source and harness summaries are published.

The inherited offline guard and new capture guard observe/deny external effects
in Python. They are instrumented tests, not an adversarial OS sandbox. The fake
clock establishes parser/deadline logic, not target latency. Source-order/import
authentication and exact implemented-head execution remain future disposition
steps. Local held implementation is no waiver of independent test/source ordering.

The four IF/2 declaration dependencies are now bound by this delta. There is no
remaining IF/3 schema request for these cases. Software652 can import and return
its exact implemented head with required CI. Target F1/F2/F5, real witness/raw audit,
timing/output caps, media qualification, purchases and all physical holds stand.
