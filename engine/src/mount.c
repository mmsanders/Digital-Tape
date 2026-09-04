/*
 * mount.c — instance lifecycle and the mount read path.
 * Normative: spec/engine-api.md §4, §5; spec/tapefs-v1.md §4.1, §5.2, §7.
 *
 * The order of refusals in tape_mount is itself normative and each step has a
 * test that exercises its refusal path (spec/acceptance.md, WP-06).
 *
 * DRAFT-4 reconciled. Mount is three phases and ONLY PHASE 3 WRITES:
 *
 *   1  selection   read both superblock copies, pick a candidate. No writes.
 *   2  admission   version, then state, then geometry. No writes.
 *   3  repair      rewrite the invalid copy from the candidate. Writes.
 *
 * The ordering is the point. DRAFT-3 let repair precede the version check, which
 * meant a v1 engine could write to v2 media it is forbidden to touch (V3-006).
 * A version_major = 2 mount now writes nothing at all, including no mirror
 * repair, and acceptance.md WP-06 names that as a required test.
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
 * spec §4.1, phases 1 and 2. No writes happen anywhere in this function; repair
 * is phase 3 and is a separate call, so that the "writes nothing" guarantee is
 * structural rather than a matter of reading the control flow carefully.
 *
 * On return, *repair_lba is the block to rewrite if phase 3 runs, or UINT32_MAX
 * if both copies were valid.
 */
static tape_result resolve_superblock(struct tape *t, uint32_t *repair_lba)
{
    unsigned char pri[TAPE_BLOCK_SIZE], mir[TAPE_BLOCK_SIZE];
    struct tape_sb sb_pri, sb_mir;
    tape_result r_pri, r_mir, rc;
    const struct tape_sb *chosen;
    bool pri_ok, mir_ok;

    *repair_lba = 0xFFFFFFFFu;
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
        /* Exactly one valid: it is the candidate, and the partner is recorded as
           needing repair. Whether repair actually happens is phase 3's business
           and depends on passing phase 2 first. */
        t->needs_repair = true;
        *repair_lba = pri_ok ? (t->dev.block_count - 1u) : TAPE_LBA_SUPERBLOCK;
        memcpy(t->block, pri_ok ? pri : mir, TAPE_BLOCK_SIZE);
    }

    t->sb = *chosen;

    /* --- phase 2: admission, in this order. Still no writes. --- */

    /* 1. An unsupported version is not corruption. Nothing is written and no
          repair happens — repairing it is exactly how an old reader downgrades
          new media. This must come before everything else. */
    if (t->sb.version_major != 1u) { return TAPE_ERR_VERSION; }

    /* 2. version_minor > 0 mounts read-only. */
    if (t->sb.version_minor > 0u) { t->writable = false; }

    /* 3. An interrupted duplicate or format. */
    if (t->sb.state == TAPE_STATE_WRITE_IN_PROGRESS) { return TAPE_ERR_INCOMPLETE; }

    /* 4. Geometry, all in 64-bit, against an untrusted block_count. */
    rc = tape_sb_check_geometry(&t->sb, t->dev.block_count);
    if (rc != TAPE_OK) { return rc; }

    return TAPE_OK;
}

/*
 * spec §4.1 phase 3 — the only phase that writes.
 *
 * Runs only if the candidate passed phase 2, exactly one copy was structurally
 * valid, and the device is writable. sb_generation is NOT incremented: repair
 * restores a copy of an existing logical state, it does not create a new one.
 */
static tape_result repair_superblock(struct tape *t, uint32_t repair_lba)
{
    if (repair_lba == 0xFFFFFFFFu) { return TAPE_OK; }   /* nothing to repair */
    if (t->dev.write == NULL)      { return TAPE_OK; }   /* read-only: skip, report */

    if (dev_write(&t->dev, repair_lba, 1u, t->block) != 0) { return TAPE_ERR_IO; }
    if (dev_flush(&t->dev) != 0)                           { return TAPE_ERR_IO; }

    t->needs_repair = false;
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

/*
 * spec §5.3 index-slot selection, now normative. It performs NO WRITES.
 *
 * Reconciliation note: my DRAFT-3-era invented rule differed in one place. It
 * accepted two valid slots at equal `sequence` when they were byte-identical.
 * DRAFT-4 says equal sequence is TAPE_ERR_INCONSISTENT unconditionally. The
 * spec wins, and it is the better rule: equal sequence is unreachable through
 * §8, so it means media fault or implementation bug, and byte-identity would
 * have quietly accepted a card that had somehow produced two live generations.
 *
 * The invalid partner is NEVER repaired. It is the normal resting state after
 * format (§9.6) and after every commit (§8), and repairing it would destroy the
 * fallback the commit protocol depends on — which is also how promote recovers.
 */
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
        /* §5.3: equal sequence is inconsistent regardless of content. */
        return TAPE_ERR_INCONSISTENT;
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
                       const tape_warm_start *warm)
{
    uint32_t repair_lba;
    tape_result rc;

    if (t == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (side != TAPE_SIDE_A && side != TAPE_SIDE_B) { return TAPE_ERR_INVALID_ARG; }

    t->mounted = false;
    t->warm_start_used = false;

    /* Phases 1 and 2. Any refusal from here returns before phase 3 exists. */
    rc = resolve_superblock(t, &repair_lba);
    if (rc != TAPE_OK) { return rc; }

    /* Phase 3. Only reached by media that passed admission. */
    rc = repair_superblock(t, repair_lba);
    if (rc != TAPE_OK) { return rc; }

    /* §5.3 index-slot selection, then §5.1's overlap rule against the selected
       index. Scratch is free at mount and is the sort's working space. */
    rc = pick_live_index(t, side);
    if (rc != TAPE_OK) { return rc; }

    rc = tape_index_check_overlap(&t->live, &t->scratch);
    if (rc != TAPE_OK) { return rc; }

    t->side      = side;
    t->free_next = tape_derive_free_next(&t->live, &t->sb, side);
    t->rate_q16_16 = 0;

    /* Seek to resume_frame, clamped to the timeline (§5, §11). Beyond end is
       not an error — it clamps. */
    t->position_frame = (resume_frame > t->live.total_frames)
                      ? t->live.total_frames : resume_frame;

    /*
     * Warm start (§5, §12). Validated, and a mismatch DISABLES it rather than
     * failing the mount: a ring retained from cartridge X side A rendered into a
     * mount of cartridge Y side B is the failure this descriptor exists to
     * prevent (V3-016), and a wrong buffer should cost instant-on, not the
     * cartridge. The engine borrows the buffer; it never owns it (Rule 1).
     */
    if (warm != NULL && warm->data != NULL && warm->valid_frames > 0u
        && warm->side == side
        && memcmp(warm->uuid, t->sb.cartridge_uuid, 16) == 0
        && (uint64_t)warm->start_frame <= t->position_frame
        && t->position_frame < (uint64_t)warm->start_frame + warm->valid_frames) {
        t->warm_start_used = true;
    }

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
    out->warm_start_used  = t->warm_start_used;
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
        rc = tape_index_check_overlap(&t->live, &t->scratch);
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
