/*
 * mount.c — instance lifecycle and the mount read path.
 * Normative: spec/engine-api.md §3.1, §4, §5; spec/tapefs-v1.md §4.1–§4.5, §5, §7.
 *
 * DRAFT-6 reconciled. MOUNT IS FOUR PHASES AND ONLY THE LAST ONE WRITES:
 *
 *   1  selection   read both superblock copies, pick a candidate.   No writes.
 *   2  admission   version, minor, defined values, state, geometry.  No writes.
 *   3  indices     select and validate BOTH sides, then degraded-B,
 *                  then the stage oracle.                            No writes.
 *   4  repair      rewrite the invalid superblock copy.             WRITES.
 *
 * The ordering is the whole point, and it has moved twice for the same reason.
 * DRAFT-3 let repair precede the version check, so a v1 engine could write to v2
 * media it is forbidden to touch (V3-006). DRAFT-5 let repair precede INDEX
 * validation, so a mount destined to fail on TAPE_ERR_NO_VALID_INDEX or the
 * stage oracle had already written the mirror (V5-003).
 *
 * So: no mount that is going to fail writes anything. That is invariant 26, and
 * before DRAFT-6 it was a claim the algorithm could not deliver. The two
 * concerns are independent — repair is about the superblock, selection is about
 * index slots — so the reorder costs nothing.
 *
 * Phase 4 is also the one write in the engine that does NOT fault the instance
 * on failure (§7.2). It changes no logical state: it only makes a second copy
 * agree with the candidate already selected, so the cartridge is exactly as
 * readable as it was, and refusing the mount would deny a child their music to
 * fix a redundancy they cannot hear.
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
    /* effective_writable is NOT decided here. It is the conjunction in §4.3, and
       its second term — the mounted version_minor — does not exist until a
       superblock has been read. Until then the instance is not mounted and every
       mutator refuses on that ground instead. */
    t->effective_writable = false;
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

    /* --- phase 2: admission, in spec order. Still no writes. --- */

    /* 1. An unsupported version is not corruption. Nothing is written and no
          repair happens — repairing it is exactly how an old reader downgrades
          new media. This must come before everything else. */
    if (t->sb.version_major != 1u) { return TAPE_ERR_VERSION; }

    /* 2. §4.3's permission predicate, both terms, computed once and stored.
          DRAFT-4 declared a version_minor > 0 cartridge read-only in one document
          and authorised every write by `write != NULL` in another, so on a
          writable device a v1 engine was still permitted to commit v1 structures
          onto v1.1 media whose semantics it does not understand (V4-001). The
          barrier existed in prose and in no code path. It is one variable now,
          and phase 4 consults it too. */
    t->effective_writable = (t->dev.write != NULL) && (t->sb.version_minor == 0u);

    /* 3. Defined-value check (V4-012). A CRC-correct superblock with state = 2
          previously passed — the only test was `state == WRITE_IN_PROGRESS` — so
          damaged or future values FAILED OPEN and the cartridge mounted
          read-write with its transaction state unknown. Undefined values now
          fail closed, which is the discipline step 1 already applies to
          version_major. */
    if (t->sb.state > TAPE_STATE_WRITE_IN_PROGRESS)          { return TAPE_ERR_UNSUPPORTED_STATE; }
    if (t->sb.promote_stage > TAPE_PROMOTE_STAGE_PHASE1)     { return TAPE_ERR_UNSUPPORTED_STATE; }

    /* 4. An interrupted duplicate or format; the remedy is to re-run it. */
    if (t->sb.state == TAPE_STATE_WRITE_IN_PROGRESS) { return TAPE_ERR_INCOMPLETE; }

    /* 5. Geometry, all in 64-bit, against an untrusted block_count. */
    rc = tape_sb_check_geometry(&t->sb, t->dev.block_count);
    if (rc != TAPE_OK) { return rc; }

    return TAPE_OK;
}

/*
 * spec §4.1 phase 4 — the only phase that writes.
 *
 * Runs only if the candidate passed phases 2 AND 3, exactly one superblock copy
 * was structurally valid, and the mount is EFFECTIVELY WRITABLE (§4.3) — not
 * merely on a device with a write pointer. sb_generation is NOT incremented:
 * repair restores a copy of an existing logical state, it does not create one.
 *
 * A repair failure is not fatal and does not fault the instance (§4.1, §7.2).
 * The mount succeeds with needs_repair = true. This is the single write in the
 * engine with that property, and the reason is that nothing the mount depends on
 * was being changed.
 */
static void repair_superblock(struct tape *t, uint32_t repair_lba)
{
    if (repair_lba == 0xFFFFFFFFu)  { return; }   /* nothing to repair */
    if (!t->effective_writable)     { return; }   /* skipped, and reported */

    if (dev_write(&t->dev, repair_lba, 1u, t->block) != 0) { return; }
    if (dev_flush(&t->dev) != 0)                           { return; }

    t->needs_repair = false;
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
 * spec §5.3 index-slot selection, per side. It performs NO WRITES.
 *
 * My DRAFT-3-era invented rule differed in one place: it accepted two valid
 * slots at equal `sequence` when they were byte-identical. §5.3 says equal
 * sequence is TAPE_ERR_INCONSISTENT unconditionally, and it is the better rule —
 * equal sequence is unreachable through §8, so it means media fault or
 * implementation bug, and byte-identity would have quietly accepted a card that
 * had somehow produced two live generations.
 *
 * THE INVALID PARTNER IS NEVER REPAIRED. It is the normal resting state after
 * format (§9.6) and after every commit (§8), and repairing it would destroy the
 * fallback the commit protocol depends on — which is also how promote recovers.
 */
static tape_result select_side(struct tape *t, tape_side side)
{
    struct tape_index *live = &t->idx[side];
    uint32_t lba0 = (side == TAPE_SIDE_A) ? t->sb.lba_index_a0 : t->sb.lba_index_b0;
    uint32_t lba1 = (side == TAPE_SIDE_A) ? t->sb.lba_index_a1 : t->sb.lba_index_b1;
    tape_result r0, r1, rc;
    bool valid0, valid1;
    uint32_t seq0 = 0u;

    /*
     * Both slots are parsed into the SAME buffer, one after the other, and the
     * winner is reloaded if it was the first. That costs one extra slot read
     * when slot 0 wins and slot 1 is also valid — at most 97 blocks, and one or
     * two in practice, since entry counts are small until a cartridge has been
     * spliced hundreds of times.
     *
     * The obvious optimisation is to parse slot 1 into the OTHER side's buffer,
     * which is free during Side A's selection. It is wrong, and I wrote it that
     * way first: phase 3 selects A and then B, so during B's selection that
     * buffer holds SIDE A'S ALREADY-SELECTED INDEX. A cartridge with two valid
     * B slots would have had Side A's index overwritten by a Side B slot —
     * silently, since the result still parses. Every test passed, because the
     * fixtures leave the second slot invalid, which is §5.3's resting state.
     *
     * A third buffer would avoid the reload and cost 49 KiB against a budget
     * already at 76 %. The reload is the cheaper mistake to make.
     */
    r0 = load_slot(t, lba0, (uint8_t)side, live);
    valid0 = (r0 == TAPE_OK);
    if (valid0) { seq0 = live->sequence; }

    r1 = load_slot(t, lba1, (uint8_t)side, live);
    valid1 = (r1 == TAPE_OK);

    if (!valid0 && !valid1) {
        return (r0 == TAPE_ERR_IO || r1 == TAPE_ERR_IO) ? TAPE_ERR_IO
                                                        : TAPE_ERR_NO_VALID_INDEX;
    }

    if (valid0 && valid1 && live->sequence == seq0) {
        /* §5.3, regardless of content. My DRAFT-3-era invented rule accepted
           this when the two were byte-identical; equal sequence is unreachable
           through §8, so it means media fault or implementation bug either way,
           and byte-identity would have quietly accepted a card that had somehow
           produced two live generations. */
        return TAPE_ERR_INCONSISTENT;
    }

    if (valid1 && (!valid0 || live->sequence > seq0)) {
        t->live_slot[side] = 1u;
    } else {
        /* Slot 0 wins: it is no longer in the buffer, so read it back. It
           validated a moment ago, so a failure here is genuine I/O or media
           changing underneath us — either way it is not a valid index. */
        r0 = load_slot(t, lba0, (uint8_t)side, live);
        if (r0 != TAPE_OK) { return r0; }
        t->live_slot[side] = 0u;
    }

    /* §5.1's interval-disjointness rule is part of §5.2 validity, so it belongs
       here and not after selection: an index that overlaps itself is not valid,
       and "not valid" is what selection is deciding. No chunk is read, which
       WP-06c asserts by counting chunk-region reads across a whole mount. */
    rc = tape_index_check_overlap(live, t->sort_perm);
    if (rc != TAPE_OK) { return rc; }

    return TAPE_OK;
}

/* True iff `idx` is exactly one entry equal to {chunk, 0, n}. The oracle's rows
   are all of this shape, so stating it once keeps them readable. */
static bool one_entry_at(const struct tape_index *idx, uint32_t chunk, uint64_t n)
{
    return idx->entry_count == 1u
        && idx->entries[0].first_chunk_id == chunk
        && idx->entries[0].start_frame    == 0u
        && (uint64_t)idx->entries[0].frame_count == n
        && idx->total_frames == n;
}

static bool same_entries(const struct tape_index *a, const struct tape_index *b)
{
    uint32_t i;
    if (a->entry_count != b->entry_count) { return false; }
    if (a->total_frames != b->total_frames) { return false; }
    for (i = 0; i < a->entry_count; i++) {
        if (a->entries[i].first_chunk_id != b->entries[i].first_chunk_id) { return false; }
        if (a->entries[i].start_frame    != b->entries[i].start_frame)    { return false; }
        if (a->entries[i].frame_count    != b->entries[i].frame_count)    { return false; }
    }
    return true;
}

/*
 * spec §4.2 step 3 and §9.3.3 — THE STAGE ORACLE. No writes.
 *
 * With promote_stage == 1 the live A and B indices must match exactly one of
 * three shapes. Matching none is TAPE_ERR_INCONSISTENT: media fault or
 * implementation defect, not something to recover from silently.
 *
 * This has to happen AT MOUNT, and V5-003 is why. Invariant 25 and WP-10 both
 * required the check, and only a later tape_promote performed it — so two
 * conforming mounts could disagree. Worse: §8's stage clearing would have erased
 * the evidence. An ordinary tape_arm clears promote_stage before anything
 * reported the fault, and the corruption becomes permanently invisible.
 *
 * `S > 0` on rows 2 and 3 is load-bearing, not decoration. Without it rows 1 and
 * 2 are the SAME PREDICATE whenever S == 0 — and S == 0 is the ordinary
 * first-use path: format leaves a_high_water = 0, the first Side B recording
 * allocates from free_next = 0 giving {0,0,N}, and adopt-in-place makes S = 0.
 * Row 3 carries the same guard because `H > len` implies `S > 0` only through
 * the engine's own H = S + len, which is a reachability argument — and crafted
 * media defeats it: S = 0, A == B == {0,0,N}, len = 5, H = 6 matches rows 1
 * and 3 at once. With the guards the three partition unconditionally.
 */
static tape_result check_stage_oracle(const struct tape *t)
{
    const struct tape_index *a = &t->idx[TAPE_SIDE_A];
    const struct tape_index *b = &t->idx[TAPE_SIDE_B];
    uint32_t S = t->sb.promote_staging_chunk;
    uint32_t H = t->sb.a_high_water;
    uint64_t n = a->total_frames;
    uint32_t len;

    /* Row 1 — phase 1 landed, phase 2 not committed. Resume at step 5. */
    if (one_entry_at(a, S, n) && same_entries(a, b)) { return TAPE_OK; }

    /* Row 2 — phase 2 committed A only. Resume at step 8. */
    if (S > 0u && one_entry_at(a, 0u, n) && one_entry_at(b, S, n)) { return TAPE_OK; }

    /* Row 3 — phase 2 committed both indices. Resume at step 9. */
    len = tape_chunks_for_frames(n);
    if (S > 0u && one_entry_at(a, 0u, n) && same_entries(a, b) && H > len) {
        return TAPE_OK;
    }

    return TAPE_ERR_INCONSISTENT;
}

/*
 * spec §4.1 phase 3 / §4.2 — index selection and validation for BOTH SIDES,
 * whichever was requested. No writes.
 *
 * Both, because both are needed. free_next (§7) is defined over the live SIDE B
 * index, so a Side-A mount that had not selected B could not compute it — and
 * tape_respool and tape_promote are both permitted from a Side-A mount and both
 * allocate from it. With free_next degenerated to a_high_water they would
 * allocate straight over Side B's live chunks, violating invariant 10. And
 * §9.3.1's adopt-in-place is safe only because Side A's entries satisfy §5.2's
 * Side-A bound, which has to have been EVALUATED for the argument to hold.
 */
static tape_result select_indices(struct tape *t, tape_side side)
{
    tape_result ra, rb;

    ra = select_side(t, TAPE_SIDE_A);
    rb = select_side(t, TAPE_SIDE_B);

    /* 1. Side A unselectable → the mount fails with that error, whichever side
          was asked for. §5.3: such a cartridge is unusable. */
    if (ra != TAPE_OK) { return ra; }

    /* 2. Side B unselectable → degraded-B (§4.4) on a Side-A request; the error
          itself on a Side-B request. */
    t->side_b_valid = (rb == TAPE_OK);
    if (!t->side_b_valid) {
        if (rb == TAPE_ERR_IO) { return rb; }
        if (side == TAPE_SIDE_B) { return TAPE_ERR_NO_VALID_INDEX; }
        /*
         * THE STAGE ORACLE IS SKIPPED HERE, and the order is normative.
         *
         * Every row of §9.3.3 constrains a live Side B index, so with none
         * present the oracle can match nothing. DRAFT-6's own first cut ran the
         * oracle first, and a cartridge that was BOTH stage-1 and degraded-B
         * therefore returned TAPE_ERR_INCONSISTENT — permanently unmountable.
         * That cartridge is reachable (a promote interrupted between §9.3 steps
         * 4 and 6, then later damage to both B slots) and the consequence was
         * total: tape_reset_side_b is the only recovery and it needs a
         * successful mount, so the whole of Side A's music was unreachable
         * forever on a cartridge whose Side A was intact.
         *
         * The stage resolves itself instead, through §8's clearing write on the
         * tape_reset_side_b that recovers the cartridge.
         */
        return TAPE_OK;
    }

    /* 3. The oracle, only with a live B index to constrain. */
    if (t->sb.promote_stage == TAPE_PROMOTE_STAGE_PHASE1) {
        return check_stage_oracle(t);
    }
    return TAPE_OK;
}

/*
 * spec §5's warm-start rule, ORDERED. The order is normative and the reason is
 * V5-007: DRAFT-5 wrote it as an unordered list of predicates that BEGAN by
 * computing an end frame from warm->start_frame — while the API expressly
 * permits warm == NULL, which is the ordinary cold-mount case. Read as written
 * it dereferenced a null pointer on every cold boot. And `data` itself was never
 * checked, so a descriptor with correct metadata, positive valid_frames,
 * sufficient data_bytes and data == NULL passed every listed predicate and sent
 * the renderer to address zero.
 *
 * Both are impossible to read wrong once the rule is a sequence rather than a
 * conjunction, so this is written as a sequence even though C's && would
 * short-circuit identically. The next person to edit it should not have to know
 * that to keep it safe.
 *
 * A WRONG BUFFER COSTS INSTANT-ON, NEVER CORRECTNESS.
 */
static bool warm_start_ok(const struct tape *t, const tape_warm_start *warm,
                          uint64_t resume_frame)
{
    uint64_t end;

    if (warm == NULL)                { return false; }
    if (warm->data == NULL)          { return false; }
    if (warm->valid_frames == 0u)    { return false; }
    if ((uint64_t)warm->data_bytes
            < (uint64_t)warm->valid_frames * (uint64_t)TAPE_FRAME_BYTES) { return false; }

    /* Checked 64-bit. DRAFT-4 wrote this as prose over 32-bit fields, and a
       direct C evaluation of start_frame + valid_frames WRAPS for start_frame
       near UINT32_MAX — so a stale ring could be accepted for a range it does
       not cover. That is exactly the defect WP-11's seventh mutation exists to
       catch, admitted by the spec defining the mutation (V4-011). */
    end = (uint64_t)warm->start_frame + (uint64_t)warm->valid_frames;
    if (end > TAPE_LIVE(t).total_frames)             { return false; }
    if (resume_frame < (uint64_t)warm->start_frame)  { return false; }
    if (resume_frame >= end)                         { return false; }
    if (memcmp(warm->uuid, t->sb.cartridge_uuid, 16) != 0) { return false; }
    if (warm->side != t->side)                       { return false; }
    return true;
}

tape_result tape_mount(tape *t, tape_side side, uint64_t resume_frame,
                       const tape_warm_start *warm)
{
    uint32_t repair_lba;
    tape_result rc;

    if (t == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (side != TAPE_SIDE_A && side != TAPE_SIDE_B) { return TAPE_ERR_INVALID_ARG; }

    t->mounted         = false;
    t->warm_start_used = false;
    /* A fresh mount is the ONLY exit from §7.2's quarantine, and it is one
       because it re-runs §4.1 and resolves the media honestly. */
    t->faulted         = false;

    /* Phases 1 and 2. No writes anywhere below this line until phase 4. */
    rc = resolve_superblock(t, &repair_lba);
    if (rc != TAPE_OK) { return rc; }

    /* Phase 3 — both sides, degraded-B, then the oracle. Still no writes. */
    rc = select_indices(t, side);
    if (rc != TAPE_OK) { return rc; }

    t->side = side;

    /* Phase 4. Reached only by a mount that is going to succeed, which is what
       makes invariant 26 true. It cannot fail the mount: a repair failure leaves
       needs_repair set and nothing else (§4.1). */
    repair_superblock(t, repair_lba);

    /* §7 / §4.4: free_next is derived from the live SIDE B index, never stored,
       and degenerates to a_high_water only in degraded-B — where there is no
       live B index to derive it from and reset_b is the only thing that writes. */
    t->free_next = t->side_b_valid
                 ? tape_derive_free_next(&t->idx[TAPE_SIDE_B], &t->sb, TAPE_SIDE_B)
                 : t->sb.a_high_water;

    t->rate_q16_16    = 0;
    t->at_end         = false;
    t->at_start       = false;
    t->play_ring_valid = false;

    /* Seek to resume_frame, clamped to the timeline (§5, §11). Beyond end is not
       an error — it clamps. */
    t->position_frame = (resume_frame > TAPE_LIVE(t).total_frames)
                      ? TAPE_LIVE(t).total_frames : resume_frame;

    t->mounted = true;
    t->warm_start_used = warm_start_ok(t, warm, t->position_frame);
    if (t->warm_start_used) { t->play_ring_valid = true; }
    return TAPE_OK;
}

tape_result tape_unmount(tape *t, uint64_t *out_position_frame)
{
    if (t == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }

    /* Permitted in FAULTED — it is the only exit (§7.2). The engine never writes
       position to media (§5, §11): the source slot is read-only, so position
       lives in the device's flash and the position table is the caller's. */
    if (out_position_frame != NULL) {
        *out_position_frame = t->position_frame;
    }
    t->mounted = false;
    t->faulted = false;
    return TAPE_OK;
}

tape_result tape_get_info(const tape *t, tape_info *out)
{
    if (t == NULL || out == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)              { return TAPE_ERR_NOT_MOUNTED; }
    /* Permitted in FAULTED (§7.2): it touches no media. */

    memset(out, 0, sizeof *out);
    memcpy(out->uuid, t->sb.cartridge_uuid, 16);
    memcpy(out->label, t->sb.label, sizeof out->label);
    out->nominal_length_s = t->sb.nominal_length_s;
    out->total_frames     = TAPE_LIVE(t).total_frames;
    out->total_chunks     = t->sb.total_chunks;
    out->free_chunks      = (t->sb.total_chunks > t->free_next)
                          ? t->sb.total_chunks - t->free_next : 0u;
    out->entry_count      = TAPE_LIVE(t).entry_count;
    out->entries_free     = TAPE_MAX_ENTRIES - TAPE_LIVE(t).entry_count;
    out->version_minor    = t->sb.version_minor;
    /*
     * §3.1: this is effective_writable, and it is about THE MOUNT, not the
     * mounted side. DRAFT-4's first cut reported `writable && side == B`, which
     * reads as if promote and dup were forbidden from a Side-A mount — and dup
     * writes the destination's Side A by definition, so it would have been
     * forbidden outright. The Side-A rule belongs to tape_arm and tape_feed
     * alone: those write THE MOUNTED SIDE. reset_b, promote and dup write
     * regions chosen by the operation.
     */
    out->writable         = t->effective_writable;
    out->side_b_valid     = t->side_b_valid;
    out->needs_repair     = t->needs_repair;
    out->warm_start_used  = t->warm_start_used;
    return TAPE_OK;
}

/*
 * §5's side-switch transition, which is NORMATIVE and was not (V5-013).
 *
 * DRAFT-5 said only that this "commits nothing and discards nothing", leaving
 * position, the endpoint flags and the ring undefined across a switch. Mount
 * Side A at frame 1000 with at_end set, switch to a 100-frame Side B: an
 * implementation could keep and clamp the number, reset it, or try a stored
 * resume; keep or clear the flag; keep or drop buffered frames.
 *
 * THE STALE RING IS THE ONE THAT HURTS — it plays audio from the OTHER SIDE for
 * up to 372 ms. So the ring is invalidated and tape_render owes the caller a
 * tape_service before it returns frames.
 *
 * Position resets to 0 because that is what flipping a tape over does. The
 * device-side position table (§11) is the caller's, so firmware restores its own
 * bookmark with a tape_seek immediately after — Principle 1, and it keeps the
 * engine free of a table it has no business owning.
 */
tape_result tape_set_side(tape *t, tape_side side)
{
    if (t == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted)  { return TAPE_ERR_FAULTED; }
    if (side != TAPE_SIDE_A && side != TAPE_SIDE_B) { return TAPE_ERR_INVALID_ARG; }

    /*
     * §10: TAPE_ERR_NO_VALID_INDEX if the requested side has no live index NOW —
     * keyed to current state, not to mount-time, so a successful
     * tape_reset_side_b immediately makes Side B reachable rather than requiring
     * an eject and reinsert. Without this refusal a Side-A mount of a cartridge
     * with a damaged Side B could switch to a side with no live index at all.
     */
    if (side == TAPE_SIDE_B && !t->side_b_valid) { return TAPE_ERR_NO_VALID_INDEX; }

    /* tape_set_side(TAPE_SIDE_A) on the already-mounted side is allowed (the ᴮ
       footnote in §10) and, per the table, still performs the transition. */
    t->side            = side;
    t->position_frame  = 0;
    t->at_end          = false;
    t->at_start        = false;
    t->play_ring_valid = false;
    t->warm_start_used = false;
    return TAPE_OK;
}

tape_result tape_tell(const tape *t, uint64_t *out_frame)
{
    if (t == NULL || out_frame == NULL) { return TAPE_ERR_INVALID_ARG; }
    /* On refusal *out_frame is left untouched (WP-06h). The old bare-uint64_t
       signature had no error channel, so an implementation had to invent a
       sentinel or return a stale position (V5-009). */
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    *out_frame = t->position_frame;
    return TAPE_OK;
}
