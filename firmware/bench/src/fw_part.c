/*
 * fw_part.c — partition 2 of a whole card as the engine's tape_dev.
 * See fw_part.h. The firmware twin of host/port/partview.c.
 */

#include "fw_part.h"
#include "layout.h"

static int in_range(const struct fw_part *p, uint32_t lba, uint32_t count)
{
    return lba <= p->blocks && count <= p->blocks - lba;
}

static int part_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    struct fw_part *p = (struct fw_part *)ctx;
    if (!in_range(p, lba, count)) { return 2; }
    p->reads++;
    return p->card->read(p->card->ctx, p->base + lba, count, dst) ? 1 : 0;
}

/* One block per card call (FW-1 §4: write batching stays off until the Q-P2-1
   any-subset coverage is complete). */
static int part_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    struct fw_part *p = (struct fw_part *)ctx;
    const uint8_t *b = (const uint8_t *)src;
    uint32_t i;
    if (!in_range(p, lba, count)) { return 2; }
    for (i = 0; i < count; i++) {
        p->writes++;
        if (p->card->write(p->card->ctx, p->base + lba + i, 1u, b + (uint32_t)i * TAPE_BLOCK_SIZE)) { return 1; }
    }
    return 0;
}

static int part_flush(void *ctx)
{
    struct fw_part *p = (struct fw_part *)ctx;
    p->flushes++;
    return p->card->flush(p->card->ctx) ? 1 : 0;
}

fw_part_result fw_part_open(struct fw_part *p, const tape_dev *card, tape_dev *out, int writable)
{
    uint8_t lba0[TAPE_BLOCK_SIZE];
    uint32_t start, sectors;

    if (card->read(card->ctx, 0u, 1u, lba0)) { return FW_PART_IO; }
    if (!mbr_is_layout(lba0, card->block_count)) { return FW_PART_NOT_PROVISIONED; }
    mbr_entry2(lba0, &start, &sectors);

    p->card = card;
    p->base = start;
    p->blocks = sectors;
    p->reads = p->writes = p->flushes = 0;
    out->read = part_read;
    /* Read-only is the absence of a function, not a flag (guardrail 06). */
    out->write = (writable && card->write != NULL) ? part_write : NULL;
    out->flush = part_flush;
    out->ctx = p;
    out->block_count = sectors;
    return FW_PART_OK;
}
