/*
 * discover_macos.c — cards enumeration on macOS (APP-1A §5).
 *
 * Whole disks are the IOKit registry's whole IOMedia objects. DiskArbitration
 * describes each (whole, removable, protocol, size); the registry gives the OS
 * partition view (scheme, and each partition's type hint, offset and size);
 * getmntinfo gives the mounts. No device node is opened: unelevated, the raw
 * nodes are root:operator 0640 anyway, and discovery needs none of them.
 */

#if defined(__APPLE__)

#include "discover.h"
#include "safety.h"

#include <CoreFoundation/CoreFoundation.h>
#include <DiskArbitration/DiskArbitration.h>
#include <IOKit/IOKitLib.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/param.h>

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

static int reg_string(io_registry_entry_t e, CFStringRef key, char *out, size_t cap)
{
    CFTypeRef v = IORegistryEntryCreateCFProperty(e, key, NULL, 0);
    int ok = v != NULL && CFGetTypeID(v) == CFStringGetTypeID()
             && CFStringGetCString((CFStringRef)v, out, (CFIndex)cap, kCFStringEncodingUTF8);
    if (v) { CFRelease(v); }
    return ok ? 0 : -1;
}

static int reg_number(io_registry_entry_t e, CFStringRef key, long long *out)
{
    CFTypeRef v = IORegistryEntryCreateCFProperty(e, key, NULL, 0);
    int ok = v != NULL && CFGetTypeID(v) == CFNumberGetTypeID()
             && CFNumberGetValue((CFNumberRef)v, kCFNumberLongLongType, out);
    if (v) { CFRelease(v); }
    return ok ? 0 : -1;
}

static int reg_bool(io_registry_entry_t e, CFStringRef key)
{
    CFTypeRef v = IORegistryEntryCreateCFProperty(e, key, NULL, 0);
    int r = v != NULL && CFGetTypeID(v) == CFBooleanGetTypeID() && CFBooleanGetValue((CFBooleanRef)v);
    if (v) { CFRelease(v); }
    return r;
}

/* Does any service-plane ancestor of `e` have a class containing one of the
   given substrings, or conform to `conforms`? */
static int ancestor_is(io_registry_entry_t e, const char *a, const char *b, const char *conforms)
{
    io_iterator_t it;
    io_registry_entry_t p;
    io_name_t cls;
    int hit = 0;
    if (IORegistryEntryCreateIterator(e, kIOServicePlane, kIORegistryIterateRecursively | kIORegistryIterateParents,
                                      &it) != KERN_SUCCESS) { return -1; }
    while ((p = IOIteratorNext(it)) != IO_OBJECT_NULL) {
        if (IOObjectGetClass(p, cls) == KERN_SUCCESS && ((a && strstr(cls, a)) || (b && strstr(cls, b)))) { hit = 1; }
        if (conforms && IOObjectConformsTo(p, conforms)) { hit = 1; }
        IOObjectRelease(p);
    }
    IOObjectRelease(it);
    return hit;
}

/* The whole disk's BSD name beneath the mount device `bsd` (e.g. disk3 for
   disk3s1s1), walking service-plane ancestors; -1 if none is found. */
static int whole_of(const char *bsd, char *out, size_t cap)
{
    io_service_t media = IOServiceGetMatchingService(MACH_PORT_NULL, IOBSDNameMatching(MACH_PORT_NULL, 0, bsd));
    io_iterator_t it;
    io_registry_entry_t e;
    int found = -1;
    if (media == IO_OBJECT_NULL) { return -1; }
    if (reg_bool(media, CFSTR("Whole")) && reg_string(media, CFSTR("BSD Name"), out, cap) == 0
        && ancestor_is(media, NULL, NULL, "AppleAPFSContainer") == 0) {
        IOObjectRelease(media);
        return 0;
    }
    if (IORegistryEntryCreateIterator(media, kIOServicePlane, kIORegistryIterateRecursively | kIORegistryIterateParents,
                                      &it) == KERN_SUCCESS) {
        while ((e = IOIteratorNext(it)) != IO_OBJECT_NULL) {
            /* The last whole IOMedia met walking up is the physical one, below
               any APFS container's synthesized disk. */
            if (IOObjectConformsTo(e, "IOMedia") && reg_bool(e, CFSTR("Whole"))
                && reg_string(e, CFSTR("BSD Name"), out, cap) == 0) { found = 0; }
            IOObjectRelease(e);
        }
        IOObjectRelease(it);
    }
    IOObjectRelease(media);
    return found;
}

static int is_system_mount(const struct statfs *m)
{
    return (m->f_flags & MNT_ROOTFS) != 0 || strcmp(m->f_mntonname, "/") == 0
        || strncmp(m->f_mntonname, "/System/Volumes/", 16) == 0
        || strcmp(m->f_mntonname, "/private/var/vm") == 0;
}

struct use { char disk[64]; char bsd[64]; int system; };
static struct use g_use[128];
static int g_nuse, g_use_unknown, g_os_unresolved;

static int gather_uses(char *err, size_t cap)
{
    struct statfs *mnts = NULL;
    int n = getmntinfo(&mnts, MNT_NOWAIT), i;
    g_nuse = g_use_unknown = g_os_unresolved = 0;
    if (n <= 0) { snprintf(err, cap, "getmntinfo failed"); return -1; }
    for (i = 0; i < n; i++) {
        const char *from = mnts[i].f_mntfromname;
        char disk[64];
        if (strncmp(from, "/dev/disk", 9) != 0) { continue; }
        if (whole_of(from + 5, disk, sizeof disk) != 0) {
            if (is_system_mount(&mnts[i])) { g_os_unresolved = 1; }
            continue;
        }
        if (g_nuse >= (int)(sizeof g_use / sizeof g_use[0])) { g_use_unknown = 1; continue; }
        snprintf(g_use[g_nuse].disk, sizeof g_use[0].disk, "%s", disk);
        snprintf(g_use[g_nuse].bsd, sizeof g_use[0].bsd, "%s", from + 5);
        g_use[g_nuse].system = is_system_mount(&mnts[i]);
        g_nuse++;
    }
    return 0;
}

/* The MBR type byte from IOFDiskPartitionScheme's content hint ("0xDA"), or
   DISC_UNKNOWN for any hint that is not that form. */
static int hint_type(const char *hint)
{
    char *end;
    long v;
    if (hint[0] != '0' || (hint[1] != 'x' && hint[1] != 'X')) { return DISC_UNKNOWN; }
    v = strtol(hint + 2, &end, 16);
    return (*end == '\0' && end != hint + 2 && v >= 0 && v <= 255) ? (int)v : DISC_UNKNOWN;
}

static void partitions(io_registry_entry_t whole, const char *disk, struct disc_disk *d)
{
    io_iterator_t it;
    io_registry_entry_t e;
    char content[64];
    int i;

    if (reg_string(whole, CFSTR("Content"), content, sizeof content) == 0) {
        d->mbr = strcmp(content, "FDisk_partition_scheme") == 0 ? DISC_YES : DISC_NO;
    }
    if (IORegistryEntryCreateIterator(whole, kIOServicePlane, kIORegistryIterateRecursively, &it) != KERN_SUCCESS) {
        return;                                    /* n_parts stays unknown */
    }
    d->n_parts = 0;
    while ((e = IOIteratorNext(it)) != IO_OBJECT_NULL) {
        char bsd[64], hint[64];
        long long base, size, id;
        struct disc_part *q;
        if (!IOObjectConformsTo(e, "IOMedia") || reg_bool(e, CFSTR("Whole"))
            || reg_string(e, CFSTR("BSD Name"), bsd, sizeof bsd) != 0
            || strncmp(bsd, disk, strlen(disk)) != 0 || bsd[strlen(disk)] != 's'
            || strchr(bsd + strlen(disk) + 1, 's') != NULL) {
            IOObjectRelease(e);
            continue;                              /* only diskNsM, not nested slices */
        }
        if (d->n_parts >= DISC_MAX_PARTS) { d->n_parts = DISC_UNKNOWN; IOObjectRelease(e); break; }
        q = &d->parts[d->n_parts++];
        q->index = reg_number(e, CFSTR("Partition ID"), &id) == 0 ? (int)id : atoi(bsd + strlen(disk) + 1);
        q->type = DISC_UNKNOWN;
        if (reg_string(e, CFSTR("Content"), hint, sizeof hint) == 0) {
            snprintf(q->hint, sizeof q->hint, "%s", hint);
            q->type = hint_type(hint);       /* a name ("DOS_FAT_16") is not a type byte */
        }
        q->start = reg_number(e, CFSTR("Base"), &base) == 0 && base >= 0 ? (int64_t)base : DISC_UNKNOWN;
        q->length = reg_number(e, CFSTR("Size"), &size) == 0 && size >= 0 ? (int64_t)size : DISC_UNKNOWN;
        q->mounted = g_use_unknown ? DISC_UNKNOWN : DISC_NO;
        for (i = 0; i < g_nuse; i++) {
            if (strcmp(g_use[i].bsd, bsd) == 0) { q->mounted = DISC_YES; }
        }
        IOObjectRelease(e);
    }
    IOObjectRelease(it);
}

static void facts(io_registry_entry_t whole, DASessionRef session, struct disc_disk *d)
{
    char disk[64];
    DADiskRef dadisk;
    CFDictionaryRef desc;
    int i;

    discover_init(d);
    if (reg_string(whole, CFSTR("BSD Name"), disk, sizeof disk) != 0) { return; }
    snprintf(d->path, sizeof d->path, "/dev/%s", disk);
    dadisk = DADiskCreateFromBSDName(kCFAllocatorDefault, session, disk);
    desc = dadisk ? DADiskCopyDescription(dadisk) : NULL;
    if (desc != NULL) {
        int synth = ancestor_is(whole, NULL, NULL, "AppleAPFSContainer");
        int image = ancestor_is(whole, "HDIX", "DiskImage", NULL);
        CFTypeRef v = CFDictionaryGetValue(desc, kDADiskDescriptionMediaSizeKey);
        long long sz = 0;
        d->whole = (cf_bool(desc, kDADiskDescriptionMediaWholeKey) && synth == 0 && path_is_whole_form(d->path))
                   ? DISC_YES : (synth < 0 ? DISC_UNKNOWN : DISC_NO);
        d->is_virtual = (image < 0) ? DISC_UNKNOWN
                        : (image || cf_string_is(desc, kDADiskDescriptionDeviceProtocolKey, "Disk Image")
                           || cf_string_is(desc, kDADiskDescriptionDeviceProtocolKey, "Virtual Interface")) ? DISC_YES : DISC_NO;
        d->removable_or_sd = (cf_bool(desc, kDADiskDescriptionMediaRemovableKey)
                              || cf_string_is(desc, kDADiskDescriptionDeviceProtocolKey, "Secure Digital")) ? DISC_YES : DISC_NO;
        if (v && CFGetTypeID(v) == CFNumberGetTypeID() && CFNumberGetValue((CFNumberRef)v, kCFNumberLongLongType, &sz) && sz >= 0) {
            d->bytes = (uint64_t)sz;
            d->bytes_known = 1;
        }
        CFRelease(desc);
    }
    if (dadisk) { CFRelease(dadisk); }
    partitions(whole, disk, d);

    d->n_mounted = 0;
    d->holds_os = DISC_NO;
    d->mounted_unattributed = DISC_NO;
    for (i = 0; i < g_nuse; i++) {
        int j, attributed = 0;
        if (strcmp(g_use[i].disk, disk) != 0) { continue; }
        d->n_mounted++;
        if (g_use[i].system) { d->holds_os = DISC_YES; }
        for (j = 0; d->n_parts > 0 && j < d->n_parts; j++) {
            char want[80];
            snprintf(want, sizeof want, "%ss%d", disk, d->parts[j].index);
            if (strcmp(g_use[i].bsd, want) == 0) { attributed = 1; }
        }
        if (!attributed) { d->mounted_unattributed = DISC_YES; }
    }
    if (g_use_unknown) { d->n_mounted = DISC_UNKNOWN; d->mounted_unattributed = DISC_UNKNOWN; }
    if (g_os_unresolved && d->holds_os != DISC_YES) { d->holds_os = DISC_UNKNOWN; }
}

int discover_enumerate(disc_each each, void *ctx, char *err, size_t cap)
{
    CFMutableDictionaryRef match;
    io_iterator_t it;
    io_registry_entry_t e;
    io_registry_entry_t wholes[DISC_MAX_DISKS];
    char names[DISC_MAX_DISKS][64];
    DASessionRef session;
    int n = 0, i, j;

    match = IOServiceMatching("IOMedia");
    if (match == NULL) { snprintf(err, cap, "IOServiceMatching(IOMedia) failed"); return -1; }
    CFDictionarySetValue(match, CFSTR("Whole"), kCFBooleanTrue);
    if (IOServiceGetMatchingServices(MACH_PORT_NULL, match, &it) != KERN_SUCCESS) {
        snprintf(err, cap, "IOServiceGetMatchingServices failed");
        return -1;
    }
    while ((e = IOIteratorNext(it)) != IO_OBJECT_NULL) {
        if (n >= DISC_MAX_DISKS || reg_string(e, CFSTR("BSD Name"), names[n], sizeof names[0]) != 0) {
            IOObjectRelease(e);
            if (n >= DISC_MAX_DISKS) {
                IOObjectRelease(it);
                for (i = 0; i < n; i++) { IOObjectRelease(wholes[i]); }
                snprintf(err, cap, "more than %d disks", DISC_MAX_DISKS);
                return -1;
            }
            continue;
        }
        wholes[n++] = e;
    }
    IOObjectRelease(it);
    /* Stable order: diskN by number. */
    for (i = 1; i < n; i++) {
        for (j = i; j > 0 && atoi(names[j - 1] + 4) > atoi(names[j] + 4); j--) {
            char t[64];
            io_registry_entry_t te = wholes[j];
            memcpy(t, names[j], sizeof t); memcpy(names[j], names[j - 1], sizeof t); memcpy(names[j - 1], t, sizeof t);
            wholes[j] = wholes[j - 1]; wholes[j - 1] = te;
        }
    }
    session = DASessionCreate(kCFAllocatorDefault);
    if (session == NULL || gather_uses(err, cap) != 0) {
        if (session == NULL) { snprintf(err, cap, "DiskArbitration unavailable"); }
        else { CFRelease(session); }
        for (i = 0; i < n; i++) { IOObjectRelease(wholes[i]); }
        return -1;
    }
    for (i = 0; i < n; i++) {
        struct disc_disk d;
        facts(wholes[i], session, &d);
        IOObjectRelease(wholes[i]);
        each(ctx, &d, i + 1, n);
    }
    CFRelease(session);
    return 0;
}

#endif /* __APPLE__ */
