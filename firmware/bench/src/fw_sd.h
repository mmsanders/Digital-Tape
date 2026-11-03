/*
 * fw_sd.h — the Teensy 4.1 built-in microSD slot (SDIO) as a whole-card tape_dev.
 *
 * Normative: docs/WP17-FIRMWARE-CONTRACT.md §4, spec/engine-api.md §3. This is
 * the card below the partition view (fw_part.h): block 0 is the MBR. It is the
 * WP-17 work slot, so it binds `write`. The read-only source slot, with
 * write == NULL, arrives with WP-18.
 */

#ifndef FW_SD_H
#define FW_SD_H

#include "tape_dev.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Start the card and bind `card`. Returns 0, or -1 if no card answered. */
int fw_sd_begin(tape_dev *card);

/* Is the card still answering? A failed status poll means it was pulled. */
int fw_sd_present(void);

#ifdef __cplusplus
}
#endif

#endif /* FW_SD_H */
