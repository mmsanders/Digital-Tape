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
#include "winutf.h"
#else
#include <fcntl.h>
#include <unistd.h>
#endif

#if defined(_WIN32)
static HANDLE g_h = INVALID_HANDLE_VALUE;
#else
static int g_fd = -1;
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

/* One record. On the first failure: stop, warn once, change nothing else. */
static void line(const char *json)
{
    char buf[2048];
    size_t len = strlen(json);
    if (!g_open || g_stopped) { return; }
    if (len + 1 > sizeof buf) { len = sizeof buf - 1; }
    memcpy(buf, json, len);
    buf[len] = '\n';
    if (os_write(buf, len + 1) != 0) {
        g_stopped = 1;
#if defined(_WIN32)
        fprintf(stderr, "tapectl: warning: report: cannot write %s (error %lu)\n", g_file, (unsigned long)GetLastError());
#else
        fprintf(stderr, "tapectl: warning: report: cannot write %s (%s)\n", g_file, strerror(errno));
#endif
    }
}

int report_open(const char *file, const char *tool, const char *version, const char *nonce)
{
    char rec[512], t[96], v[256];
#if defined(_WIN32)
    wchar_t w[1024];
    if (utf8_to_wide(file, w, 1024)) { snprintf(g_err, sizeof g_err, "path is not valid UTF-8"); return -1; }
    /* CREATE_NEW never opens an existing name; FILE_FLAG_OPEN_REPARSE_POINT keeps
       a reparse point at the leaf from being followed. */
    g_h = CreateFileW(w, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (g_h == INVALID_HANDLE_VALUE) { snprintf(g_err, sizeof g_err, "error %lu", (unsigned long)GetLastError()); return -1; }
#else
    /* O_CREAT|O_EXCL fails on any existing leaf, a dangling symlink included. */
    g_fd = open(file, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (g_fd < 0) { snprintf(g_err, sizeof g_err, "%s", strerror(errno)); return -1; }
#endif
    g_open = 1;
    g_file = file;
    report_json_string(t, sizeof t, tool);
    report_json_string(v, sizeof v, version);
    snprintf(rec, sizeof rec, "{\"t\":\"start\",\"tool\":%s,\"version\":%s,\"nonce\":\"%s\"}", t, v, nonce);
    line(rec);
    return 0;
}

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
    char rec[160];
    snprintf(rec, sizeof rec, "{\"t\":\"refusal\",\"id\":\"%s\",\"subject\":null}", id);
    line(rec);
}

void report_end(int exit_code)
{
    char rec[48];
    snprintf(rec, sizeof rec, "{\"t\":\"end\",\"exit\":%d}", exit_code);
    line(rec);
#if defined(_WIN32)
    if (g_open) { CloseHandle(g_h); g_h = INVALID_HANDLE_VALUE; }
#else
    if (g_open) { close(g_fd); g_fd = -1; }
#endif
    g_open = 0;
}
