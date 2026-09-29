# WP-06 R52 closure coverage

The machine-readable authority is `coverage-ledger.json`. The audit authenticates prior accepted campaigns rather than re-running them. Seven distinct observable gaps are packaged, exceeding the “three distinct rows” branch of the Phase 1 minimum; cases are not padded.

| Case | Frozen row | Causal observation |
|---|---|---|
| E-SIDEA-REFUSE | WP-06e stage-1 arm on Side A | READ_ONLY, byte-identical media, zero writes |
| E-RESPOOL-FULL | WP-06e stage-1 re-spool with no destination | CARTRIDGE_FULL, stage remains 1, zero writes |
| E-RECORD-PROMOTE | WP-06e stale-stage ordinary-use chain | clear → record commit → later promote completes |
| F-STAGE-DEGRADED-ABSENT | WP-06f stage-1 plus absent B | reset clears stage, remount selects B, set-side succeeds |
| F-STAGE-DEGRADED-DIVERGENT | WP-06f stage-1 plus equal-divergent B | same recovery, including surviving higher/equal slot hazard |
| F-LIVEB-PROMOTE-FLOOR | WP-06f Side-A mount with recorded B | every promote chunk destination is above live B |
| F-LIVEB-RESPOOL-FLOOR | WP-06f Side-A mount with recorded B | every re-spool chunk destination is above live B |

Two literal WP-06e clauses cannot be constructed through the frozen public contract. All three `tapefs` §9.3.3 stage-1 rows require a one-entry live B, so a mountable stage-1 cartridge cannot be index-full. A zero-entry B matches none of those rows, so stage-1 plus empty is refused by mount before `tape_respool` can run. They remain `missing Product observation` in the ledger, with explicit blockers; no fake case is invented.

Excluded: Product implementation/source review, self-acceptance, full WP-10/WP-11/WP-12 campaigns, hardware, release, and accepted campaigns already bound in the ledger.
