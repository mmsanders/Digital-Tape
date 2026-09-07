#!/usr/bin/env python3
"""Validate Digital Tape Agent Bus routing/state transitions.

Pure-stdlib and intentionally side-effect free. It is suitable for CI or a listener
preflight. It does not mutate GitHub and it does not dispatch an agent.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Iterable


LEADS = {"software", "hardware", "verification"}
WORKERS = {"worker_chatgpt", "worker_grok"}
ROLES = {"michael", "pm", *LEADS, *WORKERS}

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
    "state:review": "review",
    "state:blocked": "blocked",
    "state:protocol-error": "protocol-error",
}

LEGAL_EDGES = {
    "michael": {"pm"},
    "pm": LEADS,
    "software": {"pm", *WORKERS},
    "hardware": {"pm", *WORKERS},
    "verification": {"pm", *WORKERS},
    "worker_chatgpt": LEADS,
    "worker_grok": LEADS,
}

# Legal lifecycle edges. Route checks further constrain these.
LEGAL_STATE_EDGES = {
    ("draft", "queued"),
    ("review", "queued"),
    ("blocked", "queued"),
    ("queued", "working"),
    ("working", "review"),
    ("working", "blocked"),
    ("queued", "protocol-error"),
    ("working", "protocol-error"),
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
    verification_self_service_allowed: bool = True


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


def validate(env: Envelope) -> list[str]:
    errors: list[str] = []

    if env.sender not in ROLES:
        errors.append(f"unknown sender role: {env.sender}")
    if env.destination not in ROLES:
        errors.append(f"unknown destination role: {env.destination}")
    if errors:
        return errors

    if env.destination not in LEGAL_EDGES[env.sender]:
        errors.append(
            f"illegal hierarchy edge: {env.sender} -> {env.destination}; level skipping is forbidden"
        )

    if (env.old_state, env.new_state) not in LEGAL_STATE_EDGES:
        errors.append(f"illegal lifecycle transition: {env.old_state} -> {env.new_state}")

    # PM is a review/synthesis sink inside a round, not an inbound task worker.
    if env.destination == "pm" and env.new_state == "queued":
        errors.append("PM cannot receive or claim queued agent work; leads return review/blocked only")

    # PM may issue root work only after Michael's explicit authorization.
    if env.sender == "pm" and env.new_state == "queued" and not env.round_authorized:
        errors.append("PM dispatch requires Michael-authorized active round")

    # No one but Michael creates new root objectives.
    if env.is_root and env.sender != "pm":
        errors.append("only PM may create lead root tasks inside an authorized round")

    # Rework is allowed only within scope already authorized for this root.
    if env.new_state == "queued" and not env.existing_root_scope:
        errors.append("dispatch would expand root scope; defer to a future Michael-authorized round")

    # Preserve the existing Digital-Tape Verification seam.
    if (
        env.sender == "software"
        and env.destination == "verification"
        and not env.verification_self_service_allowed
    ):
        errors.append("independent review is not self-service for this behavior; route finding to PM")

    # Worker constraints are worth checking explicitly even though LEGAL_EDGES covers them.
    if env.sender in WORKERS and env.destination == "pm":
        errors.append("workers may not route directly to PM")
    if env.sender in WORKERS and env.destination in WORKERS:
        errors.append("worker-to-worker routing is forbidden")

    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sender", required=True, choices=sorted(ROLES))
    p.add_argument("--destination", required=True, choices=sorted(ROLES))
    p.add_argument("--old-state", required=True)
    p.add_argument("--new-state", required=True)
    p.add_argument("--round-authorized", action="store_true")
    p.add_argument("--root", action="store_true")
    p.add_argument("--new-scope", action="store_true")
    p.add_argument("--verification-not-self-service", action="store_true")
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
        verification_self_service_allowed=not args.verification_not_self_service,
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
