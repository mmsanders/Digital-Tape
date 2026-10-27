# Windows diagnostic expectations r2 — Verification332

Additive correction to published r1 tree08b6d314e04fd439cf9f74880c9c7a2f631e451e
at d916750db4974467b9cc79a6e5f242b5baa2ecff. Original r1 stays immutable.
All original C01–C28 method, limits, controlled-helper scope and native holds carry.
No Product or process execution occurs in these independent scripts.

Software594 correctly reported two defects in our oracle. `receipts.py` corrects
only their predicates, retaining schema1 and its closed fields: positive epoch
nanoseconds are exact unsigned64 integers, rather than bounded by JavaScript's
53-bit Number range; keep original integer bytes, never divide timestamps or
round-trip through a lossy numeric parser. Work counters retain their old bound.
Each scheduled work freezes the cumulative ordered accepted folders as of its drop;
Start over clears the current accumulation but never rewrites older work snapshots.
Rejected/no-change drops add nothing. Windows production identity is unknown in
the existing classifier, so scheduled Windows drops retain each incoming folder;
no new deduplication behavior or non-Windows receipt qualification is inferred.

`cases.py` is unchanged from r1. `regressions.py` proves full-size epochs and
cumulative/reset cases, rejects invalid timestamp types/ranges and missing,
reordered or added folder arguments, and adds focused controls for existing
provenance, limit-stop, incomplete and footer obligations. These are independently
authored corrections and source-review predicates, not Product test passes.

The complete-footer check also rejects a cancelled child with no retained report;
missing report facts cannot silently become complete simply because it was killed.
An explicitly incomplete receipt remains valid partial evidence.

The old 594 originals may be rejudged OFFLINE against this package without rerunning
their accepted actual rows. The reported C13-cumulative `oracle-gap` expectation
is a complete original chain under APP-1 §2; it is no longer an expected rejection.
The old catch-all timestamp rejection cannot qualify negative controls: a real
unmodified positive must pass, then EACH mutation must fail for its own cause.
Any source correction needs only its impacted controlled cases plus normal CI.
No permission is issued to rerun a native app/INGEST/poller/device or to dispatch
old full campaigns. C02's positive contrast is still unexecuted; two false console
associations are no positive control. Use only the published existing permitted
console-attached harmless-helper method if actually available; do not fabricate a
PASS, change security/provider or ask Michael to repeat564.
