/*
 * fw_storage.c — the caller-owned engine storage (guardrail 08, FW-1 §2).
 *
 * Static, never heap. It lives in OCRAM (the Teensy's DMAMEM region, RAM2) so
 * the tightly coupled RAM stays for code, stack and the audio library.
 *
 * FW_INSTANCE_RESERVE is what tape_instance_size() returns on the desktop build
 * (191 600 bytes at engine tree d96b4245). The ARM instance is no larger:
 * pointers shrink and the 64-bit fields keep their 8-byte alignment under
 * AAPCS. main.cpp checks tape_instance_size() against it at boot and refuses
 * to start the engine if it does not fit, so a wrong reserve is loud, never a
 * silent overrun. The F2 size gate (tools/size_gate.py) counts this reserve as
 * the instance term, so the gate measures what the firmware actually spends.
 */

#include "fw_storage.h"

#ifndef FW_SIZE_GATE_CONTROL
#define FW_SIZE_GATE_CONTROL 0
#endif

#if FW_SIZE_GATE_CONTROL
/* F2 negative control only (env teensy41_oversize): 16 KiB more instance
   reserve takes the counted RAM over 200 KiB. CI requires the gate to fail. */
#define FW_RESERVE (FW_INSTANCE_RESERVE + 16384u)
#else
#define FW_RESERVE FW_INSTANCE_RESERVE
#endif

#define FW_DMAMEM __attribute__((section(".dmabuffers"), used, aligned(8)))

FW_DMAMEM uint8_t fw_engine_instance[FW_RESERVE];
FW_DMAMEM uint8_t fw_play_ring[TAPE_PLAY_RING_MIN];
FW_DMAMEM uint8_t fw_rec_ring[TAPE_REC_RING_MIN];

const size_t fw_engine_instance_len = sizeof fw_engine_instance;
