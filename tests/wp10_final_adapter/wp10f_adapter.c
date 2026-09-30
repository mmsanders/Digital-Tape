/*
 * WP-10 final backlog (Verification #118) product adapter.
 *
 * Software-owned binding for the imported verifier package tests/wp10_final_r54.
 * Public header only; it does not import the oracle and decides nothing.
 * The fault-injecting device, remounts and duplicate runner are the #330
 * binding's (tests/wp10_backlog_r54_adapter/wp10r54_adapter.c); the four row
 * runners are new. run_product.py writes the input (fixture images from the
 * package's model.py/dupmodel.py and the planned case list); this program
 * writes one wp10-final-r54-observation-v1 object per case to OUTPUT ("wb").
 *
 * Usage: wp10f_adapter INPUT OUTPUT
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
#define MAX_TRACKED 16
#define MAX_FIX_BLOCKS 8192
#define MAX_PENDING 64
#define DUP_BUDGET 65535u

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
/* sparse image: NULL block = zero                                           */
/* ------------------------------------------------------------------------ */

#define LBA_CHUNK_BASE 2048u
#define MAX_LBAS 4096

struct image { unsigned char **blk; uint32_t n; };

static void img_init(struct image *m, uint32_t n)
{
    m->n = n;
    m->blk = calloc(n, sizeof *m->blk);
    if (m->blk == NULL) { fprintf(stderr, "oom\n"); exit(3); }
}

static void img_clear(struct image *m)
{
    uint32_t i;
    for (i = 0u; i < m->n; ++i) { free(m->blk[i]); m->blk[i] = NULL; }
}

static void img_put(struct image *m, uint32_t lba, const unsigned char *data)
{
    if (m->blk[lba] == NULL) {
        m->blk[lba] = malloc(BLOCK);
        if (m->blk[lba] == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    }
    memcpy(m->blk[lba], data, BLOCK);
}

static void img_get(const struct image *m, uint32_t lba, unsigned char *out)
{
    if (m->blk[lba]) memcpy(out, m->blk[lba], BLOCK); else memset(out, 0, BLOCK);
}

/* dst takes src's geometry as well as its contents. */
static void img_copy(struct image *dst, const struct image *src)
{
    uint32_t i;
    if (dst->blk == NULL || dst->n != src->n) {
        if (dst->blk) { img_clear(dst); free(dst->blk); }
        img_init(dst, src->n);
    } else {
        img_clear(dst);
    }
    for (i = 0u; i < src->n; ++i) if (src->blk[i]) img_put(dst, i, src->blk[i]);
}

/* ------------------------------------------------------------------------ */
/* fault-injecting device                                                    */
/* ------------------------------------------------------------------------ */

enum mode { MODE_WRITE_THROUGH, MODE_FLUSH_REQUIRED };

struct pending { uint32_t lba; unsigned char data[BLOCK]; };

struct dev {
    struct image cur;      /* what reads see */
    struct image dur;      /* durable media */
    enum mode mode;
    struct pending pend[MAX_PENDING];
    unsigned npend;
    /* planned power cut: kind 0 none, 1 write k landed, 2 flush j */
    int inj_kind;
    unsigned inj_k, inj_landed;
    unsigned nwrites, nflushes;
    bool dead, fired;
    bool torn_set;
    uint32_t torn_lba;
    unsigned char torn[BLOCK];
    bool wrote;            /* any successful write since setup */
    struct buf *trace;     /* write/flush trace, trace format; NULL = none */
    uint32_t *lbas;        /* chunk-region LBAs addressed by read/write; NULL = none */
    unsigned nlbas;
    struct buf *all;       /* every callback incl. reads; NULL = none */
    unsigned long ncb;     /* callbacks since the last count reset */
    unsigned long inj_pos; /* 1-based callback position of the fired injection */
};

static void trace_add(struct buf *t, const char *op, uint32_t lba, uint32_t count, const unsigned char *data)
{
    char dg[65];
    if (t == NULL) return;
    if (t->len > 1u) buf_str(t, ",");
    if (strcmp(op, "flush") == 0) { buf_str(t, "{\"op\":\"flush\"}"); return; }
    if (data) {
        sha_hex(data, (size_t)count * BLOCK, dg);
        buf_fmt(t, "{\"count\":%" PRIu32 ",\"data_sha256\":\"%s\",\"lba\":%" PRIu32 ",\"op\":\"%s\"}", count, dg, lba, op);
    } else {
        buf_fmt(t, "{\"count\":%" PRIu32 ",\"lba\":%" PRIu32 ",\"op\":\"%s\"}", count, lba, op);
    }
}

/* ADAPTER.md row 1: every block a read/write callback addresses at or above
   LBA_CHUNK_BASE, except the mirror LBA, recorded before any range check so an
   out-of-range attempt is recorded (and then fails) rather than trapping. */
static void note_lbas(struct dev *d, uint32_t lba, uint32_t count)
{
    uint32_t mirror = d->cur.n - 1u;
    uint64_t i;
    if (d->lbas == NULL || d->dead) return;
    for (i = lba; i < (uint64_t)lba + count; ++i) {
        unsigned k;
        if (i < LBA_CHUNK_BASE || i == mirror) continue;
        for (k = 0u; k < d->nlbas && d->lbas[k] != (uint32_t)i; ++k) {}
        if (k < d->nlbas) continue;
        if (d->nlbas >= MAX_LBAS) { fprintf(stderr, "lba list overflow\n"); exit(3); }
        d->lbas[d->nlbas++] = (uint32_t)i;
    }
}

static int d_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    struct dev *d = (struct dev *)v;
    uint32_t i;
    note_lbas(d, lba, count);
    if (d->dead || dst == NULL || count == 0u || (uint64_t)lba + count > d->cur.n) return 1;
    d->ncb++;
    for (i = 0u; i < count; ++i) img_get(&d->cur, lba + i, (unsigned char *)dst + (size_t)i * BLOCK);
    trace_add(d->all, "read", lba, count, NULL);
    return 0;
}

static int d_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    struct dev *d = (struct dev *)v;
    const unsigned char *s = (const unsigned char *)src;
    uint32_t i;
    note_lbas(d, lba, count);
    if (d->dead || src == NULL || count == 0u || (uint64_t)lba + count > d->cur.n) return 1;
    d->ncb++;
    trace_add(d->trace, "write", lba, count, s);
    trace_add(d->all, "write", lba, count, s);
    if (d->inj_kind == 1 && d->nwrites == d->inj_k) {
        /* Power cut during this write: the first `landed` bytes of its first
           block become durable over the durable contents, nothing else. */
        d->fired = true;
        d->dead = true;
        d->inj_pos = d->ncb;
        if (d->inj_landed == BLOCK) {
            for (i = 0u; i < count; ++i) {
                if (d->mode == MODE_WRITE_THROUGH) img_put(&d->dur, lba + i, s + (size_t)i * BLOCK);
                else {
                    if (d->npend >= MAX_PENDING) { fprintf(stderr, "pending overflow\n"); exit(3); }
                    d->pend[d->npend].lba = lba + i;
                    memcpy(d->pend[d->npend].data, s + (size_t)i * BLOCK, BLOCK);
                    d->npend++;
                }
            }
        } else if (d->inj_landed > 0u) {
            img_get(&d->dur, lba, d->torn);
            memcpy(d->torn, s, d->inj_landed);
            d->torn_lba = lba;
            d->torn_set = true;
        }
        return 1;
    }
    d->nwrites++;
    for (i = 0u; i < count; ++i) {
        img_put(&d->cur, lba + i, s + (size_t)i * BLOCK);
        if (d->mode == MODE_WRITE_THROUGH) img_put(&d->dur, lba + i, s + (size_t)i * BLOCK);
        else {
            if (d->npend >= MAX_PENDING) { fprintf(stderr, "pending overflow\n"); exit(3); }
            d->pend[d->npend].lba = lba + i;
            memcpy(d->pend[d->npend].data, s + (size_t)i * BLOCK, BLOCK);
            d->npend++;
        }
    }
    d->wrote = true;
    return 0;
}

static int d_flush(void *v)
{
    struct dev *d = (struct dev *)v;
    unsigned i;
    if (d->dead) return 1;
    d->ncb++;
    trace_add(d->trace, "flush", 0u, 0u, NULL);
    trace_add(d->all, "flush", 0u, 0u, NULL);
    if (d->inj_kind == 2 && d->nflushes == d->inj_k) {
        d->fired = true;
        d->dead = true;
        d->inj_pos = d->ncb;
        return 1;
    }
    d->nflushes++;
    for (i = 0u; i < d->npend; ++i) img_put(&d->dur, d->pend[i].lba, d->pend[i].data);
    d->npend = 0u;
    return 0;
}

static tape_dev dev_of(struct dev *d, bool writable)
{
    tape_dev x;
    x.read = d_read;
    x.write = writable ? d_write : NULL;
    x.flush = d_flush;
    x.ctx = d;
    x.block_count = d->cur.n;
    return x;
}

static void dev_reset(struct dev *d, const struct image *from, enum mode mode)
{
    img_copy(&d->cur, from);
    img_copy(&d->dur, from);
    d->mode = mode;
    d->npend = 0u;
    d->inj_kind = 0;
    d->inj_k = d->inj_landed = 0u;
    d->nwrites = d->nflushes = 0u;
    d->dead = d->fired = d->torn_set = d->wrote = false;
    d->trace = d->all = NULL;
    d->lbas = NULL;
    d->nlbas = 0u;
    d->ncb = d->inj_pos = 0u;
}

/* The durable image after a power cut: flushed media, then the chosen subset
   of completed-but-unflushed writes (flush-required only), then any torn
   prefix. The subset is fixed by the case index, as the model enumerates it:
   pending write i is kept iff bit (n-1-i) of (index mod 2^n) is set. */
static void dev_settle(struct dev *d, unsigned long index)
{
    unsigned i, n = d->npend;
    unsigned long long pick = n >= 63u ? (unsigned long long)index : (unsigned long long)index % (1ull << n);
    for (i = 0u; i < n; ++i)
        if ((pick >> (n - 1u - i)) & 1ull) img_put(&d->dur, d->pend[i].lba, d->pend[i].data);
    d->npend = 0u;
    if (d->torn_set) img_put(&d->dur, d->torn_lba, d->torn);
}

/* ------------------------------------------------------------------------ */
/* inputs                                                                    */
/* ------------------------------------------------------------------------ */

static uint32_t g_tracked[MAX_TRACKED];
static unsigned g_ntracked;
static uint8_t g_uuid_dup[16];
static uint32_t g_dst_nominal;

struct fixture { char name[96]; struct image img; };
static struct fixture g_fix[64];
static unsigned g_nfix;

static const struct image *fixture(const char *name)
{
    unsigned i;
    for (i = 0u; i < g_nfix; ++i) if (strcmp(g_fix[i].name, name) == 0) return &g_fix[i].img;
    fprintf(stderr, "unknown fixture %s\n", name);
    exit(2);
}

static void unhex(const char *h, unsigned char *out, size_t n)
{
    size_t i;
    for (i = 0u; i < n; ++i) {
        unsigned v;
        if (sscanf(h + 2u * i, "%2x", &v) != 1) { fprintf(stderr, "bad hex\n"); exit(2); }
        out[i] = (unsigned char)v;
    }
}

/* ------------------------------------------------------------------------ */
/* engine helpers                                                            */
/* ------------------------------------------------------------------------ */

static unsigned char *g_mem, *g_play, *g_rec, *g_mem2, *g_play2, *g_rec2;
static size_t g_mem_len;

static tape *inst(tape_dev *x, bool second)
{
    tape *t = NULL;
    tape_result r;
    unsigned char *m = second ? g_mem2 : g_mem, *p = second ? g_play2 : g_play, *c = second ? g_rec2 : g_rec;
    memset(m, 0, g_mem_len);
    memset(p, 0, TAPE_PLAY_RING_MIN);
    memset(c, 0, TAPE_REC_RING_MIN);
    r = tape_init(m, g_mem_len, x, p, TAPE_PLAY_RING_MIN, c, TAPE_REC_RING_MIN, &t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init %s\n", rname(r)); exit(3); }
    return t;
}

static struct dev g_dst, g_src, g_mnt;
static struct image g_final, g_hold;

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

static void json_string(struct buf *out, const char *s)
{
    buf_str(out, "\"");
    for (; *s; ++s) {
        unsigned char ch = (unsigned char)*s;
        if (ch == '"' || ch == '\\') { char e[3] = {'\\', (char)ch, 0}; buf_str(out, e); }
        else if (ch < 0x20u) buf_fmt(out, "\\u%04x", ch);
        else { char e[2] = {(char)ch, 0}; buf_str(out, e); }
    }
    buf_str(out, "\"");
}

/* One mount of `img` on a fresh write-through device and instance.
   row3 = false: {result, repair_events, info{uuid,...}, pcm_sha256 on a writable Side A}.
   row3 = true:  {result, info{total_frames, side_b_valid, label}, pcm_sha256 on Side A}.
   Afterwards g_mnt.dur holds the durable bytes the mount left. */
static void remount(struct buf *out, const char *key, const struct image *img, bool writable, tape_side side,
                    bool first, bool row3)
{
    struct buf ev = {NULL, 0u, 0u};
    tape_dev x;
    tape *t;
    tape_result r;
    char u[33], h[65];

    dev_reset(&g_mnt, img, MODE_WRITE_THROUGH);
    buf_str(&ev, "[");
    g_mnt.trace = &ev;
    x = dev_of(&g_mnt, writable);
    t = inst(&x, false);
    r = tape_mount(t, side, 0u, NULL);
    g_mnt.trace = NULL;
    buf_str(&ev, "]");
    buf_fmt(out, "%s\"%s\":{\"result\":\"%s\"", first ? "" : ",", key, rname(r));
    if (!row3) { buf_str(out, ",\"repair_events\":"); buf_str(out, ev.p); }
    if (r == TAPE_OK) {
        tape_info info;
        memset(&info, 0, sizeof info);
        (void)tape_get_info(t, &info);
        if (row3) {
            info.label[32] = '\0';
            buf_fmt(out, ",\"info\":{\"total_frames\":%" PRIu64 ",\"side_b_valid\":%s,\"label\":",
                    info.total_frames, info.side_b_valid ? "true" : "false");
            json_string(out, info.label);
            buf_str(out, "}");
        } else {
            hex_of(info.uuid, 16u, u);
            buf_fmt(out, ",\"info\":{\"entry_count\":%" PRIu32 ",\"free_chunks\":%" PRIu32 ",\"needs_repair\":%s,"
                    "\"side_b_valid\":%s,\"total_frames\":%" PRIu64 ",\"uuid\":\"%s\"}",
                    info.entry_count, info.free_chunks, info.needs_repair ? "true" : "false",
                    info.side_b_valid ? "true" : "false", info.total_frames, u);
        }
        if (side == TAPE_SIDE_A && (writable || row3)) {
            render_sha(t, info.total_frames, h);
            buf_fmt(out, ",\"pcm_sha256\":\"%s\"", h);
        }
    }
    buf_str(out, "}");
    free(ev.p);
}

/* model.TRACKED blocks of `img`, concatenated in sorted name order. */
static void tracked_sha(const struct image *img, char out[65])
{
    unsigned char cat[MAX_TRACKED * BLOCK];
    unsigned i;
    for (i = 0u; i < g_ntracked; ++i) img_get(img, g_tracked[i], cat + (size_t)i * BLOCK);
    sha_hex(cat, (size_t)g_ntracked * BLOCK, out);
}

/* tape_dup from `src_fixture` (Side A) onto g_dst until more_work == false or
   the destination dies. A fresh source device and instance each time. */
static tape_result run_dup(const char *src_fixture, bool *more_out)
{
    tape_result r;
    bool more = false;
    tape_dev sx, dx;
    tape *src;
    unsigned guard = 0u;
    dev_reset(&g_src, fixture(src_fixture), MODE_WRITE_THROUGH);
    sx = dev_of(&g_src, true);
    src = inst(&sx, true);
    r = tape_mount(src, TAPE_SIDE_A, 0u, NULL);
    if (r != TAPE_OK) { fprintf(stderr, "source mount %s\n", rname(r)); exit(3); }
    dx = dev_of(&g_dst, true);
    for (;;) {
        more = false;
        r = tape_dup(src, &dx, g_uuid_dup, 0u, g_dst_nominal, DUP_BUDGET, &more, NULL, NULL);
        if (r != TAPE_OK || !more || g_dst.dead || ++guard > 100000u) break;
    }
    *more_out = more;
    return r;
}

static void arm(struct dev *d, const char *ikind, unsigned k, unsigned landed)
{
    d->inj_kind = strcmp(ikind, "write") == 0 ? 1 : 2;
    d->inj_k = k;
    d->inj_landed = landed;
}

/* SHA-256 of a whole device image, zero blocks included. */
static void img_sha(const struct image *m, char out[65])
{
    static const unsigned char zero[BLOCK];
    SHA256_CTX c;
    unsigned char dg[SHA256_DIGEST_LENGTH];
    uint32_t i;
    SHA256_Init(&c);
    for (i = 0u; i < m->n; ++i) SHA256_Update(&c, m->blk[i] ? m->blk[i] : zero, BLOCK);
    SHA256_Final(dg, &c);
    hex_of(dg, SHA256_DIGEST_LENGTH, out);
}

static void raw_blocks(struct buf *out, const char *key, const struct image *img, uint32_t lba, unsigned n, bool first)
{
    unsigned char b[BLOCK];
    char h[2u * BLOCK + 1u];
    unsigned i;
    buf_fmt(out, "%s\"%s\":\"", first ? "" : ",", key);
    for (i = 0u; i < n; ++i) {
        img_get(img, lba + i, b);
        hex_of(b, BLOCK, h);
        buf_str(out, h);
    }
    buf_str(out, "\"");
}

/* ------------------------------------------------------------------------ */
/* rows 1-2: contract cases                                                  */
/* ------------------------------------------------------------------------ */

static void run_contract(struct buf *out, unsigned long index, unsigned row, const char *cid,
                         const char *side_s, const char *fn)
{
    char name[128], before[65], after[65];
    struct buf ev = {NULL, 0u, 0u};
    tape_side side = strcmp(side_s, "A") == 0 ? TAPE_SIDE_A : TAPE_SIDE_B;
    tape_dev x;
    tape *t;
    tape_result r, rm;
    bool more = false, has_more = false;
    unsigned guard = 0u;

    snprintf(name, sizeof name, "c_%s", cid);
    dev_reset(&g_dst, fixture(name), MODE_WRITE_THROUGH);
    img_sha(&g_dst.dur, before);
    x = dev_of(&g_dst, true);
    t = inst(&x, false);
    rm = tape_mount(t, side, 0u, NULL);
    buf_str(&ev, "[");
    g_dst.trace = &ev;
    if (strcmp(fn, "tape_reset_side_b") == 0) r = tape_reset_side_b(t);
    else if (strcmp(fn, "tape_arm") == 0) r = tape_arm(t, TAPE_REC_OVERWRITE);
    else {
        has_more = true;
        for (;;) {
            more = false;
            r = tape_respool(t, 65535u, &more);
            if (r != TAPE_OK || !more || ++guard > 100000u) break;
        }
    }
    g_dst.trace = NULL;
    buf_str(&ev, "]");
    img_sha(&g_dst.dur, after);
    buf_fmt(out, "{\"schema\":\"wp10-final-r54-observation-v1\",\"index\":%lu,\"row\":%u,\"kind\":\"contract\","
            "\"case\":\"%s\",\"image_sha256_before\":\"%s\",\"mount\":{\"fn\":\"tape_mount\",\"side\":\"%s\","
            "\"result\":\"%s\"},\"call\":{\"fn\":\"%s\",\"result\":\"%s\"",
            index, row, cid, before, side_s, rname(rm), fn, rname(r));
    if (has_more) buf_fmt(out, ",\"more_work\":%s", more ? "true" : "false");
    buf_str(out, "},\"events\":");
    buf_str(out, ev.p);
    buf_fmt(out, ",\"image_sha256_after\":\"%s\",\"after_raw\":{", after);
    raw_blocks(out, "P", &g_dst.dur, 0u, 1u, true);
    raw_blocks(out, "M", &g_dst.dur, g_dst.dur.n - 1u, 1u, false);
    raw_blocks(out, "A0", &g_dst.dur, 8u, 2u, false);
    raw_blocks(out, "A1", &g_dst.dur, 136u, 2u, false);
    raw_blocks(out, "B0", &g_dst.dur, 264u, 2u, false);
    raw_blocks(out, "B1", &g_dst.dur, 392u, 2u, false);
    buf_str(out, "}}\n");
    free(ev.p);
}

/* ------------------------------------------------------------------------ */
/* row 3: post-crash re-spool render                                         */
/* ------------------------------------------------------------------------ */

/* Mount `side` of `img` on a fresh writable device and render the whole side.
   full: {result, info{total_frames, entry_count, side_b_valid}, pcm_sha256};
   otherwise {result, pcm_sha256}. */
static void mount_render(struct buf *out, const char *key, const struct image *img, tape_side side, bool full)
{
    tape_dev x;
    tape *t;
    tape_result r;
    char h[65];
    dev_reset(&g_mnt, img, MODE_WRITE_THROUGH);
    x = dev_of(&g_mnt, true);
    t = inst(&x, false);
    r = tape_mount(t, side, 0u, NULL);
    buf_fmt(out, "\"%s\":{\"result\":\"%s\"", key, rname(r));
    if (r == TAPE_OK) {
        tape_info info;
        memset(&info, 0, sizeof info);
        (void)tape_get_info(t, &info);
        if (full)
            buf_fmt(out, ",\"info\":{\"total_frames\":%" PRIu64 ",\"entry_count\":%" PRIu32 ",\"side_b_valid\":%s}",
                    info.total_frames, info.entry_count, info.side_b_valid ? "true" : "false");
        render_sha(t, info.total_frames, h);
        buf_fmt(out, ",\"pcm_sha256\":\"%s\"", h);
    }
    buf_str(out, "}");
}

/* Mount Side B of g_dst, then tape_respool(64) until done, refused, or the
   device dies. Callback counters restart after the mount, so positions count
   from the first re-spool callback, as the clean trace does. With `calls`,
   each call is recorded; with `all`, every callback is listed. */
static void respool_run(struct buf *calls, struct buf *all)
{
    tape_dev x = dev_of(&g_dst, true);
    tape *t = inst(&x, false);
    tape_result r;
    unsigned guard = 0u;
    bool first = true;
    r = tape_mount(t, TAPE_SIDE_B, 0u, NULL);
    if (r != TAPE_OK) { fprintf(stderr, "row-3 mount %s\n", rname(r)); exit(3); }
    g_dst.ncb = 0u;
    g_dst.nwrites = g_dst.nflushes = 0u;
    g_dst.all = all;
    for (;;) {
        bool more = false;
        r = tape_respool(t, 64u, &more);
        if (calls) {
            buf_fmt(calls, "%s{\"fn\":\"tape_respool\",\"block_budget\":64,\"result\":\"%s\",\"more_work\":%s}",
                    first ? "" : ",", rname(r), more ? "true" : "false");
            first = false;
        }
        if (r != TAPE_OK || !more || g_dst.dead || ++guard > 100000u) break;
    }
    g_dst.all = NULL;
}

static void run_row3(struct buf *out, unsigned long index, const char *fid)
{
    char name[128], h[65];
    struct buf calls = {NULL, 0u, 0u}, ev = {NULL, 0u, 0u};
    unsigned long w = 0u, f = 0u, ordinal = 0u;
    unsigned mi;
    const struct image *fx;
    const char *p;
    static const char *const modes[2] = {"flush_required", "write_through"};

    snprintf(name, sizeof name, "r3_%s", fid);
    fx = fixture(name);
    img_sha(fx, h);
    buf_fmt(out, "{\"schema\":\"wp10-final-r54-observation-v1\",\"index\":%lu,\"row\":3,\"kind\":\"respool_render\","
            "\"fixture\":\"%s\",\"image_sha256\":\"%s\",\"pre\":{", index, fid, h);
    mount_render(out, "mount_B", fx, TAPE_SIDE_B, true);
    buf_str(out, ",");
    {
        struct buf tmp = {NULL, 0u, 0u};
        mount_render(&tmp, "a", fx, TAPE_SIDE_A, false);
        p = strstr(tmp.p, "\"pcm_sha256\":\"");
        if (p == NULL) { fprintf(stderr, "row-3 Side A did not mount\n"); exit(3); }
        memcpy(h, p + 14, 64);
        h[64] = '\0';
        free(tmp.p);
    }
    buf_fmt(out, "\"a_pcm_sha256\":\"%s\"},\"clean\":{\"calls\":[", h);

    /* Clean run: every callback across the re-spool calls, reads included. */
    dev_reset(&g_dst, fx, MODE_WRITE_THROUGH);
    buf_str(&ev, "[");
    respool_run(&calls, &ev);
    buf_str(&ev, "]");
    buf_str(out, calls.p ? calls.p : "");
    buf_str(out, "],\"events\":");
    buf_str(out, ev.p);
    buf_str(out, ",");
    img_copy(&g_hold, &g_dst.dur);
    mount_render(out, "post_mount_B", &g_hold, TAPE_SIDE_B, true);
    buf_str(out, "},\"crashes\":[");
    for (p = ev.p; (p = strstr(p, "\"op\":\"")) != NULL; ) {
        p += 6;
        if (*p == 'w') ++w;
        else if (*p == 'f') ++f;
    }
    free(ev.p);
    free(calls.p);

    /* ADAPTER.md row 3: per mode, every clean write at landed 0..512, then every clean flush. */
    for (mi = 0u; mi < 2u; ++mi) {
        unsigned long k, landed;
        enum mode m = mi == 1u ? MODE_WRITE_THROUGH : MODE_FLUSH_REQUIRED;
        for (k = 0u; k < w + f; ++k) {
            bool is_write = k < w;
            unsigned long j = is_write ? k : k - w;
            unsigned long hi = is_write ? BLOCK : 0u;
            for (landed = 0u; landed <= hi; ++landed) {
                dev_reset(&g_dst, fx, m);
                arm(&g_dst, is_write ? "write" : "flush", (unsigned)j, (unsigned)landed);
                respool_run(NULL, NULL);
                dev_settle(&g_dst, ordinal);
                img_copy(&g_final, &g_dst.dur);
                buf_fmt(out, "%s{\"mode\":\"%s\",", ordinal ? "," : "", modes[mi]);
                if (is_write) buf_fmt(out, "\"inject\":[\"write\",%lu,%lu]", j, landed);
                else buf_fmt(out, "\"inject\":[\"flush\",%lu]", j);
                buf_fmt(out, ",\"fired\":%s,\"prefix_len\":%lu,", g_dst.fired ? "true" : "false", g_dst.inj_pos);
                mount_render(out, "remount_B", &g_final, TAPE_SIDE_B, true);
                buf_str(out, ",");
                mount_render(out, "remount_A", &g_final, TAPE_SIDE_A, false);
                buf_str(out, "}");
                ++ordinal;
            }
        }
    }
    buf_str(out, "]}\n");
}

/* ------------------------------------------------------------------------ */
/* row 4: crashes inside the duplicate re-run                                */
/* ------------------------------------------------------------------------ */

static char g_src_sha[65];

static void inject_json(struct buf *out, const char *key, const char *kind, unsigned k, unsigned landed)
{
    if (strcmp(kind, "write") == 0) buf_fmt(out, "\"%s\":[\"write\",%u,%u]", key, k, landed);
    else buf_fmt(out, "\"%s\":[\"flush\",%u]", key, k);
}

static void run_row4(struct buf *out, unsigned long index, const char *shape, const char *cls0, const char *cls1,
                     const char *fmode, const char *fkind, unsigned fk, unsigned fl,
                     const char *mode, const char *ikind, unsigned k, unsigned landed)
{
    char name[128], first_dur[65], tr_sha[65], dur[65], src_after[65];
    struct buf tr = {NULL, 0u, 0u};
    enum mode m1 = strcmp(fmode, "write_through") == 0 ? MODE_WRITE_THROUGH : MODE_FLUSH_REQUIRED;
    enum mode m2 = strcmp(mode, "write_through") == 0 ? MODE_WRITE_THROUGH : MODE_FLUSH_REQUIRED;
    bool more = false, fired;

    snprintf(name, sizeof name, "dst_%s", shape);
    dev_reset(&g_dst, fixture(name), m1);
    arm(&g_dst, fkind, fk, fl);
    (void)run_dup("src128", &more);
    dev_settle(&g_dst, index);
    tracked_sha(&g_dst.dur, first_dur);

    /* Power returns: the same device holds only its durable bytes; no format in between. */
    img_copy(&g_hold, &g_dst.dur);
    dev_reset(&g_dst, &g_hold, m2);
    arm(&g_dst, ikind, k, landed);
    buf_str(&tr, "[");
    g_dst.trace = &tr;
    (void)run_dup("src128", &more);
    g_dst.trace = NULL;
    buf_str(&tr, "]");
    sha_hex(tr.p, tr.len, tr_sha);
    free(tr.p);
    fired = g_dst.fired;
    dev_settle(&g_dst, index);
    img_copy(&g_final, &g_dst.dur);
    tracked_sha(&g_final, dur);
    if (g_src.wrote) img_sha(&g_src.dur, src_after);
    else memcpy(src_after, g_src_sha, 65);

    buf_fmt(out, "{\"schema\":\"wp10-final-r54-observation-v1\",\"index\":%lu,\"row\":4,\"kind\":\"rerun_crash\","
            "\"shape\":\"%s\",\"class\":[\"%s\",", index, shape, cls0);
    if (strcmp(cls1, "null") == 0) buf_str(out, "null],");
    else buf_fmt(out, "\"%s\"],", cls1);
    buf_fmt(out, "\"first_mode\":\"%s\",", fmode);
    inject_json(out, "first_inject", fkind, fk, fl);
    buf_fmt(out, ",\"mode\":\"%s\",", mode);
    inject_json(out, "inject", ikind, k, landed);
    buf_fmt(out, ",\"first_durable_sha256\":\"%s\",\"fired\":%s,\"trace_sha256\":\"%s\",\"durable_sha256\":\"%s\","
            "\"source_sha256_before\":\"%s\",\"source_sha256_after\":\"%s\",",
            first_dur, fired ? "true" : "false", tr_sha, dur, g_src_sha, src_after);
    remount(out, "ro_A", &g_final, false, TAPE_SIDE_A, true, false);
    remount(out, "rw_A", &g_final, true, TAPE_SIDE_A, false, false);
    remount(out, "rw_B", &g_final, true, TAPE_SIDE_B, false, false);
    buf_str(out, "}\n");
}

/* ------------------------------------------------------------------------ */
/* main                                                                      */
/* ------------------------------------------------------------------------ */

static int read_inject(FILE *in, char *kind, unsigned *k, unsigned *landed)
{
    *k = *landed = 0u;
    if (fscanf(in, "%63s", kind) != 1) return 0;
    if (strcmp(kind, "write") == 0) return fscanf(in, "%u %u", k, landed) == 2;
    return fscanf(in, "%u", k) == 1;
}

int main(int argc, char **argv)
{
    FILE *in, *outf;
    char word[64], a[96], b[64], c[64], d[64], e[64], f[64], g[64];
    static char hexblock[2u * BLOCK + 8u];
    unsigned char blockbuf[BLOCK];
    struct buf out = {NULL, 0u, 0u};
    unsigned long ncases = 0u;
    bool src_hashed = false;

    if (argc != 3) { fprintf(stderr, "usage: %s INPUT OUTPUT\n", argv[0]); return 2; }
    in = fopen(argv[1], "rb");
    outf = fopen(argv[2], "wb");
    if (in == NULL || outf == NULL) { fprintf(stderr, "cannot open input/output\n"); return 2; }

    g_mem_len = tape_instance_size();
    g_mem = calloc(1u, g_mem_len); g_mem2 = calloc(1u, g_mem_len);
    g_play = calloc(1u, TAPE_PLAY_RING_MIN); g_play2 = calloc(1u, TAPE_PLAY_RING_MIN);
    g_rec = calloc(1u, TAPE_REC_RING_MIN); g_rec2 = calloc(1u, TAPE_REC_RING_MIN);
    if (!g_mem || !g_mem2 || !g_play || !g_play2 || !g_rec || !g_rec2) { fprintf(stderr, "oom\n"); return 3; }

    while (fscanf(in, "%63s", word) == 1) {
        if (strcmp(word, "TRACKED") == 0) {
            unsigned i;
            if (fscanf(in, "%u", &g_ntracked) != 1 || g_ntracked > MAX_TRACKED) return 2;
            for (i = 0u; i < g_ntracked; ++i) if (fscanf(in, "%" SCNu32, &g_tracked[i]) != 1) return 2;
        } else if (strcmp(word, "DUP") == 0) {
            if (fscanf(in, "%63s %" SCNu32, b, &g_dst_nominal) != 2) return 2;
            unhex(b, g_uuid_dup, 16u);
        } else if (strcmp(word, "FIXTURE") == 0) {
            unsigned n, i;
            uint32_t count;
            struct fixture *fx;
            if (g_nfix >= sizeof g_fix / sizeof g_fix[0]) { fprintf(stderr, "too many fixtures\n"); return 2; }
            fx = &g_fix[g_nfix++];
            if (fscanf(in, "%95s %" SCNu32 " %u", fx->name, &count, &n) != 3 || n > MAX_FIX_BLOCKS) return 2;
            img_init(&fx->img, count);
            for (i = 0u; i < n; ++i) {
                uint32_t lba;
                if (fscanf(in, "%" SCNu32 " %1030s", &lba, hexblock) != 2 || lba >= count) return 2;
                unhex(hexblock, blockbuf, BLOCK);
                img_put(&fx->img, lba, blockbuf);
            }
        } else if (strcmp(word, "CASE") == 0) {
            unsigned long index;
            unsigned row;
            if (fscanf(in, "%lu %u", &index, &row) != 2) return 2;
            out.len = 0u;
            if (row == 1 || row == 2) {
                if (fscanf(in, "%95s %63s %63s", a, b, c) != 3) return 2;
                run_contract(&out, index, row, a, b, c);
            } else if (row == 3) {
                if (fscanf(in, "%95s", a) != 1) return 2;
                run_row3(&out, index, a);
            } else {
                unsigned fk, fl, k, landed;
                if (!src_hashed) { img_sha(fixture("src128"), g_src_sha); src_hashed = true; }
                if (fscanf(in, "%95s %63s %63s %63s", a, b, c, d) != 4) return 2;
                if (!read_inject(in, e, &fk, &fl)) return 2;
                if (fscanf(in, "%63s", f) != 1) return 2;
                if (!read_inject(in, g, &k, &landed)) return 2;
                run_row4(&out, index, a, b, c, d, e, fk, fl, f, g, k, landed);
            }
            if (fwrite(out.p, 1u, out.len, outf) != out.len) return 3;
            ++ncases;
        } else {
            fprintf(stderr, "unknown directive %s\n", word);
            return 2;
        }
    }
    fclose(in);
    if (fclose(outf) != 0) return 3;
    fprintf(stderr, "%lu cases\n", ncases);
    return 0;
}
