/*
 * mount.c — instance lifecycle and the mount read path.
 * Normative: spec/engine-api.md §4, §5; spec/tapefs-v1.md §4.1, §5.2, §7.
 *
 * The order of refusals in tape_mount is itself normative and each step has a
 * test that exercises its refusal path (spec/acceptance.md, WP-06).
 */

#include <string.h>
#include "tape_internal.h"
#include "dev.h"

size_t tape_instance_size(void)
{
    return sizeof(struct tape);
}

tape_result tape_init(void *mem, size_t mem_len,
                      const tape_dev *dev,
                      void *play_ring, size_t play_ring_len,
                      void *rec_ring,  size_t rec_ring_len,
                      tape **out)
{
    struct tape *t;

    if (mem == NULL || dev == NULL || out == NULL)      { return TAPE_ERR_INVALID_ARG; }
    if (mem_len < sizeof(struct tape))                  { return TAPE_ERR_INVALID_ARG; }
    if (dev->read == NULL || dev->flush == NULL)        { return TAPE_ERR_INVALID_ARG; }
    if (play_ring == NULL || play_ring_len < TAPE_PLAY_RING_MIN) { return TAPE_ERR_INVALID_ARG; }
    if (rec_ring  == NULL || rec_ring_len  < TAPE_REC_RING_MIN)  { return TAPE_ERR_INVALID_ARG; }

    /* The caller owns this memory; the engine allocates nothing, ever (§4). */
    t = (struct tape *)mem;
    memset(t, 0, sizeof *t);
    t->dev           = *dev;
    t->play_ring     = play_ring;
    t->play_ring_len = play_ring_len;
    t->rec_ring      = rec_ring;
    t->rec_ring_len  = rec_ring_len;
    t->rate_q16_16   = 0;
    /* Read-only is the absence of a write function, not a flag (guardrail 06). */
    t->writable      = (dev->write != NULL);
    *out = t;
    return TAPE_OK;
}

/* Read one 512-byte block into the instance's staging buffer. */
static tape_result read_block(struct tape *t, uint32_t lba, unsigned char *dst)
{
    if (dev_read(&t->dev, lba, 1u, dst) != 0) {
        return TAPE_ERR_IO;
    }
    return TAPE_OK;
}

/*
 * spec §4.1 two-copy protocol. Resolution order is normative:
 *   validity -> pick copy -> version -> state -> geometry
 * Version is checked BEFORE any repair: an unsupported version is not
 * corruption, and repairing it is how a v1 reader would downgrade v2 media.
 */
static tape_result resolve_superblock(struct tape *t)
{
    unsigned char pri[TAPE_BLOCK_SIZE], mir[TAPE_BLOCK_SIZE];
    struct tape_sb sb_pri, sb_mir;
    tape_result r_pri, r_mir, rc;
    const struct tape_sb *chosen;
    bool pri_ok, mir_ok;

    if (t->dev.block_count == 0u) {
        return TAPE_ERR_GEOMETRY;
    }

    rc = read_block(t, TAPE_LBA_SUPERBLOCK, pri);
    if (rc != TAPE_OK) { return rc; }
    /* The mirror is at block_count - 1 (§3). That is the only way to find it,
       and block_count is untrusted — which is why geometry re-checks that the
       superblock's own lba_superblock_mirror agrees. */
    rc = read_block(t, t->dev.block_count - 1u, mir);
    if (rc != TAPE_OK) { return rc; }

    r_pri = tape_sb_parse(pri, &sb_pri);
    r_mir = tape_sb_parse(mir, &sb_mir);
    pri_ok = (r_pri == TAPE_OK);
    mir_ok = (r_mir == TAPE_OK);

    if (!pri_ok && !mir_ok) {
        /* Report magic ahead of CRC: a blank or foreign card is a different
           problem from a corrupted one, and the caller can tell them apart. */
        return (r_pri == TAPE_ERR_BAD_MAGIC) ? r_pri : r_mir;
    }

    if (pri_ok && mir_ok) {
        if (sb_pri.sb_generation == sb_mir.sb_generation) {
            if (memcmp(pri, mir, TAPE_BLOCK_SIZE) != 0) {
                return TAPE_ERR_INCONSISTENT;
            }
            chosen = &sb_pri;
        } else {
            chosen = (sb_pri.sb_generation > sb_mir.sb_generation) ? &sb_pri : &sb_mir;
        }
        t->needs_repair = false;
    } else {
        chosen = pri_ok ? &sb_pri : &sb_mir;
        /* One copy invalid. A writable device may be repaired; a read-only one
           never is, and reports the fact instead (§4.1). Repair itself is a
           write and therefore waits for the commit path. */
        t->needs_repair = true;
    }

    t->sb = *chosen;

    if (t->sb.version_major != 1u) { return TAPE_ERR_VERSION; }
    if (t->sb.state == TAPE_STATE_WRITE_IN_PROGRESS) { return TAPE_ERR_INCOMPLETE; }

    rc = tape_sb_check_geometry(&t->sb, t->dev.block_count);
    if (rc != TAPE_OK) { return rc; }

    /* version_minor > 0 mounts read-only (§4.1). */
    if (t->sb.version_minor > 0u) {
        t->writable = false;
    }
    return TAPE_OK;
}

/* Load one index slot: header block, then the entry blocks it needs. */
static tape_result load_slot(struct tape *t, uint32_t lba, uint8_t side,
                             struct tape_index *out)
{
    unsigned char hdr[TAPE_BLOCK_SIZE];
    uint32_t count, blocks;
    tape_result rc;

    rc = read_block(t, lba, hdr);
    if (rc != TAPE_OK) { return rc; }

    count = tape_rd32(hdr + 16);
    if (count > TAPE_MAX_ENTRIES) { return TAPE_ERR_NO_VALID_INDEX; }

    if (count > 0u) {
        /* The entry array begins at block 1 of the slot (§5). */
        blocks = (count * TAPE_INDEX_ENTRY_BYTES + TAPE_BLOCK_SIZE - 1u) / TAPE_BLOCK_SIZE;
        if (dev_read(&t->dev, lba + 1u, blocks, t->entry_bytes) != 0) {
            return TAPE_ERR_IO;
        }
    }
    return tape_index_parse(hdr, t->entry_bytes, side, &t->sb, out);
}

/* Pick the live slot for a side: higher sequence with a valid CRC. Equal and
   both valid but differing is TAPE_ERR_INCONSISTENT, which format makes
   unreachable by leaving exactly one valid slot per side (§9.6). */
static tape_result pick_live_index(struct tape *t, tape_side side)
{
    /* The scratch index is the instance's second index buffer (§4). It is free
       at mount time, and using it keeps the engine free of statics. */
    struct tape_index *cand = &t->scratch;
    uint32_t lba0 = (side == TAPE_SIDE_A) ? t->sb.lba_index_a0 : t->sb.lba_index_b0;
    uint32_t lba1 = (side == TAPE_SIDE_A) ? t->sb.lba_index_a1 : t->sb.lba_index_b1;
    tape_result r0, r1;
    bool have0;

    r0 = load_slot(t, lba0, (uint8_t)side, &t->live);
    have0 = (r0 == TAPE_OK);

    r1 = load_slot(t, lba1, (uint8_t)side, cand);

    if (!have0 && r1 != TAPE_OK) {
        return (r0 == TAPE_ERR_IO || r1 == TAPE_ERR_IO) ? TAPE_ERR_IO
                                                        : TAPE_ERR_NO_VALID_INDEX;
    }
    if (!have0) {
        t->live = *cand;
        t->live_slot = 1u;
        return TAPE_OK;
    }
    if (r1 != TAPE_OK) {
        t->live_slot = 0u;
        return TAPE_OK;
    }
    if (cand->sequence == t->live.sequence) {
        if (cand->entry_count != t->live.entry_count
            || cand->total_frames != t->live.total_frames
            || memcmp(cand->entries, t->live.entries,
                      (size_t)cand->entry_count * sizeof(struct tape_entry)) != 0) {
            return TAPE_ERR_INCONSISTENT;
        }
        t->live_slot = 0u;
        return TAPE_OK;
    }
    if (cand->sequence > t->live.sequence) {
        t->live = *cand;
        t->live_slot = 1u;
    } else {
        t->live_slot = 0u;
    }
    return TAPE_OK;
}

tape_result tape_mount(tape *t, tape_side side, uint64_t resume_frame,
                       const void *warm_start, size_t warm_start_len)
{
    tape_result rc;

    if (t == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (side != TAPE_SIDE_A && side != TAPE_SIDE_B) { return TAPE_ERR_INVALID_ARG; }
    if (warm_start == NULL && warm_start_len != 0u)  { return TAPE_ERR_INVALID_ARG; }

    t->mounted = false;

    rc = resolve_superblock(t);
    if (rc != TAPE_OK) { return rc; }

    rc = pick_live_index(t, side);
    if (rc != TAPE_OK) { return rc; }

    t->side      = side;
    t->free_next = tape_derive_free_next(&t->live, &t->sb, side);
    t->rate_q16_16 = 0;

    /* Seek to resume_frame, clamped to the timeline (§5, §11). Beyond end is
       not an error — it clamps. */
    t->position_frame = (resume_frame > t->live.total_frames)
                      ? t->live.total_frames : resume_frame;

    /* The warm-start buffer is the caller's retained play ring from before
       sleep. The engine borrows it; it never owns it (Rule 1). Rendering from
       it is the play path and lands with WP-08. */
    (void)warm_start;
    (void)warm_start_len;

    t->mounted = true;
    return TAPE_OK;
}

tape_result tape_unmount(tape *t, uint64_t *out_position_frame)
{
    if (t == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }

    /* The engine never writes position to media (§5, §11): the source slot is
       read-only, so position lives in the device's flash. */
    if (out_position_frame != NULL) {
        *out_position_frame = t->position_frame;
    }
    t->mounted = false;
    return TAPE_OK;
}

tape_result tape_get_info(const tape *t, tape_info *out)
{
    if (t == NULL || out == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)              { return TAPE_ERR_NOT_MOUNTED; }

    memset(out, 0, sizeof *out);
    memcpy(out->uuid, t->sb.cartridge_uuid, 16);
    memcpy(out->label, t->sb.label, sizeof out->label);
    out->nominal_length_s = t->sb.nominal_length_s;
    out->total_frames     = t->live.total_frames;
    out->total_chunks     = t->sb.total_chunks;
    out->free_chunks      = (t->sb.total_chunks > t->free_next)
                          ? t->sb.total_chunks - t->free_next : 0u;
    out->entry_count      = t->live.entry_count;
    out->entries_free     = TAPE_MAX_ENTRIES - t->live.entry_count;
    /* Side A refuses writes at the API boundary regardless of the device. */
    out->writable         = t->writable && (t->side == TAPE_SIDE_B);
    out->needs_repair     = t->needs_repair;
    return TAPE_OK;
}

tape_result tape_set_side(tape *t, tape_side side)
{
    if (t == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    if (side != TAPE_SIDE_A && side != TAPE_SIDE_B) { return TAPE_ERR_INVALID_ARG; }
    if (side == t->side) { return TAPE_OK; }

    /* §5: commits nothing, discards nothing. Implicit commits are how a child
       loses work they did not mean to keep. Recording state gates this once the
       record path exists; there is none yet, so nothing to refuse. */
    {
        tape_result rc = pick_live_index(t, side);
        if (rc != TAPE_OK) { return rc; }
    }
    t->side           = side;
    t->free_next      = tape_derive_free_next(&t->live, &t->sb, side);
    t->position_frame = 0;
    return TAPE_OK;
}

uint64_t tape_tell(const tape *t)
{
    return (t != NULL && t->mounted) ? t->position_frame : 0u;
}
