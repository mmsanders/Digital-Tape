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
#define MED_A_HIGH_WATER CHUNKS
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
    return tape_mount(t, side, 0u, NULL);
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
        CHECK_EQ_U32(info.nominal_length_s, med_max_label_s(CHUNKS));
        CHECK(!info.writable);                            /* read-only device */
        CHECK(!info.needs_repair);
        { uint64_t pos = 0xDEADu; CHECK_EQ_INT(tape_tell(t, &pos), TAPE_OK); CHECK_EQ_U32((uint32_t)pos, 0u); }
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
    /*
     * The marker has to be a field that is NOT load-bearing, and finding one
     * took three attempts. A C-90 label failed DRAFT-4's label-coverage check.
     * A 5 s label then failed DRAFT-6's stricter rule, which requires the stored
     * total_chunks to EQUAL what nominal_length_s derives — 5 s derives 2
     * chunks against a 4-chunk store. Both times the marker was itself invalid
     * media and the engine was right to refuse it.
     *
     * `label` at offset 88 is advisory by definition (§4) and reaches
     * tape_info, so it distinguishes the two copies without changing geometry.
     */
    memcpy(MED.mirror + 88, "GENERATION SEVEN", 16);
    med_fix_sb_crc(MED.mirror);
    {
        tape *t = NULL; tape_info info;
        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, &t), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK_EQ_INT(memcmp(info.label, "GENERATION SEVEN", 16), 0);  /* gen 7 won */
    }

    /* both valid, equal generation, differing bytes -> INCONSISTENT */
    build_valid();
    memcpy(MED.mirror + 88, "GENERATION SEVEN", 16);
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
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 999999u, NULL), TAPE_OK);
        { uint64_t pos = 0; CHECK_EQ_INT(tape_tell(t, &pos), TAPE_OK); CHECK_EQ_U32((uint32_t)pos, 1000u); }
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

    /* ================= reconciled at DRAFT-4 ===================== */

    /* --- V3-001: the 64-bit run extent. The spec's own repro values. --- */
    {
        static const ent wrap[1] = { { 0u, 131071u, 0xFFFFFFFFu } };
        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, wrap, 1u);
        /* In u32 this wrapped to last == 0 — the most permissive value there is,
           passing every bound including a_high_water. In 64-bit it is 32768,
           past total_chunks, and refused. */
        CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);
    }

    /* --- V3-004: geometry at EXACT equality with the mirror block is refused.
           Named in acceptance.md WP-06. --- */
    {
        uint32_t bc = TAPE_LBA_CHUNK_BASE + CHUNKS * TAPE_CHUNK_BLOCKS; /* end == block_count */
        build_valid();
        MED.block_count = bc;
        med_sb(MED.head[0], CHUNKS, CHUNKS, bc, 1u, TAPE_STATE_VALID);
        memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        CHECK_EQ_INT(mount_a(), TAPE_ERR_GEOMETRY);

        /* One block short is the accepted case — proving the check is an
           off-by-one boundary and not a blanket refusal. */
        build_valid();
        CHECK_EQ_INT(mount_a(), TAPE_OK);
    }

    /* --- the store must EQUAL what the label derives (§2.1, DRAFT-6) ---
           DRAFT-4 asked only that the store COVER the label. Equality closes the
           gap where two cartridges both read "C-60" with different capacities
           and nothing says which is right. Both directions are refused. */
    build_valid();
    wr32(MED.head[0] + 48, med_max_label_s(CHUNKS) + 1u);   /* label too long */
    med_fix_sb_crc(MED.head[0]);
    memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
    CHECK_EQ_INT(mount_a(), TAPE_ERR_GEOMETRY);

    /* A label SHORT enough to derive fewer chunks than the store holds is now
       refused too — that is the half DRAFT-4 accepted. 8 s derives 3 chunks
       against a 4-chunk store. (9, 10 and 11 s all derive 4 and still mount:
       the rule is about the derived count, not the second count.) */
    build_valid();
    wr32(MED.head[0] + 48, 8u);
    med_fix_sb_crc(MED.head[0]);
    memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
    CHECK_EQ_INT(mount_a(), TAPE_ERR_GEOMETRY);

    /* --- §5.3: both slots valid at EQUAL sequence is refused, unconditionally.
           Named in acceptance.md WP-06. My DRAFT-3-era rule accepted this when
           the two were byte-identical; DRAFT-4 does not, and is right — equal
           sequence is unreachable through §8, so it means media fault or an
           implementation bug either way. --- */
    {
        static const ent one[1] = { { 0u, 0u, 100u } };
        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 5u, one, 1u);
        med_index(&MED, TAPE_LBA_INDEX_A1, 0u, 5u, one, 1u);   /* byte-identical */
        CHECK_EQ_INT(mount_a(), TAPE_ERR_INCONSISTENT);
    }

    /* --- §4.1: a version_major = 2 mount with one torn copy WRITES NOTHING.
           Named in acceptance.md WP-06, and the reason the three phases exist:
           repairing unsupported media is how an old reader downgrades new
           media. --- */
    {
        tape_dev dev; tape *t = NULL;
        build_valid();
        MED.writable = 1;                                   /* writable device */
        wr16(MED.head[0] + 8, 2u);                          /* v2 primary */
        med_fix_sb_crc(MED.head[0]);
        memset(MED.mirror, 0, TAPE_BLOCK_SIZE);             /* torn partner */
        MED.writes = 0u; MED.flushes = 0u;
        med_bind(&MED, &dev);
        CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_OK);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_ERR_VERSION);
        CHECK_EQ_U32(MED.writes, 0u);        /* the whole point */
        CHECK_EQ_U32(MED.flushes, 0u);
    }

    /* --- phase 3 DOES repair a v1 cartridge with one torn copy, and does not
           bump sb_generation: repair restores an existing logical state. --- */
    {
        tape_dev dev; tape *t = NULL; tape_info info;
        build_valid();
        MED.writable = 1;
        memset(MED.mirror, 0, TAPE_BLOCK_SIZE);
        MED.writes = 0u;
        med_bind(&MED, &dev);
        CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_OK);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_OK);
        CHECK_EQ_U32(MED.writes, 1u);                        /* the mirror */
        CHECK_MEM_EQ(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        CHECK_EQ_U32(med_rd32(MED.mirror + 12), 1u);        /* generation unchanged */
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.needs_repair);                            /* repaired */
    }

    /* --- and a read-only device is never repaired, only reported --- */
    {
        tape *t = NULL; tape_info info;
        build_valid();
        memset(MED.mirror, 0, TAPE_BLOCK_SIZE);
        MED.writes = 0u;
        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, &t), TAPE_OK);
        CHECK_EQ_U32(MED.writes, 0u);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(info.needs_repair);
    }

    /* --- §5.1: entry ranges must not overlap --- */
    {
        /* Two entries both fully referencing chunk 0. Every other check passes:
           the CRC is right, both runs are in bounds, and total_frames matches
           the sum. §9.3's phase-2 reasoning breaks on exactly this. */
        static const ent dup2[2] = { { 0u, 0u, TAPE_CHUNK_FRAMES },
                                     { 0u, 0u, TAPE_CHUNK_FRAMES } };
        /* Disjoint frame ranges inside one shared chunk: legal, and what a
           splice produces when it splits a run. */
        static const ent split[2] = { { 0u, 0u,    1000u },
                                      { 0u, 1000u, 1000u } };
        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, dup2, 2u);
        CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);

        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, split, 2u);
        CHECK_EQ_INT(mount_a(), TAPE_OK);

        /* The case §5.1's "Equivalently:" aggregate formula does NOT catch:
           two entries covering the same 1000 frames of chunk 0. total_frames is
           2000, the aggregate bound is 131072, so the aggregate passes it —
           while the pairwise rule refuses. Filed as a finding; the pairwise rule
           is what is implemented. */
        {
            static const ent same[2] = { { 0u, 0u, 1000u }, { 0u, 0u, 1000u } };
            build_valid();
            med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, same, 2u);
            CHECK_EQ_INT(mount_a(), TAPE_ERR_NO_VALID_INDEX);
        }
    }

    /* --- Rule 3: Side B may REFERENCE chunks owned by Side A. This is the
           reset-B shape, and DRAFT-3's invariant 4 made it unmountable. --- */
    {
        static const ent low[1] = { { 0u, 0u, 1000u } };
        tape *t = NULL;
        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_B0, 1u, 3u, low, 1u);   /* B -> chunk 0 */
        CHECK_EQ_INT(mount_side(TAPE_SIDE_B, &t), TAPE_OK);
        /* and free_next is not raised by a reference below the mark (§7) */
        {
            tape_info info;
            CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
            CHECK_EQ_U32(info.free_chunks, CHUNKS - MED_A_HIGH_WATER);
        }
    }

    /* --- warm start: validated, and a mismatch disables it rather than failing
           the mount (V3-016) --- */
    {
        static int16_t ring[256];
        tape_warm_start w;
        tape_dev dev; tape *t = NULL; tape_info info;

        build_valid();
        med_bind(&MED, &dev);
        w.data = ring; w.data_bytes = (uint32_t)sizeof ring;
        w.valid_frames = 128u; w.start_frame = 0u;
        w.side = TAPE_SIDE_A;
        memset(w.uuid, 0xAB, 16);                      /* matches the fixture */

        CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_OK);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 10u, &w), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(info.warm_start_used);

        /* wrong cartridge -> ignored, mount still succeeds */
        memset(w.uuid, 0x11, 16);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 10u, &w), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.warm_start_used);

        /* wrong side -> ignored */
        memset(w.uuid, 0xAB, 16);
        w.side = TAPE_SIDE_B;
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 10u, &w), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.warm_start_used);

        /* resume outside the ring's range -> ignored */
        w.side = TAPE_SIDE_A;
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 500u, &w), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.warm_start_used);

        /* no descriptor at all is fine */
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.warm_start_used);
    }

    /* ================= reconciled at DRAFT-6 ===================== */
    /*
     * Eight sub-criteria, acceptance.md WP-06a..WP-06h. Where one needs a call
     * that structural Rule 1 holds off this branch — tape_arm above all — the
     * mount half is exercised and the gap is named rather than skipped quietly.
     */

    /* --- WP-06a: effective writability on v1.1 media (V4-001) --------------
     * The blocker. §4.1 phase 2 declared a version_minor > 0 cartridge
     * read-only, and every write authorisation in the API was defined solely by
     * dev.write != NULL. On a WRITABLE device the matrix therefore still
     * permitted reset_b, promote, respool and arm against v1.1 media — a v1
     * engine committing v1 structures onto media whose newer semantics it does
     * not understand. The barrier was written in one document and enforced in
     * neither.
     */
    {
        tape_dev dev; tape *t = NULL; tape_info info;
        build_valid();
        MED.writable = 1;                       /* a device that CAN write */
        med_sb_minor(MED.head[0], 1u);          /* ...and media it may not */
        memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        memset(MED.mirror, 0, TAPE_BLOCK_SIZE); /* one torn copy: repair is due */
        MED.writes = 0u; MED.flushes = 0u;
        med_bind(&MED, &dev);
        CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_OK);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK_EQ_U32(info.version_minor, 1u);   /* why writable is false */
        CHECK(!info.writable);                  /* effective_writable, §4.3 */
        /* Repair is SKIPPED, not refused: TAPE_OK with needs_repair true. */
        CHECK(info.needs_repair);
        CHECK_EQ_U32(MED.writes, 0u);           /* invariant 23 */
        CHECK_EQ_U32(MED.flushes, 0u);
    }

    /* The converse, so the predicate is a conjunction and not a rename of one
       term: v1.0 on the same writable device IS effectively writable, and does
       repair. */
    {
        tape_dev dev; tape *t = NULL; tape_info info;
        build_valid();
        MED.writable = 1;
        memset(MED.mirror, 0, TAPE_BLOCK_SIZE);
        MED.writes = 0u;
        med_bind(&MED, &dev);
        CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_OK);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(info.writable);
        CHECK_EQ_U32(info.version_minor, 0u);
        CHECK_EQ_U32(MED.writes, 1u);
        CHECK(!info.needs_repair);
    }

    /* --- WP-06b: undefined field values (V4-012) ---------------------------
     * A CRC-correct superblock with state = 2 previously passed admission — the
     * only test was `state == WRITE_IN_PROGRESS` — so damaged or future values
     * FAILED OPEN and the cartridge mounted read-write with its transaction
     * state unknown. Both copies identical, so this is admission and not
     * selection.
     */
    {
        tape_dev dev; tape *t = NULL;
        build_valid();
        MED.writable = 1;
        med_sb_state(MED.head[0], 2u);
        memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        MED.writes = 0u;
        med_bind(&MED, &dev);
        CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_OK);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_ERR_UNSUPPORTED_STATE);
        CHECK_EQ_U32(MED.writes, 0u);
        CHECK_EQ_U32(MED.flushes, 0u);

        /* Same for promote_stage. */
        build_valid();
        MED.writable = 1;
        med_sb_stage(MED.head[0], 2u, 0u);
        memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        MED.writes = 0u;
        med_bind(&MED, &dev);
        CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_OK);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_ERR_UNSUPPORTED_STATE);
        CHECK_EQ_U32(MED.writes, 0u);

        /* 0 and 1 remain the only accepted values, for both fields. Note that
           state = 1 is INCOMPLETE, not UNSUPPORTED_STATE: it is defined, and
           the difference is the whole point of the new code. */
        build_valid();
        med_sb_state(MED.head[0], TAPE_STATE_VALID);
        memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        CHECK_EQ_INT(mount_a(), TAPE_OK);
        build_valid();
        med_sb_state(MED.head[0], TAPE_STATE_WRITE_IN_PROGRESS);
        memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        CHECK_EQ_INT(mount_a(), TAPE_ERR_INCOMPLETE);
    }

    /* --- WP-06c: the disjointness check reads NO chunk ---------------------
     * The overlap cases themselves are above. What is new is the cost claim:
     * §5.1 says the rule is checkable from index metadata alone, and mount is on
     * the wake-to-audio path (guardrail 04), so "no chunk is read" is a budget
     * commitment and not a stylistic note.
     */
    {
        static const ent split[2] = { { 0u, 0u,    1000u },
                                      { 0u, 1000u, 1000u } };
        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, split, 2u);
        MED.chunk_reads = 0u;
        CHECK_EQ_INT(mount_a(), TAPE_OK);
        CHECK_EQ_U32(MED.chunk_reads, 0u);
    }
    /* and a Side B index referencing chunks Side A also references is ACCEPTED
       — required by Rule 3, not merely tolerated; the rule is per index. */
    {
        static const ent shared[1] = { { 0u, 0u, 1000u } };
        tape *t = NULL;
        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_B0, 1u, 3u, shared, 1u);   /* same chunk as A */
        CHECK_EQ_INT(mount_side(TAPE_SIDE_B, &t), TAPE_OK);
    }

    /* --- WP-06d: the fixture builder's own label invariant ------------------
     * Asserted rather than commented, because if med_max_label_s ever stops
     * satisfying the equality rule then every fixture in this file starts
     * failing with TAPE_ERR_GEOMETRY and the cause is the harness, not the
     * engine. A test suite should say which of the two it is.
     */
    CHECK(med_check_label(CHUNKS));

    /* --- WP-06f: both-side mount and degraded-B (§4.2, §4.4, V5-004) -------
     * The dangerous reading DRAFT-5 permitted was "silently treat B as empty" —
     * and promote of an empty B ERASES SIDE A.
     */
    {
        tape *t = NULL; tape_info info;

        /* Side A unselectable fails the mount whichever side was requested. */
        build_valid();
        med_invalidate(&MED, TAPE_LBA_INDEX_A0);
        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, NULL), TAPE_ERR_NO_VALID_INDEX);
        build_valid();
        med_invalidate(&MED, TAPE_LBA_INDEX_A0);
        CHECK_EQ_INT(mount_side(TAPE_SIDE_B, NULL), TAPE_ERR_NO_VALID_INDEX);

        /* Side B unselectable: a Side-B REQUEST is refused... */
        build_valid();
        med_invalidate(&MED, TAPE_LBA_INDEX_B0);
        CHECK_EQ_INT(mount_side(TAPE_SIDE_B, NULL), TAPE_ERR_NO_VALID_INDEX);

        /* ...and a Side-A request mounts DEGRADED-B, with free_next pinned to
           a_high_water because there is no live B index to derive it from. */
        build_valid();
        med_invalidate(&MED, TAPE_LBA_INDEX_B0);
        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, &t), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.side_b_valid);
        /* a_high_water == CHUNKS here, so nothing is free above the mark. */
        CHECK_EQ_U32(info.free_chunks, 0u);

        /* set_side(B) is refused while degraded; set_side(A) is allowed. */
        CHECK_EQ_INT(tape_set_side(t, TAPE_SIDE_B), TAPE_ERR_NO_VALID_INDEX);
        CHECK_EQ_INT(tape_set_side(t, TAPE_SIDE_A), TAPE_OK);
    }

    /* A Side-A mount of a cartridge with a RECORDED Side B derives free_next
       from SIDE B's live index. The failure mode this guards is a respool or
       promote issued from that Side-A mount allocating straight over Side B's
       live chunks (invariant 10). */
    {
        static const ent a1[1] = { { 0u, 0u, 1000u } };
        static const ent b1[1] = { { 1u, 0u, TAPE_CHUNK_FRAMES + 1u } };  /* ends chunk 2 */
        tape *t = NULL; tape_info info;
        build_valid();
        wr32(MED.head[0] + 56, 1u);                 /* a_high_water = 1 */
        med_fix_sb_crc(MED.head[0]);
        memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, a1, 1u);
        med_index(&MED, TAPE_LBA_INDEX_B0, 1u, 3u, b1, 1u);
        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, &t), TAPE_OK);   /* side A mounted */
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(info.side_b_valid);
        /* free_next is 3, from B — not 1, from a_high_water. 4 - 3 = 1 free. */
        CHECK_EQ_U32(info.free_chunks, 1u);
        CHECK_EQ_U32((uint32_t)info.total_frames, 1000u);      /* A's timeline */
    }

    /* --- both sides selected, and neither clobbers the other ---------------
     * Phase 3 selects Side A and then Side B into two buffers, and slot 1 is
     * parsed over slot 0's result in the SAME buffer. The tempting alternative
     * — parse slot 1 into the other side's buffer, which really is free during
     * Side A's selection — silently destroys Side A's already-selected index
     * during Side B's, because by then it is not free at all.
     *
     * Nothing else in this file catches that: §5.3's resting state after every
     * commit is exactly one valid slot, so every other fixture leaves the
     * partner invalid and the second parse never happens. This one gives BOTH
     * Side B slots valid content and then asks what Side A's timeline is.
     */
    {
        static const ent a1[1]   = { { 0u, 0u, 1000u } };
        static const ent b_old[1]= { { 1u, 0u,  100u } };
        static const ent b_new[1]= { { 2u, 0u,  200u } };
        tape *t = NULL; tape_info info;

        build_valid();
        wr32(MED.head[0] + 56, 1u);                 /* a_high_water = 1 */
        med_fix_sb_crc(MED.head[0]);
        memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, a1, 1u);
        med_index(&MED, TAPE_LBA_INDEX_B0, 1u, 3u, b_old, 1u);
        med_index(&MED, TAPE_LBA_INDEX_B1, 1u, 9u, b_new, 1u);   /* both valid */

        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, &t), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK_EQ_U32((uint32_t)info.total_frames, 1000u);   /* SIDE A, intact */
        CHECK_EQ_U32(info.entry_count, 1u);
        /* B's higher sequence won, and free_next comes from it: chunk 2 is B's
           last, so free_next is 3 and one chunk of four is free. */
        CHECK(info.side_b_valid);
        CHECK_EQ_U32(info.free_chunks, 1u);

        /* And the same the other way round: mount B, Side A must still be
           selectable and correct on a switch. */
        CHECK_EQ_INT(mount_side(TAPE_SIDE_B, &t), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK_EQ_U32((uint32_t)info.total_frames, 200u);    /* B, higher sequence */
        CHECK_EQ_INT(tape_set_side(t, TAPE_SIDE_A), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK_EQ_U32((uint32_t)info.total_frames, 1000u);
    }

    /* The slot-0-wins path, which is the one that costs a reload. Both slots
       valid, slot 0 higher: the engine must end up holding slot 0's entries and
       not slot 1's, which is only true if the reload actually happened. */
    {
        static const ent hi[1] = { { 0u, 0u, 700u } };
        static const ent lo[1] = { { 0u, 0u, 300u } };
        tape *t = NULL; tape_info info;
        build_valid();
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 9u, hi, 1u);   /* slot 0, higher */
        med_index(&MED, TAPE_LBA_INDEX_A1, 0u, 5u, lo, 1u);
        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, &t), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK_EQ_U32((uint32_t)info.total_frames, 700u);
    }

    /* --- WP-06g: a failing mount writes NOTHING, and the stage oracle -------
     * (V5-003.) Invariant 25 and WP-10 both required a mount to reject stage-1
     * media matching no resume row, and the mount algorithm never performed the
     * check — only a later tape_promote did. Worse: §8's stage clearing would
     * have ERASED THE EVIDENCE, because an ordinary tape_arm clears
     * promote_stage before anything reported the fault.
     *
     * All of these run on a WRITABLE device with one torn superblock copy, so
     * repair is due and would happen if phase 4 ran before phase 3. Every one
     * asserts zero writes. That is the assertion DRAFT-5 could not satisfy.
     */
    {
        tape_dev dev; tape *t = NULL;
        /* N = 1000 frames -> len = 1 chunk. */
        static const ent at0[1] = { { 0u, 0u, 1000u } };
        static const ent at1[1] = { { 1u, 0u, 1000u } };
        static const ent at2[1] = { { 2u, 0u, 1000u } };
        static const ent at1_big[1] = { { 1u, 0u, 2000u } };
        static const ent two[2] = { { 0u, 0u, 1000u }, { 2u, 0u, 1000u } };
        unsigned k;

        /* stage_media: a_high_water = H, promote_stage = 1, staging chunk = S,
           Side A from `ea`, Side B from `eb`. */
#define STAGE_MEDIA(H, S, ea, na, eb, nb)                                      \
        do {                                                                   \
            build_valid();                                                     \
            MED.writable = 1;                                                  \
            wr32(MED.head[0] + 56, (H));                                       \
            med_sb_stage(MED.head[0], TAPE_PROMOTE_STAGE_PHASE1, (S));         \
            memset(MED.mirror, 0, TAPE_BLOCK_SIZE);   /* torn: repair is due */\
            med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, (ea), (na));            \
            med_index(&MED, TAPE_LBA_INDEX_B0, 1u, 2u, (eb), (nb));            \
            MED.writes = 0u; MED.flushes = 0u;                                 \
            med_bind(&MED, &dev);                                              \
            CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY, \
                                   REC, sizeof REC, &t), TAPE_OK);             \
        } while (0)

        /* Row 1 — phase 1 landed, phase 2 not committed. A = {S,0,N}, B == A. */
        STAGE_MEDIA(2u, 1u, at1, 1u, at1, 1u);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_OK);

        /* Row 2 — phase 2 committed A only. A = {0,0,N}, B = {S,0,N}, S > 0. */
        STAGE_MEDIA(2u, 1u, at0, 1u, at1, 1u);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_OK);

        /* Row 3 — phase 2 committed both. A = {0,0,N}, B == A, S > 0, H > len. */
        STAGE_MEDIA(2u, 1u, at0, 1u, at0, 1u);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_OK);

        /*
         * The S == 0 partition case, called out by §9.3.3 by name. It is the
         * ORDINARY FIRST-USE PATH: format leaves a_high_water = 0, the first
         * Side B recording allocates from free_next = 0 giving {0,0,N}, and
         * adopt-in-place makes S = 0. Without the `S > 0` guards on rows 2 and
         * 3 this matched more than one row, falsifying invariant 25.
         *
         * It must mount, and it must mount by row 1 alone.
         */
        STAGE_MEDIA(2u, 0u, at0, 1u, at0, 1u);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_OK);

        /* Four crafted cases that match NO row. Each must return
           TAPE_ERR_INCONSISTENT having written nothing at all. */
        {
            /* (a) A at a chunk that is neither S nor 0. */
            STAGE_MEDIA(3u, 1u, at2, 1u, at2, 1u);
            CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_ERR_INCONSISTENT);
            CHECK_EQ_U32(MED.writes, 0u); CHECK_EQ_U32(MED.flushes, 0u);

            /* (b) Row 2's shape but N differs between the sides. */
            STAGE_MEDIA(2u, 1u, at0, 1u, at1_big, 1u);
            CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_ERR_INCONSISTENT);
            CHECK_EQ_U32(MED.writes, 0u);

            /* (c) Row 3's shape but H == len, so the H > len guard bites. */
            STAGE_MEDIA(1u, 1u, at0, 1u, at0, 1u);
            CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_ERR_INCONSISTENT);
            CHECK_EQ_U32(MED.writes, 0u);

            /* (d) Side A with two entries — no row admits a multi-entry A. */
            STAGE_MEDIA(3u, 1u, two, 2u, two, 2u);
            CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_ERR_INCONSISTENT);
            CHECK_EQ_U32(MED.writes, 0u);
        }

        /*
         * A cartridge that is BOTH stage-1 and degraded-B must MOUNT. DRAFT-6's
         * own first cut ran the oracle before the degraded-B branch, and since
         * every row constrains a live Side B index, this returned
         * TAPE_ERR_INCONSISTENT — permanently unmountable, with the whole of
         * Side A's music unreachable forever on a cartridge whose Side A was
         * intact. tape_reset_side_b is the only recovery and it needs a
         * successful mount.
         */
        STAGE_MEDIA(3u, 1u, at2, 1u, at2, 1u);   /* a shape matching NO row */
        med_invalidate(&MED, TAPE_LBA_INDEX_B0); /* ...and no live B at all */
        MED.writes = 0u;
        {
            tape_info info;
            CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_OK);
            CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
            CHECK(!info.side_b_valid);
        }

        /*
         * The general assertion behind all of the above (invariant 26): across
         * every refusal, on a writable device with a repair pending, mount
         * writes nothing. Phase 4 is the only phase that writes and it runs
         * after phases 2 AND 3.
         */
        for (k = 0; k < 6u; k++) {
            tape_result want = TAPE_OK;
            build_valid();
            MED.writable = 1;
            switch (k) {
            case 0: wr16(MED.head[0] + 8, 2u); med_fix_sb_crc(MED.head[0]);
                    want = TAPE_ERR_VERSION; break;
            case 1: med_sb_state(MED.head[0], 2u);
                    want = TAPE_ERR_UNSUPPORTED_STATE; break;
            case 2: med_sb_state(MED.head[0], TAPE_STATE_WRITE_IN_PROGRESS);
                    want = TAPE_ERR_INCOMPLETE; break;
            case 3: wr32(MED.head[0] + 52, 0u); med_fix_sb_crc(MED.head[0]);
                    want = TAPE_ERR_GEOMETRY; break;
            case 4: med_invalidate(&MED, TAPE_LBA_INDEX_A0);
                    want = TAPE_ERR_NO_VALID_INDEX; break;
            default: {
                    static const ent one[1] = { { 0u, 0u, 100u } };
                    med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 5u, one, 1u);
                    med_index(&MED, TAPE_LBA_INDEX_A1, 0u, 5u, one, 1u);
                    want = TAPE_ERR_INCONSISTENT; break;
                }
            }
            /* Tear the mirror in every case, so repair is genuinely pending. */
            memset(MED.mirror, 0, TAPE_BLOCK_SIZE);
            MED.writes = 0u; MED.flushes = 0u;
            med_bind(&MED, &dev);
            CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY,
                                   REC, sizeof REC, &t), TAPE_OK);
            CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), want);
            CHECK_EQ_U32(MED.writes, 0u);
            CHECK_EQ_U32(MED.flushes, 0u);
        }
#undef STAGE_MEDIA
    }

    /* --- WP-06h: the Not-mounted contract (V5-009) -------------------------
     * §10's Not-mounted row, which no work package previously exercised. The
     * old bare-uint64_t tape_tell had no error channel at all, so an
     * implementation had to invent a sentinel.
     */
    {
        tape_dev dev; tape *t = NULL; tape_info info;
        uint64_t pos = 0x5A5Au;
        build_valid();
        med_bind(&MED, &dev);
        CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_OK);

        /* Before any mount. */
        CHECK_EQ_INT(tape_tell(t, &pos), TAPE_ERR_NOT_MOUNTED);
        CHECK_EQ_U32((uint32_t)pos, 0x5A5Au);        /* left untouched */
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_ERR_NOT_MOUNTED);
        CHECK_EQ_INT(tape_set_side(t, TAPE_SIDE_A), TAPE_ERR_NOT_MOUNTED);
        CHECK_EQ_INT(tape_unmount(t, NULL), TAPE_ERR_NOT_MOUNTED);

        /* And after unmount. */
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 0u, NULL), TAPE_OK);
        CHECK_EQ_INT(tape_unmount(t, NULL), TAPE_OK);
        pos = 0x5A5Au;
        CHECK_EQ_INT(tape_tell(t, &pos), TAPE_ERR_NOT_MOUNTED);
        CHECK_EQ_U32((uint32_t)pos, 0x5A5Au);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_ERR_NOT_MOUNTED);
        CHECK_EQ_INT(tape_set_side(t, TAPE_SIDE_A), TAPE_ERR_NOT_MOUNTED);

        /* A null out-parameter is an argument error, not a crash. */
        CHECK_EQ_INT(tape_tell(t, NULL), TAPE_ERR_INVALID_ARG);
        CHECK_EQ_INT(tape_tell(NULL, &pos), TAPE_ERR_INVALID_ARG);
    }

    /* --- V5-013: the side-switch transition is normative -------------------
     * DRAFT-5 said only "commits nothing and discards nothing", leaving
     * position, the endpoint flags and the ring undefined across a switch. The
     * stale ring is the one that hurts: it plays audio from the OTHER SIDE for
     * up to 372 ms. Position resets to 0 because that is what flipping a tape
     * over does; the bookmark is the caller's (§11, Principle 1).
     */
    {
        static const ent a1[1] = { { 0u, 0u, 1000u } };
        static const ent b1[1] = { { 1u, 0u, 100u } };
        tape *t = NULL; tape_info info; uint64_t pos;
        build_valid();
        wr32(MED.head[0] + 56, 1u);                 /* a_high_water = 1 */
        med_fix_sb_crc(MED.head[0]);
        memcpy(MED.mirror, MED.head[0], TAPE_BLOCK_SIZE);
        med_index(&MED, TAPE_LBA_INDEX_A0, 0u, 1u, a1, 1u);
        med_index(&MED, TAPE_LBA_INDEX_B0, 1u, 3u, b1, 1u);
        CHECK_EQ_INT(mount_side(TAPE_SIDE_A, &t), TAPE_OK);
        /* Mount at frame 500 of a 1000-frame Side A. */
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 500u, NULL), TAPE_OK);
        pos = 0; CHECK_EQ_INT(tape_tell(t, &pos), TAPE_OK);
        CHECK_EQ_U32((uint32_t)pos, 500u);

        CHECK_EQ_INT(tape_set_side(t, TAPE_SIDE_B), TAPE_OK);
        pos = 0xFFFFu; CHECK_EQ_INT(tape_tell(t, &pos), TAPE_OK);
        CHECK_EQ_U32((uint32_t)pos, 0u);                   /* position resets */
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.warm_start_used);                      /* and warm start drops */
        CHECK_EQ_U32((uint32_t)info.total_frames, 100u);   /* B's timeline now */
        CHECK_EQ_U32(info.entry_count, 1u);

        /* And back, without a commit and without a discard. */
        CHECK_EQ_INT(tape_set_side(t, TAPE_SIDE_A), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK_EQ_U32((uint32_t)info.total_frames, 1000u);
        pos = 0xFFFFu; CHECK_EQ_INT(tape_tell(t, &pos), TAPE_OK);
        CHECK_EQ_U32((uint32_t)pos, 0u);
    }

    /* --- V5-007 / V4-011: the warm-start algorithm is ORDERED --------------
     * DRAFT-5 wrote it as an unordered predicate list that BEGAN by computing an
     * end frame from warm->start_frame, while the API expressly permits
     * warm == NULL — the ordinary cold mount. Read as written it dereferenced a
     * null pointer on every cold boot. And `data` was never checked, so a
     * descriptor with correct metadata and data == NULL sent the renderer to
     * address zero.
     */
    {
        static int16_t ring[256];
        tape_warm_start w;
        tape_dev dev; tape *t = NULL; tape_info info;

        build_valid();
        med_bind(&MED, &dev);
        CHECK_EQ_INT(tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY,
                               REC, sizeof REC, &t), TAPE_OK);

        /* The two pointer cases. Both must cold-mount cleanly. */
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 10u, NULL), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.warm_start_used);

        w.data = NULL; w.data_bytes = (uint32_t)sizeof ring;
        w.valid_frames = 128u; w.start_frame = 0u; w.side = TAPE_SIDE_A;
        memset(w.uuid, 0xAB, 16);
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 10u, &w), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.warm_start_used);

        /* data_bytes one byte short of valid_frames * 4 — the caller's buffer
           dimensions, which the engine no longer takes on trust. */
        w.data = ring;
        w.data_bytes = 128u * TAPE_FRAME_BYTES - 1u;
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 10u, &w), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.warm_start_used);

        /* Exactly enough is accepted: the boundary is >=, not >. */
        w.data_bytes = 128u * TAPE_FRAME_BYTES;
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 10u, &w), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(info.warm_start_used);

        /* valid_frames == 0. */
        w.valid_frames = 0u;
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 10u, &w), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.warm_start_used);

        /*
         * start_frame near UINT32_MAX with non-zero valid_frames. In u32
         * start_frame + valid_frames WRAPS, so a stale ring is accepted for a
         * range it does not cover — WP-11's seventh mutation, admitted by the
         * spec that defines the mutation (V4-011). resume_frame 10 sits inside
         * the wrapped range [4294967291, 4) and outside the real one.
         */
        w.data = ring; w.data_bytes = (uint32_t)sizeof ring;
        w.valid_frames = 8u; w.start_frame = 0xFFFFFFFBu;
        CHECK_EQ_INT(tape_mount(t, TAPE_SIDE_A, 10u, &w), TAPE_OK);
        CHECK_EQ_INT(tape_get_info(t, &info), TAPE_OK);
        CHECK(!info.warm_start_used);
    }

    return TAPE_TEST_REPORT("mount read path");
}
