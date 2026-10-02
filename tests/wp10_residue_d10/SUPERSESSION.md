# Supersession record: DRAFT-9 expectations replaced under DRAFT-10 (Verification #138)

**Basis.** Issued DRAFT-10 (Product main `d8243c95`):

- tapefs `2a6a9f7b…9c17eba`;
- engine-api `aa042e41…c66b33a`;
- acceptance `50aa63bd…9b9e547`.

The acceptance WP-10 **Residue destinations** paragraph ends: "this replaces the DRAFT-9 V-R54-03 cells". The
machine-readable form is `SUPERSESSION.json`, which `audit.py` checks against the planner.

**How to retire the pins.** The Software tranche that lands the V10-001 engine change will break these
accepted byte-identical gates, correctly. Retire exactly the cases below as a recorded supersession, not as an
edit, and bind the replacement rows. Nothing else in those packages changes.

| Id | Old package @ subtree (case set) | Product binding / disposition | Rows and cases replaced | Replaced by |
|---|---|---|---|---|
| S1 | `wp10_final_r54` @ `598ebcd8` (`159b4ac6…`) | PR #336 / #128 PASS 207,584 | Row 4 `WP10.dup.rerun_crash`, 2 of 16 representatives. **22,604** cases: indices 131,548–142,849 (`exhaustion_candidate`) and 182,924–194,225 (`exhaustion_equal_divergent`). Both are class `BAD_MAGIC`, first cut `["write",1,1]` flush-required. Includes all **48 V-R54-03 cells** (`oracle.PM_FINDING_CELLS`). | `wp10_residue_d10` R1 dup groups 0, 511, 1022, 1533 (L1 = 1, scope `all_writes`, both modes): the same first cut, re-run injected at every write, landed length and flush. The rest of R1 extends this to L1 1…511, both mirror-candidate shapes, and format. |
| S2 | `wp10_backlog_r54` @ `d6e9a242` (`68083302…`) | PR #330 / #120 PASS 68,854 | Row 2 `WP10.dup.rerun_completes`. **5,110** cases: 10 groups of 511 (landed 1…511), listed below. | The same package and case indices at this publication's subtree. The re-run planner follows DRAFT-10, so the re-run trace and re-run images change; the final media do not. The case set `68083302…` is unchanged. |
| S3 | `format_dup_identity_draft8` @ `f76ab23d` (`c493e77d…`) | R29-B accepted | Crash scope: the final mirror write torn after 8…511 bytes, on both exhaustion shapes. **4,032** cases, listed below. | **Relaxation (V10-003).** These states have no valid copy and a magic-intact copy. R29-B predicts `TAPE_ERR_BAD_MAGIC` and compares exactly, but §4.1 permits `TAPE_ERR_CRC` too. `wp10_residue_d10` R1/R2 `sb_mirror` assert the same superblock states with both codes permitted. R29-B is not edited (pinned), and no change is needed while the engine answers `BAD_MAGIC`. |

## S2: index ranges (`wp10_backlog_r54` row 2)

| Shape | Mode | Cut | Indices |
|---|---|---|---|
| blank | flush_required | write 9 → M (fresh mirror) | 8,730–9,240 |
| blank | write_through | write 9 → M | 14,381–14,891 |
| exhaustion_candidate | flush_required | write 1 → P (last fallback zero) | 42,644–43,154 |
| exhaustion_candidate | flush_required | write 11 → M (fresh mirror) | 47,774–48,284 |
| exhaustion_candidate | write_through | write 1 → P | 49,323–49,833 |
| exhaustion_candidate | write_through | write 11 → M | 54,453–54,963 |
| exhaustion_equal_divergent | flush_required | write 1 → P | 56,002–56,512 |
| exhaustion_equal_divergent | flush_required | write 11 → M | 61,132–61,642 |
| exhaustion_equal_divergent | write_through | write 1 → P | 62,681–63,191 |
| exhaustion_equal_divergent | write_through | write 11 → M | 67,811–68,321 |

## S3: index ranges (`format_dup_identity_draft8` crash scope, write ordinal 2, landed 8…511)

| Operation | Shape | Mode | Indices |
|---|---|---|---|
| format | exhaustion_candidate | flush_required | 21,594–22,097 |
| format | exhaustion_candidate | write_through | 23,650–24,153 |
| format | exhaustion_equal_divergent | flush_required | 25,706–26,209 |
| format | exhaustion_equal_divergent | write_through | 27,762–28,265 |
| dup | exhaustion_candidate | flush_required | 50,378–50,881 |
| dup | exhaustion_candidate | write_through | 52,434–52,937 |
| dup | exhaustion_equal_divergent | flush_required | 54,490–54,993 |
| dup | exhaustion_equal_divergent | write_through | 56,546–57,049 |

## Why these and only these

**The scan rule.** A case is in S1 or S2 if and only if the durable state its re-run starts from (any
permitted image) has no structurally valid superblock but is not all-zero in both superblock blocks. Under
DRAFT-9 such a state re-ran as blank; under DRAFT-10 it re-runs through residue zeroing. The scan was run
mechanically over both accepted packages at the subtrees above.

**What is unaffected.**

- **`wp10_final_r54`:** the other 184,980 of 207,584 cases (rows 1–3, and the other 14 row-4
  representatives).
- **`wp10_backlog_r54`:** rows 1 and 3, and the other 59,624 row-2 cases.
- **`wp10_closure_r53` and `wp10_backlog_r53`:** no re-runs, and their blank fixtures are all-zero.
- **The rest of R29-B:** it has no residue shapes and no re-run.

**DRAFT-9 rule witness** (`evidence/d9_census.json`). Over the 17,025,380 R1/R2 injections, the DRAFT-9 rule
mounts the previous identity at 1,456 injections in 200 groups. The 48 V-R54-03 cells are the dup, L1 = 1,
primary-candidate subset. DRAFT-10 has none.
