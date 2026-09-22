/*
 * commit.c — the §8 index commit protocol. Normative: spec/tapefs-v1.md
 * §4.5, §8, §8.1.
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
 *
 * §8's STAGE CLEARING also lives here, because it is the other write protocol
 * with an order that must not drift: §4.6's partner first, candidate last, a
 * flush behind each. It is a superblock update rather than an index commit, so
 * it is a separate function — but it belongs beside tape_commit_index for the
 * same reason tape_commit_index exists at all: stated once.
 *
 * tape_reset_side_b's stage clearing is NOT enabled by this change. WP-09's
 * independent package covers tape_arm's, and only tape_arm's; ops.c keeps its
 * documented refusal until reset-B's is independently covered too.
 */

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
 * §8 stage clearing, written through §4.6's ordinary superblock update.
 *
 * Field-wise on the bytes §4.1 selected, not a re-serialisation: promote_stage
 * and promote_staging_chunk to 0, sb_generation + 1, a_high_water UNCHANGED —
 * §8 says so explicitly, and moving the water line here would orphan Side B's
 * chunks — then the §5.2 CRC over bytes 0…507.
 *
 * Partner first. V7-001 is the whole reason: a mirror-first update that tears
 * can leave selection on a copy OLDER than a generation this operation already
 * made durable, and one such cartridge lost its Side A permanently. The new
 * generation is strictly greater than the candidate's, so the partner becomes
 * selectable the moment step 1 is durable.
 *
 * Exactly two writes and two flushes, and NO READ: the bytes come from
 * t->sb_block, which mount kept. A read here would be a block callback in a
 * call whose observable trace §4.6 fixes at four events.
 */
tape_result tape_sb_clear_stage(struct tape *t)
{
    unsigned char *blk = t->sb_block;

    tape_wr32(blk + 12,  t->sb.sb_generation + 1u);
    tape_wr32(blk + 124, TAPE_PROMOTE_STAGE_NONE);
    tape_wr32(blk + 128, 0u);
    tape_wr32(blk + 508, tape_crc32(blk, 508u));

    if (dev_write(&t->dev, t->sb_partner_lba, 1u, blk) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    if (dev_flush(&t->dev) != 0) { t->faulted = true; return TAPE_ERR_IO; }

    if (dev_write(&t->dev, t->sb_candidate_lba, 1u, blk) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    if (dev_flush(&t->dev) != 0) { t->faulted = true; return TAPE_ERR_IO; }

    /* Only now is the in-memory superblock allowed to agree with the media.
       Both copies carry the same bytes at the same generation, so §4.6 case 3
       applies from here on: primary candidate, mirror partner. */
    t->sb.sb_generation        += 1u;
    t->sb.promote_stage         = TAPE_PROMOTE_STAGE_NONE;
    t->sb.promote_staging_chunk = 0u;
    t->sb_candidate_lba         = TAPE_LBA_SUPERBLOCK;
    t->sb_partner_lba           = t->dev.block_count - 1u;
    return TAPE_OK;
}
