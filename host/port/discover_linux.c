/*
 * discover_linux.c — cards enumeration on Linux (CI only; APP-1A §5).
 *
 * Whole disks are /sys/block entries. Facts come from sysfs, udev's database
 * (/run/udev/data), /proc/self/mountinfo and /proc/swaps; device nodes are
 * stat()ed, never opened. Anything those files do not say stays unknown.
 */

#if defined(__linux__)

#define _GNU_SOURCE

#include "discover.h"
#include "safety.h"

#include <dirent.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

/* Paths are built with bounded snprintf. A name too long to fit only makes a
   sysfs or udev lookup fail, and a failed lookup leaves that fact unknown,
   which never makes a disk a candidate. */
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC diagnostic ignored "-Wformat-truncation"
#endif

static int read_line(const char *path, char *out, size_t cap)
{
    FILE *fp = fopen(path, "re");
    size_t n;
    if (fp == NULL) { return -1; }
    if (fgets(out, (int)cap, fp) == NULL) { fclose(fp); return -1; }
    fclose(fp);
    n = strlen(out);
    while (n > 0 && (out[n - 1] == '\n' || out[n - 1] == ' ')) { out[--n] = '\0'; }
    return 0;
}

/* KEY's value in udev's record for block device M:m, or -1. */
static int udev_prop(const char *devnum, const char *key, char *out, size_t cap)
{
    char path[96], line[512];
    size_t klen = strlen(key);
    FILE *fp;
    int found = -1;
    snprintf(path, sizeof path, "/run/udev/data/b%s", devnum);
    fp = fopen(path, "re");
    if (fp == NULL) { return -1; }
    while (found < 0 && fgets(line, sizeof line, fp) != NULL) {
        line[strcspn(line, "\n")] = '\0';
        if (strncmp(line, "E:", 2) == 0 && strncmp(line + 2, key, klen) == 0 && line[2 + klen] == '=') {
            snprintf(out, cap, "%s", line + 3 + klen);
            found = 0;
        }
    }
    fclose(fp);
    return found;
}

/* The disk a non-stacked block device `name` sits on (itself for a whole disk). */
static int parent_disk(const char *name, char *out, size_t cap)
{
    char path[PATH_MAX], real[PATH_MAX], *slash;
    snprintf(path, sizeof path, "/sys/class/block/%s/partition", name);
    if (access(path, F_OK) != 0) {
        snprintf(path, sizeof path, "/sys/block/%s", name);
        if (access(path, F_OK) != 0) { return -1; }
        snprintf(out, cap, "%s", name);
        return 0;
    }
    snprintf(path, sizeof path, "/sys/class/block/%s", name);
    if (realpath(path, real) == NULL) { return -1; }
    slash = strrchr(real, '/');
    if (slash == NULL) { return -1; }
    *slash = '\0';
    slash = strrchr(real, '/');
    if (slash == NULL) { return -1; }
    snprintf(out, cap, "%s", slash + 1);
    return 0;
}

static int devnum_name(unsigned maj, unsigned min, char *out, size_t cap)
{
    char link[64], target[PATH_MAX];
    const char *base;
    ssize_t n;
    snprintf(link, sizeof link, "/sys/dev/block/%u:%u", maj, min);
    n = readlink(link, target, sizeof target - 1);
    if (n <= 0) { return -1; }
    target[n] = '\0';
    base = strrchr(target, '/');
    snprintf(out, cap, "%s", base ? base + 1 : target);
    return 0;
}

static void unescape_octal(char *s)
{
    char *d = s;
    while (*s) {
        if (s[0] == '\\' && s[1] >= '0' && s[1] <= '7' && s[2] && s[3]) {
            *d++ = (char)(((s[1] - '0') << 6) | ((s[2] - '0') << 3) | (s[3] - '0'));
            s += 4;
        } else {
            *d++ = *s++;
        }
    }
    *d = '\0';
}

static int is_system_mount(const char *where)
{
    return strcmp(where, "/") == 0 || strcmp(where, "/boot") == 0 || strcmp(where, "/boot/efi") == 0
        || strcmp(where, "/usr") == 0 || strcmp(where, "/var") == 0;
}

/* Mount and swap facts, gathered once for all disks. */
struct mnt { char disk[64]; char name[64]; int system; };
static struct mnt g_mnt[256];
static int g_nmnt, g_mnt_unknown, g_os_unresolved;

static int record_use(const char *disk, const char *name, int system)
{
    if (g_nmnt >= (int)(sizeof g_mnt / sizeof g_mnt[0])) { return -1; }
    snprintf(g_mnt[g_nmnt].disk, sizeof g_mnt[0].disk, "%s", disk);
    snprintf(g_mnt[g_nmnt].name, sizeof g_mnt[0].name, "%s", name);
    g_mnt[g_nmnt].system = system;
    g_nmnt++;
    return 0;
}

/* Record a use of block device `name` on every disk beneath it: a stacked
   (dm/md) device's uses are its slaves', down to partitions or whole disks.
   -1 when any link of the stack cannot be resolved or recorded. */
static int resolve_use(const char *name, int system, int depth)
{
    char path[PATH_MAX], disk[64];
    DIR *dir;
    struct dirent *de;
    int any = 0, bad = 0;
    snprintf(path, sizeof path, "/sys/class/block/%s", name);
    if (access(path, F_OK) != 0) { return -1; }
    snprintf(path, sizeof path, "/sys/class/block/%s/slaves", name);
    dir = opendir(path);
    if (dir != NULL) {
        while ((de = readdir(dir)) != NULL) {
            if (de->d_name[0] == '.') { continue; }
            any = 1;
            if (depth >= 8 || DISC_FAULT("linux.stack_unresolved") || resolve_use(de->d_name, system, depth + 1) != 0) {
                bad = 1;
            }
        }
        closedir(dir);
    }
    if (any) { return bad ? -1 : 0; }
    if (parent_disk(name, disk, sizeof disk) != 0) { return -1; }
    return record_use(disk, name, system);
}

static void add_use(const char *name, int system)
{
    /* Unresolvable: a system use makes every disk's OS use unknown, any other
       every disk's mount facts (it may be on any of them). */
    if (resolve_use(name, system, 0) != 0) {
        if (system) { g_os_unresolved = 1; }
        g_mnt_unknown = 1;
    }
}

/* The block device named by mountinfo's mount source, for a mount whose
   major:minor is not one (btrfs, for instance). 1 found, 0 not a device path,
   -1 a device path that cannot be resolved. */
static int source_device(const char *line, char *name, size_t cap)
{
    const char *sep = strstr(line, " - ");
    char src[1024];
    struct stat st;
    if (sep == NULL || sscanf(sep + 3, "%*s %1023s", src) != 1) { return -1; }
    unescape_octal(src);
    if (strncmp(src, "/dev/", 5) != 0) { return 0; }
    if (stat(src, &st) != 0 || !S_ISBLK(st.st_mode)) { return -1; }
    return devnum_name(major(st.st_rdev), minor(st.st_rdev), name, cap) == 0 ? 1 : -1;
}

static int gather_uses(char *err, size_t cap)
{
    char line[4096];
    FILE *fp = fopen("/proc/self/mountinfo", "re");
    int root_seen = 0;
    if (fp == NULL) { snprintf(err, cap, "/proc/self/mountinfo: %s", strerror(errno)); return -1; }
    while (fgets(line, sizeof line, fp) != NULL) {
        unsigned maj = 0, min = 0;
        char where[1024], name[64];
        if (sscanf(line, "%*s %*s %u:%u %*s %1023s", &maj, &min, where) != 3) { continue; }
        unescape_octal(where);
        if (devnum_name(maj, min, name, sizeof name) != 0) {
            int found = source_device(line, name, sizeof name);
            if (found < 0) {
                if (is_system_mount(where)) { g_os_unresolved = 1; }
                g_mnt_unknown = 1;
                continue;
            }
            if (found == 0) {
                if (is_system_mount(where)) { g_os_unresolved = 1; }
                continue;                            /* not a block device (tmpfs, proc, ...) */
            }
        }
        if (strcmp(where, "/") == 0) { root_seen = 1; }
        add_use(name, is_system_mount(where));
    }
    fclose(fp);
    if (!root_seen) { g_os_unresolved = 1; }
    fp = fopen("/proc/swaps", "re");
    if (fp == NULL) { g_os_unresolved = 1; return 0; }
    if (fgets(line, sizeof line, fp) != NULL) {
        while (fgets(line, sizeof line, fp) != NULL) {
            char spath[1024], name[64];
            struct stat ss;
            if (sscanf(line, "%1023s", spath) != 1) { continue; }
            unescape_octal(spath);
            if (stat(spath, &ss) != 0) { g_os_unresolved = 1; continue; }
            if (devnum_name(S_ISBLK(ss.st_mode) ? major(ss.st_rdev) : major(ss.st_dev),
                            S_ISBLK(ss.st_mode) ? minor(ss.st_rdev) : minor(ss.st_dev), name, sizeof name) != 0) {
                g_os_unresolved = 1;
                continue;
            }
            add_use(name, 1);
        }
    }
    fclose(fp);
    return 0;
}

static int is_virtual_name(const char *n)
{
    return strncmp(n, "loop", 4) == 0 || strncmp(n, "nbd", 3) == 0 || strncmp(n, "zram", 4) == 0
        || strncmp(n, "ram", 3) == 0 || strncmp(n, "dm-", 3) == 0 || strncmp(n, "md", 2) == 0;
}

static void facts(const char *disk, struct disc_disk *d)
{
    char sys[PATH_MAX], line[256], real[PATH_MAX], devnum[32], val[64];
    struct stat st;
    DIR *dir;
    struct dirent *de;
    int i;

    discover_init(d);
    snprintf(d->path, sizeof d->path, "/dev/%s", disk);
    snprintf(sys, sizeof sys, "/sys/block/%s/dev", disk);
    if (read_line(sys, devnum, sizeof devnum) != 0) { return; }
    if (stat(d->path, &st) == 0 && S_ISBLK(st.st_mode)) {
        char want[32];
        snprintf(want, sizeof want, "%u:%u", major(st.st_rdev), minor(st.st_rdev));
        d->whole = (strcmp(want, devnum) == 0 && path_is_whole_form(d->path)) ? DISC_YES : DISC_NO;
    }
    snprintf(sys, sizeof sys, "/sys/block/%s", disk);
    if (realpath(sys, real) != NULL) {
        d->is_virtual = (strstr(real, "/devices/virtual/") != NULL || is_virtual_name(disk)) ? DISC_YES : DISC_NO;
        if (strstr(real, "/mmc_host/") != NULL) { d->removable_or_sd = DISC_YES; }
    }
    if (d->removable_or_sd != DISC_YES) {
        snprintf(sys, sizeof sys, "/sys/block/%s/removable", disk);
        if (read_line(sys, line, sizeof line) == 0) { d->removable_or_sd = strcmp(line, "1") == 0 ? DISC_YES : DISC_NO; }
    }
    snprintf(sys, sizeof sys, "/sys/block/%s/size", disk);
    if (read_line(sys, line, sizeof line) == 0) {
        d->bytes = strtoull(line, NULL, 10) * 512ull;
        d->bytes_known = 1;
    }
    if (udev_prop(devnum, "ID_PART_TABLE_TYPE", val, sizeof val) == 0) {
        d->mbr = strcmp(val, "dos") == 0 ? DISC_YES : DISC_NO;
    }

    /* Partitions: sysfs gives index, start and size; udev gives the type byte. */
    snprintf(sys, sizeof sys, "/sys/block/%s", disk);
    dir = opendir(sys);
    if (dir != NULL) {
        d->n_parts = 0;
        while ((de = readdir(dir)) != NULL) {
            char p[PATH_MAX], pdev[32];
            struct disc_part *q;
            if (strncmp(de->d_name, disk, strlen(disk)) != 0) { continue; }
            snprintf(p, sizeof p, "%s/%s/partition", sys, de->d_name);
            if (read_line(p, line, sizeof line) != 0) { continue; }
            if (d->n_parts >= DISC_MAX_PARTS) { d->n_parts = DISC_UNKNOWN; break; }
            q = &d->parts[d->n_parts++];
            q->index = atoi(line);
            q->type = DISC_UNKNOWN;
            q->start = q->length = DISC_UNKNOWN;
            q->mounted = DISC_NO;
            snprintf(p, sizeof p, "%s/%s/start", sys, de->d_name);
            if (read_line(p, line, sizeof line) == 0) { q->start = (int64_t)strtoll(line, NULL, 10) * 512; }
            snprintf(p, sizeof p, "%s/%s/size", sys, de->d_name);
            if (read_line(p, line, sizeof line) == 0) { q->length = (int64_t)strtoll(line, NULL, 10) * 512; }
            snprintf(p, sizeof p, "%s/%s/dev", sys, de->d_name);
            if (read_line(p, pdev, sizeof pdev) == 0 && udev_prop(pdev, "ID_PART_ENTRY_TYPE", val, sizeof val) == 0) {
                q->type = (int)strtol(val, NULL, 16);
                snprintf(q->hint, sizeof q->hint, "%s", val);
            }
            for (i = 0; i < g_nmnt; i++) {
                if (strcmp(g_mnt[i].name, de->d_name) == 0) { q->mounted = DISC_YES; }
            }
            if (g_mnt_unknown) { q->mounted = DISC_UNKNOWN; }
        }
        closedir(dir);
    }

    /* Uses of this disk: mounts (whole-disk or partition) and swap. */
    d->n_mounted = 0;
    d->holds_os = DISC_NO;
    d->mounted_unattributed = DISC_NO;
    for (i = 0; i < g_nmnt; i++) {
        if (strcmp(g_mnt[i].disk, disk) != 0) { continue; }
        d->n_mounted++;
        if (g_mnt[i].system) { d->holds_os = DISC_YES; }
        if (strcmp(g_mnt[i].name, disk) == 0) { d->mounted_unattributed = DISC_YES; }
    }
    if (g_mnt_unknown) { d->n_mounted = DISC_UNKNOWN; d->mounted_unattributed = DISC_UNKNOWN; }
    if (g_os_unresolved && d->holds_os != DISC_YES) { d->holds_os = DISC_UNKNOWN; }
}

int discover_enumerate(disc_each each, void *ctx, char *err, size_t cap)
{
    DIR *dir;
    struct dirent *de;
    char names[DISC_MAX_DISKS][64];
    int n = 0, i, j;

    g_nmnt = g_mnt_unknown = g_os_unresolved = 0;
    dir = opendir("/sys/block");
    if (dir == NULL) { snprintf(err, cap, "/sys/block: %s", strerror(errno)); return -1; }
    while ((de = readdir(dir)) != NULL) {
        if (de->d_name[0] == '.') { continue; }
        if (n >= DISC_MAX_DISKS) { closedir(dir); snprintf(err, cap, "more than %d disks", DISC_MAX_DISKS); return -1; }
        snprintf(names[n++], sizeof names[0], "%s", de->d_name);
    }
    closedir(dir);
    /* readdir order is arbitrary: list in name order, so output is stable. */
    for (i = 1; i < n; i++) {
        for (j = i; j > 0 && strcmp(names[j - 1], names[j]) > 0; j--) {
            char t[64];
            memcpy(t, names[j], sizeof t); memcpy(names[j], names[j - 1], sizeof t); memcpy(names[j - 1], t, sizeof t);
        }
    }
    if (gather_uses(err, cap) != 0) { return -1; }
    for (i = 0; i < n; i++) {
        struct disc_disk d;
        facts(names[i], &d);
        each(ctx, &d, i + 1, n);
    }
    return 0;
}

#endif /* __linux__ */
