/*
 * probe_win.c — device facts on Windows 10 (docs/WP14-CLI-CONTRACT.md §2, §5).
 *
 * The disk is queried through \\.\PhysicalDriveN opened for read or for
 * queries only. Volumes are mapped to disks through their disk extents: the
 * system volume and every page-file volume decide holds_os, and every volume
 * with a mount point on this disk is listed. A fact that cannot be established
 * keeps its refusing value.
 */

#if defined(_WIN32)

#include "safety.h"
#include "layout.h"
#include "winutf.h"

#include <windows.h>
#include <winioctl.h>
#include <psapi.h>
#include <wctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Volume handles locked for the life of the process (partition 1 dismount). */
static HANDLE g_locked[4];
static int g_nlocked;

/* Disk numbers a volume spans. Returns the count, or -1. */
static int volume_disks(const wchar_t *volume, DWORD disks[8], ULONGLONG *start, ULONGLONG *len)
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
    for (i = 0; i < (DWORD)n; i++) { disks[i] = ext.v.Extents[i].DiskNumber; }
    if (start) { *start = (ULONGLONG)ext.v.Extents[0].StartingOffset.QuadPart; }
    if (len) { *len = (ULONGLONG)ext.v.Extents[0].ExtentLength.QuadPart; }
    return n;
}

/* Does the volume holding drive-letter path `p` ("C:\...") span disk `disk`?
   1 yes, 0 no, -1 could not tell. */
static int letter_on_disk(const wchar_t *p, DWORD disk)
{
    wchar_t vol[8];
    DWORD disks[8];
    int n, i;
    if (p[0] == L'\\' && p[1] == L'?' && p[2] == L'?' && p[3] == L'\\') { p += 4; }
    if (!iswalpha(p[0]) || p[1] != L':') { return -1; }
    swprintf(vol, 8, L"\\\\.\\%c:", p[0]);
    n = volume_disks(vol, disks, NULL, NULL);
    if (n < 0) { return -1; }
    for (i = 0; i < n; i++) { if (disks[i] == disk) { return 1; } }
    return 0;
}

struct pagefile_scan { DWORD disk; int hit; int unknown; };

static BOOL CALLBACK pagefile_cb(LPVOID ctx, PENUM_PAGE_FILE_INFORMATION info, LPCWSTR name)
{
    struct pagefile_scan *s = (struct pagefile_scan *)ctx;
    int r = letter_on_disk(name, s->disk);
    (void)info;
    if (r < 0) { s->unknown = 1; }
    if (r > 0) { s->hit = 1; }
    return TRUE;
}

int probe_device(const char *path, struct device_facts *f)
{
    wchar_t wpath[64], sysdir[MAX_PATH], vol[MAX_PATH];
    DWORD disk, got = 0;
    HANDLE h, fv;
    STORAGE_PROPERTY_QUERY q;
    union { STORAGE_DEVICE_DESCRIPTOR d; unsigned char raw[1024]; } sdd;
    STORAGE_DEVICE_NUMBER sdn;
    GET_LENGTH_INFORMATION li;
    struct pagefile_scan ps;
    int r;

    memset(f, 0, sizeof *f);
    f->holds_os = 1;
    if (!path_is_whole_form(path)) {
        snprintf(f->detail, sizeof f->detail, "%s is not \\\\.\\PhysicalDriveN", path);
        return 0;
    }
    disk = (DWORD)strtoul(path + 17, NULL, 10);
    if (utf8_to_wide(path, wpath, 64)) { return 0; }

    h = CreateFileW(wpath, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        snprintf(f->detail, sizeof f->detail, "cannot open %s (error %lu; run as Administrator)",
                 path, (unsigned long)GetLastError());
        return 0;
    }
    if (DeviceIoControl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, NULL, 0, &sdn, sizeof sdn, &got, NULL)
        && sdn.DeviceNumber == disk && sdn.PartitionNumber == 0) {
        f->whole_device = 1;
    }
    memset(&q, 0, sizeof q);
    q.PropertyId = StorageDeviceProperty;
    q.QueryType = PropertyStandardQuery;
    if (DeviceIoControl(h, IOCTL_STORAGE_QUERY_PROPERTY, &q, sizeof q, &sdd, sizeof sdd, &got, NULL)) {
        f->removable = sdd.d.RemovableMedia ? 1 : 0;
        f->sd_bus = (sdd.d.BusType == BusTypeSd || sdd.d.BusType == BusTypeMmc);
        /* ADR-164 §5: virtual media (a VHD, a file-backed disk) is never a card. */
        if (sdd.d.BusType == BusTypeVirtual || sdd.d.BusType == BusTypeFileBackedVirtual) {
            f->removable = 0;
            f->sd_bus = 0;
        }
    }
    f->bytes = DeviceIoControl(h, IOCTL_DISK_GET_LENGTH_INFO, NULL, 0, &li, sizeof li, &got, NULL)
               ? (uint64_t)li.Length.QuadPart : UINT64_MAX;
    if (!f->whole_device) {
        snprintf(f->detail, sizeof f->detail, "%s is not a whole disk", path);
        CloseHandle(h);
        return 0;
    }

    /* holds_os: the Windows volume, the boot volume (same), and page files. */
    if (GetSystemWindowsDirectoryW(sysdir, MAX_PATH) == 0) { CloseHandle(h); return 0; }
    r = letter_on_disk(sysdir, disk);
    ps.disk = disk; ps.hit = 0; ps.unknown = 0;
    if (!EnumPageFilesW(pagefile_cb, &ps)) { ps.unknown = 1; }
    if (r < 0 || ps.unknown) {
        snprintf(f->detail, sizeof f->detail, "cannot tell which disk holds the system or a page file");
        CloseHandle(h);
        return 0;                                   /* holds_os stays 1 */
    }
    f->holds_os = (r > 0 || ps.hit);

    /* Every volume on this disk that has a mount point. */
    fv = FindFirstVolumeW(vol, MAX_PATH);
    if (fv == INVALID_HANDLE_VALUE) {
        f->n_mounted = SAFETY_MAX_MOUNTS + 1;
        snprintf(f->detail, sizeof f->detail, "cannot list volumes");
        CloseHandle(h);
        return 0;
    }
    do {
        wchar_t names[512], novs[MAX_PATH];
        DWORD disks[8], need = 0;
        ULONGLONG start = 0, len = 0;
        size_t L = wcslen(vol);
        int n, i, on = 0;
        if (L == 0 || L >= MAX_PATH) { continue; }
        wcscpy(novs, vol);
        if (novs[L - 1] == L'\\') { novs[L - 1] = L'\0'; }
        n = volume_disks(novs, disks, &start, &len);
        for (i = 0; i < n; i++) { if (disks[i] == disk) { on = 1; } }
        if (!on) { continue; }
        names[0] = L'\0';
        if (!GetVolumePathNamesForVolumeNameW(vol, names, 512, &need) || names[0] == L'\0') { continue; }
        if (f->n_mounted < SAFETY_MAX_MOUNTS) {
            struct mounted_volume *m = &f->mounted[f->n_mounted];
            m->partition = (n == 1 && start == (ULONGLONG)LAYOUT_P1_START * 512u
                            && len == (ULONGLONG)LAYOUT_P1_SECTORS * 512u) ? 1 : 0;
            wide_to_utf8(novs, m->where, (int)sizeof m->where);
            f->n_mounted++;
        } else {
            f->n_mounted = SAFETY_MAX_MOUNTS + 1;
        }
    } while (FindNextVolumeW(fv, vol, MAX_PATH));
    FindVolumeClose(fv);

    if (f->n_mounted > 0 && f->n_mounted <= SAFETY_MAX_MOUNTS) {
        uint8_t lba0[512];
        OVERLAPPED ov;
        DWORD rd = 0;
        memset(&ov, 0, sizeof ov);
        if (ReadFile(h, lba0, sizeof lba0, &rd, &ov) && rd == sizeof lba0) {
            f->layout_ok = mbr_is_layout(lba0, f->bytes / 512u);
        }
    }
    CloseHandle(h);
    return 0;
}

int probe_unmount_p1(const char *path, const struct device_facts *f, int i)
{
    wchar_t w[200];
    HANDLE h;
    DWORD got = 0;
    (void)path;
    if (!safety_mount_is_own_p1(f, i) || g_nlocked >= 4) { return -1; }
    if (utf8_to_wide(f->mounted[i].where, w, 200)) { return -1; }
    h = CreateFileW(w, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) { return -1; }
    if (!DeviceIoControl(h, FSCTL_LOCK_VOLUME, NULL, 0, NULL, 0, &got, NULL)
        || !DeviceIoControl(h, FSCTL_DISMOUNT_VOLUME, NULL, 0, NULL, 0, &got, NULL)) {
        CloseHandle(h);
        return -1;
    }
    g_locked[g_nlocked++] = h;     /* released when tapectl exits */
    return 0;
}

#endif /* _WIN32 */
