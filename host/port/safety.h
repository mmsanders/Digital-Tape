/*
 * safety.h — disk safety (A4): facts, then policy.
 *
 * Normative: docs/WP14-CLI-CONTRACT.md §5, which outranks everything else.
 * A platform probe (probe_*.c) gathers a device_facts record; safety_policy()
 * is a pure function of that record and decides. Nothing is written, and no
 * write-mode open happens, before the policy says yes.
 *
 * The TAPECTL_TEST seam (facts_test.c) replaces the probe with facts read from
 * a file. It is compiled only when TAPECTL_TEST is defined, into the test
 * binary; the shipped tapectl does not contain it.
 */

#ifndef HOST_SAFETY_H
#define HOST_SAFETY_H

#include <stdint.h>

#define SAFETY_MAX_MOUNTS 16
#define SAFETY_TOO_LARGE  (1ull << 37)   /* 128 GiB: §5 REFUSE_TOO_LARGE */

struct mounted_volume {
    int partition;            /* 1..4 when the OS says which MBR entry; 0 unknown */
    char where[160];          /* mount point or volume name, for the message */
};

struct device_facts {
    int whole_device;         /* §2 platform form AND the OS says a whole disk */
    int removable;            /* OS: removable media */
    int sd_bus;               /* OS: an SD/MMC-class bus */
    uint64_t bytes;           /* capacity */
    int holds_os;             /* a partition holds the running OS, a boot volume or swap */
    int layout_ok;            /* LBA 0 is the exact §3.1 layout (read-only probe) */
    int n_mounted;            /* mounted volumes on this disk */
    struct mounted_volume mounted[SAFETY_MAX_MOUNTS];
    char detail[256];         /* the probe's own explanation, for the message */
};

enum refusal {
    REFUSE_NONE = 0,
    REFUSE_NOT_WHOLE_DEVICE,
    REFUSE_NOT_REMOVABLE,
    REFUSE_TOO_LARGE,
    REFUSE_SYSTEM_DISK,
    REFUSE_FOREIGN_MOUNT,
    REFUSE_ERASE_NOT_CONFIRMED
};

/* §5, in its order. `provision` is non-zero for the provision command, and
   `erase_matches` says whether --erase repeated the device path exactly. */
enum refusal safety_policy(const struct device_facts *f, int provision, int erase_matches);

const char *refusal_id(enum refusal r);
const char *refusal_sentence(enum refusal r);

/* The one mounted volume tapectl may unmount: partition 1 of an exact layout. */
int safety_mount_is_own_p1(const struct device_facts *f, int i);

/* Platform probe. Fills `f` for `path` without writing or opening for write.
   Returns 0; a probe that cannot establish a fact leaves it at its refusing
   value (not whole, not removable, holds the OS) and explains in f->detail. */
int probe_device(const char *path, struct device_facts *f);

/* Unmount partition 1 (mounted[i]) before provision rewrites it. 0 on success. */
int probe_unmount_p1(const char *path, const struct device_facts *f, int i);

/* The OS call probe_unmount_p1 makes, for the trace (e.g. "umount2"). */
const char *probe_unmount_call(void);

#ifdef TAPECTL_TEST
/* unmount-error control: the same OS unmount call, issued on an invalid
   target so the OS itself fails it. Returns -1 and leaves errno/last error. */
int probe_unmount_invalid(void);
#endif

/* §2 platform path forms. */
int path_is_device_form(const char *path);   /* anything shaped like a device path */
int path_is_whole_form(const char *path);    /* the accepted whole-disk form */

#ifdef TAPECTL_TEST
/* Test seam: TAPECTL_TEST_FACTS names a key=value file that replaces the probe.
   Returns 1 if the seam supplied facts, 0 if the variable is unset. */
int tapectl_test_facts_seam(const char *path, struct device_facts *f);
#endif

#endif /* HOST_SAFETY_H */
