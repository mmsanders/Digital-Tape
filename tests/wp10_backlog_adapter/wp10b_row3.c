/*
 * WP-10 backlog row 3 product adapter: recording-session service writes.
 *
 * Software-owned binding for the imported verifier package
 * tests/wp10_backlog_r53. Public header only; it does not import the oracle
 * and decides nothing. run_product.py writes the C69 record fixture
 * (crash_core_draft8.fixture.record_fixture(), whole image) to IMAGE. For one
 * record mode and one durability mode this program:
 *
 *   1. runs the setup on a fresh device and instance: tape_mount(B),
 *      tape_seek(0), tape_arm(mode), one tape_feed of 384 frames;
 *   2. runs tape_service(1) until more_work == false, recording every
 *      read/write/flush callback of that service phase (the clean trace);
 *   3. for every service write k (landed 0..512) and every observed service
 *      flush j, replays 1-2 on a fresh device and cuts power at that callback,
 *      then mounts the durable bytes on a fresh device and instance, writable,
 *      Side B, and renders the whole side at 1.0x.
 *
 * It prints one wp10-backlog-r53-observation-v2 row-3 object (without the
 * index, which run_product.py adds).
 *
 * Usage: wp10b_row3 IMAGE RECORD_MODE(overwrite|overdub|splice) MODE(flush_required|write_through)
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
#define SLOT_BLOCKS 128u
#define LBA_A0 8u
#define LBA_A1 136u
#define LBA_B0 264u
#define LBA_B1 392u
#define LBA_CHUNK_BASE 2048u
#define CHUNK_BLOCKS 1024u
#define REC_FRAMES 384u
#define REC_BUDGET 1u
#define MAX_PENDING 64u

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
    case TAPE_ERR_INCOMPLETE: return "TAPE_ERR_INCOMPLETE";
    case TAPE_ERR_INCONSISTENT: return "TAPE_ERR_INCONSISTENT";
    case TAPE_ERR_NO_VALID_INDEX: return "TAPE_ERR_NO_VALID_INDEX";
    case TAPE_ERR_READ_ONLY: return "TAPE_ERR_READ_ONLY";
    case TAPE_ERR_CARTRIDGE_FULL: return "TAPE_ERR_CARTRIDGE_FULL";
    case TAPE_ERR_INDEX_FULL: return "TAPE_ERR_INDEX_FULL";
    case TAPE_ERR_FAULTED: return "TAPE_ERR_FAULTED";
    case TAPE_ERR_NOT_MOUNTED: return "TAPE_ERR_NOT_MOUNTED";
    case TAPE_ERR_BUSY: return "TAPE_ERR_BUSY";
    case TAPE_ERR_UNDERRUN: return "TAPE_ERR_UNDERRUN";
    case TAPE_ERR_INVALID_ARG: return "TAPE_ERR_INVALID_ARG";
    default: return "TAPE_ERR_OTHER";
    }
}

/* ------------------------------------------------------------------------ */
/* fault-injecting flat device                                               */
/* ------------------------------------------------------------------------ */

static uint32_t g_block_count;
static unsigned char *g_fixture;

struct pending { uint32_t lba; unsigned char data[BLOCK]; };

struct dev {
    unsigned char *cur, *dur;     /* what reads see / durable media */
    bool write_through;
    struct pending pend[MAX_PENDING];
    unsigned npend;
    int inj_kind;                 /* 0 none, 1 write k landed, 2 flush j */
    unsigned inj_k, inj_landed;
    unsigned nwrites, nflushes, ncallbacks;
    bool dead, fired;
    unsigned fired_at;            /* 1-based callback index of the injection */
    struct buf *events;           /* {op, lba, count, rc}; NULL = not listed */
};

static void ev(struct dev *d, const char *op, bool has_lba, uint32_t lba, uint32_t count, int rc)
{
    if (d->events == NULL) return;
    if (d->events->len > 1u) buf_str(d->events, ",");
    if (has_lba) buf_fmt(d->events, "{\"count\":%" PRIu32 ",\"lba\":%" PRIu32 ",\"op\":\"%s\",\"rc\":%d}", count, lba, op, rc);
    else buf_fmt(d->events, "{\"op\":\"%s\",\"rc\":%d}", op, rc);
}

static int d_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    struct dev *d = (struct dev *)v;
    if (d->dead || dst == NULL || count == 0u || (uint64_t)lba + count > g_block_count) return 1;
    d->ncallbacks++;
    memcpy(dst, d->cur + (size_t)lba * BLOCK, (size_t)count * BLOCK);
    ev(d, "read", true, lba, count, 0);
    return 0;
}

static int d_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    struct dev *d = (struct dev *)v;
    const unsigned char *s = (const unsigned char *)src;
    uint32_t i;
    if (d->dead || src == NULL || count == 0u || (uint64_t)lba + count > g_block_count) return 1;
    d->ncallbacks++;
    if (d->inj_kind == 1 && d->nwrites == d->inj_k) {
        /* Power cut during this write: its first `landed` bytes land on durable
           media over the old contents (tapefs §8.1), nothing else does. A full
           block is durable at once in write-through, and in flush-required it
           joins the unflushed set, which the cut discards. */
        d->fired = true;
        d->dead = true;
        d->fired_at = d->ncallbacks;
        if (d->inj_landed == BLOCK && d->write_through) memcpy(d->dur + (size_t)lba * BLOCK, s, BLOCK);
        else if (d->inj_landed > 0u && d->inj_landed < BLOCK) memcpy(d->dur + (size_t)lba * BLOCK, s, d->inj_landed);
        ev(d, "write", true, lba, count, 1);
        return 1;
    }
    d->nwrites++;
    for (i = 0u; i < count; ++i) {
        memcpy(d->cur + (size_t)(lba + i) * BLOCK, s + (size_t)i * BLOCK, BLOCK);
        if (d->write_through) memcpy(d->dur + (size_t)(lba + i) * BLOCK, s + (size_t)i * BLOCK, BLOCK);
        else {
            if (d->npend >= MAX_PENDING) { fprintf(stderr, "pending overflow\n"); exit(3); }
            d->pend[d->npend].lba = lba + i;
            memcpy(d->pend[d->npend].data, s + (size_t)i * BLOCK, BLOCK);
            d->npend++;
        }
    }
    ev(d, "write", true, lba, count, 0);
    return 0;
}

static int d_flush(void *v)
{
    struct dev *d = (struct dev *)v;
    unsigned i;
    if (d->dead) return 1;
    d->ncallbacks++;
    if (d->inj_kind == 2 && d->nflushes == d->inj_k) {
        /* Power cut inside this flush: the unflushed writes are discarded. */
        d->fired = true;
        d->dead = true;
        d->fired_at = d->ncallbacks;
        ev(d, "flush", false, 0u, 0u, 1);
        return 1;
    }
    d->nflushes++;
    for (i = 0u; i < d->npend; ++i) memcpy(d->dur + (size_t)d->pend[i].lba * BLOCK, d->pend[i].data, BLOCK);
    d->npend = 0u;
    ev(d, "flush", false, 0u, 0u, 0);
    return 0;
}

static void dev_reset(struct dev *d, const unsigned char *from, bool write_through)
{
    memcpy(d->cur, from, (size_t)g_block_count * BLOCK);
    memcpy(d->dur, from, (size_t)g_block_count * BLOCK);
    d->write_through = write_through;
    d->npend = 0u;
    d->inj_kind = 0;
    d->inj_k = d->inj_landed = 0u;
    d->nwrites = d->nflushes = d->ncallbacks = 0u;
    d->dead = d->fired = false;
    d->fired_at = 0u;
    d->events = NULL;
}

static tape_dev dev_of(struct dev *d)
{
    tape_dev x;
    x.read = d_read;
    x.write = d_write;
    x.flush = d_flush;
    x.ctx = d;
    x.block_count = g_block_count;
    return x;
}

/* ------------------------------------------------------------------------ */
/* engine                                                                    */
/* ------------------------------------------------------------------------ */

static unsigned char *g_mem, *g_play, *g_rec;
static size_t g_mem_len;
static tape_dev g_x;

static tape *inst(struct dev *d)
{
    tape *t = NULL;
    tape_result r;
    memset(g_mem, 0, g_mem_len);
    memset(g_play, 0, TAPE_PLAY_RING_MIN);
    memset(g_rec, 0, TAPE_REC_RING_MIN);
    g_x = dev_of(d);
    r = tape_init(g_mem, g_mem_len, &g_x, g_play, TAPE_PLAY_RING_MIN, g_rec, TAPE_REC_RING_MIN, &t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init %s\n", rname(r)); exit(3); }
    return t;
}

static tape_rec_mode g_rmode;
static const char *g_rmode_name;
static int16_t g_input[2u * REC_FRAMES];

/* The setup, identical in the clean run and every crash replay. Appends the
   setup call records to `setup` when non-NULL; returns the instance. */
static tape *setup(struct dev *d, struct buf *setup_out)
{
    tape *t = inst(d);
    tape_result rm, rs, ra, rf;
    uint32_t accepted = 0u;
    unsigned before;
    rm = tape_mount(t, TAPE_SIDE_B, 0u, NULL);
    rs = tape_seek(t, 0u);
    ra = tape_arm(t, g_rmode);
    before = d->ncallbacks;
    rf = tape_feed(t, g_input, REC_FRAMES, &accepted);
    if (setup_out) {
        buf_fmt(setup_out, "[{\"fn\":\"tape_mount\",\"side\":\"B\",\"result\":\"%s\"},"
                "{\"fn\":\"tape_seek\",\"frame\":0,\"result\":\"%s\"},"
                "{\"fn\":\"tape_arm\",\"record_mode\":\"%s\",\"result\":\"%s\"},"
                "{\"fn\":\"tape_feed\",\"requested\":%u,\"accepted\":%" PRIu32 ",\"result\":\"%s\",\"events_from_call\":%u}]",
                rname(rm), rname(rs), g_rmode_name, rname(ra), REC_FRAMES, accepted, rname(rf),
                d->ncallbacks - before);
    }
    /* Service-phase counters start here: the injections index service callbacks. */
    d->nwrites = d->nflushes = d->ncallbacks = 0u;
    return t;
}

static tape_result service_all(tape *t, bool *owed_after)
{
    tape_result r = TAPE_OK;
    unsigned guard = 0u;
    tape_status_t st;
    for (;;) {
        bool more = false;
        r = tape_service(t, REC_BUDGET, &more);
        if (r != TAPE_OK || !more || ++guard > 100000u) break;
    }
    memset(&st, 0, sizeof st);
    if (owed_after) *owed_after = tape_status(t, &st) == TAPE_OK ? st.frames_owed : true;
    return r;
}

static void sha_region(const unsigned char *img, char out[65], bool meta)
{
    SHA256_CTX c;
    unsigned char dg[SHA256_DIGEST_LENGTH];
    SHA256_Init(&c);
    if (meta) {
        /* primary SB || A0 || A1 || B0 || B1 (whole slots) || mirror SB */
        SHA256_Update(&c, img, BLOCK);
        SHA256_Update(&c, img + (size_t)LBA_A0 * BLOCK, (size_t)SLOT_BLOCKS * BLOCK);
        SHA256_Update(&c, img + (size_t)LBA_A1 * BLOCK, (size_t)SLOT_BLOCKS * BLOCK);
        SHA256_Update(&c, img + (size_t)LBA_B0 * BLOCK, (size_t)SLOT_BLOCKS * BLOCK);
        SHA256_Update(&c, img + (size_t)LBA_B1 * BLOCK, (size_t)SLOT_BLOCKS * BLOCK);
        SHA256_Update(&c, img + (size_t)(g_block_count - 1u) * BLOCK, BLOCK);
    } else {
        SHA256_Update(&c, img + (size_t)LBA_CHUNK_BASE * BLOCK, (size_t)CHUNK_BLOCKS * BLOCK);
    }
    SHA256_Final(dg, &c);
    hex_of(dg, SHA256_DIGEST_LENGTH, out);
}

static struct dev g_run, g_mnt;

/* Fresh writable Side-B mount of the durable image, with a whole-side 1.0x render. */
static void remount(struct buf *out, const unsigned char *durable)
{
    tape *t;
    tape_result r;
    dev_reset(&g_mnt, durable, true);
    t = inst(&g_mnt);
    r = tape_mount(t, TAPE_SIDE_B, 0u, NULL);
    buf_fmt(out, "{\"side\":\"B\",\"result\":\"%s\"", rname(r));
    if (r == TAPE_OK) {
        static int16_t pcm[2u * 4096u];
        tape_info info;
        SHA256_CTX c;
        unsigned char dg[SHA256_DIGEST_LENGTH];
        char h[65];
        uint64_t done = 0u;
        unsigned guard = 0u;
        memset(&info, 0, sizeof info);
        (void)tape_get_info(t, &info);
        buf_fmt(out, ",\"info\":{\"free_chunks\":%" PRIu32 ",\"total_frames\":%" PRIu64 ",\"entry_count\":%" PRIu32
                ",\"side_b_valid\":%s,\"needs_repair\":%s}", info.free_chunks, info.total_frames, info.entry_count,
                info.side_b_valid ? "true" : "false", info.needs_repair ? "true" : "false");
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
    buf_str(out, "}");
}

static void crash(struct buf *out, bool write_through, int kind, unsigned k, unsigned landed, bool first)
{
    tape *t;
    char meta[65], chunk0[65];
    dev_reset(&g_run, g_fixture, write_through);
    t = setup(&g_run, NULL);
    g_run.inj_kind = kind;
    g_run.inj_k = k;
    g_run.inj_landed = landed;
    (void)service_all(t, NULL);
    /* A flush-required cut discards every unflushed write. */
    g_run.npend = 0u;
    sha_region(g_run.dur, meta, true);
    sha_region(g_run.dur, chunk0, false);
    if (kind == 1) buf_fmt(out, "%s{\"inject\":[\"write\",%u,%u]", first ? "" : ",", k, landed);
    else buf_fmt(out, "%s{\"inject\":[\"flush\",%u]", first ? "" : ",", k);
    buf_fmt(out, ",\"fired\":%s,\"prefix_len\":%u,\"meta_sha256\":\"%s\",\"chunk0_sha256\":\"%s\",\"remount\":",
            g_run.fired ? "true" : "false", g_run.fired_at, meta, chunk0);
    remount(out, g_run.dur);
    buf_str(out, "}");
}

int main(int argc, char **argv)
{
    FILE *f;
    long size;
    struct buf out = {NULL, 0u, 0u}, st = {NULL, 0u, 0u}, evs = {NULL, 0u, 0u};
    bool write_through, owed = true;
    tape *t;
    unsigned i, k, nwrites, nflushes;

    if (argc != 4) { fprintf(stderr, "usage: %s IMAGE RECORD_MODE MODE\n", argv[0]); return 2; }
    if (strcmp(argv[2], "overwrite") == 0) g_rmode = TAPE_REC_OVERWRITE;
    else if (strcmp(argv[2], "overdub") == 0) g_rmode = TAPE_REC_OVERDUB;
    else if (strcmp(argv[2], "splice") == 0) g_rmode = TAPE_REC_SPLICE;
    else { fprintf(stderr, "unknown record mode\n"); return 2; }
    g_rmode_name = argv[2];
    if (strcmp(argv[3], "write_through") == 0) write_through = true;
    else if (strcmp(argv[3], "flush_required") == 0) write_through = false;
    else { fprintf(stderr, "unknown mode\n"); return 2; }

    f = fopen(argv[1], "rb");
    if (f == NULL || fseek(f, 0, SEEK_END) != 0 || (size = ftell(f)) <= 0 || size % (long)BLOCK) return 2;
    rewind(f);
    g_block_count = (uint32_t)(size / (long)BLOCK);
    g_fixture = malloc((size_t)size);
    if (g_fixture == NULL || fread(g_fixture, 1u, (size_t)size, f) != (size_t)size) return 2;
    fclose(f);
    g_run.cur = malloc((size_t)size); g_run.dur = malloc((size_t)size);
    g_mnt.cur = malloc((size_t)size); g_mnt.dur = malloc((size_t)size);
    g_mem_len = tape_instance_size();
    g_mem = calloc(1u, g_mem_len);
    g_play = calloc(1u, TAPE_PLAY_RING_MIN);
    g_rec = calloc(1u, TAPE_REC_RING_MIN);
    if (!g_run.cur || !g_run.dur || !g_mnt.cur || !g_mnt.dur || !g_mem || !g_play || !g_rec) return 3;

    /* A fixed, non-silent stimulus: frame i = (1000 + i, -1000 - i). */
    for (i = 0u; i < REC_FRAMES; ++i) {
        g_input[2u * i] = (int16_t)(1000 + (int)i);
        g_input[2u * i + 1u] = (int16_t)(-1000 - (int)i);
    }

    /* Clean run. */
    dev_reset(&g_run, g_fixture, write_through);
    t = setup(&g_run, &st);
    buf_str(&evs, "[");
    g_run.events = &evs;
    (void)service_all(t, &owed);
    g_run.events = NULL;
    buf_str(&evs, "]");
    nwrites = g_run.nwrites;
    nflushes = g_run.nflushes;

    buf_fmt(&out, "{\"schema\":\"wp10-backlog-r53-observation-v2\",\"row\":3,\"kind\":\"record_group\","
            "\"record_mode\":\"%s\",\"mode\":\"%s\",\"setup\":", argv[2], argv[3]);
    buf_str(&out, st.p);
    buf_str(&out, ",\"clean\":{\"events\":");
    buf_str(&out, evs.p);
    buf_fmt(&out, ",\"frames_owed_after\":%s},\"crashes\":[", owed ? "true" : "false");

    /* ADAPTER.md: every service write (landed 0..512), then each observed flush. */
    for (k = 0u; k < nwrites; ++k)
        for (i = 0u; i <= BLOCK; ++i) crash(&out, write_through, 1, k, i, k == 0u && i == 0u);
    for (k = 0u; k < nflushes; ++k) crash(&out, write_through, 2, k, 0u, nwrites == 0u && k == 0u);
    buf_str(&out, "]}\n");
    fwrite(out.p, 1u, out.len, stdout);
    return 0;
}
