/*
 * tape_dev.h — the block device interface.
 *
 * Normative: spec/engine-api.md DRAFT-3 §3. This header is that definition in C.
 *
 * The entire coupling between the engine and the world (guardrail 09,
 * contract 2). Every tape_dev is a block view of TAPEFS partition 2 — LBA 0 is
 * the partition's first block, and the engine never sees the MBR.
 */

#ifndef TAPE_DEV_H
#define TAPE_DEV_H

#include <stddef.h>
#include <stdint.h>

#define TAPE_BLOCK_SIZE 512u

/* spec/engine-api.md §2. Every engine call returns one of these. There are no
   error strings, and there are no timeouts: the engine has no clock and must
   not acquire one. */
typedef enum {
    TAPE_OK = 0,
    TAPE_ERR_IO,                  /* block device returned failure */
    TAPE_ERR_BAD_MAGIC,
    TAPE_ERR_CRC,
    TAPE_ERR_VERSION,             /* version_major != 1; nothing touched */
    TAPE_ERR_GEOMETRY,            /* fails the tapefs §4.1 geometry checks */
    TAPE_ERR_INCOMPLETE,          /* superblock state == WRITE_IN_PROGRESS */
    TAPE_ERR_INCONSISTENT,        /* two valid copies, equal generation, differing */
    TAPE_ERR_NO_VALID_INDEX,
    TAPE_ERR_READ_ONLY,           /* write against write == NULL, or against Side A */
    TAPE_ERR_CARTRIDGE_FULL,
    TAPE_ERR_INDEX_FULL,
    TAPE_ERR_SEQUENCE_EXHAUSTED,
    TAPE_ERR_NOT_MOUNTED,
    TAPE_ERR_BUSY,                /* the §10 state matrix forbids this call now */
    TAPE_ERR_UNDERRUN,            /* tape_render had less than requested */
    TAPE_ERR_INVALID_ARG
} tape_result;

/* Callbacks return 0 on success, non-zero on failure. `count` is in 512-byte
   blocks. `flush` must not return success until data has reached media — on SD,
   the card has left the busy state, not merely accepted the blocks. */
typedef struct {
    int (*read)(void *ctx, uint32_t lba, uint32_t count, void *dst);
    int (*write)(void *ctx, uint32_t lba, uint32_t count, const void *src);
    int (*flush)(void *ctx);
    void *ctx;
    uint32_t block_count;
} tape_dev;

/*
 * `write` is NULL for a read-only device. That is the entire mechanism for the
 * source slot — no flag, no mode, no permission check (guardrail 06).
 *
 * `block_count` is caller-supplied and UNTRUSTED. tape_mount validates the
 * superblock's geometry against it and refuses on mismatch; the geometry checks
 * exist to protect against this field as much as against the card.
 */

#endif /* TAPE_DEV_H */
