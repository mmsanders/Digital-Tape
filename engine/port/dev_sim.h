/*
 * dev_sim.h — fault-injecting block device.
 *
 * Wraps another tape_dev and misbehaves on demand. This is the substrate WP-10
 * needs: a child yanking a cartridge mid-write is a power loss at an arbitrary
 * write boundary, and proving that cannot destroy a cartridge means being able
 * to cut power at *every* boundary rather than a sampled few.
 *
 * Division of labour: this port provides the capability. The crash-injection
 * harness that drives it exhaustively, and decides what "still mounts" means,
 * is the Verification Lead's (tests/crash/, WP-10). Do not write that here.
 *
 * Two failure shapes, because they are genuinely different:
 *
 *   POWER LOSS   after N block-writes the device stops accepting writes and
 *                returns TAPE_DEV_ERR_IO forever. Blocks already written stay
 *                written. This models the plug being pulled.
 *
 *   TORN WRITE   the Nth write lands partially: `torn_bytes` of the block are
 *                written, the rest keeps its previous content, and power is
 *                then lost. Real flash does not guarantee block atomicity, and
 *                a commit protocol that assumes it is untested against the
 *                thing it claims to survive.
 */

#ifndef TAPE_PORT_DEV_SIM_H
#define TAPE_PORT_DEV_SIM_H

#include "port.h"

enum tape_sim_mode {
    TAPE_SIM_HEALTHY = 0,
    TAPE_SIM_POWER_LOSS,
    TAPE_SIM_TORN_WRITE
};

struct tape_dev_sim {
    const tape_dev *inner;

    enum tape_sim_mode mode;
    uint32_t fail_after_writes;  /* writes allowed before the fault */
    uint32_t torn_bytes;         /* TORN_WRITE: bytes of the block that land */

    /* Observable by the harness. */
    uint32_t writes_seen;
    uint32_t reads_seen;
    uint32_t flushes_seen;
    int      dead;               /* nonzero once the fault has fired */
};

/*
 * Bind a simulator over `inner`. The simulator is writable only if `inner` is:
 * wrapping the source slot must not manufacture a write path that guardrail 06
 * says does not exist.
 */
void tape_dev_sim_bind(struct tape_dev_sim *st, tape_dev *dev,
                       const tape_dev *inner);

void tape_dev_sim_arm(struct tape_dev_sim *st, enum tape_sim_mode mode,
                      uint32_t fail_after_writes, uint32_t torn_bytes);

/* Back to healthy, counters preserved. */
void tape_dev_sim_revive(struct tape_dev_sim *st);

#endif /* TAPE_PORT_DEV_SIM_H */
