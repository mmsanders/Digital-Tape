/*
 * WP-10 backlog row 1 product adapter: fragmented dup onto a smaller destination.
 *
 * Software-owned binding for the imported verifier package
 * tests/wp10_backlog_r53, carried forward from the WP-10 R53 closure adapter
 * (held PR #318, tests/wp10_closure_adapter/wp10c_adapter.c). Public header
 * only; it does not import the oracle and decides nothing. run_product.py
 * writes an input file holding the destination fixtures (the package's
 * dupfrag.destination), the fragmented C-90 source, the tracked LBAs and the
 * planned row-1 case list; this program runs every case on caller-owned sparse
 * devices that inject exactly one power cut, and writes the row-1 part of each
 * wp10-backlog-r53-observation-v1 object to OUTPUT (opened "wb").
 *
 * Differences from the closure adapter: the source and destination have their
 * own geometries (8 chunks / 21 s and 4 chunks / 9 s), and every destination
 * read/write callback at or above LBA_CHUNK_BASE (except the mirror LBA) is
 * recorded, including attempts outside the device, as dst_chunk_lbas.
 *
 * Usage: wp10b_row1 INPUT OUTPUT
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

/* SHA-256 of the whole device image, zero blocks included. */
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

struct fixture { char name[32]; struct image img; };
static struct fixture g_fix[8];
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
static struct image g_final;
static char g_src_sha[65];
static uint32_t g_lbas[MAX_LBAS];

/* One remount of the durable image on a fresh device. */
static void remount(struct buf *out, const char *key, bool writable, tape_side side, bool first)
{
    struct buf ev = {NULL, 0u, 0u};
    tape_dev x;
    tape *t;
    tape_result r;
    char u[33];

    dev_reset(&g_mnt, &g_final, MODE_WRITE_THROUGH);
    buf_str(&ev, "[");
    g_mnt.trace = &ev;
    x = dev_of(&g_mnt, writable);
    t = inst(&x, false);
    r = tape_mount(t, side, 0u, NULL);
    g_mnt.trace = NULL;
    buf_str(&ev, "]");
    buf_fmt(out, "%s\"%s\":{\"result\":\"%s\",\"repair_events\":", first ? "" : ",", key, rname(r));
    buf_str(out, ev.p);
    if (r == TAPE_OK) {
        tape_info info;
        memset(&info, 0, sizeof info);
        (void)tape_get_info(t, &info);
        hex_of(info.uuid, 16u, u);
        buf_fmt(out, ",\"info\":{\"entry_count\":%" PRIu32 ",\"free_chunks\":%" PRIu32 ",\"needs_repair\":%s,"
                "\"side_b_valid\":%s,\"total_frames\":%" PRIu64 ",\"uuid\":\"%s\"}",
                info.entry_count, info.free_chunks, info.needs_repair ? "true" : "false",
                info.side_b_valid ? "true" : "false", info.total_frames, u);
        if (writable && side == TAPE_SIDE_A) {
            /* Render the whole side at 1.0x from frame 0. */
            static int16_t pcm[2u * 4096u];
            SHA256_CTX c;
            unsigned char dg[SHA256_DIGEST_LENGTH];
            char h[65];
            uint64_t done = 0u;
            unsigned guard = 0u;
            g_mnt.all = NULL;
            (void)tape_seek(t, 0u);
            (void)tape_set_rate(t, 65536);
            SHA256_Init(&c);
            while (done < info.total_frames && guard++ < 100000u) {
                bool more = true;
                unsigned sg = 0u;
                uint32_t got = 0u, k;
                uint32_t want = (uint32_t)((info.total_frames - done) > 4096u ? 4096u : (info.total_frames - done));
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
            hex_of(dg, SHA256_DIGEST_LENGTH, h);
            buf_fmt(out, ",\"pcm_sha256\":\"%s\"", h);
        }
    }
    buf_str(out, "}");
    free(ev.p);
}

static void durable_sha(char out[65])
{
    unsigned char cat[MAX_TRACKED * BLOCK];
    unsigned i;
    for (i = 0u; i < g_ntracked; ++i) img_get(&g_final, g_tracked[i], cat + (size_t)i * BLOCK);
    sha_hex(cat, (size_t)g_ntracked * BLOCK, out);
}

/* tape_dup from the fragmented source (Side A) until more_work == false. */
static tape_result run_dup(bool *more_out, char src_after[65])
{
    tape_result r;
    bool more = false;
    tape_dev sx, dx;
    tape *src;
    unsigned guard = 0u;
    dev_reset(&g_src, fixture("source"), MODE_WRITE_THROUGH);
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
    if (g_src.wrote) img_sha(&g_src.dur, src_after);
    else memcpy(src_after, g_src_sha, 65);
    *more_out = more;
    return r;
}

static int cmp_u32(const void *a, const void *b)
{
    uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;
    return (x > y) - (x < y);
}

static void run_case(struct buf *out, unsigned long index, const char *kind, const char *sid,
                     const char *shape, const char *mode, const char *ikind, unsigned k, unsigned landed)
{
    struct buf tr = {NULL, 0u, 0u};
    char trace_sha[65], dur_sha[65], src_after[65];
    tape_result r;
    bool more = false;
    bool crash = strcmp(kind, "crash") == 0;
    unsigned i;

    dev_reset(&g_dst, fixture(shape), crash && strcmp(mode, "write_through") == 0 ? MODE_WRITE_THROUGH : MODE_FLUSH_REQUIRED);
    if (crash) {
        g_dst.inj_kind = strcmp(ikind, "write") == 0 ? 1 : 2;
        g_dst.inj_k = k;
        g_dst.inj_landed = landed;
    }
    g_dst.lbas = g_lbas;
    buf_str(&tr, "[");
    g_dst.trace = &tr;
    r = run_dup(&more, src_after);
    g_dst.trace = NULL;
    g_dst.lbas = NULL;
    buf_str(&tr, "]");
    sha_hex(tr.p, tr.len, trace_sha);
    free(tr.p);
    if (crash) dev_settle(&g_dst, index);
    img_copy(&g_final, &g_dst.dur);
    durable_sha(dur_sha);

    buf_fmt(out, "{\"schema\":\"wp10-backlog-r53-observation-v1\",\"index\":%lu,\"row\":1,\"kind\":\"%s\",\"scenario\":\"%s\"",
            index, kind, sid);
    buf_fmt(out, ",\"source_sha256_before\":\"%s\",\"source_sha256_after\":\"%s\"", g_src_sha, src_after);
    if (crash) {
        if (g_dst.inj_kind == 1) buf_fmt(out, ",\"mode\":\"%s\",\"inject\":[\"write\",%u,%u]", mode, k, landed);
        else buf_fmt(out, ",\"mode\":\"%s\",\"inject\":[\"flush\",%u]", mode, k);
        buf_fmt(out, ",\"fired\":%s", g_dst.fired ? "true" : "false");
    } else {
        buf_fmt(out, ",\"call\":{\"fn\":\"tape_dup\",\"result\":\"%s\",\"more_work\":%s}", rname(r), more ? "true" : "false");
    }
    buf_fmt(out, ",\"trace_sha256\":\"%s\",\"durable_sha256\":\"%s\",\"dst_chunk_lbas\":[", trace_sha, dur_sha);
    qsort(g_lbas, g_dst.nlbas, sizeof g_lbas[0], cmp_u32);
    for (i = 0u; i < g_dst.nlbas; ++i) buf_fmt(out, "%s%" PRIu32, i ? "," : "", g_lbas[i]);
    buf_str(out, "],");
    remount(out, "ro_A", false, TAPE_SIDE_A, true);
    remount(out, "rw_A", true, TAPE_SIDE_A, false);
    remount(out, "rw_B", true, TAPE_SIDE_B, false);
    buf_str(out, "}\n");
}

/* ------------------------------------------------------------------------ */
/* main                                                                      */
/* ------------------------------------------------------------------------ */

int main(int argc, char **argv)
{
    FILE *in, *outf;
    char word[64], a[64], b[64], c[64], d[64], e[64];
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
            struct fixture *f = &g_fix[g_nfix++];
            if (fscanf(in, "%31s %" SCNu32 " %u", f->name, &count, &n) != 3 || n > MAX_FIX_BLOCKS) return 2;
            img_init(&f->img, count);
            for (i = 0u; i < n; ++i) {
                uint32_t lba;
                if (fscanf(in, "%" SCNu32 " %1030s", &lba, hexblock) != 2 || lba >= count) return 2;
                unhex(hexblock, blockbuf, BLOCK);
                img_put(&f->img, lba, blockbuf);
            }
            if (strcmp(f->name, "source") == 0) img_sha(&f->img, g_src_sha);
        } else if (strcmp(word, "CASE") == 0) {
            unsigned long index;
            unsigned k = 0u, landed = 0u;
            if (fscanf(in, "%lu %63s %63s %63s", &index, a, b, e) != 4) return 2;
            if (strcmp(a, "crash") == 0) {
                if (fscanf(in, "%63s %63s", c, d) != 2) return 2;
                if (strcmp(d, "write") == 0) { if (fscanf(in, "%u %u", &k, &landed) != 2) return 2; }
                else if (fscanf(in, "%u", &k) != 1) return 2;
            } else { c[0] = d[0] = '\0'; }
            out.len = 0u;
            run_case(&out, index, a, b, e, c, d, k, landed);
            if (fwrite(out.p, 1u, out.len, outf) != out.len) return 3;
            ++ncases;
        } else {
            fprintf(stderr, "unknown directive %s\n", word);
            return 2;
        }
    }
    fclose(in);
    if (fclose(outf) != 0) return 3;
    fprintf(stderr, "%lu row-1 cases\n", ncases);
    return 0;
}
