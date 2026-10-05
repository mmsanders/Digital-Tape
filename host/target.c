/*
 * target.c — target recognition, disk safety and the partition view.
 * Normative: docs/WP14-CLI-CONTRACT.md §2, §4.1, §5, §6.
 */

#include "target.h"
#include "layout.h"

#include <stdio.h>
#include <string.h>

int target_names_device(const char *path)
{
    return path_is_device_form(path) || hport_classify(path) == HPORT_DEVICE;
}

static void gather_facts(const char *path, struct device_facts *f, int *seam)
{
    *seam = 0;
#ifdef TAPECTL_TEST
    if (tapectl_test_facts_seam(path, f)) { *seam = 1; return; }
#endif
    (void)probe_device(path, f);
}

int target_safety(const char *path, int provision, const char *erase)
{
    struct device_facts f;
    enum refusal r;
    int seam, i;

    gather_facts(path, &f, &seam);
    r = safety_policy(&f, provision, erase != NULL && strcmp(erase, path) == 0);
    if (r != REFUSE_NONE) {
        fprintf(stderr, "tapectl: %s: %s\n", refusal_id(r), refusal_sentence(r));
        if (f.detail[0]) { fprintf(stderr, "tapectl:   %s\n", f.detail); }
        if (r == REFUSE_FOREIGN_MOUNT) {
            for (i = 0; i < f.n_mounted && i < SAFETY_MAX_MOUNTS; i++) {
                if (!safety_mount_is_own_p1(&f, i)) { fprintf(stderr, "tapectl:   mounted: %s\n", f.mounted[i].where); }
            }
        }
        return EXIT_REFUSE;
    }
    /* provision rewrites partition 1, so its own volume comes off first (§5:
       "tapectl may unmount that one, and only that one"). Other commands never
       touch partition 1 and leave it mounted. */
    if (provision) {
        for (i = 0; i < f.n_mounted; i++) {
            int ok = seam ? 0 : probe_unmount_p1(path, &f, i);
            if (ok != 0) {
                fprintf(stderr, "tapectl: %s: cannot unmount partition 1 (%s). Eject it in the operating system first.\n",
                        refusal_id(REFUSE_FOREIGN_MOUNT), f.mounted[i].where);
                return EXIT_REFUSE;
            }
        }
    }
    return 0;
}

static int read_lba0(struct hport *p, uint8_t lba0[512])
{
    if (p->bytes < 512u) { memset(lba0, 0, 512); return 0; }
    return hport_read(p, 0, lba0, 512);
}

static int open_common(struct target *t, const char *path, int writable)
{
    memset(t, 0, sizeof *t);
    t->is_device = target_names_device(path);
    if (t->is_device) {
        int rc = target_safety(path, 0, NULL);
        if (rc) { return rc; }
    } else if (hport_classify(path) != HPORT_REGULAR) {
        fprintf(stderr, "tapectl: cannot open image %s\n", path);
        return EXIT_USAGE;
    }
    if (hport_open(&t->hp, path, t->is_device, writable) != 0) {
        fprintf(stderr, "tapectl: cannot open %s %s\n", t->is_device ? "device" : "image", path);
        return EXIT_USAGE;
    }
    t->open = 1;
    t->sectors = t->hp.bytes / 512u;
    return 0;
}

int target_open(struct target *t, const char *path, int writable)
{
    uint8_t lba0[512];
    int rc = open_common(t, path, writable);

    if (rc) { return rc; }
    if (read_lba0(&t->hp, lba0) != 0) {
        fprintf(stderr, "tapectl: cannot read %s\n", path);
        return EXIT_USAGE;
    }
    if (mbr_is_layout(lba0, t->sectors)) {
        uint32_t s2, n2;
        mbr_entry2(lba0, &s2, &n2);
        t->provisioned = 1;
        partview_bind(&t->view, &t->dev, &t->hp, s2, n2, writable);
        return 0;
    }
    if (t->is_device) {
        fprintf(stderr, "tapectl: NOT_PROVISIONED: %s is not a Digital Tape card. Use provision.\n", path);
        return EXIT_USAGE;
    }
    /* A bare WP-11 image is the TAPEFS partition itself. */
    if (t->sectors > 0xFFFFFFFFull) {
        fprintf(stderr, "tapectl: image %s is too large for a bare TAPEFS partition\n", path);
        return EXIT_USAGE;
    }
    partview_bind(&t->view, &t->dev, &t->hp, 0, (uint32_t)t->sectors, writable);
    return 0;
}

int target_open_verify(struct target *t, const char *path, unsigned *findings, int *have_view)
{
    uint8_t lba0[512];
    int rc = open_common(t, path, 0);

    *findings = 0;
    *have_view = 0;
    if (rc) { return rc; }
    if (read_lba0(&t->hp, lba0) != 0) {
        fprintf(stderr, "tapectl: cannot read %s\n", path);
        return EXIT_USAGE;
    }
    if (mbr_is_layout(lba0, t->sectors) || mbr_is_mbr_shaped(lba0)) {
        uint32_t s2, n2;
        *findings = mbr_is_layout(lba0, t->sectors) ? 0u : mbr_findings(lba0, t->sectors);
        mbr_entry2(lba0, &s2, &n2);
        t->provisioned = 1;
        if (s2 > 0 && n2 > 0 && s2 < t->sectors) {
            /* The engine is shown partition 2 as the card records it. A truncated
               partition's missing tail then reads as failed I/O. */
            partview_bind(&t->view, &t->dev, &t->hp, s2, n2, 0);
            *have_view = 1;
        }
        return 0;
    }
    if (t->is_device) {
        fprintf(stderr, "tapectl: NOT_PROVISIONED: %s is not a Digital Tape card. Use provision.\n", path);
        return EXIT_USAGE;
    }
    if (t->sectors > 0xFFFFFFFFull) {
        fprintf(stderr, "tapectl: image %s is too large for a bare TAPEFS partition\n", path);
        return EXIT_USAGE;
    }
    partview_bind(&t->view, &t->dev, &t->hp, 0, (uint32_t)t->sectors, 0);
    *have_view = 1;
    return 0;
}

int target_close(struct target *t)
{
    int rc = 0;
    if (t->open) { rc = hport_close(&t->hp); t->open = 0; }
    return rc;
}
