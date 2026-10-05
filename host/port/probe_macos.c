/*
 * probe_macos.c — device facts on macOS (docs/WP14-CLI-CONTRACT.md §2, §5).
 *
 * DiskArbitration describes the disk (whole, removable, protocol, size). The
 * IOKit registry answers "which physical disk is this mount on?": every mount
 * is walked up the service plane to the whole IOMedia beneath it, through
 * APFS containers and synthesized disks. Nothing is opened for write; LBA 0
 * is read through a read-only open, only for the partition-1 exception.
 */

#if defined(__APPLE__)

#include "safety.h"
#include "layout.h"

#include <CoreFoundation/CoreFoundation.h>
#include <DiskArbitration/DiskArbitration.h>
#include <IOKit/IOKitLib.h>

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/param.h>
#include <unistd.h>

/* BSD name ("disk4") from /dev/disk4 or /dev/rdisk4; the caller checked the form. */
static void bsd_name(const char *path, char *out, size_t cap)
{
    const char *p = path + 5;
    if (*p == 'r') { p++; }
    snprintf(out, cap, "%s", p);
}

static int cf_bool(CFDictionaryRef d, CFStringRef key)
{
    CFTypeRef v = CFDictionaryGetValue(d, key);
    return v != NULL && CFGetTypeID(v) == CFBooleanGetTypeID() && CFBooleanGetValue((CFBooleanRef)v);
}

static int cf_string_is(CFDictionaryRef d, CFStringRef key, const char *want)
{
    char buf[128];
    CFTypeRef v = CFDictionaryGetValue(d, key);
    if (v == NULL || CFGetTypeID(v) != CFStringGetTypeID()) { return 0; }
    if (!CFStringGetCString((CFStringRef)v, buf, sizeof buf, kCFStringEncodingUTF8)) { return 0; }
    return strcmp(buf, want) == 0;
}

static int registry_bool(io_registry_entry_t e, const char *key)
{
    CFStringRef k = CFStringCreateWithCString(NULL, key, kCFStringEncodingUTF8);
    CFTypeRef v = IORegistryEntryCreateCFProperty(e, k, NULL, 0);
    int r = v != NULL && CFGetTypeID(v) == CFBooleanGetTypeID() && CFBooleanGetValue((CFBooleanRef)v);
    if (v) { CFRelease(v); }
    CFRelease(k);
    return r;
}

static int registry_bsd(io_registry_entry_t e, char *out, size_t cap)
{
    CFTypeRef v = IORegistryEntryCreateCFProperty(e, CFSTR("BSD Name"), NULL, 0);
    int ok = v != NULL && CFGetTypeID(v) == CFStringGetTypeID()
             && CFStringGetCString((CFStringRef)v, out, (CFIndex)cap, kCFStringEncodingUTF8);
    if (v) { CFRelease(v); }
    return ok ? 0 : -1;
}

/* Is the mount whose device is `bsd` (e.g. disk3s1s1) on physical disk `disk`?
   Walks every service-plane ancestor and compares each whole IOMedia. Returns
   1 yes, 0 no, -1 could not tell. */
static int mount_on_disk(const char *bsd, const char *disk, int *synth_on_disk)
{
    io_service_t media;
    io_iterator_t it;
    io_registry_entry_t e;
    int hit = 0, saw_whole = 0;
    char name[64];

    *synth_on_disk = 0;
    media = IOServiceGetMatchingService(MACH_PORT_NULL, IOBSDNameMatching(MACH_PORT_NULL, 0, bsd));
    if (media == IO_OBJECT_NULL) { return -1; }
    if (registry_bsd(media, name, sizeof name) == 0 && strcmp(name, disk) == 0) { hit = 1; }
    if (IORegistryEntryCreateIterator(media, kIOServicePlane,
                                      kIORegistryIterateRecursively | kIORegistryIterateParents, &it) != KERN_SUCCESS) {
        IOObjectRelease(media);
        return -1;
    }
    while ((e = IOIteratorNext(it)) != IO_OBJECT_NULL) {
        if (IOObjectConformsTo(e, "IOMedia") && registry_bool(e, "Whole")) {
            saw_whole = 1;
            if (registry_bsd(e, name, sizeof name) == 0 && strcmp(name, disk) == 0) { hit = 1; }
        }
        IOObjectRelease(e);
    }
    IOObjectRelease(it);
    IOObjectRelease(media);
    if (hit && strncmp(bsd, disk, strlen(disk)) != 0) { *synth_on_disk = 1; }
    return (hit || saw_whole) ? hit : -1;
}

/* An APFS synthesized disk's IOMedia sits on an AppleAPFSContainer. */
static int is_synthesized(const char *disk)
{
    io_service_t media = IOServiceGetMatchingService(MACH_PORT_NULL, IOBSDNameMatching(MACH_PORT_NULL, 0, disk));
    io_iterator_t it;
    io_registry_entry_t e;
    int synth = 0;
    if (media == IO_OBJECT_NULL) { return 1; }
    if (IORegistryEntryCreateIterator(media, kIOServicePlane,
                                      kIORegistryIterateRecursively | kIORegistryIterateParents, &it) == KERN_SUCCESS) {
        while ((e = IOIteratorNext(it)) != IO_OBJECT_NULL) {
            if (IOObjectConformsTo(e, "AppleAPFSContainer")) { synth = 1; }
            IOObjectRelease(e);
        }
        IOObjectRelease(it);
    } else {
        synth = 1;
    }
    IOObjectRelease(media);
    return synth;
}

static int is_system_mount(const struct statfs *m)
{
    return (m->f_flags & MNT_ROOTFS) != 0 || strcmp(m->f_mntonname, "/") == 0
        || strncmp(m->f_mntonname, "/System/Volumes/", 16) == 0
        || strcmp(m->f_mntonname, "/private/var/vm") == 0;
}

int probe_device(const char *path, struct device_facts *f)
{
    char disk[64];
    DASessionRef session;
    DADiskRef dadisk;
    CFDictionaryRef desc;
    struct statfs *mnts = NULL;
    int n, i, unresolved = 0, os_hit = 0;

    memset(f, 0, sizeof *f);
    f->holds_os = 1;
    if (!path_is_whole_form(path)) {
        snprintf(f->detail, sizeof f->detail, "%s is not /dev/diskN or /dev/rdiskN", path);
        return 0;
    }
    bsd_name(path, disk, sizeof disk);

    session = DASessionCreate(kCFAllocatorDefault);
    if (session == NULL) { snprintf(f->detail, sizeof f->detail, "DiskArbitration unavailable"); return 0; }
    dadisk = DADiskCreateFromBSDName(kCFAllocatorDefault, session, disk);
    desc = dadisk ? DADiskCopyDescription(dadisk) : NULL;
    if (desc == NULL) {
        snprintf(f->detail, sizeof f->detail, "%s: no such disk", disk);
        if (dadisk) { CFRelease(dadisk); }
        CFRelease(session);
        return 0;
    }
    f->whole_device = cf_bool(desc, kDADiskDescriptionMediaWholeKey) && !is_synthesized(disk);
    f->removable = cf_bool(desc, kDADiskDescriptionMediaRemovableKey);
    f->sd_bus = cf_string_is(desc, kDADiskDescriptionDeviceProtocolKey, "Secure Digital");
    {
        CFTypeRef v = CFDictionaryGetValue(desc, kDADiskDescriptionMediaSizeKey);
        long long sz = 0;
        if (v && CFGetTypeID(v) == CFNumberGetTypeID() && CFNumberGetValue((CFNumberRef)v, kCFNumberLongLongType, &sz) && sz > 0) {
            f->bytes = (uint64_t)sz;
        } else {
            f->bytes = UINT64_MAX;
        }
    }
    CFRelease(desc);
    CFRelease(dadisk);
    CFRelease(session);
    if (!f->whole_device) {
        snprintf(f->detail, sizeof f->detail, "%s is not a whole physical disk", disk);
        return 0;
    }

    n = getmntinfo(&mnts, MNT_NOWAIT);
    if (n <= 0) {
        snprintf(f->detail, sizeof f->detail, "cannot list mounts");
        f->n_mounted = SAFETY_MAX_MOUNTS + 1;
        return 0;
    }
    for (i = 0; i < n; i++) {
        const char *from = mnts[i].f_mntfromname;
        int synth = 0, on;
        if (strncmp(from, "/dev/disk", 9) != 0) { continue; }
        on = mount_on_disk(from + 5, disk, &synth);
        if (on < 0) {
            if (is_system_mount(&mnts[i])) { unresolved = 1; }
            continue;
        }
        if (!on) { continue; }
        if (is_system_mount(&mnts[i])) { os_hit = 1; }
        if (f->n_mounted < SAFETY_MAX_MOUNTS) {
            struct mounted_volume *m = &f->mounted[f->n_mounted];
            const char *s = from + 5 + strlen(disk);
            /* diskNsM is MBR entry M; anything else (APFS, nested) is unknown. */
            m->partition = (!synth && s[0] == 's' && s[1] >= '1' && s[1] <= '4' && s[2] == '\0') ? s[1] - '0' : 0;
            snprintf(m->where, sizeof m->where, "%s", mnts[i].f_mntonname);
            f->n_mounted++;
        } else {
            f->n_mounted = SAFETY_MAX_MOUNTS + 1;
        }
    }
    if (unresolved) {
        snprintf(f->detail, sizeof f->detail, "cannot tell which disk holds a system volume");
        return 0;                                   /* holds_os stays 1 */
    }
    f->holds_os = os_hit;

    if (f->n_mounted > 0 && f->n_mounted <= SAFETY_MAX_MOUNTS) {
        char raw[80];
        uint8_t lba0[512];
        int fd;
        snprintf(raw, sizeof raw, "/dev/r%s", disk);
        fd = open(raw, O_RDONLY | O_CLOEXEC);
        if (fd >= 0) {
            if (pread(fd, lba0, sizeof lba0, 0) == (ssize_t)sizeof lba0) {
                f->layout_ok = mbr_is_layout(lba0, f->bytes / 512u);
            }
            close(fd);
        }
    }
    return 0;
}

int probe_unmount_p1(const char *path, const struct device_facts *f, int i)
{
    (void)path;
    if (!safety_mount_is_own_p1(f, i)) { return -1; }
    return unmount(f->mounted[i].where, 0) == 0 ? 0 : -1;
}

#endif /* __APPLE__ */
