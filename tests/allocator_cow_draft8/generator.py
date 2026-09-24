#!/usr/bin/env python3
"""Verifier-owned deterministic generator for frozen WP-07 allocator/COW fuzz."""
from __future__ import annotations

import hashlib
import json
from collections import Counter

FORMAT = "WP07-COW-PLAN-1"
RNG_ALGORITHM = "splitmix64-v1"
MASTER_SEED = 0x573037A110C02026
SEQUENCE_COUNT = 10_000
MIN_ACTIONS = 4
MAX_ACTIONS = 9
CHUNK_FRAMES = 131_072

MODES = ("overwrite", "overdub", "splice")
SELECTORS = (
    "start",
    "mid",
    "end",
    "q1",
    "q3",
    "cf_half",
    "cf_boundary",
    "cf_boundary_minus",
    "cf_boundary_plus",
)
FRAME_POOL = (1, 2, 31, 128, 511, 1024, 4096, 8192)
SERVICE_BUDGET_POOL = (1, 2, 8, 64, 256, 1024)

EXPECTED_PLAN_SHA256 = "dd2a25b5d45ee5fe343cf48d2168ffa275bbb5adb6f3cd398559ae56529da9cd"
EXPECTED_TOTAL_ACTIONS = 65_026
EXPECTED_EDIT_ACTIONS = 59_423
EXPECTED_RESET_ACTIONS = 5_603

MASK64 = (1 << 64) - 1
GAMMA = 0x9E3779B97F4A7C15


def _mix64(z: int) -> int:
    z &= MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)) & MASK64


class SplitMix64:
    def __init__(self, seed: int):
        self.state = seed & MASK64

    def next_u64(self) -> int:
        self.state = (self.state + GAMMA) & MASK64
        return _mix64(self.state)

    def randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be positive")
        return self.next_u64() % n


def sequence_seed(index: int) -> int:
    if index < 0:
        raise ValueError("negative sequence index")
    return _mix64((MASTER_SEED + (index + 1) * GAMMA) & MASK64)


def generate_sequence(index: int) -> dict:
    seed = sequence_seed(index)
    r = SplitMix64(seed)
    count = MIN_ACTIONS + r.randbelow(MAX_ACTIONS - MIN_ACTIONS + 1)
    actions = []
    previous_reset = False

    for i in range(count):
        can_reset = i < count - 1 and not previous_reset
        do_reset = can_reset and r.randbelow(9) == 0
        if do_reset:
            actions.append({"kind": "reset"})
            previous_reset = True
            continue

        actions.append(
            {
                "kind": "edit",
                "mode": MODES[r.randbelow(len(MODES))],
                "selector": SELECTORS[r.randbelow(len(SELECTORS))],
                "frames": FRAME_POOL[r.randbelow(len(FRAME_POOL))],
                "service_budget": SERVICE_BUDGET_POOL[
                    r.randbelow(len(SERVICE_BUDGET_POOL))
                ],
            }
        )
        previous_reset = False

    return {
        "format": FORMAT,
        "seq_index": index,
        "seq_seed": f"{seed:016x}",
        "actions": actions,
    }


def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def resolve_selector(selector: str, total_frames: int) -> int:
    if total_frames < 0:
        raise ValueError("negative total_frames")
    if selector == "start":
        return 0
    if selector == "mid":
        return total_frames // 2
    if selector == "end":
        return total_frames
    if selector == "q1":
        return total_frames // 4
    if selector == "q3":
        return (3 * total_frames) // 4
    if selector == "cf_half":
        return min(total_frames, CHUNK_FRAMES // 2)
    if selector == "cf_boundary":
        return min(total_frames, CHUNK_FRAMES)
    if selector == "cf_boundary_minus":
        return min(total_frames, CHUNK_FRAMES - 1)
    if selector == "cf_boundary_plus":
        return min(total_frames, CHUNK_FRAMES + 1)
    raise ValueError(f"unknown selector {selector!r}")


def census_and_digest(sequence_count: int = SEQUENCE_COUNT) -> tuple[dict, str]:
    if sequence_count < 0:
        raise ValueError("negative sequence_count")

    counts = Counter()
    sequence_features = Counter()
    h = hashlib.sha256()
    min_actions = None
    max_actions = 0
    total_actions = 0

    for i in range(sequence_count):
        plan = generate_sequence(i)
        h.update((canonical_json(plan) + "\n").encode("ascii"))
        n = len(plan["actions"])
        total_actions += n
        min_actions = n if min_actions is None else min(min_actions, n)
        max_actions = max(max_actions, n)
        features = set()

        for action in plan["actions"]:
            kind = action["kind"]
            counts[kind] += 1
            features.add(kind)
            if kind == "edit":
                for key in ("mode", "selector"):
                    token = f"{key}_{action[key]}"
                    counts[token] += 1
                    features.add(token)
                counts[f"frames_{action['frames']}"] += 1
                counts[f"budget_{action['service_budget']}"] += 1

        for feature in features:
            sequence_features[f"seq_has_{feature}"] += 1

    census = {
        "sequence_count": sequence_count,
        "total_actions": total_actions,
        "min_actions_per_sequence": min_actions if min_actions is not None else 0,
        "max_actions_per_sequence": max_actions,
        "counts": dict(sorted(counts.items())),
        "sequence_features": dict(sorted(sequence_features.items())),
    }
    return census, h.hexdigest()


def validate_generator_census(census: dict) -> list[str]:
    errors = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errors.append(msg)

    need(census.get("sequence_count") == SEQUENCE_COUNT, "sequence count is not 10000")
    need(census.get("min_actions_per_sequence") == MIN_ACTIONS, "minimum action length absent")
    need(census.get("max_actions_per_sequence") == MAX_ACTIONS, "maximum action length absent")
    counts = census.get("counts", {})
    need(int(counts.get("edit", 0)) > 0, "no edit actions")
    need(int(counts.get("reset", 0)) > 0, "no reset actions")
    for mode in MODES:
        need(int(counts.get("mode_" + mode, 0)) > 0, f"mode {mode} absent")
    for selector in SELECTORS:
        need(int(counts.get("selector_" + selector, 0)) > 0, f"selector {selector} absent")
    for n in FRAME_POOL:
        need(int(counts.get("frames_" + str(n), 0)) > 0, f"frame size {n} absent")
    for n in SERVICE_BUDGET_POOL:
        need(int(counts.get("budget_" + str(n), 0)) > 0, f"service budget {n} absent")
    return errors
