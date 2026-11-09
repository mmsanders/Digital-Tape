# Hardware18852b5 review regressions r1

Derived from the already-published plan4/manifest/rollback contract during Michael's
exact-head review. This new package preserves every earlier package unchanged; it
does not claim these new edge cases predated candidate18852b5. Import it unchanged
before corresponding fixes. Dependency: sibling rig_records_r1 tree0d38fbe2.

```
python -B tests/rig_review_r1/run.py --judge PATH/media_atomicity.py --out NEW_OUTPUT
```

Seven cases: positive authenticated OLD rollback; failed E0, absent manifest,
repointed exact bytes and wrong-card setup cannot award qualifying credit or
completed-write proof; a NUL ref and an out-of-window500-digit integer must produce
loader problems rather than exceptions. ADR204 excludes unqualified evidence from
completion proof; schema says method rows need an authenticated plan4 manifest.
An overall FAIL alone cannot authenticate the erroneous proof/count fields.

Candidate18852b5 passes the positive case and fails all six new negative cases.
Strict/default mode exits1. Four proof-predicate controls detect counting without
setup, erasing valid completion, crediting unauthenticated rows and relabelling
rollback TORN. All inputs/controls are synthetic; no physical result is asserted.

`--record-known-findings` is for this historical reproduction only: it authenticates
exact Git blob03382e6ec422a06048514122db0c2b4557ae46ba, requires exactly those six
failed expectations and a passing positive, then exits0. CI green in that mode
means the findings were reproduced, **never candidate clearance**. A different
candidate cannot use it. Use canonical Git source bytes; CRLF and LF file hashes
are different tool identities, not interchangeable observations.

The original27/71/229 cases pass on the held head. These new combinations were
missing from that coverage; green prior tests are not full acceptance. No loader
or Product code is implemented here, and no raw campaign files are committed.
