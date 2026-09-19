# P1-R17-SW — VT8-001 two-case product run (BLOCKED)

**Issue:** [#95](https://github.com/mmsanders/Digital-Tape/issues/95) ·
**Input product main:** `a277ee7d52b26a5cf100b6d3bd69e2b6f6638802` ·
**Date:** 19 September 2026 UTC

This packet is **raw observation, not acceptance**. It records a product run that
**failed**, and the reason it failed is a defect in the verifier fixture rather
than in the engine. Nothing here accepts a package, a source design, a helper or
an operation, and nothing here is a Verification disposition.

## What is in here

| Path | What it is |
|---|---|
| `product-evidence/` | The authentic run: unchanged `tests/ops_draft8/` runner, unchanged product adapter, `adapter_kind=product`, 120 s timeout. **Both cases FAIL.** |
| `diagnostic/geometry.txt` | The arithmetic showing the fixture superblock is not §4.1-admissible. |
| `diagnostic/replay-divergence.txt` | Why `replay.py` cannot close over a failing run, proven exactly. |
| `diagnostic/diag.py` | Software-owned script that imports the package read-only and changes **one** fixture field. |
| `diagnostic/geometry-corrected-bundle/` | What that script produced: **both cases PASS**. |

## The blocker

`tests/ops_draft8/oracle.py`'s `sb()` helper writes `nominal_length_s = 60` at
offset 48 while writing `total_chunks = 16` at offset 52 and sizing the device at
`2048 + 16*1024 + 1 = 18433` blocks. TapeFS DRAFT-8 derives `total_chunks` from
the superblock's **own** `nominal_length_s`, and 60 s derives **21**, not 16.

That superblock fails §4.1 phase 2 step 5 in **two independent ways**:

1. **§2.1 GEOMETRY_OK line 3** — `2048 + 21*1024 = 23552` is not `<= 18432`.
2. **§4.1 phase 2 step 5, last line** — stored `total_chunks` 16 does not equal
   the derived 21. That line is bolded normative text, and DRAFT-8's own note
   says equality "replaces DRAFT-4's pair of separate inequalities".

Either alone is `TAPE_ERR_GEOMETRY` with zero writes. **Both VT8-001 fixtures are
therefore unmountable by any DRAFT-8-conforming engine**, so neither case can
reach the operation it exists to test.

This is not an interpretation this candidate invented. The independently landed
mount package derives the same way and has a negative control for exactly this
mismatch:

- `tests/mount_draft8/cases.py:27` — `chunks(seconds) = (seconds*44100 + CF-1)//CF`
- `tests/mount_draft8/cases.py:115` — `n=chunks(seconds); bc=2048+n*1024+1`
- `tests/mount_draft8/cases.py:120` — `('chunks', chunks(60)+1)` → refuse `GEOMETRY`

Those 286 mount records pass against this same engine build.

The package's own `selftest.py` cannot see the defect: its synthetic path never
mounts a real engine, so the superblock's geometry is never evaluated. That is
exactly what `tests/ops_adapter/README.md` predicted — *"the first product run is
where that schema is actually tested."*

## Is geometry the only blocker?

No other one was found. `diagnostic/diag.py` imports `tests/ops_draft8/` read-only
and changes **one field of one structure**: `nominal_length_s` 60 → 46, at offset
48, with the superblock CRC recomputed. Every assertion, every expected value,
every other fixture byte, the oracle, the hardening layer and the runner are the
package's own, unmodified. Result:

```
VT8-001-RB-ALLSLOT: PASS
VT8-001-REC-ALLOCSEQ: PASS
2 cases; 0 failed
```

`46` is one of exactly three values (45, 46, 47) that derive 16 chunks and satisfy
line 3 at this device size. **Choosing among them, or changing `total_chunks` and
the device size instead, is Verification's decision, not Software's.** This
directory contains no change to `tests/ops_draft8/`; the tree is still
`4a862fa69ccb2fc4c9afe59c9c9161c3470f9263`.

**The corrected-geometry bundle is not evidence and carries no coverage.** Its own
replay correctly refuses it — `replay.py` regenerates the fixture from
`make_cases()` and reports *"input media differs from independently generated
fixture"*, which is the check doing its job.

## Second, smaller finding — replay cannot close over a failing run

`replay.py` recomputes `hardened.check(...)` and compares it for exact equality
against the saved verdict. `runner.py` additionally records its own runner-level
strings, among them `adapter returned {rc}`. So a bundle whose adapter exited
nonzero can never replay-match, whatever the cause.

`diagnostic/replay-divergence.txt` shows the divergence is **exactly** that one
string, in both cases, and nothing else:

- input media **equals** the independently regenerated fixture — for both cases;
- every file hash binding verifies;
- the DRAFT-8 spec bytes authenticate;
- saved minus recomputed = `['adapter returned 1']`;
- recomputed minus saved = `[]`.

So "prove unmodified offline replay", which issue #95 requires, is **structurally
unavailable for a failing run** with this package. It is reported rather than
worked around: no evidence byte was edited to make replay agree.

## Exclusions — what this packet does NOT establish

Nothing about: warm start; overwrite or overdub; `tape_abort`; zero-frame commit;
crash injection or recovery; FAULTED quarantine; promote, re-spool, duplicate or
format; stage clearing (both fixtures are `promote_stage == 0`, so that path never
executed); interior splice or splice at an entry boundary (only the append row ran);
partial-block record drain, multi-chunk allocation or a `CARTRIDGE_FULL` short
accept; long-operation continuation; target performance; media atomicity; goldens;
or human listening. It establishes no package acceptance and no operation freeze.
