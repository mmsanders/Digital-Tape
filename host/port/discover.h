/*
 * discover.h — `tapectl cards`: read-only candidate discovery (APP-1A §5, S2).
 *
 * Normative: docs/WP15-APP-ANNEX.md §3 (cards IDs) and §5, docs/WP15-APP-CONTRACT.md §3.
 * A platform enumerator (discover_<os>.c) lists whole disks and the OS's view of
 * them using enumeration and zero-access queries only: no device is opened for
 * reading or writing, nothing is written and nothing is unmounted. Every fact it
 * cannot establish is DISC_UNKNOWN. discover_policy() is a pure function of the
 * facts. Discovery is a candidate hint only: `make` repeats the exact WP-14 §5 and
 * §2 checks before any write, and nothing here authorizes a device.
 */

#ifndef HOST_DISCOVER_H
#define HOST_DISCOVER_H

#include <stddef.h>
#include <stdint.h>

#define DISC_NO       0
#define DISC_YES      1
#define DISC_UNKNOWN (-1)

#define DISC_MAX_PARTS 8
#define DISC_MAX_DISKS 64

struct disc_part {
    int index;                /* MBR entry 1..4, as the OS numbers it */
    int type;                 /* MBR partition type byte, or DISC_UNKNOWN */
    int64_t start;            /* first 512-byte sector, or DISC_UNKNOWN */
    int64_t sectors;          /* length in 512-byte sectors, or DISC_UNKNOWN */
    int mounted;              /* tri-state */
    char hint[32];            /* the OS's own type text, as given (observation only) */
};

struct disc_disk {
    char path[64];            /* the whole-disk path make would be given */
    uint64_t bytes;           /* capacity; 0 when the OS gives none */
    int bytes_known;
    int whole;                /* tri-state: a whole disk in the WP-14 §2 path form */
    int removable_or_sd;      /* tri-state: removable media, or an SD/MMC-class bus */
    int is_virtual;           /* tri-state: an image, VHD, loop or other virtual disk */
    int holds_os;             /* tri-state: system, boot or swap use */
    int mbr;                  /* tri-state: the OS reports MBR partitioning */
    int n_parts;              /* partitions in the OS view, or DISC_UNKNOWN */
    struct disc_part parts[DISC_MAX_PARTS];
    int n_mounted;            /* mounted volumes on the disk, or DISC_UNKNOWN */
    int mounted_unattributed; /* tri-state: a mounted volume not tied to a listed partition */
};

enum disc_verdict { DISC_REFUSE = 0, DISC_OFFER, DISC_UNPROBED };

/* APP-1A §5. A known refusing fact refuses (the disk is never listed or
   counted). Otherwise an unknown required fact makes the disk unprobed, never
   safe. Otherwise it is offered. */
enum disc_verdict discover_policy(const struct disc_disk *d);

/* The platform enumerator. Calls `each` once per whole disk the OS lists, in a
   stable order, with that disk's 1-based position and the number of disks
   listed. Returns 0, or -1 with the OS's reason in `err` when the enumeration
   itself fails (CARDS_ENUM_UNAVAILABLE). */
typedef void (*disc_each)(void *ctx, const struct disc_disk *d, int done, int total);
int discover_enumerate(disc_each each, void *ctx, char *err, size_t cap);

/* A fresh record with every fact unknown. */
void discover_init(struct disc_disk *d);

#ifdef TAPECTL_TEST
/* Test seam (discover_test.c): TAPECTL_TEST_CARDS names a file of
   `PATH key=value ...` lines whose keys replace facts of that real enumerated
   disk. Compiled only into tapectl-test. */
void tapectl_test_cards_seam(struct disc_disk *d);
#endif

#endif /* HOST_DISCOVER_H */
