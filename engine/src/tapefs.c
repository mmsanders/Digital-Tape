/*
 * tapefs.c — on-media parsing and validation.
 * Normative: spec/tapefs-v1.md DRAFT-3 §4, §4.1, §5, §5.2, §7.
 *
 * Everything here is pure: it takes bytes and produces structures or refusals.
 * No device access, so it is trivially testable against synthetic media.
 *
 * ============================================================================
 *  PROVISIONAL — DO NOT EXTEND THESE RULES UNTIL DRAFT-4  (PM Decisions 004 §5)
 * ============================================================================
 *
 * Five verifier findings against DRAFT-3 land directly on this file. Two are
 * blockers and both are CONFIRMED present in this code, with the spec's own
 * repro values:
 *
 *   V3-001  blocker  tape_entry_last_chunk() computes in u32 and wraps before
 *                    any bounds test. Confirmed: first=0, start_frame=131071,
 *                    frame_count=0xFFFFFFFF gives last_chunk_id == 0, when the
 *                    true value is 32768. Zero is the MOST permissive result
 *                    possible -- it passes the `last < first` guard below and
 *                    every bound including a_high_water. A CRC-correct index
 *                    claiming a 4-billion-frame run validates as a single chunk
 *                    at position 0. On Side A this defeats immutability.
 *                    Fix needs checked 64-bit intermediates; DRAFT-4 defines it.
 *
 *   V3-004  blocker  The geometry inequality accepts equality, so the last
 *                    chunk's final block can BE the mirror superblock.
 *                    Confirmed: block_count 6144, chunk store ends at 6144,
 *                    mirror at 6143 -- and tape_sb_check_geometry accepts it.
 *                    Filling that chunk overwrites the mirror; a superblock
 *                    update overwrites referenced audio.
 *
 *   V3-005  major    DRAFT-3 has NO normative index-slot selection algorithm.
 *                    What pick_live_index() does in mount.c was invented here.
 *
 *   V3-006  major    §4.1 orders repair before the version check while also
 *                    forbidding any touch of unsupported media. This code
 *                    encodes one of two incompatible orders.
 *
 *   V3-009  major    Engine invariant 4 contradicts tape_reset_side_b, which
 *                    aliases Side A chunks below a_high_water by design.
 *
 * These are NOT fixed here on purpose. The spec is upstream of the code
 * (contract 1): DRAFT-4 changes the rules, and guessing the fix now would mean
 * implementing a rule that is not normative and may differ. The bugs are real
 * and the exposure is bounded -- nothing writes to media yet.
 */

#include <string.h>
#include "tape_internal.h"
#include "tape_crc32.h"

uint16_t tape_rd16(const unsigned char *p)
{
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

uint32_t tape_rd32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

uint64_t tape_rd64(const unsigned char *p)
{
    return (uint64_t)tape_rd32(p) | ((uint64_t)tape_rd32(p + 4) << 32);
}

uint32_t tape_entry_last_chunk(const struct tape_entry *e)
{
    /* PROVISIONAL — V3-001 blocker. This is DRAFT-3 §5.1 transcribed directly,
       and the direct transcription is the bug: every operand is u32, so the
       expression wraps before any caller can test it. Left as written because
       the spec is upstream of the code and DRAFT-4 defines the widening rule.
       spec §5.1. frame_count >= 1 is a validity precondition, so the -1 cannot
       underflow on a valid entry; callers check frame_count first. */
    return e->first_chunk_id
         + (e->start_frame + e->frame_count - 1u) / TAPE_CHUNK_FRAMES;
}

static const unsigned char SB_MAGIC[8] = {
    0x54, 0x41, 0x50, 0x45, 0x46, 0x53, 0x00, 0x01   /* "TAPEFS\0\x01" */
};
static const unsigned char IDX_MAGIC[8] = {
    0x54, 0x41, 0x50, 0x45, 0x49, 0x44, 0x58, 0x01   /* "TAPEIDX\x01" */
};

tape_result tape_sb_parse(const unsigned char *blk, struct tape_sb *out)
{
    if (memcmp(blk, SB_MAGIC, sizeof SB_MAGIC) != 0) {
        return TAPE_ERR_BAD_MAGIC;
    }
    if (tape_crc32(blk, 508u) != tape_rd32(blk + 508)) {
        return TAPE_ERR_CRC;
    }

    out->version_major        = tape_rd16(blk + 8);
    out->version_minor        = tape_rd16(blk + 10);
    out->sb_generation        = tape_rd32(blk + 12);
    out->state                = blk[16];
    memcpy(out->cartridge_uuid, blk + 20, 16);
    out->sample_rate          = tape_rd32(blk + 36);
    out->channels             = tape_rd16(blk + 40);
    out->bits_per_sample      = tape_rd16(blk + 42);
    out->chunk_bytes          = tape_rd32(blk + 44);
    out->nominal_length_s     = tape_rd32(blk + 48);
    out->total_chunks         = tape_rd32(blk + 52);
    out->a_high_water         = tape_rd32(blk + 56);
    out->index_slot_bytes     = tape_rd32(blk + 60);
    out->lba_index_a0         = tape_rd32(blk + 64);
    out->lba_index_a1         = tape_rd32(blk + 68);
    out->lba_index_b0         = tape_rd32(blk + 72);
    out->lba_index_b1         = tape_rd32(blk + 76);
    out->lba_chunk_base       = tape_rd32(blk + 80);
    out->lba_superblock_mirror= tape_rd32(blk + 84);
    memcpy(out->label, blk + 88, 32);
    out->label[32] = '\0';
    out->format_epoch         = tape_rd32(blk + 120);
    return TAPE_OK;
}

tape_result tape_sb_check_geometry(const struct tape_sb *sb, uint32_t block_count)
{
    uint64_t chunk_end;

    /* Fixed constants, spec §1. */
    if (sb->sample_rate      != TAPE_SAMPLE_RATE)      { return TAPE_ERR_GEOMETRY; }
    if (sb->channels         != TAPE_CHANNELS)         { return TAPE_ERR_GEOMETRY; }
    if (sb->bits_per_sample  != 16u)                   { return TAPE_ERR_GEOMETRY; }
    if (sb->chunk_bytes      != TAPE_CHUNK_BYTES)      { return TAPE_ERR_GEOMETRY; }
    if (sb->index_slot_bytes != TAPE_INDEX_SLOT_BYTES) { return TAPE_ERR_GEOMETRY; }

    /* Fixed region LBAs, spec §3. */
    if (sb->lba_index_a0   != TAPE_LBA_INDEX_A0)   { return TAPE_ERR_GEOMETRY; }
    if (sb->lba_index_a1   != TAPE_LBA_INDEX_A1)   { return TAPE_ERR_GEOMETRY; }
    if (sb->lba_index_b0   != TAPE_LBA_INDEX_B0)   { return TAPE_ERR_GEOMETRY; }
    if (sb->lba_index_b1   != TAPE_LBA_INDEX_B1)   { return TAPE_ERR_GEOMETRY; }
    if (sb->lba_chunk_base != TAPE_LBA_CHUNK_BASE) { return TAPE_ERR_GEOMETRY; }

    /* The caller's block_count is untrusted; these checks defend against it as
       much as against the card (spec §4.1, issue #14 candidate 5). */
    if (block_count == 0u)                                  { return TAPE_ERR_GEOMETRY; }
    if (sb->lba_superblock_mirror != block_count - 1u)      { return TAPE_ERR_GEOMETRY; }
    if (sb->total_chunks < 1u)                              { return TAPE_ERR_GEOMETRY; }
    if (sb->a_high_water > sb->total_chunks)                { return TAPE_ERR_GEOMETRY; }

    /* 64-bit, so a large total_chunks cannot wrap into a passing value.
       PROVISIONAL — V3-004 blocker: `>` accepts equality, and at equality the
       last chunk's final block IS the mirror superblock at block_count - 1.
       The verifier's fix is `<= block_count - 1` with a prior
       `block_count > lba_chunk_base` check. Not applied here: DRAFT-4 owns the
       inequality, and changing it now would move the refusal tests off-spec. */
    chunk_end = (uint64_t)sb->lba_chunk_base
              + (uint64_t)sb->total_chunks * (uint64_t)TAPE_CHUNK_BLOCKS;
    if (chunk_end > (uint64_t)block_count)                  { return TAPE_ERR_GEOMETRY; }

    return TAPE_OK;
}

tape_result tape_index_parse(const unsigned char *hdr, const unsigned char *entries,
                             uint8_t side, const struct tape_sb *sb,
                             struct tape_index *out)
{
    uint32_t i, count;
    uint64_t sum = 0;
    uint32_t crc;

    if (memcmp(hdr, IDX_MAGIC, sizeof IDX_MAGIC) != 0) {
        return TAPE_ERR_BAD_MAGIC;
    }
    if (hdr[12] != side) {
        return TAPE_ERR_NO_VALID_INDEX;
    }

    count = tape_rd32(hdr + 16);
    if (count > TAPE_MAX_ENTRIES) {
        return TAPE_ERR_NO_VALID_INDEX;
    }

    /* spec §5: CRC is over bytes 0…59 concatenated with the entry array. Bytes
       beyond the live entries are undefined and NOT covered. */
    crc = tape_crc32_init();
    crc = tape_crc32_update(crc, hdr, 60u);
    crc = tape_crc32_update(crc, entries, (size_t)count * TAPE_INDEX_ENTRY_BYTES);
    if (tape_crc32_final(crc) != tape_rd32(hdr + 60)) {
        return TAPE_ERR_CRC;
    }

    out->sequence     = tape_rd32(hdr + 8);
    out->side         = side;
    out->entry_count  = count;
    out->total_frames = tape_rd64(hdr + 20);

    for (i = 0; i < count; i++) {
        const unsigned char *e = entries + (size_t)i * TAPE_INDEX_ENTRY_BYTES;
        uint32_t last;

        out->entries[i].first_chunk_id = tape_rd32(e);
        out->entries[i].start_frame    = tape_rd32(e + 4);
        out->entries[i].frame_count    = tape_rd32(e + 8);

        if (out->entries[i].frame_count < 1u)                  { return TAPE_ERR_NO_VALID_INDEX; }
        if (out->entries[i].start_frame >= TAPE_CHUNK_FRAMES)  { return TAPE_ERR_NO_VALID_INDEX; }

        last = tape_entry_last_chunk(&out->entries[i]);
        if (last < out->entries[i].first_chunk_id)             { return TAPE_ERR_NO_VALID_INDEX; }
        if (last >= sb->total_chunks)                          { return TAPE_ERR_NO_VALID_INDEX; }

        /* spec §5.2: for Side A the bound is the LAST chunk of each run, not the
           first. This is the check that keeps the sandbox out of the music, and
           an off-by-one at the end of a run is exactly how it would fail.
           PROVISIONAL — V3-001 defeats this check via the u32 wrap above. */
        if (side == (uint8_t)TAPE_SIDE_A && last >= sb->a_high_water) {
            return TAPE_ERR_NO_VALID_INDEX;
        }

        sum += out->entries[i].frame_count;
    }

    if (sum != out->total_frames) {
        return TAPE_ERR_NO_VALID_INDEX;
    }
    return TAPE_OK;
}

uint32_t tape_derive_free_next(const struct tape_index *idx, const struct tape_sb *sb,
                               tape_side side)
{
    uint32_t next = sb->a_high_water;
    uint32_t i;

    /* spec §7: only Side B allocations move free_next. Side A lives below the
       high-water mark by construction. */
    if (side != TAPE_SIDE_B) {
        return next;
    }
    for (i = 0; i < idx->entry_count; i++) {
        uint32_t last = tape_entry_last_chunk(&idx->entries[i]);
        if (last + 1u > next) {
            next = last + 1u;
        }
    }
    return next;
}
