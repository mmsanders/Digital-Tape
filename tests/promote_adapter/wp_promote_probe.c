/*
 * Mechanical product adapter for tests/promote_draft8.
 * Verifier-owned fixture/oracle bytes are not interpreted beyond the VO08
 * envelope required to place their superblocks and four index slots on a real
 * in-memory tape_dev.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "tape.h"

#define VO08_SIZE (8u + 2u * TAPE_BLOCK_SIZE + 4u * TAPE_INDEX_SLOT_BYTES)
#define MAX_EVENTS 20000u
#define MAX_CALLS 10000u
#define ADAPTER_ID "p1-r25-promote-product-v1"

struct event_rec {
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
    bool has_budget;
    uint32_t budget;
};

struct media_ctx {
    unsigned char *bytes;
    uint32_t blocks;
    bool trace;
    bool overflow;
    size_t event_count;
    struct event_rec events[MAX_EVENTS];
};

static struct call_rec g_calls[MAX_CALLS];
static size_t g_call_count;

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

static void trace_extent(struct media_ctx *m, const char *op,
                         uint32_t lba, uint32_t count)
{
    struct event_rec *e;

    if (!m->trace) { return; }
    if (m->event_count >= MAX_EVENTS) {
        m->overflow = true;
        return;
    }
    e = &m->events[m->event_count++];
    e->op = op;
    e->lba = lba;
    e->count = count;
    e->has_extent = true;
}

static void trace_flush(struct media_ctx *m)
{
    struct event_rec *e;

    if (!m->trace) { return; }
    if (m->event_count >= MAX_EVENTS) {
        m->overflow = true;
        return;
    }
    e = &m->events[m->event_count++];
    e->op = "flush";
    e->lba = 0u;
    e->count = 0u;
    e->has_extent = false;
}

static int mem_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    struct media_ctx *m = ctx;
    uint64_t end = (uint64_t)lba + (uint64_t)count;

    if (end > (uint64_t)m->blocks) { return -1; }
    memcpy(dst,
           m->bytes + (size_t)lba * TAPE_BLOCK_SIZE,
           (size_t)count * TAPE_BLOCK_SIZE);
    trace_extent(m, "read", lba, count);
    return 0;
}

static int mem_write(void *ctx, uint32_t lba, uint32_t count,
                     const void *src)
{
    struct media_ctx *m = ctx;
    uint64_t end = (uint64_t)lba + (uint64_t)count;

    if (end > (uint64_t)m->blocks) { return -1; }
    memcpy(m->bytes + (size_t)lba * TAPE_BLOCK_SIZE,
           src, (size_t)count * TAPE_BLOCK_SIZE);
    trace_extent(m, "write", lba, count);
    return 0;
}

static int mem_flush(void *ctx)
{
    struct media_ctx *m = ctx;
    trace_flush(m);
    return 0;
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

static const char *side_name(tape_side side)
{
    return side == TAPE_SIDE_A ? "A" : "B";
}

static int read_file(const char *path, unsigned char **out, size_t *out_len)
{
    FILE *f;
    long n;
    unsigned char *buf;

    f = fopen(path, "rb");
    if (f == NULL) { return -1; }
    if (fseek(f, 0L, SEEK_END) != 0) { fclose(f); return -1; }
    n = ftell(f);
    if (n < 0L) { fclose(f); return -1; }
    if (fseek(f, 0L, SEEK_SET) != 0) { fclose(f); return -1; }
    buf = malloc((size_t)n);
    if (buf == NULL) { fclose(f); return -1; }
    if (fread(buf, 1u, (size_t)n, f) != (size_t)n) {
        free(buf);
        fclose(f);
        return -1;
    }
    if (fclose(f) != 0) { free(buf); return -1; }
    *out = buf;
    *out_len = (size_t)n;
    return 0;
}

static int expand_vo08(const unsigned char *vo, size_t n,
                       struct media_ctx *m)
{
    size_t p = 8u;
    size_t bytes;

    if (n != VO08_SIZE || memcmp(vo, "VO08", 4u) != 0) { return -1; }
    m->blocks = rd32(vo + 4u);
    if (m->blocks <= TAPE_LBA_CHUNK_BASE) { return -1; }
    if ((uint64_t)m->blocks * TAPE_BLOCK_SIZE > (uint64_t)SIZE_MAX) {
        return -1;
    }
    bytes = (size_t)m->blocks * TAPE_BLOCK_SIZE;
    m->bytes = calloc(1u, bytes);
    if (m->bytes == NULL) { return -1; }

    memcpy(m->bytes + (size_t)TAPE_LBA_SUPERBLOCK * TAPE_BLOCK_SIZE,
           vo + p, TAPE_BLOCK_SIZE);
    p += TAPE_BLOCK_SIZE;
    memcpy(m->bytes + (size_t)(m->blocks - 1u) * TAPE_BLOCK_SIZE,
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
    return 0;
}

static int store_vo08(const char *path, const struct media_ctx *m)
{
    FILE *f;
    unsigned char head[8];

    memcpy(head, "VO08", 4u);
    wr32(head + 4u, m->blocks);
    f = fopen(path, "wb");
    if (f == NULL) { return -1; }
    if (fwrite(head, 1u, sizeof head, f) != sizeof head) {
        fclose(f); return -1;
    }
    if (fwrite(m->bytes + (size_t)TAPE_LBA_SUPERBLOCK * TAPE_BLOCK_SIZE,
               1u, TAPE_BLOCK_SIZE, f) != TAPE_BLOCK_SIZE) {
        fclose(f); return -1;
    }
    if (fwrite(m->bytes + (size_t)(m->blocks - 1u) * TAPE_BLOCK_SIZE,
               1u, TAPE_BLOCK_SIZE, f) != TAPE_BLOCK_SIZE) {
        fclose(f); return -1;
    }
    if (fwrite(m->bytes + (size_t)TAPE_LBA_INDEX_A0 * TAPE_BLOCK_SIZE,
               1u, TAPE_INDEX_SLOT_BYTES, f) != TAPE_INDEX_SLOT_BYTES) {
        fclose(f); return -1;
    }
    if (fwrite(m->bytes + (size_t)TAPE_LBA_INDEX_A1 * TAPE_BLOCK_SIZE,
               1u, TAPE_INDEX_SLOT_BYTES, f) != TAPE_INDEX_SLOT_BYTES) {
        fclose(f); return -1;
    }
    if (fwrite(m->bytes + (size_t)TAPE_LBA_INDEX_B0 * TAPE_BLOCK_SIZE,
               1u, TAPE_INDEX_SLOT_BYTES, f) != TAPE_INDEX_SLOT_BYTES) {
        fclose(f); return -1;
    }
    if (fwrite(m->bytes + (size_t)TAPE_LBA_INDEX_B1 * TAPE_BLOCK_SIZE,
               1u, TAPE_INDEX_SLOT_BYTES, f) != TAPE_INDEX_SLOT_BYTES) {
        fclose(f); return -1;
    }
    return fclose(f) == 0 ? 0 : -1;
}

static int add_mount_call(tape_result r, tape_side side)
{
    struct call_rec *c;
    if (g_call_count >= MAX_CALLS) { return -1; }
    c = &g_calls[g_call_count++];
    memset(c, 0, sizeof *c);
    c->phase = "mount";
    c->fn = "tape_mount";
    c->result = r;
    c->has_side = true;
    c->side = side;
    return 0;
}

static int add_promote_call(tape_result r, bool more)
{
    struct call_rec *c;
    if (g_call_count >= MAX_CALLS) { return -1; }
    c = &g_calls[g_call_count++];
    memset(c, 0, sizeof *c);
    c->phase = "promote";
    c->fn = "tape_promote";
    c->result = r;
    c->has_more = true;
    c->more = more;
    c->has_budget = true;
    c->budget = 64u;
    return 0;
}

static int add_unmount_call(tape_result r)
{
    struct call_rec *c;
    if (g_call_count >= MAX_CALLS) { return -1; }
    c = &g_calls[g_call_count++];
    memset(c, 0, sizeof *c);
    c->phase = "unmount";
    c->fn = "tape_unmount";
    c->result = r;
    return 0;
}

static void emit_json(const char *case_id, const struct media_ctx *m)
{
    size_t i;

    printf("{\"format\":\"WP-PROMOTE-OBSERVATION-1\",");
    printf("\"case_id\":\"%s\",", case_id);
    printf("\"adapter_kind\":\"product\",");
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
        if (c->has_budget) {
            printf(",\"block_budget\":%lu", (unsigned long)c->budget);
        }
        putchar('}');
    }

    fputs("],\"events\":[", stdout);
    for (i = 0u; i < m->event_count; i++) {
        const struct event_rec *e = &m->events[i];
        if (i != 0u) { putchar(','); }
        if (e->has_extent) {
            printf("{\"phase\":\"promote\",\"op\":\"%s\","
                   "\"lba\":%lu,\"count\":%lu}",
                   e->op, (unsigned long)e->lba, (unsigned long)e->count);
        } else {
            printf("{\"phase\":\"promote\",\"op\":\"%s\"}", e->op);
        }
    }
    puts("]}");
}

int main(int argc, char **argv)
{
    unsigned char *vo = NULL;
    size_t vo_len = 0u;
    struct media_ctx media;
    tape_dev dev;
    tape *t = NULL;
    void *instance = NULL;
    void *play_ring = NULL;
    void *rec_ring = NULL;
    tape_side mount_side;
    tape_result rc;
    tape_result unmount_rc = TAPE_ERR_NOT_MOUNTED;
    bool more = false;
    bool mounted = false;
    int failed = 0;
    uint32_t iterations = 0u;

    if (argc != 4) {
        fprintf(stderr, "usage: %s CASE_ID INPUT.vo08 OUTPUT.vo08\n", argv[0]);
        return 2;
    }
    memset(&media, 0, sizeof media);
    if (read_file(argv[2], &vo, &vo_len) != 0
        || expand_vo08(vo, vo_len, &media) != 0) {
        fprintf(stderr, "failed to load/expand VO08 input\n");
        free(vo);
        free(media.bytes);
        return 2;
    }
    free(vo);

    instance = calloc(1u, tape_instance_size());
    play_ring = calloc(1u, TAPE_PLAY_RING_MIN);
    rec_ring = calloc(1u, TAPE_REC_RING_MIN);
    if (instance == NULL || play_ring == NULL || rec_ring == NULL) {
        fprintf(stderr, "allocation failure\n");
        failed = 1;
        goto out;
    }

    dev.read = mem_read;
    dev.write = mem_write;
    dev.flush = mem_flush;
    dev.ctx = &media;
    dev.block_count = media.blocks;

    rc = tape_init(instance, tape_instance_size(), &dev,
                   play_ring, TAPE_PLAY_RING_MIN,
                   rec_ring, TAPE_REC_RING_MIN, &t);
    if (rc != TAPE_OK) {
        fprintf(stderr, "tape_init: %s\n", result_name(rc));
        failed = 1;
        goto out;
    }

    mount_side = strcmp(argv[1], "PR-DEGRADED") == 0
               ? TAPE_SIDE_A : TAPE_SIDE_B;
    rc = tape_mount(t, mount_side, 0u, NULL);
    if (add_mount_call(rc, mount_side) != 0) { failed = 1; goto out; }
    if (rc != TAPE_OK) {
        fprintf(stderr, "tape_mount: %s\n", result_name(rc));
        failed = 1;
        goto output;
    }
    mounted = true;

    /* ADAPTER.md: setup/teardown I/O is outside the promote event trace. */
    media.event_count = 0u;
    media.overflow = false;
    media.trace = true;

    do {
        more = false;
        rc = tape_promote(t, 64u, &more, NULL, NULL);
        if (add_promote_call(rc, more) != 0) {
            failed = 1;
            break;
        }
        iterations++;
        if (rc != TAPE_OK || !more) { break; }
        if (iterations >= MAX_CALLS - 3u) {
            fprintf(stderr, "promote continuation did not terminate\n");
            failed = 1;
            break;
        }
    } while (true);

    media.trace = false;
    if (media.overflow) {
        fprintf(stderr, "promote callback trace overflow\n");
        failed = 1;
    }

    unmount_rc = tape_unmount(t, NULL);
    if (add_unmount_call(unmount_rc) != 0) { failed = 1; }
    if (unmount_rc != TAPE_OK) {
        fprintf(stderr, "tape_unmount: %s\n", result_name(unmount_rc));
        failed = 1;
    } else {
        mounted = false;
    }

output:
    media.trace = false;
    if (store_vo08(argv[3], &media) != 0) {
        fprintf(stderr, "failed to write VO08 output\n");
        failed = 1;
    }
    emit_json(argv[1], &media);

out:
    if (mounted && t != NULL) {
        media.trace = false;
        (void)tape_unmount(t, NULL);
    }
    free(rec_ring);
    free(play_ring);
    free(instance);
    free(media.bytes);
    return failed ? 1 : 0;
}
