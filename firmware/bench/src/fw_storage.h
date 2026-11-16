/*
 * fw_storage.h — the caller-owned engine storage. See fw_storage.c.
 */

#ifndef FW_STORAGE_H
#define FW_STORAGE_H

#include <stddef.h>
#include <stdint.h>
#include "tape.h"
#include "fw_wake.h"

#ifdef __cplusplus
extern "C" {
#endif

#define FW_INSTANCE_RESERVE 191600u

extern uint8_t fw_engine_instance[];
extern const size_t fw_engine_instance_len;
extern uint8_t fw_play_ring[TAPE_PLAY_RING_MIN];
extern uint8_t fw_rec_ring[TAPE_REC_RING_MIN];
/* Audio retained across a bench sleep (fw_wake.h). Caller storage, like the
   rings: outside the engine budget the F2 gate counts. */
extern int16_t fw_warm_pcm[];

#ifdef __cplusplus
}
#endif

#endif /* FW_STORAGE_H */
