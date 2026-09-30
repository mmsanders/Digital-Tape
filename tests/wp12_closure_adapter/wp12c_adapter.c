/*
 * WP-12/WP-12a R53 closure-gap product adapter.
 *
 * Software-owned binding for the imported verifier package
 * tests/wp12_closure_r53. Public header only; it does not import the oracle
 * and decides nothing. run_product.py writes each case's device image from
 * the package's own pinned fixture builders; this program loads that image
 * into a caller-owned simulator, drives the public API per ADAPTER.md, and
 * prints one JSON object of raw observations.
 *
 * Usage:
 *   wp12c_adapter render IMAGE
 *   wp12c_adapter fault IMAGE OP(respool|promote) SIDE(A|B) BUDGET
 *                 RULE(first_of_call|first_after_write) INJECT_OP CALL LBA COUNT
 */
#include "tape.h"

#include <openssl/sha.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BLOCK 512u
#define SLOT_BYTES 65536u
#define LBA_A0 8u
#define LBA_A1 136u
#define LBA_B0 264u
#define LBA_B1 392u
#define RENDER_FRAMES 4096u
#define RATE_ONE 65536
#define RENDER_SERVICE_BUDGET 64u
#define RESPOOL_BUDGET 64u
#define PROBE_FRAMES 16u
/* Callbacks return non-zero on failure (Engine API §3); this simulator uses 1. */
#define SIM_FAIL_RC 1

/* ------------------------------------------------------------------------ */
/* output                                                                    */
/* ------------------------------------------------------------------------ */

struct buf { char *p; size_t len, cap; };

static void buf_add(struct buf *b, const char *s, size_t n)
{
    if (b->len + n + 1u > b->cap) {
        while (b->len + n + 1u > b->cap) b->cap = b->cap ? b->cap * 2u : 4096u;
        b->p = realloc(b->p, b->cap);
        if (b->p == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    }
    memcpy(b->p + b->len, s, n);
    b->len += n;
    b->p[b->len] = '\0';
}

static void buf_str(struct buf *b, const char *s) { buf_add(b, s, strlen(s)); }

#if defined(__GNUC__)
static void buf_fmt(struct buf *b, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
#endif
static void buf_fmt(struct buf *b, const char *fmt, ...)
{
    char s[512];
    va_list ap;
    int n;
    va_start(ap, fmt);
    n = vsnprintf(s, sizeof s, fmt, ap);
    va_end(ap);
    if (n < 0 || (size_t)n >= sizeof s) { fprintf(stderr, "format overflow\n"); exit(3); }
    buf_add(b, s, (size_t)n);
}

static void buf_hex(struct buf *b, const unsigned char *p, size_t n)
{
    static const char d[] = "0123456789abcdef";
    size_t i;
    char two[2];
    for (i = 0u; i < n; ++i) {
        two[0] = d[p[i] >> 4];
        two[1] = d[p[i] & 15u];
        buf_add(b, two, 2u);
    }
}

static void sha_hex(const unsigned char *p, size_t n, char out[65])
{
    static const char hx[] = "0123456789abcdef";
    unsigned char dg[SHA256_DIGEST_LENGTH];
    unsigned i;
    SHA256(p, n, dg);
    for (i = 0u; i < SHA256_DIGEST_LENGTH; ++i) {
        out[2u * i] = hx[dg[i] >> 4];
        out[2u * i + 1u] = hx[dg[i] & 15u];
    }
    out[64] = '\0';
}

static const char *rname(tape_result r)
{
    switch (r) {
    case TAPE_OK: return "TAPE_OK";
    case TAPE_ERR_IO: return "TAPE_ERR_IO";
    case TAPE_ERR_BAD_MAGIC: return "TAPE_ERR_BAD_MAGIC";
    case TAPE_ERR_CRC: return "TAPE_ERR_CRC";
    case TAPE_ERR_VERSION: return "TAPE_ERR_VERSION";
    case TAPE_ERR_UNSUPPORTED_STATE: return "TAPE_ERR_UNSUPPORTED_STATE";
    case TAPE_ERR_GEOMETRY: return "TAPE_ERR_GEOMETRY";
    case TAPE_ERR_INCOMPLETE: return "TAPE_ERR_INCOMPLETE";
    case TAPE_ERR_INCONSISTENT: return "TAPE_ERR_INCONSISTENT";
    case TAPE_ERR_NO_VALID_INDEX: return "TAPE_ERR_NO_VALID_INDEX";
    case TAPE_ERR_READ_ONLY: return "TAPE_ERR_READ_ONLY";
    case TAPE_ERR_CARTRIDGE_FULL: return "TAPE_ERR_CARTRIDGE_FULL";
    case TAPE_ERR_INDEX_FULL: return "TAPE_ERR_INDEX_FULL";
    case TAPE_ERR_DEST_TOO_SMALL: return "TAPE_ERR_DEST_TOO_SMALL";
    case TAPE_ERR_SEQUENCE_EXHAUSTED: return "TAPE_ERR_SEQUENCE_EXHAUSTED";
    case TAPE_ERR_FAULTED: return "TAPE_ERR_FAULTED";
    case TAPE_ERR_NOT_MOUNTED: return "TAPE_ERR_NOT_MOUNTED";
    case TAPE_ERR_BUSY: return "TAPE_ERR_BUSY";
    case TAPE_ERR_UNDERRUN: return "TAPE_ERR_UNDERRUN";
    case TAPE_ERR_INVALID_ARG: return "TAPE_ERR_INVALID_ARG";
    default: return "TAPE_ERR_UNKNOWN";
    }
}

/* ------------------------------------------------------------------------ */
/* caller-owned simulator with one planned failure                           */
/* ------------------------------------------------------------------------ */

enum rule { RULE_NONE, RULE_FIRST_OF_CALL, RULE_FIRST_AFTER_WRITE };

struct sim {
    unsigned char *media;          /* NULL: a blank destination that stores nothing */
    uint32_t block_count;
    struct buf *events;            /* where callbacks are listed; NULL = not listed */
    /* planned failure */
    enum rule rule;
    const char *inject_op;
    int call_index;                /* current long-op call, -1 outside it */
    int inject_call;
    uint32_t after_lba, after_count;
    bool seen_trigger, fired;
};

static struct sim g_src, g_dst;

static bool should_fail(struct sim *s, const char *op, uint32_t lba, uint32_t count)
{
    bool fail = false;
    if (s->fired || s->rule == RULE_NONE || s->call_index < 0) return false;
    if (s->rule == RULE_FIRST_OF_CALL) {
        fail = s->call_index == s->inject_call && strcmp(op, s->inject_op) == 0;
    } else {
        if (!s->seen_trigger) {
            if (strcmp(op, "write") == 0 && lba == s->after_lba && count == s->after_count) s->seen_trigger = true;
        } else if (strcmp(op, s->inject_op) == 0) {
            fail = true;
        }
    }
    if (fail) s->fired = true;
    return fail;
}

static void log_ev(struct sim *s, const char *op, bool has_lba, uint32_t lba, uint32_t count, int rc)
{
    if (s->events == NULL) return;
    if (s->events->len && s->events->p[s->events->len - 1u] != '[') buf_str(s->events, ",");
    if (has_lba) buf_fmt(s->events, "{\"count\":%" PRIu32 ",\"lba\":%" PRIu32 ",\"op\":\"%s\",\"rc\":%d}", count, lba, op, rc);
    else buf_fmt(s->events, "{\"op\":\"%s\",\"rc\":%d}", op, rc);
}

static int cb_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    struct sim *s = (struct sim *)v;
    if (dst == NULL || count == 0u || (uint64_t)lba + count > s->block_count || should_fail(s, "read", lba, count)) {
        log_ev(s, "read", true, lba, count, SIM_FAIL_RC);
        return SIM_FAIL_RC;
    }
    if (s->media) memcpy(dst, s->media + (size_t)lba * BLOCK, (size_t)count * BLOCK);
    else memset(dst, 0, (size_t)count * BLOCK);
    log_ev(s, "read", true, lba, count, 0);
    return 0;
}

static int cb_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    struct sim *s = (struct sim *)v;
    if (src == NULL || count == 0u || (uint64_t)lba + count > s->block_count || should_fail(s, "write", lba, count)) {
        log_ev(s, "write", true, lba, count, SIM_FAIL_RC);
        return SIM_FAIL_RC;
    }
    if (s->media) memcpy(s->media + (size_t)lba * BLOCK, src, (size_t)count * BLOCK);
    log_ev(s, "write", true, lba, count, 0);
    return 0;
}

static int cb_flush(void *v)
{
    struct sim *s = (struct sim *)v;
    if (should_fail(s, "flush", 0u, 0u)) {
        log_ev(s, "flush", false, 0u, 0u, SIM_FAIL_RC);
        return SIM_FAIL_RC;
    }
    log_ev(s, "flush", false, 0u, 0u, 0);
    return 0;
}

static tape_dev dev_of(struct sim *s)
{
    tape_dev x;
    x.read = cb_read;
    x.write = cb_write;
    x.flush = cb_flush;
    x.ctx = s;
    x.block_count = s->block_count;
    return x;
}

static void load_image(const char *path)
{
    FILE *f = fopen(path, "rb");
    long n;
    if (f == NULL) { fprintf(stderr, "cannot open %s\n", path); exit(2); }
    if (fseek(f, 0, SEEK_END) != 0 || (n = ftell(f)) <= 0 || n % (long)BLOCK != 0) { fprintf(stderr, "bad image\n"); exit(2); }
    rewind(f);
    g_src.block_count = (uint32_t)((unsigned long)n / BLOCK);
    g_src.media = malloc((size_t)n);
    if (g_src.media == NULL || fread(g_src.media, 1u, (size_t)n, f) != (size_t)n) { fprintf(stderr, "read image\n"); exit(2); }
    fclose(f);
    g_src.call_index = -1;
}

/* Primary SB, mirror SB (block_count - 1 as the device reports it) and the
   four whole slots, read back from the device before mount. */
static void fixture_metadata(struct buf *out)
{
    static const uint32_t slots[4] = {LBA_A0, LBA_A1, LBA_B0, LBA_B1};
    unsigned i;
    buf_str(out, "\"fixture_metadata_hex\":\"");
    buf_hex(out, g_src.media, BLOCK);
    buf_hex(out, g_src.media + (size_t)(g_src.block_count - 1u) * BLOCK, BLOCK);
    for (i = 0u; i < 4u; ++i) buf_hex(out, g_src.media + (size_t)slots[i] * BLOCK, SLOT_BYTES);
    buf_str(out, "\"");
}

static void device_sha(char out[65])
{
    sha_hex(g_src.media, (size_t)g_src.block_count * BLOCK, out);
}

/* ------------------------------------------------------------------------ */
/* instance                                                                  */
/* ------------------------------------------------------------------------ */

static unsigned char *g_mem, *g_play, *g_rec;
static size_t g_mem_len;
static tape_dev g_x;
static tape *g_t;

static void inst_new(void)
{
    tape_result r;
    memset(g_mem, 0, g_mem_len);
    memset(g_play, 0, TAPE_PLAY_RING_MIN);
    memset(g_rec, 0, TAPE_REC_RING_MIN);
    g_x = dev_of(&g_src);
    g_t = NULL;
    r = tape_init(g_mem, g_mem_len, &g_x, g_play, TAPE_PLAY_RING_MIN, g_rec, TAPE_REC_RING_MIN, &g_t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init %s\n", rname(r)); exit(3); }
}

static void mount_rec(struct buf *out, const char *key, tape_side side)
{
    tape_result r = tape_mount(g_t, side, 0u, NULL);
    buf_fmt(out, ",\"%s\":{\"fn\":\"tape_mount\",\"result\":\"%s\",\"side\":\"%s\"}",
            key, rname(r), side == TAPE_SIDE_A ? "A" : "B");
}

/* ------------------------------------------------------------------------ */
/* render cases                                                              */
/* ------------------------------------------------------------------------ */

static int16_t *g_pcm;
static size_t g_pcm_cap;   /* frames */

static void render_phase(struct buf *out, const char *name)
{
    struct buf ev = {NULL, 0u, 0u};
    tape_result r;
    uint64_t total = 0u, tell = 0u;
    unsigned guard = 0u;
    tape_status_t st;
    char digest[65];
    unsigned char *le;
    size_t i;
    bool first = true;

    g_src.events = NULL;
    r = tape_seek(g_t, 0u);
    buf_fmt(out, ",\"%s\":{\"seek\":{\"fn\":\"tape_seek\",\"frame\":0,\"result\":\"%s\"}", name, rname(r));
    r = tape_set_rate(g_t, RATE_ONE);
    buf_fmt(out, ",\"set_rate\":{\"fn\":\"tape_set_rate\",\"rate_q16_16\":%d,\"result\":\"%s\"},\"renders\":[", RATE_ONE, rname(r));
    for (;;) {
        bool more = true;
        unsigned sg = 0u;
        uint32_t got = 0u;
        while (more && sg++ < 1000000u) {
            more = false;
            if (tape_service(g_t, RENDER_SERVICE_BUDGET, &more) != TAPE_OK) break;
        }
        if (total + RENDER_FRAMES > g_pcm_cap) {
            g_pcm_cap = (size_t)(total + RENDER_FRAMES) * 2u;
            g_pcm = realloc(g_pcm, g_pcm_cap * 4u);
            if (g_pcm == NULL) { fprintf(stderr, "oom\n"); exit(3); }
        }
        ev.len = 0u;
        buf_str(&ev, "[");
        g_src.events = &ev;
        r = tape_render(g_t, g_pcm + 2u * total, RENDER_FRAMES, &got);
        g_src.events = NULL;
        buf_str(&ev, "]");
        buf_fmt(out, "%s{\"block_events\":", first ? "" : ",");
        buf_str(out, ev.p);
        buf_fmt(out, ",\"rendered\":%" PRIu32 ",\"requested\":%u,\"result\":\"%s\"}", got, RENDER_FRAMES, rname(r));
        first = false;
        total += got;
        if (got < RENDER_FRAMES || ++guard > 100000u) break;
    }
    le = malloc((size_t)total * 4u + 1u);
    if (le == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    for (i = 0u; i < (size_t)total * 2u; ++i) {
        uint16_t u = (uint16_t)g_pcm[i];
        le[2u * i] = (unsigned char)u;
        le[2u * i + 1u] = (unsigned char)(u >> 8);
    }
    sha_hex(le, (size_t)total * 4u, digest);
    free(le);
    (void)tape_tell(g_t, &tell);
    memset(&st, 0, sizeof st);
    (void)tape_status(g_t, &st);
    buf_fmt(out, "],\"pcm_bytes\":%" PRIu64 ",\"pcm_sha256\":\"%s\",\"tell\":%" PRIu64 ",\"at_end\":%s",
            total * 4u, digest, tell, st.at_end ? "true" : "false");
    r = tape_set_rate(g_t, 0);
    buf_fmt(out, ",\"stop\":{\"fn\":\"tape_set_rate\",\"rate_q16_16\":0,\"result\":\"%s\"}}", rname(r));
    free(ev.p);
}

static void run_render(struct buf *out)
{
    unsigned guard = 0u;
    bool first = true;
    uint64_t pos = 0u;
    tape_result r;

    inst_new();
    mount_rec(out, "mount", TAPE_SIDE_B);
    render_phase(out, "pre");

    buf_str(out, ",\"respool\":[");
    for (;;) {
        bool more = false;
        r = tape_respool(g_t, RESPOOL_BUDGET, &more);
        buf_fmt(out, "%s{\"block_budget\":%u,\"fn\":\"tape_respool\",\"more_work\":%s,\"result\":\"%s\"}",
                first ? "" : ",", RESPOOL_BUDGET, more ? "true" : "false", rname(r));
        first = false;
        if (r != TAPE_OK || !more || ++guard > 1000000u) break;
    }
    buf_str(out, "],\"post_b_slots\":{\"B0\":\"");
    buf_hex(out, g_src.media + (size_t)LBA_B0 * BLOCK, SLOT_BYTES);
    buf_str(out, "\",\"B1\":\"");
    buf_hex(out, g_src.media + (size_t)LBA_B1 * BLOCK, SLOT_BYTES);
    buf_str(out, "\"}");

    render_phase(out, "post_same_session");

    r = tape_unmount(g_t, &pos);
    buf_fmt(out, ",\"unmount\":{\"fn\":\"tape_unmount\",\"result\":\"%s\"}", rname(r));
    inst_new();
    mount_rec(out, "remount", TAPE_SIDE_B);
    render_phase(out, "post_remount");
}

/* ------------------------------------------------------------------------ */
/* fault cases                                                               */
/* ------------------------------------------------------------------------ */

static void cell_begin(struct buf *out, struct buf *ev, const char *column, bool first)
{
    buf_fmt(out, "%s{\"column\":\"%s\",\"calls\":[", first ? "" : ",", column);
    ev->len = 0u;
    buf_str(ev, "[");
    g_src.events = ev;
}

static void cell_call(struct buf *out, const char *fn, tape_result r, bool first)
{
    buf_fmt(out, "%s{\"fn\":\"%s\",\"result\":\"%s\"}", first ? "" : ",", fn, rname(r));
}

static void cell_end(struct buf *out, struct buf *ev)
{
    g_src.events = NULL;
    buf_str(ev, "]");
    buf_str(out, "],\"block_events\":");
    buf_str(out, ev->p);
}

static void probe(struct buf *out, const char *column, bool first, char before_unmount[65])
{
    static int16_t in[2u * PROBE_FRAMES];
    static int16_t outbuf[2u * PROBE_FRAMES];
    struct buf ev = {NULL, 0u, 0u};
    uint32_t n = 0u;
    uint64_t v64 = 0u;
    bool more = false;
    unsigned i;

    for (i = 0u; i < PROBE_FRAMES; ++i) { in[2u * i] = (int16_t)(1000 + (int)i); in[2u * i + 1u] = (int16_t)(-1000 - (int)i); }
    if (strcmp(column, "unmount") == 0) device_sha(before_unmount);
    cell_begin(out, &ev, column, first);
    if (strcmp(column, "arm") == 0) cell_call(out, "tape_arm", tape_arm(g_t, TAPE_REC_OVERWRITE), true);
    else if (strcmp(column, "feed") == 0) cell_call(out, "tape_feed", tape_feed(g_t, in, PROBE_FRAMES, &n), true);
    else if (strcmp(column, "seek") == 0) cell_call(out, "tape_seek", tape_seek(g_t, 0u), true);
    else if (strcmp(column, "set_rate") == 0) cell_call(out, "tape_set_rate", tape_set_rate(g_t, RATE_ONE), true);
    else if (strcmp(column, "service") == 0) cell_call(out, "tape_service", tape_service(g_t, 64u, &more), true);
    else if (strcmp(column, "commit") == 0) cell_call(out, "tape_commit", tape_commit(g_t), true);
    else if (strcmp(column, "set_side") == 0) cell_call(out, "tape_set_side", tape_set_side(g_t, TAPE_SIDE_A), true);
    else if (strcmp(column, "reset_b") == 0) cell_call(out, "tape_reset_side_b", tape_reset_side_b(g_t), true);
    else if (strcmp(column, "promote") == 0) cell_call(out, "tape_promote", tape_promote(g_t, 64u, &more, NULL, NULL), true);
    else if (strcmp(column, "respool") == 0) cell_call(out, "tape_respool", tape_respool(g_t, 64u, &more), true);
    else if (strcmp(column, "render") == 0) cell_call(out, "tape_render", tape_render(g_t, outbuf, PROBE_FRAMES, &n), true);
    else if (strcmp(column, "abort") == 0) cell_call(out, "tape_abort", tape_abort(g_t), true);
    else if (strcmp(column, "unmount") == 0) cell_call(out, "tape_unmount", tape_unmount(g_t, &v64), true);
    else if (strcmp(column, "status_info_tell") == 0) {
        tape_status_t st;
        tape_info info;
        cell_call(out, "tape_status", tape_status(g_t, &st), true);
        cell_call(out, "tape_get_info", tape_get_info(g_t, &info), false);
        cell_call(out, "tape_tell", tape_tell(g_t, &v64), false);
    } else if (strcmp(column, "dup") == 0) {
        static const uint8_t uuid[16] = {0x57,0x50,0x31,0x32,0x2d,0x52,0x35,0x33,0x2d,0x64,0x75,0x70,0x64,0x73,0x74,0x21};
        struct buf dev_ev = {NULL, 0u, 0u};
        tape_dev dx;
        tape_result r;
        g_dst.media = NULL;
        g_dst.block_count = g_src.block_count;
        g_dst.rule = RULE_NONE;
        g_dst.call_index = -1;
        buf_str(&dev_ev, "[");
        g_dst.events = &dev_ev;
        dx = dev_of(&g_dst);
        r = tape_dup(g_t, &dx, uuid, 1u, 9u, 64u, &more, NULL, NULL);
        g_dst.events = NULL;
        buf_str(&dev_ev, "]");
        cell_call(out, "tape_dup", r, true);
        cell_end(out, &ev);
        buf_str(out, ",\"dst_block_events\":");
        buf_str(out, dev_ev.p);
        buf_str(out, "}");
        free(dev_ev.p);
        free(ev.p);
        return;
    } else {
        fprintf(stderr, "unknown column %s\n", column);
        exit(2);
    }
    cell_end(out, &ev);
    buf_str(out, "}");
    free(ev.p);
}

static const char *const PROBE_ORDER[15] = {
    "arm", "feed", "seek", "set_rate", "service", "commit", "set_side", "reset_b",
    "promote", "respool", "dup", "render", "status_info_tell", "abort", "unmount"};

static void run_fault(struct buf *out, char **a)
{
    bool promote = strcmp(a[0], "promote") == 0;
    tape_side side = strcmp(a[1], "A") == 0 ? TAPE_SIDE_A : TAPE_SIDE_B;
    uint32_t budget = (uint32_t)strtoul(a[2], NULL, 10);
    struct buf ev = {NULL, 0u, 0u};
    char at_fault[65], before_unmount[65] = {0};
    unsigned i;
    int call;

    g_src.rule = strcmp(a[3], "first_of_call") == 0 ? RULE_FIRST_OF_CALL : RULE_FIRST_AFTER_WRITE;
    g_src.inject_op = a[4];
    g_src.inject_call = atoi(a[5]);
    g_src.after_lba = (uint32_t)strtoul(a[6], NULL, 10);
    g_src.after_count = (uint32_t)strtoul(a[7], NULL, 10);

    inst_new();
    mount_rec(out, "mount", side);
    buf_str(out, ",\"calls\":[");
    for (call = 0; call < 100000; ++call) {
        bool more = false;
        tape_result r;
        ev.len = 0u;
        buf_str(&ev, "[");
        g_src.events = &ev;
        g_src.call_index = call;
        r = promote ? tape_promote(g_t, budget, &more, NULL, NULL) : tape_respool(g_t, budget, &more);
        g_src.call_index = -1;
        g_src.events = NULL;
        buf_str(&ev, "]");
        buf_fmt(out, "%s{\"block_budget\":%" PRIu32 ",\"events\":", call ? "," : "", budget);
        buf_str(out, ev.p);
        buf_fmt(out, ",\"fn\":\"%s\",\"more_work\":%s,\"result\":\"%s\"}",
                promote ? "tape_promote" : "tape_respool", more ? "true" : "false", rname(r));
        /* Stop after the failing call; otherwise run the operation to its end. */
        if (g_src.fired || r != TAPE_OK || !more) break;
    }
    buf_str(out, "]");
    device_sha(at_fault);
    buf_fmt(out, ",\"device_sha256_at_fault\":\"%s\",\"probe\":[", at_fault);
    for (i = 0u; i < 15u; ++i) probe(out, PROBE_ORDER[i], i == 0u, before_unmount);
    buf_fmt(out, "],\"device_sha256_before_unmount\":\"%s\"", before_unmount);
    free(ev.p);
}

int main(int argc, char **argv)
{
    struct buf out = {NULL, 0u, 0u};

    if (argc < 3 || (strcmp(argv[1], "render") != 0 && strcmp(argv[1], "fault") != 0)
        || (strcmp(argv[1], "fault") == 0 && argc != 11)) {
        fprintf(stderr, "usage: see header\n");
        return 2;
    }
    load_image(argv[2]);
    g_mem_len = tape_instance_size();
    g_mem = calloc(1u, g_mem_len);
    g_play = calloc(1u, TAPE_PLAY_RING_MIN);
    g_rec = calloc(1u, TAPE_REC_RING_MIN);
    if (g_mem == NULL || g_play == NULL || g_rec == NULL) { fprintf(stderr, "oom\n"); return 3; }

    buf_str(&out, "{");
    fixture_metadata(&out);
    if (strcmp(argv[1], "render") == 0) run_render(&out);
    else run_fault(&out, argv + 3);
    buf_str(&out, "}\n");
    fwrite(out.p, 1u, out.len, stdout);
    return 0;
}
