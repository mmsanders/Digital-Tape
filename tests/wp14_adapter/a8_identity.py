#!/usr/bin/env python3
"""Bind the unchanged independent A8 audit to PM's immutable ADR-175 pin."""
import argparse
import importlib.util
import json
from pathlib import Path

ORIGINAL_ENGINE = 'b80a8e54775c5aabad7bc338a6e30db3596b657b'
ACCEPTED_ENGINE = 'd96b4245e04d74078f8938744b1394c3018516f7'
AUTHORITY = '842eae65f65bec8baf469377f605a72d7acb6bd9'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('verification', 'product', 'publication', 'candidate',
                 'import-commit', 'import-path', 'golden-path'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / 'wp14_r1' / 'a8_identity.py'
    spec = importlib.util.spec_from_file_location('wp14_independent_a8', path)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    # Keep the publication byte-identical. Only the issued comparison operand
    # changes; every imported assertion, golden comparison and ancestry check runs.
    audit.tree_equal(ORIGINAL_ENGINE, audit.ENGINE, 'authored A8 pin')
    audit.ENGINE = ACCEPTED_ENGINE
    result = audit.audit(args.verification, args.product, args.publication,
                         args.candidate, args.import_commit, args.import_path,
                         args.golden_path)
    result['pin_authority'] = AUTHORITY
    result['original_package_engine_tree'] = ORIGINAL_ENGINE
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
