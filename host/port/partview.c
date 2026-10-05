/*
 * partview.c — a block range of an hport as the engine's tape_dev.
 *
 * Normative: docs/WP14-CLI-CONTRACT.md §6 ("a partition view presenting
 * partition 2 as the engine's tape_dev") and §4.1 (verify binds a NULL write
 * callback). The engine sees LBA 0 as the first block of the range and never
 * sees the MBR. Each write is issued before it returns: no coalescing.
 */

#include "hport.h"

static int in_range(const struct partview *v, uint32_t lba, uint32_t count)
{
    return lba <= v->blocks && count <= v->blocks - lba;
}

static int pv_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    struct partview *v = (struct partview *)ctx;
    v->reads++;
    if (!in_range(v, lba, count)) { return 2; }
    return hport_read(v->p, (v->base + lba) * TAPE_BLOCK_SIZE, dst, (size_t)count * TAPE_BLOCK_SIZE) ? 1 : 0;
}

static int pv_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    struct partview *v = (struct partview *)ctx;
    v->writes++;
    if (!in_range(v, lba, count)) { return 2; }
    return hport_write(v->p, (v->base + lba) * TAPE_BLOCK_SIZE, src, (size_t)count * TAPE_BLOCK_SIZE) ? 1 : 0;
}

static int pv_flush(void *ctx)
{
    struct partview *v = (struct partview *)ctx;
    v->flushes++;
    return hport_flush(v->p) ? 1 : 0;
}

void partview_bind(struct partview *v, tape_dev *dev, struct hport *p,
                   uint64_t base_lba, uint32_t blocks, int writable)
{
    v->p = p;
    v->base = base_lba;
    v->blocks = blocks;
    v->reads = v->writes = v->flushes = 0;
    dev->read = pv_read;
    /* Read-only is the absence of a function, not a flag (guardrail 06). */
    dev->write = (writable && p->writable) ? pv_write : NULL;
    dev->flush = pv_flush;
    dev->ctx = v;
    dev->block_count = blocks;
}
