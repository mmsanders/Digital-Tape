/*
 * raw_ops.c — bounded DRAFT-8 raw cartridge-operation tranche.
 *
 * This file implements only the independently published zero-write refusal
 * boundary in tests/format_dup_draft8:
 *
 *   - tape_format: §9.6 writability -> GEOMETRY_OK precedence;
 *   - tape_dup: §9.5 items 1..4, in their normative order.
 *
 * Raw-superblock classification, destructive construction, identity assignment,
 * crash closure and long-operation continuation are deliberately NOT implemented
 * by this tranche. Once every independently covered refusal has passed, these
 * entry points return TAPE_ERR_BUSY with zero callbacks/writes as an explicit
 * coverage hold rather than beginning an untested destructive path.
 *
 * Normative: spec/tapefs-v1.md §2.1, §9.5, §9.6; engine-api §9.
 */

#include "tape_internal.h"
#include "dev.h"

tape_result tape_format(const tape_dev *dev, const uint8_t uuid[16], uint32_t epoch,
                        const char *label, uint32_t nominal_length_s)
{
    uint32_t total_chunks;
    tape_result rc;

    /*
     * uuid/epoch/label belong to the success transaction and must not be
     * consulted before the refusal preconditions. In particular, a read-only
     * or impossible-geometry destination is refused without any media callback.
     */
    (void)uuid;
    (void)epoch;
    (void)label;

    if (dev == NULL) { return TAPE_ERR_INVALID_ARG; }

    /* §9.6 precondition order is normative. */
    if (dev->write == NULL) { return TAPE_ERR_READ_ONLY; }

    rc = tape_geometry_ok(nominal_length_s, dev->block_count, &total_chunks);
    if (rc != TAPE_OK) { return rc; }

    /*
     * COVERAGE HOLD, not a format result from the specification.
     * The next normative action is raw-superblock classification followed by
     * destructive construction. Those success/crash paths are explicitly
     * excluded from #156 and have no independent product evidence yet.
     */
    (void)total_chunks;
    return TAPE_ERR_BUSY;
}

tape_result tape_dup(tape *src, const tape_dev *dst_dev,
                     const uint8_t new_uuid[16], uint32_t epoch,
                     uint32_t dst_nominal_length_s,
                     uint32_t block_budget, bool *more_work,
                     tape_progress_fn cb, void *user)
{
    uint32_t dst_total_chunks;
    uint32_t need_chunks;
    uint64_t source_frames;
    tape_result rc;

    /*
     * These arguments are success/continuation inputs. The refusal tranche does
     * not inspect them except for the mandatory output pointer; doing so earlier
     * would change the normative §9.5 refusal precedence.
     */
    (void)new_uuid;
    (void)epoch;
    (void)block_budget;
    (void)cb;
    (void)user;

    if (src == NULL || dst_dev == NULL || more_work == NULL) {
        return TAPE_ERR_INVALID_ARG;
    }
    *more_work = false;

    /* Ordinary source-instance state gates. No destination callback occurs. */
    if (!src->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    if (src->faulted) { return TAPE_ERR_FAULTED; }
    if (src->rec_armed || src->promote_in_progress) { return TAPE_ERR_BUSY; }

    /*
     * §9.5 items 1..4 — exact normative order, all before any destination
     * superblock read and all with zero writes.
     */

    /* 1. Aliasing. tape_dev exposes ctx as the available device identity. */
    if (dev_same_context(&src->dev, dst_dev)) { return TAPE_ERR_INVALID_ARG; }

    /* 2. Destination writability. */
    if (dst_dev->write == NULL) { return TAPE_ERR_READ_ONLY; }

    /* 3. Destination geometry, including DEVICE_ADDRESSABLE. */
    rc = tape_geometry_ok(dst_nominal_length_s, dst_dev->block_count,
                          &dst_total_chunks);
    if (rc != TAPE_OK) { return rc; }

    /* 4. Side-A capacity. Mount has already validated the source timeline. */
    source_frames = src->idx[TAPE_SIDE_A].total_frames;
    need_chunks = tape_chunks_for_frames(source_frames);
    if (source_frames > (uint64_t)TAPE_MAX_TOTAL_FRAMES
        || need_chunks > dst_total_chunks) {
        return TAPE_ERR_DEST_TOO_SMALL;
    }

    /*
     * COVERAGE HOLD, not a duplicate result from the specification.
     * Raw destination classification and the destructive incremental copy /
     * identity-assignment transaction remain outside #156.
     */
    return TAPE_ERR_BUSY;
}
