/*
 * trace_test.c — the TAPECTL_TEST observation and fault seam (see tseam.h).
 *
 * COMPILED ONLY WITH -DTAPECTL_TEST. The trace is streamed: events go to the
 * file as they happen, so a full C-60 load (about 1.24 M writes) never sits in
 * memory, and a crash still leaves every event up to the crash. The closing
 * fields (target, facts, exit) are written by tseam_finish().
 */

#ifdef TAPECTL_TEST

#include "tseam.h"
#include "safety.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef TAPECTL_HEAD
#define TAPECTL_HEAD "unknown"
#endif

#if defined(_WIN32)
#define TS_PLATFORM "windows"
#elif defined(__APPLE__)
#define TS_PLATFORM "macos"
#else
#define TS_PLATFORM "linux"
#endif

static FILE *g_fp;
static int g_events;
static char g_op[32] = "";
static char g_target[512] = "";
static int g_target_is_device;
static unsigned long long g_target_bytes;
static char g_refusal[40] = "";
static int g_have_facts;
static struct device_facts g_facts;
static char g_verdict[40] = "";
static int g_facts_from_seam;
static unsigned long long g_writes, g_flushes;

static void json_str(const char *s)
{
    fputc('"', g_fp);
    for (; *s; s++) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') { fputc('\\', g_fp); fputc(c, g_fp); }
        else if (c < 0x20) { fprintf(g_fp, "\\u%04x", c); }
        else { fputc(c, g_fp); }
    }
    fputc('"', g_fp);
}

static void event_begin(const char *kind)
{
    fprintf(g_fp, "%s\n  {\"kind\":\"%s\"", g_events++ ? "," : "", kind);
}

/* ---------------------------------------------------------------- faults */

static const char *fault(void)
{
    const char *f = getenv("TAPECTL_TEST_FAULT");
    return f ? f : "";
}

int tseam_fault_noop_flush(void)         { return strcmp(fault(), "noop-flush") == 0; }
int tseam_fault_hidden_flush_error(void) { return strcmp(fault(), "hidden-flush-error") == 0; }
int tseam_fault_nonnull_binding(void)    { return strcmp(fault(), "nonnull-binding") == 0; }

int tseam_fault_read(uint64_t partition_lba, uint32_t count)
{
    const char *f = fault();
    unsigned long long at;
    if (strncmp(f, "read-error:", 11) != 0) { return 0; }
    at = strtoull(f + 11, NULL, 10);
    if (at < partition_lba || at >= partition_lba + count) { return 0; }
    tseam_read_fault(at, count);
    return 1;
}

/* ----------------------------------------------------------- observation */

void tseam_begin(int argc, char **argv)
{
    const char *path = getenv("TAPECTL_TEST_TRACE");
    int i;
    if (argc > 1) { snprintf(g_op, sizeof g_op, "%s", argv[1]); }
    if (path == NULL || *path == '\0') { return; }
    g_fp = fopen(path, "w");
    if (g_fp == NULL) { fprintf(stderr, "tapectl-test: cannot write trace %s\n", path); return; }
    fprintf(g_fp, "{\"schema\":\"wp14-trace-1\",\"platform\":\"%s\",\"build\":", TS_PLATFORM);
    json_str(TAPECTL_HEAD);
    fprintf(g_fp, ",\"capture\":\"tapectl-test host-port instrumentation (host/port/trace_test.c); engine not instrumented\"");
    fprintf(g_fp, ",\"fault\":");
    json_str(fault());
    fprintf(g_fp, ",\"operation\":");
    json_str(g_op);
    fprintf(g_fp, ",\"argv\":[");
    for (i = 1; i < argc; i++) { if (i > 1) { fputc(',', g_fp); } json_str(argv[i]); }
    fprintf(g_fp, "],\"events\":[");
}

void tseam_target(const char *path, int is_device, uint64_t bytes)
{
    snprintf(g_target, sizeof g_target, "%s", path);
    g_target_is_device = is_device;
    g_target_bytes = bytes;
}

void tseam_facts(const struct device_facts *f, const char *verdict, int from_seam)
{
    g_facts = *f;
    g_have_facts = 1;
    snprintf(g_verdict, sizeof g_verdict, "%s", verdict);
    g_facts_from_seam = from_seam;
}

void tseam_refusal(const char *id)
{
    snprintf(g_refusal, sizeof g_refusal, "%s", id);
}

void tseam_open(const char *path, int is_device, int writable, int ok)
{
    if (!g_fp) { return; }
    event_begin(writable ? "write_open" : "open");
    fprintf(g_fp, ",\"path\":");
    json_str(path);
    fprintf(g_fp, ",\"device\":%s,\"ok\":%s}", is_device ? "true" : "false", ok ? "true" : "false");
}

void tseam_write(uint64_t offset, size_t bytes, int ok)
{
    g_writes++;
    if (!g_fp) { return; }
    event_begin("write");
    fprintf(g_fp, ",\"offset\":%llu,\"bytes\":%llu,\"issued_before_return\":true,\"coalesced\":false,\"ok\":%s}",
            (unsigned long long)offset, (unsigned long long)bytes, ok ? "true" : "false");
}

void tseam_flush(const char *os_call, int os_success, int success)
{
    g_flushes++;
    if (!g_fp) { return; }
    event_begin("flush");
    fprintf(g_fp, ",\"os_call\":");
    json_str(os_call);
    fprintf(g_fp, ",\"os_success\":%s,\"success\":%s}", os_success ? "true" : "false", success ? "true" : "false");
}

void tseam_bind(uint64_t base_lba, uint32_t blocks, int write_is_null)
{
    if (!g_fp) { return; }
    event_begin("engine_bind");
    fprintf(g_fp, ",\"base_lba\":%llu,\"blocks\":%lu,\"write_is_null\":%s}",
            (unsigned long long)base_lba, (unsigned long)blocks, write_is_null ? "true" : "false");
}

void tseam_read_fault(uint64_t lba, uint32_t count)
{
    if (!g_fp) { return; }
    event_begin("read_fault");
    fprintf(g_fp, ",\"partition_lba\":%llu,\"call_blocks\":%lu}", (unsigned long long)lba, (unsigned long)count);
}

int tseam_finish(int exit_code)
{
    int i;
    if (!g_fp) { return exit_code; }
    fprintf(g_fp, "\n],\"target\":");
    json_str(g_target);
    fprintf(g_fp, ",\"target_is_device\":%s,\"target_bytes\":%llu", g_target_is_device ? "true" : "false", g_target_bytes);
    if (g_have_facts) {
        const struct device_facts *f = &g_facts;
        fprintf(g_fp, ",\"facts\":{\"source\":\"%s\",\"whole\":%d,\"removable\":%d,\"sd_bus\":%d,\"bytes\":%llu,"
                "\"holds_os\":%d,\"layout_ok\":%d,\"mounted\":[",
                g_facts_from_seam ? "TAPECTL_TEST_FACTS" : "platform probe", f->whole_device, f->removable,
                f->sd_bus, (unsigned long long)f->bytes, f->holds_os, f->layout_ok);
        for (i = 0; i < f->n_mounted && i < SAFETY_MAX_MOUNTS; i++) {
            fprintf(g_fp, "%s{\"partition\":%d,\"where\":", i ? "," : "", f->mounted[i].partition);
            json_str(f->mounted[i].where);
            fputc('}', g_fp);
        }
        fprintf(g_fp, "],\"policy\":");
        json_str(g_verdict);
        fputc('}', g_fp);
    }
    fprintf(g_fp, ",\"refusal\":");
    if (g_refusal[0]) { json_str(g_refusal); } else { fputs("null", g_fp); }
    fprintf(g_fp, ",\"writes\":%llu,\"flushes\":%llu,\"exit\":%d,\"success\":%s}\n",
            g_writes, g_flushes, exit_code, exit_code == 0 ? "true" : "false");
    fclose(g_fp);
    g_fp = NULL;
    return exit_code;
}

#endif /* TAPECTL_TEST */
