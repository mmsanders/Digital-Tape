/*
 * iocap_posix.c — external OS-call capture for the SHIPPED tapectl
 * (WP-14 binding, Product #392). Test transport only; never linked into tapectl.
 *
 * The shipped binary carries no observation seam (that is the point of it), so
 * its refusal cases are observed from outside: this library is preloaded into
 * the process (Linux LD_PRELOAD, macOS DYLD_INSERT_LIBRARIES) and records the
 * file opens, reads, writes and flush calls the binary actually makes, with
 * their OS results, to the file named by IOCAP_LOG. It changes nothing: every
 * call is forwarded unchanged and its result returned unchanged.
 *
 * One JSON object per line:
 *   {"call":"open","path":...,"flags":...,"write":bool,"fd":n,"errno":e}
 *   {"call":"pread"|"pwrite","fd":n,"offset":o,"bytes":b,"ret":r,"errno":e}
 *   {"call":"fsync"|"fcntl_fullfsync"|"ioctl_synccache","fd":n,"ret":r,"errno":e}
 */

#if defined(__linux__)
#define _GNU_SOURCE
#endif

#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <unistd.h>
#if defined(__APPLE__)
#include <sys/disk.h>
#endif

static void logline(const char *fmt, ...)
{
    const char *path = getenv("IOCAP_LOG");
    int saved = errno;
    FILE *fp;
    va_list ap;
    if (path == NULL) { errno = saved; return; }
    fp = fopen(path, "a");
    if (fp == NULL) { errno = saved; return; }
    va_start(ap, fmt);
    vfprintf(fp, fmt, ap);
    va_end(ap);
    fputc('\n', fp);
    fclose(fp);
    errno = saved;
}

/* Proof that the capture was loaded: an empty log then means no calls. */
__attribute__((constructor)) static void iocap_attach(void)
{
    logline("{\"call\":\"iocap_attach\",\"pid\":%d}", (int)getpid());
}

static void log_open(const char *path, int flags, int fd, int err)
{
    char esc[1024];
    size_t i, j = 0;
    for (i = 0; path[i] && j < sizeof esc - 2; i++) {
        if (path[i] == '"' || path[i] == '\\') { esc[j++] = '\\'; }
        esc[j++] = path[i];
    }
    esc[j] = '\0';
    logline("{\"call\":\"open\",\"path\":\"%s\",\"flags\":%d,\"write\":%s,\"fd\":%d,\"errno\":%d}",
            esc, flags, (flags & O_ACCMODE) != O_RDONLY ? "true" : "false", fd, fd < 0 ? err : 0);
}

#if defined(__linux__)

typedef int (*open_fn)(const char *, int, ...);
typedef int (*openat_fn)(int, const char *, int, ...);
typedef ssize_t (*pread_fn)(int, void *, size_t, off_t);
typedef ssize_t (*pwrite_fn)(int, const void *, size_t, off_t);
typedef int (*fsync_fn)(int);
#define REAL(name, type) static type real_##name; if (!real_##name) { real_##name = (type)dlsym(RTLD_NEXT, #name); }

int open(const char *path, int flags, ...)
{
    mode_t mode = 0; int fd;
    REAL(open, open_fn);
    if (flags & O_CREAT) { va_list ap; va_start(ap, flags); mode = (mode_t)va_arg(ap, int); va_end(ap); }
    fd = real_open(path, flags, mode);
    log_open(path, flags, fd, errno);
    return fd;
}

int open64(const char *path, int flags, ...)
{
    mode_t mode = 0; int fd;
    REAL(open64, open_fn);
    if (flags & O_CREAT) { va_list ap; va_start(ap, flags); mode = (mode_t)va_arg(ap, int); va_end(ap); }
    fd = real_open64(path, flags, mode);
    log_open(path, flags, fd, errno);
    return fd;
}

int openat(int dirfd, const char *path, int flags, ...)
{
    mode_t mode = 0; int fd;
    REAL(openat, openat_fn);
    if (flags & O_CREAT) { va_list ap; va_start(ap, flags); mode = (mode_t)va_arg(ap, int); va_end(ap); }
    fd = real_openat(dirfd, path, flags, mode);
    log_open(path, flags, fd, errno);
    return fd;
}

/* Fortified builds (_FORTIFY_SOURCE) call these for open(path, flags). */
int __open_2(const char *path, int flags)
{
    int fd;
    REAL(open, open_fn);
    fd = real_open(path, flags);
    log_open(path, flags, fd, errno);
    return fd;
}

int __open64_2(const char *path, int flags)
{
    int fd;
    REAL(open64, open_fn);
    fd = real_open64(path, flags);
    log_open(path, flags, fd, errno);
    return fd;
}

ssize_t pread64(int fd, void *buf, size_t n, off_t off)
{
    ssize_t r;
    REAL(pread64, pread_fn);
    r = real_pread64(fd, buf, n, off);
    logline("{\"call\":\"pread\",\"fd\":%d,\"offset\":%lld,\"bytes\":%zu,\"ret\":%zd,\"errno\":%d}", fd, (long long)off, n, r, r < 0 ? errno : 0);
    return r;
}

ssize_t pwrite64(int fd, const void *buf, size_t n, off_t off)
{
    ssize_t r;
    REAL(pwrite64, pwrite_fn);
    r = real_pwrite64(fd, buf, n, off);
    logline("{\"call\":\"pwrite\",\"fd\":%d,\"offset\":%lld,\"bytes\":%zu,\"ret\":%zd,\"errno\":%d}", fd, (long long)off, n, r, r < 0 ? errno : 0);
    return r;
}

ssize_t pread(int fd, void *buf, size_t n, off_t off)
{
    ssize_t r;
    REAL(pread, pread_fn);
    r = real_pread(fd, buf, n, off);
    logline("{\"call\":\"pread\",\"fd\":%d,\"offset\":%lld,\"bytes\":%zu,\"ret\":%zd,\"errno\":%d}", fd, (long long)off, n, r, r < 0 ? errno : 0);
    return r;
}

ssize_t pwrite(int fd, const void *buf, size_t n, off_t off)
{
    ssize_t r;
    REAL(pwrite, pwrite_fn);
    r = real_pwrite(fd, buf, n, off);
    logline("{\"call\":\"pwrite\",\"fd\":%d,\"offset\":%lld,\"bytes\":%zu,\"ret\":%zd,\"errno\":%d}", fd, (long long)off, n, r, r < 0 ? errno : 0);
    return r;
}

int fsync(int fd)
{
    int r;
    REAL(fsync, fsync_fn);
    r = real_fsync(fd);
    logline("{\"call\":\"fsync\",\"fd\":%d,\"ret\":%d,\"errno\":%d}", fd, r, r < 0 ? errno : 0);
    return r;
}

#elif defined(__APPLE__)

/* dyld interposition: calls from the target image to these symbols go to the
   replacements; the replacements' own calls go to the originals. */
#define DYLD_INTERPOSE(_replacement, _replacee) \
    __attribute__((used)) static struct { const void *replacement; const void *replacee; } _interpose_##_replacee \
    __attribute__((section("__DATA,__interpose"))) = { (const void *)(unsigned long)&_replacement, (const void *)(unsigned long)&_replacee };

static int cap_open(const char *path, int flags, ...)
{
    mode_t mode = 0; int fd;
    if (flags & O_CREAT) { va_list ap; va_start(ap, flags); mode = (mode_t)va_arg(ap, int); va_end(ap); }
    fd = open(path, flags, mode);
    log_open(path, flags, fd, errno);
    return fd;
}
DYLD_INTERPOSE(cap_open, open)

static ssize_t cap_pread(int fd, void *buf, size_t n, off_t off)
{
    ssize_t r = pread(fd, buf, n, off);
    logline("{\"call\":\"pread\",\"fd\":%d,\"offset\":%lld,\"bytes\":%zu,\"ret\":%zd,\"errno\":%d}", fd, (long long)off, n, r, r < 0 ? errno : 0);
    return r;
}
DYLD_INTERPOSE(cap_pread, pread)

static ssize_t cap_pwrite(int fd, const void *buf, size_t n, off_t off)
{
    ssize_t r = pwrite(fd, buf, n, off);
    logline("{\"call\":\"pwrite\",\"fd\":%d,\"offset\":%lld,\"bytes\":%zu,\"ret\":%zd,\"errno\":%d}", fd, (long long)off, n, r, r < 0 ? errno : 0);
    return r;
}
DYLD_INTERPOSE(cap_pwrite, pwrite)

static int cap_fcntl(int fd, int cmd, ...)
{
    va_list ap; long arg; int r;
    va_start(ap, cmd); arg = va_arg(ap, long); va_end(ap);
    r = fcntl(fd, cmd, arg);
    if (cmd == F_FULLFSYNC) {
        logline("{\"call\":\"fcntl_fullfsync\",\"fd\":%d,\"ret\":%d,\"errno\":%d}", fd, r, r < 0 ? errno : 0);
    }
    return r;
}
DYLD_INTERPOSE(cap_fcntl, fcntl)

static int cap_ioctl(int fd, unsigned long req, ...)
{
    va_list ap; void *arg; int r;
    va_start(ap, req); arg = va_arg(ap, void *); va_end(ap);
    r = ioctl(fd, req, arg);
    if (req == DKIOCSYNCHRONIZECACHE) {
        logline("{\"call\":\"ioctl_synccache\",\"fd\":%d,\"ret\":%d,\"errno\":%d}", fd, r, r < 0 ? errno : 0);
    }
    return r;
}
DYLD_INTERPOSE(cap_ioctl, ioctl)

#endif
