/*
 * WP-06 mount read path — every refusal in tapefs §4.1 and §5.2.
 *
 * spec/acceptance.md, WP-06: "Every mount rule in tapefs §4.1 and §5.2 has a
 * test that exercises its refusal path."
 *
 * Software Lead scaffolding. NOT acceptance — the Verification Lead signs off,
 * and these exist so that when its tests land they fail on the engine rather
 * than on my plumbing. Each case breaks exactly one thing in an otherwise valid
 * cartridge, because a fixture broken two ways cannot tell you which rule fired.
 */

#include <stdlib.h>
#include "harness.h"
#include "media.h"
#include "tape.h"

/* Sized so the geometry check passes: chunk_base + total_chunks*CHUNK_BLOCKS
   must be <= block_count. Getting this wrong makes every index test fail with
   TAPE_ERR_GEOMETRY instead, because §4.1 validates geometry before it reads an
   index — which is the correct order, and worth stating since it caught me. */
#define CHUNKS     4u
#define BLOCKS  (TAPE_LBA_CHUNK_BASE + CHUNKS * TAPE_CHUNK_BLOCKS + 1u)

static struct media MED;
static unsigned char INST[262144];
static unsigned char PLAY[TAPE_PLAY_RING_MIN], REC[TAPE_REC_RING_MIN];

typedef struct med_ent ent;

/* A valid C-60-shaped cartridge: Side A one run, Side B mirroring it. */
static void build_valid(void)
{
    static const ent a[1] = { { 0u, 0u, 1000u } };
    memset(&MED, 0, sizeof MED);
    MED.block_count = BLOCKS;
    MED.writable = 0;
    med_sb(MED.head[0], CHUNKS, CHUNKS, BLOCKS, 1u, TAPE_STATE_VALID);
    memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
    med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, a, 1u);
    med_invalidate(&MED, TAPE_LBA_INDEX_A1);
    med_index(&MED, TAPE_LBA_INDEX_B0, 1u, 2u, a, 1u);
    med_invalidate(&MED, TAPE_LBA_INDEX_B1);
}

static tape_result mount_side(tape_side side, tape **out)
{
    tape_dev dev;
    tape *t = NULL;
    tape_result rc;

    med_bind(&MED, &dev);
    rc = tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY, REC, sizeof REC, &t);
    if (rc != TAPE_OK) { return rc; }
    if (out != NULL) { *out = t; }
    return tape_mount(t, side, 0u, NULL, 0u);
}

static tape_result mount_a(void) { return mount_side(TAPE_SIDE_A, NULL); }

int main(void);

int main(void)
{
    /* ---- the instance fits its budget ---- */
    CHECK(tape_instance_size() <= 200u * 1024u);
    CHECK(tape_instance_size() <= sizeof INST);

    /* ---- baseline: a valid cartridge mounts ---- */
    build_valid();
    {
        tape *t = NULL;
        tape_info info;
        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, &t), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK_EQ_U32((uint32_t)info.total_frames, 1000u);
        CHECK_EQ_U32(info.entry_count, 1u);
        CHECK_EQ_U32(info.entries_free, TAPE_MAX_ENTRIES - 1u);
        CHECK_EQ_U32(info.nominal_length_s, 3600u);      /* C-60 */
        CHECK(!info.writable);                            /* read-only device */
        CHECK(!info.needs_repair);
        CHECK_EQ_U32((uint32_t)tape_tell(t), 0u);
        /* Side A refuses writes at the API boundary even on a writable device. */
        CHECK_EQ_INT(tape_unmount(t, NULL), TAPE_OK);
        CHECK_EQ_INT(tape_unmount(t, NULL), TAPE_ERR_NOT_MOUNTED);
    }

    /* ---- §4.1 superblock refusals ---- */

    /* both copies bad magic */
    build_valid();
    MED.head[0][0] ^= 0xFFu; MED.mirror[0] ^= 0xFFu;
    CHECK_EQ_INT(mount_a(), TAPE_ERR_BAD_MAGIC);

    /* both copies bad CRC (magic intact) */
    build_valid();
    MED.head[0][36] ^= 0x01u; MED.mirror[36] ^= 0x01u;
    CHECK_EQ_INT(mount_a(), TAPE_ERR_CRC);

    /* exactly one valid -> mounts, and reports needs_repair on a read-only device */
    build_valid();
    memset(MED.mirror, 0, TAPE_BLOCK_SIZE);
    {
        tape *t = NULL; tape_info info;
        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, &t), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(info.needs_repair);       /* never repaired: write == NULL */
    }

    /* both valid, different generation -> the higher wins */
    build_valid();
    med_sb(MED.mirror, CHUNKS, CHUNKS, BLOCKS, 7u, TAPE_STATE_VALID);
    wr32(MED.mirror + 48, 5400u);       /* C-90 label, only in the mirror */
    med_fix_sb_crc(MED.mirror);
    {
        tape *t = NULL; tape_info info;
        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, &t), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK_EQ_U32(info.nominal_length_s, 5400u);   /* generation 7 chosen */
    }

    /* both valid, equal generation, differing bytes -> INCONSISTENT */
    build_valid();
    wr32(MED.mirror + 48, 7200u);
    med_fix_sb_crc(MED.mirror);
    CHECK_EQ_INT(mount_a(), TAPE_ERR_INCONSISTENT);

    /* version refusal comes BEFORE repair: an unsupported version is not
       corruption, and repairing it is how a v1 reader downgrades v2 media */
    build_valid();
    wr16(MED.head[0] + 8, 2u); med_fix_sb_crc(MED.head[0]);
    memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
    CHECK_EQ_INT(mount_a(), TAPE_ERR_VERSION);

    /* an interrupted duplicate is recognisably unfinished, not corrupt */
    build_valid();
    MED.head[0][16] = TAPE_STATE_WRITE_IN_PROGRESS; med_fix_sb_crc(MED.head[0]);
    memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
    CHECK_EQ_INT(mount_a(), TAPE_ERR_INCOMPLETE);

    /* ---- §4.1 geometry refusals, one field at a time ---- */
    {
        static const struct { const char *what; uint32_t off; uint32_t bad; int is16; } G[] = {
            { "sample_rate",     36,  48000u, 0 },
            { "channels",        40,      1u, 1 },
            { "bits_per_sample", 42,     24u, 1 },
            { "chunk_bytes",     44, 262144u, 0 },
            { "index_slot_bytes",60,  32768u, 0 },
            { "lba_index_a0",    64,      9u, 0 },
            { "lba_index_a1",    68,    137u, 0 },
            { "lba_index_b0",    72,    265u, 0 },
            { "lba_index_b1",    76,    393u, 0 },
            { "lba_chunk_base",  80,   4096u, 0 },
            { "mirror lba",      84, BLOCKS, 0 },      /* must be block_count-1 */
            { "total_chunks 0",  52,      0u, 0 },
        };
        size_t k;
        for (k = 0; k < sizeof G / sizeof G[0]; k++) {
            build_valid();
            if (G[k].is16) { wr16(MED.head[0] + G[k].off, (uint16_t)G[k].bad); }
            else           { wr32(MED.head[0] + G[k].off, G[k].bad); }
            med_fix_sb_crc(MED.head[0]);
            memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
            CHECK_EQ_INT(mount_a(), TAPE_ERR_GEOMETRY);
        }
    }

    /* a_high_water > total_chunks */
    build_valid();
    wr32(MED.head[0] + 56, CHUNKS + 1u); med_fix_sb_crc(MED.head[0]);
    memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
    CHECK_EQ_INT(mount_a(), TAPE_ERR_GEOMETRY);

    /* chunk store runs past the end of the device — the check that must be done
       in 64-bit so a huge total_chunks cannot wrap into a passing value */
    build_valid();
    wr32(MED.head[0] + 52, 0xFFFFFFu); med_fix_sb_crc(MED.head[0]);
    memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
    CHECK_EQ_INT(mount_a(), TAPE_ERR_GEOMETRY);

    /* block_count is untrusted input (issue #14): a device that lies about its
       own size must be refused, not believed */
    build_valid();
    MED.block_count = BLOCKS + 1u;
    CHECK_EQ_INT(mount_a(), TAPE_ERR_GEOMETRY);

    /* ---- §5.2 index refusals ---- */

    /* no valid slot for the side */
    build_valid();
    med_invalidate(&MED, TAPE_LBA_INDEX_A0);
    CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);

    /* wrong side marker in the slot */
    build_valid();
    MED.head[TAPE_LBA_INDEX_A0][12] = 1u;
    CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);

    /* entry_count over the maximum */
    build_valid();
    wr32(MED.head[TAPE_LBA_INDEX_A0] + 16, TAPE_MAX_ENTRIES + 1u);
    CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);

    /* index CRC */
    build_valid();
    MED.head[TAPE_LBA_INDEX_A0 + 1u][0] ^= 0x01u;
    CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);

    /* total_frames disagreeing with the sum of frame_count */
    build_valid();
    { unsigned char *h = MED.head[TAPE_LBA_INDEX_A0];
      uint32_t crc;
      wr64(h + 20, 999u);
      crc = tape_crc32_init();
      crc = tape_crc32_update(crc, h, 60u);
      crc = tape_crc32_update(crc, MED.head[TAPE_LBA_INDEX_A0 + 1u], 12u);
      wr32(h + 60, tape_crc32_final(crc)); }
    CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);

    /* frame_count == 0, and start_frame >= CHUNK_FRAMES */
    {
        static const ent bad_zero[1]  = { { 0u, 0u, 0u } };
        static const ent bad_start[1] = { { 0u, TAPE_CHUNK_FRAMES, 10u } };
        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, bad_zero, 1u);
        CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);
        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, bad_start, 1u);
        CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);
    }

    /*
     * §5.2's most important check: for Side A the bound is the LAST chunk of a
     * run, not the first. This run STARTS below a_high_water and ENDS above it —
     * a first-chunk-only check would accept it, and Side A would reference the
     * sandbox. This is the off-by-one the spec calls out by name.
     */
    {
        static const ent straddle[1] = { { 0u, 0u, TAPE_CHUNK_FRAMES + 1u } };
        build_valid();
        wr32(MED.head[0] + 52, 4u);          /* total_chunks = 4 */
        wr32(MED.head[0] + 56, 1u);          /* a_high_water = 1 */
        med_fix_sb_crc(MED.head[0]);
        memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, straddle, 1u);
        CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);
    }

    /* run ending past total_chunks */
    {
        static const ent over[1] = { { 0u, 0u, TAPE_CHUNK_FRAMES * 8u } };
        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, over, 1u);
        CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);
    }

    /* higher sequence wins between two valid slots */
    {
        static const ent one[1] = { { 0u, 0u, 100u } };
        static const ent two[1] = { { 0u, 0u, 200u } };
        tape *t = NULL; tape_info info;
        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 5u, one, 1u);
        med_index(&MED, TAPE_LBA_INDEX_A1, 0u, 9u, two, 1u);
        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, &t), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK_EQ_U32((uint32_t)info.total_frames, 200u);
    }

    /* ---- §7 free_next is derived, never stored ---- */
    {
        /* Side B run ending in chunk 2 -> free_next 3, so 1 free chunk of 4. */
        static const ent b[1] = { { 1u, 0u, TAPE_CHUNK_FRAMES + 1u } };
        tape *t = NULL; tape_info info;
        build_valid();
        wr32(MED.head[0] + 52, 4u);         /* total_chunks */
        wr32(MED.head[0] + 56, 1u);         /* a_high_water */
        med_fix_sb_crc(MED.head[0]);
        memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        med_index(&MED, TAPE_LBA_INDEX_B0, 1u, 3u, b, 1u);
        CHECK_EQ_INT(mount_side(TAPE_SIDE_B, &t), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK_EQ_U32(info.free_chunks, 1u);
    }

    /* resume_frame beyond the timeline clamps rather than failing (§11) */
    {
        tape *t = NULL;
        tape_dev dev;
        build_valid();
        med_bind(&MED, &dev);
        CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_OK);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 999999u, NULL, 0u), TAPE_OK);
        CHECK_EQ_U32((uint32_t)tape_tell(t), 1000u);
    }

    /* ---- tape_init argument checks ---- */
    {
        tape_dev dev; tape *t = NULL;
        build_valid();
        med_bind(&MED, &dev);
        CHECK_EQ_INT(tape_init(NULL, sizeof INST, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_ERR_INVALID_ARG);
        CHECK_EQ_INT(tape_init(INST, 16u, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_ERR_INVALID_ARG);
        CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, 1024u,
                               REC, sizeof REC, &t), TAPE_ERR_INVALID_ARG);
    }

    return TAPE_TEST_REPORT("mount read path");
}
