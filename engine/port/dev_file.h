/*
 * dev_file.h — file-backed block device. Desktop only.
 *
 * A cartridge image in a regular file. This is what the golden fixtures run
 * against and what tapectl uses against a real card.
 *
 * Ports live outside the engine proper: this one uses libc file I/O, which
 * guardrail 08 forbids *in the engine*. That is the point of the block-device
 * boundary — the engine never learns that a file exists. Ports are built into
 * a separate archive and are not subject to the engine's allocation, stack or
 * memory gates.
 */

#ifndef TAPE_PORT_DEV_FILE_H
#define TAPE_PORT_DEV_FILE_H

#include <stdio.h>
#include "tape_dev.h"

struct tape_dev_file {
    FILE    *fp;
    uint32_t block_count;
    int      writable;
};

/*
 * Open an existing image. `writable` false produces a device with write == NULL
 * — the source slot, by construction rather than by a flag (guardrail 06).
 * Returns TAPE_OK, or TAPE_ERR_IO.
 */
int tape_dev_file_open(struct tape_dev_file *st, struct tape_dev *dev,
                       const char *path, int writable);

/* Create (or truncate) an image of `blocks` blocks, zero-filled, and open it
   writable. Returns TAPE_OK, or TAPE_ERR_IO. */
int tape_dev_file_create(struct tape_dev_file *st, struct tape_dev *dev,
                         const char *path, uint32_t blocks);

int tape_dev_file_close(struct tape_dev_file *st);

#endif /* TAPE_PORT_DEV_FILE_H */
