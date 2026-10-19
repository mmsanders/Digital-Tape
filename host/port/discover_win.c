/*
 * discover_win.c — cards enumeration on Windows (APP-1A §5).
 *
 * Whole disks are \\.\PhysicalDrive0..63 opened with zero access (no read or
 * write right; Product #444 F1: this succeeds unelevated where GENERIC_READ
 * fails). Only FILE_ANY_ACCESS queries are issued on that handle: device
 * number, storage properties, geometry and the drive layout. Volumes are mapped
 * to disks through their extents on zero-access volume handles; the system
 * volume and the page files named in the registry decide OS use. The disk
 * interfaces SetupAPI lists must all be among the drives probed, or the census
 * is incomplete and the enumeration fails rather than list part of it.
 */

#if defined(_WIN32)

#include "discover.h"
#include "safety.h"
#include "winutf.h"

#include <windows.h>
#include <winioctl.h>
#include <setupapi.h>
#include <wctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct vol { DWORD disk; ULONGLONG start, len; int spans; int mounted; int system; };   /* mounted, system: tri-state */
static struct vol g_vol[128];
static int g_nvol, g_vol_unknown, g_os_unresolved;

/* Disk extents of a volume, on a zero-access handle. Count, or -1. */
static int volume_extents(const wchar_t *volume, DWORD disks[8], ULONGLONG starts[8], ULONGLONG lens[8])
{
    HANDLE h = CreateFileW(volume, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    union { VOLUME_DISK_EXTENTS v; unsigned char raw[sizeof(VOLUME_DISK_EXTENTS) + 8 * sizeof(DISK_EXTENT)]; } ext;
    DWORD got = 0, i;
    int n;
    if (h == INVALID_HANDLE_VALUE) { return -1; }
    if (!DeviceIoControl(h, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, NULL, 0, &ext, sizeof ext, &got, NULL)) {
        CloseHandle(h);
        return -1;
    }
    CloseHandle(h);
    n = (int)(ext.v.NumberOfDiskExtents > 8 ? 8 : ext.v.NumberOfDiskExtents);
    for (i = 0; i < (DWORD)n; i++) {
        disks[i] = ext.v.Extents[i].DiskNumber;
        starts[i] = (ULONGLONG)ext.v.Extents[i].StartingOffset.QuadPart;
        lens[i] = (ULONGLONG)ext.v.Extents[i].ExtentLength.QuadPart;
    }
    return n;
}

/* Does the volume of drive-letter path `p` span `vol`'s first extent's disk? */
static int letter_volume_is(const wchar_t *p, wchar_t letter)
{
    if (p[0] == L'\\' && p[1] == L'?' && p[2] == L'?' && p[3] == L'\\') { p += 4; }
    return iswalpha(p[0]) && p[1] == L':' && towupper(p[0]) == towupper(letter);
}

/* System-use drive letters: the Windows directory's, and each page file's from
   the Memory Management key (readable unelevated). Returns the count, or -1. */
static int system_letters(wchar_t out[27])
{
    wchar_t dir[MAX_PATH], buf[2048];
    DWORD type = 0, size = sizeof buf;
    HKEY k;
    int n = 0;
    LONG r;
    const wchar_t *s;
    if (GetSystemWindowsDirectoryW(dir, MAX_PATH) == 0 || !iswalpha(dir[0])) { return -1; }
    out[n++] = (wchar_t)towupper(dir[0]);
    if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, L"SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management",
                      0, KEY_QUERY_VALUE, &k) != ERROR_SUCCESS) { return -1; }
    r = RegQueryValueExW(k, L"ExistingPageFiles", NULL, &type, (LPBYTE)buf, &size);
    RegCloseKey(k);
    if (r == ERROR_FILE_NOT_FOUND) { out[n] = 0; return n; }    /* no page file */
    if (r != ERROR_SUCCESS || type != REG_MULTI_SZ || size < sizeof(wchar_t)) { return -1; }
    buf[sizeof buf / sizeof buf[0] - 1] = 0;
    for (s = buf; *s && n < 26; s += wcslen(s) + 1) {
        const wchar_t *p = s;
        if (p[0] == L'\\' && p[1] == L'?' && p[2] == L'?' && p[3] == L'\\') { p += 4; }
        if (!iswalpha(p[0]) || p[1] != L':') { return -1; }
        out[n++] = (wchar_t)towupper(p[0]);
    }
    out[n] = 0;
    return n;
}

/* The volume's mount paths into `names` (a malloc'd multi-string the caller
   frees): DISC_YES with at least one, DISC_NO with none, DISC_UNKNOWN when the
   query fails. */
static int volume_paths(const wchar_t *vol, wchar_t **names)
{
    DWORD cap = 1024, need = 0;
    int tries;
    *names = NULL;
    for (tries = 0; tries < 4; tries++) {
        wchar_t *buf = malloc((size_t)cap * sizeof(wchar_t));
        if (buf == NULL) { return DISC_UNKNOWN; }
        buf[0] = L'\0';
        if (!DISC_FAULT("win.volume_paths") && GetVolumePathNamesForVolumeNameW(vol, buf, cap, &need)) {
            *names = buf;
            return buf[0] != L'\0' ? DISC_YES : DISC_NO;
        }
        free(buf);
        if (DISC_FAULT("win.volume_paths") || GetLastError() != ERROR_MORE_DATA || need <= cap) { return DISC_UNKNOWN; }
        cap = need;
    }
    return DISC_UNKNOWN;
}

static int gather_volumes(char *err, size_t cap)
{
    wchar_t vol[MAX_PATH], sys[27];
    HANDLE fv;
    DWORD e;
    int nsys = system_letters(sys);

    g_nvol = g_vol_unknown = 0;
    g_os_unresolved = nsys < 0;
    fv = FindFirstVolumeW(vol, MAX_PATH);
    if (fv == INVALID_HANDLE_VALUE) { snprintf(err, cap, "FindFirstVolumeW: error %lu", (unsigned long)GetLastError()); return -1; }
    do {
        wchar_t novs[MAX_PATH], *names;
        DWORD disks[8];
        ULONGLONG starts[8], lens[8];
        size_t L = wcslen(vol);
        int n, i, mounted, system = DISC_NO;
        if (L == 0 || L >= MAX_PATH) { continue; }
        wcscpy(novs, vol);
        if (novs[L - 1] == L'\\') { novs[L - 1] = L'\0'; }
        mounted = volume_paths(vol, &names);
        if (mounted == DISC_UNKNOWN) {
            system = DISC_UNKNOWN;                 /* its drive letters, if any, are unknown */
        } else if (mounted == DISC_YES && nsys > 0) {
            const wchar_t *s;
            int j;
            for (s = names; *s; s += wcslen(s) + 1) {
                for (j = 0; j < nsys; j++) { if (letter_volume_is(s, sys[j])) { system = DISC_YES; } }
            }
        }
        free(names);
        n = DISC_FAULT("win.volume_extents") ? -1 : volume_extents(novs, disks, starts, lens);
        if (n < 0) {
            /* A volume whose disk cannot be told: a mounted or system one (or
               one that may be) makes every disk's mount/OS facts unknown. */
            if (system != DISC_NO) { g_os_unresolved = 1; }
            if (mounted != DISC_NO) { g_vol_unknown = 1; }
            continue;
        }
        for (i = 0; i < n; i++) {
            if (g_nvol >= (int)(sizeof g_vol / sizeof g_vol[0])) { g_vol_unknown = 1; break; }
            g_vol[g_nvol].disk = disks[i];
            g_vol[g_nvol].start = starts[i];
            g_vol[g_nvol].len = lens[i];
            g_vol[g_nvol].spans = n;
            g_vol[g_nvol].mounted = mounted;
            g_vol[g_nvol].system = system;
            g_nvol++;
        }
    } while (FindNextVolumeW(fv, vol, MAX_PATH));
    e = DISC_FAULT("win.volume_next") ? ERROR_INVALID_FUNCTION : GetLastError();
    FindVolumeClose(fv);
    if (e != ERROR_NO_MORE_FILES) {
        /* The volume list ended early: the mounts it did not reach are unknown. */
        snprintf(err, cap, "FindNextVolumeW: error %lu", (unsigned long)e);
        return -1;
    }
    return 0;
}

/* GUID_DEVINTERFACE_DISK. */
static const GUID disk_interface = {0x53f56307, 0xb6bf, 0x11d0, {0x94, 0xf2, 0x00, 0xa0, 0xc9, 0x1e, 0xfb, 0x8b}};

/* Every present disk interface must be one of the probed drives `nums`. 0, or
   -1 with the reason when the census is incomplete or cannot be taken. */
static int disk_census(const DWORD *nums, int n, char *err, size_t cap)
{
    HDEVINFO set = SetupDiGetClassDevsW(&disk_interface, NULL, NULL, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    SP_DEVICE_INTERFACE_DATA ifd;
    DWORD idx, e;
    int rc = 0;
    if (set == INVALID_HANDLE_VALUE) {
        snprintf(err, cap, "SetupDiGetClassDevsW: error %lu", (unsigned long)GetLastError());
        return -1;
    }
    for (idx = 0; rc == 0; idx++) {
        union { SP_DEVICE_INTERFACE_DETAIL_DATA_W d; unsigned char raw[sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W) + 1024 * sizeof(wchar_t)]; } det;
        STORAGE_DEVICE_NUMBER sdn;
        HANDLE h;
        DWORD got = 0;
        int i, found = 0;
        ifd.cbSize = sizeof ifd;
        if (!SetupDiEnumDeviceInterfaces(set, NULL, &disk_interface, idx, &ifd)) {
            e = GetLastError();
            if (e != ERROR_NO_MORE_ITEMS) { snprintf(err, cap, "SetupDiEnumDeviceInterfaces: error %lu", (unsigned long)e); rc = -1; }
            break;
        }
        det.d.cbSize = sizeof det.d;
        if (!SetupDiGetDeviceInterfaceDetailW(set, &ifd, &det.d, sizeof det, NULL, NULL)) {
            snprintf(err, cap, "disk interface %lu: no path (error %lu)", (unsigned long)idx, (unsigned long)GetLastError());
            rc = -1;
            break;
        }
        h = CreateFileW(det.d.DevicePath, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
        if (h == INVALID_HANDLE_VALUE
            || !DeviceIoControl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, NULL, 0, &sdn, sizeof sdn, &got, NULL)) {
            snprintf(err, cap, "disk interface %lu: no device number (error %lu)", (unsigned long)idx, (unsigned long)GetLastError());
            if (h != INVALID_HANDLE_VALUE) { CloseHandle(h); }
            rc = -1;
            break;
        }
        CloseHandle(h);
        if (DISC_FAULT("win.disk_census")) { sdn.DeviceNumber = DISC_MAX_DISKS; }   /* a disk past the probed range */
        for (i = 0; i < n; i++) { if (nums[i] == sdn.DeviceNumber) { found = 1; } }
        if (!found) {
            snprintf(err, cap, "disk %lu is not among the probed \\\\.\\PhysicalDrive0..%d", (unsigned long)sdn.DeviceNumber,
                     DISC_MAX_DISKS - 1);
            rc = -1;
        }
    }
    SetupDiDestroyDeviceInfoList(set);
    return rc;
}

static void facts(DWORD disk, HANDLE h, struct disc_disk *d)
{
    STORAGE_PROPERTY_QUERY q;
    union { STORAGE_DEVICE_DESCRIPTOR d; unsigned char raw[1024]; } sdd;
    union { DISK_GEOMETRY_EX g; unsigned char raw[256]; } geo;
    union { DRIVE_LAYOUT_INFORMATION_EX l; unsigned char raw[sizeof(DRIVE_LAYOUT_INFORMATION_EX) + 128 * sizeof(PARTITION_INFORMATION_EX)]; } lay;
    STORAGE_DEVICE_NUMBER sdn;
    DWORD got = 0, i;
    int v, j, mount_unknown = 0, os_unknown = 0;

    if (DeviceIoControl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, NULL, 0, &sdn, sizeof sdn, &got, NULL)) {
        d->whole = (sdn.DeviceNumber == disk && sdn.PartitionNumber == 0) ? DISC_YES : DISC_NO;
    }
    memset(&q, 0, sizeof q);
    q.PropertyId = StorageDeviceProperty;
    q.QueryType = PropertyStandardQuery;
    if (DeviceIoControl(h, IOCTL_STORAGE_QUERY_PROPERTY, &q, sizeof q, &sdd, sizeof sdd, &got, NULL)) {
        d->removable_or_sd = (sdd.d.RemovableMedia || sdd.d.BusType == BusTypeSd || sdd.d.BusType == BusTypeMmc)
                             ? DISC_YES : DISC_NO;
        d->is_virtual = (sdd.d.BusType == BusTypeVirtual || sdd.d.BusType == BusTypeFileBackedVirtual) ? DISC_YES : DISC_NO;
    }
    if (DeviceIoControl(h, IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, NULL, 0, &geo, sizeof geo, &got, NULL)
        && geo.g.DiskSize.QuadPart >= 0) {
        d->bytes = (uint64_t)geo.g.DiskSize.QuadPart;
        d->bytes_known = 1;
    }
    if (DeviceIoControl(h, IOCTL_DISK_GET_DRIVE_LAYOUT_EX, NULL, 0, &lay, sizeof lay, &got, NULL)) {
        d->mbr = lay.l.PartitionStyle == PARTITION_STYLE_MBR ? DISC_YES : DISC_NO;
        d->n_parts = 0;
        for (i = 0; i < lay.l.PartitionCount && i < 128; i++) {
            PARTITION_INFORMATION_EX *p = &lay.l.PartitionEntry[i];
            struct disc_part *dp;
            if (p->PartitionStyle == PARTITION_STYLE_MBR && p->Mbr.PartitionType == PARTITION_ENTRY_UNUSED) { continue; }
            if (p->PartitionNumber == 0) { continue; }
            if (d->n_parts >= DISC_MAX_PARTS) { d->n_parts = DISC_UNKNOWN; break; }
            dp = &d->parts[d->n_parts++];
            dp->index = (int)p->PartitionNumber;
            dp->type = p->PartitionStyle == PARTITION_STYLE_MBR ? (int)p->Mbr.PartitionType : DISC_UNKNOWN;
            if (dp->type >= 0) { snprintf(dp->hint, sizeof dp->hint, "0x%02X", (unsigned)dp->type); }
            dp->start = (int64_t)p->StartingOffset.QuadPart;
            dp->length = (int64_t)p->PartitionLength.QuadPart;
            dp->mounted = g_vol_unknown ? DISC_UNKNOWN : DISC_NO;
        }
    }

    d->n_mounted = 0;
    d->holds_os = DISC_NO;
    d->mounted_unattributed = DISC_NO;
    for (v = 0; v < g_nvol; v++) {
        int attributed = 0;
        if (g_vol[v].disk != disk) { continue; }
        if (g_vol[v].system == DISC_YES) { d->holds_os = DISC_YES; }
        if (g_vol[v].system == DISC_UNKNOWN) { os_unknown = 1; }
        if (g_vol[v].mounted == DISC_NO) { continue; }
        if (g_vol[v].mounted == DISC_UNKNOWN) { mount_unknown = 1; continue; }
        d->n_mounted++;
        for (j = 0; g_vol[v].spans == 1 && d->n_parts > 0 && j < d->n_parts; j++) {
            if (d->parts[j].start >= 0 && (ULONGLONG)d->parts[j].start == g_vol[v].start
                && d->parts[j].length >= 0 && (ULONGLONG)d->parts[j].length == g_vol[v].len) {
                d->parts[j].mounted = DISC_YES;
                attributed = 1;
            }
        }
        if (!attributed) { d->mounted_unattributed = DISC_YES; }
    }
    if (g_vol_unknown || mount_unknown) {
        d->n_mounted = DISC_UNKNOWN;
        d->mounted_unattributed = DISC_UNKNOWN;
        for (j = 0; d->n_parts > 0 && j < d->n_parts; j++) {
            if (d->parts[j].mounted != DISC_YES) { d->parts[j].mounted = DISC_UNKNOWN; }
        }
    }
    if ((g_os_unresolved || os_unknown) && d->holds_os != DISC_YES) { d->holds_os = DISC_UNKNOWN; }
}

int discover_enumerate(disc_each each, void *ctx, char *err, size_t cap)
{
    HANDLE hs[DISC_MAX_DISKS];
    DWORD nums[DISC_MAX_DISKS];
    int n = 0, i;
    DWORD k;

    for (k = 0; k < DISC_MAX_DISKS; k++) {
        wchar_t w[40];
        HANDLE h;
        DWORD e;
        swprintf(w, 40, L"\\\\.\\PhysicalDrive%lu", (unsigned long)k);
        h = CreateFileW(w, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
        if (h == INVALID_HANDLE_VALUE) {
            e = GetLastError();
            if (e == ERROR_FILE_NOT_FOUND || e == ERROR_PATH_NOT_FOUND) { continue; }   /* no such disk */
        }
        nums[n] = k;
        hs[n++] = h;                  /* INVALID_HANDLE_VALUE: listed, every fact unknown */
    }
    if (disk_census(nums, n, err, cap) != 0 || gather_volumes(err, cap) != 0) {
        for (i = 0; i < n; i++) { if (hs[i] != INVALID_HANDLE_VALUE) { CloseHandle(hs[i]); } }
        return -1;
    }
    for (i = 0; i < n; i++) {
        struct disc_disk d;
        discover_init(&d);
        snprintf(d.path, sizeof d.path, "\\\\.\\PhysicalDrive%lu", (unsigned long)nums[i]);
        if (hs[i] != INVALID_HANDLE_VALUE) {
            facts(nums[i], hs[i], &d);
            CloseHandle(hs[i]);
        }
        each(ctx, &d, i + 1, n);
    }
    return 0;
}

#endif /* _WIN32 */
