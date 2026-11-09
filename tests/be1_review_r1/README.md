# V388 Software kit review regressions r1

Independent review of Softwared62e0de07c81dc5abe1c8ffbf378bd077a2a7eab under
V388/BE1-IF3. Existing109/4 and53/47 suites pass. These new combinations expose
three further defects without editing earlier packages. Runtime dependencies are
the unchanged sibling be1_binding_r1 and be1_if3_r1 packages.

```
python -B tests/be1_review_r1/run.py --checker PRODUCT/firmware/bench/tools/bench_evidence.py --helper PRODUCT/firmware/bench/tools/bench_capture.py --golden tests/golden --out NEW_OUTPUT
```

Two before-deadline positives and three continuous-input deadline cases use the
published fake serial/clock boundary. Deadline expiry must stop digest/info with3
or timed-interrupt with0/timeout, keep all received bytes exactly (verified against
the fake port's delivered-byte hash), and not wait for an empty read. One blocking
read-timeout of slack is allowed; a completed0.91-second transcript cannot satisfy
a0.03-second timeout. This is simulated logic, not measured target latency.

The sixth case supplies an external **synthetic saved file** through a directory
alias inside BUNDLE. Windows uses a task-owned junction; Linux uses a symlink.
The checker must reject it as INVALID without opening outside the resolved bundle.
The inherited audit guard observes attempted reads; its denial is not Product
confinement. A Product checker that attempts the outside read fails even if an
external guard prevents it. No real external/private file or device is accessed.
Links and fixtures remain in the new output directory; no recursive deletion occurs.

Six predicate controls detect late success, a wrong hash, late stopping, dropped
received bytes, silent alias acceptance and an outside attempt hidden by a rejection.
Two further malformed-type cases supply array values for criterion and superseded_by.
Both must produce an INVALID report and exit 2, without an uncaught exception.
On the original head the two positives pass and six cases fail. Default mode exits1.

`--record-known-findings` authenticates the original checker/helper SHA256 pair
and requires exactly those six failures, then exits0. It is only an immutable
historical reproduction mode, never candidate clearance. Future candidate fixes
must use default mode. Export canonical Git bytes for that mode; working CRLF
source files have different tool hashes. No current candidate implementation is
substituted by harness doubles. Import new expectations before their fixes and
retain original evidence/source identities.
