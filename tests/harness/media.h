/*
 * media.h — build synthetic TAPEFS media in memory.
 *
 * Scaffolding. Lets a test construct a byte-exact valid cartridge and then break
 * exactly one thing, which is what testing a refusal path requires: if the
 * fixture is wrong in two ways you cannot tell which one the engine caught.
 *
 * Sparse on purpose — only the head blocks and the mirror are stored, because a
 * real C-60 image is 635 MB and the mount path never reads a chunk.
 */

#ifndef TAPE_TEST_MEDIA_H
#define TAPE_TEST_MEDIA_H

#include <string.h>
#include "tape.h"
#include "tape_crc32.h"
#include "port.h"

#define MED_HEAD_BLOCKS 600u          /* superblock + all four index slots */

/* One index entry, as a test states it. Mirrors spec §5.1. */
struct med_ent { uint32_t first, start, count; };

struct media {
    unsigned char head[MED_HEAD_BLOCKS][TAPE_BLOCK_SIZE];
    unsigned char mirror[TAPE_BLOCK_SIZE];
    uint32_t block_count;
    int      writable;
    uint32_t reads;
    uint32_t chunk_reads; /* reads at or above LBA_CHUNK_BASE. WP-06c asserts the
                             disjointness check reads NO chunk during mount */
    uint32_t writes;      /* so a test can assert "writes nothing" */
    uint32_t flushes;
};

static void wr32(unsigned char *p, uint32_t v)
{
    p[0]=(unsigned char)(v); p[1]=(unsigned char)(v>>8);
    p[2]=(unsigned char)(v>>16); p[3]=(unsigned char)(v>>24);
}
static void wr16(unsigned char *p, uint16_t v)
{
    p[0]=(unsigned char)(v); p[1]=(unsigned char)(v>>8);
}
static void wr64(unsigned char *p, uint64_t v)
{
    wr32(p, (uint32_t)(v & 0xFFFFFFFFu)); wr32(p + 4, (uint32_t)(v >> 32));
}

static int med_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    struct media *m = (struct media *)ctx;
    unsigned char *d = (unsigned char *)dst;
    uint32_t i;

    m->reads++;
    /* The chunk REGION only. The superblock mirror sits at block_count-1, which
       is above LBA_CHUNK_BASE and is emphatically not a chunk — counting it
       would make WP-06c's "reads no chunk" assertion fail on every mount, for
       the wrong reason. */
    if (lba >= TAPE_LBA_CHUNK_BASE) {
        uint32_t i2, last = m->block_count - 1u;
        for (i2 = 0; i2 < count; i2++) {
            if (lba + i2 < last) { m->chunk_reads++; }
        }
    }
    if (lba > m->block_count || count > m->block_count - lba) {
        return TAPE_DEV_ERR_RANGE;
    }
    for (i = 0; i < count; i++) {
        uint32_t b = lba + i;
        if (b == m->block_count - 1u) {
            memcpy(d + (size_t)i * TAPE_BLOCK_SIZE, m->mirror, TAPE_BLOCK_SIZE);
        } else if (b < MED_HEAD_BLOCKS) {
            memcpy(d + (size_t)i * TAPE_BLOCK_SIZE, m->head[b], TAPE_BLOCK_SIZE);
        } else {
            memset(d + (size_t)i * TAPE_BLOCK_SIZE, 0, TAPE_BLOCK_SIZE);
        }
    }
    return TAPE_DEV_OK;
}
static int med_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    struct media *m = (struct media *)ctx;
    const unsigned char *sp = (const unsigned char *)src;
    uint32_t i;

    m->writes += count;
    if (lba > m->block_count || count > m->block_count - lba) {
        return TAPE_DEV_ERR_RANGE;
    }
    for (i = 0; i < count; i++) {
        uint32_t b = lba + i;
        if (b == m->block_count - 1u) {
            memcpy(m->mirror, sp + (size_t)i * TAPE_BLOCK_SIZE, TAPE_BLOCK_SIZE);
        } else if (b < MED_HEAD_BLOCKS) {
            memcpy(m->head[b], sp + (size_t)i * TAPE_BLOCK_SIZE, TAPE_BLOCK_SIZE);
        }
    }
    return TAPE_DEV_OK;
}
static int med_flush(void *ctx)
{
    struct media *m = (struct media *)ctx;
    m->flushes++;
    return TAPE_DEV_OK;
}

static void med_bind(struct media *m, tape_dev *dev)
{
    dev->read  = med_read;
    dev->write = m->writable ? med_write : NULL;   /* guardrail 06 */
    dev->flush = med_flush;
    dev->ctx   = m;
    dev->block_count = m->block_count;
}

/* Write a superblock into `blk`, then fix its CRC. */
/*
 * DRAFT-4 §4.1 phase 2 requires total_chunks >= ceil(nominal_length_s * 44100 /
 * CHUNK_FRAMES) — the store must cover the label. Test media is deliberately
 * tiny, so the label has to be tiny too: with 4 chunks the largest honest label
 * is 11 s. A fixture claiming C-60 on 4 chunks is now correctly refused, which
 * is the check working.
 */
/* Little-endian read, so a test can inspect what the engine wrote back. */
static uint32_t med_rd32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/*
 * The largest label this store honestly carries.
 *
 * DRAFT-6 §4.1 phase 2 step 5 requires the stored total_chunks to EQUAL the
 * value GEOMETRY_OK derives from nominal_length_s, not merely to cover it. The
 * floor below satisfies that exactly, and not by luck: with
 * L = floor(tc * CHUNK_FRAMES / SAMPLE_RATE), the derived
 * ceil(L * SAMPLE_RATE / CHUNK_FRAMES) is <= tc because L <= tc*CF/SR, and
 * >= tc because L > tc*CF/SR - 1 gives L*SR/CF > tc - SR/CF > tc - 1. So it is
 * exactly tc. med_check_label() asserts it rather than leaving that as a
 * comment, because a fixture that is wrong in two ways tells you nothing about
 * which one the engine caught.
 */
static uint32_t med_max_label_s(uint32_t total_chunks)
{
    return (uint32_t)(((uint64_t)total_chunks * TAPE_CHUNK_FRAMES) / TAPE_SAMPLE_RATE);
}

static int med_check_label(uint32_t total_chunks)
{
    uint32_t L = med_max_label_s(total_chunks);
    uint64_t derived = ((uint64_t)L * TAPE_SAMPLE_RATE + TAPE_CHUNK_FRAMES - 1u)
                     / TAPE_CHUNK_FRAMES;
    return L > 0u && derived == (uint64_t)total_chunks;
}

static void med_sb(unsigned char *blk, uint32_t total_chunks, uint32_t a_high_water,
                   uint32_t block_count, uint32_t generation, uint8_t state)
{
    static const unsigned char magic[8] =
        { 0x54,0x41,0x50,0x45,0x46,0x53,0x00,0x01 };
    memset(blk, 0, TAPE_BLOCK_SIZE);
    memcpy(blk, magic, 8);
    wr16(blk + 8, 1); wr16(blk + 10, 0);        /* version 1.0 */
    wr32(blk + 12, generation);
    blk[16] = state;
    memset(blk + 20, 0xAB, 16);                  /* uuid */
    wr32(blk + 36, TAPE_SAMPLE_RATE);
    wr16(blk + 40, TAPE_CHANNELS);
    wr16(blk + 42, 16);
    wr32(blk + 44, TAPE_CHUNK_BYTES);
    wr32(blk + 48, med_max_label_s(total_chunks));  /* honest label for this store */
    wr32(blk + 52, total_chunks);
    wr32(blk + 56, a_high_water);
    wr32(blk + 60, TAPE_INDEX_SLOT_BYTES);
    wr32(blk + 64, TAPE_LBA_INDEX_A0);
    wr32(blk + 68, TAPE_LBA_INDEX_A1);
    wr32(blk + 72, TAPE_LBA_INDEX_B0);
    wr32(blk + 76, TAPE_LBA_INDEX_B1);
    wr32(blk + 80, TAPE_LBA_CHUNK_BASE);
    wr32(blk + 84, block_count - 1u);
    memcpy(blk + 88, "TEST CARTRIDGE", 14);
    wr32(blk + 120, 1756800000u);
    wr32(blk + 508, tape_crc32(blk, 508));
}

static void med_fix_sb_crc(unsigned char *blk)
{
    wr32(blk + 508, tape_crc32(blk, 508));
}

/* Write an index slot: header at `lba`, entries from block lba+1. */
static void med_index(struct media *m, uint32_t lba, uint8_t side, uint32_t sequence,
                      const struct med_ent *ents, uint32_t n)
{
    static const unsigned char magic[8] =
        { 0x54,0x41,0x50,0x45,0x49,0x44,0x58,0x01 };
    unsigned char *hdr = m->head[lba];
    unsigned char *ea  = m->head[lba + 1u];
    uint64_t total = 0;
    uint32_t i, crc;

    memset(hdr, 0, TAPE_BLOCK_SIZE);
    memset(ea, 0, TAPE_BLOCK_SIZE * 4u);
    memcpy(hdr, magic, 8);
    wr32(hdr + 8, sequence);
    hdr[12] = side;
    wr32(hdr + 16, n);
    for (i = 0; i < n; i++) {
        wr32(ea + i * 12u,      ents[i].first);
        wr32(ea + i * 12u + 4u, ents[i].start);
        wr32(ea + i * 12u + 8u, ents[i].count);
        total += ents[i].count;
    }
    wr64(hdr + 20, total);
    crc = tape_crc32_init();
    crc = tape_crc32_update(crc, hdr, 60u);
    crc = tape_crc32_update(crc, ea, (size_t)n * 12u);
    wr32(hdr + 60, tape_crc32_final(crc));
}

static void med_invalidate(struct media *m, uint32_t lba)
{
    memset(m->head[lba], 0, TAPE_BLOCK_SIZE);
}

/* --- DRAFT-6 superblock fields, set after med_sb and before the CRC fix ------ */

/* §4 offsets 124 and 128. `stage` is deliberately a raw uint32 so a fixture can
   plant an UNDEFINED value (WP-06b) as easily as a defined one. */
static void med_sb_stage(unsigned char *blk, uint32_t stage, uint32_t staging_chunk)
{
    wr32(blk + 124, stage);
    wr32(blk + 128, staging_chunk);
    med_fix_sb_crc(blk);
}

/* §4 offset 10. version_minor > 0 makes the mount not effectively writable
   (§4.3) on a device that can write perfectly well — WP-06a. */
static void med_sb_minor(unsigned char *blk, uint16_t minor)
{
    wr16(blk + 10, minor);
    med_fix_sb_crc(blk);
}

/* §4 offset 16, raw, so a fixture can plant state = 2 (WP-06b). */
static void med_sb_state(unsigned char *blk, uint8_t state)
{
    blk[16] = state;
    med_fix_sb_crc(blk);
}

#endif /* TAPE_TEST_MEDIA_H */
