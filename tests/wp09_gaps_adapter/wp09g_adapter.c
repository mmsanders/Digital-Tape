/*
 * #130 rows (Verification #130) product adapter, row 1: full-scale overdub.
 *
 * Software-owned binding for the imported verifier package
 * tests/wp09_gaps_r56. Public header only; it does not import the oracle and
 * decides nothing. run_product.py builds rows.overdub_image() byte for byte
 * and the row's input PCM from rows.input_frames(); this program makes the
 * ADAPTER.md calls on a caller-owned writable flat device and writes one JSON
 * object of raw observations to OUTPUT ("wb"). Row 2 (the V-R55-01 trace floor)
 * needs no engine run: run_product.py wraps the accepted #336 row-3 records.
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
#define RENDER 32u
#define MAX_INPUT 4096u

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
/* flat write-through device                                                 */
/* ------------------------------------------------------------------------ */

struct dev { unsigned char *m; uint32_t n; };

static int d_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    struct dev *d = (struct dev *)v;
    if (dst == NULL || count == 0u || (uint64_t)lba + count > d->n) return 1;
    memcpy(dst, d->m + (size_t)lba * BLOCK, (size_t)count * BLOCK);
    return 0;
}

static int d_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    struct dev *d = (struct dev *)v;
    if (src == NULL || count == 0u || (uint64_t)lba + count > d->n) return 1;
    memcpy(d->m + (size_t)lba * BLOCK, src, (size_t)count * BLOCK);
    return 0;
}

static int d_flush(void *v) { (void)v; return 0; }

static struct buf g_out;
static bool g_first = true;

static void call_open(const char *fn)
{
    buf_fmt(&g_out, "%s{\"fn\":\"%s\"", g_first ? "" : ",", fn);
    g_first = false;
}

static void call_close(tape_result r) { buf_fmt(&g_out, ",\"result\":\"%s\"}", rname(r)); }

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
        tape_result r = tape_service(t, SERVICE_BUDGET, &more);
        call_open("tape_service");
        buf_fmt(&g_out, ",\"block_budget\":%u,\"more_work\":%s", SERVICE_BUDGET, more ? "true" : "false");
        call_close(r);
        if (r != TAPE_OK || !more || ++guard > 100000u) return;
    }
}

static void mount_b(tape *t)
{
    tape_result r = tape_mount(t, TAPE_SIDE_B, 0u, NULL);
    call_open("tape_mount");
    buf_str(&g_out, ",\"side\":\"B\",\"resume_frame\":0,\"warm\":null");
    call_close(r);
}

static void seek(tape *t, uint64_t frame)
{
    tape_result r = tape_seek(t, frame);
    call_open("tape_seek");
    buf_fmt(&g_out, ",\"frame\":%" PRIu64, frame);
    call_close(r);
}

/* Usage: wp09g_adapter IMAGE.img AT INPUT_PCM_HEX OUTPUT
   Row 1 of tests/wp09_gaps_r56/ADAPTER.md: overdub INPUT at AT on Side B,
   commit, unmount, remount and render the whole side. */
int main(int argc, char **argv)
{
    static int16_t in[2u * MAX_INPUT], pcm[2u * RENDER];
    static unsigned char raw[4u * MAX_INPUT];
    static char hex[2u * 4u * MAX_INPUT + 1u];
    struct dev d;
    FILE *f;
    long len;
    uint64_t at, pos = 0u;
    size_t hl, i;
    uint32_t frames, accepted = 0u;
    tape_dev x;
    tape *t = NULL;
    size_t mem_len;
    unsigned char *mem, *play, *rec, dg[SHA256_DIGEST_LENGTH];
    char h[65];
    tape_result r;
    unsigned guard = 0u;

    if (argc != 5) { fprintf(stderr, "usage: %s IMAGE.img AT INPUT_PCM_HEX OUTPUT\n", argv[0]); return 2; }
    at = arg_u64(argv[2]);
    hl = strlen(argv[3]);
    if (hl == 0u || hl % 8u != 0u || hl / 8u > MAX_INPUT) { fprintf(stderr, "bad input pcm\n"); return 2; }
    frames = (uint32_t)(hl / 8u);
    for (i = 0u; i < hl / 2u; ++i) {
        unsigned v;
        if (sscanf(argv[3] + 2u * i, "%2x", &v) != 1) { fprintf(stderr, "bad hex\n"); return 2; }
        raw[i] = (unsigned char)v;
    }
    for (i = 0u; i < 2u * frames; ++i)
        in[i] = (int16_t)(uint16_t)((unsigned)raw[2u * i] | ((unsigned)raw[2u * i + 1u] << 8));

    f = fopen(argv[1], "rb");
    if (f == NULL || fseek(f, 0, SEEK_END) != 0 || (len = ftell(f)) <= 0 || len % (long)BLOCK != 0
        || fseek(f, 0, SEEK_SET) != 0) { fprintf(stderr, "cannot load image\n"); return 2; }
    d.n = (uint32_t)((unsigned long)len / BLOCK);
    d.m = malloc((size_t)len);
    if (d.m == NULL || fread(d.m, 1u, (size_t)len, f) != (size_t)len) { fprintf(stderr, "read\n"); return 2; }
    fclose(f);
    SHA256(d.m, (size_t)len, dg);
    hex_of(dg, sizeof dg, h);

    mem_len = tape_instance_size();
    mem = calloc(1u, mem_len);
    play = calloc(1u, TAPE_PLAY_RING_MIN);
    rec = calloc(1u, TAPE_REC_RING_MIN);
    if (!mem || !play || !rec) { fprintf(stderr, "oom\n"); return 3; }
    x.read = d_read;
    x.write = d_write;
    x.flush = d_flush;
    x.ctx = &d;
    x.block_count = d.n;
    r = tape_init(mem, mem_len, &x, play, TAPE_PLAY_RING_MIN, rec, TAPE_REC_RING_MIN, &t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init %s\n", rname(r)); return 3; }

    buf_fmt(&g_out, "{\"image_sha256\":\"%s\",\"calls\":[", h);
    mount_b(t);
    seek(t, at);
    r = tape_arm(t, TAPE_REC_OVERDUB);
    call_open("tape_arm");
    buf_str(&g_out, ",\"mode\":\"TAPE_REC_OVERDUB\"");
    call_close(r);
    r = tape_feed(t, in, frames, &accepted);
    hex_of(raw, (size_t)frames * 4u, hex);
    call_open("tape_feed");
    buf_fmt(&g_out, ",\"frames\":%" PRIu32 ",\"pcm_hex\":\"", frames);
    buf_str(&g_out, hex);
    buf_fmt(&g_out, "\",\"accepted\":%" PRIu32, accepted);
    call_close(r);
    service_to_completion(t);
    r = tape_commit(t);
    call_open("tape_commit");
    call_close(r);
    r = tape_unmount(t, &pos);
    call_open("tape_unmount");
    call_close(r);

    mount_b(t);
    seek(t, 0u);
    r = tape_set_rate(t, 65536);
    call_open("tape_set_rate");
    buf_str(&g_out, ",\"rate\":65536");
    call_close(r);
    for (;;) {
        uint32_t got = 0u, k;
        unsigned char le[4u * RENDER];
        char ph[2u * 4u * RENDER + 1u];
        service_to_completion(t);
        r = tape_render(t, pcm, RENDER, &got);
        if (got > RENDER) got = RENDER;
        for (k = 0u; k < 2u * got; ++k) {
            uint16_t w = (uint16_t)pcm[k];
            le[2u * k] = (unsigned char)w;
            le[2u * k + 1u] = (unsigned char)(w >> 8);
        }
        hex_of(le, (size_t)got * 4u, ph);
        call_open("tape_render");
        buf_fmt(&g_out, ",\"requested\":%u,\"rendered\":%" PRIu32 ",\"pcm_hex\":\"%s\"", RENDER, got, ph);
        call_close(r);
        if (r != TAPE_OK || got < RENDER || ++guard > 100000u) break;
    }
    buf_str(&g_out, "]}\n");

    f = fopen(argv[4], "wb");
    if (f == NULL || fwrite(g_out.p, 1u, g_out.len, f) != g_out.len || fclose(f) != 0) {
        fprintf(stderr, "cannot write output\n");
        return 3;
    }
    return 0;
}
