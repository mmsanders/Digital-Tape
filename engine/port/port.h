/*
 * port.h — shared definitions for the block-device ports.
 *
 * spec/engine-api.md §3: "Callbacks return 0 on success, non-zero on failure."
 * They do NOT return tape_result — that is the engine's vocabulary, and the
 * engine maps any non-zero to TAPE_DEV_ERR_IO. These codes are the ports' own, so a
 * port can distinguish its failures for its own tests without inventing engine
 * error codes the spec does not define.
 */

#ifndef TAPE_PORT_H
#define TAPE_PORT_H

#include "tape_dev.h"

#define TAPE_DEV_OK                   0
#define TAPE_DEV_ERR_IO               1
#define TAPE_DEV_ERR_RANGE            2
#define TAPE_DEV_ERR_NOT_IMPLEMENTED  3

#endif /* TAPE_PORT_H */
