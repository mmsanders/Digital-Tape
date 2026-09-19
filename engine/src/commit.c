/*
 * commit.c — the §8 commit protocol and the superblock update it sometimes
 * needs first. Normative: spec/tapefs-v1.md §4.5, §4.6, §8, §8.1.
 *
 * One index commit, stated once. tape_reset_side_b and tape_commit both land
 * here, so "entry array, flush, header, flush" is a single piece of code rather
 * than two transcriptions that can drift. The header is written LAST and is the
 * commit point: before it lands, the inactive slot's block 0 still holds the
 * previous generation's header, whose CRC does not match the entries just
 * written, so §5.3 falls back to the other slot. A crash DURING it leaves a
 * header failing its own CRC, with the same result.
 *
 * Every write and flush here is against the instance's own device, so every
 * failure is §7.2 quarantine — the durability of that block is unknown and the
 * only honest recovery is a remount. §4.1 phase-4 repair is the one write in
 * the engine excluded from that rule, and it is not here.
 */

#include <string.h>

#include "tape_internal.h"
#include "tape_crc32.h"
#include "dev.h"

bool tape_headroom_ok(uint32_t current, uint32_t need)
{
    /* §4.5: a counter whose `needed` is 0 is NOT CONSULTED. A zero-write branch
       must not be refused because a stored counter already sits at 0xFFFFFFFE —
       those values are never written (§10) but are reachable on crafted media,
       and §5.2 does not reject them (V7-002). */
    if (need == 0u) { return true; }
    /* 64-bit: in u32, 0xFFFFFFFC + 4 wraps to 0 and the test would PASS, after
       which a commit writes the two values §10 forbids and §5.3 starts selecting
       the older slot. WP-10 crafts exactly that cartridge. */
    return (uint64_t)current + (uint64_t)need <= 0xFFFFFFFDu;
}

tape_result tape_commit_index(struct tape *t, uint32_t slot_lba,
                              const struct tape_index *idx)
{
    uint32_t blocks = tape_index_serialize_entries(idx, t->entry_bytes);

    /* §8 step 3 — the entry array into blocks 1 … ceil(count*12/512). At
       TAPE_MAX_ENTRIES that is 96 blocks; with block 0 below, §7.1's 97-block
       bound is this line plus that one. */
    if (blocks > 0u
        && dev_write(&t->dev, slot_lba + 1u, blocks, t->entry_bytes) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    /* step 4 — the barrier. Unconditional: §8 does not make it depend on
       whether the entry array happened to be empty. */
    if (dev_flush(&t->dev) != 0) { t->faulted = true; return TAPE_ERR_IO; }

    /* step 5 — block 0, and THE COMMIT POINT. */
    tape_index_header_block(idx, t->entry_bytes, t->block);
    if (dev_write(&t->dev, slot_lba, 1u, t->block) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    /* step 6 */
    if (dev_flush(&t->dev) != 0) { t->faulted = true; return TAPE_ERR_IO; }

    return TAPE_OK;
}

/*
 * §8's stage clearing, expressed as §4.6's ordinary superblock update.
 *
 * NOT REACHED BY EITHER VT8-001 CASE: both fixtures are promote_stage == 0, so
 * this whole function is unexercised by the landed package. It is here because
 * §8 states the rule as a requirement ON tape_arm AND tape_reset_side_b, and
 * omitting it would make those two calls commit an index onto stage-1 media —
 * which §8 forbids in as many words, and whose consequence it spells out: every
 * later tape_promote matches no §9.3.3 row and reports a media fault forever
 * after one power loss during one superblock write.
 *
 * a_high_water is UNCHANGED. Only promote_stage, promote_staging_chunk and
 * sb_generation move.
 */
tape_result tape_clear_promote_stage(struct tape *t)
{
    unsigned char pri[TAPE_BLOCK_SIZE], mir[TAPE_BLOCK_SIZE];
    struct tape_sb sb_pri, sb_mir;
    bool     pri_ok, mir_ok, primary_is_candidate;
    uint32_t cand_gen, cand_lba, partner_lba, mirror_lba;

    mirror_lba = t->dev.block_count - 1u;

    if (dev_read(&t->dev, TAPE_LBA_SUPERBLOCK, 1u, pri) != 0) { return TAPE_ERR_IO; }
    if (dev_read(&t->dev, mirror_lba, 1u, mir) != 0)          { return TAPE_ERR_IO; }

    pri_ok = (tape_sb_parse(pri, &sb_pri) == TAPE_OK);
    mir_ok = (tape_sb_parse(mir, &sb_mir) == TAPE_OK);

    /* §4.6 row 5. Unreachable from a mounted instance — §4.1 phase 1 would have
       refused the mount — but a refusal is the only safe answer if it happens. */
    if (!pri_ok && !mir_ok) { return TAPE_ERR_BAD_MAGIC; }

    /* §4.6 rows 1–3. `>=` is row 3's tie-break: equal generation and
       byte-identical is the healthy resting state, and the PRIMARY is the
       candidate there. Row 4 (equal, divergent) cannot reach a mounted
       instance either; phase 1 returned TAPE_ERR_INCONSISTENT. */
    primary_is_candidate = (pri_ok && mir_ok)
                         ? (sb_pri.sb_generation >= sb_mir.sb_generation)
                         : pri_ok;

    cand_gen    = primary_is_candidate ? sb_pri.sb_generation : sb_mir.sb_generation;
    cand_lba    = primary_is_candidate ? TAPE_LBA_SUPERBLOCK  : mirror_lba;
    partner_lba = primary_is_candidate ? mirror_lba           : TAPE_LBA_SUPERBLOCK;

    /* The new bytes are the candidate's, with three fields moved and the CRC
       recomputed. Copying the candidate rather than re-serialising t->sb keeps
       every field this engine does not interpret exactly as it found it. */
    memcpy(t->block, primary_is_candidate ? pri : mir, TAPE_BLOCK_SIZE);
    tape_wr32(t->block + 12,  cand_gen + 1u);
    tape_wr32(t->block + 124, TAPE_PROMOTE_STAGE_NONE);
    tape_wr32(t->block + 128, 0u);
    tape_wr32(t->block + 508, tape_crc32(t->block, 508u));

    /* §4.6: partner first, candidate last, flushing after each. The new
       generation is strictly greater than the candidate's, so the partner
       becomes selectable as soon as step 1 is durable — whether or not its
       flush returned (§8.1). Tearing step 1 leaves the previous candidate
       untouched; tearing step 2 leaves the new generation on the partner and
       §4.1 selects it. There is no injection point at which the only valid copy
       is older than a generation this call already made durable (V7-001). */
    if (dev_write(&t->dev, partner_lba, 1u, t->block) != 0) { t->faulted = true; return TAPE_ERR_IO; }
    if (dev_flush(&t->dev) != 0)                            { t->faulted = true; return TAPE_ERR_IO; }
    if (dev_write(&t->dev, cand_lba, 1u, t->block) != 0)    { t->faulted = true; return TAPE_ERR_IO; }
    if (dev_flush(&t->dev) != 0)                            { t->faulted = true; return TAPE_ERR_IO; }

    t->sb.sb_generation         = cand_gen + 1u;
    t->sb.promote_stage         = TAPE_PROMOTE_STAGE_NONE;
    t->sb.promote_staging_chunk = 0u;
    /* Both copies now carry these bytes, so whatever phase 4 left outstanding
       is resolved. */
    t->needs_repair = false;
    return TAPE_OK;
}
