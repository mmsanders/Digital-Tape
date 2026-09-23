/*
 * wp36_slot_probe.c — mechanical real-product adapter for slot_draft8.
 *
 * Contract: tests/slot_draft8/ADAPTER.md. This adapter uses only the public
 * tape.h API. The source-slot device has a literal write == NULL. Expectations
 * remain exclusively in the independently published verifier package.
 *
 * Usage: wp36_slot_probe CASE_ID INPUT.vo08 OUTPUT.vo08
 */
#ifndef TAPE_PUBLIC_HEADER
#define TAPE_PUBLIC_HEADER "tape.h"
#endif
#include TAPE_PUBLIC_HEADER

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#ifdef NDEBUG
#error "WP-36 product evidence requires debug assertions enabled"
#endif

#define OBS_FORMAT "WP36-SLOT-OBSERVATION-2"
#define VO_BLOCK 512u
#define VO_SLOT_BYTES 65536u
#define VO_SLOT_BLOCKS (VO_SLOT_BYTES / VO_BLOCK)
#define VO_SLOTS 4u
#define VO_HEADER 8u
#define VO_SIZE (VO_HEADER + 2u * VO_BLOCK + VO_SLOTS * VO_SLOT_BYTES)
#define LBA_A0 8u
#define INSTANCE_BYTES 262144u
#define MAX_EVENTS 4096u
#define MAX_CALLS 128u
#define SERVICE_BUDGET 1024u
#define SERVICE_GUARD 64u

enum case_kind {
    CASE_PLAYBACK,
    CASE_MUTATORS,
    CASE_REPAIR
};

struct case_row {
    const char *id;
    enum case_kind kind;
    tape_side side;
};

static const struct case_row g_cases[] = {
    {"WP36-SRC-A", CASE_PLAYBACK, TAPE_SIDE_A},
    {"WP36-SRC-B", CASE_PLAYBACK, TAPE_SIDE_B},
    {"WP36-SRC-MUTATORS-B", CASE_MUTATORS, TAPE_SIDE_B},
    {"WP36-SRC-MUTATORS-A", CASE_MUTATORS, TAPE_SIDE_A},
    {"WP36-SRC-REPAIR-A", CASE_REPAIR, TAPE_SIDE_A}
};

struct media {
    uint32_t blocks;
    unsigned char primary[VO_BLOCK];
    unsigned char mirror[VO_BLOCK];
    unsigned char slots[VO_SLOTS][VO_SLOT_BYTES];
};
static struct media g_media;

struct event_rec {
    const char *op;
    uint32_t lba;
    uint32_t count;
    int rc;
};
static struct event_rec g_events[MAX_EVENTS];
static size_t g_event_count;
static bool g_event_overflow;

enum call_kind {
    CALL_INIT,
    CALL_MOUNT,
    CALL_INFO,
    CALL_SEEK,
    CALL_RATE,
    CALL_SERVICE,
    CALL_RENDER,
    CALL_ARM,
    CALL_FEED,
    CALL_COMMIT,
    CALL_RESET_B,
    CALL_PROMOTE,
    CALL_RESPOOL,
    CALL_UNMOUNT
};

struct call_rec {
    enum call_kind kind;
    tape_result result;
    tape_side side;
    bool writable;
    bool needs_repair;
    bool more_work;
    uint32_t rendered;
    uint32_t accepted;
};
static struct call_rec g_calls[MAX_CALLS];
static size_t g_call_count;

union aligned_buf {
    uint64_t align;
    unsigned char bytes[INSTANCE_BYTES];
};
static union aligned_buf g_inst;

union aligned_ring {
    uint64_t align;
    unsigned char bytes[TAPE_PLAY_RING_MIN];
};
static union aligned_ring g_play;
static union aligned_ring g_rec;

static int16_t g_pcm[8u * TAPE_CHANNELS];

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

static const struct case_row *find_case(const char *id)
{
    size_t i;
    for (i = 0u; i < sizeof g_cases / sizeof g_cases[0]; i++) {
        if (strcmp(id, g_cases[i].id) == 0) { return &g_cases[i]; }
    }
    return NULL;
}

static void event_push(const char *op, uint32_t lba, uint32_t count, int rc)
{
    struct event_rec *e;
    if (g_event_count >= MAX_EVENTS) {
        g_event_overflow = true;
        return;
    }
    e = &g_events[g_event_count++];
    e->op = op;
    e->lba = lba;
    e->count = count;
    e->rc = rc;
}

static struct call_rec *call_push(enum call_kind kind, tape_result result)
{
    struct call_rec *c;
    if (g_call_count >= MAX_CALLS) { return NULL; }
    c = &g_calls[g_call_count++];
    memset(c, 0, sizeof *c);
    c->kind = kind;
    c->result = result;
    return c;
}

static bool range_ok(uint32_t lba, uint32_t count)
{
    return count != 0u
        && (uint64_t)lba + (uint64_t)count <= (uint64_t)g_media.blocks;
}

static const unsigned char *media_block(uint32_t lba)
{
    if (lba == 0u) { return g_media.primary; }
    if (g_media.blocks != 0u && lba == g_media.blocks - 1u) {
        return g_media.mirror;
    }
    if (lba >= LBA_A0 && lba < LBA_A0 + VO_SLOTS * VO_SLOT_BLOCKS) {
        uint32_t off = lba - LBA_A0;
        uint32_t slot = off / VO_SLOT_BLOCKS;
        uint32_t block = off % VO_SLOT_BLOCKS;
        return g_media.slots[slot] + (size_t)block * VO_BLOCK;
    }
    return NULL;
}

static int source_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    unsigned char *out = dst;
    uint32_t i;
    int rc = range_ok(lba, count) ? 0 : -1;
    (void)ctx;

    /* Log the invocation before refusal so failed callbacks cannot disappear. */
    event_push("read", lba, count, rc);
    if (rc != 0) { return rc; }

    for (i = 0u; i < count; i++) {
        const unsigned char *src = media_block(lba + i);
        if (src == NULL) {
            memset(out + (size_t)i * VO_BLOCK, 0, VO_BLOCK);
        } else {
            memcpy(out + (size_t)i * VO_BLOCK, src, VO_BLOCK);
        }
    }
    return 0;
}

static int source_flush(void *ctx)
{
    (void)ctx;
    event_push("flush", 0u, 0u, 0);
    return 0;
}

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

static int media_load(const char *path)
{
    static unsigned char buf[VO_SIZE];
    FILE *f;
    size_t got;
    size_t p;
    unsigned i;

    f = fopen(path, "rb");
    if (f == NULL) { return -1; }
    got = fread(buf, 1u, sizeof buf, f);
    if (got != sizeof buf || fgetc(f) != EOF) {
        fclose(f);
        return -1;
    }
    if (fclose(f) != 0) { return -1; }
    if (memcmp(buf, "VO08", 4u) != 0) { return -1; }

    memset(&g_media, 0, sizeof g_media);
    g_media.blocks = rd32(buf + 4u);
    p = VO_HEADER;
    memcpy(g_media.primary, buf + p, VO_BLOCK);
    p += VO_BLOCK;
    memcpy(g_media.mirror, buf + p, VO_BLOCK);
    p += VO_BLOCK;
    for (i = 0u; i < VO_SLOTS; i++) {
        memcpy(g_media.slots[i], buf + p, VO_SLOT_BYTES);
        p += VO_SLOT_BYTES;
    }
    return 0;
}

static int media_store(const char *path)
{
    static unsigned char buf[VO_SIZE];
    FILE *f;
    size_t p = VO_HEADER;
    unsigned i;

    memcpy(buf, "VO08", 4u);
    wr32(buf + 4u, g_media.blocks);
    memcpy(buf + p, g_media.primary, VO_BLOCK);
    p += VO_BLOCK;
    memcpy(buf + p, g_media.mirror, VO_BLOCK);
    p += VO_BLOCK;
    for (i = 0u; i < VO_SLOTS; i++) {
        memcpy(buf + p, g_media.slots[i], VO_SLOT_BYTES);
        p += VO_SLOT_BYTES;
    }

    f = fopen(path, "wb");
    if (f == NULL) { return -1; }
    if (fwrite(buf, 1u, sizeof buf, f) != sizeof buf) {
        fclose(f);
        return -1;
    }
    return fclose(f) == 0 ? 0 : -1;
}

static void run_playback(tape *t)
{
    tape_result rc;
    bool more = true;
    uint32_t guard = 0u;
    uint32_t rendered = 0u;
    struct call_rec *c;

    rc = tape_seek(t, 0u);
    (void)call_push(CALL_SEEK, rc);

    rc = tape_set_rate(t, 65536);
    (void)call_push(CALL_RATE, rc);

    while (more && guard < SERVICE_GUARD) {
        more = false;
        rc = tape_service(t, SERVICE_BUDGET, &more);
        c = call_push(CALL_SERVICE, rc);
        if (c != NULL) { c->more_work = more; }
        guard++;
        if (rc != TAPE_OK) { break; }
    }

    rc = tape_render(t, g_pcm, 8u, &rendered);
    c = call_push(CALL_RENDER, rc);
    if (c != NULL) { c->rendered = rendered; }
}

static void run_mutators(tape *t)
{
    tape_result rc;
    bool more;
    uint32_t accepted = 0u;
    int16_t frame[TAPE_CHANNELS] = {0, 0};
    struct call_rec *c;

    rc = tape_arm(t, TAPE_REC_OVERWRITE);
    (void)call_push(CALL_ARM, rc);

    rc = tape_feed(t, frame, 1u, &accepted);
    c = call_push(CALL_FEED, rc);
    if (c != NULL) { c->accepted = accepted; }

    rc = tape_commit(t);
    (void)call_push(CALL_COMMIT, rc);

    rc = tape_reset_side_b(t);
    (void)call_push(CALL_RESET_B, rc);

    more = false;
    rc = tape_promote(t, 64u, &more, NULL, NULL);
    c = call_push(CALL_PROMOTE, rc);
    if (c != NULL) { c->more_work = more; }

    more = false;
    rc = tape_respool(t, 64u, &more);
    c = call_push(CALL_RESPOOL, rc);
    if (c != NULL) { c->more_work = more; }
}

static const char *call_name(enum call_kind kind)
{
    switch (kind) {
    case CALL_INIT: return "tape_init";
    case CALL_MOUNT: return "tape_mount";
    case CALL_INFO: return "tape_get_info";
    case CALL_SEEK: return "tape_seek";
    case CALL_RATE: return "tape_set_rate";
    case CALL_SERVICE: return "tape_service";
    case CALL_RENDER: return "tape_render";
    case CALL_ARM: return "tape_arm";
    case CALL_FEED: return "tape_feed";
    case CALL_COMMIT: return "tape_commit";
    case CALL_RESET_B: return "tape_reset_side_b";
    case CALL_PROMOTE: return "tape_promote";
    case CALL_RESPOOL: return "tape_respool";
    case CALL_UNMOUNT: return "tape_unmount";
    default: return "unknown";
    }
}

static void print_calls(void)
{
    size_t i;
    for (i = 0u; i < g_call_count; i++) {
        const struct call_rec *c = &g_calls[i];
        if (i != 0u) { putchar(','); }
        printf("{\"fn\":\"%s\",\"result\":\"%s\"",
               call_name(c->kind), result_name(c->result));
        if (c->kind == CALL_MOUNT) {
            printf(",\"side\":\"%s\"", side_name(c->side));
        } else if (c->kind == CALL_INFO) {
            printf(",\"writable\":%s,\"needs_repair\":%s",
                   c->writable ? "true" : "false",
                   c->needs_repair ? "true" : "false");
        } else if (c->kind == CALL_SERVICE
                   || c->kind == CALL_PROMOTE
                   || c->kind == CALL_RESPOOL) {
            printf(",\"more_work\":%s", c->more_work ? "true" : "false");
        } else if (c->kind == CALL_RENDER) {
            printf(",\"rendered\":%lu", (unsigned long)c->rendered);
        } else if (c->kind == CALL_FEED) {
            printf(",\"accepted\":%lu", (unsigned long)c->accepted);
        }
        putchar('}');
    }
}

static void print_events(void)
{
    size_t i;
    for (i = 0u; i < g_event_count; i++) {
        const struct event_rec *e = &g_events[i];
        if (i != 0u) { putchar(','); }
        printf("{\"op\":\"%s\",\"lba\":%lu,\"count\":%lu,\"rc\":%d}",
               e->op, (unsigned long)e->lba, (unsigned long)e->count, e->rc);
    }
}

int main(int argc, char **argv)
{
    const struct case_row *row;
    tape_dev dev;
    tape *t = NULL;
    tape_info info;
    tape_result rc;
    struct call_rec *c;
    size_t instance_size;
    uint64_t position = 0u;

    if (argc != 4) {
        fprintf(stderr, "usage: %s CASE_ID INPUT.vo08 OUTPUT.vo08\n", argv[0]);
        return 2;
    }
    row = find_case(argv[1]);
    if (row == NULL || media_load(argv[2]) != 0) { return 2; }

    memset(&dev, 0, sizeof dev);
    dev.read = source_read;
    dev.write = NULL;              /* WP-36 premise: literal source-slot NULL. */
    dev.flush = source_flush;
    dev.ctx = &g_media;
    dev.block_count = g_media.blocks;

    instance_size = tape_instance_size();
    if (instance_size > sizeof g_inst.bytes) { return 2; }

    memset(&g_inst, 0, sizeof g_inst);
    memset(&g_play, 0, sizeof g_play);
    memset(&g_rec, 0, sizeof g_rec);
    memset(&info, 0, sizeof info);
    memset(g_pcm, 0, sizeof g_pcm);
    g_event_count = 0u;
    g_event_overflow = false;
    g_call_count = 0u;

    rc = tape_init(g_inst.bytes, instance_size, &dev,
                   g_play.bytes, sizeof g_play.bytes,
                   g_rec.bytes, sizeof g_rec.bytes, &t);
    (void)call_push(CALL_INIT, rc);

    if (rc == TAPE_OK) {
        rc = tape_mount(t, row->side, 0u, NULL);
        c = call_push(CALL_MOUNT, rc);
        if (c != NULL) { c->side = row->side; }

        if (rc == TAPE_OK) {
            rc = tape_get_info(t, &info);
            c = call_push(CALL_INFO, rc);
            if (c != NULL) {
                c->writable = info.writable;
                c->needs_repair = info.needs_repair;
            }

            if (row->kind == CASE_PLAYBACK) {
                run_playback(t);
            } else if (row->kind == CASE_MUTATORS) {
                run_mutators(t);
            }

            rc = tape_unmount(t, &position);
            (void)call_push(CALL_UNMOUNT, rc);
        }
    }

    if (media_store(argv[3]) != 0) { return 2; }

    printf("{\"format\":\"%s\",\"adapter_kind\":\"product\","
           "\"debug_assertions\":true,\"event_overflow\":%s,\"calls\":[",
           OBS_FORMAT, g_event_overflow ? "true" : "false");
    print_calls();
    fputs("],\"events\":[", stdout);
    print_events();
    puts("]}");

    return g_event_overflow ? 2 : 0;
}
