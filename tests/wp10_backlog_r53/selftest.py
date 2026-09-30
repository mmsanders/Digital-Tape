#!/usr/bin/env python3
"""WP-10 backlog rows 1-3 self-test: census, clean synthetic run, causal controls per row."""
from __future__ import annotations

import copy

import oracle as O
from synthetic_adapter import MUTANTS, lines, observation, setup_audio_image

EXPECTED = {"row1_crash": 24_660, "row1_complete": 2, "row2_frontier": 55_152, "row3_groups": 6,
            "caseset_sha256": "036e255eb2a704d041b87eb21116900ea307ba450a5cf72f3b0440dffdd3b2d7"}
ROW_OF = {1: O.ROW1, 2: O.ROW2, 3: O.ROW3}
C69_TOTAL, C69_RECORD = 28_760, 6_168
# #124: each real divergence must be killed on exactly these C69 cases (and on no R29-B case).
C69_EXACT_KILLS = {"c69_post_metadata_diverges": C69_TOTAL, "c69_post_chunk_diverges": C69_TOTAL,
                   "c69_pre_metadata_drift": C69_TOTAL, "c69_setup_alters_live_chunk": C69_RECORD}


def c69_pre_state_equivalence():
    """The corrected binding simulates post-crash metadata from the fixture's metadata. Prove that equals the
    accepted campaign's simulation from the *observed* pre-state, whose metadata the check requires to equal the
    fixture's but whose chunk digests may differ (record setup audio in chunk 2): every C69 transaction writes
    only superblock/index blocks and carries chunk digests through unchanged."""
    n = 0
    for case in O._c69_cases().values():
        fixture = O.C.oracle._fixture_snapshot(case)
        observed_pre = copy.deepcopy(fixture)
        observed_pre["image_sha256"] = "f" * 64
        observed_pre["chunk_sha256"] = {k: format(int(k) + 1, "064x") for k in fixture["chunk_sha256"]}
        from_fixture = O.C.oracle.expected_snapshot(case, fixture)
        from_observed = O.C.oracle.expected_snapshot(case, observed_pre)
        assert O.c69_metadata_sha256(from_fixture) == O.c69_metadata_sha256(from_observed), case
        assert from_observed["chunk_sha256"] == observed_pre["chunk_sha256"], case
        n += 1
    assert n == C69_TOTAL
    return n


def _write_metadata(image, snapshot):
    """Real bytes of a post-crash device: the pre image with the durable metadata blocks written in."""
    B, img = O.C.fixture.BLOCK, bytearray(image)
    img[0:B] = bytes.fromhex(snapshot["primary_hex"])
    m = O.C.fixture.LBA_MIRROR * B
    img[m:m + B] = bytes.fromhex(snapshot["mirror_hex"])
    for name, lba in O.C.media.SLOT_LBAS.items():
        raw = bytes.fromhex(snapshot["slots"][name])
        img[lba * B:lba * B + len(raw)] = raw
    return bytes(img)


def c69_byte_real_control():
    """Causal control the old whole-snapshot hash kills wrongly. One case per C69 shape (family, variant, scope,
    seed, mode, injection kind) runs on real device bytes: lawful record setup audio in chunk 2, the durable
    post-crash metadata written into the image, and `compact_snapshot` of those real bytes (true
    `image_sha256`). The corrected binding must accept every one; the #110 binding rejected every one that
    differs from the fixture image, which is all of them except unchanged non-record images."""
    seen, old_red, new_green, unchanged_non_record = {}, 0, 0, 0
    for case in O._c69_cases().values():
        key = (case["family"], case["variant"], case["scope"], case.get("seed"), case["mode"],
               case["injection"]["kind"])
        if key in seen:
            continue
        seen[key] = case["case_index"]
        image = O.C.fixture.fixture_bytes(case["family"], case["variant"], seed=case.get("seed"))
        if case["family"] == "record_commit":
            image = setup_audio_image(image)
        pre = O.C.media.compact_snapshot(image)
        expected_post = O.C.oracle.expected_snapshot(case, pre)
        post = O.C.media.compact_snapshot(_write_metadata(image, expected_post))
        assert O.C.oracle._raw_parts(post) == O.C.oracle._raw_parts(expected_post), key   # faithful bytes
        # The #110 binding: SHA-256 of the whole expected snapshot simulated from the fixture.
        old = O.sha(O.canonical(O.C.oracle.expected_snapshot(case, O.C.oracle._fixture_snapshot(case))).encode())
        if O.sha(O.canonical(post).encode()) != old:
            old_red += 1
        elif case["family"] != "record_commit" and post["image_sha256"] == pre["image_sha256"]:
            unchanged_non_record += 1
        exp = O.row2_expectation("C69", case["case_index"])
        obs = {"schema": O.SCHEMA, "index": 0, "row": 2, "kind": "frontier", "campaign": "C69",
               "case_index": case["case_index"], "pre_metadata_sha256": O.c69_metadata_sha256(pre),
               "pre_chunk_sha256": pre["chunk_sha256"], "post_metadata_sha256": O.c69_metadata_sha256(post),
               "post_chunk_sha256": post["chunk_sha256"],
               "remount": {"side": exp["side"], "result": exp["result"], "total_chunks": exp["total_chunks"],
                           "free_chunks": exp["free_chunks"]}}
        O.check_row2({"campaign": "C69", "case_index": case["case_index"]}, obs)
        new_green += 1
    assert old_red + unchanged_non_record == len(seen) and old_red > 0, (old_red, unchanged_non_record, len(seen))
    return len(seen), old_red, new_green


def main():
    census = O.plan_census()
    for k, v in EXPECTED.items():
        assert census[k] == v, f"census {k}: {census[k]} != {v}"
    n, row3 = O.check_stream(lines())
    equivalence = c69_pre_state_equivalence()
    shapes, old_red, new_green = c69_byte_real_control()
    killed = {}
    for mutant, row in MUTANTS.items():
        for trust_trace in ((False, True) if row == 1 else (False,)):
            reds, groups = 0, set()
            for case in O.iter_cases():
                if case["row"] != row:
                    continue
                try:
                    O.check(case, observation(case, mutant), trust_trace)
                except AssertionError:
                    reds += 1
                    groups.add(case.get("scenario") or case.get("campaign") or case.get("record_mode"))
            assert reds, f"control {mutant} (trust_trace={trust_trace}) survived"
            if row in (1, 3):
                want = set(O.D.SCENARIOS) if row == 1 else set(O.RECORD_MODES)
                assert groups == want, f"control {mutant} missed {want - groups}"
            if mutant in C69_EXACT_KILLS:
                assert reds == C69_EXACT_KILLS[mutant] and groups == {"C69"}, \
                    f"control {mutant} killed {reds} in {groups}, want {C69_EXACT_KILLS[mutant]} C69 only"
            killed[(mutant, trust_trace)] = reds
    rows_controlled = {ROW_OF[r] for r in MUTANTS.values()}
    assert rows_controlled == {O.ROW1, O.ROW2, O.ROW3}
    print(f"PASS census row1 {census['row1_crash']} crash ({census['row1_by_mode']}) + {census['row1_complete']} complete; "
          f"row2 {census['row2_frontier']} frontier ({census['row2_by_campaign']} of {census['row2_campaign_totals']}, "
          f"{census['row2_by_mode']}); row3 {census['row3_groups']} groups; caseset {census['caseset_sha256']}; "
          f"clean synthetic {n}/{n} with {row3} row-3 injections; "
          f"C69 pre-state equivalence {equivalence}/{C69_TOTAL}; "
          f"C69 byte-real control: {shapes} shapes, #110 whole-snapshot binding red on {old_red}, corrected green on "
          f"{new_green}; {len(MUTANTS)} causal controls killed: "
          + ", ".join(f"{m}{'[outcome-only]' if t else ''}={r}" for (m, t), r in killed.items()))


if __name__ == "__main__":
    main()
