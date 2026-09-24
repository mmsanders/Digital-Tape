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

#define RF_BLOCK 512u
#define RF_MAX_INSTANCE 262144u
#define RF_MAX_TRACE 5000u
#define RF_CHUNK_BASE 2048u
#define RF_BPC 1024u
#define RF_SLOT_BYTES 65536u
#define RF_SLOT_BLOCKS 128u
#define RF_A0 8u
#define RF_A1 136u
#define RF_B0 264u
#define RF_B1 392u

#define RF_FIX_V3_PASS1 1
#define RF_FIX_V3_PASS2 2
#define RF_FIX_DECLINE 3

#define RF_MODE_FLUSH 0
#define RF_MODE_WRITE 1

#define RF_TARGET_CHUNK 1
#define RF_TARGET_CHUNK_FLUSH 2
#define RF_TARGET_ENTRY 3
#define RF_TARGET_ENTRY_FLUSH 4
#define RF_TARGET_HEADER 5
#define RF_TARGET_HEADER_FLUSH 6

#define RF_INJ_BEFORE 0
#define RF_INJ_TORN 1
#define RF_INJ_AFTER 2
#define RF_INJ_FLUSH 3

#define RF_EV_WRITE 1
#define RF_EV_FLUSH 2

struct rf_snapshot {
    uint32_t block_count;
    unsigned char primary[RF_BLOCK];
    unsigned char mirror[RF_BLOCK];
    unsigned char slots[4][2u * RF_BLOCK];
};

struct rf_info {
    unsigned char uuid[16];
    uint32_t total_chunks;
    uint32_t free_chunks;
    uint32_t entry_count;
    uint64_t total_frames;
    uint8_t side_b_valid;
};

struct rf_hashes {
    unsigned char live_a[SHA256_DIGEST_LENGTH];
    unsigned char source[SHA256_DIGEST_LENGTH];
    unsigned char copy[SHA256_DIGEST_LENGTH];
};

struct rf_result {
    int32_t injection_fired;
    int32_t remount_result;
    int32_t remount_writes;
    int32_t event_op;
    uint32_t event_lba;
    uint32_t event_count;
    int32_t has_target_block;
    int32_t metadata_changed;
    struct rf_info info;
    unsigned char before[RF_BLOCK];
    unsigned char intended[RF_BLOCK];
    unsigned char durable[RF_BLOCK];
    struct rf_snapshot post;
};

struct trace_event {
    int kind;
    uint32_t lba;
    uint32_t count;
    unsigned char data[RF_BLOCK];
};

union aligned_instance {
    uint64_t align;
    unsigned char bytes[RF_MAX_INSTANCE];
};
union aligned_play {
    uint64_t align;
    unsigned char bytes[TAPE_PLAY_RING_MIN];
};
union aligned_rec {
    uint64_t align;
    unsigned char bytes[TAPE_REC_RING_MIN];
};

static unsigned char *g_initial;
static unsigned char *g_trace_work;
static unsigned char *g_trace_durable;
static unsigned char *g_prefix_work;
static unsigned char *g_prefix_durable;
static size_t g_bytes;
static uint32_t g_blocks;
static int g_fixture;
static int g_mode;

static struct trace_event g_trace[RF_MAX_TRACE];
static uint32_t g_trace_count;
static bool g_trace_overflow;
static bool g_trace_active;
static uint32_t g_selected_start;
static uint32_t g_selected_count;
static uint32_t g_data_blocks;
static uint32_t g_dest_start;
static uint32_t g_slot_lba;
static uint32_t g_event_pos;

static bool g_override;
static uint32_t g_override_lba;
static unsigned char g_override_data[RF_BLOCK];
static int g_remount_writes;

static struct rf_snapshot g_pre_snapshot;
static struct rf_hashes g_hashes;

static union aligned_instance g_inst;
static union aligned_play g_play;
static union aligned_rec g_rec;
static tape_dev g_dev;

static int raw_read(const unsigned char *image, uint32_t lba,
                    uint32_t count, void *dst)
{
    uint64_t end = (uint64_t)lba + (uint64_t)count;
    if (image == NULL || dst == NULL || count == 0u || end > g_blocks) {
        return -1;
    }
    memcpy(dst, image + (size_t)lba * RF_BLOCK, (size_t)count * RF_BLOCK);
    return 0;
}

static int trace_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    (void)ctx;
    return raw_read(g_trace_work, lba, count, dst);
}

static void trace_push_flush(void)
{
    if (!g_trace_active) { return; }
    if (g_trace_count >= RF_MAX_TRACE) {
        g_trace_overflow = true;
        return;
    }
    memset(&g_trace[g_trace_count], 0, sizeof g_trace[g_trace_count]);
    g_trace[g_trace_count].kind = RF_EV_FLUSH;
    g_trace_count++;
}

static int trace_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    uint64_t end = (uint64_t)lba + (uint64_t)count;
    (void)ctx;
    if (src == NULL || count == 0u || end > g_blocks) { return -1; }

    if (g_trace_active) {
        if (count != 1u || g_trace_count >= RF_MAX_TRACE) {
            g_trace_overflow = true;
            return -1;
        }
        g_trace[g_trace_count].kind = RF_EV_WRITE;
        g_trace[g_trace_count].lba = lba;
        g_trace[g_trace_count].count = count;
        memcpy(g_trace[g_trace_count].data, src, RF_BLOCK);
        g_trace_count++;
    }

    memcpy(g_trace_work + (size_t)lba * RF_BLOCK, src,
           (size_t)count * RF_BLOCK);
    return 0;
}

static int trace_flush(void *ctx)
{
    (void)ctx;
    trace_push_flush();
    memcpy(g_trace_durable, g_trace_work, g_bytes);
    return 0;
}

static int virtual_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    unsigned char *out = dst;
    uint32_t i;
    (void)ctx;
    if (dst == NULL || count == 0u
        || (uint64_t)lba + (uint64_t)count > g_blocks) {
        return -1;
    }
    for (i = 0u; i < count; i++) {
        uint32_t q = lba + i;
        if (g_override && q == g_override_lba) {
            memcpy(out + (size_t)i * RF_BLOCK, g_override_data, RF_BLOCK);
        } else {
            memcpy(out + (size_t)i * RF_BLOCK,
                   g_prefix_durable + (size_t)q * RF_BLOCK, RF_BLOCK);
        }
    }
    return 0;
}

static int virtual_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    (void)ctx;
    (void)lba;
    (void)count;
    (void)src;
    g_remount_writes++;
    /* Phase-4 repair is not expected in this stage-0 campaign. Do not mutate
       the crash image if it nevertheless occurs; the caller treats it as a
       binding failure. */
    return 0;
}

static int virtual_flush(void *ctx)
{
    (void)ctx;
    return 0;
}

static void snapshot_from_virtual(struct rf_snapshot *out)
{
    static const uint32_t lbas[4] = {RF_A0, RF_A1, RF_B0, RF_B1};
    unsigned i;
    memset(out, 0, sizeof *out);
    out->block_count = g_blocks;
    (void)virtual_read(NULL, 0u, 1u, out->primary);
    (void)virtual_read(NULL, g_blocks - 1u, 1u, out->mirror);
    for (i = 0u; i < 4u; i++) {
        (void)virtual_read(NULL, lbas[i], 2u, out->slots[i]);
    }
}

static void snapshot_from_image(const unsigned char *image, struct rf_snapshot *out)
{
    static const uint32_t lbas[4] = {RF_A0, RF_A1, RF_B0, RF_B1};
    unsigned i;
    memset(out, 0, sizeof *out);
    out->block_count = g_blocks;
    memcpy(out->primary, image, RF_BLOCK);
    memcpy(out->mirror, image + (size_t)(g_blocks - 1u) * RF_BLOCK, RF_BLOCK);
    for (i = 0u; i < 4u; i++) {
        memcpy(out->slots[i], image + (size_t)lbas[i] * RF_BLOCK,
               2u * RF_BLOCK);
    }
}

static bool snapshot_equal(const struct rf_snapshot *a,
                           const struct rf_snapshot *b)
{
    return a->block_count == b->block_count
        && memcmp(a->primary, b->primary, RF_BLOCK) == 0
        && memcmp(a->mirror, b->mirror, RF_BLOCK) == 0
        && memcmp(a->slots, b->slots, sizeof a->slots) == 0;
}

static tape_result mount_with_callbacks(int (*read_fn)(void *, uint32_t, uint32_t, void *),
                                        int (*write_fn)(void *, uint32_t, uint32_t, const void *),
                                        int (*flush_fn)(void *),
                                        tape **out)
{
    size_t need = tape_instance_size();
    tape_result rc;
    if (need > sizeof g_inst.bytes) { return TAPE_ERR_INVALID_ARG; }
    memset(&g_inst, 0, sizeof g_inst);
    memset(&g_play, 0, sizeof g_play);
    memset(&g_rec, 0, sizeof g_rec);
    memset(&g_dev, 0, sizeof g_dev);
    g_dev.read = read_fn;
    g_dev.write = write_fn;
    g_dev.flush = flush_fn;
    g_dev.ctx = NULL;
    g_dev.block_count = g_blocks;
    rc = tape_init(g_inst.bytes, need, &g_dev,
                   g_play.bytes, sizeof g_play.bytes,
                   g_rec.bytes, sizeof g_rec.bytes, out);
    if (rc != TAPE_OK) { return rc; }
    return tape_mount(*out, TAPE_SIDE_B, 0u, NULL);
}

static int run_clean_trace(void)
{
    tape *t = NULL;
    tape_result rc;
    bool more = false;
    unsigned calls = 0u;

    memcpy(g_trace_work, g_initial, g_bytes);
    memcpy(g_trace_durable, g_initial, g_bytes);
    g_trace_count = 0u;
    g_trace_overflow = false;
    g_trace_active = false;

    rc = mount_with_callbacks(trace_read, trace_write, trace_flush, &t);
    if (rc != TAPE_OK) { return -10 - (int)rc; }

    /* Mount callbacks are not part of the operation trace. */
    g_trace_count = 0u;
    g_trace_active = true;
    do {
        more = false;
        rc = tape_respool(t, 65535u, &more);
        calls++;
        if (rc != TAPE_OK) {
            g_trace_active = false;
            return -40 - (int)rc;
        }
        if (calls > 16u) {
            g_trace_active = false;
            return -80;
        }
    } while (more);
    g_trace_active = false;
    if (g_trace_overflow) { return -81; }
    return 0;
}

static int select_pass_events(void)
{
    uint32_t want_lba = RF_CHUNK_BASE + g_dest_start * RF_BPC;
    uint32_t i, j;
    uint32_t start = UINT32_MAX;

    for (i = 0u; i < g_trace_count; i++) {
        if (g_trace[i].kind == RF_EV_WRITE
            && g_trace[i].lba == want_lba
            && g_trace[i].count == 1u) {
            start = i;
            break;
        }
    }
    if (start == UINT32_MAX) { return -90; }

    j = start;
    for (i = 0u; i < g_data_blocks; i++, j++) {
        if (j >= g_trace_count
            || g_trace[j].kind != RF_EV_WRITE
            || g_trace[j].lba != want_lba + i
            || g_trace[j].count != 1u) {
            return -91;
        }
    }
    if (j >= g_trace_count || g_trace[j].kind != RF_EV_FLUSH) { return -92; }
    j++;
    if (j >= g_trace_count || g_trace[j].kind != RF_EV_WRITE
        || g_trace[j].lba != g_slot_lba + 1u || g_trace[j].count != 1u) {
        return -93;
    }
    j++;
    if (j >= g_trace_count || g_trace[j].kind != RF_EV_FLUSH) { return -94; }
    j++;
    if (j >= g_trace_count || g_trace[j].kind != RF_EV_WRITE
        || g_trace[j].lba != g_slot_lba || g_trace[j].count != 1u) {
        return -95;
    }
    j++;
    if (j >= g_trace_count || g_trace[j].kind != RF_EV_FLUSH) { return -96; }

    g_selected_start = start;
    g_selected_count = g_data_blocks + 5u;
    return 0;
}

static void sha_region(const unsigned char *p, size_t n, unsigned char out[32])
{
    (void)SHA256(p, n, out);
}

static void compute_hashes(void)
{
    unsigned char logical[40];
    unsigned i;
    const unsigned char *final = g_trace_work;

    sha_region(g_initial + (size_t)RF_CHUNK_BASE * RF_BLOCK,
               RF_BLOCK, g_hashes.live_a);

    if (g_fixture == RF_FIX_V3_PASS1) {
        sha_region(g_initial + (size_t)(RF_CHUNK_BASE + 10u * RF_BPC) * RF_BLOCK,
                   (size_t)2u * RF_BPC * RF_BLOCK, g_hashes.source);
        sha_region(final + (size_t)(RF_CHUNK_BASE + 12u * RF_BPC) * RF_BLOCK,
                   (size_t)2u * RF_BPC * RF_BLOCK, g_hashes.copy);
    } else if (g_fixture == RF_FIX_V3_PASS2) {
        sha_region(g_initial + (size_t)(RF_CHUNK_BASE + 12u * RF_BPC) * RF_BLOCK,
                   (size_t)2u * RF_BPC * RF_BLOCK, g_hashes.source);
        sha_region(final + (size_t)(RF_CHUNK_BASE + 10u * RF_BPC) * RF_BLOCK,
                   (size_t)2u * RF_BPC * RF_BLOCK, g_hashes.copy);
    } else {
        for (i = 0u; i < 10u; i++) {
            memcpy(logical + (size_t)i * 4u,
                   g_initial + (size_t)(RF_CHUNK_BASE + (11u + i) * RF_BPC) * RF_BLOCK,
                   4u);
        }
        sha_region(logical, sizeof logical, g_hashes.source);
        sha_region(final + (size_t)(RF_CHUNK_BASE + 10u * RF_BPC) * RF_BLOCK,
                   sizeof logical, g_hashes.copy);
    }
}

static int load_file(const char *path)
{
    FILE *f;
    long n;
    size_t got;

    f = fopen(path, "rb");
    if (f == NULL) { return -1; }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return -2; }
    n = ftell(f);
    if (n <= 0 || (n % (long)RF_BLOCK) != 0) { fclose(f); return -3; }
    if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); return -4; }

    g_bytes = (size_t)n;
    g_blocks = (uint32_t)(g_bytes / RF_BLOCK);
    g_initial = malloc(g_bytes);
    g_trace_work = malloc(g_bytes);
    g_trace_durable = malloc(g_bytes);
    g_prefix_work = malloc(g_bytes);
    g_prefix_durable = malloc(g_bytes);
    if (g_initial == NULL || g_trace_work == NULL || g_trace_durable == NULL
        || g_prefix_work == NULL || g_prefix_durable == NULL) {
        fclose(f);
        return -5;
    }
    got = fread(g_initial, 1u, g_bytes, f);
    if (got != g_bytes || fclose(f) != 0) { return -6; }
    return 0;
}

void rf_close(void)
{
    free(g_initial); g_initial = NULL;
    free(g_trace_work); g_trace_work = NULL;
    free(g_trace_durable); g_trace_durable = NULL;
    free(g_prefix_work); g_prefix_work = NULL;
    free(g_prefix_durable); g_prefix_durable = NULL;
    g_bytes = 0u;
    g_blocks = 0u;
    g_trace_count = 0u;
    g_selected_count = 0u;
}

int rf_open(const char *path, int fixture, int mode)
{
    int rc;
    rf_close();
    if (path == NULL) { return -1; }
    if (fixture < RF_FIX_V3_PASS1 || fixture > RF_FIX_DECLINE) { return -2; }
    if (mode != RF_MODE_FLUSH && mode != RF_MODE_WRITE) { return -3; }

    g_fixture = fixture;
    g_mode = mode;
    if (fixture == RF_FIX_V3_PASS1) {
        g_data_blocks = 2048u; g_dest_start = 12u; g_slot_lba = RF_B1;
    } else if (fixture == RF_FIX_V3_PASS2) {
        g_data_blocks = 2048u; g_dest_start = 10u; g_slot_lba = RF_B0;
    } else {
        g_data_blocks = 1u; g_dest_start = 10u; g_slot_lba = RF_B1;
    }

    rc = load_file(path);
    if (rc != 0) { rf_close(); return rc; }
    snapshot_from_image(g_initial, &g_pre_snapshot);
    rc = run_clean_trace();
    if (rc != 0) { rf_close(); return rc; }
    rc = select_pass_events();
    if (rc != 0) { rf_close(); return rc; }
    compute_hashes();

    memcpy(g_prefix_work, g_initial, g_bytes);
    memcpy(g_prefix_durable, g_initial, g_bytes);
    g_event_pos = 0u;
    return 0;
}

int rf_get_pre_snapshot(struct rf_snapshot *out)
{
    if (out == NULL || g_initial == NULL) { return -1; }
    *out = g_pre_snapshot;
    return 0;
}

int rf_get_hashes(struct rf_hashes *out)
{
    if (out == NULL || g_initial == NULL) { return -1; }
    *out = g_hashes;
    return 0;
}

static void apply_success(uint32_t event_index)
{
    const struct trace_event *e =
        &g_trace[g_selected_start + event_index];
    if (e->kind == RF_EV_WRITE) {
        memcpy(g_prefix_work + (size_t)e->lba * RF_BLOCK, e->data, RF_BLOCK);
        if (g_mode == RF_MODE_WRITE) {
            memcpy(g_prefix_durable + (size_t)e->lba * RF_BLOCK,
                   e->data, RF_BLOCK);
        }
    } else if (e->kind == RF_EV_FLUSH) {
        memcpy(g_prefix_durable, g_prefix_work, g_bytes);
    }
}

static int target_event_index(int target, uint32_t ordinal, uint32_t *out)
{
    uint32_t q;
    if (target == RF_TARGET_CHUNK) {
        if (ordinal >= g_data_blocks) { return -1; }
        q = ordinal;
    } else if (target == RF_TARGET_CHUNK_FLUSH) {
        q = g_data_blocks;
    } else if (target == RF_TARGET_ENTRY) {
        q = g_data_blocks + 1u;
    } else if (target == RF_TARGET_ENTRY_FLUSH) {
        q = g_data_blocks + 2u;
    } else if (target == RF_TARGET_HEADER) {
        q = g_data_blocks + 3u;
    } else if (target == RF_TARGET_HEADER_FLUSH) {
        q = g_data_blocks + 4u;
    } else {
        return -2;
    }
    if (q >= g_selected_count) { return -3; }
    *out = q;
    return 0;
}

static bool block_is_metadata(uint32_t lba)
{
    return lba == RF_A0 || lba == RF_A0 + 1u
        || lba == RF_A1 || lba == RF_A1 + 1u
        || lba == RF_B0 || lba == RF_B0 + 1u
        || lba == RF_B1 || lba == RF_B1 + 1u
        || lba == 0u || lba == g_blocks - 1u;
}

static tape_result fresh_remount(struct rf_info *info)
{
    tape *t = NULL;
    tape_info got;
    tape_result rc;

    g_remount_writes = 0;
    rc = mount_with_callbacks(virtual_read, virtual_write, virtual_flush, &t);
    if (rc != TAPE_OK) { return rc; }
    rc = tape_get_info(t, &got);
    if (rc != TAPE_OK) { return rc; }

    memset(info, 0, sizeof *info);
    memcpy(info->uuid, got.uuid, 16u);
    info->total_chunks = got.total_chunks;
    info->free_chunks = got.free_chunks;
    info->entry_count = got.entry_count;
    info->total_frames = got.total_frames;
    info->side_b_valid = got.side_b_valid ? 1u : 0u;
    return TAPE_OK;
}

int rf_case(int target, uint32_t ordinal, int injection, uint32_t landed,
            struct rf_result *out)
{
    uint32_t event_index;
    const struct trace_event *e;
    struct rf_snapshot snap;
    const unsigned char *before;
    int rc;

    if (out == NULL || g_initial == NULL) { return -1; }
    rc = target_event_index(target, ordinal, &event_index);
    if (rc != 0) { return -2; }
    if (event_index < g_event_pos) { return -3; }

    while (g_event_pos < event_index) {
        apply_success(g_event_pos);
        g_event_pos++;
    }

    e = &g_trace[g_selected_start + event_index];
    memset(out, 0, sizeof *out);
    out->injection_fired = 1;

    g_override = false;
    if (e->kind == RF_EV_WRITE) {
        if (target == RF_TARGET_CHUNK_FLUSH
            || target == RF_TARGET_ENTRY_FLUSH
            || target == RF_TARGET_HEADER_FLUSH
            || (injection != RF_INJ_BEFORE
                && injection != RF_INJ_TORN
                && injection != RF_INJ_AFTER)) {
            return -4;
        }
        before = g_prefix_durable + (size_t)e->lba * RF_BLOCK;
        memcpy(out->before, before, RF_BLOCK);
        memcpy(out->intended, e->data, RF_BLOCK);

        if (injection == RF_INJ_BEFORE) {
            memcpy(out->durable, before, RF_BLOCK);
        } else if (injection == RF_INJ_TORN) {
            if (landed == 0u || landed >= RF_BLOCK) { return -5; }
            memcpy(out->durable, before, RF_BLOCK);
            memcpy(out->durable, e->data, landed);
        } else {
            if (landed != RF_BLOCK) { return -6; }
            memcpy(out->durable,
                   g_mode == RF_MODE_WRITE ? e->data : before,
                   RF_BLOCK);
        }

        out->has_target_block = 1;
        out->event_op = RF_EV_WRITE;
        out->event_lba = e->lba;
        out->event_count = e->count;
        if (memcmp(out->durable, before, RF_BLOCK) != 0) {
            g_override = true;
            g_override_lba = e->lba;
            memcpy(g_override_data, out->durable, RF_BLOCK);
        }
    } else {
        if (injection != RF_INJ_FLUSH
            || (target != RF_TARGET_CHUNK_FLUSH
                && target != RF_TARGET_ENTRY_FLUSH
                && target != RF_TARGET_HEADER_FLUSH)) {
            return -7;
        }
        out->event_op = RF_EV_FLUSH;
    }

    out->remount_result = (int32_t)fresh_remount(&out->info);
    out->remount_writes = g_remount_writes;
    snapshot_from_virtual(&snap);
    out->post = snap;
    out->metadata_changed = snapshot_equal(&snap, &g_pre_snapshot) ? 0 : 1;
    g_override = false;

    if (out->remount_result != (int32_t)TAPE_OK) {
        return 0; /* verifier owns the verdict */
    }
    if (out->remount_writes != 0) {
        return 0; /* runner classifies this as binding/product evidence */
    }
    return 0;
}
