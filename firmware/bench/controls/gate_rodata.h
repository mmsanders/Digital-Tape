/*
 * gate_rodata.h — F2 negative control only (env teensy41_ctl_rodata).
 *
 * Force-included into every engine translation unit of the control build, so
 * the linked libtape_engine.a carries 33 KiB of .rodata: one byte-for-byte
 * engine build plus an oversized static. tools/size_gate.py must FAIL on it.
 * Weak, so the copies in each object collapse to one; main.cpp references it
 * in this build so --gc-sections keeps it. Never in a real build; never flash.
 */
extern const unsigned char tape_gate_control_rodata[33u * 1024u];
__attribute__((weak, used)) const unsigned char tape_gate_control_rodata[33u * 1024u] = {1u};
