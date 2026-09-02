/*
 * dev_sd.h — SD block device.
 *
 * NOT IMPLEMENTED, deliberately. There is no SD peripheral in a desktop build
 * and no board yet; the real implementation lands with Stream 4 (WP-17, Teensy
 * USDHC1) and Stream 5 (WP-28, dual USDHC with UHS-I bring-up).
 *
 * This header exists now so the shape of the seam is fixed before firmware
 * arrives: whatever the peripheral turns out to need — DMA alignment, a 1.8 V
 * switch sequence, tuned delay lines — it is absorbed here, behind the same
 * three callbacks. Nothing about UHS-I reaches the engine (guardrail 09).
 *
 * The stub returns TAPE_ERR_NOT_IMPLEMENTED rather than pretending, so a build
 * that accidentally links it fails loudly instead of silently reading zeroes.
 */

#ifndef TAPE_PORT_DEV_SD_H
#define TAPE_PORT_DEV_SD_H

#include "tape_dev.h"

struct tape_dev_sd {
    unsigned slot;      /* 0 = source (left, read-only), 1 = work (right) */
    uint32_t block_count;
};

/*
 * Slot 0 is bound with write == NULL. Guardrail 06: the source slot has no
 * write function — not a permission check, not an `if`. The firmware that fills
 * this in must preserve that, and tests/fuzz (WP-36) asserts no transport input
 * sequence produces a write transaction on slot 0.
 */
int tape_dev_sd_bind(struct tape_dev_sd *st, struct tape_dev *dev, unsigned slot);

#endif /* TAPE_PORT_DEV_SD_H */
