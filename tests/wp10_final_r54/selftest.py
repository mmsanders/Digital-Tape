#!/usr/bin/env python3
"""Final WP-10 backlog (#118) self-test: census, model proofs, clean synthetic run, causal controls."""
from __future__ import annotations

import sys

import dupmodel as DM
import oracle as O
from synthetic_adapter import MUTANTS, lines, observation

EXPECTED = {"row1": 13, "row2": 6, "row3_groups": 5, "row4": 207_560, "row4_representatives": 16,
            "caseset_sha256": "159b4ac64a5e653df2625a025f5f8cf13bcb90fed9a11905a1733f7a97167cd1"}
# Rows 1-2: every control must kill exactly these contract cases, and no others.
EXACT_KILLS = {
    "reset_b_ignores_sequence_headroom": {"RB-HEALTHY-SEQ-SHORT", "RB-DEGRADED-SEQ-SHORT", "SC-RESETB-SEQ-SHORT"},
    "stage_clear_before_headroom": {"SC-RESETB-GEN-SHORT", "SC-RESETB-SEQ-SHORT", "SC-ARM-GEN-SHORT",
                                    "SC-ARM-SEQ-SHORT", "SC-RESPOOL-GEN-SHORT", "SC-RESPOOL-SEQ-SHORT"},
    "stage_clear_generation_not_counted": {"SC-RESETB-GEN-SHORT", "SC-ARM-GEN-SHORT", "SC-RESPOOL-GEN-SHORT"},
    "zero_needed_consults_counters": {"ZN-EMPTY-SEQ-FFFFFFFE", "ZN-EMPTY-SEQ-FFFFFFFF", "ZN-EMPTY-GEN-FFFFFFFE",
                                      "ZN-EMPTY-GEN-FFFFFFFF", "ZN-NONEMPTY-GEN-FFFFFFFF"},
    "respool_ignores_sequence_headroom": {"ZN-NONEMPTY-SEQ-FFFFFFFE"},
}
# Row 4: the #116 hazard must be caught by outcomes alone, not only by trace binding.
OUTCOME_ONLY = {"rerun_skips_barrier", "rerun_final_keeps_old_uuid"}
REQUIRED_CLASSES = {("TAPE_ERR_BAD_MAGIC", None), ("TAPE_OK", "old"), ("TAPE_OK", "new"),
                    ("TAPE_ERR_INCOMPLETE", None), ("TAPE_ERR_INCONSISTENT", None)}


def identity_census():
    """Model proof over every permitted durable image of every planned re-run injection: a writable Side-A
    mount pairs the previous identity with the source's audio (or the fresh identity with the old audio)
    exactly in O.PM_FINDING_CELLS, where every permitted image does so (the frozen contract forces it)."""
    images, violating_cells = 0, set()
    for rep in O.rerun_representatives():
        ops = DM.dup_ops(rep["crashed"])
        for mode, inject in DM.injections(ops):
            imgs = DM.possible_images(rep["crashed"], ops, inject, mode)
            bad = 0
            for img in imgs:
                exp = O.mount_expectation(img, "A", True)
                if exp["results"] == ["TAPE_OK"] and O.identity_violation(
                        {"rw_A": {"result": "TAPE_OK", "info": exp["info"], "pcm_sha256": exp["pcm_sha256"]}}):
                    bad += 1
                images += 1
            if bad:
                assert bad == len(imgs), (rep["shape"], mode, inject)
                violating_cells.add((rep["shape"], tuple(rep["first_inject"]), mode, inject))
    assert violating_cells == O.PM_FINDING_CELLS, sorted(violating_cells ^ O.PM_FINDING_CELLS)
    assert {tuple(r["class"]) for r in O.rerun_representatives()} == REQUIRED_CLASSES
    return images, len(violating_cells)


def main():
    census = O.plan_census()
    for k, v in EXPECTED.items():
        assert census[k] == v, f"census {k}: {census[k]} != {v}"
    images, finding_cells = identity_census()
    n, row3, findings = O.check_stream(lines())
    assert findings == {"v_r54_03_resurrected_previous_superblock": finding_cells}, findings
    killed = {}
    for mutant, row in MUTANTS.items():
        for trust_trace in ((False, True) if mutant in OUTCOME_ONLY else (False,)):
            reds, where = 0, set()
            for case in O.iter_cases():
                if case["row"] != row:
                    continue
                try:
                    O.check(case, observation(case, mutant), trust_trace)
                except AssertionError:
                    reds += 1
                    where.add(case.get("case") or case.get("fixture") or f"{case['shape']}/{case['class']}")
            assert reds, f"control {mutant} (trust_trace={trust_trace}) survived"
            if mutant in EXACT_KILLS:
                assert where == EXACT_KILLS[mutant], f"control {mutant} killed {sorted(where)}"
            killed[(mutant, trust_trace)] = (reds, len(where))
    assert {r for r in MUTANTS.values()} == {1, 2, 3, 4}
    print(f"PASS census row1 {census['row1']} + row2 {census['row2']} contract cases, row3 {census['row3_groups']} "
          f"groups ({row3} crash injections), row4 {census['row4']} ({census['row4_by_mode']}) over "
          f"{census['row4_representatives']} interruption representatives; caseset {census['caseset_sha256']}; "
          f"identity census over {images} permitted re-run images: PM finding V-R54-03 forced in exactly "
          f"{finding_cells} cells; clean synthetic {n}/{n} (findings {findings}); "
          f"{len(MUTANTS)} controls killed: "
          + ", ".join(f"{m}{'[outcome-only]' if t else ''}={r} in {g}" for (m, t), (r, g) in killed.items()))


if __name__ == "__main__":
    sys.exit(main())
