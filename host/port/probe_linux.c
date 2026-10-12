/*
 * probe_linux.c — device facts on Linux (CI only; docs/WP14-CLI-CONTRACT.md §2, §5).
 *
 * Everything comes from sysfs and /proc. Nothing is opened for write; LBA 0 is
 * read through a read-only open, and only to test the partition-1 exception.
 * A fact the probe cannot establish keeps its refusing value.
 */

#if defined(__linux__)

#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64

#include "safety.h"
#include "layout.h"

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

/* Bounded copy; -1 (and an empty string) if `src` does not fit. */
static int copy_str(char *dst, size_t cap, const char *src)
{
    size_t n = strlen(src);
    if (n >= cap) { dst[0] = '\0'; return -1; }
    memcpy(dst, src, n + 1);
    return 0;
}

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

/* Block device name for a dev_t, via /sys/dev/block/M:m. */
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
    base = base ? base + 1 : target;
    return copy_str(out, cap, base);
}

/* Does block device `name` sit on disk `disk`? Partitions resolve to their
   parent; device-mapper and md devices resolve through their slaves. */
static int backs(const char *name, const char *disk, int depth)
{
    char path[PATH_MAX], real[PATH_MAX], parent[PATH_MAX];
    char *slash;
    DIR *dir;
    struct dirent *de;
    int hit = 0;

    if (depth > 8) { return 1; }               /* unbounded stacking: assume yes */
    if (strcmp(name, disk) == 0) { return 1; }
    snprintf(path, sizeof path, "/sys/class/block/%s/partition", name);
    if (access(path, F_OK) == 0) {
        snprintf(path, sizeof path, "/sys/class/block/%s", name);
        if (realpath(path, real) == NULL) { return 1; }
        strcpy(parent, real);
        slash = strrchr(parent, '/');
        if (slash == NULL) { return 1; }
        *slash = '\0';
        slash = strrchr(parent, '/');
        return slash != NULL && strcmp(slash + 1, disk) == 0;
    }
    snprintf(path, sizeof path, "/sys/class/block/%s/slaves", name);
    dir = opendir(path);
    if (dir == NULL) { return 0; }             /* a plain whole disk with no slaves */
    while (!hit && (de = readdir(dir)) != NULL) {
        if (de->d_name[0] != '.' && backs(de->d_name, disk, depth + 1)) { hit = 1; }
    }
    closedir(dir);
    return hit;
}

static int partition_number(const char *name)
{
    char path[PATH_MAX], line[32];
    snprintf(path, sizeof path, "/sys/class/block/%s/partition", name);
    if (read_line(path, line, sizeof line)) { return 0; }
    return atoi(line);
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

int probe_device(const char *path, struct device_facts *f)
{
    char disk[64], sys[PATH_MAX], line[4096];
    struct stat st;
    FILE *mi;
    int root_resolved = 0, os_hit = 0;

    memset(f, 0, sizeof *f);
    f->holds_os = 1;
    /* The facts below are gathered for any /dev/<name> with a /sys/block
       entry, so `tapectl-test probe` can show them for a loop device; but only
       the §2 forms are ever a whole device to the policy. */
    if (strncmp(path, "/dev/", 5) != 0 || copy_str(disk, sizeof disk, path + 5) || strchr(disk, '/') != NULL) {
        snprintf(f->detail, sizeof f->detail, "%s is not /dev/sdX or /dev/mmcblkN", path);
        return 0;
    }
    snprintf(sys, sizeof sys, "/sys/block/%s/dev", disk);
    if (stat(path, &st) != 0 || !S_ISBLK(st.st_mode) || read_line(sys, line, sizeof line)) {
        snprintf(f->detail, sizeof f->detail, "%s is not a whole block device", path);
        return 0;
    }
    {
        char want[32];
        snprintf(want, sizeof want, "%u:%u", major(st.st_rdev), minor(st.st_rdev));
        if (strcmp(want, line) != 0) {
            snprintf(f->detail, sizeof f->detail, "%s does not match /sys/block/%s", path, disk);
            return 0;
        }
    }
    f->whole_device = path_is_whole_form(path);
    if (!f->whole_device) {
        snprintf(f->detail, sizeof f->detail, "%s is not /dev/sdX or /dev/mmcblkN", path);
    }

    snprintf(sys, sizeof sys, "/sys/block/%s/removable", disk);
    f->removable = read_line(sys, line, sizeof line) == 0 && strcmp(line, "1") == 0;
    /* ADR-164 §5: virtual media is never a card (a loop device is refused by
       its path form already; this keeps the fact honest for `probe`). */
    if (strncmp(disk, "loop", 4) == 0 || strncmp(disk, "nbd", 3) == 0 || strncmp(disk, "zram", 4) == 0
        || strncmp(disk, "ram", 3) == 0 || strncmp(disk, "dm-", 3) == 0) {
        f->removable = 0;
    }
    snprintf(sys, sizeof sys, "/sys/block/%s", disk);
    {
        char real[PATH_MAX];
        f->sd_bus = realpath(sys, real) != NULL && strstr(real, "/mmc_host/") != NULL;
    }
    snprintf(sys, sizeof sys, "/sys/block/%s/size", disk);
    if (read_line(sys, line, sizeof line) == 0) {
        f->bytes = strtoull(line, NULL, 10) * 512ull;
    } else {
        f->bytes = UINT64_MAX;
    }

    /* Mounts: the system ones decide holds_os, any on this disk are listed. */
    mi = fopen("/proc/self/mountinfo", "re");
    if (mi == NULL) {
        snprintf(f->detail, sizeof f->detail, "cannot read /proc/self/mountinfo");
        f->n_mounted = SAFETY_MAX_MOUNTS + 1;
        return 0;
    }
    while (fgets(line, sizeof line, mi) != NULL) {
        unsigned maj = 0, min = 0;
        char where[1024], name[64], source[1024] = "";
        char *dash;
        int on_disk = 0;
        if (sscanf(line, "%*s %*s %u:%u %*s %1023s", &maj, &min, where) != 3) { continue; }
        unescape_octal(where);
        dash = strstr(line, " - ");
        if (dash != NULL) { (void)sscanf(dash + 3, "%*s %1023s", source); }
        if (devnum_name(maj, min, name, sizeof name) == 0) {
            on_disk = backs(name, disk, 0);
        } else if (strncmp(source, "/dev/", 5) == 0) {
            (void)copy_str(name, sizeof name, source + 5);
            on_disk = backs(name, disk, 0);
        } else {
            name[0] = '\0';
        }
        if (strcmp(where, "/") == 0 && name[0]) { root_resolved = 1; }
        if (!on_disk) { continue; }
        if (is_system_mount(where)) { os_hit = 1; }
        if (f->n_mounted < SAFETY_MAX_MOUNTS) {
            struct mounted_volume *m = &f->mounted[f->n_mounted];
            m->partition = (strcmp(name, disk) == 0) ? 0 : partition_number(name);
            if (copy_str(m->where, sizeof m->where, where)) { memcpy(m->where, where, sizeof m->where - 1); m->where[sizeof m->where - 1] = '\0'; }
            f->n_mounted++;
        } else {
            f->n_mounted = SAFETY_MAX_MOUNTS + 1;
        }
    }
    fclose(mi);

    /* Swap on this disk, as a partition or a file on one of its volumes. */
    mi = fopen("/proc/swaps", "re");
    if (mi != NULL) {
        if (fgets(line, sizeof line, mi) != NULL) {
            while (fgets(line, sizeof line, mi) != NULL) {
                char spath[1024], name[64];
                struct stat ss;
                if (sscanf(line, "%1023s", spath) != 1) { continue; }
                unescape_octal(spath);
                if (stat(spath, &ss) != 0) { os_hit = 1; continue; }
                if (S_ISBLK(ss.st_mode)) {
                    if (devnum_name(major(ss.st_rdev), minor(ss.st_rdev), name, sizeof name) != 0
                        || backs(name, disk, 0)) { os_hit = 1; }
                } else if (devnum_name(major(ss.st_dev), minor(ss.st_dev), name, sizeof name) != 0
                           || backs(name, disk, 0)) {
                    os_hit = 1;
                }
            }
        }
        fclose(mi);
    } else {
        os_hit = 1;
    }

    if (!root_resolved) {
        snprintf(f->detail, sizeof f->detail, "cannot tell which disk holds /");
        return 0;                               /* holds_os stays 1 */
    }
    f->holds_os = os_hit;

    if (f->n_mounted > 0 && f->n_mounted <= SAFETY_MAX_MOUNTS) {
        uint8_t lba0[512];
        int fd = open(path, O_RDONLY | O_CLOEXEC);
        if (fd >= 0) {
            if (pread(fd, lba0, sizeof lba0, 0) == (ssize_t)sizeof lba0) {
                f->layout_ok = mbr_is_layout(lba0, f->bytes / 512u);
            }
            close(fd);
        }
    }
    return 0;
}

const char *probe_unmount_call(void) { return "umount2"; }

#ifdef TAPECTL_TEST
int probe_unmount_invalid(void)
{
    return umount2("", 0) == 0 ? 0 : -1;      /* ENOENT from the kernel */
}
#endif

int probe_unmount_p1(const char *path, const struct device_facts *f, int i)
{
    (void)path;
    if (!safety_mount_is_own_p1(f, i)) { return -1; }
    if (umount2(f->mounted[i].where, 0) == 0) { return 0; }
    /* Already gone (ejected since the probe, or unmounted by an earlier
       command): the goal, no mount, holds. EINVAL means "not a mount point". */
    return (errno == EINVAL || errno == ENOENT) ? 0 : -1;
}

#endif /* __linux__ */
