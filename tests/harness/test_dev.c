/*
 * Block-device port self-tests.
 *
 * Software Lead scaffolding verification, NOT acceptance. These check that the
 * ports do what their headers claim, so that when a Verification Lead test
 * fails it is failing on the engine rather than on my plumbing.
 *
 * The one thing here that is load-bearing beyond plumbing: guardrail 06 says a
 * read-only device has no write function, and these assert that neither opening
 * read-only nor wrapping in the simulator ever manufactures one.
 */

#include <stdlib.h>
#include "harness.h"
#include "dev_file.h"
#include "dev_sim.h"
#include "dev_sd.h"

#define IMG_BLOCKS 64u

static void fill(unsigned char *b, unsigned char seed)
{
    unsigned i;
    for (i = 0; i < TAPE_BLOCK_SIZE; i++) {
        b[i] = (unsigned char)(seed + i);
    }
}

int main(void);

int main(void)
{
    const char *path = "./tape_test_scratch.img";
    struct tape_dev_file f;
    tape_dev dev;
    unsigned char w[TAPE_BLOCK_SIZE], r[TAPE_BLOCK_SIZE];

    /* --- create, write, read back --- */
    if (tape_dev_file_create(&f, &dev, path, IMG_BLOCKS) != TAPE_DEV_OK) {
        (void)fprintf(stderr, "  FAIL cannot create %s — aborting\n", path);
        return TAPE_TEST_REPORT("dev ports") + 1;
    }
    tape_test_checks++;
    CHECK_EQ_U32(dev.block_count, IMG_BLOCKS);
    CHECK(dev.write != NULL);

    fill(w, 0x11);
    CHECK_EQ_INT(dev.write(dev.ctx, 5u, 1u, w), TAPE_DEV_OK);
    CHECK_EQ_INT(dev.flush(dev.ctx), TAPE_DEV_OK);
    memset(r, 0, sizeof r);
    CHECK_EQ_INT(dev.read(dev.ctx, 5u, 1u, r), TAPE_DEV_OK);
    CHECK_MEM_EQ(r, w, TAPE_BLOCK_SIZE);

    /* A freshly created image is zero-filled, not garbage. */
    CHECK_EQ_INT(dev.read(dev.ctx, 6u, 1u, r), TAPE_DEV_OK);
    {
        unsigned char zero[TAPE_BLOCK_SIZE];
        memset(zero, 0, sizeof zero);
        CHECK_MEM_EQ(r, zero, TAPE_BLOCK_SIZE);
    }

    /* Range checks: the last block is addressable, one past it is not. Written
       as lba+count so a count that overruns is caught, not just a bad lba. */
    CHECK_EQ_INT(dev.read(dev.ctx, IMG_BLOCKS - 1u, 1u, r), TAPE_DEV_OK);
    CHECK_EQ_INT(dev.read(dev.ctx, IMG_BLOCKS, 1u, r), TAPE_DEV_ERR_RANGE);
    CHECK_EQ_INT(dev.read(dev.ctx, IMG_BLOCKS - 1u, 2u, r), TAPE_DEV_ERR_RANGE);
    CHECK_EQ_INT(dev.write(dev.ctx, IMG_BLOCKS - 1u, 2u, w), TAPE_DEV_ERR_RANGE);
    CHECK_EQ_INT(tape_dev_file_close(&f), TAPE_DEV_OK);

    /* --- guardrail 06: read-only has no write function at all --- */
    CHECK_EQ_INT(tape_dev_file_open(&f, &dev, path, 0), TAPE_DEV_OK);
    CHECK(dev.write == NULL);
    CHECK_EQ_INT(dev.read(dev.ctx, 5u, 1u, r), TAPE_DEV_OK);
    CHECK_MEM_EQ(r, w, TAPE_BLOCK_SIZE);

    /* Wrapping a read-only device must not manufacture a write path. */
    {
        struct tape_dev_sim sim;
        tape_dev simdev;
        tape_dev_sim_bind(&sim, &simdev, &dev);
        CHECK(simdev.write == NULL);
    }
    CHECK_EQ_INT(tape_dev_file_close(&f), TAPE_DEV_OK);

    /* --- simulator: power loss --- */
    CHECK_EQ_INT(tape_dev_file_open(&f, &dev, path, 1), TAPE_DEV_OK);
    {
        struct tape_dev_sim sim;
        tape_dev sd;
        tape_dev_sim_bind(&sim, &sd, &dev);
        CHECK(sd.write != NULL);
        tape_dev_sim_arm(&sim, TAPE_SIM_POWER_LOSS, 2u, 0u);

        fill(w, 0x22);
        CHECK_EQ_INT(sd.write(sd.ctx, 10u, 1u, w), TAPE_DEV_OK);
        CHECK_EQ_INT(sd.write(sd.ctx, 11u, 1u, w), TAPE_DEV_OK);
        /* Third write is past the limit: dies, and stays dead. */
        CHECK_EQ_INT(sd.write(sd.ctx, 12u, 1u, w), TAPE_ERR_IO);
        CHECK_EQ_INT(sd.write(sd.ctx, 13u, 1u, w), TAPE_ERR_IO);
        CHECK_EQ_U32(sim.writes_seen, 2u);
        CHECK(sim.dead != 0);

        /* What landed before the cut is still there; what did not, is not. */
        CHECK_EQ_INT(dev.read(dev.ctx, 11u, 1u, r), TAPE_DEV_OK);
        CHECK_MEM_EQ(r, w, TAPE_BLOCK_SIZE);
        CHECK_EQ_INT(dev.read(dev.ctx, 12u, 1u, r), TAPE_DEV_OK);
        {
            unsigned char zero[TAPE_BLOCK_SIZE];
            memset(zero, 0, sizeof zero);
            CHECK_MEM_EQ(r, zero, TAPE_BLOCK_SIZE);
        }
    }

    /* --- simulator: torn write --- */
    {
        struct tape_dev_sim sim;
        tape_dev sd;
        unsigned char before[TAPE_BLOCK_SIZE];

        fill(before, 0x33);
        CHECK_EQ_INT(dev.write(dev.ctx, 20u, 1u, before), TAPE_DEV_OK);

        tape_dev_sim_bind(&sim, &sd, &dev);
        tape_dev_sim_arm(&sim, TAPE_SIM_TORN_WRITE, 0u, 100u);
        fill(w, 0x44);
        CHECK_EQ_INT(sd.write(sd.ctx, 20u, 1u, w), TAPE_ERR_IO);

        CHECK_EQ_INT(dev.read(dev.ctx, 20u, 1u, r), TAPE_DEV_OK);
        CHECK_MEM_EQ(r, w, 100u);                       /* the part that landed */
        CHECK_MEM_EQ(r + 100, before + 100, TAPE_BLOCK_SIZE - 100u); /* and the part that did not */
    }
    CHECK_EQ_INT(tape_dev_file_close(&f), TAPE_DEV_OK);
    (void)remove(path);

    /* --- SD stub: honest failure, and slot 0 has no write function --- */
    {
        struct tape_dev_sd sd_st;
        tape_dev sd_dev;
        CHECK_EQ_INT(tape_dev_sd_bind(&sd_st, &sd_dev, 0u), TAPE_DEV_ERR_NOT_IMPLEMENTED);
        CHECK(sd_dev.write == NULL);                    /* source slot */
        CHECK_EQ_INT(tape_dev_sd_bind(&sd_st, &sd_dev, 1u), TAPE_DEV_ERR_NOT_IMPLEMENTED);
        CHECK(sd_dev.write != NULL);                    /* work slot */
        CHECK_EQ_INT(sd_dev.read(sd_dev.ctx, 0u, 1u, r), TAPE_DEV_ERR_NOT_IMPLEMENTED);
    }

    return TAPE_TEST_REPORT("dev ports");
}
