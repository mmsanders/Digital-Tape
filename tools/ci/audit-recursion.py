#!/usr/bin/env python3
"""CI gate 3 — guardrail 08: no recursion.

Builds a direct call graph from the disassembled archive and reports any cycle.

The archive is unlinked, so a call to an external symbol is emitted against a
relocation and disassembles as an offset inside the *calling* function — which
reads as self-recursion if you trust the `<name>` in the call line. We parse
`objdump -dr` and prefer the relocation's symbol whenever one is attached.

Indirect calls are counted separately: they cannot be proven acyclic here, and
in this engine the only sanctioned indirect calls are the two block-device
function pointers.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "build" / "engine" / "libtape.a"

# Two block-device function pointers are the entire coupling to the world.
INDIRECT_BUDGET = 2

FUNC = re.compile(r"^[0-9a-f]+ <([^>]+)>:")
CALL_DIRECT = re.compile(r"\bcall\w*\s+(?:0x)?[0-9a-f]+\s+<([^>]+)>")
CALL_INDIRECT = re.compile(r"\bcall\w*\s+\*")
# A tail call is a jmp to a function entry point. A jmp to <fn+0x..> is a branch
# inside the current function and is not an edge.
TAIL_DIRECT = re.compile(r"\bjmp\w*\s+(?:0x)?[0-9a-f]+\s+<([^>]+)>")
RELOC = re.compile(r"^\s+[0-9a-f]+:\s+R_\S+\s+(\S+)\s*$")
SUFFIX = re.compile(r"[+-]0x[0-9a-f]+$")


def strip_offset(sym: str) -> str:
    return SUFFIX.sub("", sym)


def build_graph(disasm: str):
    lines = disasm.splitlines()
    graph: dict[str, set[str]] = {}
    indirect: dict[str, int] = {}
    current = None

    for i, line in enumerate(lines):
        m = FUNC.match(line)
        if m:
            current = m.group(1)
            graph.setdefault(current, set())
            continue
        if current is None:
            continue

        if CALL_INDIRECT.search(line):
            indirect[current] = indirect.get(current, 0) + 1
            continue

        m = CALL_DIRECT.search(line)
        tail = None if m else TAIL_DIRECT.search(line)
        if m is None and tail is None:
            continue

        # A relocation on the following line names the real callee. Without it,
        # the <name+offset> in the instruction is an intra-object target.
        reloc = None
        if i + 1 < len(lines):
            r = RELOC.match(lines[i + 1])
            if r:
                reloc = strip_offset(r.group(1))

        if m is not None:
            graph[current].add(reloc if reloc is not None else strip_offset(m.group(1)))
        else:
            raw = tail.group(1)
            if reloc is not None:
                graph[current].add(reloc)
            elif not SUFFIX.search(raw):
                # Bare symbol: a tail call into another function (or itself).
                graph[current].add(raw)

    return graph, indirect


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Every elementary cycle reachable in the direct call graph."""
    found: list[list[str]] = []
    seen: set[frozenset[str]] = set()
    colour: dict[str, int] = {}

    def walk(node: str, path: list[str]) -> None:
        colour[node] = 1
        path.append(node)
        for nxt in sorted(graph.get(node, ())):
            state = colour.get(nxt, 0)
            if state == 1:
                cyc = path[path.index(nxt):] + [nxt]
                key = frozenset(cyc)
                if key not in seen:
                    seen.add(key)
                    found.append(cyc)
            elif state == 0 and nxt in graph:
                walk(nxt, path)
        path.pop()
        colour[node] = 2

    for node in sorted(graph):
        if colour.get(node, 0) == 0:
            walk(node, [])
    return found


def main() -> int:
    print("== gate: recursion audit ==")
    if not LIB.exists():
        print(f"FAIL  {LIB.relative_to(ROOT)} not built — cannot audit")
        return 1

    try:
        disasm = subprocess.run(
            ["objdump", "-dr", "--no-show-raw-insn", str(LIB)],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"FAIL  objdump unavailable or failed: {exc}")
        return 2

    graph, indirect = build_graph(disasm)
    cycles = find_cycles(graph)
    n_indirect = sum(indirect.values())

    if cycles:
        print("FAIL  recursion found:")
        for cyc in cycles:
            print("        " + " -> ".join(cyc))
        print()
        print("      Guardrail 08: no recursion. Stack depth in this engine must")
        print("      be statically bounded — it runs in an interrupt context.")
        return 1

    if n_indirect > INDIRECT_BUDGET:
        print(f"FAIL  {n_indirect} indirect call sites, budget is {INDIRECT_BUDGET}")
        for fn, n in sorted(indirect.items()):
            print(f"        {fn}: {n}")
        print()
        print("      The two block-device function pointers are the entire coupling")
        print("      between the engine and the world (guardrail 09). A third")
        print("      indirect call is an escalation, not a widening.")
        return 1

    print(f"PASS  no recursion; {n_indirect} indirect call site(s), budget {INDIRECT_BUDGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
