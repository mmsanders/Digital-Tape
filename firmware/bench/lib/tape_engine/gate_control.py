# F2 .rodata negative control hook (env teensy41_ctl_rodata only).
#
# Inert in every other build. When the env defines FW_SIZE_GATE_RODATA_CONTROL,
# every engine translation unit is compiled with controls/gate_rodata.h
# force-included, so the linked engine archive carries an oversized static and
# tools/size_gate.py must fail on it. The engine sources are never touched.
import os

Import("env")

project = env.subst("$PROJECT_DIR")
defines = env.Flatten(env.get("CPPDEFINES", []))
if any(str(d).startswith("FW_SIZE_GATE_RODATA_CONTROL") for d in defines):
    env.Append(CCFLAGS=["-include", os.path.join(project, "controls", "gate_rodata.h")])
    print("tape_engine: F2 .rodata NEGATIVE CONTROL build (never flash)")
