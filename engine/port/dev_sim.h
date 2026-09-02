/*
 * dev_sim.h — pass-through block device with observable counters.
 *
 * THIS IS NOT A FAULT INJECTOR. It used to be, and that was a defect.
 *
 * Its power-loss and torn-write modes were deleted per PM Decisions 004 §4 and
 * ADR-025. The reason generalises, so it is written here rather than only in
 * the ADR:
 *
 *   The old model treated every completed write as durable. But tapefs §8's
 *   whole safety argument is an ORDERING over flushes -- chunks, flush,
 *   entries, flush, header, flush -- and §13 lists "a flush that returns
 *   success means data has reached media" as an ASSUMPTION, not a fact.
 *
 *   A simulator in which writes are always durable is structurally incapable of
 *   failing any test that depends on a flush having actually happened. It would
 *   have reported the commit ordering as safe whether or not it was. The
 *   verifier found exactly that class of defect in DRAFT-1 by reading (V-004: a
 *   commit protocol with no final flush) -- a defect this simulator could never
 *   have caught, no matter how many cases were run through it.
 *
 * The single fault injector is now the Verification Lead's
 * tests/crash/fault_block_device.[ch], which models flush-required durability
 * and write-through as selectable modes, and so brackets the contract instead of
 * assuming one half of it.
 *
 * What remains here is a pass-through that counts operations. That is genuinely
 * useful -- tape_render performing zero block-device calls is engine-api
 * invariant 12, and counting is how you assert it -- and it makes no claim about
 * durability at all.
 */

#ifndef TAPE_PORT_DEV_SIM_H
#define TAPE_PORT_DEV_SIM_H

#include "port.h"

struct tape_dev_sim {
    const tape_dev *inner;
    uint32_t writes_seen;
    uint32_t reads_seen;
    uint32_t flushes_seen;
};

/*
 * Bind a counter over `inner`. Writable only if `inner` is: wrapping the source
 * slot must not manufacture a write path that guardrail 06 says does not exist.
 */
void tape_dev_sim_bind(struct tape_dev_sim *st, tape_dev *dev, const tape_dev *inner);

/* Zero the counters. */
void tape_dev_sim_reset(struct tape_dev_sim *st);

#endif /* TAPE_PORT_DEV_SIM_H */
