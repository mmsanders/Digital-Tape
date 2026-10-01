/*
 * #126 strengthening rows 1-2 product adapter (Verification #126, DRAFT-9).
 *
 * Software-owned binding for the imported verifier package tests/strengthen_r55.
 * Public header only; it does not import the oracle and decides nothing.
 * run_product.py builds each fixture image byte for byte from the package's
 * rows.py and writes it to a file; this program loads it onto a caller-owned
 * flat device, runs the public calls ADAPTER.md names, and writes one JSON
 * object of raw observations to OUTPUT ("wb"). The render and device shapes
 * follow the #334 binding (tests/wp10_final_adapter/wp10f_adapter.c).
 *
 * Usage: str55_adapter dup   SOURCE.img DEST.img FRAMES DUP_UUID_HEX NOMINAL_S OUTPUT
 *        str55_adapter pass2 IMAGE.img OUTPUT
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
#define LBA_CHUNK_BASE 2048u
#define DUP_BUDGET 65535u
#define RESPOOL_BUDGET 64u

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

static void sha_hex(const void *p, size_t n, char out[65])
{
    unsigned char dg[SHA256_DIGEST_LENGTH];
    SHA256((const unsigned char *)p, n, dg);
    hex_of(dg, SHA256_DIGEST_LENGTH, out);
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

struct dev {
    unsigned char *m;      /* the whole image */
    uint32_t n;            /* block_count */
    struct buf *events;    /* write/flush callbacks; NULL = not recording */
    bool events_first;
};

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
    if (d->events) {
        buf_fmt(d->events, "%s{\"op\":\"write\",\"lba\":%" PRIu32 ",\"count\":%" PRIu32,
                d->events_first ? "" : ",", lba, count);
        d->events_first = false;
        /* ADAPTER.md row 2: a write outside the chunk store carries its blocks. */
        if (lba < LBA_CHUNK_BASE || (uint64_t)lba + count > d->n - 1u) {
            size_t len = (size_t)count * BLOCK;
            char *h = malloc(2u * len + 1u);
            if (h == NULL) { fprintf(stderr, "oom\n"); exit(3); }
            hex_of((const unsigned char *)src, len, h);
            buf_str(d->events, ",\"data\":\"");
            buf_str(d->events, h);
            buf_str(d->events, "\"");
            free(h);
        }
        buf_str(d->events, "}");
    }
    memcpy(d->m + (size_t)lba * BLOCK, src, (size_t)count * BLOCK);
    return 0;
}

static int d_flush(void *v)
{
    struct dev *d = (struct dev *)v;
    if (d->events) {
        buf_str(d->events, d->events_first ? "{\"op\":\"flush\"}" : ",{\"op\":\"flush\"}");
        d->events_first = false;
    }
    return 0;
}

static tape_dev dev_of(struct dev *d, bool writable)
{
    tape_dev x;
    x.read = d_read;
    x.write = writable ? d_write : NULL;
    x.flush = d_flush;
    x.ctx = d;
    x.block_count = d->n;
    return x;
}

static void dev_load(struct dev *d, const char *path)
{
    FILE *f = fopen(path, "rb");
    long len;
    if (f == NULL || fseek(f, 0, SEEK_END) != 0 || (len = ftell(f)) <= 0 || len % (long)BLOCK != 0
        || fseek(f, 0, SEEK_SET) != 0) {
        fprintf(stderr, "cannot load image %s\n", path);
        exit(2);
    }
    d->n = (uint32_t)((unsigned long)len / BLOCK);
    d->m = malloc((size_t)len);
    if (d->m == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    if (fread(d->m, 1u, (size_t)len, f) != (size_t)len) { fprintf(stderr, "short read %s\n", path); exit(2); }
    fclose(f);
    d->events = NULL;
    d->events_first = true;
}

static void dev_clone(struct dev *dst, const struct dev *src)
{
    dst->n = src->n;
    dst->m = malloc((size_t)src->n * BLOCK);
    if (dst->m == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    memcpy(dst->m, src->m, (size_t)src->n * BLOCK);
    dst->events = NULL;
    dst->events_first = true;
}

static void dev_free(struct dev *d) { free(d->m); d->m = NULL; }

static void dev_sha(const struct dev *d, char out[65]) { sha_hex(d->m, (size_t)d->n * BLOCK, out); }

/* ------------------------------------------------------------------------ */
/* engine helpers                                                            */
/* ------------------------------------------------------------------------ */

struct inst { unsigned char *mem, *play, *rec; };
static size_t g_mem_len;

static tape *inst_new(struct inst *s, tape_dev *x)
{
    tape *t = NULL;
    tape_result r;
    s->mem = calloc(1u, g_mem_len);
    s->play = calloc(1u, TAPE_PLAY_RING_MIN);
    s->rec = calloc(1u, TAPE_REC_RING_MIN);
    if (!s->mem || !s->play || !s->rec) { fprintf(stderr, "oom\n"); exit(3); }
    r = tape_init(s->mem, g_mem_len, x, s->play, TAPE_PLAY_RING_MIN, s->rec, TAPE_REC_RING_MIN, &t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init %s\n", rname(r)); exit(3); }
    return t;
}

static void inst_free(struct inst *s) { free(s->mem); free(s->play); free(s->rec); }

/* SHA-256 of the whole side rendered at 1.0x from frame 0 (tape_render output, little-endian). */
static void render_sha(tape *t, uint64_t total, char out[65])
{
    static int16_t pcm[2u * 4096u];
    SHA256_CTX c;
    unsigned char dg[SHA256_DIGEST_LENGTH];
    uint64_t done = 0u;
    unsigned guard = 0u;
    (void)tape_seek(t, 0u);
    (void)tape_set_rate(t, 65536);
    SHA256_Init(&c);
    while (done < total && guard++ < 100000u) {
        bool more = true;
        unsigned sg = 0u;
        uint32_t got = 0u, k;
        uint32_t want = (uint32_t)((total - done) > 4096u ? 4096u : (total - done));
        while (more && sg++ < 100000u) { more = false; if (tape_service(t, 64u, &more) != TAPE_OK) break; }
        (void)tape_render(t, pcm, want, &got);
        for (k = 0u; k < 2u * got; ++k) {
            unsigned char le[2];
            uint16_t w = (uint16_t)pcm[k];
            le[0] = (unsigned char)w; le[1] = (unsigned char)(w >> 8);
            SHA256_Update(&c, le, 2u);
        }
        if (got == 0u) break;
        done += got;
    }
    SHA256_Final(dg, &c);
    hex_of(dg, SHA256_DIGEST_LENGTH, out);
}

/* A fresh mount of `side` of a copy of `img` on a writable device and a fresh
   instance: {result, info{total_frames, entry_count}, pcm_sha256}. `img` is
   left untouched. */
static void mount_render(struct buf *out, const char *key, const struct dev *img, tape_side side)
{
    struct dev d;
    struct inst s;
    tape_dev x;
    tape *t;
    tape_result r;
    char h[65];
    dev_clone(&d, img);
    x = dev_of(&d, true);
    t = inst_new(&s, &x);
    r = tape_mount(t, side, 0u, NULL);
    buf_fmt(out, ",\"%s\":{\"result\":\"%s\"", key, rname(r));
    if (r == TAPE_OK) {
        tape_info info;
        memset(&info, 0, sizeof info);
        (void)tape_get_info(t, &info);
        buf_fmt(out, ",\"info\":{\"total_frames\":%" PRIu64 ",\"entry_count\":%" PRIu32 "}",
                info.total_frames, info.entry_count);
        render_sha(t, info.total_frames, h);
        buf_fmt(out, ",\"pcm_sha256\":\"%s\"", h);
    }
    buf_str(out, "}");
    inst_free(&s);
    dev_free(&d);
}

static void unhex(const char *h, unsigned char *out, size_t n)
{
    size_t i;
    if (strlen(h) != 2u * n) { fprintf(stderr, "bad hex length\n"); exit(2); }
    for (i = 0u; i < n; ++i) {
        unsigned v;
        if (sscanf(h + 2u * i, "%2x", &v) != 1) { fprintf(stderr, "bad hex\n"); exit(2); }
        out[i] = (unsigned char)v;
    }
}

static uint32_t arg_u32(const char *s)
{
    char *end;
    unsigned long v = strtoul(s, &end, 10);
    if (*s == '\0' || *end != '\0' || v > 0xFFFFFFFFul) { fprintf(stderr, "bad number %s\n", s); exit(2); }
    return (uint32_t)v;
}

/* ------------------------------------------------------------------------ */
/* row 1: tape_dup copies every audio block                                  */
/* ------------------------------------------------------------------------ */

static void run_dup(struct buf *out, const char *src_path, const char *dst_path, uint32_t frames,
                    const uint8_t uuid[16], uint32_t nominal)
{
    struct dev src, dst;
    struct inst ss, ps;
    tape_dev sx, dx, px;
    tape *s, *p;
    tape_result r, rm;
    bool more = false;
    unsigned guard = 0u;
    char h[65];

    dev_load(&src, src_path);
    dev_load(&dst, dst_path);
    dev_sha(&src, h);
    buf_fmt(out, "{\"source_image_sha256\":\"%s\"", h);
    dev_sha(&dst, h);
    buf_fmt(out, ",\"destination_image_sha256_before\":\"%s\"", h);

    /* Source: a source-slot device, so a NULL write callback (guardrail 06). */
    sx = dev_of(&src, false);
    s = inst_new(&ss, &sx);
    rm = tape_mount(s, TAPE_SIDE_A, 0u, NULL);
    if (rm != TAPE_OK) { fprintf(stderr, "source mount %s\n", rname(rm)); exit(3); }
    dx = dev_of(&dst, true);
    for (;;) {
        more = false;
        r = tape_dup(s, &dx, uuid, 0u, nominal, DUP_BUDGET, &more, NULL, NULL);
        if (r != TAPE_OK || !more || ++guard > 100000u) break;
    }
    buf_fmt(out, ",\"call\":{\"fn\":\"tape_dup\",\"result\":\"%s\",\"more_work\":%s}", rname(r),
            more ? "true" : "false");
    inst_free(&ss);

    /* The source's Side A at 1.0x, on its own fresh read-only mount. */
    px = dev_of(&src, false);
    p = inst_new(&ps, &px);
    rm = tape_mount(p, TAPE_SIDE_A, 0u, NULL);
    if (rm != TAPE_OK) { fprintf(stderr, "source remount %s\n", rname(rm)); exit(3); }
    {
        tape_info info;
        memset(&info, 0, sizeof info);
        (void)tape_get_info(p, &info);
        render_sha(p, info.total_frames, h);
    }
    buf_fmt(out, ",\"source_pcm_sha256\":\"%s\"", h);
    inst_free(&ps);

    /* Destination raw bytes [chunk-store base, base + frames*4), straight from the device. */
    if ((uint64_t)LBA_CHUNK_BASE * BLOCK + (uint64_t)frames * 4u > (uint64_t)dst.n * BLOCK) {
        fprintf(stderr, "frames beyond the destination\n");
        exit(2);
    }
    sha_hex(dst.m + (size_t)LBA_CHUNK_BASE * BLOCK, (size_t)frames * 4u, h);
    buf_fmt(out, ",\"copy_raw_sha256\":\"%s\"", h);

    mount_render(out, "mount_A", &dst, TAPE_SIDE_A);
    mount_render(out, "mount_B", &dst, TAPE_SIDE_B);
    buf_str(out, "}\n");
    dev_free(&src);
    dev_free(&dst);
}

/* ------------------------------------------------------------------------ */
/* row 2: re-spool from a Side-A mount, pass 2 run branch                    */
/* ------------------------------------------------------------------------ */

static void run_pass2(struct buf *out, const char *img_path)
{
    struct dev d;
    struct inst s;
    struct buf ev = {NULL, 0u, 0u};
    tape_dev x;
    tape *t;
    tape_result r, rm;
    unsigned guard = 0u;
    bool first = true;
    char h[65];

    dev_load(&d, img_path);
    dev_sha(&d, h);
    buf_fmt(out, "{\"image_sha256_before\":\"%s\"", h);
    x = dev_of(&d, true);
    t = inst_new(&s, &x);
    rm = tape_mount(t, TAPE_SIDE_A, 0u, NULL);
    buf_fmt(out, ",\"mount\":{\"fn\":\"tape_mount\",\"side\":\"A\",\"result\":\"%s\"},\"calls\":[", rname(rm));
    buf_str(&ev, "");
    d.events = &ev;
    d.events_first = true;
    for (;;) {
        bool more = false;
        r = tape_respool(t, RESPOOL_BUDGET, &more);
        buf_fmt(out, "%s{\"fn\":\"tape_respool\",\"block_budget\":%u,\"result\":\"%s\",\"more_work\":%s}",
                first ? "" : ",", RESPOOL_BUDGET, rname(r), more ? "true" : "false");
        first = false;
        if (r != TAPE_OK || !more || ++guard > 100000u) break;
    }
    d.events = NULL;
    buf_str(out, "],\"events\":[");
    buf_str(out, ev.p);
    buf_str(out, "]");
    free(ev.p);
    inst_free(&s);
    mount_render(out, "mount_B_after", &d, TAPE_SIDE_B);
    buf_str(out, "}\n");
    dev_free(&d);
}

/* ------------------------------------------------------------------------ */
/* main                                                                      */
/* ------------------------------------------------------------------------ */

int main(int argc, char **argv)
{
    struct buf out = {NULL, 0u, 0u};
    const char *outpath;
    FILE *f;

    g_mem_len = tape_instance_size();
    if (argc == 8 && strcmp(argv[1], "dup") == 0) {
        uint8_t uuid[16];
        unhex(argv[5], uuid, 16u);
        run_dup(&out, argv[2], argv[3], arg_u32(argv[4]), uuid, arg_u32(argv[6]));
        outpath = argv[7];
    } else if (argc == 4 && strcmp(argv[1], "pass2") == 0) {
        run_pass2(&out, argv[2]);
        outpath = argv[3];
    } else {
        fprintf(stderr, "usage: %s dup SOURCE.img DEST.img FRAMES DUP_UUID_HEX NOMINAL_S OUTPUT\n"
                        "       %s pass2 IMAGE.img OUTPUT\n", argv[0], argv[0]);
        return 2;
    }
    f = fopen(outpath, "wb");
    if (f == NULL || fwrite(out.p, 1u, out.len, f) != out.len || fclose(f) != 0) {
        fprintf(stderr, "cannot write %s\n", outpath);
        return 3;
    }
    free(out.p);
    return 0;
}
