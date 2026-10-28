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
   match. When the command will open the device for writing (need_write), our
   own partition 1, the only volume §5 lets stay mounted, is unmounted first:
   macOS refuses a read-write raw open of a disk with a mounted volume. Prints
   the refusal and returns EXIT_REFUSE, or returns 0. Nothing is written. */
int target_safety(const char *path, int provision, const char *erase, int need_write);

/* target_safety, also saying which rule refused (*why) and whether the refusal
   was a failed unmount of our own partition 1 (*unmount_failed). make's report. */
int target_safety_why(const char *path, int provision, const char *erase, int need_write,
                      enum refusal *why, int *unmount_failed);

/* make (APP-1 §3): bind the engine to partition 2 of a target whose device is
   ALREADY open in t->hp, without opening anything. Same recognition as
   target_open / target_open_verify; the verify binding has a NULL write. */
int target_bind_write(struct target *t, const char *path);
int target_bind_verify(struct target *t, const char *path, unsigned *findings, int *have_view);

/* Open for an engine command: safety for a device, then the §2 recognition.
   A device that is not an exact §3.1 layout is NOT_PROVISIONED (exit 2).
   writable = 0 binds a NULL write callback. Returns 0 or an exit code. */
int target_open(struct target *t, const char *path, int writable);

/* verify's open (ADR-164/165): read-only. A candidate MBR (the target-kind
   rule in layout.h) is reported through *findings instead of being refused.
   *have_view says whether a partition-2 view could be formed for the engine. */
int target_open_verify(struct target *t, const char *path, unsigned *findings, int *have_view);

int target_close(struct target *t);

#ifdef TAPECTL_INTERNAL_COMPOSE
/* Test-only borrowed-session binding; caller owns prior authorization and close. */
int target_borrow_write(struct target *, const char *);
int target_borrow_verify(struct target *, const char *, unsigned *, int *);
#endif

#endif /* TAPECTL_TARGET_H */
