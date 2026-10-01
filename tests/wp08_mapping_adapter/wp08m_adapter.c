/*
 * WP-08 mapped-run rows (Verification #129) product adapter.
 *
 * Software-owned binding for the imported verifier package
 * tests/wp08_mapping_r56. Public header only; it does not import the oracle
 * and decides nothing. run_product.py builds the fixture image byte for byte
 * from the package's rows.py and writes it to a file; this program loads it
 * onto a fresh caller-owned flat device, makes the calls ADAPTER.md names,
 * and writes one JSON object of raw observations to OUTPUT ("wb"). Every
 * block-device callback made during each call is listed with that call.
 *
 * Usage: wp08m_adapter IMAGE.img ROW SIDE SEEK RATE REQUESTED OUTPUT
 *   ROW 1: seek, set_rate, service to completion, one render/tell/status.
 *   ROW 2: the same, with service/render/tell/status repeated until a render
 *          returns fewer than REQUESTED frames.
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
#define SERVICE_BUDGET 64u
#define MAX_REQUESTED 4096u

/* ------------------------------------------------------------------------ */
/* text buffer                                                               */
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

static void hex_of(const unsigned char *p, size_t n, char *out)
{
    static const char d[] = "0123456789abcdef";
    size_t i;
    for (i = 0u; i < n; ++i) { out[2u * i] = d[p[i] >> 4]; out[2u * i + 1u] = d[p[i] & 15u]; }
    out[2u * n] = '\0';
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
/* flat device: every callback appended to the current call's event list     */
/* ------------------------------------------------------------------------ */

struct dev {
    unsigned char *m;
    uint32_t n;
    struct buf ev;     /* events of the call in progress, without brackets */
};

static void ev_sep(struct dev *d) { if (d->ev.len) buf_str(&d->ev, ","); }

static int d_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    struct dev *d = (struct dev *)v;
    int rc = (dst == NULL || count == 0u || (uint64_t)lba + count > d->n) ? 1 : 0;
    if (rc == 0) memcpy(dst, d->m + (size_t)lba * BLOCK, (size_t)count * BLOCK);
    ev_sep(d);
    buf_fmt(&d->ev, "{\"op\":\"read\",\"lba\":%" PRIu32 ",\"count\":%" PRIu32 ",\"rc\":%d}", lba, count, rc);
    return rc;
}

static int d_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    struct dev *d = (struct dev *)v;
    int rc = (src == NULL || count == 0u || (uint64_t)lba + count > d->n) ? 1 : 0;
    if (rc == 0) memcpy(d->m + (size_t)lba * BLOCK, src, (size_t)count * BLOCK);
    ev_sep(d);
    buf_fmt(&d->ev, "{\"op\":\"write\",\"lba\":%" PRIu32 ",\"count\":%" PRIu32 ",\"rc\":%d}", lba, count, rc);
    return rc;
}

static int d_flush(void *v)
{
    struct dev *d = (struct dev *)v;
    ev_sep(d);
    buf_str(&d->ev, "{\"op\":\"flush\",\"rc\":0}");
    return 0;
}

static struct dev g_dev;
static struct buf g_out;
static bool g_first_call = true;

/* Open a call record: {"fn":FN<fields so far>. */
static void call_begin(const char *fn)
{
    buf_fmt(&g_out, "%s{\"fn\":\"%s\"", g_first_call ? "" : ",", fn);
    g_first_call = false;
    g_dev.ev.len = 0u;
    if (g_dev.ev.p) g_dev.ev.p[0] = '\0';
}

/* Close it with the callbacks made since call_begin. */
static void call_end(void)
{
    buf_str(&g_out, ",\"events\":[");
    if (g_dev.ev.len) buf_str(&g_out, g_dev.ev.p);
    buf_str(&g_out, "]}");
}

static uint64_t arg_u64(const char *s)
{
    char *end;
    unsigned long long v = strtoull(s, &end, 10);
    if (*s == '\0' || *end != '\0') { fprintf(stderr, "bad number %s\n", s); exit(2); }
    return (uint64_t)v;
}

static void service_to_completion(tape *t)
{
    unsigned guard = 0u;
    for (;;) {
        bool more = false;
        tape_result r;
        call_begin("tape_service");
        r = tape_service(t, SERVICE_BUDGET, &more);
        buf_fmt(&g_out, ",\"block_budget\":%u,\"result\":\"%s\",\"more_work\":%s",
                SERVICE_BUDGET, rname(r), more ? "true" : "false");
        call_end();
        if (r != TAPE_OK || !more || ++guard > 100000u) return;
    }
}

/* render, tell, status; returns the frames rendered. */
static uint32_t render_tell_status(tape *t, uint32_t requested)
{
    static int16_t pcm[2u * MAX_REQUESTED];
    static char hex[2u * 4u * MAX_REQUESTED + 1u];
    unsigned char le[4u * MAX_REQUESTED];
    uint32_t got = 0u, k;
    uint64_t pos = 0u;
    tape_status_t st;
    tape_result r;

    call_begin("tape_render");
    r = tape_render(t, pcm, requested, &got);
    if (got > requested) got = requested;
    for (k = 0u; k < 2u * got; ++k) {
        uint16_t w = (uint16_t)pcm[k];
        le[2u * k] = (unsigned char)w;
        le[2u * k + 1u] = (unsigned char)(w >> 8);
    }
    hex_of(le, (size_t)got * 4u, hex);
    buf_fmt(&g_out, ",\"requested\":%" PRIu32 ",\"result\":\"%s\",\"rendered\":%" PRIu32 ",\"pcm_hex\":\"",
            requested, rname(r), got);
    buf_str(&g_out, hex);
    buf_str(&g_out, "\"");
    call_end();

    call_begin("tape_tell");
    r = tape_tell(t, &pos);
    buf_fmt(&g_out, ",\"result\":\"%s\",\"frame\":%" PRIu64, rname(r), pos);
    call_end();

    memset(&st, 0, sizeof st);
    call_begin("tape_status");
    r = tape_status(t, &st);
    buf_fmt(&g_out, ",\"result\":\"%s\",\"at_start\":%s,\"at_end\":%s", rname(r),
            st.at_start ? "true" : "false", st.at_end ? "true" : "false");
    call_end();
    return got;
}

int main(int argc, char **argv)
{
    FILE *f;
    long len;
    unsigned row;
    tape_side side;
    uint64_t seek;
    int32_t rate;
    uint32_t requested;
    tape_dev x;
    tape *t = NULL;
    size_t mem_len;
    unsigned char *mem, *play, *rec, dg[SHA256_DIGEST_LENGTH];
    char h[65];
    tape_result r;

    if (argc != 8) {
        fprintf(stderr, "usage: %s IMAGE.img ROW SIDE SEEK RATE REQUESTED OUTPUT\n", argv[0]);
        return 2;
    }
    row = (unsigned)arg_u64(argv[2]);
    if (strcmp(argv[3], "A") == 0) side = TAPE_SIDE_A;
    else if (strcmp(argv[3], "B") == 0) side = TAPE_SIDE_B;
    else { fprintf(stderr, "bad side\n"); return 2; }
    seek = arg_u64(argv[4]);
    rate = (int32_t)strtol(argv[5], NULL, 10);
    requested = (uint32_t)arg_u64(argv[6]);
    if ((row != 1u && row != 2u) || requested == 0u || requested > MAX_REQUESTED) { fprintf(stderr, "bad args\n"); return 2; }

    f = fopen(argv[1], "rb");
    if (f == NULL || fseek(f, 0, SEEK_END) != 0 || (len = ftell(f)) <= 0 || len % (long)BLOCK != 0
        || fseek(f, 0, SEEK_SET) != 0) { fprintf(stderr, "cannot load image\n"); return 2; }
    g_dev.n = (uint32_t)((unsigned long)len / BLOCK);
    g_dev.m = malloc((size_t)len);
    if (g_dev.m == NULL || fread(g_dev.m, 1u, (size_t)len, f) != (size_t)len) { fprintf(stderr, "read\n"); return 2; }
    fclose(f);
    SHA256(g_dev.m, (size_t)len, dg);
    hex_of(dg, sizeof dg, h);

    mem_len = tape_instance_size();
    mem = calloc(1u, mem_len);
    play = calloc(1u, TAPE_PLAY_RING_MIN);
    rec = calloc(1u, TAPE_REC_RING_MIN);
    if (!mem || !play || !rec) { fprintf(stderr, "oom\n"); return 3; }
    x.read = d_read;
    x.write = d_write;
    x.flush = d_flush;
    x.ctx = &g_dev;
    x.block_count = g_dev.n;
    r = tape_init(mem, mem_len, &x, play, TAPE_PLAY_RING_MIN, rec, TAPE_REC_RING_MIN, &t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init %s\n", rname(r)); return 3; }

    buf_fmt(&g_out, "{\"image_sha256\":\"%s\",\"block_count\":%" PRIu32 ",\"calls\":[", h, g_dev.n);

    call_begin("tape_mount");
    r = tape_mount(t, side, 0u, NULL);
    buf_fmt(&g_out, ",\"side\":\"%s\",\"resume_frame\":0,\"warm\":null,\"result\":\"%s\"", argv[3], rname(r));
    call_end();

    call_begin("tape_seek");
    r = tape_seek(t, seek);
    buf_fmt(&g_out, ",\"frame\":%" PRIu64 ",\"result\":\"%s\"", seek, rname(r));
    call_end();

    call_begin("tape_set_rate");
    r = tape_set_rate(t, rate);
    buf_fmt(&g_out, ",\"rate\":%" PRId32 ",\"result\":\"%s\"", rate, rname(r));
    call_end();

    if (row == 1u) {
        service_to_completion(t);
        (void)render_tell_status(t, requested);
    } else {
        unsigned guard = 0u;
        for (;;) {
            service_to_completion(t);
            if (render_tell_status(t, requested) < requested || ++guard > 100000u) break;
        }
    }
    buf_str(&g_out, "]}\n");

    f = fopen(argv[7], "wb");
    if (f == NULL || fwrite(g_out.p, 1u, g_out.len, f) != g_out.len || fclose(f) != 0) {
        fprintf(stderr, "cannot write output\n");
        return 3;
    }
    return 0;
}
