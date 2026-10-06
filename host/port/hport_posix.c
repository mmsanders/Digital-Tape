/*
 * hport_posix.c — the host port on Linux and macOS (docs/WP14-CLI-CONTRACT.md §6).
 */

#if !defined(_WIN32)

#define _FILE_OFFSET_BITS 64
#if defined(__APPLE__)
#define _DARWIN_C_SOURCE
#else
#define _GNU_SOURCE
#endif

#include "hport.h"

#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>

#if defined(__APPLE__)
#include <sys/disk.h>
#else
#include <linux/fs.h>
#endif

enum hport_path hport_classify(const char *path)
{
    struct stat st;
    if (stat(path, &st) != 0) { return errno == ENOENT ? HPORT_MISSING : HPORT_OTHER; }
    if (S_ISREG(st.st_mode)) { return HPORT_REGULAR; }
    if (S_ISBLK(st.st_mode) || S_ISCHR(st.st_mode)) { return HPORT_DEVICE; }
    return HPORT_OTHER;
}

static int device_bytes(int fd, uint64_t *out)
{
#if defined(__APPLE__)
    uint64_t count = 0;
    uint32_t size = 0;
    if (ioctl(fd, DKIOCGETBLOCKCOUNT, &count) != 0 || ioctl(fd, DKIOCGETBLOCKSIZE, &size) != 0) { return -1; }
    *out = count * size;
    return 0;
#else
    uint64_t bytes = 0;
    if (ioctl(fd, BLKGETSIZE64, &bytes) != 0) { return -1; }
    *out = bytes;
    return 0;
#endif
}

int hport_os_open(struct hport *p, const char *path, int is_device, int writable)
{
    char raw[64];
    struct stat st;

    memset(p, 0, sizeof *p);
    p->fd = -1;
#if defined(__APPLE__)
    /* Raw I/O always goes through /dev/rdiskN (§2): the buffered /dev/diskN
       would put the buffer cache between the engine and the card. */
    if (is_device && strncmp(path, "/dev/disk", 9) == 0 && strlen(path) < sizeof raw - 1) {
        memcpy(raw, "/dev/r", 6);
        memcpy(raw + 6, path + 5, strlen(path + 5) + 1);
        path = raw;
    }
#else
    (void)raw;
#endif
    p->fd = open(path, (writable ? O_RDWR : O_RDONLY) | O_CLOEXEC);
    if (p->fd < 0) { return -1; }
    if (fstat(p->fd, &st) != 0) { (void)close(p->fd); p->fd = -1; return -1; }
    if (is_device) {
        if (device_bytes(p->fd, &p->bytes) != 0) { (void)close(p->fd); p->fd = -1; return -1; }
    } else {
        if (!S_ISREG(st.st_mode)) { (void)close(p->fd); p->fd = -1; return -1; }
        p->bytes = (uint64_t)st.st_size;
    }
    p->is_device = is_device;
    p->writable = writable;
#if defined(__APPLE__)
    p->flush_how = "F_FULLFSYNC";
#else
    p->flush_how = "fsync";
#endif
    return 0;
}

int hport_os_create(struct hport *p, const char *path, uint64_t bytes)
{
    memset(p, 0, sizeof *p);
    p->fd = open(path, O_RDWR | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    if (p->fd < 0) { return -1; }
    if (ftruncate(p->fd, (off_t)bytes) != 0) { (void)close(p->fd); p->fd = -1; return -1; }
    p->bytes = bytes;
    p->writable = 1;
#if defined(__APPLE__)
    p->flush_how = "F_FULLFSYNC";
#else
    p->flush_how = "fsync";
#endif
    return 0;
}

int hport_read(struct hport *p, uint64_t off, void *buf, size_t len)
{
    unsigned char *b = (unsigned char *)buf;
    while (len > 0) {
        ssize_t n = pread(p->fd, b, len, (off_t)off);
        if (n < 0 && errno == EINTR) { continue; }
        if (n <= 0) { return -1; }
        b += n; off += (uint64_t)n; len -= (size_t)n;
    }
    return 0;
}

int hport_os_write(struct hport *p, uint64_t off, const void *buf, size_t len)
{
    const unsigned char *b = (const unsigned char *)buf;
    if (!p->writable) { return -1; }
    while (len > 0) {
        ssize_t n = pwrite(p->fd, b, len, (off_t)off);
        if (n < 0 && errno == EINTR) { continue; }
        if (n <= 0) { return -1; }
        b += n; off += (uint64_t)n; len -= (size_t)n;
    }
    return 0;
}

int hport_os_flush(struct hport *p)
{
#if defined(__APPLE__)
    if (fcntl(p->fd, F_FULLFSYNC) == 0) { p->flush_how = "F_FULLFSYNC"; return 0; }
    /* #384 Q6: F_FULLFSYNC asks a filesystem to flush the drive's cache. On a
       raw disk node there is no filesystem, and the kernel may report it
       unsupported; then make the same request of the disk directly. Any other
       failure fails the flush. */
    /* ADR-164 §6: only an explicit unsupported-descriptor result permits it. */
    if (p->is_device && (errno == ENOTTY || errno == ENOTSUP)) {
        if (ioctl(p->fd, DKIOCSYNCHRONIZECACHE) == 0) {
            p->flush_how = "DKIOCSYNCHRONIZECACHE";
            return 0;
        }
    }
    return -1;
#else
    return fsync(p->fd) == 0 ? 0 : -1;
#endif
}

const char *hport_error(void)
{
    return strerror(errno);
}

int hport_close(struct hport *p)
{
    int rc = 0;
    if (p->fd >= 0) { rc = close(p->fd); p->fd = -1; }
    return rc == 0 ? 0 : -1;
}

#endif /* !_WIN32 */
