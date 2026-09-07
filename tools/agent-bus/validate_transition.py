#!/usr/bin/env python3
"""Validate Digital Tape Agent Bus routing/state/capability transitions.

Pure-stdlib and side-effect free. This models the protocol rules used by listeners
and staged GitHub workflows; it never mutates GitHub or dispatches a model.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Iterable


LEADS = {"software", "hardware", "verification"}
WORKERS = {"worker_chatgpt", "worker_grok"}
MODEL_ROLES = {"pm", *LEADS, *WORKERS}
ACTORS = {"michael", "bus", *MODEL_ROLES}
CAPABILITIES = {"auto", "frontier", "strong", "balanced", "economy"}

ALLOWED_CAPABILITIES = {
    "pm": {"auto", "strong", "frontier"},
    "software": {"auto", "balanced", "strong", "frontier"},
    "hardware": {"auto", "balanced", "strong", "frontier"},
    "verification": {"auto", "strong", "frontier"},
    "worker_chatgpt": {"auto", "economy", "balanced"},
    "worker_grok": {"auto", "economy", "balanced"},
}

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
    "state:ready": "ready",
    "state:queued": "queued",
    "state:working": "working",
    "state:waiting": "waiting",
    "state:review": "review",
    "state:blocked": "blocked",
    "state:protocol-error": "protocol-error",
}

NORMAL_HANDOFFS = {
    "pm": LEADS,
    "software": {"pm", *WORKERS},
    "hardware": {"pm", *WORKERS},
    "verification": {"pm", *WORKERS},
    "worker_chatgpt": LEADS,
    "worker_grok": LEADS,
}

LEGAL_STATE_EDGES = {
    ("draft", "ready"),
    ("review", "ready"),
    ("blocked", "ready"),
    ("ready", "queued"),
    ("draft", "queued"),       # protected bus release of PM-prepared root only
    ("queued", "working"),
    ("working", "waiting"),
    ("waiting", "queued"),     # bus fan-in release only
    ("working", "review"),
    ("working", "blocked"),
    ("queued", "protocol-error"),
    ("ready", "protocol-error"),
    ("working", "protocol-error"),
    ("waiting", "protocol-error"),
    ("review", "protocol-error"),
    ("blocked", "protocol-error"),
}


@dataclass(frozen=True)
class Envelope:
    actor: str
    destination: str
    old_state: str
    new_state: str
    round_authorized: bool
    is_root: bool = False
    existing_root_scope: bool = True
    independent_review: bool = False
    verification_self_service_allowed: bool = True
    is_native_child: bool = True
    parent_lead: str | None = None
    requested_capability: str = "auto"


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


def _typed_review_request(env: Envelope) -> bool:
    return (
        env.independent_review
        and env.actor in {"software", "hardware"}
        and env.destination == "verification"
    )


def _typed_review_return(env: Envelope) -> bool:
    return (
        env.independent_review
        and env.actor == "verification"
        and env.destination in {"software", "hardware"}
    )


def validate(env: Envelope) -> list[str]:
    errors: list[str] = []

    if env.actor not in ACTORS:
        return [f"unknown actor role: {env.actor}"]
    if env.destination not in MODEL_ROLES:
        return [f"unknown destination role: {env.destination}"]
    if env.requested_capability not in CAPABILITIES:
        return [f"unknown capability class: {env.requested_capability}"]
    if env.requested_capability not in ALLOWED_CAPABILITIES[env.destination]:
        errors.append(
            f"capability {env.requested_capability} is not allowed for destination {env.destination}"
        )

    if (env.old_state, env.new_state) not in LEGAL_STATE_EDGES:
        errors.append(f"illegal lifecycle transition: {env.old_state} -> {env.new_state}")

    # System actor owns the actual dispatch bell. It may release a validated child,
    # a human-authorized PM root, or a waiting root at fan-in — nothing else.
    if env.actor == "bus":
        bus_ok = (
            env.round_authorized
            and env.destination != "pm"
            and (
                (env.old_state == "ready" and env.new_state == "queued" and not env.is_root)
                or (env.old_state == "draft" and env.new_state == "queued" and env.is_root and env.destination in LEADS)
                or (env.old_state == "waiting" and env.new_state == "queued" and env.is_root and env.destination in LEADS)
            )
        )
        if not bus_ok:
            errors.append("bus may only perform validated ready/root/fan-in release inside an authorized round")
        return errors

    # A model never adds queued directly. It requests dispatch by moving to ready.
    if env.new_state == "queued":
        errors.append("models never add state:queued; request state:ready and let the bus validate")

    # Claims are self-actions against an already-routed envelope.
    if env.old_state == "queued" and env.new_state == "working":
        if env.actor != env.destination:
            errors.append("only the destination may claim queued work")
        return errors

    # Waiting is a lead putting its own root to sleep after fan-out.
    if env.old_state == "working" and env.new_state == "waiting":
        if not env.is_root or env.actor != env.destination or env.actor not in LEADS:
            errors.append("only a lead may put its own root into waiting after fan-out")
        return errors

    # PM cannot be tasked by agents. Leads return state:review/state:blocked instead.
    if env.destination == "pm" and env.new_state == "ready":
        errors.append("PM never accepts ready/queued agent work; leads return review/blocked only")

    # Root objectives are PM-authored drafts and are never readied by a model.
    if env.is_root and env.new_state == "ready":
        errors.append("root tasks are PM-prepared drafts released only by the protected bus")

    if not env.is_root and not env.is_native_child:
        errors.append("non-root Agent Bus work must be attached as a native GitHub sub-issue")

    if env.new_state == "ready" and not env.existing_root_scope:
        errors.append("dispatch would expand root scope; defer to a future Michael-authorized round")

    # Normal child dispatch requests must originate at the parent lead and target a worker.
    if env.new_state == "ready" and not env.independent_review:
        if env.actor not in LEADS or env.destination not in WORKERS:
            errors.append("normal ready request must be parent lead -> worker")
        if env.parent_lead is not None and env.actor != env.parent_lead:
            errors.append("only the parent lead may request dispatch for its child")

    # Sanctioned lateral Verification service edge.
    if env.independent_review:
        if env.new_state == "ready":
            if not _typed_review_request(env):
                errors.append("independent review request must be Software/Hardware -> Verification")
            if env.parent_lead is not None and env.actor != env.parent_lead:
                errors.append("independent review requester must own the parent root")
        elif env.new_state in {"review", "blocked"}:
            if not _typed_review_return(env):
                errors.append("independent review result must return Verification -> requesting lead")
        if not env.verification_self_service_allowed:
            errors.append("independent review is not self-service for this behavior; return root to PM")

    # Ordinary results flow exactly one level upward.
    if env.new_state in {"review", "blocked"} and not env.independent_review:
        if env.actor in WORKERS:
            if env.destination not in LEADS:
                errors.append("worker result must return to a lead, never PM/worker")
            if env.parent_lead is not None and env.destination != env.parent_lead:
                errors.append("worker result must return to its parent lead")
        elif env.actor in LEADS:
            if env.destination != "pm":
                errors.append("lead root result/escalation must return to PM")
        else:
            errors.append("only workers/leads return ordinary review or blocked results")

    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--actor", required=True, choices=sorted(ACTORS))
    p.add_argument("--destination", required=True, choices=sorted(MODEL_ROLES))
    p.add_argument("--old-state", required=True)
    p.add_argument("--new-state", required=True)
    p.add_argument("--round-authorized", action="store_true")
    p.add_argument("--root", action="store_true")
    p.add_argument("--new-scope", action="store_true")
    p.add_argument("--independent-review", action="store_true")
    p.add_argument("--verification-not-self-service", action="store_true")
    p.add_argument("--not-native-child", action="store_true")
    p.add_argument("--parent-lead", choices=sorted(LEADS))
    p.add_argument("--capability", default="auto", choices=sorted(CAPABILITIES))
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    env = Envelope(
        actor=args.actor,
        destination=args.destination,
        old_state=args.old_state,
        new_state=args.new_state,
        round_authorized=args.round_authorized,
        is_root=args.root,
        existing_root_scope=not args.new_scope,
        independent_review=args.independent_review,
        verification_self_service_allowed=not args.verification_not_self_service,
        is_native_child=not args.not_native_child,
        parent_lead=args.parent_lead,
        requested_capability=args.capability,
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
