/*
 * Mechanical product adapter for tests/format_dup_draft8.
 *
 * It observes only the independently published 17-case zero-write tranche.
 * Setup/teardown mount callbacks are excluded; every callback made by the
 * operation under test is retained, including rejected/out-of-range calls.
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "tape.h"

#define VO08_SIZE (8u + 2u * TAPE_BLOCK_SIZE + 4u * TAPE_INDEX_SLOT_BYTES)
#define SLOT_BLOCKS (TAPE_INDEX_SLOT_BYTES / TAPE_BLOCK_SIZE)
#define MAX_EVENTS 4096u
#define MAX_CALLS 8u
#define ADAPTER_ID "p1-r25-format-dup-product-v1"

struct event_rec {
    const char *phase;
    const char *device;
    const char *op;
    uint32_t lba;
    uint32_t count;
    bool has_extent;
};

struct call_rec {
    const char *phase;
    const char *fn;
    tape_result result;
    bool has_side;
    tape_side side;
    bool has_more;
    bool more;
    bool has_alias;
    bool aliased;
};

struct media_ctx {
    unsigned char *bytes;
    uint32_t physical_blocks;
    uint32_t advertised_blocks;
    const char *name;
    bool trace;
};

struct case_cfg {
    enum { CASE_FORMAT, CASE_DUP, CASE_PROMOTE } kind;
    uint32_t dest_blocks;
    uint32_t dest_nominal;
    bool dest_writable;
    bool aliases;
};

static struct event_rec g_events[MAX_EVENTS];
static size_t g_event_count;
static bool g_event_overflow;
static struct call_rec g_calls[MAX_CALLS];
static size_t g_call_count;
static const char *g_phase = "setup";

static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0]
         | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16)
         | ((uint32_t)p[3] << 24);
}

static void wr32(unsigned char *p, uint32_t v)
{
    p[0] = (unsigned char)(v & 0xffu);
    p[1] = (unsigned char)((v >> 8) & 0xffu);
    p[2] = (unsigned char)((v >> 16) & 0xffu);
    p[3] = (unsigned char)((v >> 24) & 0xffu);
}

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
    }
    return "TAPE_ERR_UNKNOWN";
}

static const char *side_name(tape_side s)
{
    return s == TAPE_SIDE_A ? "A" : "B";
}

static void reset_trace(void)
{
    g_event_count = 0u;
    g_event_overflow = false;
}

static void push_event(struct media_ctx *m, const char *op,
                       uint32_t lba, uint32_t count, bool extent)
{
    struct event_rec *e;
    if (!m->trace) { return; }
    if (g_event_count >= MAX_EVENTS) {
        g_event_overflow = true;
        return;
    }
    e = &g_events[g_event_count++];
    e->phase = g_phase;
    e->device = m->name;
    e->op = op;
    e->lba = lba;
    e->count = count;
    e->has_extent = extent;
}

static int media_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    struct media_ctx *m = ctx;
    uint64_t end = (uint64_t)lba + (uint64_t)count;

    push_event(m, "read", lba, count, true);
    if (count == 0u
        || end > (uint64_t)m->advertised_blocks
        || end > (uint64_t)m->physical_blocks) {
        return -1;
    }
    memcpy(dst, m->bytes + (size_t)lba * TAPE_BLOCK_SIZE,
           (size_t)count * TAPE_BLOCK_SIZE);
    return 0;
}

static int media_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    struct media_ctx *m = ctx;
    uint64_t end = (uint64_t)lba + (uint64_t)count;

    push_event(m, "write", lba, count, true);
    if (count == 0u
        || end > (uint64_t)m->advertised_blocks
        || end > (uint64_t)m->physical_blocks) {
        return -1;
    }
    memcpy(m->bytes + (size_t)lba * TAPE_BLOCK_SIZE, src,
           (size_t)count * TAPE_BLOCK_SIZE);
    return 0;
}

static int media_flush(void *ctx)
{
    struct media_ctx *m = ctx;
    push_event(m, "flush", 0u, 0u, false);
    return 0;
}

static struct call_rec *push_call(const char *phase, const char *fn, tape_result r)
{
    struct call_rec *c;
    if (g_call_count >= MAX_CALLS) { return NULL; }
    c = &g_calls[g_call_count++];
    memset(c, 0, sizeof *c);
    c->phase = phase;
    c->fn = fn;
    c->result = r;
    return c;
}

static int read_file(const char *path, unsigned char **out, size_t *out_len)
{
    FILE *f;
    long n;
    unsigned char *b;

    f = fopen(path, "rb");
    if (f == NULL) { return -1; }
    if (fseek(f, 0L, SEEK_END) != 0) { fclose(f); return -1; }
    n = ftell(f);
    if (n < 0L) { fclose(f); return -1; }
    if (fseek(f, 0L, SEEK_SET) != 0) { fclose(f); return -1; }
    b = malloc((size_t)n);
    if (b == NULL) { fclose(f); return -1; }
    if (fread(b, 1u, (size_t)n, f) != (size_t)n) {
        free(b); fclose(f); return -1;
    }
    if (fclose(f) != 0) { free(b); return -1; }
    *out = b;
    *out_len = (size_t)n;
    return 0;
}

static int load_vo08(const char *path, struct media_ctx *m, const char *name)
{
    unsigned char *vo = NULL;
    size_t n = 0u;
    size_t p = 8u;
    uint64_t bytes;

    memset(m, 0, sizeof *m);
    if (read_file(path, &vo, &n) != 0) { return -1; }
    if (n != VO08_SIZE || memcmp(vo, "VO08", 4u) != 0) {
        free(vo); return -1;
    }

    m->physical_blocks = rd32(vo + 4u);
    m->advertised_blocks = m->physical_blocks;
    m->name = name;
    bytes = (uint64_t)m->physical_blocks * (uint64_t)TAPE_BLOCK_SIZE;
    if (m->physical_blocks <= TAPE_LBA_CHUNK_BASE || bytes > (uint64_t)SIZE_MAX) {
        free(vo); return -1;
    }
    m->bytes = calloc(1u, (size_t)bytes);
    if (m->bytes == NULL) { free(vo); return -1; }

    memcpy(m->bytes, vo + p, TAPE_BLOCK_SIZE);
    p += TAPE_BLOCK_SIZE;
    memcpy(m->bytes + (size_t)(m->physical_blocks - 1u) * TAPE_BLOCK_SIZE,
           vo + p, TAPE_BLOCK_SIZE);
    p += TAPE_BLOCK_SIZE;
    memcpy(m->bytes + (size_t)TAPE_LBA_INDEX_A0 * TAPE_BLOCK_SIZE,
           vo + p, TAPE_INDEX_SLOT_BYTES);
    p += TAPE_INDEX_SLOT_BYTES;
    memcpy(m->bytes + (size_t)TAPE_LBA_INDEX_A1 * TAPE_BLOCK_SIZE,
           vo + p, TAPE_INDEX_SLOT_BYTES);
    p += TAPE_INDEX_SLOT_BYTES;
    memcpy(m->bytes + (size_t)TAPE_LBA_INDEX_B0 * TAPE_BLOCK_SIZE,
           vo + p, TAPE_INDEX_SLOT_BYTES);
    p += TAPE_INDEX_SLOT_BYTES;
    memcpy(m->bytes + (size_t)TAPE_LBA_INDEX_B1 * TAPE_BLOCK_SIZE,
           vo + p, TAPE_INDEX_SLOT_BYTES);
    free(vo);
    return 0;
}

static int clone_media(const struct media_ctx *src, struct media_ctx *dst,
                       const char *name)
{
    size_t bytes = (size_t)src->physical_blocks * TAPE_BLOCK_SIZE;
    memset(dst, 0, sizeof *dst);
    dst->bytes = malloc(bytes);
    if (dst->bytes == NULL) { return -1; }
    memcpy(dst->bytes, src->bytes, bytes);
    dst->physical_blocks = src->physical_blocks;
    dst->advertised_blocks = src->physical_blocks;
    dst->name = name;
    return 0;
}

static int store_vo08(const char *path, const struct media_ctx *m)
{
    unsigned char *vo;
    FILE *f;
    size_t p = 8u;

    vo = malloc(VO08_SIZE);
    if (vo == NULL) { return -1; }
    memcpy(vo, "VO08", 4u);
    wr32(vo + 4u, m->physical_blocks);
    memcpy(vo + p, m->bytes, TAPE_BLOCK_SIZE);
    p += TAPE_BLOCK_SIZE;
    memcpy(vo + p,
           m->bytes + (size_t)(m->physical_blocks - 1u) * TAPE_BLOCK_SIZE,
           TAPE_BLOCK_SIZE);
    p += TAPE_BLOCK_SIZE;
    memcpy(vo + p, m->bytes + (size_t)TAPE_LBA_INDEX_A0 * TAPE_BLOCK_SIZE,
           TAPE_INDEX_SLOT_BYTES);
    p += TAPE_INDEX_SLOT_BYTES;
    memcpy(vo + p, m->bytes + (size_t)TAPE_LBA_INDEX_A1 * TAPE_BLOCK_SIZE,
           TAPE_INDEX_SLOT_BYTES);
    p += TAPE_INDEX_SLOT_BYTES;
    memcpy(vo + p, m->bytes + (size_t)TAPE_LBA_INDEX_B0 * TAPE_BLOCK_SIZE,
           TAPE_INDEX_SLOT_BYTES);
    p += TAPE_INDEX_SLOT_BYTES;
    memcpy(vo + p, m->bytes + (size_t)TAPE_LBA_INDEX_B1 * TAPE_BLOCK_SIZE,
           TAPE_INDEX_SLOT_BYTES);

    f = fopen(path, "wb");
    if (f == NULL) { free(vo); return -1; }
    if (fwrite(vo, 1u, VO08_SIZE, f) != VO08_SIZE) {
        free(vo); fclose(f); return -1;
    }
    free(vo);
    return fclose(f) == 0 ? 0 : -1;
}

static uint32_t min_blocks(uint32_t nominal)
{
    uint64_t frames = (uint64_t)nominal * (uint64_t)TAPE_SAMPLE_RATE;
    uint64_t chunks = (frames + (uint64_t)TAPE_CHUNK_FRAMES - 1u)
                    / (uint64_t)TAPE_CHUNK_FRAMES;
    uint64_t blocks = (uint64_t)TAPE_LBA_CHUNK_BASE
                    + chunks * (uint64_t)TAPE_CHUNK_BLOCKS + 1u;
    return (uint32_t)blocks;
}

static int case_config(const char *id, uint32_t physical_blocks, struct case_cfg *c)
{
    uint32_t fit_minus_one = min_blocks(60u) - 1u;
    memset(c, 0, sizeof *c);

    if (strcmp(id, "FMT-RO") == 0) {
        c->kind = CASE_FORMAT; c->dest_blocks = physical_blocks;
        c->dest_nominal = 60u; c->dest_writable = false; return 0;
    }
    if (strcmp(id, "FMT-GEOM-0") == 0) {
        c->kind = CASE_FORMAT; c->dest_blocks = 0u;
        c->dest_nominal = 60u; c->dest_writable = true; return 0;
    }
    if (strcmp(id, "FMT-GEOM-1") == 0) {
        c->kind = CASE_FORMAT; c->dest_blocks = 1u;
        c->dest_nominal = 60u; c->dest_writable = true; return 0;
    }
    if (strcmp(id, "FMT-GEOM-BASE") == 0) {
        c->kind = CASE_FORMAT; c->dest_blocks = TAPE_LBA_CHUNK_BASE;
        c->dest_nominal = 60u; c->dest_writable = true; return 0;
    }
    if (strcmp(id, "FMT-GEOM-FIT") == 0) {
        c->kind = CASE_FORMAT; c->dest_blocks = fit_minus_one;
        c->dest_nominal = 60u; c->dest_writable = true; return 0;
    }
    if (strcmp(id, "FMT-ORDER-RO") == 0) {
        c->kind = CASE_FORMAT; c->dest_blocks = 0u;
        c->dest_nominal = 60u; c->dest_writable = false; return 0;
    }

    if (strcmp(id, "DUP-ALIAS") == 0) {
        c->kind = CASE_DUP; c->dest_blocks = physical_blocks;
        c->dest_nominal = 60u; c->dest_writable = true; c->aliases = true; return 0;
    }
    if (strcmp(id, "DUP-RO") == 0) {
        c->kind = CASE_DUP; c->dest_blocks = physical_blocks;
        c->dest_nominal = 60u; c->dest_writable = false; return 0;
    }
    if (strcmp(id, "DUP-GEOM-0") == 0) {
        c->kind = CASE_DUP; c->dest_blocks = 0u;
        c->dest_nominal = 60u; c->dest_writable = true; return 0;
    }
    if (strcmp(id, "DUP-GEOM-1") == 0) {
        c->kind = CASE_DUP; c->dest_blocks = 1u;
        c->dest_nominal = 60u; c->dest_writable = true; return 0;
    }
    if (strcmp(id, "DUP-GEOM-BASE") == 0) {
        c->kind = CASE_DUP; c->dest_blocks = TAPE_LBA_CHUNK_BASE;
        c->dest_nominal = 60u; c->dest_writable = true; return 0;
    }
    if (strcmp(id, "DUP-GEOM-FIT") == 0) {
        c->kind = CASE_DUP; c->dest_blocks = fit_minus_one;
        c->dest_nominal = 60u; c->dest_writable = true; return 0;
    }
    if (strcmp(id, "DUP-TOO-SMALL") == 0) {
        c->kind = CASE_DUP;
        c->dest_blocks = TAPE_LBA_CHUNK_BASE + TAPE_CHUNK_BLOCKS + 2u;
        c->dest_nominal = 1u; c->dest_writable = true; return 0;
    }
    if (strcmp(id, "DUP-ORDER-ALIAS") == 0) {
        c->kind = CASE_DUP; c->dest_blocks = 0u;
        c->dest_nominal = 1u; c->dest_writable = false; c->aliases = true; return 0;
    }
    if (strcmp(id, "DUP-ORDER-RO") == 0) {
        c->kind = CASE_DUP; c->dest_blocks = TAPE_LBA_CHUNK_BASE;
        c->dest_nominal = 1u; c->dest_writable = false; return 0;
    }
    if (strcmp(id, "DUP-ORDER-GEOM") == 0) {
        c->kind = CASE_DUP; c->dest_blocks = TAPE_LBA_CHUNK_BASE;
        c->dest_nominal = 1u; c->dest_writable = true; return 0;
    }
    if (strcmp(id, "PROMOTE-EMPTY") == 0) {
        c->kind = CASE_PROMOTE; c->dest_blocks = physical_blocks;
        c->dest_nominal = 60u; c->dest_writable = true; return 0;
    }
    return -1;
}

static int init_tape(struct media_ctx *m, bool writable, tape_side side,
                     tape **out, void **inst, void **play, void **rec)
{
    tape_dev d;
    tape_result rc;

    *inst = calloc(1u, tape_instance_size());
    *play = calloc(1u, TAPE_PLAY_RING_MIN);
    *rec = calloc(1u, TAPE_REC_RING_MIN);
    if (*inst == NULL || *play == NULL || *rec == NULL) { return -1; }

    d.read = media_read;
    d.write = writable ? media_write : NULL;
    d.flush = media_flush;
    d.ctx = m;
    d.block_count = m->physical_blocks;

    rc = tape_init(*inst, tape_instance_size(), &d,
                   *play, TAPE_PLAY_RING_MIN, *rec, TAPE_REC_RING_MIN, out);
    if (rc != TAPE_OK) { return -1; }
    rc = tape_mount(*out, side, 0u, NULL);
    {
        struct call_rec *c = push_call("mount", "tape_mount", rc);
        if (c != NULL) { c->has_side = true; c->side = side; }
    }
    return rc == TAPE_OK ? 0 : -1;
}

static int run_format(const struct case_cfg *cfg, struct media_ctx *dst)
{
    tape_dev d;
    uint8_t uuid[16] = {0};
    tape_result rc;

    d.read = media_read;
    d.write = cfg->dest_writable ? media_write : NULL;
    d.flush = media_flush;
    d.ctx = dst;
    d.block_count = cfg->dest_blocks;
    dst->advertised_blocks = cfg->dest_blocks;
    dst->trace = true;
    g_phase = "format";
    rc = tape_format(&d, uuid, 1u, "fixture", cfg->dest_nominal);
    dst->trace = false;
    (void)push_call("format", "tape_format", rc);
    return 0;
}

static int run_dup(const struct case_cfg *cfg, struct media_ctx *src,
                   struct media_ctx *dst)
{
    tape *t = NULL;
    void *inst = NULL, *play = NULL, *rec = NULL;
    tape_dev d;
    uint8_t uuid[16] = {1u};
    bool more = false;
    tape_result rc;
    struct call_rec *c;
    struct media_ctx *target = cfg->aliases ? src : dst;

    /* Alias rows need a writable source device so item 1, not item 2, wins. */
    if (init_tape(src, cfg->aliases, TAPE_SIDE_A, &t, &inst, &play, &rec) != 0) {
        free(rec); free(play); free(inst); return -1;
    }

    d.read = media_read;
    d.write = cfg->dest_writable ? media_write : NULL;
    d.flush = media_flush;
    d.ctx = target;
    d.block_count = cfg->dest_blocks;

    target->advertised_blocks = cfg->dest_blocks;
    target->name = "destination";
    src->trace = true;
    target->trace = true;
    g_phase = "dup";
    rc = tape_dup(t, &d, uuid, 1u, cfg->dest_nominal, 64u, &more, NULL, NULL);
    src->trace = false;
    target->trace = false;

    c = push_call("dup", "tape_dup", rc);
    if (c != NULL) {
        c->has_more = true; c->more = more;
        c->has_alias = true; c->aliased = cfg->aliases;
    }

    /* Teardown is outside events. Restore source view before unmount. */
    src->advertised_blocks = src->physical_blocks;
    src->name = "source";
    rc = tape_unmount(t, NULL);
    (void)push_call("unmount", "tape_unmount", rc);

    free(rec); free(play); free(inst);
    return rc == TAPE_OK ? 0 : -1;
}

static int run_promote(struct media_ctx *src)
{
    tape *t = NULL;
    void *inst = NULL, *play = NULL, *rec = NULL;
    bool more = false;
    tape_result rc;
    struct call_rec *c;

    if (init_tape(src, true, TAPE_SIDE_B, &t, &inst, &play, &rec) != 0) {
        free(rec); free(play); free(inst); return -1;
    }

    src->name = "source";
    src->trace = true;
    g_phase = "promote";
    rc = tape_promote(t, 64u, &more, NULL, NULL);
    src->trace = false;
    c = push_call("promote", "tape_promote", rc);
    if (c != NULL) { c->has_more = true; c->more = more; }

    rc = tape_unmount(t, NULL);
    (void)push_call("unmount", "tape_unmount", rc);
    free(rec); free(play); free(inst);
    return rc == TAPE_OK ? 0 : -1;
}

static void emit_json(const char *id)
{
    size_t i;
    printf("{\"format\":\"WP-FMTDUP-OBSERVATION-1\",");
    printf("\"case_id\":\"%s\",\"adapter_kind\":\"product\",", id);
    printf("\"adapter_id\":\"%s\",\"calls\":[", ADAPTER_ID);

    for (i = 0u; i < g_call_count; i++) {
        const struct call_rec *c = &g_calls[i];
        if (i != 0u) { putchar(','); }
        printf("{\"phase\":\"%s\",\"fn\":\"%s\",\"result\":\"%s\"",
               c->phase, c->fn, result_name(c->result));
        if (c->has_side) {
            printf(",\"side\":\"%s\"", side_name(c->side));
        }
        if (c->has_more) {
            printf(",\"more_work\":%s", c->more ? "true" : "false");
        }
        if (c->has_alias) {
            printf(",\"aliased\":%s", c->aliased ? "true" : "false");
        }
        putchar('}');
    }

    fputs("],\"events\":[", stdout);
    for (i = 0u; i < g_event_count; i++) {
        const struct event_rec *e = &g_events[i];
        if (i != 0u) { putchar(','); }
        if (e->has_extent) {
            printf("{\"phase\":\"%s\",\"device\":\"%s\","
                   "\"op\":\"%s\",\"lba\":%lu,\"count\":%lu}",
                   e->phase, e->device, e->op,
                   (unsigned long)e->lba, (unsigned long)e->count);
        } else {
            printf("{\"phase\":\"%s\",\"device\":\"%s\",\"op\":\"%s\"}",
                   e->phase, e->device, e->op);
        }
    }
    puts("]}");
}

static int selfcheck_trace(void)
{
    unsigned char block[TAPE_BLOCK_SIZE];
    struct media_ctx m;
    int rr, wr;

    memset(block, 0, sizeof block);
    memset(&m, 0, sizeof m);
    m.bytes = block;
    m.physical_blocks = 1u;
    m.advertised_blocks = 1u;
    m.name = "destination";
    m.trace = true;
    reset_trace();
    g_phase = "selfcheck";

    rr = media_read(&m, 1u, 1u, block);
    wr = media_write(&m, 1u, 1u, block);
    if (rr != -1 || wr != -1 || g_event_overflow || g_event_count != 2u
        || strcmp(g_events[0].op, "read") != 0
        || strcmp(g_events[1].op, "write") != 0
        || g_events[0].lba != 1u || g_events[1].lba != 1u) {
        fprintf(stderr, "callback trace self-check failed\n");
        return 1;
    }
    puts("PASS rejected format/dup callbacks remain observable");
    return 0;
}

int main(int argc, char **argv)
{
    struct media_ctx src, dst;
    struct case_cfg cfg;
    struct media_ctx *tracked;
    int failed = 0;

    if (argc == 2 && strcmp(argv[1], "--selfcheck-callback-trace") == 0) {
        return selfcheck_trace();
    }
    if (argc != 4) {
        fprintf(stderr, "usage: %s CASE_ID INPUT.vo08 OUTPUT.vo08\n", argv[0]);
        return 2;
    }

    memset(&src, 0, sizeof src);
    memset(&dst, 0, sizeof dst);
    g_call_count = 0u;
    reset_trace();

    if (load_vo08(argv[2], &src, "source") != 0
        || case_config(argv[1], src.physical_blocks, &cfg) != 0) {
        fprintf(stderr, "failed to load input or configure case\n");
        free(src.bytes);
        return 2;
    }

    if (cfg.kind == CASE_FORMAT) {
        /* For format the fixture bytes are the destination under test. */
        src.name = "destination";
        if (run_format(&cfg, &src) != 0) { failed = 1; }
        tracked = &src;
    } else if (cfg.kind == CASE_DUP) {
        if (!cfg.aliases && clone_media(&src, &dst, "destination") != 0) {
            free(src.bytes);
            return 2;
        }
        if (run_dup(&cfg, &src, cfg.aliases ? &src : &dst) != 0) { failed = 1; }
        tracked = cfg.aliases ? &src : &dst;
    } else {
        if (run_promote(&src) != 0) { failed = 1; }
        tracked = &src;
    }

    if (store_vo08(argv[3], tracked) != 0) {
        fprintf(stderr, "failed to store output\n");
        failed = 1;
    }
    if (g_event_overflow) {
        fprintf(stderr, "event trace overflow\n");
        failed = 1;
    }
    emit_json(argv[1]);

    free(dst.bytes);
    free(src.bytes);
    return failed ? 1 : 0;
}
