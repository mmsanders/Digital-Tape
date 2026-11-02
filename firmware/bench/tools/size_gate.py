#!/usr/bin/env python3
"""F2 static budgets for the linked Teensy image (FW-1 §6, guardrail 08).

    RAM     <= 200 KiB   engine .data + engine .bss + the instance
    .rodata <=  32 KiB   engine .rodata

The same sums tools/ci/audit-memory.sh asserts for the desktop archive
(spec/engine-api.md §4), measured here from the LINKED firmware, which is the
authoritative number that script's closing note leaves to Stream 4:

  * engine sections come from the link map: every input section the linker
    kept from libtape_engine.a, so what --gc-sections dropped is not counted;
  * the instance term is the firmware's static reservation for it,
    fw_engine_instance, sized from the ELF symbol table. That is what the
    firmware spends; the firmware refuses at boot if tape_instance_size()
    does not fit in it.

Whole-image section totals are printed for context and never gated: the play
and record rings and the Teensy core are caller storage, outside the budget.

Prints every measured value whether it passes or not. Exit 0 pass, 1 over
budget, 2 the gate could not measure (a broken gate is never a pass).

    size_gate.py --map firmware.map --elf firmware.elf --nm arm-none-eabi-nm
"""

import argparse
import re
import subprocess
import sys

RAM_BUDGET = 200 * 1024
ROD_BUDGET = 32 * 1024
ENGINE_ARCHIVE = "libtape_engine.a("
INSTANCE_SYMBOL = "fw_engine_instance"

# An input-section entry in a GNU ld map: " .name  0xaddr  0xsize  file". Long
# names put the address, size and file on the following line.
ENTRY = re.compile(r"^ (\.\S+|COMMON)(?:\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+(.+))?$")
CONT = re.compile(r"^\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+(.+)$")


def kind(section):
    for k in ("data", "bss", "rodata"):
        if section == "." + k or section.startswith("." + k + "."):
            return k
    if section == "COMMON":
        return "common"
    return None


def engine_sections(map_text):
    """Sum engine input sections by kind. Raises if the map has no memory-map part."""
    marker = "Linker script and memory map"
    if marker not in map_text:
        raise ValueError("not a GNU ld map file: no '%s' section" % marker)
    lines = map_text.split(marker, 1)[1].splitlines()
    sums = {"data": 0, "bss": 0, "rodata": 0, "common": 0}
    objects = set()
    i = 0
    while i < len(lines):
        m = ENTRY.match(lines[i])
        if m:
            name, addr, size, path = m.groups()
            if size is None and i + 1 < len(lines):
                c = CONT.match(lines[i + 1])
                if c:
                    addr, size, path = c.groups()
                    i += 1
            if size is not None and ENGINE_ARCHIVE in path:
                objects.add(path.strip())
                k = kind(name)
                if k is not None:
                    sums[k] += int(size, 16)
        i += 1
    return sums, objects


def symbol_size(nm, elf, symbol):
    out = subprocess.run([nm, "-S", "--defined-only", elf], check=True,
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[3] == symbol:
            return int(parts[1], 16)
    raise ValueError("symbol %s not found in %s" % (symbol, elf))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--elf", required=True)
    ap.add_argument("--nm", required=True)
    ap.add_argument("--size-tool", help="arm-none-eabi-size, for the whole-image context lines")
    a = ap.parse_args()

    try:
        with open(a.map, encoding="utf-8", errors="replace") as f:
            sums, objects = engine_sections(f.read())
        if not objects:
            raise ValueError("no input sections from %s) in the map: the engine is not "
                             "linked, or the archive was renamed" % ENGINE_ARCHIVE[:-1])
        instance = symbol_size(a.nm, a.elf, INSTANCE_SYMBOL)
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        print("FAIL  gate is broken: %s" % e)
        return 2

    data, bss, rodata, common = sums["data"], sums["bss"], sums["rodata"], sums["common"]
    ram = data + bss + common + instance
    print("== gate: F2 firmware budgets (linked image) ==")
    print("        engine objects linked  %d" % len(objects))
    print("        engine .data    %8d" % data)
    print("        engine .bss     %8d" % bss)
    print("        engine COMMON   %8d" % common)
    print("        instance        %8d   (%s reservation)" % (instance, INSTANCE_SYMBOL))
    print("        RAM             %8d / %d bytes  (%d%%)" % (ram, RAM_BUDGET, ram * 100 // RAM_BUDGET))
    print("        engine .rodata  %8d / %d bytes  (%d%%)" % (rodata, ROD_BUDGET, rodata * 100 // ROD_BUDGET))
    if a.size_tool:
        out = subprocess.run([a.size_tool, "-A", a.elf], capture_output=True, text=True).stdout
        print("        whole image, for context only (not gated):")
        for line in out.splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[0].startswith(".") and parts[1].isdigit() and int(parts[1]) > 0:
                print("          %-16s %8s" % (parts[0], parts[1]))

    rc = 0
    if ram > RAM_BUDGET:
        print("FAIL  RAM %d exceeds 200 KiB by %d bytes" % (ram, ram - RAM_BUDGET))
        print("      = engine .data %d + .bss %d + COMMON %d + instance %d" % (data, bss, common, instance))
        rc = 1
    if rodata > ROD_BUDGET:
        print("FAIL  engine .rodata %d exceeds 32 KiB by %d bytes" % (rodata, rodata - ROD_BUDGET))
        rc = 1
    if rc == 0:
        print("PASS  both budgets")
    return rc


if __name__ == "__main__":
    sys.exit(main())
