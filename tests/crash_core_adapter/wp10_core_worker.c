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
#define SLOT_BLOCKS 128u
#define SLOT_BYTES (SLOT_BLOCKS * BLOCK)
#define CHUNK_BLOCKS 1024u
#define CHUNK_BYTES (CHUNK_BLOCKS * BLOCK)
#define LBA_PRIMARY 0u
#define LBA_A0 8u
#define LBA_A1 136u
#define LBA_B0 264u
#define LBA_B1 392u
#define LBA_CHUNK_BASE 2048u
#define TOTAL_CHUNKS 5u
#define MAX_INSTANCE 262144u
#define REC_RING_BYTES TAPE_REC_RING_MIN
#define PLAY_RING_BYTES TAPE_PLAY_RING_MIN
#define SERVICE_GUARD 100000u

enum inj_kind {
    INJ_NONE = 0,
    INJ_BEFORE_WRITE,
    INJ_TORN_WRITE,
    INJ_AFTER_WRITE,
    INJ_AT_FLUSH,
    INJ_BEFORE_PARTNER,
    INJ_TORN_PARTNER,
    INJ_AFTER_PARTNER
};

struct baseline_write {
    uint32_t lba;
    uint32_t count;
    unsigned char digest[SHA256_DIGEST_LENGTH];
};

struct baseline {
    struct baseline_write writes[2];
    unsigned write_count;
    unsigned flush_count;
    bool post_clear_reached;
    const char *post_clear_kind;
    bool post_clear_write_landed;
};

struct dev_ctx {
    unsigned char *durable;
    unsigned char *working;
    size_t len;
    uint32_t blocks;
    bool write_through;

    bool scope;
    bool baseline_mode;
    struct baseline baseline;
    bool stop_post_clear;

    enum inj_kind inj;
    unsigned target_ordinal;
    unsigned landed_bytes;
    unsigned write_seen;
    unsigned flush_seen;
    bool injection_fired;
    bool after_write_pending;

    bool setup_repair_fault;
    bool setup_repair_fault_fired;
};

struct snapshot {
    unsigned char image_sha[SHA256_DIGEST_LENGTH];
    unsigned char primary[BLOCK];
    unsigned char mirror[BLOCK];
    unsigned char slots[4][2u * BLOCK];
    unsigned char chunk_sha[TOTAL_CHUNKS][SHA256_DIGEST_LENGTH];
};

struct fixture {
    const char *name;
    unsigned char *bytes;
    size_t len;
};

static struct fixture g_fixtures[8];
static size_t g_len;
static uint32_t g_blocks;
static uint32_t g_mirror_lba;

static unsigned char *g_durable;
static unsigned char *g_working;
static struct dev_ctx g_devctx;
static tape_dev g_dev;

static unsigned char *g_instance;
static unsigned char *g_play;
static unsigned char *g_rec;
static int16_t g_zero_pcm[1 * TAPE_CHANNELS];

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

static void hex_bytes(const unsigned char *p, size_t n)
{
    static const char d[] = "0123456789abcdef";
    size_t i;
    for (i = 0u; i < n; i++) {
        putchar(d[(p[i] >> 4) & 15u]);
        putchar(d[p[i] & 15u]);
    }
}

static void hash_bytes(const unsigned char *p, size_t n,
                       unsigned char out[SHA256_DIGEST_LENGTH])
{
    (void)SHA256(p, n, out);
}

static int read_fixture(struct fixture *f, const char *name, const char *path)
{
    FILE *fp;
    long n;
    size_t got;

    fp = fopen(path, "rb");
    if (fp == NULL) {
        fprintf(stderr, "cannot open fixture %s\n", path);
        return -1;
    }
    if (fseek(fp, 0, SEEK_END) != 0) { fclose(fp); return -1; }
    n = ftell(fp);
    if (n <= 0 || fseek(fp, 0, SEEK_SET) != 0) { fclose(fp); return -1; }
    f->bytes = malloc((size_t)n);
    if (f->bytes == NULL) { fclose(fp); return -1; }
    got = fread(f->bytes, 1u, (size_t)n, fp);
    if (got != (size_t)n || fclose(fp) != 0) {
        free(f->bytes);
        f->bytes = NULL;
        return -1;
    }
    f->name = name;
    f->len = (size_t)n;
    return 0;
}

static struct fixture *fixture_by_name(const char *name)
{
    unsigned i;
    for (i = 0u; i < 8u; i++) {
        if (strcmp(g_fixtures[i].name, name) == 0) return &g_fixtures[i];
    }
    return NULL;
}

static int load_fixture(const char *name)
{
    struct fixture *f = fixture_by_name(name);
    if (f == NULL || f->len != g_len) return -1;
    memcpy(g_durable, f->bytes, g_len);
    memcpy(g_working, f->bytes, g_len);
    memset(&g_devctx, 0, sizeof g_devctx);
    g_devctx.durable = g_durable;
    g_devctx.working = g_working;
    g_devctx.len = g_len;
    g_devctx.blocks = g_blocks;
    return 0;
}

static bool range_ok(uint32_t lba, uint32_t count)
{
    uint64_t end = (uint64_t)lba + (uint64_t)count;
    return count > 0u && end <= (uint64_t)g_devctx.blocks;
}

static bool is_superblock_lba(uint32_t lba)
{
    return lba == LBA_PRIMARY || lba == g_mirror_lba;
}

static const char *write_class(uint32_t lba)
{
    if (lba >= LBA_CHUNK_BASE && lba < g_mirror_lba) return "chunk";
    if ((lba >= LBA_A0 && lba < LBA_A0 + 2u * SLOT_BLOCKS)
        || (lba >= LBA_B0 && lba < LBA_B0 + 2u * SLOT_BLOCKS)) return "index";
    if (is_superblock_lba(lba)) return "superblock";
    return "other";
}

static int dev_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    size_t off, n;
    (void)ctx;
    if (dst == NULL || !range_ok(lba, count)) return -1;
    off = (size_t)lba * BLOCK;
    n = (size_t)count * BLOCK;
    memcpy(dst, g_working + off, n);
    return 0;
}

static void full_write(uint32_t lba, uint32_t count, const unsigned char *src)
{
    size_t off = (size_t)lba * BLOCK;
    size_t n = (size_t)count * BLOCK;
    memcpy(g_working + off, src, n);
    if (g_devctx.write_through) memcpy(g_durable + off, src, n);
}

static int dev_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    unsigned ordinal;
    size_t off;
    (void)ctx;

    if (src == NULL || !range_ok(lba, count)) return -1;

    if (!g_devctx.scope && g_devctx.setup_repair_fault && is_superblock_lba(lba)) {
        g_devctx.setup_repair_fault_fired = true;
        return -1;
    }

    if (!g_devctx.scope) {
        full_write(lba, count, (const unsigned char *)src);
        return 0;
    }

    ordinal = g_devctx.write_seen++;

    if (g_devctx.stop_post_clear && ordinal >= 2u) {
        g_devctx.baseline.post_clear_reached = true;
        g_devctx.baseline.post_clear_kind = write_class(lba);
        g_devctx.baseline.post_clear_write_landed = false;
        return -1;
    }

    if (g_devctx.baseline_mode && ordinal < 2u) {
        struct baseline_write *w = &g_devctx.baseline.writes[ordinal];
        w->lba = lba;
        w->count = count;
        if (count == 1u) {
            hash_bytes((const unsigned char *)src, BLOCK, w->digest);
        } else {
            memset(w->digest, 0, sizeof w->digest);
        }
        g_devctx.baseline.write_count = ordinal + 1u;
    }

    if (!g_devctx.baseline_mode && ordinal == g_devctx.target_ordinal) {
        if (g_devctx.inj == INJ_BEFORE_WRITE || g_devctx.inj == INJ_BEFORE_PARTNER) {
            g_devctx.injection_fired = true;
            return -1;
        }
        if (g_devctx.inj == INJ_TORN_WRITE || g_devctx.inj == INJ_TORN_PARTNER) {
            if (count != 1u || g_devctx.landed_bytes == 0u
                || g_devctx.landed_bytes >= BLOCK) return -1;
            off = (size_t)lba * BLOCK;
            memcpy(g_working + off, src, g_devctx.landed_bytes);
            memcpy(g_durable + off, src, g_devctx.landed_bytes);
            g_devctx.injection_fired = true;
            return -1;
        }
        if (g_devctx.inj == INJ_AFTER_WRITE || g_devctx.inj == INJ_AFTER_PARTNER) {
            full_write(lba, count, (const unsigned char *)src);
            g_devctx.after_write_pending = true;
            return 0;
        }
    }

    full_write(lba, count, (const unsigned char *)src);
    return 0;
}

static int dev_flush(void *ctx)
{
    unsigned ordinal;
    (void)ctx;

    if (!g_devctx.scope) {
        memcpy(g_durable, g_working, g_len);
        return 0;
    }

    ordinal = g_devctx.flush_seen++;

    if (g_devctx.after_write_pending) {
        g_devctx.after_write_pending = false;
        g_devctx.injection_fired = true;
        return -1;
    }

    if (!g_devctx.baseline_mode && g_devctx.inj == INJ_AT_FLUSH
        && ordinal == g_devctx.target_ordinal) {
        g_devctx.injection_fired = true;
        return -1;
    }

    if (g_devctx.baseline_mode && ordinal < 2u) {
        g_devctx.baseline.flush_count = ordinal + 1u;
    }

    memcpy(g_durable, g_working, g_len);
    return 0;
}

static void init_dev(void)
{
    memset(&g_dev, 0, sizeof g_dev);
    g_dev.read = dev_read;
    g_dev.write = dev_write;
    g_dev.flush = dev_flush;
    g_dev.ctx = &g_devctx;
    g_dev.block_count = g_blocks;
}

static tape_result fresh_mount(tape_side side, tape **out)
{
    size_t need = tape_instance_size();
    tape_result r;
    if (need > MAX_INSTANCE) return TAPE_ERR_INVALID_ARG;
    memset(g_instance, 0, MAX_INSTANCE);
    memset(g_play, 0, PLAY_RING_BYTES);
    memset(g_rec, 0, REC_RING_BYTES);
    r = tape_init(g_instance, need, &g_dev,
                  g_play, PLAY_RING_BYTES, g_rec, REC_RING_BYTES, out);
    if (r != TAPE_OK) return r;
    return tape_mount(*out, side, 0u, NULL);
}

static tape_result fresh_remount_from_durable(tape_side side)
{
    tape *t = NULL;
    g_devctx.scope = false;
    g_devctx.setup_repair_fault = false;
    g_devctx.after_write_pending = false;
    memcpy(g_working, g_durable, g_len);
    return fresh_mount(side, &t);
}

static tape_result service_until_done(tape *t, uint32_t budget)
{
    uint32_t guard = 0u;
    bool more = true;
    tape_result r = TAPE_OK;
    while (more) {
        more = false;
        r = tape_service(t, budget, &more);
        if (r != TAPE_OK) return r;
        guard++;
        if (guard > SERVICE_GUARD) return TAPE_ERR_BUSY;
    }
    return r;
}

static tape_rec_mode parse_record_mode(const char *s)
{
    if (strcmp(s, "overwrite") == 0) return TAPE_REC_OVERWRITE;
    if (strcmp(s, "overdub") == 0) return TAPE_REC_OVERDUB;
    if (strcmp(s, "splice") == 0) return TAPE_REC_SPLICE;
    return TAPE_REC_OVERWRITE;
}

static int setup_record(const char *variant, tape **out)
{
    tape *t = NULL;
    tape_result r;
    uint32_t accepted = 0u;

    r = fresh_mount(TAPE_SIDE_B, &t);
    if (r != TAPE_OK) return -1;
    r = tape_seek(t, 0u);
    if (r != TAPE_OK) return -1;
    r = tape_arm(t, parse_record_mode(variant));
    if (r != TAPE_OK) return -1;
    r = tape_feed(t, g_zero_pcm, 1u, &accepted);
    if (r != TAPE_OK || accepted != 1u) return -1;
    r = service_until_done(t, 1024u);
    if (r != TAPE_OK) return -1;
    *out = t;
    return 0;
}

static int setup_reset(const char *variant, tape **out)
{
    tape *t = NULL;
    tape_side side = strcmp(variant, "degraded_equal") == 0 ? TAPE_SIDE_A : TAPE_SIDE_B;
    tape_result r = fresh_mount(side, &t);
    if (r != TAPE_OK) return -1;
    *out = t;
    return 0;
}

static int setup_stage(const char *seed, tape **out,
                       bool *setup_fault_fired, bool *needs_repair)
{
    tape *t = NULL;
    tape_result r;
    tape_info info;

    if (seed != NULL && strcmp(seed, "-") != 0) {
        g_devctx.setup_repair_fault = true;
    }
    r = fresh_mount(TAPE_SIDE_B, &t);
    if (setup_fault_fired != NULL) *setup_fault_fired = g_devctx.setup_repair_fault_fired;
    g_devctx.setup_repair_fault = false;
    if (r != TAPE_OK) return -1;
    if (tape_get_info(t, &info) != TAPE_OK) return -1;
    if (needs_repair != NULL) *needs_repair = info.needs_repair;
    *out = t;
    return 0;
}

static tape_result run_stage_caller(tape *t, const char *variant)
{
    tape_result r;
    if (strcmp(variant, "arm") == 0) {
        uint32_t accepted = 0u;
        r = tape_arm(t, TAPE_REC_OVERWRITE);
        if (r != TAPE_OK) return r;
        r = tape_feed(t, g_zero_pcm, 1u, &accepted);
        if (r != TAPE_OK || accepted != 1u) return r != TAPE_OK ? r : TAPE_ERR_IO;
        return service_until_done(t, 1024u);
    }
    if (strcmp(variant, "reset_b") == 0) {
        return tape_reset_side_b(t);
    }
    if (strcmp(variant, "respool") == 0) {
        bool more = false;
        return tape_respool(t, 65535u, &more);
    }
    return TAPE_ERR_INVALID_ARG;
}

static int fixture_name(char *out, size_t n,
                        const char *family, const char *variant, const char *seed)
{
    if (strcmp(family, "record_commit") == 0) {
        return snprintf(out, n, "record_commit") < (int)n ? 0 : -1;
    }
    if (strcmp(family, "reset_b") == 0) {
        if (strcmp(variant, "healthy") == 0)
            return snprintf(out, n, "reset_healthy") < (int)n ? 0 : -1;
        if (strcmp(variant, "degraded_equal") == 0)
            return snprintf(out, n, "reset_degraded_equal") < (int)n ? 0 : -1;
    }
    if (strcmp(family, "stage_clear") == 0) {
        if (seed != NULL && strcmp(seed, "-") != 0)
            return snprintf(out, n, "stage_%s", seed) < (int)n ? 0 : -1;
        return snprintf(out, n, "stage_healthy") < (int)n ? 0 : -1;
    }
    return -1;
}

static int prepare_case(const char *family, const char *variant, const char *seed,
                        tape **out, bool *setup_fault_fired, bool *needs_repair)
{
    char name[96];
    if (fixture_name(name, sizeof name, family, variant, seed) != 0) return -1;
    if (load_fixture(name) != 0) return -1;
    init_dev();

    if (strcmp(family, "record_commit") == 0) {
        return setup_record(variant, out);
    }
    if (strcmp(family, "reset_b") == 0) {
        return setup_reset(variant, out);
    }
    if (strcmp(family, "stage_clear") == 0) {
        return setup_stage(seed, out, setup_fault_fired, needs_repair);
    }
    return -1;
}

static void capture_snapshot(struct snapshot *s)
{
    uint32_t chunk;
    size_t off;

    hash_bytes(g_durable, g_len, s->image_sha);
    memcpy(s->primary, g_durable, BLOCK);
    memcpy(s->mirror, g_durable + (size_t)g_mirror_lba * BLOCK, BLOCK);
    memcpy(s->slots[0], g_durable + (size_t)LBA_A0 * BLOCK, 2u * BLOCK);
    memcpy(s->slots[1], g_durable + (size_t)LBA_A1 * BLOCK, 2u * BLOCK);
    memcpy(s->slots[2], g_durable + (size_t)LBA_B0 * BLOCK, 2u * BLOCK);
    memcpy(s->slots[3], g_durable + (size_t)LBA_B1 * BLOCK, 2u * BLOCK);
    for (chunk = 0u; chunk < TOTAL_CHUNKS; chunk++) {
        off = (size_t)(LBA_CHUNK_BASE + chunk * CHUNK_BLOCKS) * BLOCK;
        hash_bytes(g_durable + off, CHUNK_BYTES, s->chunk_sha[chunk]);
    }
}

static void emit_snapshot(const struct snapshot *s)
{
    unsigned i;
    fputs("{\"format\":\"WP10-CORE-SNAPSHOT-1\",\"image_sha256\":\"", stdout);
    hex_bytes(s->image_sha, sizeof s->image_sha);
    fputs("\",\"primary_hex\":\"", stdout);
    hex_bytes(s->primary, sizeof s->primary);
    fputs("\",\"mirror_hex\":\"", stdout);
    hex_bytes(s->mirror, sizeof s->mirror);
    fputs("\",\"slots\":{", stdout);
    for (i = 0u; i < 4u; i++) {
        static const char *names[] = {"A0","A1","B0","B1"};
        if (i != 0u) putchar(',');
        printf("\"%s\":\"", names[i]);
        hex_bytes(s->slots[i], sizeof s->slots[i]);
        putchar('"');
    }
    fputs("},\"chunk_sha256\":{", stdout);
    for (i = 0u; i < TOTAL_CHUNKS; i++) {
        if (i != 0u) putchar(',');
        printf("\"%u\":\"", i);
        hex_bytes(s->chunk_sha[i], SHA256_DIGEST_LENGTH);
        putchar('"');
    }
    fputs("}}", stdout);
}

static enum inj_kind parse_inj(const char *s)
{
    if (strcmp(s, "before_write") == 0) return INJ_BEFORE_WRITE;
    if (strcmp(s, "torn_write") == 0) return INJ_TORN_WRITE;
    if (strcmp(s, "after_write") == 0) return INJ_AFTER_WRITE;
    if (strcmp(s, "at_flush") == 0) return INJ_AT_FLUSH;
    if (strcmp(s, "before_partner") == 0) return INJ_BEFORE_PARTNER;
    if (strcmp(s, "torn_partner") == 0) return INJ_TORN_PARTNER;
    if (strcmp(s, "after_partner") == 0) return INJ_AFTER_PARTNER;
    return INJ_NONE;
}

static tape_result run_operation(tape *t, const char *family, const char *variant)
{
    if (strcmp(family, "record_commit") == 0) return tape_commit(t);
    if (strcmp(family, "reset_b") == 0) return tape_reset_side_b(t);
    if (strcmp(family, "stage_clear") == 0) return run_stage_caller(t, variant);
    return TAPE_ERR_INVALID_ARG;
}

static int compute_baseline(const char *family, const char *variant, const char *seed)
{
    tape *t = NULL;
    bool setup_fault = false, needs_repair = false;
    tape_result r;
    unsigned i;

    if (prepare_case(family, variant, seed, &t, &setup_fault, &needs_repair) != 0) return -1;

    g_devctx.scope = true;
    g_devctx.baseline_mode = true;
    g_devctx.stop_post_clear = strcmp(family, "stage_clear") == 0;
    g_devctx.write_seen = 0u;
    g_devctx.flush_seen = 0u;
    memset(&g_devctx.baseline, 0, sizeof g_devctx.baseline);
    r = run_operation(t, family, variant);
    (void)r;
    g_devctx.scope = false;

    fputs("{\"writes\":[", stdout);
    for (i = 0u; i < g_devctx.baseline.write_count; i++) {
        if (i != 0u) putchar(',');
        printf("{\"ordinal\":%u,\"lba\":%u,\"count\":%u,\"sha256\":\"",
               i, g_devctx.baseline.writes[i].lba, g_devctx.baseline.writes[i].count);
        hex_bytes(g_devctx.baseline.writes[i].digest, SHA256_DIGEST_LENGTH);
        fputs("\"}", stdout);
    }
    fputs("],\"flushes\":[", stdout);
    for (i = 0u; i < g_devctx.baseline.flush_count; i++) {
        if (i != 0u) putchar(',');
        printf("{\"ordinal\":%u}", i);
    }
    putchar(']');
    if (strcmp(family, "stage_clear") == 0) {
        printf(",\"post_clear_reached\":%s,\"post_clear_next_kind\":\"%s\","
               "\"post_clear_write_landed\":%s",
               g_devctx.baseline.post_clear_reached ? "true" : "false",
               g_devctx.baseline.post_clear_kind != NULL ? g_devctx.baseline.post_clear_kind : "none",
               g_devctx.baseline.post_clear_write_landed ? "true" : "false");
    }
    fputs("}\n", stdout);
    fflush(stdout);
    return 0;
}

static int run_injected(unsigned long case_index,
                        const char *scope, const char *family, const char *variant,
                        const char *mode, const char *kind,
                        unsigned ordinal, unsigned landed, const char *seed)
{
    tape *t = NULL;
    bool setup_fault = false, needs_repair = false;
    struct snapshot pre, post;
    tape_result operation_result, remount_result;
    tape_side remount_side;
    enum inj_kind inj = parse_inj(kind);

    if (prepare_case(family, variant, seed, &t, &setup_fault, &needs_repair) != 0) return -1;
    capture_snapshot(&pre);

    g_devctx.write_through = strcmp(mode, "write_through") == 0;
    g_devctx.scope = true;
    g_devctx.baseline_mode = false;
    g_devctx.stop_post_clear = false;
    g_devctx.inj = inj;
    g_devctx.target_ordinal = ordinal;
    g_devctx.landed_bytes = landed;
    g_devctx.write_seen = 0u;
    g_devctx.flush_seen = 0u;
    g_devctx.injection_fired = false;
    g_devctx.after_write_pending = false;

    operation_result = run_operation(t, family, variant);
    (void)operation_result;
    g_devctx.scope = false;

    capture_snapshot(&post);

    remount_side = (strcmp(family, "reset_b") == 0
                    && strcmp(variant, "degraded_equal") == 0)
                 ? TAPE_SIDE_A : TAPE_SIDE_B;
    remount_result = fresh_remount_from_durable(remount_side);

    printf("{\"format\":\"WP10-CORE-OBSERVATION-1\","
           "\"case_index\":%lu,\"scope\":\"%s\",\"family\":\"%s\","
           "\"variant\":\"%s\",\"mode\":\"%s\",",
           case_index, scope, family, variant, mode);
    if (seed != NULL && strcmp(seed, "-") != 0) {
        printf("\"seed\":\"%s\","
               "\"setup_mount_result\":\"TAPE_OK\","
               "\"setup_needs_repair\":%s,"
               "\"setup_repair_fault_fired\":%s,",
               seed,
               needs_repair ? "true" : "false",
               setup_fault ? "true" : "false");
    }
    fputs("\"pre_snapshot\":", stdout);
    emit_snapshot(&pre);
    fputs(",\"post_snapshot\":", stdout);
    emit_snapshot(&post);
    printf(",\"injection_fired\":%s,\"fired_at\":{",
           g_devctx.injection_fired ? "true" : "false");
    if (inj == INJ_AT_FLUSH) {
        printf("\"kind\":\"%s\",\"flush_ordinal\":%u", kind, ordinal);
    } else {
        printf("\"kind\":\"%s\",\"write_ordinal\":%u,\"landed_bytes\":%u",
               kind, ordinal, landed);
    }
    printf("},\"remount_side\":\"%s\",\"actual_remount_result\":\"%s\"}\n",
           remount_side == TAPE_SIDE_A ? "A" : "B",
           result_name(remount_result));
    fflush(stdout);
    return 0;
}

static int split_tabs(char *line, char **fields, int max_fields)
{
    int n = 0;
    char *p = line;
    while (n < max_fields) {
        char *tab;
        fields[n++] = p;
        tab = strchr(p, '\t');
        if (tab == NULL) break;
        *tab = '\0';
        p = tab + 1;
    }
    if (n > 0) {
        char *nl = strchr(fields[n - 1], '\n');
        if (nl != NULL) *nl = '\0';
    }
    return n;
}

int main(int argc, char **argv)
{
    static const char *names[8] = {
        "record_commit",
        "reset_healthy",
        "reset_degraded_equal",
        "stage_healthy",
        "stage_primary_only",
        "stage_mirror_only",
        "stage_primary_newer_mirror_stale",
        "stage_mirror_newer_primary_stale"
    };
    char line[1024];
    unsigned i;

    if (argc != 9) {
        fprintf(stderr, "usage: worker RECORD RESET_H RESET_D STAGE PONLY MONLY PN MS\n");
        return 2;
    }
    for (i = 0u; i < 8u; i++) {
        if (read_fixture(&g_fixtures[i], names[i], argv[i + 1]) != 0) return 2;
        if (i == 0u) g_len = g_fixtures[i].len;
        if (g_fixtures[i].len != g_len || g_len % BLOCK != 0u) return 2;
    }

    g_blocks = (uint32_t)(g_len / BLOCK);
    g_mirror_lba = g_blocks - 1u;
    g_durable = malloc(g_len);
    g_working = malloc(g_len);
    g_instance = malloc(MAX_INSTANCE);
    g_play = malloc(PLAY_RING_BYTES);
    g_rec = malloc(REC_RING_BYTES);
    if (g_durable == NULL || g_working == NULL || g_instance == NULL
        || g_play == NULL || g_rec == NULL) return 2;

    while (fgets(line, sizeof line, stdin) != NULL) {
        char *f[12];
        int n = split_tabs(line, f, 12);
        if (n <= 0) continue;
        if (strcmp(f[0], "D") == 0) break;
        if (strcmp(f[0], "B") == 0) {
            if (n != 4 || compute_baseline(f[1], f[2], f[3]) != 0) return 2;
            continue;
        }
        if (strcmp(f[0], "C") == 0) {
            unsigned long idx;
            unsigned ord, landed;
            if (n != 10) return 2;
            idx = strtoul(f[1], NULL, 10);
            ord = (unsigned)strtoul(f[7], NULL, 10);
            landed = (unsigned)strtoul(f[8], NULL, 10);
            if (run_injected(idx, f[2], f[3], f[4], f[5], f[6],
                             ord, landed, f[9]) != 0) return 2;
            continue;
        }
        return 2;
    }

    return 0;
}
