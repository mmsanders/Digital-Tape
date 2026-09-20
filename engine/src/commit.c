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
 * NOTHING HERE WRITES A SUPERBLOCK. §8's stage clearing, which would, is not
 * implemented in this split: both accepted VT8-001 observations are on
 * promote_stage == 0 media, so it is not a dependency of either, and P1-R21
 * excludes behaviour the two observations do not cover. tape_arm and
 * tape_reset_side_b refuse on stage-1 media instead — see engine/src/record.c.
 */

#include "tape_internal.h"
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
