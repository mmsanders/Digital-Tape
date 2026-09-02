/*
 * tape.h — Digital Tape engine, public API.
 *
 * Normative: spec/engine-api.md DRAFT-3. Where this header and the spec differ,
 * the spec is right and this is a defect.
 *
 * Implementation status. The engine is built against structural Rule 1: engine
 * implementation stays on unmerged branches until the Verification Lead's tests
 * for that behaviour have landed on main, so main carries spec, then tests, then
 * implementation, in that order.
 *
 *   Implemented   tape_instance_size, tape_init, tape_mount (read path),
 *                 tape_unmount, tape_get_info, tape_set_side, tape_tell
 *   Declared,     everything else. Calling one is a link error, which is the
 *   not defined   intended loud failure rather than a silent stub.
 *
 * Guardrails this header exists to keep: no allocation ever (the caller owns all
 * storage, §4); no clock and no timeout anywhere (§9); nothing returns a pointer
 * the caller must free.
 */

#ifndef TAPE_H
#define TAPE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "tape_dev.h"

/* --- constants, normative in spec/tapefs-v1.md §1 --------------------------- */

#define TAPE_SAMPLE_RATE      44100u
#define TAPE_CHANNELS             2u
#define TAPE_FRAME_BYTES          4u
#define TAPE_BYTE_RATE       176400u
#define TAPE_CHUNK_BYTES     524288u
#define TAPE_CHUNK_FRAMES    131072u
#define TAPE_CHUNK_BLOCKS      1024u
#define TAPE_INDEX_SLOT_BYTES 65536u
#define TAPE_INDEX_ENTRY_BYTES   12u
#define TAPE_MAX_ENTRIES       4096u

/* Region LBAs, normative in spec/tapefs-v1.md §3. */
#define TAPE_LBA_SUPERBLOCK      0u
#define TAPE_LBA_INDEX_A0        8u
#define TAPE_LBA_INDEX_A1      136u
#define TAPE_LBA_INDEX_B0      264u
#define TAPE_LBA_INDEX_B1      392u
#define TAPE_LBA_CHUNK_BASE   2048u

/* Superblock `state`, spec §4. */
#define TAPE_STATE_VALID             0u
#define TAPE_STATE_WRITE_IN_PROGRESS 1u

typedef enum { TAPE_SIDE_A = 0, TAPE_SIDE_B = 1 } tape_side;

typedef struct tape tape;

/* --- memory: the caller owns all storage (§4) ------------------------------- */

size_t tape_instance_size(void);   /* compile-time constant */

tape_result tape_init(void *mem, size_t mem_len,
                      const tape_dev *dev,
                      void *play_ring, size_t play_ring_len,
                      void *rec_ring,  size_t rec_ring_len,
                      tape **out);

#define TAPE_PLAY_RING_MIN 65536u  /* ~372 ms */
#define TAPE_REC_RING_MIN  65536u

/* --- lifecycle (§5) --------------------------------------------------------- */

tape_result tape_mount(tape *t, tape_side side, uint64_t resume_frame,
                       const void *warm_start, size_t warm_start_len);
tape_result tape_unmount(tape *t, uint64_t *out_position_frame);

typedef struct {
    uint8_t  uuid[16];
    char     label[33];
    uint32_t nominal_length_s;
    uint64_t total_frames;              /* of the mounted side */
    uint32_t total_chunks, free_chunks;
    uint32_t entry_count, entries_free;
    bool     writable;
    bool     needs_repair;              /* one copy invalid; device is read-only */
} tape_info;

tape_result tape_get_info(const tape *t, tape_info *out);
tape_result tape_set_side(tape *t, tape_side side);

/* --- transport (§6) --------------------------------------------------------- */

tape_result tape_seek(tape *t, uint64_t frame);   /* beyond end clamps; TAPE_OK */
uint64_t    tape_tell(const tape *t);
tape_result tape_set_rate(tape *t, int32_t rate_q16_16);

tape_result tape_render(tape *t, int16_t *out, uint32_t frames, uint32_t *rendered);
tape_result tape_service(tape *t, uint32_t block_budget, bool *more_work);

typedef struct {
    bool     at_end, at_start;
    bool     recording_armed, frames_owed;
    uint32_t entries_free;              /* record-light headroom colour */
    uint32_t free_chunks;
} tape_status_t;

tape_result tape_status(const tape *t, tape_status_t *out);

/* --- recording (§7) --------------------------------------------------------- */

typedef enum { TAPE_REC_OVERWRITE = 0, TAPE_REC_OVERDUB, TAPE_REC_SPLICE } tape_rec_mode;

tape_result tape_arm(tape *t, tape_rec_mode mode);
tape_result tape_feed(tape *t, const int16_t *in, uint32_t frames, uint32_t *accepted);
tape_result tape_commit(tape *t);
tape_result tape_abort(tape *t);

/* --- cartridge operations (§9) ---------------------------------------------- */

/* Counts only. Rates and ETAs are the caller's, because only the caller knows
   what a second is. Do not add timeout_ms to any call here — it will look like a
   bug fix during SD bring-up and it is a guardrail violation. */
typedef void (*tape_progress_fn)(void *user, uint32_t blocks_done, uint32_t blocks_total);

tape_result tape_reset_side_b(tape *t);
tape_result tape_promote(tape *t, tape_progress_fn cb, void *user);
tape_result tape_respool(tape *t, uint32_t block_budget, bool *more_work);
tape_result tape_dup(tape *src, tape *dst, const uint8_t new_uuid[16], uint32_t epoch,
                     tape_progress_fn cb, void *user);
tape_result tape_format(const tape_dev *dev, const uint8_t uuid[16], uint32_t epoch,
                        const char *label, uint32_t nominal_length_s);

#endif /* TAPE_H */
