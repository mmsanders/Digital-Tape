/*
 * fw_part.h — partition 2 of a whole card as the engine's tape_dev.
 *
 * Normative: docs/WP17-FIRMWARE-CONTRACT.md §4, docs/WP14-CLI-CONTRACT.md §3.1
 * and spec/tapefs-v1.md §3. Portable C99, no board knowledge: the card below is
 * any whole-card tape_dev (block 0 is the MBR). On the Teensy that is the SDIO
 * slot (fw_sd.cpp); off target it is engine/port/dev_file over a whole image,
 * which is how CI tests this file.
 *
 * Recognition is tapectl's own: host/port/mbr.c's exact §3.1 test against the
 * card's sector count, built unchanged into the firmware. A card that is not
 * the §3.1 layout is refused, never presented bare.
 */

#ifndef FW_PART_H
#define FW_PART_H

#include <stdint.h>
#include "tape_dev.h"

typedef enum {
    FW_PART_OK = 0,
    FW_PART_IO,               /* block 0 could not be read */
    FW_PART_NOT_PROVISIONED   /* block 0 is not the §3.1 layout for this card */
} fw_part_result;

struct fw_part {
    const tape_dev *card;     /* the whole card */
    uint32_t base;            /* partition 2's first block on the card */
    uint32_t blocks;          /* partition 2's length */
    uint32_t reads, writes, flushes;   /* calls made to the card */
};

/*
 * Read block 0 of `card`, check the §3.1 layout and bind `out` to partition 2,
 * so the engine sees partition 2's first block as LBA 0. `out->write` is bound
 * only when `writable` is non-zero and the card itself has a write function;
 * otherwise it is NULL (guardrail 06). Each partition write is issued to the
 * card one block per call, in ascending order, before it returns (no batching,
 * FW-1 §4). On refusal `out` is left untouched.
 */
fw_part_result fw_part_open(struct fw_part *p, const tape_dev *card, tape_dev *out, int writable);

#endif /* FW_PART_H */
