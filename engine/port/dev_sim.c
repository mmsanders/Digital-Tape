#include <string.h>
#include "dev_sim.h"

static int sim_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    struct tape_dev_sim *st = (struct tape_dev_sim *)ctx;
    st->reads_seen++;
    return st->inner->read(st->inner->ctx, lba, count, dst);
}

static int sim_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    struct tape_dev_sim *st = (struct tape_dev_sim *)ctx;
    st->writes_seen++;
    return st->inner->write(st->inner->ctx, lba, count, src);
}

static int sim_flush(void *ctx)
{
    struct tape_dev_sim *st = (struct tape_dev_sim *)ctx;
    st->flushes_seen++;
    return st->inner->flush(st->inner->ctx);
}

void tape_dev_sim_bind(struct tape_dev_sim *st, tape_dev *dev, const tape_dev *inner)
{
    memset(st, 0, sizeof *st);
    st->inner = inner;

    dev->read  = sim_read;
    /* Never manufacture a write path the inner device does not have. */
    dev->write = (inner->write != NULL) ? sim_write : NULL;
    dev->flush = sim_flush;
    dev->ctx   = st;
    dev->block_count = inner->block_count;
}

void tape_dev_sim_reset(struct tape_dev_sim *st)
{
    st->reads_seen = 0u;
    st->writes_seen = 0u;
    st->flushes_seen = 0u;
}
