#define _POSIX_C_SOURCE 200809L
#ifndef TAPE_PUBLIC_HEADER
#define TAPE_PUBLIC_HEADER "tape.h"
#endif
#include TAPE_PUBLIC_HEADER

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LP_BLOCK 512u
#define LP_MAX_INSTANCE 262144u
#define LP_MAX_CALLS 100000u
#define LP_MAX_CW 65536u

union aligned_instance { uint64_t align; unsigned char bytes[LP_MAX_INSTANCE]; };
union aligned_play { uint64_t align; unsigned char bytes[TAPE_PLAY_RING_MIN]; };
union aligned_rec { uint64_t align; unsigned char bytes[TAPE_REC_RING_MIN]; };

static unsigned char *g_base;
static unsigned char *g_media;
static size_t g_bytes;
static uint32_t g_blocks;
static uint64_t g_ops;
/* Schema 2's raw continuity fact: every successful write into the chunk region
   [TAPE_LBA_CHUNK_BASE, block_count - 1), one LBA per block, in callback order.
   The mirror superblock at block_count - 1 is excluded -- it is metadata, not a
   copied chunk block. Harness bookkeeping only; nothing here is engine state. */
static uint32_t g_cw[LP_MAX_CW];
static size_t g_cw_n;
static bool g_cw_overflow;
static bool g_fail_write;
static bool g_fail_flush;
static int g_src_ctx;
static int g_dst_ctx;
static union aligned_instance g_inst;
static union aligned_play g_play;
static union aligned_rec g_rec;
static tape_dev g_dev;

static const char *rn(tape_result r)
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

static bool range_ok(uint32_t lba, uint32_t count)
{
    return count != 0u && (uint64_t)lba + (uint64_t)count <= g_blocks;
}

static int rd(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    (void)ctx;
    g_ops++;
    if (dst == NULL || !range_ok(lba, count)) { return -1; }
    memcpy(dst, g_media + (size_t)lba * LP_BLOCK, (size_t)count * LP_BLOCK);
    return 0;
}

static int wr(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    (void)ctx;
    g_ops++;
    if (src == NULL || !range_ok(lba, count)) { return -1; }
    if (g_fail_write) {
        g_fail_write = false;
        return -1;
    }
    memcpy(g_media + (size_t)lba * LP_BLOCK, src, (size_t)count * LP_BLOCK);
    {
        uint32_t i;
        for (i = 0u; i < count; i++) {
            uint32_t b = lba + i;
            if (b < TAPE_LBA_CHUNK_BASE || b >= g_blocks - 1u) continue;
            if (g_cw_n >= LP_MAX_CW) { g_cw_overflow = true; continue; }
            g_cw[g_cw_n++] = b;
        }
    }
    return 0;
}

static int fl(void *ctx)
{
    (void)ctx;
    g_ops++;
    if (g_fail_flush) {
        g_fail_flush = false;
        return -1;
    }
    return 0;
}

static int dst_rd(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    (void)ctx; (void)lba; (void)count; (void)dst;
    g_ops++;
    return 0;
}
static int dst_wr(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    (void)ctx; (void)lba; (void)count; (void)src;
    g_ops++;
    return 0;
}
static int dst_fl(void *ctx) { (void)ctx; g_ops++; return 0; }

static int load_base(const char *path)
{
    FILE *f = fopen(path, "rb");
    long n;
    if (f == NULL) { return -1; }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return -1; }
    n = ftell(f);
    if (n <= 0 || (n % (long)LP_BLOCK) != 0 || fseek(f, 0, SEEK_SET) != 0) {
        fclose(f); return -1;
    }
    g_bytes = (size_t)n;
    g_blocks = (uint32_t)(g_bytes / LP_BLOCK);
    g_base = malloc(g_bytes);
    g_media = malloc(g_bytes);
    if (g_base == NULL || g_media == NULL) { fclose(f); return -1; }
    if (fread(g_base, 1u, g_bytes, f) != g_bytes || fclose(f) != 0) { return -1; }
    return 0;
}

static tape_result fresh(tape **out)
{
    size_t need = tape_instance_size();
    tape_result r;
    if (need > sizeof g_inst.bytes) { return TAPE_ERR_INVALID_ARG; }
    memcpy(g_media, g_base, g_bytes);
    memset(&g_inst, 0, sizeof g_inst);
    memset(&g_play, 0, sizeof g_play);
    memset(&g_rec, 0, sizeof g_rec);
    memset(&g_dev, 0, sizeof g_dev);
    g_ops = 0u;
    g_cw_n = 0u;
    g_fail_write = false;
    g_fail_flush = false;
    g_dev.read = rd; g_dev.write = wr; g_dev.flush = fl;
    g_dev.ctx = &g_src_ctx; g_dev.block_count = g_blocks;
    r = tape_init(g_inst.bytes, need, &g_dev,
                  g_play.bytes, sizeof g_play.bytes,
                  g_rec.bytes, sizeof g_rec.bytes, out);
    if (r != TAPE_OK) { return r; }
    r = tape_mount(*out, TAPE_SIDE_B, 0u, NULL);
    g_ops = 0u; /* matrix accounting begins after mount */
    return r;
}

/* Print "key":[lba,...] for the first n logged chunk-region writes. */
static void emit_cw(const char *key, size_t n)
{
    size_t i;
    printf("\"%s\":[", key);
    for (i = 0u; i < n; i++) {
        printf(i ? ",%lu" : "%lu", (unsigned long)g_cw[i]);
    }
    putchar(']');
}

static tape_result start_respool(tape *t, bool *more, uint64_t *before, uint64_t *after)
{
    tape_result r;
    *before = g_ops;
    *more = false;
    r = tape_respool(t, 1u, more);
    *after = g_ops;
    return r;
}

/*
 * Initiate, then keep calling at block_budget 1 until at least two chunk-region
 * writes are on the harness trace (or the operation ends). Schema 2 judges
 * continuity by that trace; probing BUSY or a continuation while it is still
 * empty would make "unchanged" and "exact prefix" hold vacuously. The fault
 * rows keep start_respool, because they need the very next device op to be the
 * injected write.
 */
static tape_result start_respool_advanced(tape *t, bool *more)
{
    uint64_t b, a;
    unsigned n = 0u;
    tape_result r = start_respool(t, more, &b, &a);
    while (r == TAPE_OK && *more && g_cw_n < 2u && n++ < 4096u) {
        r = tape_respool(t, 1u, more);
    }
    return r;
}

static tape_result continue_respool(tape *t, uint32_t budget, bool *more,
                                   uint64_t *before, uint64_t *after)
{
    tape_result r;
    *before = g_ops;
    *more = false;
    r = tape_respool(t, budget, more);
    *after = g_ops;
    return r;
}

static tape_result call_status_group(tape *t)
{
    tape_status_t st;
    tape_info info;
    uint64_t pos;
    tape_result a = tape_status(t, &st);
    tape_result b = tape_get_info(t, &info);
    tape_result c = tape_tell(t, &pos);
    if (a != TAPE_OK) return a;
    if (b != TAPE_OK) return b;
    return c;
}

static tape_result call_column(tape *t, const char *name)
{
    bool more = false;
    int16_t out[2] = {0, 0};
    uint32_t rendered = 0u, accepted = 0u;
    int16_t pcm[2] = {0, 0};
    uint8_t uuid[16] = {0};
    tape_dev dst;

    if (strcmp(name, "seek") == 0) return tape_seek(t, 0u);
    if (strcmp(name, "set_rate") == 0) return tape_set_rate(t, 0);
    if (strcmp(name, "render") == 0) return tape_render(t, out, 1u, &rendered);
    if (strcmp(name, "service") == 0) return tape_service(t, 1u, &more);
    if (strcmp(name, "status_info_tell") == 0) return call_status_group(t);
    if (strcmp(name, "arm") == 0) return tape_arm(t, TAPE_REC_OVERWRITE);
    if (strcmp(name, "feed") == 0) return tape_feed(t, pcm, 1u, &accepted);
    if (strcmp(name, "commit") == 0) return tape_commit(t);
    if (strcmp(name, "abort") == 0) return tape_abort(t);
    if (strcmp(name, "set_side") == 0) return tape_set_side(t, TAPE_SIDE_A);
    if (strcmp(name, "reset_b") == 0) return tape_reset_side_b(t);
    if (strcmp(name, "promote") == 0)
        return tape_promote(t, 1u, &more, NULL, NULL);
    if (strcmp(name, "respool") == 0)
        return tape_respool(t, 1u, &more);
    if (strcmp(name, "dup") == 0) {
        memset(&dst, 0, sizeof dst);
        dst.read = dst_rd; dst.write = dst_wr; dst.flush = dst_fl;
        dst.ctx = &g_dst_ctx; dst.block_count = g_blocks;
        return tape_dup(t, &dst, uuid, 1u, 60u, 1u, &more, NULL, NULL);
    }
    if (strcmp(name, "unmount") == 0) return tape_unmount(t, NULL);
    return TAPE_ERR_INVALID_ARG;
}

static void emit_in_progress_row(void)
{
    static const char *cols[15] = {
        "seek","set_rate","render","service","status_info_tell",
        "arm","feed","commit","abort","set_side","reset_b","promote",
        "respool","dup","unmount"
    };
    unsigned i;
    putchar('[');
    for (i = 0u; i < 15u; i++) {
        tape *t = NULL;
        bool more = false;
        uint64_t cb, ca, before, after;
        size_t cw_before, cw_after;
        tape_result r;
        (void)fresh(&t);
        (void)start_respool_advanced(t, &more);
        before = g_ops;
        cw_before = g_cw_n;
        if (strcmp(cols[i], "respool") == 0) {
            r = continue_respool(t, 1u, &more, &cb, &ca);
            after = g_ops;
            cw_after = g_cw_n;
            if (i != 0u) putchar(',');
            printf("{\"call\":\"%s\",\"result\":\"%s\",\"block_ops\":%llu,"
                   "\"progress_before\":%llu,\"progress_after\":%llu,",
                   cols[i], rn(r), (unsigned long long)(after - before),
                   (unsigned long long)cb, (unsigned long long)ca);
            emit_cw("chunk_write_lbas_before", cw_before);
            putchar(',');
            emit_cw("chunk_write_lbas_after", cw_after);
            putchar('}');
            continue;
        }
        r = call_column(t, cols[i]);
        after = g_ops;
        cw_after = g_cw_n;
        if (i != 0u) putchar(',');
        printf("{\"call\":\"%s\",\"result\":\"%s\",\"block_ops\":%llu,",
               cols[i], rn(r), (unsigned long long)(after - before));
        emit_cw("chunk_write_lbas_before", cw_before);
        putchar(',');
        emit_cw("chunk_write_lbas_after", cw_after);
        putchar('}');
    }
    putchar(']');
}

static bool make_faulted_respool(tape **out)
{
    tape *t = NULL;
    bool more = false;
    uint64_t b, a;
    tape_result r;
    if (fresh(&t) != TAPE_OK) return false;
    r = start_respool(t, &more, &b, &a);
    if (r != TAPE_OK || !more) { *out = t; return false; }
    g_fail_write = true;
    r = continue_respool(t, 1u, &more, &b, &a);
    *out = t;
    return r == TAPE_ERR_IO && !more;
}

static void emit_faulted_row(void)
{
    static const char *cols[15] = {
        "seek","set_rate","render","service","status_info_tell",
        "arm","feed","commit","abort","set_side","reset_b","promote",
        "respool","dup","unmount"
    };
    unsigned i;
    putchar('[');
    for (i = 0u; i < 15u; i++) {
        tape *t = NULL;
        uint64_t before, after;
        tape_result r;
        (void)make_faulted_respool(&t);
        before = g_ops;
        r = call_column(t, cols[i]);
        after = g_ops;
        if (i != 0u) putchar(',');
        printf("{\"call\":\"%s\",\"result\":\"%s\",\"block_ops\":%llu}",
               cols[i], rn(r), (unsigned long long)(after - before));
    }
    putchar(']');
}

static void emit_small_budget(void)
{
    tape *t = NULL;
    bool more = false;
    unsigned calls = 0u;
    uint64_t before, after;
    size_t cw_before, cw_after;
    tape_result r;
    (void)fresh(&t);
    putchar('[');
    do {
        before = g_ops;
        cw_before = g_cw_n;
        more = false;
        r = tape_respool(t, 1u, &more);
        after = g_ops;
        cw_after = g_cw_n;
        if (calls != 0u) putchar(',');
        printf("{\"result\":\"%s\",\"block_budget\":1,\"more_work\":%s,"
               "\"progress_before\":%llu,\"progress_after\":%llu,",
               rn(r), more ? "true" : "false",
               (unsigned long long)before, (unsigned long long)after);
        emit_cw("chunk_write_lbas_before", cw_before);
        putchar(',');
        emit_cw("chunk_write_lbas_after", cw_after);
        putchar('}');
        calls++;
        if (r != TAPE_OK || calls >= LP_MAX_CALLS) break;
    } while (more);
    putchar(']');
}

static void emit_zero_budget(void)
{
    tape *t = NULL;
    bool more = false;
    uint64_t before, after;
    size_t cw_b;
    tape_result r, sr;
    putchar('[');

    /* state_before/after are raw: how many chunk-region writes the harness has
       logged. A zero-budget call that did any copy work would change it. */
    (void)fresh(&t);
    before = g_ops;
    cw_b = g_cw_n;
    r = tape_respool(t, 0u, &more);
    after = g_ops;
    printf("{\"phase\":\"initiation\",\"block_budget\":0,\"result\":\"%s\","
           "\"block_ops\":%llu,\"state_before\":\"chunk_writes=%lu\",\"state_after\":\"chunk_writes=%lu\"}",
           rn(r), (unsigned long long)(after - before),
           (unsigned long)cw_b, (unsigned long)g_cw_n);

    (void)fresh(&t);
    sr = start_respool_advanced(t, &more);
    (void)sr;
    before = g_ops;
    cw_b = g_cw_n;
    r = tape_respool(t, 0u, &more);
    after = g_ops;
    printf(",{\"phase\":\"continuation\",\"block_budget\":0,\"result\":\"%s\","
           "\"block_ops\":%llu,\"state_before\":\"chunk_writes=%lu\",\"state_after\":\"chunk_writes=%lu\"}",
           rn(r), (unsigned long long)(after - before),
           (unsigned long)cw_b, (unsigned long)g_cw_n);
    putchar(']');
}

static void emit_busy_then_continue(void)
{
    tape *t = NULL;
    bool more = false;
    uint64_t before, after, cb, ca;
    size_t busy_b, busy_a, cont_b, cont_a;
    tape_result busy, cont;
    (void)fresh(&t);
    (void)start_respool_advanced(t, &more);
    before = g_ops;
    busy_b = g_cw_n;
    busy = tape_seek(t, 0u);
    after = g_ops;
    busy_a = g_cw_n;
    cont_b = g_cw_n;
    cont = continue_respool(t, 1u, &more, &cb, &ca);
    cont_a = g_cw_n;
    printf("{\"busy\":{\"result\":\"%s\",\"block_ops\":%llu,",
           rn(busy), (unsigned long long)(after - before));
    emit_cw("chunk_write_lbas_before", busy_b);
    putchar(',');
    emit_cw("chunk_write_lbas_after", busy_a);
    printf("},\"continuation\":{\"result\":\"%s\","
           "\"progress_before\":%llu,\"progress_after\":%llu,",
           rn(cont), (unsigned long long)cb, (unsigned long long)ca);
    emit_cw("chunk_write_lbas_before", cont_b);
    putchar(',');
    emit_cw("chunk_write_lbas_after", cont_a);
    printf("}}");
}

static void emit_own_failures(void)
{
    unsigned i;
    putchar('[');
    for (i = 0u; i < 2u; i++) {
        tape *t = NULL;
        bool more = false;
        uint64_t b, a;
        tape_result sr, r, state_probe;
        (void)fresh(&t);
        sr = start_respool(t, &more, &b, &a);
        if (i == 0u) g_fail_write = true;
        else g_fail_flush = true;
        more = false;
        r = tape_respool(t, 65535u, &more);
        state_probe = tape_seek(t, 0u);
        if (i != 0u) putchar(',');
        printf("{\"failure\":\"%s\",\"result\":\"%s\",\"more_work\":%s,"
               "\"state_after\":\"%s\",\"started\":%s}",
               i == 0u ? "write" : "flush", rn(r), more ? "true" : "false",
               state_probe == TAPE_ERR_FAULTED ? "FAULTED" : "NOT_FAULTED",
               sr == TAPE_OK ? "true" : "false");
    }
    putchar(']');
}

static void emit_faulted_over_armed(void)
{
    tape *t = NULL;
    int16_t pcm[2] = {0,0};
    uint32_t accepted = 0u;
    bool more = false;
    tape_status_t st;
    tape_result r, rr;
    uint64_t before, after;
    (void)fresh(&t);
    (void)tape_arm(t, TAPE_REC_OVERWRITE);
    (void)tape_feed(t, pcm, 1u, &accepted);
    g_fail_write = true;
    (void)tape_service(t, 8u, &more);
    (void)tape_status(t, &st);
    before = g_ops;
    rr = tape_respool(t, 1u, &more);
    after = g_ops;
    r = rr;
    printf("{\"armed\":%s,\"frames_owed\":%u,\"respool_result\":\"%s\","
           "\"block_ops\":%llu}",
           st.recording_armed ? "true" : "false",
           st.frames_owed ? 1u : 0u, rn(r),
           (unsigned long long)(after - before));
}

static void emit_faulted_ring_drain(void)
{
    tape *t = NULL;
    bool more = false;
    int16_t pcm[2] = {0,0};
    int16_t out[128];
    uint32_t accepted = 0u;
    uint32_t rendered = 0u;
    unsigned guard = 0u;
    bool underrun = false;
    tape_result r, abort_r;

    (void)fresh(&t);
    /* Load only one playback block so the retained ring has a finite boundary. */
    (void)tape_service(t, 1u, &more);
    (void)tape_set_rate(t, 0x00010000);
    (void)tape_arm(t, TAPE_REC_OVERWRITE);
    (void)tape_feed(t, pcm, 1u, &accepted);
    g_fail_write = true;
    (void)tape_service(t, 1u, &more);

    fputs("{\"rendered_frames\":[", stdout);
    do {
        rendered = 0u;
        r = tape_render(t, out, 64u, &rendered);
        if (guard != 0u) putchar(',');
        printf("%u", rendered);
        if (r == TAPE_ERR_UNDERRUN) underrun = true;
        guard++;
        if (rendered == 0u || guard > 16u) break;
    } while (true);
    abort_r = tape_abort(t);
    printf("],\"underrun\":%s,\"abort_result\":\"%s\"}",
           underrun ? "true" : "false", rn(abort_r));
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: %s RAW_IMAGE\n", argv[0]);
        return 2;
    }
    if (load_base(argv[1]) != 0) return 2;

    fputs("{\"format\":\"WP12A-RESPOOL-LONGOP-1\",\"in_progress_row\":", stdout);
    emit_in_progress_row();
    fputs(",\"faulted_row\":", stdout);
    emit_faulted_row();
    fputs(",\"small_budget_calls\":", stdout);
    emit_small_budget();
    fputs(",\"zero_budget\":", stdout);
    emit_zero_budget();
    fputs(",\"busy_then_continue\":", stdout);
    emit_busy_then_continue();
    fputs(",\"own_device_failures\":", stdout);
    emit_own_failures();
    fputs(",\"faulted_over_armed\":", stdout);
    emit_faulted_over_armed();
    fputs(",\"faulted_ring_drain\":", stdout);
    emit_faulted_ring_drain();
    fputs(",\"stable_continuation_args\":[],"
          "\"progress_callback_reentry_applicable\":false}\n", stdout);

    free(g_base);
    free(g_media);
    if (g_cw_overflow) {
        fprintf(stderr, "chunk-write trace overflowed %u entries\n", LP_MAX_CW);
        return 3;
    }
    return 0;
}
