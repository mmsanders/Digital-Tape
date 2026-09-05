/*
 * tape.h — Digital Tape engine, public API.
 *
 * Normative: spec/engine-api.md DRAFT-6. Where this header and the spec differ,
 * the spec is right and this is a defect.
 *
 * Implementation status. The engine is built against structural Rule 1: engine
 * implementation stays on unmerged branches until the Verification Lead's tests
 * for that behaviour have landed on main, so main carries spec, then tests, then
 * implementation, in that order.
 *
 *   Implemented   tape_instance_size, tape_init, tape_mount (all four phases,
 *                 both sides, degraded-B and the stage oracle), tape_unmount,
 *                 tape_get_info, tape_set_side, tape_tell, and the WP-07
 *                 allocator (tape_alloc_run)
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
/* spec/tapefs-v1.md §5.4. Position is 64-bit with 32 fractional bits, so the
   whole part holds 32 bits of frames; media declaring more is rejected at mount
   rather than becoming unseekable later. */
#define TAPE_MAX_TOTAL_FRAMES  0xFFFFFFFFu

/* Region LBAs, normative in spec/tapefs-v1.md §3. */
#define TAPE_LBA_SUPERBLOCK      0u
#define TAPE_LBA_INDEX_A0        8u
#define TAPE_LBA_INDEX_A1      136u
#define TAPE_LBA_INDEX_B0      264u
#define TAPE_LBA_INDEX_B1      392u
#define TAPE_LBA_CHUNK_BASE   2048u

/* Superblock `state`, spec §4. NO OTHER VALUE IS DEFINED — an undefined one is
   TAPE_ERR_UNSUPPORTED_STATE at mount, not a value to interpret (V4-012). */
#define TAPE_STATE_VALID             0u
#define TAPE_STATE_WRITE_IN_PROGRESS 1u

/* Superblock `promote_stage`, spec §4 offset 124. Same rule: {0, 1} only. */
#define TAPE_PROMOTE_STAGE_NONE      0u
#define TAPE_PROMOTE_STAGE_PHASE1    1u

typedef enum { TAPE_SIDE_A = 0, TAPE_SIDE_B = 1 } tape_side;

/*
 * Warm start (spec §5, §12). A validated descriptor, not a bare pointer: a ring
 * retained from cartridge X side A must not be rendered into a mount of
 * cartridge Y side B. A mismatch DISABLES warm start rather than failing the
 * mount — a wrong buffer costs instant-on, never correctness.
 *
 * `data_bytes` is the caller's buffer size and it is checked. Principle 1 says
 * the caller owns the buffer; it does not say the engine takes its dimensions on
 * trust, and without this field the engine had no way to know the buffer was big
 * enough for the valid_frames it claimed (V4-011).
 *
 * The whole descriptor is optional: `warm == NULL` is the ordinary cold mount,
 * and §5's algorithm is ORDERED so that no field is read until the pointer is
 * known non-NULL.
 */
typedef struct {
    const void *data;         /* frames, same layout as tape_render output */
    uint32_t    data_bytes;   /* size of the buffer at `data` */
    uint32_t    valid_frames;
    uint32_t    start_frame;  /* timeline frame the first sample represents */
    uint8_t     uuid[16];
    tape_side   side;
} tape_warm_start;

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
                       const tape_warm_start *warm);   /* warm may be NULL */
tape_result tape_unmount(tape *t, uint64_t *out_position_frame);

typedef struct {
    uint8_t  uuid[16];
    char     label[33];
    uint32_t nominal_length_s;
    uint64_t total_frames;              /* of the mounted side */
    uint32_t total_chunks, free_chunks;
    uint32_t entry_count, entries_free;
    uint16_t version_minor;             /* why `writable` may be false on a device
                                           that can perfectly well write */
    bool     writable;                  /* effective_writable, §3.1 */
    bool     side_b_valid;              /* false in degraded-B (tapefs §4.4) */
    bool     needs_repair;              /* one superblock copy invalid, and either the
                                           mount is not effectively writable or the
                                           phase-4 repair write failed */
    bool     warm_start_used;
} tape_info;

tape_result tape_get_info(const tape *t, tape_info *out);
tape_result tape_set_side(tape *t, tape_side side);

/* --- transport (§6) --------------------------------------------------------- */

tape_result tape_seek(tape *t, uint64_t frame);   /* beyond end clamps; TAPE_OK */
/* DRAFT-6 (V5-009): this returns tape_result, not a bare uint64_t. §2 says every
   call returns tape_result and §10's Not-mounted row requires
   TAPE_ERR_NOT_MOUNTED from every ordinary call — which the old signature had no
   channel for, so an implementation had to invent a sentinel or return a stale
   position. On refusal *out_frame is left untouched. */
tape_result tape_tell(const tape *t, uint64_t *out_frame);
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

/* respool, promote and dup share one incremental contract: each call does at
   most block_budget blocks of work and sets *more_work while any remains. A
   ~30 s blocking call in an engine that must service audio and has no clock was
   never going to work. */
tape_result tape_reset_side_b(tape *t);
tape_result tape_promote(tape *t, uint32_t block_budget, bool *more_work,
                         tape_progress_fn cb, void *user);
tape_result tape_respool(tape *t, uint32_t block_budget, bool *more_work);
/* The destination is a DEVICE, not a mount. A blank card and an interrupted copy
   are both unmountable by design, so a mounted dst made "re-run to finish"
   impossible to perform (spec §9.5). */
tape_result tape_dup(tape *src, const tape_dev *dst_dev,
                     const uint8_t new_uuid[16], uint32_t epoch,
                     uint32_t dst_nominal_length_s,
                     uint32_t block_budget, bool *more_work,
                     tape_progress_fn cb, void *user);
tape_result tape_format(const tape_dev *dev, const uint8_t uuid[16], uint32_t epoch,
                        const char *label, uint32_t nominal_length_s);

#endif /* TAPE_H */
