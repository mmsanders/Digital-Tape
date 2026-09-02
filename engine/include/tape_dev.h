/*
 * tape_dev.h — the block device interface.
 *
 * This is the entire coupling between the engine and the world (guardrail 09,
 * contract 2). Two function pointers for read and write, plus flush. The same
 * engine logic runs against a file on a laptop, a deliberately flaky simulator,
 * and a real SD peripheral.
 *
 * PROVISIONAL. The normative definition is spec/engine-api.md, authored by the
 * PM; DRAFT-3 is pending. This header carries only what PM Decisions 001/002
 * state explicitly:
 *
 *   - read, write and flush callbacks over a block view
 *   - write == NULL means read-only, by construction, not by a flag
 *   - the view is always partition 2 (Decisions 002 §10); MBR and FAT32
 *     provisioning belong to tapectl, and the engine never sees them
 *
 * Field order, error values and the exact signatures are reconciled against
 * DRAFT-3 when it lands. Nothing here is a design decision I am entitled to
 * make; where the spec is silent this file states the minimum that compiles.
 */

#ifndef TAPE_DEV_H
#define TAPE_DEV_H

#include <stddef.h>
#include <stdint.h>

/* TAPEFS addresses the partition in 512-byte blocks. */
#define TAPE_BLOCK_SIZE 512u

/*
 * PROVISIONAL error values. The normative enum is DRAFT-3's. These exist so the
 * port layer and its tests compile; they are deliberately few, and no engine
 * logic depends on their numeric values.
 */
#define TAPE_OK                 0
#define TAPE_ERR_IO           (-1)
#define TAPE_ERR_RANGE        (-2)
#define TAPE_ERR_NOT_IMPLEMENTED (-3)

/*
 * Callbacks. All take the device's own context as the first argument, so an
 * implementation carries its state without the engine knowing what state is.
 *
 * Return TAPE_OK, or a negative error. A short transfer is an error, not a
 * partial success — the engine has no path for partial block I/O.
 */
typedef int (*tape_dev_read_fn)(void *ctx, uint32_t lba, uint32_t count, void *buf);
typedef int (*tape_dev_write_fn)(void *ctx, uint32_t lba, uint32_t count, const void *buf);
typedef int (*tape_dev_flush_fn)(void *ctx);

struct tape_dev {
    tape_dev_read_fn  read;   /* never NULL */
    tape_dev_write_fn write;  /* NULL for the source slot — see guardrail 06 */
    tape_dev_flush_fn flush;  /* never NULL */
    void             *ctx;
    uint32_t          block_count;  /* size of the partition view, in blocks */
};

#endif /* TAPE_DEV_H */
