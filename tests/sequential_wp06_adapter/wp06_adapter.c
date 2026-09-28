/*
 * wp06_adapter.c — Software-owned Product adapter for the imported WP-06 R44
 * sequential package (tests/sequential_wp06_r44, tree 21d45071).
 *
 * Public API only: this file includes tape.h and nothing from engine/src. It
 * drives the real engine on a sparse in-memory block device, one fresh device
 * and fresh instances per case, and writes one JSON object per case (JSONL) to
 * stdout exactly as ADAPTER.md specifies: public tape_* results and
 * tape_get_info fields, every dev_read/dev_write/dev_flush callback in order
 * (failed ones included), and full raw superblock and index-slot bytes read
 * directly from the device outside the engine. No verdict, candidate, phase,
 * selected-slot or free_next label is emitted.
 *
 * Fixtures are built through the engine itself (format, record, promote) and
 * then, where the case names a damaged or stale block, edited byte-exactly
 * outside the engine. Each case also reports the SHA-256 of its starting
 * device image in "fixture_sha256".
 */
#define _POSIX_C_SOURCE 200809L
#include "tape.h"

#include <openssl/sha.h>
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
#define CHUNK_FRAMES 131072u

/* ------------------------------------------------------------------------ */
/* sparse device                                                            */
/* ------------------------------------------------------------------------ */

#define MAP_CAP (1u << 15)

struct blk { uint32_t lba; bool used; unsigned char data[BLOCK]; };

struct dev {
    struct blk *map;           /* open-addressed, MAP_CAP entries */
    uint32_t used;
    uint32_t block_count;
    /* fault injection: fail the Nth write / flush issued while armed */
    bool arm_fail;
    int fail_write_left;       /* >0: fail when it reaches 1 */
    int fail_flush_left;
    const char *name;
};

static struct blk *map_find(struct dev *d, uint32_t lba, bool create)
{
    uint32_t h = (lba * 2654435761u) & (MAP_CAP - 1u);
    for (;;) {
        struct blk *b = &d->map[h];
        if (!b->used) {
            if (!create) return NULL;
            if (d->used + 1u >= MAP_CAP) { fprintf(stderr, "device map full\n"); exit(3); }
            b->used = true;
            b->lba = lba;
            memset(b->data, 0, BLOCK);
            d->used++;
            return b;
        }
        if (b->lba == lba) return b;
        h = (h + 1u) & (MAP_CAP - 1u);
    }
}

static void dev_get(struct dev *d, uint32_t lba, unsigned char *out)
{
    struct blk *b = map_find(d, lba, false);
    if (b == NULL) memset(out, 0, BLOCK); else memcpy(out, b->data, BLOCK);
}

static void dev_put(struct dev *d, uint32_t lba, const unsigned char *src)
{
    struct blk *b = map_find(d, lba, false);
    if (b == NULL) {
        uint32_t k;
        for (k = 0u; k < BLOCK && src[k] == 0u; ++k) {}
        if (k == BLOCK) return;          /* absent reads as zero */
        b = map_find(d, lba, true);
    }
    memcpy(b->data, src, BLOCK);
}

static void dev_open(struct dev *d, uint32_t block_count, const char *name)
{
    if (d->map == NULL) {
        d->map = calloc(MAP_CAP, sizeof *d->map);
        if (d->map == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    } else {
        memset(d->map, 0, MAP_CAP * sizeof *d->map);
    }
    d->used = 0u;
    d->block_count = block_count;
    d->arm_fail = false;
    d->fail_write_left = 0;
    d->fail_flush_left = 0;
    d->name = name;
}

/* ------------------------------------------------------------------------ */
/* JSON output                                                               */
/* ------------------------------------------------------------------------ */

static char *g_out;
static size_t g_len, g_cap;

static void out_reserve(size_t more)
{
    if (g_len + more + 1u <= g_cap) return;
    while (g_len + more + 1u > g_cap) g_cap = g_cap ? g_cap * 2u : (1u << 20);
    g_out = realloc(g_out, g_cap);
    if (g_out == NULL) { fprintf(stderr, "oom\n"); exit(3); }
}

static void outf(const char *fmt, ...)
{
    va_list ap;
    int k;
    for (;;) {
        va_start(ap, fmt);
        k = vsnprintf(g_out + g_len, g_cap - g_len, fmt, ap);
        va_end(ap);
        if (k >= 0 && (size_t)k < g_cap - g_len) { g_len += (size_t)k; return; }
        out_reserve((size_t)(k < 0 ? 4096 : k + 1));
    }
}

static void out_hex(const unsigned char *p, size_t n)
{
    static const char d[] = "0123456789abcdef";
    size_t i;
    out_reserve(2u * n);
    for (i = 0u; i < n; ++i) {
        g_out[g_len++] = d[(p[i] >> 4) & 15u];
        g_out[g_len++] = d[p[i] & 15u];
    }
    g_out[g_len] = '\0';
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
/* per-case recording: step, events, calls                                   */
/* ------------------------------------------------------------------------ */

static const char *g_step = "setup";
static bool g_logging;           /* false while building fixtures */
static unsigned g_ordinal;
static bool g_first_event, g_first_call;
static char *g_calls;            /* calls are buffered separately */
static size_t g_calls_len, g_calls_cap;
static char *g_events;
static size_t g_events_len, g_events_cap;

static void buf_append(char **buf, size_t *len, size_t *cap, const char *fmt, va_list ap)
{
    va_list ap2;
    int k;
    for (;;) {
        va_copy(ap2, ap);
        k = vsnprintf(*buf ? *buf + *len : NULL, *buf ? *cap - *len : 0u, fmt, ap2);
        va_end(ap2);
        if (*buf && k >= 0 && (size_t)k < *cap - *len) { *len += (size_t)k; return; }
        *cap = *cap ? *cap * 2u : (1u << 16);
        while (*cap < *len + (size_t)k + 1u) *cap *= 2u;
        *buf = realloc(*buf, *cap);
        if (*buf == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    }
}

static void callf(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    buf_append(&g_calls, &g_calls_len, &g_calls_cap, fmt, ap);
    va_end(ap);
}

static void eventf(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    buf_append(&g_events, &g_events_len, &g_events_cap, fmt, ap);
    va_end(ap);
}

static void log_event(const char *device, const char *op, bool has_lba, uint32_t lba,
                      uint32_t count, int rc)
{
    if (!g_logging) return;
    eventf("%s{\"step\":\"%s\",\"device\":\"%s\",\"op\":\"%s\",\"ordinal\":%u",
           g_first_event ? "" : ",", g_step, device, op, ++g_ordinal);
    if (has_lba) eventf(",\"lba\":%u,\"count\":%u", lba, count);
    eventf(",\"result\":\"%s\",\"rc\":%d}", rc == 0 ? "ok" : "error", rc);
    g_first_event = false;
}

static void call_begin(const char *fn, tape_result r)
{
    callf("%s{\"step\":\"%s\",\"fn\":\"%s\",\"result\":\"%s\"", g_first_call ? "" : ",",
          g_step, fn, rname(r));
    g_first_call = false;
}

static void call_end(void) { callf("}"); }

static void record_call(const char *fn, tape_result r)
{
    if (!g_logging) return;
    call_begin(fn, r);
    call_end();
}

/* ------------------------------------------------------------------------ */
/* callbacks                                                                 */
/* ------------------------------------------------------------------------ */

static int cb_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    struct dev *d = (struct dev *)v;
    uint32_t i;
    if (dst == NULL || count == 0u || (uint64_t)lba + count > d->block_count) {
        log_event(d->name, "read", true, lba, count, -1);
        return -1;
    }
    for (i = 0u; i < count; ++i) dev_get(d, lba + i, (unsigned char *)dst + (size_t)i * BLOCK);
    /* One event per callback invocation; a multi-block read is one read. */
    log_event(d->name, "read", true, lba, count, 0);
    return 0;
}

static int cb_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    struct dev *d = (struct dev *)v;
    uint32_t i;
    if (src == NULL || count == 0u || (uint64_t)lba + count > d->block_count) {
        log_event(d->name, "write", true, lba, count, -1);
        return -1;
    }
    if (d->arm_fail && d->fail_write_left > 0 && --d->fail_write_left == 0) {
        log_event(d->name, "write", true, lba, count, 5);
        return 5;                         /* nothing lands */
    }
    for (i = 0u; i < count; ++i) dev_put(d, lba + i, (const unsigned char *)src + (size_t)i * BLOCK);
    log_event(d->name, "write", true, lba, count, 0);
    return 0;
}

static int cb_flush(void *v)
{
    struct dev *d = (struct dev *)v;
    if (d->arm_fail && d->fail_flush_left > 0 && --d->fail_flush_left == 0) {
        log_event(d->name, "flush", false, 0u, 0u, 5);
        return 5;
    }
    log_event(d->name, "flush", false, 0u, 0u, 0);
    return 0;
}

static tape_dev dev_of(struct dev *d)
{
    tape_dev x;
    x.read = cb_read;
    x.write = cb_write;
    x.flush = cb_flush;
    x.ctx = d;
    x.block_count = d->block_count;
    return x;
}

/* ------------------------------------------------------------------------ */
/* instances                                                                 */
/* ------------------------------------------------------------------------ */

struct inst {
    unsigned char *mem, *play, *rec;
    size_t mem_len;
    tape_dev dev;
    tape *t;
};

static void inst_new(struct inst *in, struct dev *d)
{
    tape_result r;
    if (in->mem == NULL) {
        in->mem_len = tape_instance_size();
        in->mem = calloc(1u, in->mem_len);
        in->play = calloc(1u, TAPE_PLAY_RING_MIN);
        in->rec = calloc(1u, TAPE_REC_RING_MIN);
        if (in->mem == NULL || in->play == NULL || in->rec == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    }
    memset(in->mem, 0, in->mem_len);
    in->dev = dev_of(d);
    in->t = NULL;
    r = tape_init(in->mem, in->mem_len, &in->dev, in->play, TAPE_PLAY_RING_MIN,
                  in->rec, TAPE_REC_RING_MIN, &in->t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init %s\n", rname(r)); exit(3); }
}

static tape_result do_mount(struct inst *in, tape_side side)
{
    tape_result r = tape_mount(in->t, side, 0u, NULL);
    record_call("tape_mount", r);
    return r;
}

static void do_info(struct inst *in)
{
    tape_info info;
    tape_result r = tape_get_info(in->t, &info);
    if (!g_logging) return;
    call_begin("tape_get_info", r);
    if (r == TAPE_OK) {
        callf(",\"needs_repair\":%s,\"side_b_valid\":%s,\"free_chunks\":%u,\"total_chunks\":%u,"
              "\"total_frames\":%llu,\"entry_count\":%u,\"entries_free\":%u,\"writable\":%s,\"uuid\":\"",
              info.needs_repair ? "true" : "false", info.side_b_valid ? "true" : "false",
              info.free_chunks, info.total_chunks, (unsigned long long)info.total_frames,
              info.entry_count, info.entries_free, info.writable ? "true" : "false");
        {
            static const char dg[] = "0123456789abcdef";
            unsigned i;
            char hex[33];
            for (i = 0u; i < 16u; ++i) {
                hex[2u * i] = dg[(info.uuid[i] >> 4) & 15u];
                hex[2u * i + 1u] = dg[info.uuid[i] & 15u];
            }
            hex[32] = '\0';
            callf("%s\"", hex);
        }
    }
    call_end();
}

static void do_unmount(struct inst *in)
{
    uint64_t pos = 0u;
    tape_result r = tape_unmount(in->t, &pos);
    record_call("tape_unmount", r);
}

/* ------------------------------------------------------------------------ */
/* snapshots and fixture hashing                                             */
/* ------------------------------------------------------------------------ */

static bool g_first_snap;

static void snapshot(const char *name, struct dev *d)
{
    unsigned char b[BLOCK];
    static const uint32_t bases[4] = {LBA_A0, LBA_A1, LBA_B0, LBA_B1};
    static const char *const names[4] = {"A0", "A1", "B0", "B1"};
    unsigned s, k;
    outf("%s\"%s\":{\"primary\":\"", g_first_snap ? "" : ",", name);
    g_first_snap = false;
    dev_get(d, 0u, b); out_hex(b, BLOCK);
    outf("\",\"mirror\":\"");
    dev_get(d, d->block_count - 1u, b); out_hex(b, BLOCK);
    outf("\"");
    for (s = 0u; s < 4u; ++s) {
        outf(",\"%s\":\"", names[s]);
        for (k = 0u; k < SLOT_BLOCKS; ++k) { dev_get(d, bases[s] + k, b); out_hex(b, BLOCK); }
        outf("\"");
    }
    outf("}");
}

/* SHA-256 over the sparse image: non-zero blocks in ascending LBA order, each
   as a 4-byte little-endian LBA followed by its 512 bytes. */
static int cmp_u32(const void *a, const void *b)
{
    uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;
    return (x > y) - (x < y);
}

static void image_sha(struct dev *d, char out[65])
{
    uint32_t *lbas = malloc(sizeof(uint32_t) * (d->used ? d->used : 1u));
    uint32_t n = 0u, i;
    SHA256_CTX c;
    unsigned char dg[SHA256_DIGEST_LENGTH];
    static const char hx[] = "0123456789abcdef";
    if (lbas == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    for (i = 0u; i < MAP_CAP; ++i) if (d->map[i].used) lbas[n++] = d->map[i].lba;
    qsort(lbas, n, sizeof *lbas, cmp_u32);
    SHA256_Init(&c);
    SHA256_Update(&c, &d->block_count, 4u);
    for (i = 0u; i < n; ++i) {
        unsigned char b[BLOCK];
        uint32_t z;
        dev_get(d, lbas[i], b);
        for (z = 0u; z < BLOCK && b[z] == 0u; ++z) {}
        if (z == BLOCK) continue;
        SHA256_Update(&c, &lbas[i], 4u);
        SHA256_Update(&c, b, BLOCK);
    }
    SHA256_Final(dg, &c);
    for (i = 0u; i < SHA256_DIGEST_LENGTH; ++i) {
        out[2u * i] = hx[dg[i] >> 4];
        out[2u * i + 1u] = hx[dg[i] & 15u];
    }
    out[64] = '\0';
    free(lbas);
}

/* ------------------------------------------------------------------------ */
/* raw edits (outside the engine)                                            */
/* ------------------------------------------------------------------------ */

static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void wr32(unsigned char *p, uint32_t v)
{
    p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8);
    p[2] = (unsigned char)(v >> 16); p[3] = (unsigned char)(v >> 24);
}

static uint32_t crc32_ieee(const unsigned char *p, size_t n)
{
    uint32_t c = 0xFFFFFFFFu;
    size_t i;
    unsigned k;
    for (i = 0u; i < n; ++i) {
        c ^= p[i];
        for (k = 0u; k < 8u; ++k) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return c ^ 0xFFFFFFFFu;
}

static void sb_recrc(unsigned char *b) { wr32(b + 508, crc32_ieee(b, 508u)); }

static void slot_recrc(struct dev *d, uint32_t base)
{
    unsigned char h[BLOCK];
    unsigned char *buf;
    uint32_t count, eb, k;
    dev_get(d, base, h);
    count = rd32(h + 16);
    eb = (count * 12u + BLOCK - 1u) / BLOCK;
    buf = malloc((size_t)60u + (size_t)eb * BLOCK);
    if (buf == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    memcpy(buf, h, 60u);
    for (k = 0u; k < eb; ++k) dev_get(d, base + 1u + k, buf + 60u + (size_t)k * BLOCK);
    wr32(h + 60, crc32_ieee(buf, 60u + (size_t)count * 12u));
    free(buf);
    dev_put(d, base, h);
}

static void zero_block(struct dev *d, uint32_t lba)
{
    unsigned char z[BLOCK];
    memset(z, 0, BLOCK);
    dev_put(d, lba, z);
}

/* ------------------------------------------------------------------------ */
/* recording helpers                                                         */
/* ------------------------------------------------------------------------ */

static int16_t g_pcm[2u * 4096u];

/* arm / feed / service until nothing is owed. Calls are recorded in the
   current step. Returns the arm result. */
static tape_result record_frames(struct inst *in, tape_rec_mode mode, uint64_t at, uint64_t frames)
{
    tape_result r;
    uint64_t fed = 0u;
    unsigned guard = 0u;
    tape_status_t st;

    r = tape_seek(in->t, at);
    record_call("tape_seek", r);
    r = tape_arm(in->t, mode);
    record_call("tape_arm", r);
    if (r != TAPE_OK) return r;
    while (fed < frames && guard++ < 1000000u) {
        uint32_t want = (uint32_t)((frames - fed) > 4096u ? 4096u : (frames - fed));
        uint32_t acc = 0u, i;
        bool more = false;
        for (i = 0u; i < 2u * want; ++i) g_pcm[i] = (int16_t)((fed * 2u + i) * 37u + 11u);
        r = tape_feed(in->t, g_pcm, want, &acc);
        record_call("tape_feed", r);
        if (r != TAPE_OK) return r;
        fed += acc;
        r = tape_service(in->t, 64u, &more);
        record_call("tape_service", r);
        if (r != TAPE_OK) return r;
    }
    guard = 0u;
    for (;;) {
        bool more = false;
        r = tape_status(in->t, &st);
        if (r != TAPE_OK || !st.frames_owed || guard++ > 100000u) break;
        r = tape_service(in->t, 64u, &more);
        record_call("tape_service", r);
        if (r != TAPE_OK) return r;
    }
    return TAPE_OK;
}

static tape_result do_commit(struct inst *in)
{
    tape_result r = tape_commit(in->t);
    record_call("tape_commit", r);
    return r;
}

/* ------------------------------------------------------------------------ */
/* fixtures                                                                  */
/* ------------------------------------------------------------------------ */

static const uint8_t k_uuid[16] = {0x57,0x50,0x30,0x36,0x2d,0x52,0x34,0x34,0x2d,0x66,0x69,0x78,0x74,0x75,0x72,0x65};
static const uint8_t k_dup_uuid[16] = {0xd0,0xd1,0xd2,0xd3,0xd4,0xd5,0xd6,0xd7,0xd8,0xd9,0xda,0xdb,0xdc,0xdd,0xde,0xdf};

#define NOMINAL_SMALL 60u     /* 21 chunks */

static uint32_t block_count_for(uint32_t nominal_s)
{
    uint64_t frames = (uint64_t)nominal_s * 44100u;
    uint32_t chunks = (uint32_t)((frames + CHUNK_FRAMES - 1u) / CHUNK_FRAMES);
    return LBA_CHUNK_BASE + chunks * CHUNK_BLOCKS + 1u;
}

static struct dev g_dev, g_dst;
static struct inst g_in, g_in2;

/* Base cartridge: formatted, 100 frames recorded on B and promoted to A, so
   both sides are valid and identical at chunk 0. */
static void build_base(void)
{
    tape_result r;
    bool more = true;
    unsigned guard = 0u;
    dev_open(&g_dev, block_count_for(NOMINAL_SMALL), "own");
    { tape_dev x = dev_of(&g_dev); r = tape_format(&x, k_uuid, 1u, "WP06-R44", NOMINAL_SMALL); }
    if (r != TAPE_OK) { fprintf(stderr, "format %s\n", rname(r)); exit(3); }
    inst_new(&g_in, &g_dev);
    if (tape_mount(g_in.t, TAPE_SIDE_B, 0u, NULL) != TAPE_OK) { fprintf(stderr, "base mount\n"); exit(3); }
    if (record_frames(&g_in, TAPE_REC_OVERWRITE, 0u, 100u) != TAPE_OK
        || tape_commit(g_in.t) != TAPE_OK) { fprintf(stderr, "base record\n"); exit(3); }
    while (more && guard++ < 10000u) {
        more = false;
        r = tape_promote(g_in.t, 4096u, &more, NULL, NULL);
        if (r != TAPE_OK) { fprintf(stderr, "base promote %s\n", rname(r)); exit(3); }
    }
    { uint64_t pos; (void)tape_unmount(g_in.t, &pos); }
}

/* ------------------------------------------------------------------------ */
/* case families                                                             */
/* ------------------------------------------------------------------------ */

static void case_begin(const char *id)
{
    g_len = 0u;
    g_calls_len = 0u;
    g_events_len = 0u;
    if (g_calls) g_calls[0] = '\0';
    if (g_events) g_events[0] = '\0';
    g_ordinal = 0u;
    g_first_event = true;
    g_first_call = true;
    g_first_snap = true;
    g_logging = false;
    g_step = "setup";
    outf("{\"schema\":\"wp06-r44-v1\",\"case\":\"%s\"", id);
}

static void case_end(struct dev *d, const char *fixture_sha, const char *fixture_desc)
{
    outf(",\"block_count\":%u,\"fixture_sha256\":\"%s\",\"fixture\":\"%s\",\"calls\":[%s],\"events\":[%s]}\n",
         d->block_count, fixture_sha, fixture_desc, g_calls ? g_calls : "", g_events ? g_events : "");
    fwrite(g_out, 1u, g_len, stdout);
    fflush(stdout);
}

static void run_repair(const char *id, const char *shape, const char *failure)
{
    bool primary = strstr(shape, "primary") != NULL;
    uint32_t target = primary ? 0u : g_dev.block_count - 1u;
    char fx[65];
    case_begin(id);
    build_base();
    if (strncmp(shape, "invalid", 7) == 0) {
        zero_block(&g_dev, target);
    } else {
        unsigned char b[BLOCK];
        dev_get(&g_dev, target, b);
        wr32(b + 12, rd32(b + 12) - 1u);  /* stale: one generation older */
        sb_recrc(b);
        dev_put(&g_dev, target, b);
    }
    image_sha(&g_dev, fx);
    outf(",\"snapshots\":{");
    snapshot("before", &g_dev);
    g_logging = true;
    g_step = "mount";
    inst_new(&g_in, &g_dev);
    g_dev.arm_fail = true;
    if (strcmp(failure, "write") == 0) g_dev.fail_write_left = 1;
    if (strcmp(failure, "flush") == 0) g_dev.fail_flush_left = 1;
    (void)do_mount(&g_in, TAPE_SIDE_A);
    g_dev.arm_fail = false;
    do_info(&g_in);
    g_logging = false;
    snapshot("after_mount", &g_dev);
    g_logging = true;
    do_unmount(&g_in);
    g_step = "retry";
    inst_new(&g_in2, &g_dev);
    (void)do_mount(&g_in2, TAPE_SIDE_A);
    do_info(&g_in2);
    g_logging = false;
    snapshot("after_retry", &g_dev);
    outf("}");
    case_end(&g_dev, fx, "format+record(B,100)+promote; partner superblock zeroed or generation-1");
}

static void make_degraded(const char *variant)
{
    build_base();
    if (strcmp(variant, "invalid") == 0) {
        zero_block(&g_dev, LBA_B0);
        zero_block(&g_dev, LBA_B1);
    } else {
        /* Both B slots structurally valid at the live sequence, divergent. */
        unsigned char h0[BLOCK], h1[BLOCK], e[BLOCK];
        uint32_t live, other;
        dev_get(&g_dev, LBA_B0, h0);
        dev_get(&g_dev, LBA_B1, h1);
        live = rd32(h0 + 8) > rd32(h1 + 8) ? LBA_B0 : LBA_B1;
        other = live == LBA_B0 ? LBA_B1 : LBA_B0;
        dev_get(&g_dev, live, h0);
        dev_get(&g_dev, live + 1u, e);
        dev_put(&g_dev, other, h0);
        wr32(e + 8, rd32(e + 8) / 2u);           /* frame_count halves */
        dev_put(&g_dev, other + 1u, e);
        {
            unsigned char h[BLOCK];
            dev_get(&g_dev, other, h);
            h[20] = 0; h[21] = 0; h[22] = 0; h[23] = 0; h[24] = 0; h[25] = 0; h[26] = 0; h[27] = 0;
            wr32(h + 20, rd32(e + 8));          /* total_frames (u64 low word) */
            dev_put(&g_dev, other, h);
        }
        slot_recrc(&g_dev, other);
    }
}

static void exercise(struct inst *in, const char *op)
{
    tape_result r;
    bool more = false;
    if (strcmp(op, "seek") == 0) { r = tape_seek(in->t, 10u); record_call("tape_seek", r); }
    else if (strcmp(op, "set_rate") == 0) { r = tape_set_rate(in->t, 0x10000); record_call("tape_set_rate", r); }
    else if (strcmp(op, "render") == 0) {
        uint32_t n = 0u;
        r = tape_render(in->t, g_pcm, 16u, &n);
        if (g_logging) { call_begin("tape_render", r); callf(",\"rendered\":%u", n); call_end(); }
    }
    else if (strcmp(op, "service") == 0) { r = tape_service(in->t, 16u, &more); record_call("tape_service", r); }
    else if (strcmp(op, "status_info_tell") == 0) {
        tape_status_t st;
        uint64_t pos = 0u;
        do_info(in);
        r = tape_status(in->t, &st); record_call("tape_status", r);
        r = tape_tell(in->t, &pos);
        if (g_logging) { call_begin("tape_tell", r); callf(",\"position\":%llu", (unsigned long long)pos); call_end(); }
    }
    else if (strcmp(op, "arm") == 0) { r = tape_arm(in->t, TAPE_REC_OVERWRITE); record_call("tape_arm", r); }
    else if (strcmp(op, "feed") == 0) { uint32_t acc = 0u; r = tape_feed(in->t, g_pcm, 4u, &acc); record_call("tape_feed", r); }
    else if (strcmp(op, "commit") == 0) { r = tape_commit(in->t); record_call("tape_commit", r); }
    else if (strcmp(op, "abort") == 0) { r = tape_abort(in->t); record_call("tape_abort", r); }
    else if (strcmp(op, "set_side_A") == 0) { r = tape_set_side(in->t, TAPE_SIDE_A); record_call("tape_set_side", r); }
    else if (strcmp(op, "set_side_B") == 0) { r = tape_set_side(in->t, TAPE_SIDE_B); record_call("tape_set_side", r); }
    else if (strcmp(op, "reset_b") == 0) { r = tape_reset_side_b(in->t); record_call("tape_reset_side_b", r); }
    else if (strcmp(op, "promote") == 0) { r = tape_promote(in->t, 4096u, &more, NULL, NULL); record_call("tape_promote", r); }
    else if (strcmp(op, "respool") == 0) { r = tape_respool(in->t, 4096u, &more); record_call("tape_respool", r); }
    else if (strcmp(op, "dup_source") == 0) {
        tape_dev dd;
        unsigned guard = 0u;
        dev_open(&g_dst, block_count_for(NOMINAL_SMALL), "destination");
        dd = dev_of(&g_dst);
        do {
            more = false;
            r = tape_dup(in->t, &dd, k_dup_uuid, 2u, NOMINAL_SMALL, 65536u, &more, NULL, NULL);
            record_call("tape_dup", r);
        } while (r == TAPE_OK && more && guard++ < 1000u);
    }
    else if (strcmp(op, "unmount") == 0) { do_unmount(in); }
    else { fprintf(stderr, "unknown op %s\n", op); exit(3); }
}

static void run_degraded(const char *id, const char *variant, const char *op)
{
    char fx[65];
    case_begin(id);
    make_degraded(variant);
    image_sha(&g_dev, fx);
    outf(",\"snapshots\":{");
    snapshot("before", &g_dev);
    g_logging = true;
    inst_new(&g_in, &g_dev);
    if (strcmp(op, "mount_B") == 0) {
        g_step = "probe";
        (void)do_mount(&g_in, TAPE_SIDE_B);
        g_logging = false;
        outf("}");
        case_end(&g_dev, fx, variant);
        return;
    }
    g_step = "mount";
    (void)do_mount(&g_in, TAPE_SIDE_A);
    do_info(&g_in);
    g_step = "exercise";
    exercise(&g_in, op);
    if (strcmp(op, "reset_b") == 0) {
        g_logging = false;
        snapshot("after_reset", &g_dev);
        g_logging = true;
        g_step = "remount";
        do_unmount(&g_in);
        inst_new(&g_in2, &g_dev);
        (void)do_mount(&g_in2, TAPE_SIDE_A);
        do_info(&g_in2);
        g_logging = false;
        snapshot("after_remount", &g_dev);
        g_logging = true;
        g_step = "switch";
        { tape_result r = tape_set_side(g_in2.t, TAPE_SIDE_B); record_call("tape_set_side", r); }
        g_step = "exercise";
        do_info(&g_in2);
    }
    g_logging = false;
    outf("}");
    case_end(&g_dev, fx, strcmp(variant, "invalid") == 0
             ? "format+record(B,100)+promote; B0 and B1 headers zeroed"
             : "format+record(B,100)+promote; other B slot = live header at the same sequence, frame_count halved, CRC recomputed");
}

static void run_roundtrip(const char *id, const char *variant)
{
    uint32_t nominal = NOMINAL_SMALL;
    uint32_t prep = 0u;          /* 1-frame appended recordings before the measured one */
    uint64_t frames = 1u;
    char fx[65];
    tape_result r;

    if (strcmp(variant, "chunk-boundary") == 0) frames = 131073u;
    else if (strcmp(variant, "entry-block-boundary") == 0) { prep = 42u; nominal = 128u; }
    else if (strcmp(variant, "max-entries") == 0) { prep = 4095u; nominal = 12175u; }
    case_begin(id);
    dev_open(&g_dev, block_count_for(nominal), "own");
    image_sha(&g_dev, fx);
    outf(",\"snapshots\":{");
    g_logging = true;
    g_step = "format";
    { tape_dev x = dev_of(&g_dev); r = tape_format(&x, k_uuid, 1u, "WP06-R44", nominal); record_call("tape_format", r); }
    g_logging = false;
    snapshot("after_format", &g_dev);
    g_logging = true;
    g_step = "mount1";
    inst_new(&g_in, &g_dev);
    (void)do_mount(&g_in, TAPE_SIDE_B);
    /* Preparatory recordings: every entry is one frame in its own chunk,
       appended by an overwrite at the end of the timeline (one new entry, so
       tape_arm reserves one), each committed. */
    {
        uint32_t i;
        for (i = 0u; i < prep; ++i) {
            if (record_frames(&g_in, TAPE_REC_OVERWRITE, (uint64_t)i, 1u) != TAPE_OK
                || do_commit(&g_in) != TAPE_OK) { fprintf(stderr, "%s prep %u\n", id, i); exit(3); }
        }
    }
    if (strcmp(variant, "empty-commit") == 0) {
        r = tape_arm(g_in.t, TAPE_REC_OVERWRITE);
        record_call("tape_arm", r);
    } else {
        (void)record_frames(&g_in, TAPE_REC_OVERWRITE, (uint64_t)prep, frames);
    }
    g_step = "commit";
    (void)do_commit(&g_in);
    g_step = "unmount";
    do_unmount(&g_in);
    g_step = "mount2";
    inst_new(&g_in2, &g_dev);
    (void)do_mount(&g_in2, TAPE_SIDE_B);
    do_info(&g_in2);
    g_logging = false;
    snapshot("after_remount", &g_dev);
    outf("}");
    case_end(&g_dev, fx, "blank device; the case's own tape_format");
}

static void run_refusal(const char *id, const char *variant)
{
    char fx[65];
    case_begin(id);
    build_base();
    /* Repairable partner: the mirror superblock is one generation stale. */
    {
        unsigned char b[BLOCK];
        dev_get(&g_dev, g_dev.block_count - 1u, b);
        wr32(b + 12, rd32(b + 12) - 1u);
        sb_recrc(b);
        dev_put(&g_dev, g_dev.block_count - 1u, b);
    }
    if (strcmp(variant, "bad-A-with-partner") == 0) {
        /* Both A slots valid at the same sequence, divergent: A unselectable. */
        unsigned char h0[BLOCK], h1[BLOCK], e[BLOCK];
        uint32_t live, other;
        dev_get(&g_dev, LBA_A0, h0);
        dev_get(&g_dev, LBA_A1, h1);
        live = rd32(h0 + 8) > rd32(h1 + 8) ? LBA_A0 : LBA_A1;
        other = live == LBA_A0 ? LBA_A1 : LBA_A0;
        dev_get(&g_dev, live, h0);
        dev_get(&g_dev, live + 1u, e);
        dev_put(&g_dev, other, h0);
        wr32(e + 8, rd32(e + 8) / 2u);
        dev_put(&g_dev, other + 1u, e);
        {
            unsigned char h[BLOCK];
            dev_get(&g_dev, other, h);
            memset(h + 20, 0, 8u);
            wr32(h + 20, rd32(e + 8));
            dev_put(&g_dev, other, h);
        }
        slot_recrc(&g_dev, other);
    } else {
        /* promote_stage = 1 at a staging chunk no live index matches. */
        unsigned char b[BLOCK];
        dev_get(&g_dev, 0u, b);
        wr32(b + 124, 1u);
        wr32(b + 128, 5u);
        sb_recrc(b);
        dev_put(&g_dev, 0u, b);
    }
    image_sha(&g_dev, fx);
    outf(",\"snapshots\":{");
    snapshot("before", &g_dev);
    g_logging = true;
    g_step = "mount";
    inst_new(&g_in, &g_dev);
    (void)do_mount(&g_in, TAPE_SIDE_A);
    g_logging = false;
    snapshot("after_mount", &g_dev);
    outf("}");
    case_end(&g_dev, fx, strcmp(variant, "bad-A-with-partner") == 0
             ? "format+record(B,100)+promote; mirror generation-1; other A slot = live header at the same sequence, frame_count halved"
             : "format+record(B,100)+promote; mirror generation-1; primary promote_stage=1 staging=5");
}

int main(int argc, char **argv)
{
    static const char *const repairs[10][3] = {
        {"repair-invalid-primary-write", "invalid-primary", "write"},
        {"repair-invalid-primary-flush", "invalid-primary", "flush"},
        {"repair-invalid-mirror-write", "invalid-mirror", "write"},
        {"repair-invalid-mirror-flush", "invalid-mirror", "flush"},
        {"repair-stale-primary-write", "stale-primary", "write"},
        {"repair-stale-primary-flush", "stale-primary", "flush"},
        {"repair-stale-mirror-write", "stale-mirror", "write"},
        {"repair-stale-mirror-flush", "stale-mirror", "flush"},
        {"repair-invalid-primary-success", "invalid-primary", "success"},
        {"repair-stale-mirror-success", "stale-mirror", "success"},
    };
    static const char *const degraded_ops[16] = {
        "seek", "set_rate", "render", "service", "status_info_tell", "arm", "feed",
        "commit", "abort", "set_side_A", "set_side_B", "reset_b", "promote",
        "respool", "dup_source", "unmount",
    };
    static const char *const divergent_ops[5] = {"mount_B", "reset_b", "set_side_B", "promote", "respool"};
    static const char *const roundtrips[5] = {"one-frame", "chunk-boundary", "entry-block-boundary", "max-entries", "empty-commit"};
    static const char *const refusals[2] = {"bad-A-with-partner", "bad-stage-with-partner"};
    char id[128];
    unsigned i;
    const char *only = argc > 1 ? argv[1] : NULL;

    for (i = 0u; i < 10u; ++i)
        if (!only || strcmp(only, repairs[i][0]) == 0) run_repair(repairs[i][0], repairs[i][1], repairs[i][2]);
    for (i = 0u; i < 16u; ++i) {
        snprintf(id, sizeof id, "degraded-invalid-%s", degraded_ops[i]);
        if (!only || strcmp(only, id) == 0) run_degraded(id, "invalid", degraded_ops[i]);
    }
    for (i = 0u; i < 5u; ++i) {
        snprintf(id, sizeof id, "degraded-divergent-%s", divergent_ops[i]);
        if (!only || strcmp(only, id) == 0) run_degraded(id, "divergent", divergent_ops[i]);
    }
    for (i = 0u; i < 5u; ++i) {
        snprintf(id, sizeof id, "roundtrip-%s", roundtrips[i]);
        if (!only || strcmp(only, id) == 0) run_roundtrip(id, roundtrips[i]);
    }
    for (i = 0u; i < 2u; ++i) {
        snprintf(id, sizeof id, "refusal-%s", refusals[i]);
        if (!only || strcmp(only, id) == 0) run_refusal(id, refusals[i]);
    }
    return 0;
}
