#!/usr/bin/env python3
"""WP-11 portability configuration (c): the static-assert alternative (#366).

acceptance WP-11 asks for one configuration in which integer-promotion width is
visible: a narrow-int build, a 16-bit target, or "a static assertion on INT_MAX
plus a compile-time check that the operands are cast before subtraction". The
engine cannot be built for a 16-bit target (tape_internal.h's 4096-entry index
arrays exceed a 16-bit address space; avr-gcc rejects them), so this is that
alternative. Two checks, both at compile time:

1. Static assertions, compiled with the engine's flags against the hook TU:
   INT_MAX is at least the C minimum, and int64_t is exactly 64 bits wide, so a
   difference of two int16 values formed in int64_t cannot overflow on any
   conforming target, whatever int is.
2. The compiler's own AST (clang -ast-dump=json) of engine/src/play.c's
   play_interpolate, the function tape_test_interp() calls: every binary
   subtraction must have BOTH operands as explicit casts to int64_t of the
   int16_t parameters. A late cast, (int64_t)(b - a), subtracts in int first
   and is exactly the DRAFT-5 overflow the gate exists to catch.

--control runs check 2 against a copy of play.c with the cast moved late and
requires it to go red, so the check is shown able to fail.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FUNC = "play_interpolate"

ASSERTS = r"""
#include <limits.h>
#include <stdint.h>
#include "tape_test_hooks.h"
typedef char wp11_int_max_at_least_c_minimum[(INT_MAX >= 32767) ? 1 : -1];
typedef char wp11_int64_is_64_bits[(sizeof(int64_t) * CHAR_BIT == 64) ? 1 : -1];
typedef char wp11_int16_is_16_bits[(sizeof(int16_t) * CHAR_BIT == 16) ? 1 : -1];
int wp11_static_asserts_compiled(void);
int wp11_static_asserts_compiled(void) { return (int)sizeof(wp11_int64_is_64_bits); }
"""


def static_asserts(tmp: Path) -> None:
    src = tmp / "wp11_static_asserts.c"
    src.write_text(ASSERTS)
    cmd = ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-fsyntax-only",
           "-I", str(ROOT / "engine/test"), "-I", str(ROOT / "engine/include"), str(src)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("static assertions failed to compile:\n" + r.stderr)
    print("  ok    static assertions: INT_MAX >= 32767, int64_t is 64 bits, int16_t is 16 bits")


def strip(node):
    while node.get("kind") in ("ParenExpr", "ImplicitCastExpr") and node.get("inner"):
        node = node["inner"][0]
    return node


def find_function(node):
    if isinstance(node, dict):
        if node.get("kind") == "FunctionDecl" and node.get("name") == FUNC and node.get("inner"):
            if any(c.get("kind") == "CompoundStmt" for c in node["inner"]):
                return node
        for c in node.get("inner", []) or []:
            got = find_function(c)
            if got is not None:
                return got
    return None


def subtractions(node, out):
    if isinstance(node, dict):
        if node.get("kind") == "BinaryOperator" and node.get("opcode") == "-":
            out.append(node)
        for c in node.get("inner", []) or []:
            subtractions(c, out)
    return out


def operand_ok(op) -> tuple[bool, str]:
    op = strip(op)
    if op.get("kind") != "CStyleCastExpr":
        return False, f"operand is {op.get('kind')}, not an explicit cast"
    if op.get("type", {}).get("qualType") != "int64_t":
        return False, f"cast to {op.get('type', {}).get('qualType')}, not int64_t"
    inner = strip(op["inner"][0])
    if inner.get("kind") != "DeclRefExpr" or inner.get("type", {}).get("qualType") != "int16_t":
        return False, "cast operand is not an int16_t parameter"
    return True, inner.get("referencedDecl", {}).get("name", "?")


def ast_check(play_c: Path) -> list[str]:
    """Problems found in play_interpolate's subtractions; empty means green."""
    hook = ROOT / "engine/test/tape_test_hooks.c"
    with tempfile.TemporaryDirectory() as t:
        tu = Path(t) / "hook_tu.c"
        tu.write_text(f'#include "{play_c}"\n' + "\n".join(
            l for l in hook.read_text().splitlines() if not l.startswith('#include "../src/play.c"')) + "\n")
        cmd = ["clang", "-std=c99", "-fsyntax-only", "-I", str(ROOT / "engine/include"), "-I",
               str(ROOT / "engine/src"), "-I", str(ROOT / "engine/test"), "-Xclang", "-ast-dump=json", str(tu)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        return ["clang failed: " + r.stderr.strip()[-400:]]
    fn = find_function(json.loads(r.stdout))
    if fn is None:
        return [f"{FUNC} not found in the hook translation unit"]
    subs = subtractions(fn, [])
    if not subs:
        return [f"{FUNC} has no binary subtraction; the check would prove nothing"]
    problems = []
    for s in subs:
        lhs, rhs = s["inner"][0], s["inner"][1]
        for side, op in (("left", lhs), ("right", rhs)):
            ok, why = operand_ok(op)
            if not ok:
                problems.append(f"subtraction {side} operand: {why}")
    return problems


def main() -> int:
    control = "--control" in sys.argv
    print("== WP-11 portability (c): static-assert alternative ==")
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        if not control:
            static_asserts(tmp)
            problems = ast_check(ROOT / "engine/src/play.c")
            for p in problems:
                print("  FAIL  " + p)
            if problems:
                return 1
            print(f"  ok    {FUNC}: every subtraction casts both int16_t operands to int64_t first")
            return 0
        # Negative control: the late cast must be caught.
        mutated = tmp / "play.c"
        text = (ROOT / "engine/src/play.c").read_text()
        late = re.sub(r"\(\(int64_t\)b - \(int64_t\)a\)", "((int64_t)(b - a))", text, count=1)
        if late == text:
            print("  FAIL  control could not find the subtraction to mutate")
            return 1
        mutated.write_text(late)
        for h in (ROOT / "engine/src").glob("*.h"):
            shutil.copy(h, tmp / h.name)
        problems = ast_check(mutated)
        if problems:
            print(f"  ok    late cast (int64_t)(b - a) goes red: {problems[0]}")
            return 0
        print("  FAIL  late cast survived the check")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
