#!/usr/bin/env python3
"""Validate Digital Tape Agent Bus routing/state transitions.

Pure-stdlib and intentionally side-effect free. Suitable for CI/listener preflight.
It never mutates GitHub and never dispatches an agent.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Iterable


LEADS = {"software", "hardware", "verification"}
WORKERS = {"worker_chatgpt", "worker_grok"}
MODELS = {"michael", "pm", *LEADS, *WORKERS}
ROLES = {"bus", *MODELS}

DESTINATION_LABELS = {
    "to:pm": "pm",
    "to:software": "software",
    "to:hardware": "hardware",
    "to:verification": "verification",
    "to:worker-chatgpt": "worker_chatgpt",
    "to:worker-grok": "worker_grok",
}

STATE_LABELS = {
    "state:draft": "draft",
    "state:queued": "queued",
    "state:working": "working",
    "state:waiting": "waiting",
    "state:review": "review",
    "state:blocked": "blocked",
    "state:protocol-error": "protocol-error",
}

# Normal authority edges. Independent review is handled separately as a typed
# service edge. `bus` is a non-model actor used only for barrier releases.
LEGAL_EDGES = {
    "michael": {"pm"},
    "pm": LEADS,
    "software": {"pm", *WORKERS},
    "hardware": {"pm", *WORKERS},
    "verification": {"pm", *WORKERS},
    "worker_chatgpt": LEADS,
    "worker_grok": LEADS,
    "bus": LEADS,
}

LEGAL_STATE_EDGES = {
    ("draft", "queued"),
    ("review", "queued"),
    ("blocked", "queued"),
    ("queued", "working"),
    ("working", "waiting"),
    ("waiting", "queued"),
    ("working", "review"),
    ("working", "blocked"),
    ("queued", "protocol-error"),
    ("working", "protocol-error"),
    ("waiting", "protocol-error"),
    ("review", "protocol-error"),
    ("blocked", "protocol-error"),
}


@dataclass(frozen=True)
class Envelope:
    sender: str
    destination: str
    old_state: str
    new_state: str
    round_authorized: bool
    is_root: bool = False
    existing_root_scope: bool = True
    independent_review: bool = False
    verification_self_service_allowed: bool = True
    is_native_child: bool = True


def _one(values: Iterable[str], kind: str) -> str:
    values = list(values)
    if len(values) != 1:
        raise ValueError(f"expected exactly one {kind}; got {values!r}")
    return values[0]


def parse_labels(labels: Iterable[str]) -> tuple[str, str]:
    destination = _one(
        (DESTINATION_LABELS[x] for x in labels if x in DESTINATION_LABELS),
        "destination label",
    )
    state = _one(
        (STATE_LABELS[x] for x in labels if x in STATE_LABELS),
        "state label",
    )
    return destination, state


def _typed_review_edge(env: Envelope) -> bool:
    if not env.independent_review:
        return False
    request = env.sender in {"software", "hardware"} and env.destination == "verification"
    result = env.sender == "verification" and env.destination in {"software", "hardware"}
    return request or result


def validate(env: Envelope) -> list[str]:
    errors: list[str] = []

    if env.sender not in ROLES:
        errors.append(f"unknown sender role: {env.sender}")
    if env.destination not in MODELS:
        errors.append(f"unknown destination role: {env.destination}")
    if errors:
        return errors

    normal_edge = env.destination in LEGAL_EDGES[env.sender]
    review_edge = _typed_review_edge(env)
    if not normal_edge and not review_edge:
        errors.append(
            f"illegal hierarchy edge: {env.sender} -> {env.destination}; level skipping is forbidden"
        )

    if (env.old_state, env.new_state) not in LEGAL_STATE_EDGES:
        errors.append(f"illegal lifecycle transition: {env.old_state} -> {env.new_state}")

    # The bus has exactly one task-state authority: fan-in release.
    if env.sender == "bus":
        if not (
            env.destination in LEADS
            and env.old_state == "waiting"
            and env.new_state == "queued"
            and env.round_authorized
        ):
            errors.append("bus actor may only release an authorized waiting lead at fan-in")

    # PM is a review/synthesis sink during an active round, not an inbound worker.
    if env.destination == "pm" and env.new_state == "queued":
        errors.append("PM cannot receive or claim queued agent work; leads return review/blocked only")

    # PM-authored root work is released only after the protected Michael gate.
    if env.sender == "pm" and env.new_state == "queued" and not env.round_authorized:
        errors.append("PM root dispatch requires protected Michael-authorized active round")

    if env.is_root and env.sender not in {"pm", "bus"}:
        errors.append("only PM may author lead root tasks; bus may only release pre-authored roots")

    if not env.is_root and not env.is_native_child:
        errors.append("non-root Agent Bus work must be attached as a native GitHub sub-issue")

    if env.new_state == "queued" and not env.existing_root_scope:
        errors.append("dispatch would expand root scope; defer to a future Michael-authorized round")

    if env.independent_review:
        if not review_edge:
            errors.append(
                "independent-review service edge must be software/hardware -> verification or its result return"
            )
        if not env.verification_self_service_allowed:
            errors.append("independent review is not self-service for this behavior; return root to PM")
    elif (
        (env.sender in {"software", "hardware"} and env.destination == "verification")
        or (env.sender == "verification" and env.destination in {"software", "hardware"})
    ):
        errors.append("lateral Verification routing requires kind:independent-review")

    if env.sender in WORKERS and env.destination == "pm":
        errors.append("workers may not route directly to PM")
    if env.sender in WORKERS and env.destination in WORKERS:
        errors.append("worker-to-worker routing is forbidden")

    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sender", required=True, choices=sorted(ROLES))
    p.add_argument("--destination", required=True, choices=sorted(MODELS))
    p.add_argument("--old-state", required=True)
    p.add_argument("--new-state", required=True)
    p.add_argument("--round-authorized", action="store_true")
    p.add_argument("--root", action="store_true")
    p.add_argument("--new-scope", action="store_true")
    p.add_argument("--independent-review", action="store_true")
    p.add_argument("--verification-not-self-service", action="store_true")
    p.add_argument("--not-native-child", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    env = Envelope(
        sender=args.sender,
        destination=args.destination,
        old_state=args.old_state,
        new_state=args.new_state,
        round_authorized=args.round_authorized,
        is_root=args.root,
        existing_root_scope=not args.new_scope,
        independent_review=args.independent_review,
        verification_self_service_allowed=not args.verification_not_self_service,
        is_native_child=not args.not_native_child,
    )
    errors = validate(env)

    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    elif errors:
        for err in errors:
            print(f"AGENT-BUS ERROR: {err}", file=sys.stderr)
    else:
        print("AGENT-BUS OK")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
