"""Load the unchanged V382 fixture support; no Product implementation imports."""
import importlib.util
from pathlib import Path

PREVIOUS = Path(__file__).resolve().parent.parent / 'be1_binding_r1'
spec = importlib.util.spec_from_file_location('v382_fixture_support', PREVIOUS/'fixtures.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
