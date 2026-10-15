# Existing WP-10 route: import and observation dependency

**P2V183-EXEC-001 — Product-side import required.** At Product input `c6ff868`,
the public `tests/crash_core_adapter/README.md`, `promote_adapter/README.md`,
`respool_full_adapter/README.md` and `format_dup_identity_adapter/README.md`
describe workers with their own working/durable image backends, driven by the
published fixed case protocols. The independent C69/R29 planners expose only
`flush_required` and `write_through`; their ordinal-based durable predictions
cannot encode an arbitrary event subset. Passing a third mode name or replaying
a synthetic image through these unchanged workers would not run this model.
This package cannot replace a backend inside those compiled workers from here.
PM must route the bounded import/binding to Software, as #183 explicitly allows.

Use those existing adapters and accepted fixtures, not a new engine or port.
Keep engine tree `d96b4245e04d74078f8938744b1394c3018516f7` unchanged. The binding
may implement the device callbacks in C with this Python model as the independent
shadow, or transport callbacks to this model. Verification owns persistence
selection and the original operation-outcome judgments; Software transports
actual callbacks and raw observations. Do not import operation verdicts into the
Product worker. Before importing, record this publication's commit and subtree;
do not amend the earlier immutable suites.

| Operation | Existing independent shapes / route | Permitted-outcome boundary |
|---|---|---|
| load | Existing WP-11/WP-14 load transaction, through public arm/feed/service/commit cadence | Source-data and committed-index recovery under tapefs §8.1; pre-write overage refusal remains zero-write. There is no public `tape_load` API to invent. Bind the existing host load route. |
| commit/record | `crash_core_draft8`: overwrite, overdub, splice, durable chunk before entry/header; existing later WP-10 closure variants | Validate winning committed state and preserved references/PCM; an uncommitted inactive slot may be invalid. |
| reset-b | `crash_core_draft8`: healthy, degraded/equal; stage-clear caller and two-interruption closure | Preserve A; use B's issued recovery rules, including valid intermediate degraded-B winners. |
| promote | `promote_draft8`: fresh allocation/adoption, first-use S0, decline/resume and partner/candidate closures | Existing stage oracle, H, A/B references, permitted intermediate phase and resume states, not only old/new images. |
| respool | `respool_full_draft8`: v3_003 pass1/pass2, no-lower-run decline, stage-clear/closure and resume | Existing logical PCM, high-water, relocated-index and resume predicates; physical placement may change. |
| dup | `format_dup_identity_draft8` fixtures with current `wp10_residue_d10` / `wp10_backlog_r54` supersession | DRAFT-10 tapefs §9.5/§9.6 identity/residue ordering, not the superseded DRAFT-9 fixed-identity expectations. |

For **each** accepted scenario and each write-unit boundary (including inside a
multi-block call), and each barrier entry/error, capture the initial durable
image and actual event history. Retain LBA, 512 bytes, absolute event ID, original
call ID/count, acknowledgement/error, barrier results and cut coordinate. Apply
all small-epoch classes (≤8); for larger epochs use the recorded 3 seeds and
67 records/seed, labelled sampled. Report real bounds and duplicates separately.
Include successful-operation controls, error writes/flushes and both interruptions
of accepted closure shapes. Repeat after actual recovery for the second cut;
never reuse the first run's volatile image or assumed event trace.

Before a cut, the original worker must see its normal logical working bytes.
At the cut, materialize the chosen durable projection. Destroy all engine and
device RAM, then remount via the existing public API. Return raw pre/post media,
mount/recovery result codes, public state and render/PCM observations needed by
the original predicates. Binding transport must allow arbitrary grouping; the
shadow splits actual writes at 512 and does not require a golden call trace.

Return exact Product commit, A8 tree comparison, imported subtree, adapter source
identity/build command, initial-image hashes, complete event/flush traces, actual
masks/orders and byte-image hashes, operation coordinates and raw outcomes. First
prove the binding produces `(a,B)`, reverse-order repeated-LBA persistence and a
fresh second remount. Prove ordinary all/none match the old bounded modes. Prove
successful barriers end epochs and failure does not. Preserve the separate torn
suite. Run a deliberate dropped-barrier/early-identity control against the
operation's existing raw-state oracle, without modifying the shipped engine.

**Return ownership:** after import, Verification compares actual byte projections
with `model.py`, then evaluates each operation with its own permitted crash-state
predicates extended to these durable projections. The older ordinal-only oracles
must not be used unmodified as subset oracles. Their fixture/state/recovery
predicates are reusable; their all/none durability calculations are not. This
last independent evaluation is still pending, along with engine execution; this
authoring publication does not claim the six operation campaigns are complete.
Any violation goes to Product #384 with trace, selected order and minimal image;
no engine fix, waiver, universal preservation rule or batching permission follows.
