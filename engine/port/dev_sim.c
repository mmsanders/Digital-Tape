#include <string.h>
#include "dev_sim.h"

static int sim_read(void *ctx, uint32_t lba, uint32_t count, void *buf)
{
    struct tape_dev_sim *st = (struct tape_dev_sim *)ctx;

    st->reads_seen++;
    /* Reads survive power loss: after the plug is pulled the card is simply
       re-read on the next mount, which is the case under test. */
    return st->inner->read(st->inner->ctx, lba, count, buf);
}

static int sim_write(void *ctx, uint32_t lba, uint32_t count, const void *buf)
{
    struct tape_dev_sim *st = (struct tape_dev_sim *)ctx;
    unsigned char block[TAPE_BLOCK_SIZE];
    uint32_t i;
    int rc;

    if (st->dead) {
        return TAPE_ERR_IO;
    }

    for (i = 0; i < count; i++) {
        if (st->mode != TAPE_SIM_HEALTHY && st->writes_seen >= st->fail_after_writes) {
            if (st->mode == TAPE_SIM_TORN_WRITE) {
                /* Read what is there, overlay only the bytes that made it, and
                   write that back. Then die. */
                uint32_t n = st->torn_bytes;
                if (n > TAPE_BLOCK_SIZE) {
                    n = TAPE_BLOCK_SIZE;
                }
                rc = st->inner->read(st->inner->ctx, lba + i, 1u, block);
                if (rc != TAPE_OK) {
                    st->dead = 1;
                    return rc;
                }
                memcpy(block, (const unsigned char *)buf + (size_t)i * TAPE_BLOCK_SIZE, n);
                (void)st->inner->write(st->inner->ctx, lba + i, 1u, block);
            }
            st->dead = 1;
            return TAPE_ERR_IO;
        }

        rc = st->inner->write(st->inner->ctx, lba + i, 1u,
                              (const unsigned char *)buf + (size_t)i * TAPE_BLOCK_SIZE);
        if (rc != TAPE_OK) {
            return rc;
        }
        st->writes_seen++;
    }
    return TAPE_OK;
}

static int sim_flush(void *ctx)
{
    struct tape_dev_sim *st = (struct tape_dev_sim *)ctx;

    st->flushes_seen++;
    if (st->dead) {
        return TAPE_ERR_IO;
    }
    return st->inner->flush(st->inner->ctx);
}

void tape_dev_sim_bind(struct tape_dev_sim *st, struct tape_dev *dev,
                       const struct tape_dev *inner)
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

void tape_dev_sim_arm(struct tape_dev_sim *st, enum tape_sim_mode mode,
                      uint32_t fail_after_writes, uint32_t torn_bytes)
{
    st->mode              = mode;
    st->fail_after_writes = fail_after_writes;
    st->torn_bytes        = torn_bytes;
    st->dead              = 0;
}

void tape_dev_sim_revive(struct tape_dev_sim *st)
{
    st->mode = TAPE_SIM_HEALTHY;
    st->dead = 0;
}
