/*
 * hport_win.c — the host port on Windows 10 (docs/WP14-CLI-CONTRACT.md §6).
 *
 * Paths arrive as UTF-8 and are converted to UTF-16 for the W APIs. Every
 * transfer carries its own 64-bit offset in an OVERLAPPED on a synchronous
 * handle, so there is no shared file pointer and no 32-bit `long` anywhere.
 */

#if defined(_WIN32)

#include "hport.h"
#include "winutf.h"

#include <windows.h>
#include <winioctl.h>
#include <string.h>

enum hport_path hport_classify(const char *path)
{
    wchar_t w[1024];
    DWORD a;
    if (utf8_to_wide(path, w, 1024)) { return HPORT_OTHER; }
    a = GetFileAttributesW(w);
    if (a == INVALID_FILE_ATTRIBUTES) {
        DWORD e = GetLastError();
        return (e == ERROR_FILE_NOT_FOUND || e == ERROR_PATH_NOT_FOUND) ? HPORT_MISSING : HPORT_OTHER;
    }
    if (a & FILE_ATTRIBUTE_DIRECTORY) { return HPORT_OTHER; }
    return HPORT_REGULAR;
}

static int open_handle(struct hport *p, const char *path, DWORD disposition, int writable, int is_device)
{
    wchar_t w[1024];
    HANDLE h;
    memset(p, 0, sizeof *p);
    p->h = INVALID_HANDLE_VALUE;
    if (utf8_to_wide(path, w, 1024)) { return -1; }
    h = CreateFileW(w, GENERIC_READ | (writable ? GENERIC_WRITE : 0),
                    FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, disposition,
                    FILE_ATTRIBUTE_NORMAL | (is_device ? FILE_FLAG_WRITE_THROUGH : 0), NULL);
    if (h == INVALID_HANDLE_VALUE) { return -1; }
    p->h = h;
    p->writable = writable;
    p->is_device = is_device;
    p->flush_how = "FlushFileBuffers";
    return 0;
}

int hport_open(struct hport *p, const char *path, int is_device, int writable)
{
    if (open_handle(p, path, OPEN_EXISTING, writable, is_device)) { return -1; }
    if (is_device) {
        GET_LENGTH_INFORMATION li;
        DWORD got = 0;
        if (!DeviceIoControl(p->h, IOCTL_DISK_GET_LENGTH_INFO, NULL, 0, &li, sizeof li, &got, NULL)) {
            hport_close(p);
            return -1;
        }
        p->bytes = (uint64_t)li.Length.QuadPart;
    } else {
        LARGE_INTEGER sz;
        if (!GetFileSizeEx(p->h, &sz)) { hport_close(p); return -1; }
        p->bytes = (uint64_t)sz.QuadPart;
    }
    return 0;
}

int hport_create(struct hport *p, const char *path, uint64_t bytes)
{
    LARGE_INTEGER pos;
    DWORD got = 0;
    if (open_handle(p, path, CREATE_ALWAYS, 1, 0)) { return -1; }
    /* Best effort: a sparse file keeps a 64 GB test image cheap. */
    (void)DeviceIoControl(p->h, FSCTL_SET_SPARSE, NULL, 0, NULL, 0, &got, NULL);
    pos.QuadPart = (LONGLONG)bytes;
    if (!SetFilePointerEx(p->h, pos, NULL, FILE_BEGIN) || !SetEndOfFile(p->h)) {
        hport_close(p);
        return -1;
    }
    p->bytes = bytes;
    return 0;
}

static void at(OVERLAPPED *ov, uint64_t off)
{
    memset(ov, 0, sizeof *ov);
    ov->Offset = (DWORD)(off & 0xFFFFFFFFu);
    ov->OffsetHigh = (DWORD)(off >> 32);
}

int hport_read(struct hport *p, uint64_t off, void *buf, size_t len)
{
    unsigned char *b = (unsigned char *)buf;
    while (len > 0) {
        OVERLAPPED ov;
        DWORD want = len > 0x40000000u ? 0x40000000u : (DWORD)len, got = 0;
        at(&ov, off);
        if (!ReadFile(p->h, b, want, &got, &ov) || got == 0) { return -1; }
        b += got; off += got; len -= got;
    }
    return 0;
}

int hport_write(struct hport *p, uint64_t off, const void *buf, size_t len)
{
    const unsigned char *b = (const unsigned char *)buf;
    if (!p->writable) { return -1; }
    while (len > 0) {
        OVERLAPPED ov;
        DWORD want = len > 0x40000000u ? 0x40000000u : (DWORD)len, got = 0;
        at(&ov, off);
        if (!WriteFile(p->h, b, want, &got, &ov) || got == 0) { return -1; }
        b += got; off += got; len -= got;
    }
    return 0;
}

int hport_flush(struct hport *p)
{
    p->flushes++;
    return FlushFileBuffers(p->h) ? 0 : -1;
}

int hport_close(struct hport *p)
{
    int rc = 0;
    if (p->h != INVALID_HANDLE_VALUE && p->h != NULL) {
        rc = CloseHandle(p->h) ? 0 : -1;
        p->h = INVALID_HANDLE_VALUE;
    }
    return rc;
}

#endif /* _WIN32 */
