#!/usr/bin/env python3
"""WP-10 backlog (#116) self-test: census, §9.5 interruption classes, clean synthetic run, causal controls."""
from __future__ import annotations

import model as M
import oracle as O
from synthetic_adapter import MUTANTS, lines, observation

EXPECTED = {"row1": 4_112, "row2": 64_734, "row3": 8,
            "caseset_sha256": "6808330224da3129371f482e1828eab36b801d7caa13652dfc69a99e7493aaf3"}
OLD = M.OLD_UUID.hex()
NEW = M.B.FRESH_DUP_UUID.hex()
# tapefs §9.5 permitted-outcome classes each destination shape must reach before its re-run.
REQUIRED_CLASSES = {
    "blank": {("TAPE_ERR_BAD_MAGIC", None), ("TAPE_OK", "new")},
    "healthy_pair": {("TAPE_OK", "old"), ("TAPE_ERR_INCOMPLETE", None), ("TAPE_OK", "new")},
    "equal_divergent": {("TAPE_ERR_INCONSISTENT", None), ("TAPE_OK", "old"), ("TAPE_ERR_INCOMPLETE", None),
                        ("TAPE_OK", "new")},
    "exhaustion_candidate": {("TAPE_OK", "old"), ("TAPE_ERR_BAD_MAGIC", None), ("TAPE_ERR_BAD_MAGIC", "residue"),
                             ("TAPE_OK", "new")},
    "exhaustion_equal_divergent": {("TAPE_ERR_INCONSISTENT", None), ("TAPE_OK", "old"),
                                   ("TAPE_ERR_BAD_MAGIC", None), ("TAPE_ERR_BAD_MAGIC", "residue"),
                                   ("TAPE_OK", "new")},
}


def interruption_classes():
    seen = {s: {} for s in M.RERUN_SHAPES}
    for shape in M.RERUN_SHAPES:
        base = M.rerun_destination(shape)
        ops = M.dup_ops(base)
        for mode, inject in M.injections(ops):
            for img in M.possible_images(base, ops, inject, mode):
                c = M.classify(img, "A", False)
                kind = None if c["result"] != ("TAPE_OK",) else ("new" if c["uuid"] == NEW else "old")
                if M.is_residue(img):          # DRAFT-10 V10-001: re-runs through residue zeroing
                    kind = "residue"
                    assert M.dup_ops(img)[:4] == [("w", "M", M.ZERO), ("f",), ("w", "P", M.ZERO), ("f",)]
                key = (c["result"][0], kind)
                seen[shape][key] = seen[shape].get(key, 0) + 1
                # every class, including the torn-magic BAD_MAGIC/CRC one, must re-run to the same copy
                assert M.digest(M.apply(img, M.dup_ops(img))) == M.digest(M.apply(base, ops)), (shape, inject)
    for shape, need in REQUIRED_CLASSES.items():
        missing = need - set(seen[shape])
        assert not missing, f"{shape}: interruption classes never reached {missing}"
    return seen


def main():
    census = O.plan_census()
    for k, v in EXPECTED.items():
        assert census[k] == v, f"census {k}: {census[k]} != {v}"
    classes = interruption_classes()
    n = O.check_stream(lines())
    killed = {}
    # A re-run that skips step 1 ends in byte-identical completed media (step 4 rewrites both copies),
    # so only its write order, or a crash inside the re-run, can expose the missing barrier.
    # Skipping residue zeroing likewise ends in byte-identical completed media; only the trace, or a second
    # interruption inside the re-run (wp10_residue_d10 row R1), can expose it.
    trace_only = {"rerun_skips_barrier", "rerun_skips_residue_zeroing"}
    for mutant, row in MUTANTS.items():
        for trust_trace in ((False, True) if row in (1, 2) and mutant not in trace_only else (False,)):
            reds, groups = 0, set()
            for case in O.iter_cases():
                if case["row"] != row:
                    continue
                try:
                    O.check(case, observation(case, mutant), trust_trace)
                except AssertionError:
                    reds += 1
                    groups.add(case.get("shape") or case.get("source"))
            assert reds, f"control {mutant} (trust_trace={trust_trace}) survived"
            killed[(mutant, trust_trace)] = (reds, len(groups))
    assert {r for r in MUTANTS.values()} == {1, 2, 3}
    print(f"PASS census row1 {census['row1']} {census['row1_by_mode']} row2 {census['row2']} {census['row2_by_mode']} "
          f"row3 {census['row3']}; caseset {census['caseset_sha256']}; clean synthetic {n}/{n}; "
          f"re-run classes {sum(len(v) for v in classes.values())} over {len(classes)} shapes, all §9.5 rows reached; "
          f"{len(MUTANTS)} controls killed: "
          + ", ".join(f"{m}{'[outcome-only]' if t else ''}={r} in {g} groups" for (m, t), (r, g) in killed.items()))
    for shape, seen in classes.items():
        print("  ", shape, sorted(seen.items(), key=str))


if __name__ == "__main__":
    main()
