/*
 * tape_dev.h — the block device interface.
 *
 * Normative: spec/engine-api.md DRAFT-6 §3. This header is that definition in C.
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
    TAPE_ERR_VERSION,             /* version_major != 1; nothing written, no repair */
    TAPE_ERR_UNSUPPORTED_STATE,   /* a superblock field holds a value v1 does not define:
                                     state or promote_stage outside {0,1}. Nothing written */
    TAPE_ERR_GEOMETRY,            /* fails tapefs §2.1 GEOMETRY_OK or §4.1 phase 2 */
    TAPE_ERR_INCOMPLETE,          /* superblock state == WRITE_IN_PROGRESS */
    TAPE_ERR_INCONSISTENT,        /* two valid copies that cannot be ordered: equal
                                     sb_generation and not byte-identical (superblock),
                                     or equal sequence at all (index); or
                                     promote_stage == 1 matching no §9.3.3 resume row */
    TAPE_ERR_NO_VALID_INDEX,      /* also: a B-dependent call on a degraded-B mount (§4.4) */
    TAPE_ERR_READ_ONLY,           /* the mount is not effectively writable (§3.1), a raw
                                     destination has write == NULL, or arm against Side A */
    TAPE_ERR_CARTRIDGE_FULL,
    TAPE_ERR_INDEX_FULL,
    TAPE_ERR_DEST_TOO_SMALL,      /* tape_dup: destination cannot hold the source timeline */
    TAPE_ERR_SEQUENCE_EXHAUSTED,  /* tapefs §4.5 headroom unavailable for this whole
                                     operation; refused before its first write */
    TAPE_ERR_FAULTED,             /* a write or flush failed with indeterminate durability;
                                     the instance is quarantined until unmount. §7.2 */
    TAPE_ERR_NOT_MOUNTED,
    TAPE_ERR_BUSY,                /* the §10 state matrix forbids this call now */
    TAPE_ERR_UNDERRUN,            /* tape_render was short because the play ring was */
    TAPE_ERR_INVALID_ARG          /* includes tape_dup aliasing and continuation mismatch */
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
 * `write` is NULL for a read-only device. That is how the source slot is
 * constructed — no flag, no mode, no permission check (guardrail 06).
 *
 * It is NECESSARY for a mount to be writable and, since DRAFT-6, NOT SUFFICIENT.
 * The permission model is §3.1's one predicate:
 *
 *     effective_writable = (dev.write != NULL) && (mounted version_minor == 0)
 *
 * dev_write keeps its `write != NULL` assertion as a last-line debug check. That
 * is a test instrument, not a field safety net: on a freestanding MCU address 0
 * is usually mapped, so an indirect call through a null `write` in a release
 * build is undefined and often silent. The predicate is the safety.
 *
 * `block_count` is caller-supplied and UNTRUSTED. tape_mount validates the
 * superblock's geometry against it and refuses on mismatch; the geometry checks
 * exist to protect against this field as much as against the card.
 */

#endif /* TAPE_DEV_H */
