#!/usr/bin/env python3
"""Self-test for the DRAFT-10 residue rows (#138): census, fixture classification, two-interruption
convergence, clean synthetic run on the control sample, and causal controls.

The full clean run (17,025,380 injections) is `synthetic_adapter.py | replay.py -`, which CI runs.
"""
from __future__ import annotations

import plan as P
from oracle import Oracle
from pins import M
from synthetic_adapter import MUTANTS, observation

EXPECTED = {
    "groups": {"R1.dup": 4088, "R1.format": 4088, "R2.dup": 12, "R2.format": 12, "R3.dup": 4, "R3.format": 4},
    "injections": {"R1.dup": 8_466_392, "R1.format": 8_429_520, "R2.dup": 80_148, "R2.format": 49_320},
    "injections_total": 17_025_380,
    "closure_reruns": 24_672,
    "caseset_sha256": "849a82ab2e8e4b207a52789e2c6e9dd247c3db947431e7beb4ed14916f04b1f8",
}
SAMPLE_L1 = (1, 2, 11, 12, 13, 255, 256, 510, 511)   # 12 = bytes the old and fresh superblocks share
RESIDUE_ZEROING = [("w", "M", M.ZERO), ("f",), ("w", "P", M.ZERO), ("f",)]


def sample():
    return [g for g in P.iter_groups() if g["row"] != "R1" or g["l1"] in SAMPLE_L1]


def check_fixtures():
    # dup's fresh superblock is the one the pinned model writes
    assert M.dup_ops(M.cartridge(M.ZERO, M.ZERO))[-4] == ("w", "M", P.FINAL_SB["dup"])
    for op in P.OPS:
        for shape, (p, m) in P.EXHAUSTION_SHAPES.items():
            start = P.base(p, m)
            assert M.gen(p if M.sb_valid(p) and (not M.sb_valid(m) or M.gen(p) >= M.gen(m)) else m) >= 0xFFFFFFFD
            s1 = M.step1_ops(start)
            first, last = s1[0][1], s1[2][1]
            assert [o[2] for o in s1 if o[0] == "w"] == [M.ZERO, M.ZERO] and last == P.RESIDUE_COPY[shape]
            for mode in P.MODES:
                for l1 in P.L1:
                    pre, _, _ = P.precondition({"row": "R1", "op": op, "shape": shape, "mode": mode, "l1": l1})
                    assert M.is_residue(pre) and not any(pre[first]), (shape, l1)
                    assert pre[last] == M.ZERO[:l1] + start[last][l1:]
                    assert M.classify(pre, "A", True)["result"][0] == "TAPE_ERR_BAD_MAGIC"
                    assert P.op_ops(op, pre)[:4] == RESIDUE_ZEROING
    for shape, (p, m) in P.RESIDUE_SHAPES.items():
        img = P.base(p, m)
        assert M.is_residue(img) and P.op_ops("dup", img)[:4] == P.op_ops("format", img)[:4] == RESIDUE_ZEROING, shape
    for variant in P.BLANK_VARIANTS:
        img = P.blank(variant)
        assert not M.is_residue(img) and M.step1_ops(img) == [], variant


def check_convergence(groups):
    """Two-interruption closure: every state a residue-zeroing interruption can leave re-plans to the
    same post-step-1 media and the same remaining writes as the precondition, so the fresh-superblock
    injections enumerated from the precondition are exactly those from any such state."""
    n = 0
    for g in groups:
        if g["row"] == "R3":
            continue
        pre, _, _ = P.precondition(g)
        ops = P.op_ops(g["op"], pre)
        post = M.digest(M.apply(pre, ops[:4]))
        for inject, phase in P.rerun_injections(ops, P.step1_writes(pre), g["scope"]):
            if phase != "residue":
                continue
            for x in M.possible_images(pre, ops, inject, g["mode"]):
                s1 = M.step1_ops(x)
                assert s1 in ([], RESIDUE_ZEROING), (g, inject)
                assert M.digest(M.apply(x, s1)) == post and P.op_ops(g["op"], x)[len(s1):] == ops[4:], (g, inject)
                n += 1
    return n


def run(groups, mutant=None, outcome_only=False):
    o, red = Oracle(), set()
    for g in groups:
        try:
            o.check(g, observation(g, mutant), outcome_only)
        except AssertionError:
            red.add(g["index"])
    return o, red


def expected_red(mutant, outcome_only, g):
    row = g["row"]
    if row not in MUTANTS[mutant]:
        return False
    if mutant == "skip_residue_zeroing":
        # outcome-visible only where a torn fresh write can restore the old magic: residue with the old
        # bytes from offset l1 <= 12 onward (the leading bytes both superblocks share)
        return (not outcome_only) or (row == "R1" and g["l1"] <= 12) or g.get("shape", "").startswith("b_torn")
    if mutant == "residue_zero_order":
        return not outcome_only
    if mutant == "residue_zeroes_nonzero_copy_only":
        # (c)/(d) start with both copies non-zero, but their closure re-runs start from a half-zeroed state
        return not outcome_only
    if mutant == "zero_blank_as_residue":
        return row == "R3" or (row == "R2" and not outcome_only)
    raise KeyError(mutant)


def main():
    census = P.census()
    for k, v in EXPECTED.items():
        assert census[k] == v, f"census {k}: {census[k]} != {v}"
    check_fixtures()
    groups = sample()
    converged = check_convergence(groups)
    clean, red = run(groups)
    assert not red, f"clean synthetic red on groups {sorted(red)[:10]}"
    reached = {k: sorted(v) for k, v in clean.reached.items()}
    for (row, op, phase), cats in reached.items():
        allowed = {"unmountable": {"TAPE_ERR_BAD_MAGIC", "TAPE_ERR_CRC"}, "completed": {"completed"}}
        assert set(cats) <= set().union(*(allowed[c] for c in __import__("oracle").PERMIT[phase])), (row, op, phase)
    killed = []
    for mutant in MUTANTS:
        for outcome_only in (False, True):
            _, red = run(groups, mutant, outcome_only)
            want = {g["index"] for g in groups if expected_red(mutant, outcome_only, g)}
            assert red == want, (f"control {mutant} outcome_only={outcome_only}: red {len(red)} groups, expected "
                                 f"{len(want)}; unexpected {sorted(red - want)[:5]} missed {sorted(want - red)[:5]}")
            killed.append(f"{mutant}{'[outcome-only]' if outcome_only else ''}={len(red)}")
        assert any(expected_red(mutant, False, g) for g in groups)
    print(f"PASS census groups {sum(census['groups'].values())} {census['groups']}; injections "
          f"{census['injections_total']} {census['injections']}; closure re-runs {census['closure_reruns']}; "
          f"caseset {census['caseset_sha256']}")
    print(f"PASS fixtures: 4 exhaustion shapes x 511 torn last zeros are residue in the documented copy; "
          f"(b)-(d) residue; blanks take no step-1 write")
    print(f"PASS convergence: {converged} residue-zeroing interruption states re-plan to the enumerated "
          f"post-step-1 media ({len(groups)} sample groups)")
    print(f"PASS clean synthetic on {len(groups)} sample groups; outcomes reached per phase: "
          + "; ".join(f"{r}.{o}.{ph}={c}" for (r, o, ph), c in sorted(reached.items())))
    print(f"PASS {len(MUTANTS)} controls, red groups out of {len(groups)} (exact expected sets): " + ", ".join(killed))


if __name__ == "__main__":
    main()
