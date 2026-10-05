/*
 * target.h — what tapectl opens: a bare image, a provisioned image or a device.
 *
 * Normative: docs/WP14-CLI-CONTRACT.md §2 (targets), §5 (disk safety) and §6
 * (the port). Every engine command goes through target_open(), so a device
 * passes the §5 rules before any write-mode open, and the engine only ever
 * sees partition 2 of a provisioned target.
 */

#ifndef TAPECTL_TARGET_H
#define TAPECTL_TARGET_H

#include "hport.h"
#include "safety.h"

#define EXIT_ENGINE  1
#define EXIT_USAGE   2
#define EXIT_REFUSE  3

struct target {
    struct hport hp;
    struct partview view;
    tape_dev dev;             /* what the engine is given */
    int is_device;
    int provisioned;          /* the engine sees partition 2 */
    uint64_t sectors;         /* whole target, 512-byte sectors */
    int open;
};

/* Is `path` a device (by §2 form or by what the OS says it is)? */
int target_names_device(const char *path);

/* The §5 rules for a device path. provision != 0 also requires --erase to
   match, and unmounts partition 1 if it is the only mounted volume. Prints the
   refusal and returns EXIT_REFUSE, or returns 0. Nothing is written. */
int target_safety(const char *path, int provision, const char *erase);

/* Open for an engine command: safety for a device, then the §2 recognition.
   A device that is not an exact §3.1 layout is NOT_PROVISIONED (exit 2).
   writable = 0 binds a NULL write callback. Returns 0 or an exit code. */
int target_open(struct target *t, const char *path, int writable);

/* verify's open (#384 Q3): read-only, and an MBR-shaped near miss is reported
   through *mbr_findings instead of being refused. *have_view says whether a
   partition-2 view could be formed for the engine checks. */
int target_open_verify(struct target *t, const char *path, unsigned *findings, int *have_view);

int target_close(struct target *t);

#endif /* TAPECTL_TARGET_H */
