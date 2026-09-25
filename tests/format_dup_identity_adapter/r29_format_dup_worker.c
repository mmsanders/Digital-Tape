#define _POSIX_C_SOURCE 200809L
#ifndef TAPE_PUBLIC_HEADER
#define TAPE_PUBLIC_HEADER "tape.h"
#endif
#include TAPE_PUBLIC_HEADER

#include <openssl/sha.h>
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
};

struct fixture {
    const char *name;
    unsigned char raw[SHAPE_BYTES];
};

static struct fixture g_shapes[7];
static unsigned char g_source[SOURCE_BYTES];

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
    if (dst == NULL || count == 0u || (uint64_t)lba + count > BLOCK_COUNT) return -1;
    for (i = 0u; i < count; ++i) get_block(&ctx->working, lba + i, out + (size_t)i * BLOCK);
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

static int write_cb(void *v, uint32_t lba, uint32_t count, const void *srcv)
{
    struct dev_ctx *ctx = (struct dev_ctx *)v;
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

static int flush_cb(void *v)
{
    struct dev_ctx *ctx = (struct dev_ctx *)v;
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
    (void)v;
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

static int load_source(struct dev_ctx *ctx)
{
    memset(ctx, 0, sizeof *ctx);
    if (set_block(&ctx->working, LBA_PRIMARY, g_source) != 0
        || set_block(&ctx->working, LBA_MIRROR, g_source + BLOCK) != 0
        || set_block(&ctx->working, LBA_A0, g_source + 2u * BLOCK) != 0
        || set_block(&ctx->working, LBA_A0 + 1u, g_source + 3u * BLOCK) != 0
        || set_block(&ctx->working, LBA_B0, g_source + 4u * BLOCK) != 0
        || set_block(&ctx->working, LBA_CHUNK_BASE, g_source + 5u * BLOCK) != 0) return -1;
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
        return tape_format(&dd, fmt_uuid, 7u, "", 60u);
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
        if (load_source(&src) != 0) return TAPE_ERR_IO;
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
                r = tape_dup(t, &dd, dup_uuid, 7u, 60u, 65535u, &more, NULL, NULL);
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
    printf("{\"format\":\"FMTDUP-ID-RAW-1\",\"primary_hex\":\"");
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

int main(int argc, char **argv)
{
    static const char *names[7] = {
        "healthy_pair", "mirror_only", "generation_zero", "v2_only",
        "equal_divergent", "exhaustion_candidate", "exhaustion_equal_divergent"
    };
    char line[1024];
    unsigned i;
    if (argc != 9) {
        fprintf(stderr, "usage: worker SOURCE SHAPE1 ... SHAPE7\n");
        return 2;
    }
    if (read_exact(argv[1], g_source, SOURCE_BYTES) != 0) return 2;
    for (i = 0u; i < 7u; ++i) {
        g_shapes[i].name = names[i];
        if (read_exact(argv[i + 2u], g_shapes[i].raw, SHAPE_BYTES) != 0) return 2;
    }

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
        } else {
            return 2;
        }
    }
    return 2;
}
