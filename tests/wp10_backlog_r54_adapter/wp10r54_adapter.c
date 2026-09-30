/*
 * WP-10 backlog r54 product adapter: mount repair crash, dup re-run, dup shape.
 *
 * Software-owned binding for the imported verifier package
 * tests/wp10_backlog_r54. Public header only; it does not import the oracle
 * and decides nothing. The fault-injecting sparse device, durability settling
 * and trace format are carried from the WP-10 backlog rows 1-3 adapter
 * (tests/wp10_backlog_adapter/wp10b_row1.c, itself from held #318's WP-10
 * closure adapter). run_product.py writes an input file with the fixtures (the
 * package's model.py and its pinned R29-B builders), the tracked LBAs and the
 * planned case list; this program runs every case and writes one
 * wp10-backlog-r54-observation-v1 object per case to OUTPUT (opened "wb").
 *
 * Usage: wp10r54_adapter INPUT OUTPUT
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
#define MAX_FIX_BLOCKS 64
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
    trace_add(d->trace, "write", lba, count, s);
    trace_add(d->all, "write", lba, count, s);
    if (d->inj_kind == 1 && d->nwrites == d->inj_k) {
        /* Power cut during this write: the first `landed` bytes of its first
           block become durable over the durable contents, nothing else. */
        d->fired = true;
        d->dead = true;
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
    trace_add(d->trace, "flush", 0u, 0u, NULL);
    trace_add(d->all, "flush", 0u, 0u, NULL);
    if (d->inj_kind == 2 && d->nflushes == d->inj_k) {
        d->fired = true;
        d->dead = true;
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
static struct fixture g_fix[24];
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
static uint32_t g_lbas[MAX_LBAS];

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

static int cmp_u32(const void *a, const void *b)
{
    uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;
    return (x > y) - (x < y);
}

static void arm(struct dev *d, const char *ikind, unsigned k, unsigned landed)
{
    d->inj_kind = strcmp(ikind, "write") == 0 ? 1 : 2;
    d->inj_k = k;
    d->inj_landed = landed;
}

static void inject_fields(struct buf *out, const char *shape, const char *mode, const char *ikind,
                          unsigned k, unsigned landed, bool fired)
{
    buf_fmt(out, ",\"shape\":\"%s\",\"mode\":\"%s\"", shape, mode);
    if (strcmp(ikind, "write") == 0) buf_fmt(out, ",\"inject\":[\"write\",%u,%u]", k, landed);
    else buf_fmt(out, ",\"inject\":[\"flush\",%u]", k);
    buf_fmt(out, ",\"fired\":%s", fired ? "true" : "false");
}

/* Row 1: power cut inside a writable Side-A mount's phase-4 repair. */
static void run_row1(struct buf *out, unsigned long index, const char *shape, const char *mode,
                     const char *ikind, unsigned k, unsigned landed)
{
    char name[96], tr_sha[65], dur[65], after[65];
    struct buf tr = {NULL, 0u, 0u};
    tape_dev x;
    tape *t;
    snprintf(name, sizeof name, "rep_%s", shape);
    dev_reset(&g_dst, fixture(name), strcmp(mode, "write_through") == 0 ? MODE_WRITE_THROUGH : MODE_FLUSH_REQUIRED);
    arm(&g_dst, ikind, k, landed);
    buf_str(&tr, "[");
    g_dst.trace = &tr;
    x = dev_of(&g_dst, true);
    t = inst(&x, false);
    (void)tape_mount(t, TAPE_SIDE_A, 0u, NULL);
    g_dst.trace = NULL;
    buf_str(&tr, "]");
    sha_hex(tr.p, tr.len, tr_sha);
    free(tr.p);
    dev_settle(&g_dst, index);
    img_copy(&g_final, &g_dst.dur);
    tracked_sha(&g_final, dur);
    buf_fmt(out, "{\"schema\":\"wp10-backlog-r54-observation-v1\",\"index\":%lu,\"row\":1", index);
    inject_fields(out, shape, mode, ikind, k, landed, g_dst.fired);
    buf_fmt(out, ",\"repair_trace_sha256\":\"%s\",\"durable_sha256\":\"%s\",", tr_sha, dur);
    remount(out, "ro_A", &g_final, false, TAPE_SIDE_A, true, false);
    remount(out, "rw_A", &g_final, true, TAPE_SIDE_A, false, false);
    tracked_sha(&g_mnt.dur, after);
    buf_fmt(out, ",\"durable_after_rw_sha256\":\"%s\"}\n", after);
}

/* Row 2: interrupted dup, then a re-run on the same destination device. */
static void run_row2(struct buf *out, unsigned long index, const char *shape, const char *mode,
                     const char *ikind, unsigned k, unsigned landed)
{
    char name[96], tr_sha[65], dur[65], rr_sha[65], rr_dur[65];
    struct buf tr = {NULL, 0u, 0u};
    enum mode m = strcmp(mode, "write_through") == 0 ? MODE_WRITE_THROUGH : MODE_FLUSH_REQUIRED;
    tape_result r;
    bool more = false;
    unsigned i;

    snprintf(name, sizeof name, "dst_%s", shape);
    dev_reset(&g_dst, fixture(name), m);
    arm(&g_dst, ikind, k, landed);
    buf_str(&tr, "[");
    g_dst.trace = &tr;
    (void)run_dup("src128", &more);
    g_dst.trace = NULL;
    buf_str(&tr, "]");
    sha_hex(tr.p, tr.len, tr_sha);
    dev_settle(&g_dst, index);
    tracked_sha(&g_dst.dur, dur);
    buf_fmt(out, "{\"schema\":\"wp10-backlog-r54-observation-v1\",\"index\":%lu,\"row\":2", index);
    inject_fields(out, shape, mode, ikind, k, landed, g_dst.fired);
    buf_fmt(out, ",\"trace_sha256\":\"%s\",\"durable_sha256\":\"%s\"", tr_sha, dur);

    /* Power returns: the same device now holds only its durable bytes. No format in between. */
    img_copy(&g_hold, &g_dst.dur);
    dev_reset(&g_dst, &g_hold, m);
    tr.len = 0u;
    buf_str(&tr, "[");
    g_dst.trace = &tr;
    g_dst.lbas = g_lbas;
    r = run_dup("src128", &more);
    g_dst.trace = NULL;
    g_dst.lbas = NULL;
    buf_str(&tr, "]");
    sha_hex(tr.p, tr.len, rr_sha);
    free(tr.p);
    img_copy(&g_final, &g_dst.dur);
    tracked_sha(&g_final, rr_dur);
    buf_fmt(out, ",\"rerun\":{\"call\":{\"fn\":\"tape_dup\",\"result\":\"%s\",\"more_work\":%s},"
            "\"trace_sha256\":\"%s\",\"dst_chunk_lbas\":[", rname(r), more ? "true" : "false", rr_sha);
    qsort(g_lbas, g_dst.nlbas, sizeof g_lbas[0], cmp_u32);
    for (i = 0u; i < g_dst.nlbas; ++i) buf_fmt(out, "%s%" PRIu32, i ? "," : "", g_lbas[i]);
    buf_fmt(out, "],\"durable_sha256\":\"%s\"},", rr_dur);
    remount(out, "rw_A", &g_final, true, TAPE_SIDE_A, true, false);
    remount(out, "rw_B", &g_final, true, TAPE_SIDE_B, false, false);
    buf_str(out, "}\n");
}

/* Row 3: a labelled source copied onto a destination shape. */
static void run_row3(struct buf *out, unsigned long index, const char *source, const char *dest)
{
    char name[96], dname[96], hex[2u * 32u + 1u], src_pcm[65];
    unsigned char sb[BLOCK];
    const struct image *src_img;
    tape_dev sx;
    tape *t;
    tape_result r;
    bool more = false;
    static const char *const raw_names[4] = {"P", "M", "A0h", "B0h"};
    uint32_t raw_lba[4];
    unsigned i;

    snprintf(name, sizeof name, "r3src_%s", source);
    snprintf(dname, sizeof dname, "dst_%s", dest);
    src_img = fixture(name);
    /* Raw source facts, read outside the engine: the label bytes, and the Side-A render. */
    img_get(src_img, 0u, sb);
    hex_of(sb + 88, 32u, hex);
    dev_reset(&g_src, src_img, MODE_WRITE_THROUGH);
    sx = dev_of(&g_src, false);
    t = inst(&sx, true);
    r = tape_mount(t, TAPE_SIDE_A, 0u, NULL);
    if (r != TAPE_OK) { fprintf(stderr, "row-3 source mount %s\n", rname(r)); exit(3); }
    {
        tape_info info;
        memset(&info, 0, sizeof info);
        (void)tape_get_info(t, &info);
        render_sha(t, info.total_frames, src_pcm);
    }
    dev_reset(&g_dst, fixture(dname), MODE_WRITE_THROUGH);
    r = run_dup(name, &more);
    img_copy(&g_final, &g_dst.dur);
    buf_fmt(out, "{\"schema\":\"wp10-backlog-r54-observation-v1\",\"index\":%lu,\"row\":3,\"source\":\"%s\","
            "\"destination\":\"%s\",\"source_label_hex\":\"%s\",\"source_pcm_sha256\":\"%s\","
            "\"call\":{\"fn\":\"tape_dup\",\"result\":\"%s\",\"more_work\":%s},\"raw_after\":{",
            index, source, dest, hex, src_pcm, rname(r), more ? "true" : "false");
    raw_lba[0] = 0u; raw_lba[1] = g_final.n - 1u; raw_lba[2] = 8u; raw_lba[3] = 264u;
    for (i = 0u; i < 4u; ++i) {
        char bh[2u * BLOCK + 1u];
        img_get(&g_final, raw_lba[i], sb);
        hex_of(sb, BLOCK, bh);
        buf_fmt(out, "%s\"%s\":\"", i ? "," : "", raw_names[i]);
        buf_str(out, bh);
        buf_str(out, "\"");
    }
    buf_str(out, "},");
    remount(out, "mount_A", &g_final, true, TAPE_SIDE_A, true, true);
    remount(out, "mount_B", &g_final, true, TAPE_SIDE_B, false, true);
    buf_str(out, "}\n");
}

/* ------------------------------------------------------------------------ */
/* main                                                                      */
/* ------------------------------------------------------------------------ */

int main(int argc, char **argv)
{
    FILE *in, *outf;
    char word[64], a[64], b[64], c[64], d[64];
    static char hexblock[2u * BLOCK + 8u];
    unsigned char blockbuf[BLOCK];
    struct buf out = {NULL, 0u, 0u};
    unsigned long ncases = 0u;

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
            if (fscanf(in, "%63s %" SCNu32, a, &g_dst_nominal) != 2) return 2;
            unhex(a, g_uuid_dup, 16u);
        } else if (strcmp(word, "FIXTURE") == 0) {
            unsigned n, i;
            uint32_t count;
            struct fixture *f;
            if (g_nfix >= sizeof g_fix / sizeof g_fix[0]) { fprintf(stderr, "too many fixtures\n"); return 2; }
            f = &g_fix[g_nfix++];
            if (fscanf(in, "%31s %" SCNu32 " %u", f->name, &count, &n) != 3 || n > MAX_FIX_BLOCKS) return 2;
            img_init(&f->img, count);
            for (i = 0u; i < n; ++i) {
                uint32_t lba;
                if (fscanf(in, "%" SCNu32 " %1030s", &lba, hexblock) != 2 || lba >= count) return 2;
                unhex(hexblock, blockbuf, BLOCK);
                img_put(&f->img, lba, blockbuf);
            }
        } else if (strcmp(word, "CASE") == 0) {
            unsigned long index;
            unsigned row, k = 0u, landed = 0u;
            if (fscanf(in, "%lu %u", &index, &row) != 2) return 2;
            out.len = 0u;
            if (row == 3) {
                if (fscanf(in, "%63s %63s", a, b) != 2) return 2;
                run_row3(&out, index, a, b);
            } else {
                if (fscanf(in, "%63s %63s %63s", a, b, c) != 3) return 2;
                if (strcmp(c, "write") == 0) { if (fscanf(in, "%u %u", &k, &landed) != 2) return 2; }
                else if (fscanf(in, "%u", &k) != 1) return 2;
                if (row == 1) run_row1(&out, index, a, b, c, k, landed);
                else run_row2(&out, index, a, b, c, k, landed);
            }
            (void)d;
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
