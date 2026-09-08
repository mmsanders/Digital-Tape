"""IR-018-18: exercise the documented Make entry point in isolated fixtures.

Fixture acceptances are synthetic and never modify the real safety record.
These are implementer-owned regression tests, not independent safety acceptance.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent


class MakeGateTests(unittest.TestCase):
    def invoke(self, accepted=False, qualified=False, suppress=False):
        with tempfile.TemporaryDirectory(prefix="tape-gate-test-") as folder:
            root = Path(folder)
            (root / "thermal").mkdir()
            shutil.copy2(ROOT / "thermal/solenoid_timing.py",
                         root / "thermal/solenoid_timing.py")
            recipe = (ROOT / "Makefile").read_text()
            if suppress:
                recipe = recipe.replace("@$(PY) fabrication_gate.py\n",
                                        "@$(PY) fabrication_gate.py || true\n")
            (root / "Makefile").write_text(recipe)
            gate = (ROOT / "fabrication_gate.py").read_text()
            # Test-only qualification/acceptance fixture immediately before main.
            state = ("from dataclasses import replace\n"
                     f"sol.TIMING_BOUND_VERIFIED = {qualified!r}\n"
                     "BLOCKERS = tuple(replace(b, accepted_by="
                     f"{'TEST FIXTURE ONLY' if accepted else ''!r}"
                     ") for b in BLOCKERS)\n")
            gate = gate.replace('if __name__ == "__main__":',
                                state + '\nif __name__ == "__main__":')
            (root / "fabrication_gate.py").write_text(gate)
            return subprocess.run(
                ["make", "--no-print-directory", "-C", str(root), "fabrication-gate"],
                text=True, capture_output=True, timeout=30)

    def test_closed_and_partial_acceptances_return_nonzero(self):
        for accepted, qualified in ((False, False), (True, False), (False, True)):
            with self.subTest(accepted=accepted, qualified=qualified):
                result = self.invoke(accepted, qualified)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("CLOSED", result.stdout)

    def test_only_fully_accepted_qualified_fixture_opens(self):
        result = self.invoke(accepted=True, qualified=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OPEN. Every blocker", result.stdout)

    def test_fail_open_recipe_mutation_is_detected(self):
        result = self.invoke(suppress=True)
        self.assertIn("CLOSED", result.stdout)
        # Reproduce exactly the bad exit-status contract, not a simulated verdict.
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with self.assertRaises(AssertionError):
            self.assertNotEqual(result.returncode, 0, "CLOSED must fail")


if __name__ == "__main__":
    unittest.main()
