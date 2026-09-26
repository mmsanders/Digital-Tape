#define _POSIX_C_SOURCE 200809L
#ifndef TAPE_PUBLIC_HEADER
#define TAPE_PUBLIC_HEADER "tape.h"
#endif
#include TAPE_PUBLIC_HEADER
/* Read-only white-box access for the source facts ADAPTER.md asks for that no
   public call exposes (rate_q16_16, transport row, play-window indices, fault
   state). Nothing here writes engine state. */
#include "tape_internal.h"

#include <openssl/sha.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BLOCK 512u
#define MAX_BLOCKS 96u
#define MAX_TARGETS 8u
#define SHAPE_BYTES (4u * BLOCK)
#define SOURCE_BYTES (6u * BLOCK)
#define LBA_PRIMARY 0u
#define LBA_A0 8u
#define LBA_B0 264u
#define LBA_CHUNK_BASE 2048u
#define BLOCK_COUNT 6145u
#define LBA_MIRROR (BLOCK_COUNT - 1u)

struct block_slot {
    uint32_t lba;
    unsigned char bytes[BLOCK];
};

struct image {
    struct block_slot slots[MAX_BLOCKS];
    size_t count;
};

enum inj_kind {
    INJ_NONE = 0,
    INJ_BEFORE_WRITE,
    INJ_TORN_WRITE,
    INJ_AFTER_WRITE,
    INJ_AT_FLUSH
};

struct target_write {
    uint32_t lba;
    unsigned char sha[SHA256_DIGEST_LENGTH];
};

struct dev_ctx {
    struct image working;
    struct image durable;
    bool write_through;
    enum inj_kind inj;
    unsigned target_ordinal;
    unsigned landed_bytes;
    unsigned target_write_seen;
    unsigned target_flush_seen;
    bool last_write_target;
    bool after_write_pending;
    bool injection_fired;
    bool baseline;
    struct target_write targets[MAX_TARGETS];
    unsigned target_count;
    /* Contract probe only: device label for the event trace, and an optional
       ordinal of the ordinary write that fails with a raw non-zero return. */
    const char *name;
    int fail_write_ordinal;
    unsigned writes_seen;
};

/* Chronological raw callback trace across every device, contract probe only. */
struct block_event {
    const char *device;
    char op;               /* 'r', 'w', 'f' */
    uint32_t lba, count;
    int rc;
};
#define MAX_EVENTS 8192u
static struct block_event g_ev[MAX_EVENTS];
static unsigned g_evn;
static bool g_logging;

static void log_event(const struct dev_ctx *ctx, char op, uint32_t lba, uint32_t count, int rc)
{
    if (!g_logging || g_evn >= MAX_EVENTS) return;
    g_ev[g_evn].device = ctx->name != NULL ? ctx->name : "unnamed";
    g_ev[g_evn].op = op;
    g_ev[g_evn].lba = lba;
    g_ev[g_evn].count = count;
    g_ev[g_evn].rc = rc;
    g_evn++;
}

struct fixture {
    const char *name;
    unsigned char raw[SHAPE_BYTES];
};

static struct fixture g_shapes[7];
static unsigned char g_source[SOURCE_BYTES];
static unsigned char g_source_big[SOURCE_BYTES];

static const char *result_name(tape_result r)
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

static void print_hex(const unsigned char *p, size_t n)
{
    static const char d[] = "0123456789abcdef";
    size_t i;
    for (i = 0u; i < n; ++i) {
        putchar(d[(p[i] >> 4) & 15u]);
        putchar(d[p[i] & 15u]);
    }
}

static void sha_hex(const unsigned char *p, size_t n, char out[65])
{
    unsigned char digest[SHA256_DIGEST_LENGTH];
    static const char d[] = "0123456789abcdef";
    size_t i;
    (void)SHA256(p, n, digest);
    for (i = 0u; i < SHA256_DIGEST_LENGTH; ++i) {
        out[2u * i] = d[(digest[i] >> 4) & 15u];
        out[2u * i + 1u] = d[digest[i] & 15u];
    }
    out[64] = '\0';
}

static struct block_slot *find_slot(struct image *img, uint32_t lba)
{
    size_t i;
    for (i = 0u; i < img->count; ++i) {
        if (img->slots[i].lba == lba) return &img->slots[i];
    }
    return NULL;
}

static const struct block_slot *find_slot_const(const struct image *img, uint32_t lba)
{
    size_t i;
    for (i = 0u; i < img->count; ++i) {
        if (img->slots[i].lba == lba) return &img->slots[i];
    }
    return NULL;
}

static int set_block(struct image *img, uint32_t lba, const unsigned char *src)
{
    struct block_slot *s = find_slot(img, lba);
    if (s == NULL) {
        size_t i;
        /* Absent slots read as zero, so a zero block needs no storage. */
        for (i = 0u; i < BLOCK && src[i] == 0u; ++i) {}
        if (i == BLOCK) return 0;
        if (img->count >= MAX_BLOCKS) return -1;
        s = &img->slots[img->count++];
        s->lba = lba;
    }
    memcpy(s->bytes, src, BLOCK);
    return 0;
}

static void get_block(const struct image *img, uint32_t lba, unsigned char *dst)
{
    const struct block_slot *s = find_slot_const(img, lba);
    if (s == NULL) memset(dst, 0, BLOCK);
    else memcpy(dst, s->bytes, BLOCK);
}

static int read_cb(void *v, uint32_t lba, uint32_t count, void *dst)
{
    struct dev_ctx *ctx = (struct dev_ctx *)v;
    unsigned char *out = (unsigned char *)dst;
    uint32_t i;
    if (dst == NULL || count == 0u || (uint64_t)lba + count > BLOCK_COUNT) {
        log_event(ctx, 'r', lba, count, -1);
        return -1;
    }
    for (i = 0u; i < count; ++i) get_block(&ctx->working, lba + i, out + (size_t)i * BLOCK);
    log_event(ctx, 'r', lba, count, 0);
    return 0;
}

static bool target_lba(uint32_t lba, uint32_t count)
{
    return count == 1u && (lba == LBA_PRIMARY || lba == LBA_MIRROR);
}

static int full_write(struct dev_ctx *ctx, uint32_t lba, uint32_t count,
                      const unsigned char *src)
{
    uint32_t i;
    for (i = 0u; i < count; ++i) {
        if (set_block(&ctx->working, lba + i, src + (size_t)i * BLOCK) != 0) return -1;
        if (ctx->write_through
            && set_block(&ctx->durable, lba + i, src + (size_t)i * BLOCK) != 0) return -1;
    }
    return 0;
}

static int write_cb_raw(struct dev_ctx *ctx, uint32_t lba, uint32_t count, const void *srcv);

static int write_cb(void *v, uint32_t lba, uint32_t count, const void *srcv)
{
    struct dev_ctx *ctx = (struct dev_ctx *)v;
    unsigned ord = ctx->writes_seen++;
    int rc;
    if (ctx->fail_write_ordinal >= 0 && ord == (unsigned)ctx->fail_write_ordinal) {
        log_event(ctx, 'w', lba, count, 5);
        return 5;
    }
    rc = write_cb_raw(ctx, lba, count, srcv);
    log_event(ctx, 'w', lba, count, rc);
    return rc;
}

static int write_cb_raw(struct dev_ctx *ctx, uint32_t lba, uint32_t count, const void *srcv)
{
    const unsigned char *src = (const unsigned char *)srcv;
    bool target;
    unsigned ord = 0u;
    if (src == NULL || count == 0u || (uint64_t)lba + count > BLOCK_COUNT) return -1;

    target = target_lba(lba, count);
    ctx->last_write_target = target;
    if (target) {
        ord = ctx->target_write_seen++;
        if (ctx->baseline && ctx->target_count < MAX_TARGETS) {
            ctx->targets[ctx->target_count].lba = lba;
            (void)SHA256(src, BLOCK, ctx->targets[ctx->target_count].sha);
            ctx->target_count++;
        }
        if (!ctx->baseline && ord == ctx->target_ordinal) {
            if (ctx->inj == INJ_BEFORE_WRITE) {
                ctx->injection_fired = true;
                return -1;
            }
            if (ctx->inj == INJ_TORN_WRITE) {
                unsigned char old[BLOCK];
                unsigned char torn[BLOCK];
                if (ctx->landed_bytes == 0u || ctx->landed_bytes >= BLOCK) return -1;
                get_block(&ctx->working, lba, old);
                memcpy(torn, old, BLOCK);
                memcpy(torn, src, ctx->landed_bytes);
                if (set_block(&ctx->working, lba, torn) != 0
                    || set_block(&ctx->durable, lba, torn) != 0) return -1;
                ctx->injection_fired = true;
                return -1;
            }
            if (ctx->inj == INJ_AFTER_WRITE) {
                if (full_write(ctx, lba, count, src) != 0) return -1;
                ctx->after_write_pending = true;
                return 0;
            }
        }
    }
    return full_write(ctx, lba, count, src);
}

static int flush_cb_raw(struct dev_ctx *ctx);

static int flush_cb(void *v)
{
    struct dev_ctx *ctx = (struct dev_ctx *)v;
    int rc = flush_cb_raw(ctx);
    log_event(ctx, 'f', 0u, 0u, rc);
    return rc;
}

static int flush_cb_raw(struct dev_ctx *ctx)
{
    if (ctx->last_write_target) {
        unsigned ord = ctx->target_flush_seen++;
        if (!ctx->baseline && ctx->after_write_pending
            && ord == ctx->target_ordinal) {
            ctx->after_write_pending = false;
            ctx->injection_fired = true;
            return -1;
        }
        if (!ctx->baseline && ctx->inj == INJ_AT_FLUSH
            && ord == ctx->target_ordinal) {
            ctx->injection_fired = true;
            return -1;
        }
    }
    ctx->durable = ctx->working;
    ctx->last_write_target = false;
    return 0;
}

static int noop_flush(void *v)
{
    log_event((const struct dev_ctx *)v, 'f', 0u, 0u, 0);
    return 0;
}

static const struct fixture *shape_by_name(const char *name)
{
    unsigned i;
    for (i = 0u; i < 7u; ++i) if (strcmp(g_shapes[i].name, name) == 0) return &g_shapes[i];
    return NULL;
}

static void load_destination(struct dev_ctx *ctx, const struct fixture *f)
{
    unsigned char entry[BLOCK];
    memset(ctx, 0, sizeof *ctx);
    ctx->fail_write_ordinal = -1;
    memset(entry, 0, sizeof entry);
    entry[8] = 100u;
    (void)set_block(&ctx->working, LBA_PRIMARY, f->raw);
    (void)set_block(&ctx->working, LBA_MIRROR, f->raw + BLOCK);
    (void)set_block(&ctx->working, LBA_A0, f->raw + 2u * BLOCK);
    (void)set_block(&ctx->working, LBA_B0, f->raw + 3u * BLOCK);
    /* Raw snapshots carry headers only. Add the matching one-entry payload as
       ordinary unseen device bytes so an old valid destination can be mounted. */
    memset(entry, 0, sizeof entry);
    entry[8] = 100u;
    (void)set_block(&ctx->working, LBA_A0 + 1u, entry);
    (void)set_block(&ctx->working, LBA_B0 + 1u, entry);
    ctx->durable = ctx->working;
}

static int load_source_image(struct dev_ctx *ctx, const unsigned char *img)
{
    unsigned char entry[BLOCK];
    memset(ctx, 0, sizeof *ctx);
    ctx->fail_write_ordinal = -1;
    /* B0's one-entry payload {0,0,100}; the source file carries A0's. */
    memset(entry, 0, sizeof entry);
    entry[8] = 100u;
    if (set_block(&ctx->working, LBA_PRIMARY, img) != 0
        || set_block(&ctx->working, LBA_MIRROR, img + BLOCK) != 0
        || set_block(&ctx->working, LBA_A0, img + 2u * BLOCK) != 0
        || set_block(&ctx->working, LBA_A0 + 1u, img + 3u * BLOCK) != 0
        || set_block(&ctx->working, LBA_B0, img + 4u * BLOCK) != 0
        || set_block(&ctx->working, LBA_B0 + 1u, entry) != 0
        || set_block(&ctx->working, LBA_CHUNK_BASE, img + 5u * BLOCK) != 0) return -1;
    ctx->durable = ctx->working;
    return 0;
}

static tape_result run_operation(const char *op, struct dev_ctx *dst)
{
    tape_dev dd;
    static const uint8_t fmt_uuid[16] =
        {0xa0,0xa1,0xa2,0xa3,0xa4,0xa5,0xa6,0xa7,0xa8,0xa9,0xaa,0xab,0xac,0xad,0xae,0xaf};
    static const uint8_t dup_uuid[16] =
        {0xb0,0xb1,0xb2,0xb3,0xb4,0xb5,0xb6,0xb7,0xb8,0xb9,0xba,0xbb,0xbc,0xbd,0xbe,0xbf};
    dd.read = read_cb; dd.write = write_cb; dd.flush = flush_cb; dd.ctx = dst; dd.block_count = BLOCK_COUNT;

    if (strcmp(op, "format") == 0) {
        return tape_format(&dd, fmt_uuid, 0u, "", 9u);
    }
    if (strcmp(op, "dup") == 0) {
        struct dev_ctx src;
        tape_dev sd;
        tape *t = NULL;
        void *mem;
        void *play;
        void *rec;
        size_t need = tape_instance_size();
        tape_result r;
        bool more = false;
        unsigned guard = 0u;
        if (load_source_image(&src, g_source) != 0) return TAPE_ERR_IO;
        sd.read = read_cb; sd.write = NULL; sd.flush = noop_flush; sd.ctx = &src; sd.block_count = BLOCK_COUNT;
        mem = calloc(1u, need);
        play = calloc(1u, TAPE_PLAY_RING_MIN);
        rec = calloc(1u, TAPE_REC_RING_MIN);
        if (mem == NULL || play == NULL || rec == NULL) {
            free(mem); free(play); free(rec); return TAPE_ERR_IO;
        }
        r = tape_init(mem, need, &sd, play, TAPE_PLAY_RING_MIN, rec, TAPE_REC_RING_MIN, &t);
        if (r == TAPE_OK) r = tape_mount(t, TAPE_SIDE_A, 0u, NULL);
        if (r == TAPE_OK) {
            do {
                more = false;
                r = tape_dup(t, &dd, dup_uuid, 0u, 9u, 65535u, &more, NULL, NULL);
                guard++;
            } while (r == TAPE_OK && more && guard < 10000u);
            if (guard >= 10000u && r == TAPE_OK && more) r = TAPE_ERR_BUSY;
        }
        free(mem); free(play); free(rec);
        return r;
    }
    return TAPE_ERR_INVALID_ARG;
}

static tape_result remount_result(const struct image *durable, uint8_t uuid[16], bool *have_uuid)
{
    struct dev_ctx ctx;
    tape_dev dev;
    tape *t = NULL;
    tape_info info;
    void *mem;
    void *play;
    void *rec;
    size_t need = tape_instance_size();
    tape_result r;
    memset(&ctx, 0, sizeof ctx);
    ctx.fail_write_ordinal = -1;
    ctx.working = *durable;
    ctx.durable = *durable;
    dev.read = read_cb; dev.write = write_cb; dev.flush = flush_cb; dev.ctx = &ctx; dev.block_count = BLOCK_COUNT;
    mem = calloc(1u, need);
    play = calloc(1u, TAPE_PLAY_RING_MIN);
    rec = calloc(1u, TAPE_REC_RING_MIN);
    if (mem == NULL || play == NULL || rec == NULL) {
        free(mem); free(play); free(rec); return TAPE_ERR_IO;
    }
    r = tape_init(mem, need, &dev, play, TAPE_PLAY_RING_MIN, rec, TAPE_REC_RING_MIN, &t);
    if (r == TAPE_OK) r = tape_mount(t, TAPE_SIDE_A, 0u, NULL);
    *have_uuid = false;
    if (r == TAPE_OK && tape_get_info(t, &info) == TAPE_OK) {
        memcpy(uuid, info.uuid, 16u);
        *have_uuid = true;
    }
    free(mem); free(play); free(rec);
    return r;
}

static void print_snapshot(const struct image *img)
{
    unsigned char b[BLOCK];
    printf("{\"format\":\"FMTDUP-ID-RAW-1\",\"block_count\":%u,\"primary_hex\":\"", BLOCK_COUNT);
    get_block(img, LBA_PRIMARY, b); print_hex(b, BLOCK);
    printf("\",\"mirror_hex\":\"");
    get_block(img, LBA_MIRROR, b); print_hex(b, BLOCK);
    printf("\",\"a0_head_hex\":\"");
    get_block(img, LBA_A0, b); print_hex(b, BLOCK);
    printf("\",\"b0_head_hex\":\"");
    get_block(img, LBA_B0, b); print_hex(b, BLOCK);
    printf("\"}");
}

static enum inj_kind parse_inj(const char *s)
{
    if (strcmp(s, "before_write") == 0) return INJ_BEFORE_WRITE;
    if (strcmp(s, "torn_write") == 0) return INJ_TORN_WRITE;
    if (strcmp(s, "after_write") == 0) return INJ_AFTER_WRITE;
    if (strcmp(s, "at_flush") == 0) return INJ_AT_FLUSH;
    return INJ_NONE;
}

static int read_exact(const char *path, unsigned char *dst, size_t n)
{
    FILE *f = fopen(path, "rb");
    size_t got;
    int extra;
    if (f == NULL) return -1;
    got = fread(dst, 1u, n, f);
    extra = fgetc(f);
    if (fclose(f) != 0 || got != n || extra != EOF) return -1;
    return 0;
}

static int handle_baseline(const char *op, const char *shape)
{
    const struct fixture *f = shape_by_name(shape);
    struct dev_ctx dst;
    tape_result r;
    unsigned i;
    char hex[65];
    if (f == NULL) return -1;
    load_destination(&dst, f);
    dst.baseline = true;
    r = run_operation(op, &dst);
    printf("{\"result\":\"%s\",\"targets\":[", result_name(r));
    for (i = 0u; i < dst.target_count; ++i) {
        if (i != 0u) putchar(',');
        sha_hex(dst.targets[i].sha, SHA256_DIGEST_LENGTH, hex);
        /* sha_hex above hashes the digest; print the captured digest directly instead. */
        printf("{\"lba\":%u,\"sha256\":\"", dst.targets[i].lba);
        print_hex(dst.targets[i].sha, SHA256_DIGEST_LENGTH);
        printf("\"}");
    }
    printf("]}\n");
    fflush(stdout);
    return 0;
}

static int handle_case(unsigned case_index, const char *op, const char *shape,
                       const char *mode, const char *inj_s,
                       unsigned ordinal, unsigned landed)
{
    const struct fixture *f = shape_by_name(shape);
    struct dev_ctx dst;
    tape_result r;
    tape_result remount;
    uint8_t uuid[16];
    bool have_uuid = false;
    if (f == NULL) return -1;
    load_destination(&dst, f);
    dst.write_through = strcmp(mode, "write_through") == 0;
    dst.inj = parse_inj(inj_s);
    dst.target_ordinal = ordinal;
    dst.landed_bytes = landed;
    r = run_operation(op, &dst);
    remount = remount_result(&dst.durable, uuid, &have_uuid);

    printf("{\"case_index\":%u,\"call_result\":\"%s\",\"injection_fired\":%s,\"post_snapshot\":",
           case_index, result_name(r), dst.injection_fired ? "true" : "false");
    print_snapshot(&dst.durable);
    printf(",\"actual_remount_result\":\"%s\"", result_name(remount));
    if (have_uuid) {
        printf(",\"actual_selected_uuid\":\"");
        print_hex(uuid, 16u);
        printf("\"");
    }
    printf("}\n");
    fflush(stdout);
    return 0;
}

/* ------------------------------------------------------------------------- */
/* Contract families (ADAPTER.md WP-12a vocabulary). Raw facts only: public   */
/* results, counters, byte traces and snapshots. Verification derives every   */
/* verdict; nothing below decides pass or fail.                               */
/* ------------------------------------------------------------------------- */

struct jb {
    char *p;
    size_t n, cap;
};

static char g_main_buf[1u << 20];

static void jb_init(struct jb *b, char *mem, size_t cap)
{
    b->p = mem;
    b->n = 0u;
    b->cap = cap;
    b->p[0] = '\0';
}

static void jb_printf(struct jb *b, const char *fmt, ...)
{
    va_list ap;
    int w;
    if (b->n >= b->cap) return;
    va_start(ap, fmt);
    w = vsnprintf(b->p + b->n, b->cap - b->n, fmt, ap);
    va_end(ap);
    if (w < 0) return;
    b->n += (size_t)w;
    if (b->n >= b->cap) {
        fprintf(stderr, "json buffer overflow\n");
        exit(3);
    }
}

static void jb_hex(struct jb *b, const unsigned char *p, size_t n)
{
    static const char d[] = "0123456789abcdef";
    size_t i;
    if (b->n + 2u * n + 1u >= b->cap) {
        fprintf(stderr, "json buffer overflow\n");
        exit(3);
    }
    for (i = 0u; i < n; ++i) {
        b->p[b->n++] = d[(p[i] >> 4) & 15u];
        b->p[b->n++] = d[p[i] & 15u];
    }
    b->p[b->n] = '\0';
}

static void jb_events(struct jb *b, unsigned from, unsigned to, const char *only)
{
    unsigned i;
    bool first = true;
    jb_printf(b, "[");
    for (i = from; i < to; ++i) {
        const struct block_event *e = &g_ev[i];
        if (only != NULL && strcmp(e->device, only) != 0) continue;
        if (!first) jb_printf(b, ",");
        first = false;
        if (e->op == 'f') {
            jb_printf(b, "{\"op\":\"flush\",\"device\":\"%s\",\"rc\":%d}", e->device, e->rc);
        } else {
            jb_printf(b, "{\"op\":\"%s\",\"device\":\"%s\",\"lba\":%u,\"count\":%u,\"rc\":%d}",
                      e->op == 'r' ? "read" : "write", e->device, e->lba, e->count, e->rc);
        }
    }
    jb_printf(b, "]");
}

static void jb_snapshot(struct jb *b, const struct image *img)
{
    unsigned char blk[BLOCK];
    jb_printf(b, "{\"format\":\"FMTDUP-ID-RAW-1\",\"block_count\":%u,\"primary_hex\":\"", BLOCK_COUNT);
    get_block(img, LBA_PRIMARY, blk); jb_hex(b, blk, BLOCK);
    jb_printf(b, "\",\"mirror_hex\":\"");
    get_block(img, LBA_MIRROR, blk); jb_hex(b, blk, BLOCK);
    jb_printf(b, "\",\"a0_head_hex\":\"");
    get_block(img, LBA_A0, blk); jb_hex(b, blk, BLOCK);
    jb_printf(b, "\",\"b0_head_hex\":\"");
    get_block(img, LBA_B0, blk); jb_hex(b, blk, BLOCK);
    jb_printf(b, "\"}");
}

/* The fifteen engine-api §10 columns, in planner order. */
static const char *const k_columns[15] = {
    "seek", "set_rate", "render", "service", "status_info_tell",
    "arm", "feed", "commit", "abort", "set_side", "reset_b",
    "promote", "respool", "dup", "unmount",
};

static int column_index(const char *name)
{
    int i;
    for (i = 0; i < 15; ++i) if (strcmp(k_columns[i], name) == 0) return i;
    return -1;
}

static const uint8_t k_dup_uuid[16] =
    {0xb0,0xb1,0xb2,0xb3,0xb4,0xb5,0xb6,0xb7,0xb8,0xb9,0xba,0xbb,0xbc,0xbd,0xbe,0xbf};
#define DUP_EPOCH 0u
#define DUP_NOMINAL 9u

/* Contract fixture state. Static because each is ~100 KiB of sparse image. */
static struct dev_ctx g_src_ctx, g_dst_ctx, g_dst2_ctx;
static tape_dev g_src_dev, g_dst_dev, g_dst2_dev;
static void *g_mem, *g_play, *g_rec;

/* Raw operation observation: engine-sourced progress (the last blocks_done the
   progress callback delivered), destination event count and cumulative
   chronological chunk-region write LBAs from the destination trace. The token
   is a non-causal adapter label. */
static bool g_op_started;
static uint32_t g_op_progress;

struct cb_state {
    unsigned entries, depth, max_depth;
    int probe_column;          /* -1: none */
    bool probe_done;
    tape *t;
    struct jb *out;            /* nested observation */
};

static void jb_opstate(struct jb *b)
{
    unsigned i, dst_events = 0u;
    bool first = true;
    if (g_op_started) jb_printf(b, "{\"operation_token\":\"dup-1\"");
    else jb_printf(b, "{\"operation_token\":null");
    for (i = 0u; i < g_evn; ++i) if (strcmp(g_ev[i].device, "destination") == 0) dst_events++;
    jb_printf(b, ",\"progress_blocks\":%u,\"destination_event_count\":%u,\"chunk_write_lbas\":[",
              g_op_progress, dst_events);
    for (i = 0u; i < g_evn; ++i) {
        const struct block_event *e = &g_ev[i];
        uint32_t k;
        if (e->op != 'w' || e->rc != 0 || strcmp(e->device, "destination") != 0) continue;
        for (k = 0u; k < e->count; ++k) {
            uint32_t lba = e->lba + k;
            if (lba < LBA_CHUNK_BASE || lba >= LBA_MIRROR) continue;
            if (!first) jb_printf(b, ",");
            first = false;
            jb_printf(b, "%u", lba);
        }
    }
    jb_printf(b, "]}");
}

static unsigned dst_event_count(void)
{
    unsigned i, n = 0u;
    for (i = 0u; i < g_evn; ++i) if (strcmp(g_ev[i].device, "destination") == 0) n++;
    return n;
}

static void progress_cb(void *user, uint32_t done, uint32_t total);
static void progress_cb_b(void *user, uint32_t done, uint32_t total);

static tape_result dup_call(tape *t, const tape_dev *dst, const uint8_t *uuid,
                            uint32_t epoch, uint32_t nominal, uint32_t budget,
                            bool *more, tape_progress_fn cb, void *user)
{
    tape_result r = tape_dup(t, dst, uuid, epoch, nominal, budget, more, cb, user);
    if (r == TAPE_OK) g_op_started = true;
    return r;
}

static void render_probe(tape *t, struct jb *b)
{
    int16_t out[2u * 32u];
    uint32_t rendered = 0u;
    unsigned ev0 = g_evn;
    tape_result r;
    memset(out, 0, sizeof out);
    r = tape_render(t, out, 32u, &rendered);
    jb_printf(b, "{\"fn\":\"tape_render\",\"result\":\"%s\",\"rendered\":%u,\"output_hex\":\"",
              result_name(r), rendered);
    jb_hex(b, (const unsigned char *)out, (size_t)rendered * 4u);
    jb_printf(b, "\",\"block_events\":");
    jb_events(b, ev0, g_evn, NULL);
    jb_printf(b, "}");
}

static void status_probe(tape *t, struct jb *b)
{
    tape_status_t st;
    tape_info info;
    uint64_t pos = 0u;
    unsigned ev0 = g_evn;
    tape_result r1 = tape_status(t, &st);
    tape_result r2 = tape_get_info(t, &info);
    tape_result r3 = tape_tell(t, &pos);
    jb_printf(b, "{\"calls\":[{\"fn\":\"tape_status\",\"result\":\"%s\"},"
                 "{\"fn\":\"tape_get_info\",\"result\":\"%s\"},"
                 "{\"fn\":\"tape_tell\",\"result\":\"%s\",\"position\":%llu}],\"block_events\":",
              result_name(r1), result_name(r2), result_name(r3), (unsigned long long)pos);
    jb_events(b, ev0, g_evn, NULL);
    jb_printf(b, "}");
}

/* One §10 column against the source instance. */
static void column_probe(tape *t, int col, struct jb *b, void *cb_user)
{
    unsigned ev0;
    tape_result r = TAPE_ERR_INVALID_ARG;
    bool more = false;
    bool has_more = false;
    const char *fn = "";

    if (col == 2) { render_probe(t, b); return; }
    if (col == 4) { status_probe(t, b); return; }

    ev0 = g_evn;
    if (col == 0) { fn = "tape_seek"; r = tape_seek(t, 0u); }
    else if (col == 1) { fn = "tape_set_rate"; r = tape_set_rate(t, 65536); }
    else if (col == 3) { fn = "tape_service"; r = tape_service(t, 8u, &more); }
    else if (col == 5) { fn = "tape_arm"; r = tape_arm(t, TAPE_REC_OVERWRITE); }
    else if (col == 6) {
        int16_t in[2] = {1, 1};
        uint32_t acc = 0u;
        fn = "tape_feed"; r = tape_feed(t, in, 1u, &acc);
    }
    else if (col == 7) { fn = "tape_commit"; r = tape_commit(t); }
    else if (col == 8) { fn = "tape_abort"; r = tape_abort(t); }
    else if (col == 9) { fn = "tape_set_side"; r = tape_set_side(t, TAPE_SIDE_B); }
    else if (col == 10) { fn = "tape_reset_side_b"; r = tape_reset_side_b(t); }
    else if (col == 11) { fn = "tape_promote"; r = tape_promote(t, 8u, &more, NULL, NULL); }
    else if (col == 12) { fn = "tape_respool"; r = tape_respool(t, 8u, &more); }
    else if (col == 13) {
        fn = "tape_dup";
        r = dup_call(t, &g_dst_dev, k_dup_uuid, DUP_EPOCH, DUP_NOMINAL, 1u, &more,
                     progress_cb, cb_user);
        has_more = true;
    }
    else if (col == 14) {
        uint64_t pos = 0u;
        fn = "tape_unmount"; r = tape_unmount(t, &pos);
    }
    jb_printf(b, "{\"fn\":\"%s\",\"result\":\"%s\"", fn, result_name(r));
    if (has_more) jb_printf(b, ",\"more_work\":%s", more ? "true" : "false");
    jb_printf(b, ",\"block_events\":");
    jb_events(b, ev0, g_evn, NULL);
    jb_printf(b, "}");
}

static void progress_cb(void *user, uint32_t done, uint32_t total)
{
    struct cb_state *c = (struct cb_state *)user;
    (void)total;
    c->entries++;
    c->depth++;
    if (c->depth > c->max_depth) c->max_depth = c->depth;
    g_op_progress = done;
    if (c->probe_column >= 0 && !c->probe_done) {
        c->probe_done = true;
        jb_printf(c->out, "\"callback_before\":{\"operation\":");
        jb_opstate(c->out);
        jb_printf(c->out, ",\"callback_entry_count\":%u,\"callback_max_depth\":%u},\"nested_call\":",
                  c->entries, c->max_depth);
        column_probe(c->t, c->probe_column, c->out, c);
        jb_printf(c->out, ",\"callback_after\":{\"operation\":");
        jb_opstate(c->out);
        jb_printf(c->out, ",\"callback_entry_count\":%u,\"callback_max_depth\":%u}",
                  c->entries, c->max_depth);
    }
    c->depth--;
}

/* A second callback identity for the allowed-mutables continuation. */
static void progress_cb_b(void *user, uint32_t done, uint32_t total)
{
    progress_cb(user, done, total);
}

static void contract_reset(void)
{
    g_evn = 0u;
    g_logging = true;
    g_op_started = false;
    g_op_progress = 0u;
}

static tape *source_open(const unsigned char *img, bool writable, bool playing)
{
    tape *t = NULL;
    size_t need = tape_instance_size();
    bool more = true;
    unsigned guard = 0u;

    if (load_source_image(&g_src_ctx, img) != 0) return NULL;
    g_src_ctx.name = "source";
    g_src_dev.read = read_cb;
    g_src_dev.write = writable ? write_cb : NULL;
    g_src_dev.flush = writable ? flush_cb : noop_flush;
    g_src_dev.ctx = &g_src_ctx;
    g_src_dev.block_count = BLOCK_COUNT;
    memset(g_mem, 0, need);
    memset(g_play, 0, TAPE_PLAY_RING_MIN);
    memset(g_rec, 0, TAPE_REC_RING_MIN);
    if (tape_init(g_mem, need, &g_src_dev, g_play, TAPE_PLAY_RING_MIN,
                  g_rec, TAPE_REC_RING_MIN, &t) != TAPE_OK) return NULL;
    if (tape_mount(t, TAPE_SIDE_A, 0u, NULL) != TAPE_OK) return NULL;
    if (playing) {
        if (tape_set_rate(t, 65536) != TAPE_OK) return NULL;
        while (more && guard++ < 64u) {
            if (tape_service(t, 8u, &more) != TAPE_OK) return NULL;
        }
    }
    return t;
}

static void dest_open(struct dev_ctx *ctx, tape_dev *dev, const char *shape, const char *name)
{
    load_destination(ctx, shape_by_name(shape));
    ctx->name = name;
    dev->read = read_cb;
    dev->write = write_cb;
    dev->flush = flush_cb;
    dev->ctx = ctx;
    dev->block_count = BLOCK_COUNT;
}

/* Start a duplicate with budget 1 and advance it until the destination trace
   holds a chunk-region write, leaving work outstanding. */
static int dup_advance_to_copy(tape *t, struct cb_state *cbs)
{
    unsigned guard = 0u;
    bool more = false;
    for (;;) {
        unsigned i;
        bool have_chunk = false;
        tape_result r = dup_call(t, &g_dst_dev, k_dup_uuid, DUP_EPOCH, DUP_NOMINAL, 1u,
                                 &more, progress_cb, cbs);
        if (r != TAPE_OK || !more || ++guard > 64u) return -1;
        for (i = 0u; i < g_evn; ++i) {
            if (g_ev[i].op == 'w' && strcmp(g_ev[i].device, "destination") == 0
                && g_ev[i].lba >= LBA_CHUNK_BASE && g_ev[i].lba < LBA_MIRROR) have_chunk = true;
        }
        if (have_chunk) return 0;
    }
}

static void jb_continuation(struct jb *b, tape *t, struct cb_state *cbs)
{
    bool more = false;
    tape_result r;
    jb_printf(b, "{\"before\":");
    jb_opstate(b);
    r = dup_call(t, &g_dst_dev, k_dup_uuid, DUP_EPOCH, DUP_NOMINAL, 1u, &more, progress_cb, cbs);
    jb_printf(b, ",\"call\":{\"fn\":\"tape_dup\",\"result\":\"%s\",\"more_work\":%s},\"after\":",
              result_name(r), more ? "true" : "false");
    jb_opstate(b);
    jb_printf(b, "}");
}

static const char *transport_name(const tape *t)
{
    if (!t->mounted) return "NotMounted";
    if (t->faulted) return "FAULTED";
    if (t->rec_armed) return "Armed";
    if (t->dup_in_progress) return "DupInProgress";
    if (t->promote_in_progress) return "PromoteInProgress";
    return t->rate_q16_16 != 0 ? "Playing" : "MountedIdle";
}

/* Source facts for destination-failure-while-Playing. Position is public
   (tape_tell); the ring bytes are the caller's own play_ring; the rate, row
   and window indices are read from the instance without modifying it. */
static void jb_source_facts(struct jb *b, tape *t)
{
    uint64_t pos = 0u;
    uint32_t read_index = 0u;
    unsigned char digest[SHA256_DIGEST_LENGTH];
    (void)tape_tell(t, &pos);
    if ((uint64_t)t->position_frame >> 32 >= t->play_base) {
        read_index = (uint32_t)((t->position_frame >> 32) - t->play_base);
    }
    (void)SHA256((const unsigned char *)t->play_ring, (size_t)t->play_frames * 4u, digest);
    jb_printf(b, "{\"transport_state\":\"%s\",\"rate_q16_16\":%ld,\"position\":%llu,"
                 "\"raw_instance\":{\"mounted\":%s,\"faulted\":%s,\"rec_armed\":%s,"
                 "\"dup_in_progress\":%s,\"promote_in_progress\":%s,\"play_base\":%u},"
                 "\"ring\":{\"read_index\":%u,\"write_index\":%u,\"valid_frames\":%u,"
                 "\"content_sha256\":\"",
              transport_name(t), (long)t->rate_q16_16, (unsigned long long)pos,
              t->mounted ? "true" : "false", t->faulted ? "true" : "false",
              t->rec_armed ? "true" : "false", t->dup_in_progress ? "true" : "false",
              t->promote_in_progress ? "true" : "false", t->play_base,
              read_index, t->play_frames,
              t->play_frames >= read_index ? t->play_frames - read_index : 0u);
    jb_hex(b, digest, sizeof digest);
    jb_printf(b, "\"}}");
}

static int contract_refusal(struct jb *b, const char *variant)
{
    unsigned ev0;
    tape_result r;
    bool more = false;
    contract_reset();
    dest_open(&g_dst_ctx, &g_dst_dev, "equal_divergent", "destination");
    jb_printf(b, "\"variant\":\"%s\",", variant);
    if (strcmp(variant, "format_geometry") == 0) {
        static const uint8_t fmt_uuid[16] =
            {0xa0,0xa1,0xa2,0xa3,0xa4,0xa5,0xa6,0xa7,0xa8,0xa9,0xaa,0xab,0xac,0xad,0xae,0xaf};
        ev0 = g_evn;
        /* 60 s derives 21 chunks; the 6145-block device holds 4. */
        r = tape_format(&g_dst_dev, fmt_uuid, 0u, "", 60u);
        jb_printf(b, "\"call\":{\"fn\":\"tape_format\",\"result\":\"%s\",\"nominal_length_s\":60}", result_name(r));
    } else {
        bool cap = strcmp(variant, "dup_capacity") == 0;
        tape *t = source_open(cap ? g_source_big : g_source, false, false);
        if (t == NULL) return -1;
        ev0 = g_evn;
        /* geometry: 60 s cannot fit; capacity: 1 s derives one chunk and the
           large source's Side A needs two. */
        r = dup_call(t, &g_dst_dev, k_dup_uuid, DUP_EPOCH, cap ? 1u : 60u, 64u, &more, NULL, NULL);
        jb_printf(b, "\"call\":{\"fn\":\"tape_dup\",\"result\":\"%s\",\"more_work\":%s,"
                     "\"dst_nominal_length_s\":%u}",
                  result_name(r), more ? "true" : "false", cap ? 1u : 60u);
    }
    jb_printf(b, ",\"destination_events\":");
    jb_events(b, ev0, g_evn, "destination");
    return 0;
}

static int contract_row(struct jb *b, const char *column, bool in_callback)
{
    int col = column_index(column);
    struct cb_state cbs;
    tape *t;
    if (col < 0) return -1;
    contract_reset();
    memset(&cbs, 0, sizeof cbs);
    cbs.probe_column = -1;
    dest_open(&g_dst_ctx, &g_dst_dev, "healthy_pair", "destination");
    /* Only the render column needs a non-silent Playing source; every other
       column starts from Mounted, idle so BUSY is attributable to the
       duplicate rather than to the Playing row. */
    t = source_open(g_source, false, col == 2);
    if (t == NULL) return -1;
    cbs.t = t;
    if (dup_advance_to_copy(t, &cbs) != 0) return -1;
    jb_printf(b, "\"column\":\"%s\",", column);

    if (in_callback) {
        bool more = false;
        tape_result r;
        cbs.probe_column = col;
        cbs.out = b;
        r = dup_call(t, &g_dst_dev, k_dup_uuid, DUP_EPOCH, DUP_NOMINAL, 1u, &more, progress_cb, &cbs);
        if (!cbs.probe_done) return -1;
        jb_printf(b, ",\"carrier_call\":{\"fn\":\"tape_dup\",\"result\":\"%s\",\"more_work\":%s}",
                  result_name(r), more ? "true" : "false");
        cbs.probe_column = -1;
        jb_printf(b, ",\"next_continuation\":");
        jb_continuation(b, t, &cbs);
        return 0;
    }

    jb_printf(b, "\"before\":");
    jb_opstate(b);
    jb_printf(b, ",\"probe\":");
    column_probe(t, col, b, &cbs);
    jb_printf(b, ",\"after_probe\":");
    jb_opstate(b);
    if (col != 2 && col != 3 && col != 4 && col != 13) {
        jb_printf(b, ",\"next_continuation\":");
        jb_continuation(b, t, &cbs);
    }
    return 0;
}

static int contract_zero_budget(struct jb *b, const char *variant)
{
    struct cb_state cbs;
    tape *t;
    unsigned ev0;
    bool more = false;
    tape_result r;
    contract_reset();
    memset(&cbs, 0, sizeof cbs);
    cbs.probe_column = -1;
    dest_open(&g_dst_ctx, &g_dst_dev, "healthy_pair", "destination");
    t = source_open(g_source, false, false);
    if (t == NULL) return -1;
    if (strcmp(variant, "continuation") == 0 && dup_advance_to_copy(t, &cbs) != 0) return -1;
    jb_printf(b, "\"variant\":\"%s\",\"before\":", variant);
    jb_opstate(b);
    ev0 = g_evn;
    r = tape_dup(t, &g_dst_dev, k_dup_uuid, DUP_EPOCH, DUP_NOMINAL, 0u, &more, progress_cb, &cbs);
    jb_printf(b, ",\"call\":{\"fn\":\"tape_dup\",\"block_budget\":0,\"result\":\"%s\",\"more_work\":%s,"
                 "\"block_events\":", result_name(r), more ? "true" : "false");
    jb_events(b, ev0, g_evn, NULL);
    jb_printf(b, "},\"after\":");
    jb_opstate(b);
    return 0;
}

static void jb_args(struct jb *b, const char *ctx, const uint8_t *uuid, uint32_t epoch,
                    uint32_t nominal, uint32_t budget, const char *cb, const char *user)
{
    jb_printf(b, "{\"dst_ctx\":\"%s\",\"new_uuid\":\"", ctx);
    jb_hex(b, uuid, 16u);
    jb_printf(b, "\",\"epoch\":%u,\"dst_nominal_length_s\":%u,\"block_budget\":%u,"
                 "\"cb_token\":\"%s\",\"user_token\":\"%s\"}",
              epoch, nominal, budget, cb, user);
}

static int contract_changed_argument(struct jb *b, const char *argument)
{
    static const uint8_t zero_uuid[16] = {0};
    struct cb_state cbs, cbs_b;
    tape *t;
    unsigned ev0;
    bool more = false;
    tape_result r;
    const tape_dev *dst = &g_dst_dev;
    const char *ctx_label = "dst-A", *cb_label = "cb-A", *user_label = "user-A";
    const uint8_t *uuid = k_dup_uuid;
    uint32_t epoch = DUP_EPOCH, nominal = DUP_NOMINAL, budget = 1u;
    tape_progress_fn cb = progress_cb;
    void *user = &cbs;

    contract_reset();
    memset(&cbs, 0, sizeof cbs);
    memset(&cbs_b, 0, sizeof cbs_b);
    cbs.probe_column = -1;
    cbs_b.probe_column = -1;
    dest_open(&g_dst_ctx, &g_dst_dev, "healthy_pair", "destination");
    dest_open(&g_dst2_ctx, &g_dst2_dev, "healthy_pair", "destination_b");
    t = source_open(g_source, false, false);
    if (t == NULL) return -1;
    if (dup_advance_to_copy(t, &cbs) != 0) return -1;

    if (strcmp(argument, "dst_ctx") == 0) { dst = &g_dst2_dev; ctx_label = "dst-B"; }
    else if (strcmp(argument, "new_uuid") == 0) { uuid = zero_uuid; }
    else if (strcmp(argument, "epoch") == 0) { epoch = 1u; }
    else if (strcmp(argument, "dst_nominal_length_s") == 0) { nominal = 8u; }
    else if (strcmp(argument, "allowed_mutables") == 0) {
        budget = 2u; cb = progress_cb_b; user = &cbs_b; cb_label = "cb-B"; user_label = "user-B";
    } else return -1;

    jb_printf(b, "\"argument\":\"%s\",\"initial_args\":", argument);
    jb_args(b, "dst-A", k_dup_uuid, DUP_EPOCH, DUP_NOMINAL, 1u, "cb-A", "user-A");
    jb_printf(b, ",\"call_args\":");
    jb_args(b, ctx_label, uuid, epoch, nominal, budget, cb_label, user_label);
    jb_printf(b, ",\"before\":");
    jb_opstate(b);
    ev0 = g_evn;
    r = tape_dup(t, dst, uuid, epoch, nominal, budget, &more, cb, user);
    jb_printf(b, ",\"call\":{\"fn\":\"tape_dup\",\"result\":\"%s\",\"more_work\":%s,\"block_events\":",
              result_name(r), more ? "true" : "false");
    jb_events(b, ev0, g_evn, NULL);
    jb_printf(b, "},\"after\":");
    jb_opstate(b);
    return 0;
}

static int contract_destination_failure(struct jb *b)
{
    struct cb_state cbs;
    tape *t;
    unsigned ev0;
    bool more = false;
    tape_result r;
    int16_t warm[2u * 16u];
    uint32_t rendered = 0u;

    contract_reset();
    memset(&cbs, 0, sizeof cbs);
    cbs.probe_column = -1;
    dest_open(&g_dst_ctx, &g_dst_dev, "healthy_pair", "destination");
    t = source_open(g_source, false, true);
    if (t == NULL) return -1;
    /* Move the playhead off the window start so the ring read index is not 0. */
    if (tape_render(t, warm, 16u, &rendered) != TAPE_OK || rendered == 0u) return -1;
    /* Fail the destination's first chunk-region write (ordinal 6: two step-1
       superblocks, four slot zeros), after the source has been read. */
    g_dst_ctx.fail_write_ordinal = 6;

    jb_printf(b, "\"source_before\":");
    jb_source_facts(b, t);
    ev0 = g_evn;
    r = dup_call(t, &g_dst_dev, k_dup_uuid, DUP_EPOCH, DUP_NOMINAL, 65535u, &more, progress_cb, &cbs);
    jb_printf(b, ",\"call\":{\"fn\":\"tape_dup\",\"result\":\"%s\",\"more_work\":%s},\"destination_events\":",
              result_name(r), more ? "true" : "false");
    jb_events(b, ev0, g_evn, "destination");
    jb_printf(b, ",\"source_events\":");
    jb_events(b, ev0, g_evn, "source");
    jb_printf(b, ",\"source_after\":");
    jb_source_facts(b, t);
    jb_printf(b, ",\"render_after_failure\":");
    render_probe(t, b);
    return 0;
}

static int contract_faulted_source(struct jb *b)
{
    tape *t;
    unsigned ev0;
    bool more = false;
    tape_result setup, r;

    contract_reset();
    dest_open(&g_dst_ctx, &g_dst_dev, "healthy_pair", "destination");
    t = source_open(g_source, true, false);
    if (t == NULL) return -1;
    /* Public route to FAULTED (engine-api §7.2): a mutating call whose own
       device write fails. */
    g_src_ctx.fail_write_ordinal = (int)g_src_ctx.writes_seen;
    setup = tape_reset_side_b(t);
    jb_printf(b, "\"variant\":\"dup_call\",\"setup\":{\"fn\":\"tape_reset_side_b\",\"result\":\"%s\"},"
                 "\"source_state\":\"%s\"", result_name(setup), transport_name(t));
    ev0 = g_evn;
    r = dup_call(t, &g_dst_dev, k_dup_uuid, DUP_EPOCH, DUP_NOMINAL, 64u, &more, NULL, NULL);
    jb_printf(b, ",\"call\":{\"fn\":\"tape_dup\",\"result\":\"%s\",\"more_work\":%s,\"block_events\":",
              result_name(r), more ? "true" : "false");
    jb_events(b, ev0, g_evn, NULL);
    jb_printf(b, "}");
    return 0;
}

static void jb_lbas_since(struct jb *b)
{
    unsigned i;
    bool first = true;
    jb_printf(b, "[");
    for (i = 0u; i < g_evn; ++i) {
        const struct block_event *e = &g_ev[i];
        if (e->op != 'w' || e->rc != 0 || strcmp(e->device, "destination") != 0) continue;
        if (e->lba < LBA_CHUNK_BASE || e->lba >= LBA_MIRROR) continue;
        if (!first) jb_printf(b, ",");
        first = false;
        jb_printf(b, "%u", e->lba);
    }
    jb_printf(b, "]");
}

static int contract_small_budget(struct jb *b)
{
    struct cb_state cbs;
    tape *t;
    bool more = true;
    unsigned guard = 0u;
    bool first = true;

    contract_reset();
    memset(&cbs, 0, sizeof cbs);
    cbs.probe_column = -1;
    dest_open(&g_dst_ctx, &g_dst_dev, "healthy_pair", "destination");
    t = source_open(g_source, false, false);
    if (t == NULL) return -1;
    jb_printf(b, "\"variant\":\"dup\",\"call_sequence\":[");
    while (more && guard++ < 1000u) {
        uint32_t pb = g_op_progress;
        unsigned eb = dst_event_count();
        tape_result r;
        if (!first) jb_printf(b, ",");
        first = false;
        jb_printf(b, "{\"fn\":\"tape_dup\",\"block_budget\":1,\"operation_token\":\"dup-1\","
                     "\"progress_before\":%u,\"destination_event_count_before\":%u,"
                     "\"chunk_write_lbas_before\":", pb, eb);
        jb_lbas_since(b);
        more = false;
        r = dup_call(t, &g_dst_dev, k_dup_uuid, DUP_EPOCH, DUP_NOMINAL, 1u, &more, progress_cb, &cbs);
        jb_printf(b, ",\"result\":\"%s\",\"more_work\":%s,\"progress_after\":%u,"
                     "\"destination_event_count_after\":%u,\"chunk_write_lbas_after\":",
                  result_name(r), more ? "true" : "false", g_op_progress, dst_event_count());
        jb_lbas_since(b);
        jb_printf(b, "}");
        if (r != TAPE_OK) break;
    }
    jb_printf(b, "],\"terminal_snapshot\":");
    jb_snapshot(b, &g_dst_ctx.durable);
    return 0;
}

static int handle_contract(unsigned case_index, const char *family, const char *param)
{
    struct jb b;
    int rc;
    jb_init(&b, g_main_buf, sizeof g_main_buf);
    if (strcmp(family, "equal_divergent_refusal") == 0) rc = contract_refusal(&b, param);
    else if (strcmp(family, "dup_in_progress_row") == 0) rc = contract_row(&b, param, false);
    else if (strcmp(family, "callback_reentry") == 0) rc = contract_row(&b, param, true);
    else if (strcmp(family, "zero_budget") == 0) rc = contract_zero_budget(&b, param);
    else if (strcmp(family, "changed_argument") == 0) rc = contract_changed_argument(&b, param);
    else if (strcmp(family, "destination_failure_playing") == 0) rc = contract_destination_failure(&b);
    else if (strcmp(family, "faulted_source") == 0) rc = contract_faulted_source(&b);
    else if (strcmp(family, "small_budget_completion") == 0) rc = contract_small_budget(&b);
    else rc = -1;
    g_logging = false;
    if (rc != 0) {
        fprintf(stderr, "contract setup failed: case %u family %s param %s\n", case_index, family, param);
        return -1;
    }
    printf("{\"case_index\":%u,%s}\n", case_index, b.p);
    fflush(stdout);
    return 0;
}

int main(int argc, char **argv)
{
    static const char *names[7] = {
        "healthy_pair", "mirror_only", "generation_zero", "v2_only",
        "equal_divergent", "exhaustion_candidate", "exhaustion_equal_divergent"
    };
    char line[1024];
    unsigned i;
    if (argc != 10) {
        fprintf(stderr, "usage: worker SOURCE SOURCE_BIG SHAPE1 ... SHAPE7\n");
        return 2;
    }
    if (read_exact(argv[1], g_source, SOURCE_BYTES) != 0) return 2;
    if (read_exact(argv[2], g_source_big, SOURCE_BYTES) != 0) return 2;
    for (i = 0u; i < 7u; ++i) {
        g_shapes[i].name = names[i];
        if (read_exact(argv[i + 3u], g_shapes[i].raw, SHAPE_BYTES) != 0) return 2;
    }
    g_mem = calloc(1u, tape_instance_size());
    g_play = calloc(1u, TAPE_PLAY_RING_MIN);
    g_rec = calloc(1u, TAPE_REC_RING_MIN);
    if (g_mem == NULL || g_play == NULL || g_rec == NULL) return 2;

    while (fgets(line, sizeof line, stdin) != NULL) {
        char *save = NULL;
        char *cmd = strtok_r(line, "\t\r\n", &save);
        if (cmd == NULL) continue;
        if (strcmp(cmd, "D") == 0) return 0;
        if (strcmp(cmd, "B") == 0) {
            char *op = strtok_r(NULL, "\t\r\n", &save);
            char *shape = strtok_r(NULL, "\t\r\n", &save);
            if (op == NULL || shape == NULL || handle_baseline(op, shape) != 0) return 2;
        } else if (strcmp(cmd, "C") == 0) {
            char *idx = strtok_r(NULL, "\t\r\n", &save);
            char *op = strtok_r(NULL, "\t\r\n", &save);
            char *shape = strtok_r(NULL, "\t\r\n", &save);
            char *mode = strtok_r(NULL, "\t\r\n", &save);
            char *inj = strtok_r(NULL, "\t\r\n", &save);
            char *ord = strtok_r(NULL, "\t\r\n", &save);
            char *land = strtok_r(NULL, "\t\r\n", &save);
            if (idx == NULL || op == NULL || shape == NULL || mode == NULL
                || inj == NULL || ord == NULL || land == NULL) return 2;
            if (handle_case((unsigned)strtoul(idx, NULL, 10), op, shape, mode, inj,
                            (unsigned)strtoul(ord, NULL, 10),
                            (unsigned)strtoul(land, NULL, 10)) != 0) return 2;
        } else if (strcmp(cmd, "K") == 0) {
            char *idx = strtok_r(NULL, "\t\r\n", &save);
            char *family = strtok_r(NULL, "\t\r\n", &save);
            char *param = strtok_r(NULL, "\t\r\n", &save);
            if (idx == NULL || family == NULL || param == NULL) return 2;
            if (handle_contract((unsigned)strtoul(idx, NULL, 10), family, param) != 0) return 2;
        } else {
            return 2;
        }
    }
    return 2;
}
