#!/usr/bin/env python3
"""WP-10 R53 self-test: census, table cross-check, clean synthetic run, causal controls."""
from __future__ import annotations

import model as M
from oracle import check, check_stream, iter_cases, new_findings, plan_census
from synthetic_adapter import MUTANTS, lines, observation

EXPECTED = {"crash": 57_532, "complete": 6, "empty_family": 1,
            "caseset_sha256": "72717654d563905b8e76c79959757b0ae625a3f2353944c2818baf35ca83bf0e"}
ROW_CONTROLS = {
    "WP10.dup.empty_source.every_boundary": {"empty_source_zero_frame_entry", "empty_family_promote_accepts",
                                             "source_written"},
    "WP10.format_dup.steps2_3.reusable_stale_slot1": {"slot1_not_zeroed", "template_flush_skipped"},
    "WP10.format_dup.blank_media_table": {"primary_before_mirror", "needs_repair_hidden"},
}


def table_expectation(scenario, img):
    """tapefs §9.5 / §9.6 permitted-outcome rows, restated from the superblock landmarks only."""
    op, frames, shape, _ = M.SCENARIOS[scenario]
    final = M.final_sb(op, frames)
    tmpl = None if shape == "blank" else M.B.wip_template(M.OLD_SB, existing_generation=7)
    p, m = img["P"], img["M"]
    if shape == "blank":
        if m == final or p == final:
            return {("TAPE_OK", "new")}           # mirror durable (primary absent/torn/new): completed
        return {("TAPE_ERR_BAD_MAGIC", None)}   # before / inside step 4 mirror, not yet durable
    if p == final or (m == final and p not in (tmpl, M.OLD_SB)):
        return {("TAPE_OK", "new")}               # step-4 primary durable or torn
    if m == tmpl or p == tmpl or m == final:
        return {("TAPE_ERR_INCOMPLETE", None)}    # a template (or only the new mirror) is durable
    if p == M.OLD_SB:
        return {("TAPE_OK", "old")}               # first (partner) template write not durable or tore
    raise AssertionError(f"{scenario}: image outside every table row")


def table_crosscheck():
    checked = 0
    for scenario in M.SCENARIOS:
        op, frames, shape, _ = M.SCENARIOS[scenario]
        new_uuid = (M.B.FRESH_DUP_UUID if op == "dup" else M.B.FRESH_FORMAT_UUID).hex()
        for mode, inject in M.injections(scenario):
            for img in M.possible_images(scenario, inject, mode):
                c = M.classify(img, "A", False)
                kind = None if c["result"][0] != "TAPE_OK" else ("new" if c["uuid"] == new_uuid else "old")
                got = {(r, kind) for r in c["result"] if r != "TAPE_ERR_CRC"}
                want = table_expectation(scenario, img)
                assert got == want, f"{scenario} {mode} {inject}: classifier {got} vs table {want}"
                if kind == "new":
                    assert c["layout"] == (((0, 0, frames),) if frames else ()), "completed copy layout"
                checked += 1
    return checked


def main():
    census = plan_census()
    for k, v in EXPECTED.items():
        assert census[k] == v, f"census {k}: {census[k]} != {v}"
    images = table_crosscheck()
    n, findings = check_stream(lines())
    killed = {}
    for mutant, scenarios in MUTANTS.items():
        for trust_trace in (False, True):
            reds = {s: 0 for s in scenarios}
            for case in iter_cases():
                if case["scenario"] not in scenarios:
                    continue
                if mutant == "empty_family_promote_accepts" and case["kind"] != "empty_family":
                    continue
                try:
                    check(case, observation(case, mutant), new_findings(), trust_trace)
                except AssertionError:
                    reds[case["scenario"]] += 1
            dead = [s for s, r in reds.items() if r == 0]
            assert not dead, f"control {mutant} (trust_trace={trust_trace}) survived in {dead}"
            killed[(mutant, trust_trace)] = sum(reds.values())
    covered = {row for row, ms in ROW_CONTROLS.items() if ms <= set(MUTANTS)}
    assert covered == set(ROW_CONTROLS), "row without a causal control"
    print(f"PASS census {census['crash']} crash + {census['complete']} complete + {census['empty_family']} family "
          f"(caseset {census['caseset_sha256']}); table cross-check {images} images; clean synthetic {n}/{n}; "
          f"{len(MUTANTS)} causal controls killed with and without trace binding "
          f"({sum(v for (m, t), v in killed.items() if t)} outcome-level reds); findings {findings}")


if __name__ == "__main__":
    main()
