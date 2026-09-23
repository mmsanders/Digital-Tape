/*
 * wp12_respool_probe.c — mechanical product adapter for the WP-12 respool
 * verifier package.
 *
 * This branch intentionally does not define or emulate tape_promote: #155 is
 * the authoritative promote lane. Therefore the partial runner executes the
 * seven respool cases whose verifier scripts do not call tape_promote. Once the
 * promote result is composed, this adapter can add the package's WP12-EMPTY
 * promote-asymmetry call and the unchanged oracle can run all eight cases.
 */
#ifndef TAPE_PUBLIC_HEADER
#define TAPE_PUBLIC_HEADER "tape.h"
#endif
#include TAPE_PUBLIC_HEADER

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define OBS_FORMAT "WP12-RESPOOL-OBSERVATION-1"
#define VO_BLOCK 512u
#define VO_SLOT_BYTES 65536u
#define VO_SLOT_BLOCKS (VO_SLOT_BYTES / VO_BLOCK)
#define VO_SLOTS 4u
#define VO_HEADER 8u
#define VO_SIZE (VO_HEADER + 2u * VO_BLOCK + VO_SLOTS * VO_SLOT_BYTES)
#define LBA_A0 8u
#define LBA_CHUNK_BASE 2048u
#define INSTANCE_BYTES 262144u
#define MAX_CHUNKS 64u
#define MAX_EVENTS 32768u
#define MAX_CALLS 16u
#define SEMANTIC_BUDGET 65535u
#define POISON_BYTE 0xA5u

struct media {
    uint32_t blocks;
    unsigned char primary[VO_BLOCK];
    unsigned char mirror[VO_BLOCK];
    unsigned char slots[VO_SLOTS][VO_SLOT_BYTES];
    unsigned char *chunk[MAX_CHUNKS];
};

struct event {
    const char *phase;
    const char *op;
    uint32_t lba;
    uint32_t count;
    int rc;
    bool extent;
};

struct call_rec {
    const char *phase;
    const char *fn;
    const char *result;
    const char *side;
    bool has_budget;
    uint32_t block_budget;
    bool has_more;
    bool more_work;
};

static struct media g_media;
static struct event g_events[MAX_EVENTS];
static size_t g_event_count;
static bool g_event_overflow;
static struct call_rec g_calls[MAX_CALLS];
static size_t g_call_count;
static const char *g_phase = "init";

static unsigned char g_inst[INSTANCE_BYTES];
static unsigned char g_play[TAPE_PLAY_RING_MIN];
static unsigned char g_rec[TAPE_REC_RING_MIN];
static tape_dev g_dev;

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

static const char *side_name(tape_side side)
{
    return side == TAPE_SIDE_B ? "B" : "A";
}

static void event_push(const char *op, uint32_t lba, uint32_t count, int rc, bool extent)
{
    struct event *e;
    if (g_event_count >= MAX_EVENTS) {
        g_event_overflow = true;
        return;
    }
    e = &g_events[g_event_count++];
    e->phase = g_phase;
    e->op = op;
    e->lba = lba;
    e->count = count;
    e->rc = rc;
    e->extent = extent;
}

static struct call_rec *call_push(const char *phase, const char *fn, tape_result r)
{
    struct call_rec *c;
    if (g_call_count >= MAX_CALLS) { return NULL; }
    c = &g_calls[g_call_count++];
    memset(c, 0, sizeof *c);
    c->phase = phase;
    c->fn = fn;
    c->result = result_name(r);
    return c;
}

static bool range_ok(uint32_t lba, uint32_t count)
{
    return count != 0u
        && (uint64_t)lba + (uint64_t)count <= (uint64_t)g_media.blocks;
}

static unsigned char *media_block(uint32_t lba, bool alloc)
{
    if (lba == 0u) { return g_media.primary; }
    if (lba == g_media.blocks - 1u) { return g_media.mirror; }

    if (lba >= LBA_A0 && lba < LBA_A0 + VO_SLOTS * VO_SLOT_BLOCKS) {
        uint32_t off = lba - LBA_A0;
        return g_media.slots[off / VO_SLOT_BLOCKS]
             + (size_t)(off % VO_SLOT_BLOCKS) * VO_BLOCK;
    }

    if (lba >= LBA_CHUNK_BASE && lba < g_media.blocks - 1u) {
        uint32_t rel = lba - LBA_CHUNK_BASE;
        uint32_t ci = rel / TAPE_CHUNK_BLOCKS;
        if (ci >= MAX_CHUNKS) { return NULL; }
        if (g_media.chunk[ci] == NULL) {
            if (!alloc) { return NULL; }
            g_media.chunk[ci] = malloc((size_t)TAPE_CHUNK_BLOCKS * VO_BLOCK);
            if (g_media.chunk[ci] == NULL) { return NULL; }
            memset(g_media.chunk[ci], (int)POISON_BYTE,
                   (size_t)TAPE_CHUNK_BLOCKS * VO_BLOCK);
        }
        return g_media.chunk[ci]
             + (size_t)(rel % TAPE_CHUNK_BLOCKS) * VO_BLOCK;
    }

    return NULL;
}

static int adapter_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    unsigned char *out = dst;
    uint32_t i;
    (void)ctx;

    if (!range_ok(lba, count)) {
        event_push("read", lba, count, -1, true);
        return -1;
    }

    for (i = 0u; i < count; i++) {
        const unsigned char *src = media_block(lba + i, false);
        if (src == NULL) {
            memset(out + (size_t)i * VO_BLOCK, (int)POISON_BYTE, VO_BLOCK);
        } else {
            memcpy(out + (size_t)i * VO_BLOCK, src, VO_BLOCK);
        }
    }
    event_push("read", lba, count, 0, true);
    return 0;
}

static int adapter_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    const unsigned char *in = src;
    uint32_t i;
    (void)ctx;

    if (!range_ok(lba, count)) {
        event_push("write", lba, count, -1, true);
        return -1;
    }

    for (i = 0u; i < count; i++) {
        unsigned char *dst = media_block(lba + i, true);
        if (dst == NULL) {
            event_push("write", lba, count, -1, true);
            return -1;
        }
        memcpy(dst, in + (size_t)i * VO_BLOCK, VO_BLOCK);
    }
    event_push("write", lba, count, 0, true);
    return 0;
}

static int adapter_flush(void *ctx)
{
    (void)ctx;
    event_push("flush", 0u, 0u, 0, false);
    return 0;
}

static int media_load(const char *path)
{
    unsigned char *buf;
    FILE *f;
    long size;
    size_t p;
    unsigned i;

    f = fopen(path, "rb");
    if (f == NULL) { return -1; }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return -1; }
    size = ftell(f);
    if (size != (long)VO_SIZE) { fclose(f); return -1; }
    if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); return -1; }

    buf = malloc(VO_SIZE);
    if (buf == NULL) { fclose(f); return -1; }
    if (fread(buf, 1u, VO_SIZE, f) != VO_SIZE) {
        free(buf);
        fclose(f);
        return -1;
    }
    fclose(f);

    if (memcmp(buf, "VO08", 4u) != 0) { free(buf); return -1; }
    memset(&g_media, 0, sizeof g_media);
    g_media.blocks = (uint32_t)buf[4]
                   | ((uint32_t)buf[5] << 8)
                   | ((uint32_t)buf[6] << 16)
                   | ((uint32_t)buf[7] << 24);
    p = VO_HEADER;
    memcpy(g_media.primary, buf + p, VO_BLOCK);
    p += VO_BLOCK;
    memcpy(g_media.mirror, buf + p, VO_BLOCK);
    p += VO_BLOCK;
    for (i = 0u; i < VO_SLOTS; i++) {
        memcpy(g_media.slots[i], buf + p, VO_SLOT_BYTES);
        p += VO_SLOT_BYTES;
    }
    free(buf);
    return 0;
}

static int media_store(const char *path)
{
    unsigned char *buf;
    FILE *f;
    size_t p = VO_HEADER;
    unsigned i;

    buf = malloc(VO_SIZE);
    if (buf == NULL) { return -1; }
    memcpy(buf, "VO08", 4u);
    buf[4] = (unsigned char)(g_media.blocks & 0xFFu);
    buf[5] = (unsigned char)((g_media.blocks >> 8) & 0xFFu);
    buf[6] = (unsigned char)((g_media.blocks >> 16) & 0xFFu);
    buf[7] = (unsigned char)((g_media.blocks >> 24) & 0xFFu);

    memcpy(buf + p, g_media.primary, VO_BLOCK);
    p += VO_BLOCK;
    memcpy(buf + p, g_media.mirror, VO_BLOCK);
    p += VO_BLOCK;
    for (i = 0u; i < VO_SLOTS; i++) {
        memcpy(buf + p, g_media.slots[i], VO_SLOT_BYTES);
        p += VO_SLOT_BYTES;
    }

    f = fopen(path, "wb");
    if (f == NULL) { free(buf); return -1; }
    if (fwrite(buf, 1u, VO_SIZE, f) != VO_SIZE) {
        free(buf);
        fclose(f);
        return -1;
    }
    free(buf);
    return fclose(f) == 0 ? 0 : -1;
}

static void free_chunks(void)
{
    unsigned i;
    for (i = 0u; i < MAX_CHUNKS; i++) {
        free(g_media.chunk[i]);
        g_media.chunk[i] = NULL;
    }
}

static tape_side mount_side_for(const char *id)
{
    return strcmp(id, "WP12-DEGRADED") == 0 ? TAPE_SIDE_A : TAPE_SIDE_B;
}

static int run_case(const char *id)
{
    tape *t = NULL;
    tape_side side = mount_side_for(id);
    tape_result rc;
    struct call_rec *c;
    bool more = false;

    memset(g_inst, 0, sizeof g_inst);
    memset(g_play, 0, sizeof g_play);
    memset(g_rec, 0, sizeof g_rec);

    g_dev.read = adapter_read;
    g_dev.write = adapter_write;
    g_dev.flush = adapter_flush;
    g_dev.ctx = NULL;
    g_dev.block_count = g_media.blocks;

    if (tape_instance_size() > sizeof g_inst) { return 1; }
    rc = tape_init(g_inst, tape_instance_size(), &g_dev,
                   g_play, sizeof g_play, g_rec, sizeof g_rec, &t);
    if (rc != TAPE_OK) { return 1; }

    g_phase = "mount";
    rc = tape_mount(t, side, 0u, NULL);
    c = call_push("mount", "tape_mount", rc);
    if (c != NULL) { c->side = side_name(side); }
    if (rc != TAPE_OK) { return 1; }

    g_phase = "respool";
    rc = tape_respool(t, SEMANTIC_BUDGET, &more);
    c = call_push("respool", "tape_respool", rc);
    if (c != NULL) {
        c->has_budget = true;
        c->block_budget = SEMANTIC_BUDGET;
        c->has_more = true;
        c->more_work = more;
    }

    g_phase = "unmount";
    {
        tape_result urc = tape_unmount(t, NULL);
        (void)call_push("unmount", "tape_unmount", urc);
        if (urc != TAPE_OK) { return 1; }
    }

    return 0;
}

static void emit_json(void)
{
    size_t i;

    printf("{\"format\":\"%s\",\"adapter_kind\":\"product\",\"calls\":[",
           OBS_FORMAT);
    for (i = 0u; i < g_call_count; i++) {
        const struct call_rec *c = &g_calls[i];
        if (i != 0u) { putchar(','); }
        printf("{\"phase\":\"%s\",\"fn\":\"%s\",\"result\":\"%s\"",
               c->phase, c->fn, c->result);
        if (c->side != NULL) {
            printf(",\"side\":\"%s\"", c->side);
        }
        if (c->has_budget) {
            printf(",\"block_budget\":%lu", (unsigned long)c->block_budget);
        }
        if (c->has_more) {
            fputs(",\"more_work\":", stdout);
            fputs(c->more_work ? "true" : "false", stdout);
        }
        putchar('}');
    }

    fputs("],\"events\":[", stdout);
    for (i = 0u; i < g_event_count; i++) {
        const struct event *e = &g_events[i];
        if (i != 0u) { putchar(','); }
        if (e->extent) {
            printf("{\"phase\":\"%s\",\"op\":\"%s\",\"lba\":%lu,\"count\":%lu,\"rc\":%d}",
                   e->phase, e->op, (unsigned long)e->lba,
                   (unsigned long)e->count, e->rc);
        } else {
            printf("{\"phase\":\"%s\",\"op\":\"%s\",\"rc\":%d}",
                   e->phase, e->op, e->rc);
        }
    }
    fputs("],\"event_overflow\":", stdout);
    fputs(g_event_overflow ? "true" : "false", stdout);
    puts("}");
}

int main(int argc, char **argv)
{
    int failed;

    if (argc != 4) {
        fprintf(stderr, "usage: %s CASE_ID INPUT.vo08 OUTPUT.vo08\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "WP12-EMPTY") == 0) {
        fprintf(stderr, "WP12-EMPTY requires authoritative tape_promote from Software #155\n");
        return 3;
    }
    if (media_load(argv[2]) != 0) {
        fprintf(stderr, "failed to load input\n");
        return 2;
    }

    failed = run_case(argv[1]);
    if (media_store(argv[3]) != 0) { failed = 1; }
    emit_json();
    if (g_event_overflow) { failed = 1; }
    free_chunks();
    return failed ? 1 : 0;
}
