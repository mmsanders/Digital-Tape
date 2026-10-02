/*
 * WP-10 residue destinations (DRAFT-10 V10-001) product adapter.
 *
 * Software-owned binding for the imported verifier package
 * tests/wp10_residue_d10. Public header only; it does not import the oracle
 * or the planner's injection list and decides nothing. run_product.py writes an
 * input file with the tracked LBAs, the call arguments, the fixture images (the
 * package's plan.py bases) and the group list; this program runs every group
 * and writes one wp10-residue-d10-observation-v1 object per group, in order.
 *
 * Injection coordinates come from each group's own clean re-run trace
 * (ADAPTER.md R1 step 4), never from the model.
 *
 * The device model is the WP-10 adapters' (tests/wp10_backlog_r54_adapter):
 * a torn write lands its first `landed` bytes over the durable block; a
 * write-through write is durable at once; a flush-required write is durable at
 * the next flush, and on a power cut a subset of the unflushed writes survives,
 * chosen by the injection ordinal. The sparse image is a short (lba, block)
 * list, because every group touches a dozen blocks of a 6,145-block device.
 *
 * Usage: wp10res_adapter INPUT OUTPUT
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
#define MAX_BLOCKS 32
#define MAX_PENDING 32
#define MAX_OPS 64
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
/* sparse image: an absent block reads as zero                               */
/* ------------------------------------------------------------------------ */

struct image {
    uint32_t n;                         /* block_count */
    unsigned nb;
    uint32_t lba[MAX_BLOCKS];
    unsigned char data[MAX_BLOCKS][BLOCK];
};

static void img_init(struct image *m, uint32_t n) { m->n = n; m->nb = 0u; }

static void img_put(struct image *m, uint32_t lba, const unsigned char *data)
{
    unsigned i;
    for (i = 0u; i < m->nb && m->lba[i] != lba; ++i) {}
    if (i == m->nb) {
        if (m->nb >= MAX_BLOCKS) { fprintf(stderr, "image overflow\n"); exit(3); }
        m->lba[m->nb++] = lba;
    }
    memcpy(m->data[i], data, BLOCK);
}

static void img_get(const struct image *m, uint32_t lba, unsigned char *out)
{
    unsigned i;
    for (i = 0u; i < m->nb; ++i) if (m->lba[i] == lba) { memcpy(out, m->data[i], BLOCK); return; }
    memset(out, 0, BLOCK);
}

static void img_copy(struct image *dst, const struct image *src)
{
    dst->n = src->n;
    dst->nb = src->nb;
    memcpy(dst->lba, src->lba, sizeof src->lba[0] * src->nb);
    memcpy(dst->data, src->data, (size_t)BLOCK * src->nb);
}

/* ------------------------------------------------------------------------ */
/* fault-injecting device                                                    */
/* ------------------------------------------------------------------------ */

enum mode { MODE_WRITE_THROUGH, MODE_FLUSH_REQUIRED };

struct pending { uint32_t lba; unsigned char data[BLOCK]; };

/* One write or flush callback the engine made, in call order. */
struct op { bool write; uint32_t lba; };

struct dev {
    struct image cur;      /* what reads see */
    struct image dur;      /* durable media */
    enum mode mode;
    struct pending pend[MAX_PENDING];
    unsigned npend;
    int inj_kind;          /* 0 none, 1 write k with `landed` bytes, 2 flush k */
    unsigned inj_k, inj_landed;
    unsigned nwrites, nflushes;
    bool dead, fired;
    bool torn_set;
    uint32_t torn_lba;
    unsigned char torn[BLOCK];
    struct buf *trace;     /* plan.trace form; NULL = none */
    struct op ops[MAX_OPS];
    unsigned nops;
};

static void trace_add(struct buf *t, bool write, uint32_t lba, const unsigned char *data)
{
    char dg[65];
    if (t == NULL) return;
    if (t->len > 1u) buf_str(t, ",");
    if (!write) { buf_str(t, "{\"op\":\"flush\"}"); return; }
    sha_hex(data, BLOCK, dg);
    buf_fmt(t, "{\"count\":1,\"data_sha256\":\"%s\",\"lba\":%" PRIu32 ",\"op\":\"write\"}", dg, lba);
}

static void note_op(struct dev *d, bool write, uint32_t lba)
{
    if (d->nops >= MAX_OPS) { fprintf(stderr, "op list overflow\n"); exit(3); }
    d->ops[d->nops].write = write;
    d->ops[d->nops].lba = lba;
    d->nops++;
}

static void pend_add(struct dev *d, uint32_t lba, const unsigned char *data)
{
    if (d->npend >= MAX_PENDING) { fprintf(stderr, "pending overflow\n"); exit(3); }
    d->pend[d->npend].lba = lba;
    memcpy(d->pend[d->npend].data, data, BLOCK);
    d->npend++;
}

static int d_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    struct dev *d = (struct dev *)v;
    uint32_t i;
    if (d->dead || dst == NULL || count == 0u || (uint64_t)lba + count > d->cur.n) return 1;
    for (i = 0u; i < count; ++i) img_get(&d->cur, lba + i, (unsigned char *)dst + (size_t)i * BLOCK);
    return 0;
}

static int d_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    struct dev *d = (struct dev *)v;
    const unsigned char *s = (const unsigned char *)src;
    if (d->dead || src == NULL || count != 1u || (uint64_t)lba + count > d->cur.n) return 1;
    trace_add(d->trace, true, lba, s);
    note_op(d, true, lba);
    if (d->inj_kind == 1 && d->nwrites == d->inj_k) {
        /* Power cut during this write: its first `landed` bytes reach the medium. */
        d->fired = true;
        d->dead = true;
        if (d->inj_landed == BLOCK) {
            if (d->mode == MODE_WRITE_THROUGH) img_put(&d->dur, lba, s);
            else pend_add(d, lba, s);
        } else if (d->inj_landed > 0u) {
            img_get(&d->dur, lba, d->torn);
            memcpy(d->torn, s, d->inj_landed);
            d->torn_lba = lba;
            d->torn_set = true;
        }
        return 1;
    }
    d->nwrites++;
    img_put(&d->cur, lba, s);
    if (d->mode == MODE_WRITE_THROUGH) img_put(&d->dur, lba, s);
    else pend_add(d, lba, s);
    return 0;
}

static int d_flush(void *v)
{
    struct dev *d = (struct dev *)v;
    unsigned i;
    if (d->dead) return 1;
    trace_add(d->trace, false, 0u, NULL);
    note_op(d, false, 0u);
    if (d->inj_kind == 2 && d->nflushes == d->inj_k) {
        /* Power cut at this flush: it may or may not have taken effect, which
           settling covers by keeping a subset of the pending writes. */
        d->fired = true;
        d->dead = true;
        return 1;
    }
    d->nflushes++;
    for (i = 0u; i < d->npend; ++i) img_put(&d->dur, d->pend[i].lba, d->pend[i].data);
    d->npend = 0u;
    return 0;
}

static tape_dev dev_of(struct dev *d)
{
    tape_dev x;
    x.read = d_read;
    x.write = d_write;
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
    d->dead = d->fired = d->torn_set = false;
    d->trace = NULL;
    d->nops = 0u;
}

/* The durable image after a power cut: flushed media, then a subset of the
   completed-but-unflushed writes (flush-required only), then any torn prefix.
   Pending write i is kept iff bit (n-1-i) of (ordinal mod 2^n) is set. */
static void dev_settle(struct dev *d, unsigned long ordinal)
{
    unsigned i, n = d->npend;
    unsigned long long pick = n >= 63u ? (unsigned long long)ordinal : (unsigned long long)ordinal % (1ull << n);
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
static uint8_t g_uuid_dup[16], g_uuid_format[16];
static uint32_t g_nominal;

struct fixture { char name[64]; struct image img; };
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
static struct image g_pre, g_post, g_tmp;

/* model.TRACKED blocks of `img`, concatenated in sorted name order. */
static void tracked_sha(const struct image *img, char out[65])
{
    unsigned char cat[MAX_TRACKED * BLOCK];
    unsigned i;
    for (i = 0u; i < g_ntracked; ++i) img_get(img, g_tracked[i], cat + (size_t)i * BLOCK);
    sha_hex(cat, (size_t)g_ntracked * BLOCK, out);
}

/* ADAPTER.md mount code: a writable Side-A mount of `img` on a fresh device
   and instance; the error name, or "OK." and the first 8 hex of the UUID. */
static void mount_code(const struct image *img, char out[40])
{
    tape_dev x;
    tape *t;
    tape_result r;
    dev_reset(&g_mnt, img, MODE_WRITE_THROUGH);
    x = dev_of(&g_mnt);
    t = inst(&x, false);
    r = tape_mount(t, TAPE_SIDE_A, 0u, NULL);
    if (r == TAPE_OK) {
        tape_info info;
        char u[33];
        memset(&info, 0, sizeof info);
        (void)tape_get_info(t, &info);
        hex_of(info.uuid, 16u, u);
        u[8] = '\0';
        snprintf(out, 40u, "OK.%s", u);
    } else {
        snprintf(out, 40u, "%s", rname(r));
    }
}

struct call { tape_result result; bool more; };

/* Runs `op` on g_dst to completion or until the destination dies. dup: a fresh
   source device and instance each time, tape_dup repeated while more_work. */
static struct call run_op(bool dup)
{
    struct call c;
    tape_dev dx = dev_of(&g_dst);
    c.more = false;
    if (dup) {
        tape_dev sx;
        tape *src;
        unsigned guard = 0u;
        dev_reset(&g_src, fixture("src128"), MODE_WRITE_THROUGH);
        sx = dev_of(&g_src);
        src = inst(&sx, true);
        c.result = tape_mount(src, TAPE_SIDE_A, 0u, NULL);
        if (c.result != TAPE_OK) { fprintf(stderr, "source mount %s\n", rname(c.result)); exit(3); }
        for (;;) {
            c.more = false;
            c.result = tape_dup(src, &dx, g_uuid_dup, 0u, g_nominal, DUP_BUDGET, &c.more, NULL, NULL);
            if (c.result != TAPE_OK || !c.more || g_dst.dead || ++guard > 100000u) break;
        }
    } else {
        c.result = tape_format(&dx, g_uuid_format, 0u, "", g_nominal);
    }
    return c;
}

static void call_json(struct buf *out, bool dup, struct call c)
{
    buf_fmt(out, "{\"fn\":\"%s\",\"result\":\"%s\",\"more_work\":%s}", dup ? "tape_dup" : "tape_format",
            rname(c.result), c.more ? "true" : "false");
}

static bool is_sb(uint32_t lba) { return lba == 0u || lba == g_dst.cur.n - 1u; }

/* Runs `op` from `start` (durable bytes) in `mode`, cut at the coordinate, and
   leaves the settled durable bytes in g_post. */
static void injected_run(bool dup, const struct image *start, enum mode mode, int kind, unsigned k,
                         unsigned landed, unsigned long ordinal)
{
    dev_reset(&g_dst, start, mode);
    g_dst.inj_kind = kind;
    g_dst.inj_k = k;
    g_dst.inj_landed = landed;
    (void)run_op(dup);
    if (!g_dst.fired) { fprintf(stderr, "planned cut not reached\n"); exit(3); }
    dev_settle(&g_dst, ordinal);
    img_copy(&g_post, &g_dst.dur);
}

/* An uninterrupted run from `start`: call, trace, final durable bytes (g_post). */
static struct call clean_run(bool dup, const struct image *start, enum mode mode, char trace_sha[65])
{
    struct buf tr = {NULL, 0u, 0u};
    struct call c;
    dev_reset(&g_dst, start, mode);
    buf_str(&tr, "[");
    g_dst.trace = &tr;
    c = run_op(dup);
    g_dst.trace = NULL;
    buf_str(&tr, "]");
    sha_hex(tr.p, tr.len, trace_sha);
    free(tr.p);
    img_copy(&g_post, &g_dst.dur);
    return c;
}

/* R1 and R2: the re-run from g_pre, its injections, and (R2) the closure. */
static void rerun_rows(struct buf *out, bool dup, enum mode mode, bool all_writes, bool closure)
{
    char tsha[65], dsha[65], code[40];
    struct op ops[MAX_OPS];
    unsigned nops, i, wk = 0u, fk = 0u, first_other = MAX_OPS;
    unsigned long ord = 0u;
    struct call c;
    bool first = true;
    struct buf clo = {NULL, 0u, 0u};

    c = clean_run(dup, &g_pre, mode, tsha);
    nops = g_dst.nops;
    memcpy(ops, g_dst.ops, sizeof ops[0] * nops);
    tracked_sha(&g_post, dsha);
    mount_code(&g_post, code);
    buf_str(out, ",\"rerun\":{\"call\":");
    call_json(out, dup, c);
    buf_fmt(out, ",\"trace_sha256\":\"%s\",\"durable_sha256\":\"%s\",\"mount\":\"%s\"}", tsha, dsha, code);

    /* The engine's first write to a non-superblock LBA, in call order. */
    for (i = 0u; i < nops; ++i) if (ops[i].write && !is_sb(ops[i].lba)) { first_other = i; break; }

    buf_str(out, ",\"injections\":[");
    buf_str(&clo, "[");
    for (i = 0u; i < nops; ++i) {
        unsigned landed, lo, hi;
        int kind = ops[i].write ? 1 : 2;
        unsigned k = ops[i].write ? wk : fk;
        if (ops[i].write) {
            if (!all_writes && !is_sb(ops[i].lba)) { wk++; continue; }
            lo = 0u; hi = BLOCK;
        } else {
            lo = hi = 0u;
        }
        for (landed = lo; landed <= hi; ++landed) {
            char d[65], m[40];
            injected_run(dup, &g_pre, mode, kind, k, landed, ord++);
            tracked_sha(&g_post, d);
            mount_code(&g_post, m);
            d[16] = '\0';
            buf_fmt(out, "%s\"%s %s\"", first ? "" : ",", d, m);
            if (closure && i < first_other) {
                char t2[65], f2[65], m2[40];
                img_copy(&g_tmp, &g_post);
                (void)clean_run(dup, &g_tmp, mode, t2);
                tracked_sha(&g_post, f2);
                mount_code(&g_post, m2);
                t2[16] = '\0';
                f2[16] = '\0';
                buf_fmt(&clo, "%s\"%s %s %s\"", clo.len > 1u ? "," : "", t2, f2, m2);
            }
            first = false;
        }
        if (ops[i].write) wk++; else fk++;
    }
    buf_str(out, "]");
    buf_str(&clo, "]");
    if (closure) { buf_str(out, ",\"closure\":"); buf_str(out, clo.p); }
    free(clo.p);
}

static void ident(struct buf *out, unsigned long index, const char *row, const char *op, const char *mode)
{
    buf_fmt(out, "{\"schema\":\"wp10-residue-d10-observation-v1\",\"index\":%lu,\"row\":\"%s\",\"op\":\"%s\","
            "\"mode\":\"%s\"", index, row, op, mode);
}

static void run_r1(struct buf *out, unsigned long index, const char *op, const char *shape, const char *mode,
                   unsigned l1, const char *scope)
{
    bool dup = strcmp(op, "dup") == 0;
    enum mode m = strcmp(mode, "write_through") == 0 ? MODE_WRITE_THROUGH : MODE_FLUSH_REQUIRED;
    struct buf tr = {NULL, 0u, 0u};
    char tsha[65], dsha[65], code[40], name[80];

    ident(out, index, "R1", op, mode);
    buf_fmt(out, ",\"shape\":\"%s\",\"l1\":%u,\"scope\":\"%s\"", shape, l1, scope);
    /* First run, cut during the fallback's last zero with l1 bytes landed. */
    snprintf(name, sizeof name, "base_%s", shape);
    dev_reset(&g_dst, fixture(name), m);
    g_dst.inj_kind = 1;
    g_dst.inj_k = 1u;
    g_dst.inj_landed = l1;
    buf_str(&tr, "[");
    g_dst.trace = &tr;
    (void)run_op(dup);
    g_dst.trace = NULL;
    buf_str(&tr, "]");
    if (!g_dst.fired) { fprintf(stderr, "first-run cut not reached\n"); exit(3); }
    sha_hex(tr.p, tr.len, tsha);
    free(tr.p);
    dev_settle(&g_dst, 0u);
    img_copy(&g_pre, &g_dst.dur);
    tracked_sha(&g_pre, dsha);
    mount_code(&g_pre, code);
    buf_fmt(out, ",\"first_run\":{\"trace_sha256\":\"%s\",\"durable_sha256\":\"%s\",\"mount\":\"%s\"}",
            tsha, dsha, code);
    rerun_rows(out, dup, m, strcmp(scope, "all_writes") == 0, false);
    buf_str(out, "}\n");
}

static void run_r2(struct buf *out, unsigned long index, const char *op, const char *shape, const char *mode,
                   const char *scope)
{
    bool dup = strcmp(op, "dup") == 0;
    enum mode m = strcmp(mode, "write_through") == 0 ? MODE_WRITE_THROUGH : MODE_FLUSH_REQUIRED;
    char dsha[65], code[40], name[80];

    ident(out, index, "R2", op, mode);
    buf_fmt(out, ",\"shape\":\"%s\",\"scope\":\"%s\"", shape, scope);
    snprintf(name, sizeof name, "base_%s", shape);
    img_copy(&g_pre, fixture(name));
    tracked_sha(&g_pre, dsha);
    mount_code(&g_pre, code);
    buf_fmt(out, ",\"precondition\":{\"durable_sha256\":\"%s\",\"mount\":\"%s\"}", dsha, code);
    rerun_rows(out, dup, m, strcmp(scope, "all_writes") == 0, true);
    buf_str(out, "}\n");
}

static void run_r3(struct buf *out, unsigned long index, const char *op, const char *variant, const char *mode)
{
    bool dup = strcmp(op, "dup") == 0;
    enum mode m = strcmp(mode, "write_through") == 0 ? MODE_WRITE_THROUGH : MODE_FLUSH_REQUIRED;
    char tsha[65], dsha[65], code[40], name[80];
    struct call c;
    unsigned i;
    bool first = true;

    ident(out, index, "R3", op, mode);
    buf_fmt(out, ",\"variant\":\"%s\"", variant);
    snprintf(name, sizeof name, "blank_%s", variant);
    c = clean_run(dup, fixture(name), m, tsha);
    buf_str(out, ",\"call\":");
    call_json(out, dup, c);
    buf_fmt(out, ",\"trace_sha256\":\"%s\",\"write_lbas\":[", tsha);
    for (i = 0u; i < g_dst.nops; ++i) {
        if (!g_dst.ops[i].write) continue;
        buf_fmt(out, "%s%" PRIu32, first ? "" : ",", g_dst.ops[i].lba);
        first = false;
    }
    tracked_sha(&g_post, dsha);
    mount_code(&g_post, code);
    buf_fmt(out, "],\"durable_sha256\":\"%s\",\"mount\":\"%s\"}\n", dsha, code);
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
    unsigned long ngroups = 0u;

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
        } else if (strcmp(word, "ARGS") == 0) {
            if (fscanf(in, "%63s %63s %" SCNu32, a, b, &g_nominal) != 3) return 2;
            unhex(a, g_uuid_dup, 16u);
            unhex(b, g_uuid_format, 16u);
        } else if (strcmp(word, "FIXTURE") == 0) {
            unsigned n, i;
            uint32_t count;
            struct fixture *f;
            if (g_nfix >= sizeof g_fix / sizeof g_fix[0]) { fprintf(stderr, "too many fixtures\n"); return 2; }
            f = &g_fix[g_nfix++];
            if (fscanf(in, "%63s %" SCNu32 " %u", f->name, &count, &n) != 3 || n > MAX_BLOCKS) return 2;
            img_init(&f->img, count);
            for (i = 0u; i < n; ++i) {
                uint32_t lba;
                if (fscanf(in, "%" SCNu32 " %1030s", &lba, hexblock) != 2 || lba >= count) return 2;
                unhex(hexblock, blockbuf, BLOCK);
                img_put(&f->img, lba, blockbuf);
            }
        } else if (strcmp(word, "GROUP") == 0) {
            unsigned long index;
            if (fscanf(in, "%lu %63s %63s %63s %63s", &index, a, b, c, d) != 5) return 2;
            out.len = 0u;
            if (strcmp(a, "R1") == 0) {
                unsigned l1;
                if (fscanf(in, "%u %63s", &l1, e) != 2) return 2;
                run_r1(&out, index, b, c, d, l1, e);
            } else if (strcmp(a, "R2") == 0) {
                if (fscanf(in, "%63s", e) != 1) return 2;
                run_r2(&out, index, b, c, d, e);
            } else if (strcmp(a, "R3") == 0) {
                run_r3(&out, index, b, c, d);
            } else {
                fprintf(stderr, "unknown row %s\n", a);
                return 2;
            }
            if (fwrite(out.p, 1u, out.len, outf) != out.len) return 3;
            ++ngroups;
        } else {
            fprintf(stderr, "unknown directive %s\n", word);
            return 2;
        }
    }
    fclose(in);
    if (fclose(outf) != 0) return 3;
    fprintf(stderr, "%lu groups\n", ngroups);
    return 0;
}
