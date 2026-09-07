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

    def test_authorized_pm_root_to_software_is_legal(self):
        self.ok(
            sender="pm", destination="software", old_state="draft",
            new_state="queued", round_authorized=True, is_root=True,
        )

    def test_unauthorized_pm_dispatch_is_red(self):
        self.bad(
            "protected Michael-authorized",
            sender="pm", destination="software", old_state="draft",
            new_state="queued", round_authorized=False, is_root=True,
        )

    def test_worker_cannot_skip_to_pm(self):
        self.bad(
            "illegal hierarchy edge",
            sender="worker_grok", destination="pm", old_state="working",
            new_state="review", round_authorized=True,
        )

    def test_worker_returns_to_parent_lead(self):
        self.ok(
            sender="worker_grok", destination="software", old_state="working",
            new_state="review", round_authorized=True,
        )

    def test_pm_never_receives_queued_agent_work(self):
        self.bad(
            "PM cannot receive",
            sender="software", destination="pm", old_state="review",
            new_state="queued", round_authorized=True,
        )

    def test_lead_returns_review_to_pm(self):
        self.ok(
            sender="software", destination="pm", old_state="working",
            new_state="review", round_authorized=True,
        )

    def test_waiting_parent_can_be_released_by_bus_fanin(self):
        self.ok(
            sender="bus", destination="software", old_state="waiting",
            new_state="queued", round_authorized=True,
        )

    def test_bus_cannot_invent_normal_work(self):
        self.bad(
            "bus actor may only",
            sender="bus", destination="software", old_state="draft",
            new_state="queued", round_authorized=True,
        )

    def test_untyped_lateral_review_is_red(self):
        self.bad(
            "lateral Verification routing",
            sender="software", destination="verification", old_state="draft",
            new_state="queued", round_authorized=True,
        )

    def test_typed_independent_review_request_is_legal(self):
        self.ok(
            sender="software", destination="verification", old_state="draft",
            new_state="queued", round_authorized=True,
            independent_review=True,
        )

    def test_typed_independent_review_result_returns_to_requester(self):
        self.ok(
            sender="verification", destination="software", old_state="working",
            new_state="review", round_authorized=True,
            independent_review=True,
        )

    def test_independent_review_cannot_bypass_verification_seam(self):
        self.bad(
            "not self-service",
            sender="software", destination="verification", old_state="draft",
            new_state="queued", round_authorized=True,
            independent_review=True, verification_self_service_allowed=False,
        )

    def test_new_scope_cannot_be_requeued(self):
        self.bad(
            "expand root scope",
            sender="software", destination="worker_grok", old_state="draft",
            new_state="queued", round_authorized=True,
            existing_root_scope=False,
        )

    def test_non_root_requires_native_parent(self):
        self.bad(
            "native GitHub sub-issue",
            sender="software", destination="worker_grok", old_state="draft",
            new_state="queued", round_authorized=True, is_native_child=False,
        )


if __name__ == "__main__":
    unittest.main()
