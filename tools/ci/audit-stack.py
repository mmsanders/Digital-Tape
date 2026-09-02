#!/usr/bin/env python3
"""CI gate — maximum engine stack depth <= 8 KiB (PM Decisions 001 §4).

This replaces the old recursion audit (issues #11, #12). "No recursion" was a
proxy; the requirement is a bounded stack, and this measures that directly.
Recursion falls out of it for free: a cycle in the call graph makes depth
unbounded, so it fails here without needing its own rule.

Input is GCC's own accounting -- `-fstack-usage` for frame sizes and
`-fcallgraph-info=su,da` for edges -- read from the .su/.ci files the engine
build drops beside each object. That means it measures the code that was
actually generated: an inlined callee's frame is already folded into its
caller's, and a tail call is not an edge because it does not grow the stack.
Nothing here parses disassembly.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_DIR = ROOT / "build" / "engine" / "src"
CEILING = 8 * 1024

# Externals whose frames we do not control. The allocation gate already bounds
# what the engine may reference at all, so this list stays short and explicit.
KNOWN_LEAF = {
    "__stack_chk_fail",
    "memset", "memcpy", "memmove", "memcmp",
    "__memset_chk", "__memcpy_chk", "__memmove_chk",
}

NODE = re.compile(r'node:\s*\{\s*title:\s*"([^"]+)"\s*label:\s*"([^"]*)"(.*?)\}', re.S)
EDGE = re.compile(r'edge:\s*\{\s*sourcename:\s*"([^"]+)"\s+targetname:\s*"([^"]+)"')
BYTES = re.compile(r'\\n(\d+)\s+bytes\s+\((static|dynamic|dynamic,bounded)\)')


def load():
    """Merge every .ci in the engine build into one call graph."""
    frames, dynamic, edges, declared = {}, set(), {}, set()
    files = sorted(CI_DIR.rglob("*.ci"))
    for f in files:
        text = f.read_text(errors="replace")
        for m_ in NODE.finditer(text):
            name, label, tail = m_.group(1), m_.group(2), m_.group(3)
            if "ellipse" in tail:          # declared here, defined elsewhere
                declared.add(name)
            m = BYTES.search(label)
            if m:
                frames[name] = max(frames.get(name, 0), int(m.group(1)))
                if m.group(2).startswith("dynamic"):
                    dynamic.add(name)
        for e_ in EDGE.finditer(text):
            src, dst = e_.group(1), e_.group(2)
            edges.setdefault(src, set()).add(dst)
    return files, frames, dynamic, edges, declared


def find_cycles(nodes, edges):
    found, seen, colour = [], set(), {}

    def walk(n, path):
        colour[n] = 1
        path.append(n)
        for m in sorted(edges.get(n, ())):
            c = colour.get(m, 0)
            if c == 1:
                cyc = path[path.index(m):] + [m]
                key = frozenset(cyc)
                if key not in seen:
                    seen.add(key)
                    found.append(cyc)
            elif c == 0 and m in nodes:
                walk(m, path)
        path.pop()
        colour[n] = 2

    for n in sorted(nodes):
        if colour.get(n, 0) == 0:
            walk(n, [])
    return found


def deepest(frames, edges):
    """Worst-case cumulative stack, and the chain that produces it."""
    memo = {}

    def cost(n, stack):
        if n in memo:
            return memo[n]
        if n in stack:                      # cycle; handled separately
            return (0, [n])
        own = frames.get(n, 0)
        stack.add(n)
        best, chain = 0, []
        for m in sorted(edges.get(n, ())):
            if m in KNOWN_LEAF and m not in frames:
                continue
            c, ch = cost(m, stack)
            if c > best:
                best, chain = c, ch
        stack.discard(n)
        memo[n] = (own + best, [n] + chain)
        return memo[n]

    worst, worst_chain = 0, []
    for n in frames:
        c, ch = cost(n, set())
        if c > worst:
            worst, worst_chain = c, ch
    return worst, worst_chain


def main() -> int:
    print("== gate: stack depth ==")
    files, frames, dynamic, edges, declared = load()

    if not files:
        print(f"FAIL  no .ci files under {CI_DIR.relative_to(ROOT)} — engine not built")
        print("      The gate needs -fstack-usage -fcallgraph-info=su,da (engine/Makefile).")
        return 1
    if not frames:
        print("FAIL  call graph is empty — no engine functions were compiled")
        return 1

    rc = 0

    if dynamic:
        print("FAIL  dynamically-sized stack frames (VLA or alloca):")
        for n in sorted(dynamic):
            print(f"        {n}")
        print("      Stack depth must be statically bounded; the engine runs in an")
        print("      interrupt context. Use a fixed-size buffer.")
        rc = 1

    cycles = find_cycles(set(frames), edges)
    if cycles:
        print("FAIL  recursion — stack depth is unbounded:")
        for c in cycles:
            print("        " + " -> ".join(c))
        rc = 1

    unresolved = sorted(
        d for d in declared
        if d not in frames and d not in KNOWN_LEAF
        and any(d in t for t in edges.values())
    )
    if unresolved:
        print("      note: frames unknown for external callees, counted as 0:")
        for u in unresolved:
            print(f"        {u}")

    if not cycles:
        worst, chain = deepest(frames, edges)
        pct = 100.0 * worst / CEILING
        print(f"        deepest chain  {' -> '.join(chain) if chain else '(none)'}")
        print(f"        ------  {worst} / {CEILING} bytes ({pct:.1f}% of ceiling)")
        if worst > CEILING:
            print(f"FAIL  stack depth {worst} exceeds the {CEILING}-byte ceiling "
                  f"by {worst - CEILING}")
            rc = 1

    if rc == 0:
        print(f"PASS  {len(frames)} functions, stack within {CEILING} bytes")
    return rc


if __name__ == "__main__":
    sys.exit(main())
