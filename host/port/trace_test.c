/*
 * trace_test.c — the TAPECTL_TEST observation and fault seam (see tseam.h).
 *
 * COMPILED ONLY WITH -DTAPECTL_TEST. The trace is streamed: events go to the
 * file as they happen, so a full C-60 load never sits in memory, and a crash
 * still leaves every event up to the crash. The closing fields are written by
 * tseam_finish().
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

#define CHUNK_BASE_LBA   2048u     /* tapefs §3: chunk store, partition-relative */
#define CHUNK_BLOCKS     1024u

static FILE *g_fp;
static int g_events;
static char g_op[32] = "";
static char g_target[512] = "";
static int g_target_set, g_target_is_device;
static unsigned long long g_target_bytes;
static char g_refusal[40] = "";
static int g_have_facts;
static struct device_facts g_facts;
static char g_verdict[40] = "";
static int g_facts_from_seam;
static unsigned long long g_writes, g_flushes, g_reads;
static int g_engine_used;
static int g_payloads;

/* Engine-call context for reads. */
static const char *g_phase = "other";
static char g_side;
static long long g_frame = -1;
static unsigned long long g_view_base;   /* partition base LBA of the last binding */

/* A pending run of joined successful reads. */
static struct {
    int open;
    unsigned long long offset, bytes, calls;
    const char *phase;
    char side;
    long long frame;
    int chunk;          /* -1: not the chunk store */
} g_run;

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

static void str_or_null(const char *s)
{
    if (s) { json_str(s); } else { fputs("null", g_fp); }
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
int tseam_fault_native_flush_error(void) { return strcmp(fault(), "native-flush-error") == 0; }
int tseam_fault_nonnull_binding(void)    { return strcmp(fault(), "nonnull-binding") == 0; }
int tseam_fault_unmount(void)            { return strcmp(fault(), "unmount-error") == 0; }

int tseam_fault_read(uint64_t partition_lba, uint32_t count)
{
    const char *f = fault();
    unsigned long long at;
    if (strncmp(f, "read-error:", 11) != 0) { return 0; }
    at = strtoull(f + 11, NULL, 10);
    return at >= partition_lba && at < partition_lba + count;
}

int tseam_fault_target_read(uint64_t offset, size_t bytes)
{
    const char *f = fault();
    unsigned long long lba;
    if (strncmp(f, "target-read-error:", 18) != 0) { return 0; }
    lba = strtoull(f + 18, NULL, 10);
    return lba * 512u >= offset && lba * 512u < offset + bytes;
}

/* ------------------------------------------------------------ read runs */

static void run_flush(void)
{
    if (!g_run.open || !g_fp) { g_run.open = 0; return; }
    event_begin("read");
    fprintf(g_fp, ",\"offset\":%llu,\"bytes\":%llu,\"success\":true,\"calls\":%llu,\"phase\":\"%s\"",
            g_run.offset, g_run.bytes, g_run.calls, g_run.phase);
    if (g_run.side) { fprintf(g_fp, ",\"side\":\"%c\"", g_run.side); }
    if (g_run.frame >= 0) { fprintf(g_fp, ",\"frame\":%lld", g_run.frame); }
    if (g_run.chunk >= 0) { fprintf(g_fp, ",\"referenced_chunk\":true,\"chunk\":%d", g_run.chunk); }
    fputc('}', g_fp);
    g_run.open = 0;
}

static int chunk_of(uint64_t offset)
{
    unsigned long long lba = offset / 512u;
    if (lba < g_view_base + CHUNK_BASE_LBA) { return -1; }
    return (int)((lba - g_view_base - CHUNK_BASE_LBA) / CHUNK_BLOCKS);
}

/* ----------------------------------------------------------- observation */

void tseam_begin(int argc, char **argv)
{
    const char *path = getenv("TAPECTL_TEST_TRACE");
    const char *pay = getenv("TAPECTL_TEST_PAYLOADS");
    int i;
    if (argc > 1) { snprintf(g_op, sizeof g_op, "%s", argv[1]); }
    g_payloads = (pay != NULL && strcmp(pay, "1") == 0) || strcmp(g_op, "provision") == 0;
    if (path == NULL || *path == '\0') { return; }
    g_fp = fopen(path, "w");
    if (g_fp == NULL) { fprintf(stderr, "tapectl-test: cannot write trace %s\n", path); return; }
    fprintf(g_fp, "{\"schema\":\"wp14-trace-1\",\"platform\":\"%s\",\"build\":", TS_PLATFORM);
    json_str(TAPECTL_HEAD);
    fprintf(g_fp, ",\"capture\":\"tapectl-test host-port and engine-call-site instrumentation (host/port/trace_test.c); "
                  "engine not instrumented; adjacent successful reads joined\"");
    fprintf(g_fp, ",\"fault\":");
    json_str(fault());
    fprintf(g_fp, ",\"payloads\":%s,\"operation\":", g_payloads ? "true" : "false");
    json_str(g_op);
    fprintf(g_fp, ",\"argv\":[");
    for (i = 1; i < argc; i++) { if (i > 1) { fputc(',', g_fp); } json_str(argv[i]); }
    fprintf(g_fp, "],\"events\":[");
}

void tseam_target(const char *path, int is_device, uint64_t bytes)
{
    snprintf(g_target, sizeof g_target, "%s", path);
    g_target_set = 1;
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

void tseam_engine_used(void) { g_engine_used = 1; }
void tseam_set_view_base(uint64_t base_lba) { g_view_base = base_lba; }

void tseam_phase(const char *phase, char side, int64_t frame)
{
    g_phase = phase;
    g_side = side;
    g_frame = frame;
}

void tseam_open(const char *path, int is_device, int writable, int ok)
{
    if (!g_fp) { return; }
    run_flush();
    event_begin(writable ? "write_open" : "open");
    fprintf(g_fp, ",\"path\":");
    json_str(path);
    fprintf(g_fp, ",\"device\":%s,\"ok\":%s}", is_device ? "true" : "false", ok ? "true" : "false");
}

void tseam_read(uint64_t offset, size_t bytes, int ok, const char *os_error, const char *flt)
{
    int chunk;
    g_reads++;
    if (!g_fp) { return; }
    chunk = strcmp(g_phase, "service") == 0 ? chunk_of(offset) : -1;
    if (ok && !flt) {
        if (g_run.open && g_run.offset + g_run.bytes == offset && g_run.phase == g_phase
            && g_run.side == g_side && g_run.frame == g_frame && (g_run.chunk >= 0) == (chunk >= 0)) {
            g_run.bytes += bytes;
            g_run.calls++;
            return;
        }
        run_flush();
        g_run.open = 1;
        g_run.offset = offset;
        g_run.bytes = bytes;
        g_run.calls = 1;
        g_run.phase = g_phase;
        g_run.side = g_side;
        g_run.frame = g_frame;
        g_run.chunk = chunk;
        return;
    }
    run_flush();
    event_begin("read");
    fprintf(g_fp, ",\"offset\":%llu,\"bytes\":%llu,\"success\":%s,\"calls\":1,\"phase\":\"%s\"",
            (unsigned long long)offset, (unsigned long long)bytes, ok ? "true" : "false", g_phase);
    if (g_side) { fprintf(g_fp, ",\"side\":\"%c\"", g_side); }
    if (g_frame >= 0) { fprintf(g_fp, ",\"frame\":%lld", g_frame); }
    if (chunk >= 0) { fprintf(g_fp, ",\"referenced_chunk\":true,\"chunk\":%d", chunk); }
    fprintf(g_fp, ",\"os_error\":");
    str_or_null(os_error);
    fprintf(g_fp, ",\"fault\":");
    str_or_null(flt);
    fputc('}', g_fp);
}

void tseam_write(uint64_t offset, size_t bytes, const void *data, int ok)
{
    g_writes++;
    if (!g_fp) { return; }
    run_flush();
    event_begin("write");
    fprintf(g_fp, ",\"offset\":%llu,\"bytes\":%llu,\"issued_before_return\":true,\"coalesced\":false,\"ok\":%s",
            (unsigned long long)offset, (unsigned long long)bytes, ok ? "true" : "false");
    if (g_payloads && data != NULL) {
        const unsigned char *b = (const unsigned char *)data;
        size_t i;
        fputs(",\"data_hex\":\"", g_fp);
        for (i = 0; i < bytes; i++) { fprintf(g_fp, "%02x", b[i]); }
        fputc('"', g_fp);
    }
    fputc('}', g_fp);
}

void tseam_flush(const char *os_call, int os_success, const char *os_error, int success,
                 const char *fullfsync_unsupported, const char *flt)
{
    g_flushes++;
    if (!g_fp) { return; }
    run_flush();
    event_begin("flush");
    fprintf(g_fp, ",\"os_call\":");
    json_str(os_call);
    fprintf(g_fp, ",\"os_success\":%s,\"os_error\":", os_success ? "true" : "false");
    str_or_null(os_error);
    fprintf(g_fp, ",\"success\":%s", success ? "true" : "false");
    if (fullfsync_unsupported) {
        fprintf(g_fp, ",\"fullfsync_unsupported\":");
        json_str(fullfsync_unsupported);
    }
    fprintf(g_fp, ",\"fault\":");
    str_or_null(flt);
    fputc('}', g_fp);
}

void tseam_bind(uint64_t base_lba, uint32_t blocks, int write_is_null)
{
    g_view_base = base_lba;
    if (!g_fp) { return; }
    run_flush();
    event_begin("engine_bind");
    fprintf(g_fp, ",\"base_lba\":%llu,\"blocks\":%lu,\"write_is_null\":%s}",
            (unsigned long long)base_lba, (unsigned long)blocks, write_is_null ? "true" : "false");
}

void tseam_mount(char side, int cold, const char *result)
{
    g_engine_used = 1;
    if (!g_fp) { return; }
    run_flush();
    event_begin("engine_mount");
    fprintf(g_fp, ",\"side\":\"%c\",\"cold\":%s,\"result\":", side, cold ? "true" : "false");
    json_str(result);
    fputc('}', g_fp);
}

void tseam_info(char side, int needs_repair, int side_b_valid)
{
    if (!g_fp) { return; }
    run_flush();
    event_begin("engine_info");
    fprintf(g_fp, ",\"side\":\"%c\",\"needs_repair\":%s,\"side_b_valid\":%s}", side,
            needs_repair ? "true" : "false", side_b_valid ? "true" : "false");
}

void tseam_unmount(const char *where, const char *os_call, int ok, const char *os_error, const char *flt)
{
    if (!g_fp) { return; }
    run_flush();
    event_begin("unmount");
    fprintf(g_fp, ",\"where\":");
    json_str(where);
    fprintf(g_fp, ",\"os_call\":");
    json_str(os_call);
    fprintf(g_fp, ",\"os_success\":%s,\"os_error\":", ok ? "true" : "false");
    str_or_null(os_error);
    fprintf(g_fp, ",\"fault\":");
    str_or_null(flt);
    fputc('}', g_fp);
}

int tseam_finish(int exit_code)
{
    int i;
    if (!g_fp) { return exit_code; }
    run_flush();
    fprintf(g_fp, "\n],\"target\":");
    json_str(g_target);
    fprintf(g_fp, ",\"target_kind\":");
    if (g_target_set) { json_str(g_target_is_device ? "device" : "image"); } else { fputs("null", g_fp); }
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
    fprintf(g_fp, ",\"engine_used\":%s,\"reads\":%llu,\"writes\":%llu,\"flushes\":%llu,\"exit\":%d,\"success\":%s}\n",
            g_engine_used ? "true" : "false", g_reads, g_writes, g_flushes, exit_code, exit_code == 0 ? "true" : "false");
    fclose(g_fp);
    g_fp = NULL;
    return exit_code;
}

#endif /* TAPECTL_TEST */
