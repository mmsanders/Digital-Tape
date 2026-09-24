#!/usr/bin/env python3
"""Case-level DRAFT-8 oracle for bounded WP-10 core crash evidence."""
from __future__ import annotations

import copy
from functools import lru_cache
from typing import Any

from fixture import (
    BLOCK,
    LBA_B0,
    LBA_B1,
    LBA_MIRROR,
    build_index,
    expected_record_post_slot,
    expected_reset_degraded_post_slot,
    expected_reset_healthy_post_slot,
    fixture_bytes,
    stage_cleared_superblock,
)
from media import compact_snapshot, inspect_snapshot, logical_fingerprint, require_chunk_hashes_equal
from planner import BLOCK_BYTES


class OracleError(RuntimeError):
    pass


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise OracleError(msg)


def _raw_parts(snapshot: dict) -> dict:
    _need(snapshot.get("format") == "WP10-CORE-SNAPSHOT-1", "wrong snapshot format")
    for key in ("primary_hex", "mirror_hex", "slots", "chunk_sha256", "image_sha256"):
        _need(key in snapshot, f"snapshot missing {key}")
    return {
        "primary_hex": snapshot["primary_hex"],
        "mirror_hex": snapshot["mirror_hex"],
        "slots": snapshot["slots"],
        "chunk_sha256": snapshot["chunk_sha256"],
    }


def _same_metadata(a: dict, b: dict) -> bool:
    return (
        a.get("primary_hex") == b.get("primary_hex")
        and a.get("mirror_hex") == b.get("mirror_hex")
        and a.get("slots") == b.get("slots")
    )


@lru_cache(maxsize=None)
def _fixture_snapshot_cached(family: str, variant: str, seed: str | None) -> dict:
    return compact_snapshot(fixture_bytes(family, variant, seed=seed))


def _fixture_snapshot(case: dict) -> dict:
    return _fixture_snapshot_cached(case["family"], case["variant"], case.get("seed"))


def _slot_blocks(slot: bytes) -> tuple[bytes, bytes]:
    return slot[:BLOCK], slot[BLOCK : 2 * BLOCK]


def _transaction(case: dict) -> list[dict]:
    family = case["family"]
    variant = case["variant"]

    if family == "record_commit":
        slot = expected_record_post_slot(variant)
        header, entries = _slot_blocks(slot)
        return [
            {"lba": LBA_B1 + 1, "data": entries, "role": "index_entries"},
            {"lba": LBA_B1, "data": header, "role": "index_header"},
        ]

    if family == "reset_b":
        if variant == "healthy":
            slot = expected_reset_healthy_post_slot()
            target = LBA_B1
        elif variant == "degraded_equal":
            slot = expected_reset_degraded_post_slot()
            target = LBA_B0
        else:
            raise OracleError(f"unknown reset variant {variant}")
        header, entries = _slot_blocks(slot)
        return [
            {"lba": target + 1, "data": entries, "role": "index_entries"},
            {"lba": target, "data": header, "role": "index_header"},
        ]

    if family == "stage_clear":
        new = stage_cleared_superblock()
        seed = case.get("seed")
        if seed in ("mirror_only", "mirror_newer_primary_stale"):
            partner, candidate = 0, LBA_MIRROR
        else:
            # Healthy-pair tie-break and primary-current closure seeds:
            # primary candidate, mirror partner.
            partner, candidate = LBA_MIRROR, 0
        return [
            {"lba": partner, "data": new, "role": "sb_partner"},
            {"lba": candidate, "data": new, "role": "sb_candidate"},
        ]

    raise OracleError(f"unknown family {family}")


def _get_block(snapshot: dict, lba: int) -> bytes:
    if lba == 0:
        return bytes.fromhex(snapshot["primary_hex"])
    if lba == LBA_MIRROR:
        return bytes.fromhex(snapshot["mirror_hex"])
    for name, base in (("B0", LBA_B0), ("B1", LBA_B1)):
        if lba in (base, base + 1):
            raw = bytes.fromhex(snapshot["slots"][name])
            off = (lba - base) * BLOCK
            return raw[off : off + BLOCK]
    raise OracleError(f"unretained target LBA {lba}")


def _set_block(snapshot: dict, lba: int, data: bytes) -> None:
    _need(len(data) == BLOCK, "write block must be 512 bytes")
    if lba == 0:
        snapshot["primary_hex"] = data.hex()
        return
    if lba == LBA_MIRROR:
        snapshot["mirror_hex"] = data.hex()
        return
    for name, base in (("B0", LBA_B0), ("B1", LBA_B1)):
        if lba in (base, base + 1):
            raw = bytearray(bytes.fromhex(snapshot["slots"][name]))
            off = (lba - base) * BLOCK
            raw[off : off + BLOCK] = data
            snapshot["slots"][name] = bytes(raw).hex()
            return
    raise OracleError(f"unretained target LBA {lba}")


def _write_full(working: dict, durable: dict, op: dict, *, write_through: bool) -> None:
    _set_block(working, op["lba"], op["data"])
    if write_through:
        _set_block(durable, op["lba"], op["data"])


def _write_torn(working: dict, durable: dict, op: dict, landed: int) -> None:
    _need(1 <= landed < BLOCK_BYTES, "torn landed_bytes out of range")
    old = _get_block(durable, op["lba"])
    new = op["data"]
    torn = new[:landed] + old[landed:]
    _set_block(working, op["lba"], torn)
    _set_block(durable, op["lba"], torn)


def _flush(working: dict, durable: dict) -> None:
    # Only retained metadata blocks are in scope; chunk hashes cannot change in
    # these metadata-scoped transactions.
    durable["primary_hex"] = working["primary_hex"]
    durable["mirror_hex"] = working["mirror_hex"]
    durable["slots"] = copy.deepcopy(working["slots"])


def simulate_first(case: dict, pre: dict) -> dict:
    tx = _transaction(case)
    working = copy.deepcopy(pre)
    durable = copy.deepcopy(pre)
    mode = case["mode"]
    inj = case["injection"]
    write_through = mode == "write_through"

    if inj["kind"] in ("before_write", "torn_write", "after_write"):
        target_write = inj["write_ordinal"]
        for ordinal, op in enumerate(tx):
            if ordinal == target_write:
                if inj["kind"] == "before_write":
                    return durable
                if inj["kind"] == "torn_write":
                    _write_torn(working, durable, op, inj["landed_bytes"])
                    return durable
                _write_full(working, durable, op, write_through=write_through)
                return durable

            _write_full(working, durable, op, write_through=write_through)
            _flush(working, durable)
        raise OracleError("write ordinal not reached")

    if inj["kind"] == "at_flush":
        target_flush = inj["flush_ordinal"]
        for ordinal, op in enumerate(tx):
            _write_full(working, durable, op, write_through=write_through)
            if ordinal == target_flush:
                # Fault before the flush makes any additional bytes durable.
                return durable
            _flush(working, durable)
        raise OracleError("flush ordinal not reached")

    raise OracleError(f"unknown first-interruption kind {inj['kind']}")


def simulate_closure(case: dict, pre: dict) -> dict:
    op = _transaction(case)[0]  # next partner write only
    working = copy.deepcopy(pre)
    durable = copy.deepcopy(pre)
    inj = case["injection"]
    if inj["kind"] == "before_partner":
        return durable
    if inj["kind"] == "torn_partner":
        _write_torn(working, durable, op, inj["landed_bytes"])
        return durable
    if inj["kind"] == "after_partner":
        _write_full(
            working,
            durable,
            op,
            write_through=case["mode"] == "write_through",
        )
        return durable
    raise OracleError(f"unknown closure injection {inj['kind']}")


def expected_snapshot(case: dict, pre: dict) -> dict:
    if case["scope"] == "first":
        return simulate_first(case, pre)
    if case["scope"] == "closure":
        return simulate_closure(case, pre)
    raise OracleError("unknown case scope")


def _expected_pre_metadata(case: dict, pre: dict) -> None:
    fixture = _fixture_snapshot(case)
    if case["family"] == "record_commit":
        # Service-to-completion happens before the crash-scoped commit. It may
        # change only chunk-store bytes, not superblock/index metadata.
        _need(_same_metadata(pre, fixture), "record pre-commit metadata drifted from verifier fixture")
        for chunk, digest in fixture["chunk_sha256"].items():
            if chunk != "2":
                _need(
                    pre["chunk_sha256"].get(chunk) == digest,
                    f"record setup altered non-pending chunk {chunk}",
                )
        return

    _need(_raw_parts(pre) == _raw_parts(fixture), "pre-operation durable media differs from verifier fixture")


def _validate_trace(case: dict, obs: dict) -> None:
    tx = _transaction(case)
    baseline = obs.get("target_baseline")
    _need(isinstance(baseline, dict), "missing target baseline")
    writes = baseline.get("writes")
    flushes = baseline.get("flushes")
    _need(isinstance(writes, list) and len(writes) == 2, "baseline must have exactly two target block writes")
    _need(isinstance(flushes, list) and len(flushes) == 2, "baseline must have exactly two target flushes")
    for i, (got, want) in enumerate(zip(writes, tx)):
        _need(got.get("ordinal") == i, "baseline write ordinal mismatch")
        _need(got.get("lba") == want["lba"], f"baseline write {i} LBA mismatch")
        _need(got.get("count") == 1, f"baseline write {i} not one block")
        _need(got.get("sha256") == __import__("hashlib").sha256(want["data"]).hexdigest(),
              f"baseline write {i} bytes differ from frozen transaction")
    for i, got in enumerate(flushes):
        _need(got.get("ordinal") == i, "baseline flush ordinal mismatch")

    if case["family"] == "stage_clear":
        _need(baseline.get("post_clear_reached") is True,
              "stage-clear baseline did not reach first post-clear write")
        expected_kind = "index" if case["variant"] == "reset_b" else "chunk"
        _need(baseline.get("post_clear_next_kind") == expected_kind,
              "stage-clear baseline reached wrong post-clear write class")
        _need(baseline.get("post_clear_write_landed") is False,
              "stage-clear baseline allowed post-clear probe write to land")

    _need(obs.get("injection_fired") is True, "planned injection point was skipped")
    fired = obs.get("fired_at")
    _need(isinstance(fired, dict), "missing fired_at provenance")
    for k, v in case["injection"].items():
        _need(fired.get(k) == v, f"fired_at {k} mismatch")


def _validate_actual_remount(case: dict, post: dict, obs: dict) -> None:
    side = "A" if case["family"] == "reset_b" and case["variant"] == "degraded_equal" else "B"
    predicted = inspect_snapshot(post, requested_side=side)["mount_result"]
    _need(obs.get("remount_side") == side, "wrong remount side")
    _need(obs.get("actual_remount_result") == predicted,
          f"product remount result {obs.get('actual_remount_result')} != durable-byte oracle {predicted}")


def validate_case(case: dict, obs: dict) -> dict:
    _need(isinstance(obs, dict), "observation not object")
    _need(obs.get("format") == "WP10-CORE-OBSERVATION-1", "wrong observation format")
    _need(obs.get("case_index") == case["case_index"], "case index mismatch")
    for key in ("scope", "family", "variant", "mode"):
        _need(obs.get(key) == case[key], f"{key} mismatch")
    if "seed" in case:
        _need(obs.get("seed") == case["seed"], "closure seed mismatch")

    pre = obs.get("pre_snapshot")
    post = obs.get("post_snapshot")
    _need(isinstance(pre, dict) and isinstance(post, dict), "missing raw snapshots")
    _expected_pre_metadata(case, pre)

    if case["scope"] == "closure":
        _need(obs.get("setup_mount_result") == "TAPE_OK", "closure seed did not mount")
        _need(obs.get("setup_needs_repair") is True, "closure seed did not expose needs_repair")
        _need(obs.get("setup_repair_fault_fired") is True, "closure repair-preservation fault did not fire")

    _validate_trace(case, obs)

    expected = expected_snapshot(case, pre)
    _need(_raw_parts(post) == _raw_parts(expected), "durable post-crash bytes differ from verifier simulation")
    require_chunk_hashes_equal(pre, post)
    _validate_actual_remount(case, post, obs)

    fp = logical_fingerprint(post, requested_side=obs["remount_side"])
    if case["family"] == "stage_clear":
        # The selected logical state may be the still-valid stage-1 candidate
        # or the durable stage-cleared generation, but never a rollback to the
        # stale generation used by closure seeds.
        if fp["mount_result"] == "TAPE_OK":
            _need(fp.get("sb_generation") in (10, 11), "stage clear selected unexpected generation")
            if fp.get("sb_generation") == 10:
                _need(fp.get("promote_stage") == 1 and fp.get("a_high_water") == 3,
                      "old stage-clear outcome malformed")
            if fp.get("sb_generation") == 11:
                _need(fp.get("promote_stage") == 0 and fp.get("a_high_water") == 3,
                      "new stage-clear outcome malformed")
        else:
            raise OracleError(f"stage-clear durable media not mountable: {fp}")

    return {
        "case_index": case["case_index"],
        "mount_result": fp["mount_result"],
        "logical_fingerprint": fp,
    }


def expected_clean_final(case: dict, pre: dict) -> dict:
    working = copy.deepcopy(pre)
    durable = copy.deepcopy(pre)
    for op in _transaction(case):
        _write_full(working, durable, op, write_through=False)
        _flush(working, durable)
    return durable
