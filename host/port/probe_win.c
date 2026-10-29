/*
 * probe_win.c — device facts on Windows 10 (docs/WP14-CLI-CONTRACT.md §2, §5).
 *
 * The disk is queried through \\.\PhysicalDriveN opened for read or for
 * queries only. Volumes are mapped to disks through their disk extents: the
 * system volume and every page-file volume decide holds_os, and every volume
 * with a mount point on this disk is listed. A fact that cannot be established
 * keeps its refusing value; when an OS query failed, f->query_error names it.
 */

#if defined(_WIN32)

#include "safety.h"
#include "layout.h"
#include "winutf.h"
#include "hport.h"
#include "tseam.h"

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

/* Disk numbers a volume spans. Returns the count, or -1 (the OS's error stays in
   GetLastError). `broken`: the volume-extents control, a zero-size result buffer. */
static int volume_disks(const wchar_t *volume, DWORD disks[8], ULONGLONG *start, ULONGLONG *len, int broken)
{
    HANDLE h = CreateFileW(volume, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    union { VOLUME_DISK_EXTENTS v; unsigned char raw[sizeof(VOLUME_DISK_EXTENTS) + 8 * sizeof(DISK_EXTENT)]; } ext;
    DWORD got = 0, i, e;
    int n;
    if (h == INVALID_HANDLE_VALUE) { return -1; }
    if (!DeviceIoControl(h, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, NULL, 0, &ext, broken ? 0 : sizeof ext, &got, NULL)) {
        e = GetLastError();
        CloseHandle(h);
        SetLastError(e);
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
    n = volume_disks(vol, disks, NULL, NULL, 0);
    if (n < 0) { return -1; }
    for (i = 0; i < n; i++) { if (disks[i] == disk) { return 1; } }
    return 0;
}

/* A volume whose extents could not be read: 1 only if another query proves it is
   on a different device than disk `disk` (its device number names another disk, or
   it is not a disk at all); 0 if it may be on this disk. */
static int volume_elsewhere(const wchar_t *volume, DWORD disk)
{
    HANDLE h = CreateFileW(volume, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    STORAGE_DEVICE_NUMBER sdn;
    DWORD got = 0;
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) { return 0; }
    ok = DeviceIoControl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, NULL, 0, &sdn, sizeof sdn, &got, NULL);
    CloseHandle(h);
    return ok && (sdn.DeviceType != FILE_DEVICE_DISK || sdn.DeviceNumber != disk);
}

/* A query these facts need failed: keep the first, with the OS's own error `e`. */
static void query_failed_as(struct device_facts *f, const char *call, const char *e)
{
    if (f->query_error[0] == '\0') { snprintf(f->query_error, sizeof f->query_error, "%s: %s", call, e); }
}

static void query_failed(struct device_facts *f, const char *call)
{
    query_failed_as(f, call, hport_os_errname());
}

/* The mounted-volume census could not be completed: the mount fact refuses
   (every command), and make reports the failed query. */
static void census_failed(struct device_facts *f, const char *call, const char *e)
{
    query_failed_as(f, call, e);
    f->n_mounted = SAFETY_MAX_MOUNTS + 1;
    snprintf(f->detail, sizeof f->detail, "cannot tell which volumes are mounted on this disk (%s: %s)", call, e);
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
    DWORD li_cap = sizeof li;
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
        query_failed(f, "CreateFileW");
        snprintf(f->detail, sizeof f->detail, "cannot open %s (error %lu; run as Administrator)",
                 path, (unsigned long)GetLastError());
        return 0;
    }
    if (!DeviceIoControl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, NULL, 0, &sdn, sizeof sdn, &got, NULL)) {
        query_failed(f, "IOCTL_STORAGE_GET_DEVICE_NUMBER");
    } else if (sdn.DeviceNumber == disk && sdn.PartitionNumber == 0) {
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
    } else {
        query_failed(f, "IOCTL_STORAGE_QUERY_PROPERTY");
    }
#ifdef TAPECTL_TEST
    if (tseam_fault_query("disk-length")) { li_cap = 0; }   /* control: the OS really fails the query */
#endif
    if (DeviceIoControl(h, IOCTL_DISK_GET_LENGTH_INFO, NULL, 0, &li, li_cap, &got, NULL)) {
        f->bytes = (uint64_t)li.Length.QuadPart;
    } else {
        query_failed(f, "IOCTL_DISK_GET_LENGTH_INFO");
        f->bytes = UINT64_MAX;
    }
    if (!f->whole_device) {
        snprintf(f->detail, sizeof f->detail, "%s is not a whole disk", path);
        CloseHandle(h);
        return 0;
    }

    /* holds_os: the Windows volume, the boot volume (same), and page files. */
    if (GetSystemWindowsDirectoryW(sysdir, MAX_PATH) == 0) {
        query_failed(f, "GetSystemWindowsDirectoryW");
        CloseHandle(h);
        return 0;
    }
    r = letter_on_disk(sysdir, disk);
    if (r < 0) { query_failed(f, "IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS (system volume)"); }
    ps.disk = disk; ps.hit = 0; ps.unknown = 0;
    if (!EnumPageFilesW(pagefile_cb, &ps)) { query_failed(f, "EnumPageFilesW"); ps.unknown = 1; }
    else if (ps.unknown) { query_failed(f, "IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS (page-file volume)"); }
    if (r < 0 || ps.unknown) {
        snprintf(f->detail, sizeof f->detail, "cannot tell which disk holds the system or a page file");
        CloseHandle(h);
        return 0;                                   /* holds_os stays 1 */
    }
    f->holds_os = (r > 0 || ps.hit);

    /* Every volume on this disk that has a mount point. The census is a required
       query: a volume whose disk or mount paths cannot be read, or an enumeration
       that ends in an error, leaves it incomplete (census_failed), never smaller. */
    fv = FindFirstVolumeW(vol, MAX_PATH);
    if (fv == INVALID_HANDLE_VALUE) {
        query_failed(f, "FindFirstVolumeW");
        f->n_mounted = SAFETY_MAX_MOUNTS + 1;
        snprintf(f->detail, sizeof f->detail, "cannot list volumes");
        CloseHandle(h);
        return 0;
    }
    for (;;) {
        wchar_t small[512], *names = small, novs[MAX_PATH];
        DWORD disks[8], need = 0, cap = 512, e;
        ULONGLONG start = 0, len = 0;
        size_t L = wcslen(vol);
        int n, i, on = 0, broken = 0, done = 0;
        BOOL more;
        if (L == 0 || L >= MAX_PATH) {
            census_failed(f, "FindNextVolumeW", "malformed volume name");
            break;
        }
        wcscpy(novs, vol);
        if (novs[L - 1] == L'\\') { novs[L - 1] = L'\0'; }
#ifdef TAPECTL_TEST
        broken = tseam_fault_query("volume-extents");
#endif
        n = volume_disks(novs, disks, &start, &len, broken);
        if (n < 0) {
            char why[48];
            e = GetLastError();
            snprintf(why, sizeof why, "%s", hport_os_errname());
            /* No medium (an empty reader slot or drive): nothing is mounted there.
               Otherwise it is skipped only if it is provably on another device. */
            if (e != ERROR_NOT_READY && e != ERROR_NO_MEDIA_IN_DRIVE && !volume_elsewhere(novs, disk)) {
                census_failed(f, "IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS", why);
                break;
            }
        }
        for (i = 0; i < n; i++) { if (disks[i] == disk) { on = 1; } }
        while (on) {
#ifdef TAPECTL_TEST
            if (tseam_fault_query("mount-paths")) { cap = 0; }   /* control: the OS really fails the query */
#endif
            names[0] = L'\0';
            if (GetVolumePathNamesForVolumeNameW(vol, names, cap, &need)) { break; }
            e = GetLastError();
            if (e == ERROR_MORE_DATA && names == small && need > cap) {
                names = (wchar_t *)malloc((size_t)need * sizeof *names);
                if (names != NULL) { cap = need; continue; }
                names = small;
                SetLastError(ERROR_NOT_ENOUGH_MEMORY);
            }
            census_failed(f, "GetVolumePathNamesForVolumeNameW", hport_os_errname());
            done = 1;
            break;
        }
        if (on && !done && names[0] != L'\0') {           /* an empty list: not mounted */
            if (f->n_mounted < SAFETY_MAX_MOUNTS) {
                struct mounted_volume *m = &f->mounted[f->n_mounted];
                m->partition = (n == 1 && start == (ULONGLONG)LAYOUT_P1_START * 512u
                                && len == (ULONGLONG)LAYOUT_P1_SECTORS * 512u) ? 1 : 0;
                wide_to_utf8(novs, m->where, (int)sizeof m->where);
                f->n_mounted++;
            } else {
                f->n_mounted = SAFETY_MAX_MOUNTS + 1;
            }
        }
        if (names != small) { free(names); }
        if (done) { break; }
#ifdef TAPECTL_TEST
        if (tseam_fault_query("volume-enum")) {          /* control: the OS really fails the call */
            more = FindNextVolumeW(fv, vol, 0);
        } else
#endif
        more = FindNextVolumeW(fv, vol, MAX_PATH);
        if (!more) {
            if (GetLastError() != ERROR_NO_MORE_FILES) { census_failed(f, "FindNextVolumeW", hport_os_errname()); }
            break;
        }
    }
    FindVolumeClose(fv);

    if (f->n_mounted > 0 && f->n_mounted <= SAFETY_MAX_MOUNTS) {
        uint8_t lba0[512];
        OVERLAPPED ov;
        DWORD rd = 0;
        memset(&ov, 0, sizeof ov);
        if (ReadFile(h, lba0, sizeof lba0, &rd, &ov) && rd == sizeof lba0) {
            f->layout_ok = mbr_is_layout(lba0, f->bytes / 512u);
        } else {
            query_failed(f, "ReadFile (LBA 0)");
        }
    }
    CloseHandle(h);
    return 0;
}

const char *probe_unmount_call(void) { return "FSCTL_LOCK_VOLUME+FSCTL_DISMOUNT_VOLUME"; }

#ifdef TAPECTL_TEST
int probe_unmount_invalid(void)
{
    DWORD got = 0;
    return DeviceIoControl(INVALID_HANDLE_VALUE, FSCTL_DISMOUNT_VOLUME, NULL, 0, NULL, 0, &got, NULL) ? 0 : -1;
}
#endif

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
