/*
 * report.c — the diagnostic report writer (APP-1A §1).
 */

#if !defined(_WIN32)
#define _GNU_SOURCE
#endif

#include "report.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#include <fcntl.h>
#include <io.h>
#include "winutf.h"
#else
#include <fcntl.h>
#include <pthread.h>
#include <unistd.h>
#endif

#if defined(_WIN32)
static HANDLE g_h = INVALID_HANDLE_VALUE;
static HANDLE g_parent = INVALID_HANDLE_VALUE;   /* report_open_bound: held until report_end */
static SRWLOCK g_lock = SRWLOCK_INIT;
#define LOCK()   AcquireSRWLockExclusive(&g_lock)
#define UNLOCK() ReleaseSRWLockExclusive(&g_lock)
#else
static int g_fd = -1;
static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
#define LOCK()   pthread_mutex_lock(&g_lock)
#define UNLOCK() pthread_mutex_unlock(&g_lock)
#endif
static int g_open, g_stopped;
static const char *g_file;
static char g_err[160];

const char *report_error(void) { return g_err; }

int report_nonce_ok(const char *n)
{
    int i;
    for (i = 0; i < 32; i++) {
        if (!((n[i] >= '0' && n[i] <= '9') || (n[i] >= 'a' && n[i] <= 'f'))) { return 0; }
    }
    return n[32] == '\0';
}

size_t report_json_string(char *buf, size_t cap, const char *s)
{
    size_t n = 0;
    const unsigned char *p = (const unsigned char *)s;
#define PUT(c) do { if (n + 1 < cap) { buf[n] = (char)(c); } n++; } while (0)
    PUT('"');
    for (; *p; p++) {
        if (*p == '"' || *p == '\\') { PUT('\\'); PUT(*p); }
        else if (*p == '\n') { PUT('\\'); PUT('n'); }
        else if (*p == '\r') { PUT('\\'); PUT('r'); }
        else if (*p == '\t') { PUT('\\'); PUT('t'); }
        else if (*p < 0x20) {
            static const char hex[] = "0123456789abcdef";
            PUT('\\'); PUT('u'); PUT('0'); PUT('0'); PUT(hex[*p >> 4]); PUT(hex[*p & 15]);
        } else { PUT(*p); }
    }
    PUT('"');
#undef PUT
    if (cap > 0) { buf[n < cap ? n : cap - 1] = '\0'; }
    return n;
}

static int os_write(const char *s, size_t len)
{
#if defined(_WIN32)
    DWORD w = 0;
    return WriteFile(g_h, s, (DWORD)len, &w, NULL) && w == (DWORD)len ? 0 : -1;
#else
    while (len > 0) {
        ssize_t w = write(g_fd, s, len);
        if (w < 0 && errno == EINTR) { continue; }
        if (w <= 0) { return -1; }
        s += w;
        len -= (size_t)w;
    }
    return 0;
#endif
}

/* One record. On the first failure: stop, warn once, change nothing else. The
   warning is printed after the lock is released: with stderr captured, it
   travels back through report_stderr on the capture thread. */
static void line(const char *json)
{
    char buf[2048];
    size_t len = strlen(json);
    int warn = 0;
#if defined(_WIN32)
    unsigned long why = 0;
#else
    int why = 0;
#endif
    LOCK();
    if (g_open && !g_stopped) {
        if (len + 1 > sizeof buf) { len = sizeof buf - 1; }
        memcpy(buf, json, len);
        buf[len] = '\n';
        if (os_write(buf, len + 1) != 0) {
            g_stopped = 1;
            warn = 1;
#if defined(_WIN32)
            why = (unsigned long)GetLastError();
#else
            why = errno;
#endif
        }
    }
    UNLOCK();
    if (warn) {
#if defined(_WIN32)
        fprintf(stderr, "tapectl: warning: report: cannot write %s (error %lu)\n", g_file, why);
#else
        fprintf(stderr, "tapectl: warning: report: cannot write %s (%s)\n", g_file, strerror(why));
#endif
    }
}

static void start_record(const char *tool, const char *version, const char *nonce)
{
    char rec[512], t[96], v[256];
    g_open = 1;
    report_json_string(t, sizeof t, tool);
    report_json_string(v, sizeof v, version);
    snprintf(rec, sizeof rec, "{\"t\":\"start\",\"tool\":%s,\"version\":%s,\"nonce\":\"%s\"}", t, v, nonce);
    line(rec);
}

int report_open(const char *file, const char *tool, const char *version, const char *nonce)
{
#if defined(_WIN32)
    wchar_t w[1024];
    if (utf8_to_wide(file, w, 1024)) { snprintf(g_err, sizeof g_err, "path is not valid UTF-8"); return -1; }
    /* CREATE_NEW never opens an existing name; FILE_FLAG_OPEN_REPARSE_POINT keeps
       a reparse point at the leaf from being followed. Readers may share it, so
       the app can follow progress while the child runs. */
    g_h = CreateFileW(w, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (g_h == INVALID_HANDLE_VALUE) { snprintf(g_err, sizeof g_err, "error %lu", (unsigned long)GetLastError()); return -1; }
#else
    /* O_CREAT|O_EXCL fails on any existing leaf, a dangling symlink included. */
    g_fd = open(file, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (g_fd < 0) { snprintf(g_err, sizeof g_err, "%s", strerror(errno)); return -1; }
#endif
    g_file = file;
    start_record(tool, version, nonce);
    return 0;
}

#if defined(_WIN32)
/* The directory part of `w` (modified in place); returns the leaf, or NULL. */
static wchar_t *split_leaf(wchar_t *w)
{
    wchar_t *slash = NULL, *p;
    for (p = w; *p; p++) { if (*p == L'\\' || *p == L'/') { slash = p; } }
    if (slash == NULL || slash[1] == L'\0') { return NULL; }
    *slash = L'\0';
    return slash + 1;
}

/* A prefix that is a volume or share root rather than a directory we can judge:
   "C:", "\\?", "\\?\C:", "\\server", "\\server\share". */
static int is_root_prefix(const wchar_t *w, size_t n)
{
    size_t seps = 0, i;
    if (n == 0 || w[n - 1] == L':') { return 1; }
    if (n >= 2 && (w[0] == L'\\' || w[0] == L'/') && (w[1] == L'\\' || w[1] == L'/')) {
        for (i = 0; i < n; i++) { if (w[i] == L'\\' || w[i] == L'/') { seps++; } }
        if (n >= 3 && w[2] == L'?') { return seps <= 3 || (n >= 2 && w[n - 1] == L':'); }
        return seps <= 3;
    }
    return 0;
}

int report_open_bound(const char *file, const char *tool, const char *version, const char *nonce)
{
    wchar_t full[1024], dir[1024], *leaf;
    BY_HANDLE_FILE_INFORMATION info;
    size_t i, n;
    if (utf8_to_wide(file, full, 1024)) { snprintf(g_err, sizeof g_err, "path is not valid UTF-8"); return -1; }
    memcpy(dir, full, sizeof dir);
    leaf = split_leaf(dir);
    if (leaf == NULL) { snprintf(g_err, sizeof g_err, "report path has no directory"); return -1; }
    /* Hold the parent itself, never what a reparse point names, and without
       FILE_SHARE_DELETE: while it is open neither it nor any ancestor of it can
       be renamed, so the checks below stay true until report_end. */
    g_parent = CreateFileW(dir, FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                           FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (g_parent == INVALID_HANDLE_VALUE) {
        snprintf(g_err, sizeof g_err, "cannot hold the report directory (error %lu)", (unsigned long)GetLastError());
        return -1;
    }
    if (!GetFileInformationByHandle(g_parent, &info) || !(info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
        || (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
        snprintf(g_err, sizeof g_err, "report directory is not a plain directory");
        goto refuse;
    }
    /* Every ancestor: a plain directory, never a symlink or junction. */
    n = wcslen(dir);
    for (i = 1; i <= n; i++) {
        if (i < n && dir[i] != L'\\' && dir[i] != L'/') { continue; }
        {
            wchar_t prefix[1024];
            DWORD a;
            memcpy(prefix, dir, i * sizeof(wchar_t));
            prefix[i] = L'\0';
            if (is_root_prefix(prefix, i)) { continue; }
            a = GetFileAttributesW(prefix);
            if (a == INVALID_FILE_ATTRIBUTES || !(a & FILE_ATTRIBUTE_DIRECTORY) || (a & FILE_ATTRIBUTE_REPARSE_POINT)) {
                snprintf(g_err, sizeof g_err, "an ancestor of the report is not a plain directory");
                goto refuse;
            }
        }
    }
    g_h = CreateFileW(full, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (g_h == INVALID_HANDLE_VALUE) { snprintf(g_err, sizeof g_err, "error %lu", (unsigned long)GetLastError()); goto refuse; }
    g_file = file;
    start_record(tool, version, nonce);
    return 0;
refuse:
    CloseHandle(g_parent);
    g_parent = INVALID_HANDLE_VALUE;
    return -1;
}
#else
int report_open_bound(const char *file, const char *tool, const char *version, const char *nonce)
{
    char comp[1024];
    const char *p = file, *slash;
    int dfd = open(file[0] == '/' ? "/" : ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (dfd < 0) { snprintf(g_err, sizeof g_err, "%s", strerror(errno)); return -1; }
    /* Walk each directory component relative to the last, never following a
       symlink; the leaf is then created in the final directory itself. */
    while ((slash = strchr(p, '/')) != NULL) {
        size_t len = (size_t)(slash - p);
        if (len > 0 && !(len == 1 && p[0] == '.')) {
            int next;
            if (len >= sizeof comp) { close(dfd); snprintf(g_err, sizeof g_err, "report path too long"); return -1; }
            memcpy(comp, p, len);
            comp[len] = '\0';
            next = openat(dfd, comp, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
            if (next < 0) {
                snprintf(g_err, sizeof g_err, "report directory %s: %s", comp, strerror(errno));
                close(dfd);
                return -1;
            }
            close(dfd);
            dfd = next;
        }
        p = slash + 1;
    }
    if (*p == '\0') { close(dfd); snprintf(g_err, sizeof g_err, "report path has no file name"); return -1; }
    g_fd = openat(dfd, p, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    close(dfd);
    if (g_fd < 0) { snprintf(g_err, sizeof g_err, "%s", strerror(errno)); return -1; }
    g_file = file;
    start_record(tool, version, nonce);
    return 0;
}
#endif

void report_progress(const char *step, uint64_t done, uint64_t total)
{
    char rec[160];
    snprintf(rec, sizeof rec, "{\"t\":\"progress\",\"step\":\"%s\",\"done\":%llu,\"total\":%llu}",
             step, (unsigned long long)done, (unsigned long long)total);
    line(rec);
}

void report_refusal_os(const char *id, const char *os_error)
{
    char rec[768], e[512];
    report_json_string(e, sizeof e, os_error);
    snprintf(rec, sizeof rec, "{\"t\":\"refusal\",\"id\":\"%s\",\"subject\":null,\"os_error\":%s}", id, e);
    line(rec);
}

void report_refusal(const char *id)
{
    report_refusal_payload(id, "");
}

void report_refusal_payload(const char *id, const char *payload)
{
    char rec[1536];
    snprintf(rec, sizeof rec, "{\"t\":\"refusal\",\"id\":\"%s\",\"subject\":null%s}", id, payload);
    line(rec);
}

void report_stderr(const char *text)
{
    char rec[1200], s[1100];
    report_json_string(s, sizeof s, text);
    snprintf(rec, sizeof rec, "{\"t\":\"stderr\",\"text\":%s}", s);
    line(rec);
}

void report_end(int exit_code)
{
    char rec[48];
    snprintf(rec, sizeof rec, "{\"t\":\"end\",\"exit\":%d}", exit_code);
    line(rec);
    LOCK();
#if defined(_WIN32)
    if (g_open) { CloseHandle(g_h); g_h = INVALID_HANDLE_VALUE; }
    if (g_parent != INVALID_HANDLE_VALUE) { CloseHandle(g_parent); g_parent = INVALID_HANDLE_VALUE; }
#else
    if (g_open) { close(g_fd); g_fd = -1; }
#endif
    g_open = 0;
    UNLOCK();
}

/* ------------------------------------------------------- stderr capture */

static int g_capturing;
static char g_pending[1024];
static size_t g_have;

/* Bytes read from the capture pipe: complete lines become records; a line
   longer than the buffer is recorded in pieces. Called on the pump thread. */
static void take(const char *b, size_t n)
{
    size_t i;
    for (i = 0; i < n; i++) {
        if (b[i] == '\n' || g_have == sizeof g_pending - 1) {
            if (b[i] != '\n') { g_pending[g_have++] = b[i]; }
            if (g_have > 0 && g_pending[g_have - 1] == '\r') { g_have--; }
            g_pending[g_have] = '\0';
            report_stderr(g_pending);
            g_have = 0;
        } else {
            g_pending[g_have++] = b[i];
        }
    }
}

static void take_rest(void)
{
    if (g_have > 0) { g_pending[g_have] = '\0'; report_stderr(g_pending); g_have = 0; }
}

#if defined(_WIN32)
static HANDLE g_pipe_r = INVALID_HANDLE_VALUE, g_pump;
static int g_saved = -1;

static DWORD WINAPI pump(LPVOID unused)
{
    char b[4096];
    DWORD got;
    (void)unused;
    while (ReadFile(g_pipe_r, b, sizeof b, &got, NULL) && got > 0) {
        if (g_saved >= 0) { (void)_write(g_saved, b, (unsigned)got); }
        take(b, got);
    }
    take_rest();
    return 0;
}

int report_capture_stderr(void)
{
    HANDLE w;
    int fd;
    if (!g_open || g_capturing) { return 0; }
    fflush(stderr);
    if (!CreatePipe(&g_pipe_r, &w, NULL, 65536)) { return -1; }
    g_saved = _dup(2);
    fd = _open_osfhandle((intptr_t)w, _O_BINARY);
    if (fd < 0 || _dup2(fd, 2) != 0) {
        if (fd >= 0) { _close(fd); } else { CloseHandle(w); }
        CloseHandle(g_pipe_r);
        g_pipe_r = INVALID_HANDLE_VALUE;
        if (g_saved >= 0) { _close(g_saved); g_saved = -1; }
        return -1;
    }
    _close(fd);
    (void)SetStdHandle(STD_ERROR_HANDLE, (HANDLE)_get_osfhandle(2));
    g_pump = CreateThread(NULL, 0, pump, NULL, 0, NULL);
    if (g_pump == NULL) { g_capturing = 1; report_release_stderr(); return -1; }
    g_capturing = 1;
    return 0;
}

void report_release_stderr(void)
{
    if (!g_capturing) { return; }
    fflush(stderr);
    /* Replacing fd 2 closes the pipe's only write end, so the pump sees EOF. */
    if (g_saved >= 0) {
        (void)_dup2(g_saved, 2);
        (void)SetStdHandle(STD_ERROR_HANDLE, (HANDLE)_get_osfhandle(2));
    } else {
        (void)_close(2);
    }
    if (g_pump != NULL) { WaitForSingleObject(g_pump, INFINITE); CloseHandle(g_pump); g_pump = NULL; }
    CloseHandle(g_pipe_r);
    g_pipe_r = INVALID_HANDLE_VALUE;
    if (g_saved >= 0) { _close(g_saved); g_saved = -1; }
    g_capturing = 0;
}
#else
static int g_pipe_r = -1, g_saved = -1;
static pthread_t g_pump;

static void *pump(void *unused)
{
    char b[4096];
    (void)unused;
    for (;;) {
        ssize_t got = read(g_pipe_r, b, sizeof b);
        if (got < 0 && errno == EINTR) { continue; }
        if (got <= 0) { break; }
        if (g_saved >= 0) {
            ssize_t off = 0;
            while (off < got) {
                ssize_t w = write(g_saved, b + off, (size_t)(got - off));
                if (w < 0 && errno == EINTR) { continue; }
                if (w <= 0) { break; }
                off += w;
            }
        }
        take(b, (size_t)got);
    }
    take_rest();
    return NULL;
}

int report_capture_stderr(void)
{
    int p[2];
    if (!g_open || g_capturing) { return 0; }
    fflush(stderr);
    if (pipe(p) != 0) { return -1; }
    g_saved = dup(2);
    if (dup2(p[1], 2) < 0) {
        close(p[0]); close(p[1]);
        if (g_saved >= 0) { close(g_saved); g_saved = -1; }
        return -1;
    }
    close(p[1]);
    g_pipe_r = p[0];
    if (pthread_create(&g_pump, NULL, pump, NULL) != 0) {
        if (g_saved >= 0) { (void)dup2(g_saved, 2); close(g_saved); g_saved = -1; }
        close(g_pipe_r);
        g_pipe_r = -1;
        return -1;
    }
    g_capturing = 1;
    return 0;
}

void report_release_stderr(void)
{
    if (!g_capturing) { return; }
    fflush(stderr);
    /* Replacing fd 2 closes the pipe's only write end, so the pump sees EOF. */
    if (g_saved >= 0) { (void)dup2(g_saved, 2); } else { (void)close(2); }
    (void)pthread_join(g_pump, NULL);
    close(g_pipe_r);
    g_pipe_r = -1;
    if (g_saved >= 0) { close(g_saved); g_saved = -1; }
    g_capturing = 0;
}
#endif
