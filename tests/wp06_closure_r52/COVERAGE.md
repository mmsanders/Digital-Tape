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

## R53 correction (Verification #108)

PM ruled the original floor predicate for F-LIVEB-PROMOTE-FLOOR and F-LIVEB-RESPOOL-FLOOR wrong. It required every chunk write to be at or above the pre-operation live-B floor, but promote phase 2 (tapefs §9.3.2 step 6) and re-spool pass 2 (§9.4) lawfully write below it.

The corrected oracle requires four things:

- (a) the phase-1/pass-1 allocation, before the first index commit, is one run of `len` at or above the floor;
- (b) every chunk write is disjoint from both sides' live set, rebuilt from the raw index commits seen so far;
- (c) re-spool pass 2 is at or above `a_high_water` and strictly lower, and promote phase 2 is exactly `[0, len)` after the phase-1 A and B commits and the step-4 superblock;
- a fixture precondition: live B densely fills `[a_high_water, floor)`, because §9.4 alone permits a pass-1 run anywhere at or above `a_high_water` that is disjoint from the live set.

The synthetic adapter now performs the lawful second phase, and the old predicate rejects it. Each row has four controls: `below_floor`, `below_floor_unreferenced` (rule (a) alone), `second_phase_live` (rule (b)) and `second_phase_shape` (rule (c)).
