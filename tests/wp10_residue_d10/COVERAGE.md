# Coverage: WP-10 residue destinations (DRAFT-10, Verification #138)

**Criterion.** This package covers:

- acceptance WP-10 **Residue destinations** (V10-001);
- tapefs §9.5 item 5, the residue path of §9.5 step 1, the §9.6 step-1 residue rule, and the new and
  changed §9.5/§9.6 crash-table rows.

**Model.** The pinned `wp10_backlog_r54/model.py` (blob `0981d100`) with its DRAFT-10 `step1_ops`. Format
follows §9.6 exactly: step 1, then A1/B1 zero, flush, then empty A0/B0 headers, flush, then the mirror,
flush, then the primary, flush.

## Census (`plan.census()`, caseset `849a82ab…04b1f8`)

| Row | Groups | Injections | What |
|---|---|---|---|
| R1 dup | 4,088 | 8,466,392 | shape (a): 4 exhaustion shapes × 2 modes × L1 1…511 |
| R1 format | 4,088 | 8,429,520 | the same, `tape_format` |
| R2 dup | 12 | 80,148 (+12,336 closure re-runs) | shapes (b) torn/CRC × primary/mirror, (c) foreign, (d) `0xFF` × 2 modes |
| R2 format | 12 | 49,320 (+12,336 closure re-runs) | the same, `tape_format` |
| R3 dup / format | 4 / 4 | – | all-zero blank (whole device; zero superblocks over an old cartridge) × 2 modes |

The total is **17,025,380** injected re-runs plus **24,672** closure re-runs.

**Shape (a).** These are the acceptance's four shapes:

| Shape | Primary | Mirror | Fallback order | Residue copy |
|---|---|---|---|---|
| `exhaustion_candidate` | gen `0xFFFFFFFD` | gen `0xFFFFFFFC` | M then P | primary |
| `exhaustion_equal_divergent` | gen `0xFFFFFFFD` | gen `0xFFFFFFFD` | M then P | primary |
| `exhaustion_mirror_only` | zero | gen `0xFFFFFFFD` | P then M | mirror |
| `exhaustion_mirror_candidate` | gen `0xFFFFFFFC` | gen `0xFFFFFFFD` | P then M | mirror |

The first two come from R29-B. The last two carry the label "Previous tape", so the identity check also has a
label to catch.

**Injections per re-run.** Every landed length 0…512 of both residue zeros and both fresh superblock writes,
plus every flush. That is 2,062 per dup group and 2,058 per format group. Some groups use scope `all_writes`
and inject at every write: R2, and R1 at L1 = 1, which is the exact counterpart of the superseded
`wp10_final_r54` row-4 representative. Those take 6,679 per dup group and 4,110 per format group.

## Assertions

1. **Exact.** For every observation:
   - the trace is the planned §9.5/§9.6 order from the observed state;
   - the durable image is one a conforming §8.1 device may hold;
   - the mount result is the §4.1 result for those bytes, from `{BAD_MAGIC, CRC}` where a copy keeps its
     magic (V10-003).
2. **Crash tables, by phase.**

   | Phase | Permitted |
   |---|---|
   | Residue zeroing | unmountable |
   | Steps 2–3 | unmountable |
   | Fresh mirror write and its flush | unmountable or the completed operation |
   | Fresh primary write, and after | the completed operation |

3. **Identity.** No injection mounts under anything but the fresh UUID and the fresh label. This is the
   acceptance property ("previous UUID or label over the copied indices"), stated absolutely.
4. **Precondition (a).** The torn last zero remounts unmountable (the §9.5/§9.6 "last zero tore" row). Every
   uninterrupted re-run completes and mounts fresh.
5. **R3.** Zero step-1 calls: the first write is not a superblock LBA, and exactly two superblock writes
   occur.

## Two-interruption closure

**R1.** The precondition is the first interruption, and each injection is the second.

**R2.** Each residue-zeroing interruption is followed by an observed uninterrupted re-run (`closure`), which
must reach the completed media and mount fresh.

**Every state, by convergence.** `selftest.check_convergence` proves mechanically that every residue-zeroing
interruption state:

- is residue or blank;
- re-plans to the same post-step-1 media as the precondition;
- has the same remaining writes.

So the fresh-superblock injections enumerated from the precondition are exactly those of any such state. The
check runs on the self-test sample. The argument is structural: residue zeroing writes only the two superblock
LBAs, and the oracle asserts that every such state is unmountable.

## Outcomes reached (full synthetic run, `evidence/synthetic/manifest.json`)

Every permitted category is reached in every phase:

- `TAPE_ERR_CRC` arises in the fresh-mirror phase (torn after ≥ 8 bytes), and in R2's residue phase on the
  CRC-broken shapes.
- R1's residue phase is `BAD_MAGIC` only, because a torn zero keeps the magic broken.

## Causal controls (`selftest.py`; exact expected red sets on 176 sample groups)

| Control | Red (trace and outcome) | Red (outcome only) |
|---|---|---|
| `skip_residue_zeroing` (DRAFT-9 rule) | all 168 R1/R2 | 72: R1 with L1 ≤ 12, and the R2 (b) torn shapes; the previous identity mounts |
| `residue_zero_order` (primary first) | 168 | 0 |
| `residue_zeroes_nonzero_copy_only` | 168 | 0 |
| `zero_blank_as_residue` | 32: R3, plus R2 closure re-runs from blank | 8 (R3: step-1 calls on blank) |

**DRAFT-9 census** (`d9_census.py` → `evidence/d9_census.json`). Over the full census the DRAFT-9 rule
mounts the previous identity at **1,456** injections in 200 groups: 85 per (op, exhaustion shape, mode),
and 12 per (b) torn group.

- A torn fresh write restores the old superblock when it lands up to 12 bytes (magic and version are
  shared) and reaches the first residue byte that differs from the old block.
- The **48 V-R54-03 cells** are the dup, L1 = 1 subset on the two primary-candidate shapes.
- DRAFT-10 has **0** such injections.

## Not covered here

- Template and fallback paths before the last zero tears: those are covered by the existing rows (R29-B,
  `wp10_closure_r53`, `wp10_backlog_r54` row 2).
- Product binding: pending the Software tranche.
