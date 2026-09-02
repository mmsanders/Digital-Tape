#include <string.h>
#include "dev_sd.h"

static int sd_read(void *ctx, uint32_t lba, uint32_t count, void *buf)
{
    (void)ctx; (void)lba; (void)count; (void)buf;
    return TAPE_DEV_ERR_NOT_IMPLEMENTED;
}

static int sd_write(void *ctx, uint32_t lba, uint32_t count, const void *buf)
{
    (void)ctx; (void)lba; (void)count; (void)buf;
    return TAPE_DEV_ERR_NOT_IMPLEMENTED;
}

static int sd_flush(void *ctx)
{
    (void)ctx;
    return TAPE_DEV_ERR_NOT_IMPLEMENTED;
}

int tape_dev_sd_bind(struct tape_dev_sd *st, tape_dev *dev, unsigned slot)
{
    memset(st, 0, sizeof *st);
    st->slot = slot;

    dev->read  = sd_read;
    dev->write = (slot == 0u) ? NULL : sd_write;   /* guardrail 06 */
    dev->flush = sd_flush;
    dev->ctx   = st;
    dev->block_count = st->block_count;
    return TAPE_DEV_ERR_NOT_IMPLEMENTED;
}
