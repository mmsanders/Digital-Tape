# V382 rig-r2 row qualification binding r1

Authority: V382, WP05/ADR204 at Product51d0f8f. Public declaration received:
Hardware2faa1180c6f12eb4598d1f25351766f550064055, ATOMICITY-SCHEMA-R2.md.
No uncovered R374-2 implementation inspected or executed; none exists at input.
The prior rig_correction_r2 tree1ca703a4 remains unchanged.

```
python -B tests/rig_timing_r1/run.py --selftest --out build/rig-row-controls.json
python -B tests/rig_timing_r1/run.py --qualifier PRODUCT/hardware/characterisation/media_atomicity.py --out build/rig-row-product.json
```

The candidate adapter is the preserved public `qualifies(row) -> (bool, reason)`
interface, already used by the published original rig probe. New fields are exactly
those declared in the received schema. This tests the pure row predicate, not the
complete judge, a manifest loader or a physical method. If the implementation needs
mechanically equivalent API plumbing, return that mapping without changing cases.
Candidate result must additionally be tied to the exact returned Product head.

71 cases cover: positive declared row; both inclusive ambiguous boundaries, strictly
before and just after; capture arm/end boundaries; absent and delayed opening and
exact500us bound; legacy diagnostics excluded from decisions; operator constant
overrides; protocol failures; missing fields; negative/nonfinite/nonboolean typing;
contradictory, empty, backwards and out-of-window edge records. Nonfinite primitives
are injected directly into the Python API; no NaN literal is presented as valid JSON.
Malformed wire JSON handling belongs to the still-pending complete judge interface.

**Policy override:** schema currently says edge<=rail-U is completed-before.
ADR204 supersedes that equality: only strictly< is completed-before; equality at
either boundary is ambiguous. Reason checks require the declared ambiguous/before
distinction so equality cannot accidentally become completed-write proof.

Seven detecting predicate controls qualify the harness only: always/never qualify,
incorrect lower-bound completion, counting either equality, operator-shrunk U and
an unobserved opening. The self-test uses declared expected observations and never
runs a Product qualifier. It does not qualify the electrical timing method.

## Precise remaining interface dependency

Returned before binding in Hardware651 comment6623537645:
- Record and validate rail edge direction/initial state and relation to rail_open;
  finite times, list order and capture-window consistency must be explicit. The
  ready tests reject contradictions using V382's stated requirements; they do not
  infer unseen physical edges or silently choose a chatter policy.
- Specify the actual judge/plan CLI/API for loading the immutable manifest and
  authenticating its contents, raw calibration/control and firmware identities,
  row SCK/bus/switch/card consistency. The schema declares hash fields and prose
  contents but not this loading/validation interface. Equal hash-shaped plan/row
  strings cannot supply calibrated evidence.
- Explicitly adopt ADR204's rollback failure and boundary rules in the declaration.

Until that correction, **new plan4/manifest/complete-judge bindings and completed-
write rollback execution remain unbound**, not passed. Their acceptance cases are:
positive production1000 with authenticated manifest/controls; 999 short and operator
override; all row identity/CID/method/SCK/manifest conflicts; changed/missing manifest
or calibration bytes; late lawful NEW adds no credit; OLD with qualified busy end
strictly before rail-U adds no credit and fails integrity with iteration in
completed_write_reverted; boundary-ambiguous OLD is not completion proof; damage on
any otherwise valid miss still blocks PASS. These precise expectations are authored
from WP05, but inventing a manifest grammar/API would not be an executable binding
to Hardware's public declaration. A ready subset is not a substitute for that work.

The production1000 aggregation and nonqualifying-damage behavior already tested by
the old27-case package is separately disposed on exact2faa1180. It supplies no proof
of a new plan4 manifest or completed-write rollback path. Both remain visibly pending.
U1us and delay500us are declared **model** values only; electrical justification,
representative slow/fast waveforms and E0–E3/dry-run measurements remain unqualified.
SPI characterization does not transfer to native SD4, media or system qualification.
