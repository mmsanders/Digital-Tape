#!/usr/bin/env python3

import importlib.util
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "validate_transition", HERE / "validate_transition.py"
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)
Envelope = mod.Envelope
validate = mod.validate


class ProtocolTests(unittest.TestCase):
    def ok(self, **kwargs):
        self.assertEqual([], validate(Envelope(**kwargs)))

    def bad(self, needle, **kwargs):
        errors = validate(Envelope(**kwargs))
        self.assertTrue(errors, "expected protocol rejection")
        self.assertTrue(
            any(needle in e for e in errors),
            f"expected {needle!r} in {errors!r}",
        )

    def test_protected_bus_releases_pm_root(self):
        self.ok(
            actor="bus", destination="software", old_state="draft",
            new_state="queued", round_authorized=True, is_root=True,
        )

    def test_bus_cannot_release_root_without_human_round(self):
        self.bad(
            "authorized round",
            actor="bus", destination="software", old_state="draft",
            new_state="queued", round_authorized=False, is_root=True,
        )

    def test_lead_requests_worker_by_ready_not_queued(self):
        self.ok(
            actor="software", destination="worker_grok", old_state="draft",
            new_state="ready", round_authorized=True, parent_lead="software",
        )

    def test_model_cannot_ring_queued_bell(self):
        self.bad(
            "models never add state:queued",
            actor="software", destination="worker_grok", old_state="draft",
            new_state="queued", round_authorized=True, parent_lead="software",
        )

    def test_bus_promotes_validated_child_ready_to_queued(self):
        self.ok(
            actor="bus", destination="worker_grok", old_state="ready",
            new_state="queued", round_authorized=True,
        )

    def test_worker_claims_only_own_queue(self):
        self.ok(
            actor="worker_grok", destination="worker_grok", old_state="queued",
            new_state="working", round_authorized=True,
        )

    def test_wrong_worker_cannot_claim(self):
        self.bad(
            "only the destination",
            actor="worker_chatgpt", destination="worker_grok", old_state="queued",
            new_state="working", round_authorized=True,
        )

    def test_worker_cannot_skip_to_pm(self):
        self.bad(
            "worker result must return",
            actor="worker_grok", destination="pm", old_state="working",
            new_state="review", round_authorized=True, parent_lead="software",
        )

    def test_worker_returns_to_parent_lead(self):
        self.ok(
            actor="worker_grok", destination="software", old_state="working",
            new_state="review", round_authorized=True, parent_lead="software",
        )

    def test_worker_cannot_return_to_wrong_lead(self):
        self.bad(
            "parent lead",
            actor="worker_grok", destination="hardware", old_state="working",
            new_state="review", round_authorized=True, parent_lead="software",
        )

    def test_lead_returns_review_to_pm(self):
        self.ok(
            actor="software", destination="pm", old_state="working",
            new_state="review", round_authorized=True, is_root=True,
        )

    def test_lead_cannot_send_result_to_michael(self):
        # michael is not even a valid task destination.
        self.bad(
            "unknown destination",
            actor="software", destination="michael", old_state="working",
            new_state="review", round_authorized=True, is_root=True,
        )

    def test_lead_can_sleep_own_root(self):
        self.ok(
            actor="software", destination="software", old_state="working",
            new_state="waiting", round_authorized=True, is_root=True,
        )

    def test_bus_fanin_releases_waiting_root(self):
        self.ok(
            actor="bus", destination="software", old_state="waiting",
            new_state="queued", round_authorized=True, is_root=True,
        )

    def test_root_cannot_be_readied_by_model(self):
        self.bad(
            "root tasks are PM-prepared",
            actor="software", destination="software", old_state="draft",
            new_state="ready", round_authorized=True, is_root=True,
        )

    def test_typed_independent_review_request_is_legal(self):
        self.ok(
            actor="software", destination="verification", old_state="draft",
            new_state="ready", round_authorized=True, independent_review=True,
            parent_lead="software",
        )

    def test_untyped_lateral_review_is_red(self):
        self.bad(
            "normal ready request",
            actor="software", destination="verification", old_state="draft",
            new_state="ready", round_authorized=True, parent_lead="software",
        )

    def test_typed_independent_review_result_returns_to_requester(self):
        self.ok(
            actor="verification", destination="software", old_state="working",
            new_state="review", round_authorized=True, independent_review=True,
            parent_lead="software",
        )

    def test_independent_review_cannot_bypass_verification_seam(self):
        self.bad(
            "not self-service",
            actor="software", destination="verification", old_state="draft",
            new_state="ready", round_authorized=True, independent_review=True,
            verification_self_service_allowed=False, parent_lead="software",
        )

    def test_new_scope_cannot_be_requested(self):
        self.bad(
            "expand root scope",
            actor="software", destination="worker_grok", old_state="draft",
            new_state="ready", round_authorized=True,
            existing_root_scope=False, parent_lead="software",
        )

    def test_child_requires_native_parent(self):
        self.bad(
            "native GitHub sub-issue",
            actor="software", destination="worker_grok", old_state="draft",
            new_state="ready", round_authorized=True,
            is_native_child=False, parent_lead="software",
        )


if __name__ == "__main__":
    unittest.main()
