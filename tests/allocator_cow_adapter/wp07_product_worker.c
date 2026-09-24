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
#include <signal.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define VO_BLOCK 512u
#define VO_SLOT_BYTES 65536u
#define VO_SLOT_BLOCKS (VO_SLOT_BYTES / VO_BLOCK)
#define VO_SLOTS 4u
#define VO_HEADER 8u
#define VO_SIZE (VO_HEADER + 2u * VO_BLOCK + VO_SLOTS * VO_SLOT_BYTES)
#define LBA_A0 8u
#define LBA_CHUNK_BASE 2048u
#define MAX_CHUNKS 64u
#define CHUNK_BYTES ((size_t)TAPE_CHUNK_BLOCKS * VO_BLOCK)
#define INSTANCE_BYTES 262144u
#define MAX_FEED_FRAMES 8192u
#define MAX_EVENTS 4096u
#define SERVICE_GUARD 100000u
#define MAX_ACTIONS 16u
#define LINE_BYTES 256u

struct media {
    uint32_t blocks;
    unsigned char primary[VO_BLOCK];
    unsigned char mirror[VO_BLOCK];
    unsigned char slots[VO_SLOTS][VO_SLOT_BYTES];
    unsigned char *chunk[MAX_CHUNKS];
};
static struct media g_media;

struct write_event {
    uint32_t lba;
    uint32_t count;
};
struct event_list {
    struct write_event rows[MAX_EVENTS];
    size_t count;
    bool overflow;
};
static struct event_list *g_trace;

struct slot_snap {
    unsigned char header[64];
    unsigned char entries[TAPE_MAX_ENTRIES * TAPE_INDEX_ENTRY_BYTES];
    size_t entries_len;
};
static struct slot_snap g_pre[2];

union aligned_instance {
    uint64_t align;
    unsigned char bytes[INSTANCE_BYTES];
};
union aligned_ring {
    uint64_t align;
    unsigned char bytes[TAPE_REC_RING_MIN];
};
static union aligned_instance g_instance;
static union aligned_ring g_play;
static union aligned_ring g_rec;
static int16_t g_pcm[MAX_FEED_FRAMES * TAPE_CHANNELS];
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

static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0]
         | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16)
         | ((uint32_t)p[3] << 24);
}

static void media_free(void)
{
    unsigned i;
    for (i = 0u; i < MAX_CHUNKS; i++) {
        free(g_media.chunk[i]);
        g_media.chunk[i] = NULL;
    }
}

static int media_load(const char *path)
{
    static unsigned char buf[VO_SIZE];
    FILE *f;
    size_t got;
    size_t p;
    unsigned s;

    media_free();
    memset(&g_media, 0, sizeof g_media);

    f = fopen(path, "rb");
    if (f == NULL) {
        fprintf(stderr, "cannot open fixture %s\n", path);
        return -1;
    }
    got = fread(buf, 1u, sizeof buf, f);
    if (got != sizeof buf || fgetc(f) != EOF) {
        fclose(f);
        fprintf(stderr, "fixture is not exact VO08 size\n");
        return -1;
    }
    if (fclose(f) != 0 || memcmp(buf, "VO08", 4u) != 0) {
        fprintf(stderr, "fixture VO08 envelope invalid\n");
        return -1;
    }

    g_media.blocks = rd32(buf + 4u);
    p = VO_HEADER;
    memcpy(g_media.primary, buf + p, VO_BLOCK);
    p += VO_BLOCK;
    memcpy(g_media.mirror, buf + p, VO_BLOCK);
    p += VO_BLOCK;
    for (s = 0u; s < VO_SLOTS; s++) {
        memcpy(g_media.slots[s], buf + p, VO_SLOT_BYTES);
        p += VO_SLOT_BYTES;
    }
    return 0;
}

static bool in_range(uint32_t lba, uint32_t count)
{
    uint64_t end = (uint64_t)lba + (uint64_t)count;
    return count != 0u && end <= (uint64_t)g_media.blocks;
}

static unsigned char *block_at(uint32_t lba, bool allocate)
{
    if (lba == 0u) {
        return g_media.primary;
    }
    if (g_media.blocks != 0u && lba == g_media.blocks - 1u) {
        return g_media.mirror;
    }
    if (lba >= LBA_A0 && lba < LBA_A0 + VO_SLOTS * VO_SLOT_BLOCKS) {
        uint32_t off = lba - LBA_A0;
        return g_media.slots[off / VO_SLOT_BLOCKS]
             + (size_t)(off % VO_SLOT_BLOCKS) * VO_BLOCK;
    }
    if (lba >= LBA_CHUNK_BASE && lba < g_media.blocks - 1u) {
        uint32_t rel = lba - LBA_CHUNK_BASE;
        uint32_t chunk = rel / TAPE_CHUNK_BLOCKS;
        if (chunk >= MAX_CHUNKS) {
            return NULL;
        }
        if (g_media.chunk[chunk] == NULL && allocate) {
            g_media.chunk[chunk] = calloc(1u, CHUNK_BYTES);
            if (g_media.chunk[chunk] == NULL) {
                return NULL;
            }
        }
        if (g_media.chunk[chunk] == NULL) {
            return NULL;
        }
        return g_media.chunk[chunk]
             + (size_t)(rel % TAPE_CHUNK_BLOCKS) * VO_BLOCK;
    }
    return NULL;
}

static void record_write(uint32_t lba, uint32_t count)
{
    if (g_trace == NULL) {
        return;
    }
    if (g_trace->count >= MAX_EVENTS) {
        g_trace->overflow = true;
        return;
    }
    g_trace->rows[g_trace->count].lba = lba;
    g_trace->rows[g_trace->count].count = count;
    g_trace->count++;
}

static int media_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    unsigned char *out = dst;
    uint32_t i;
    (void)ctx;

    if (!in_range(lba, count)) {
        return -1;
    }
    for (i = 0u; i < count; i++) {
        const unsigned char *src = block_at(lba + i, false);
        if (src == NULL) {
            memset(out + (size_t)i * VO_BLOCK, 0, VO_BLOCK);
        } else {
            memcpy(out + (size_t)i * VO_BLOCK, src, VO_BLOCK);
        }
    }
    return 0;
}

static int media_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    const unsigned char *in = src;
    uint32_t i;
    (void)ctx;

    /* The verifier contract requires this observation before range/error logic. */
    record_write(lba, count);

    if (!in_range(lba, count)) {
        return -1;
    }
    for (i = 0u; i < count; i++) {
        unsigned char *dst = block_at(lba + i, true);
        if (dst == NULL) {
            return -1;
        }
        memcpy(dst, in + (size_t)i * VO_BLOCK, VO_BLOCK);
    }
    return 0;
}

static int media_flush(void *ctx)
{
    (void)ctx;
    return 0;
}

static void dev_init(void)
{
    memset(&g_dev, 0, sizeof g_dev);
    g_dev.read = media_read;
    g_dev.write = media_write;
    g_dev.flush = media_flush;
    g_dev.ctx = &g_media;
    g_dev.block_count = g_media.blocks;
}

static tape_result open_mount(tape **out)
{
    size_t need = tape_instance_size();
    tape_result r;

    if (need > sizeof g_instance.bytes) {
        fprintf(stderr, "engine instance exceeds adapter reservation\n");
        return TAPE_ERR_INVALID_ARG;
    }
    memset(&g_instance, 0, sizeof g_instance);
    memset(&g_play, 0, sizeof g_play);
    memset(&g_rec, 0, sizeof g_rec);
    memset(g_pcm, 0, sizeof g_pcm);

    r = tape_init(g_instance.bytes, need, &g_dev,
                  g_play.bytes, sizeof g_play.bytes,
                  g_rec.bytes, sizeof g_rec.bytes, out);
    if (r != TAPE_OK) {
        return r;
    }
    return tape_mount(*out, TAPE_SIDE_B, 0u, NULL);
}

static void hex_bytes(const unsigned char *p, size_t n)
{
    static const char digits[] = "0123456789abcdef";
    size_t i;
    for (i = 0u; i < n; i++) {
        unsigned v = p[i];
        putchar(digits[(v >> 4) & 0xfu]);
        putchar(digits[v & 0xfu]);
    }
}

static void capture_slot(unsigned which, struct slot_snap *out)
{
    const unsigned char *slot = g_media.slots[2u + which];
    uint32_t count = 0u;
    memcpy(out->header, slot, sizeof out->header);
    out->entries_len = 0u;
    if (memcmp(slot, "TAPEIDX\1", 8u) == 0) {
        count = rd32(slot + 16u);
        if (count <= TAPE_MAX_ENTRIES) {
            out->entries_len = (size_t)count * TAPE_INDEX_ENTRY_BYTES;
            memcpy(out->entries, slot + VO_BLOCK, out->entries_len);
        }
    }
}

static void capture_b(struct slot_snap out[2])
{
    capture_slot(0u, &out[0]);
    capture_slot(1u, &out[1]);
}

static void emit_slot(const struct slot_snap *s)
{
    fputs("{\"header_hex\":\"", stdout);
    hex_bytes(s->header, sizeof s->header);
    fputs("\",\"entries_hex\":\"", stdout);
    hex_bytes(s->entries, s->entries_len);
    fputs("\"}", stdout);
}

static void emit_current_b(void)
{
    struct slot_snap now[2];
    capture_b(now);
    putchar('[');
    emit_slot(&now[0]);
    putchar(',');
    emit_slot(&now[1]);
    putchar(']');
}

static void emit_events(const struct event_list *events)
{
    size_t i;
    putchar('[');
    for (i = 0u; i < events->count; i++) {
        if (i != 0u) {
            putchar(',');
        }
        printf("{\"lba\":%lu,\"count\":%lu}",
               (unsigned long)events->rows[i].lba,
               (unsigned long)events->rows[i].count);
    }
    putchar(']');
}

static uint64_t elapsed_ns(const struct timespec *a, const struct timespec *b)
{
    uint64_t sa = (uint64_t)a->tv_sec * UINT64_C(1000000000) + (uint64_t)a->tv_nsec;
    uint64_t sb = (uint64_t)b->tv_sec * UINT64_C(1000000000) + (uint64_t)b->tv_nsec;
    return sb - sa;
}

static void alarm_handler(int sig)
{
    (void)sig;
    _exit(124);
}

static tape_result timed_reset(tape *t, uint64_t *ns)
{
    struct sigaction sa;
    struct itimerval timer;
    struct timespec a, b;
    tape_result r;

    memset(&sa, 0, sizeof sa);
    sa.sa_handler = alarm_handler;
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGALRM, &sa, NULL) != 0) {
        fprintf(stderr, "sigaction failed\n");
        _exit(125);
    }

    memset(&timer, 0, sizeof timer);
    timer.it_value.tv_sec = 1;
    if (clock_gettime(CLOCK_MONOTONIC, &a) != 0
        || setitimer(ITIMER_REAL, &timer, NULL) != 0) {
        fprintf(stderr, "timer setup failed\n");
        _exit(125);
    }

    r = tape_reset_side_b(t);

    memset(&timer, 0, sizeof timer);
    if (setitimer(ITIMER_REAL, &timer, NULL) != 0
        || clock_gettime(CLOCK_MONOTONIC, &b) != 0) {
        fprintf(stderr, "timer teardown failed\n");
        _exit(125);
    }
    *ns = elapsed_ns(&a, &b);
    return r;
}

static tape_result service_until_done(tape *t, uint32_t budget)
{
    uint32_t guard = 0u;
    bool more = true;
    tape_result r = TAPE_OK;

    while (more) {
        more = false;
        r = tape_service(t, budget, &more);
        if (r != TAPE_OK) {
            return r;
        }
        guard++;
        if (guard > SERVICE_GUARD) {
            fprintf(stderr, "service guard exceeded\n");
            _exit(126);
        }
    }
    return r;
}

static uint64_t resolve_selector(const char *selector, uint64_t total)
{
    if (strcmp(selector, "start") == 0) return 0u;
    if (strcmp(selector, "mid") == 0) return total / 2u;
    if (strcmp(selector, "end") == 0) return total;
    if (strcmp(selector, "q1") == 0) return total / 4u;
    if (strcmp(selector, "q3") == 0) return (3u * total) / 4u;
    if (strcmp(selector, "cf_half") == 0)
        return total < (TAPE_CHUNK_FRAMES / 2u) ? total : (TAPE_CHUNK_FRAMES / 2u);
    if (strcmp(selector, "cf_boundary") == 0)
        return total < TAPE_CHUNK_FRAMES ? total : TAPE_CHUNK_FRAMES;
    if (strcmp(selector, "cf_boundary_minus") == 0)
        return total < (TAPE_CHUNK_FRAMES - 1u) ? total : (TAPE_CHUNK_FRAMES - 1u);
    if (strcmp(selector, "cf_boundary_plus") == 0)
        return total < (TAPE_CHUNK_FRAMES + 1u) ? total : (TAPE_CHUNK_FRAMES + 1u);
    fprintf(stderr, "unknown selector %s\n", selector);
    _exit(127);
}

static tape_rec_mode parse_mode(const char *mode)
{
    if (strcmp(mode, "overwrite") == 0) return TAPE_REC_OVERWRITE;
    if (strcmp(mode, "overdub") == 0) return TAPE_REC_OVERDUB;
    if (strcmp(mode, "splice") == 0) return TAPE_REC_SPLICE;
    fprintf(stderr, "unknown mode %s\n", mode);
    _exit(127);
}

struct probe_obs {
    tape_result seek;
    tape_result arm;
    tape_result feed;
    uint32_t accepted;
    tape_result service;
    tape_result abort;
    tape_result unmount;
    tape_result remount;
    struct event_list events;
};

static int run_probe(tape **pt, struct probe_obs *p)
{
    tape_info info;
    tape *t = *pt;
    memset(p, 0, sizeof *p);

    if (tape_get_info(t, &info) != TAPE_OK) {
        fprintf(stderr, "probe get_info failed\n");
        return -1;
    }

    g_trace = &p->events;
    p->seek = tape_seek(t, info.total_frames);
    p->arm = tape_arm(t, TAPE_REC_OVERWRITE);
    p->feed = tape_feed(t, g_pcm, 1u, &p->accepted);
    p->service = service_until_done(t, 1024u);
    p->abort = tape_abort(t);
    p->unmount = tape_unmount(t, NULL);
    p->remount = open_mount(pt);
    g_trace = NULL;

    if (p->events.overflow) {
        fprintf(stderr, "probe event trace overflow\n");
        return -1;
    }
    return 0;
}

static void emit_probe(const struct probe_obs *p)
{
    printf("{\"event_overflow\":false,"
           "\"seek_result\":\"%s\","
           "\"arm_result\":\"%s\","
           "\"feed_result\":\"%s\","
           "\"accepted_frames\":%lu,"
           "\"service_terminal_result\":\"%s\","
           "\"abort_result\":\"%s\","
           "\"unmount_result\":\"%s\","
           "\"remount_result\":\"%s\","
           "\"write_events\":",
           result_name(p->seek), result_name(p->arm), result_name(p->feed),
           (unsigned long)p->accepted, result_name(p->service),
           result_name(p->abort), result_name(p->unmount),
           result_name(p->remount));
    emit_events(&p->events);
    putchar('}');
}

static int run_sequence(const char *fixture)
{
    char line[LINE_BYTES];
    unsigned long seq_index;
    char seq_seed[32];
    unsigned action_count;
    unsigned i;
    tape *t = NULL;
    tape_result mount_rc;

    if (media_load(fixture) != 0) return 2;
    dev_init();
    mount_rc = open_mount(&t);
    if (mount_rc != TAPE_OK) {
        fprintf(stderr, "initial mount failed: %s\n", result_name(mount_rc));
        return 2;
    }

    if (fgets(line, sizeof line, stdin) == NULL
        || sscanf(line, "SEQ %lu %31s %u", &seq_index, seq_seed, &action_count) != 3
        || action_count == 0u || action_count > MAX_ACTIONS) {
        fprintf(stderr, "bad sequence header\n");
        return 2;
    }

    printf("{\"format\":\"WP07-COW-RESULT-1\","
           "\"seq_index\":%lu,\"seq_seed\":\"%s\","
           "\"event_overflow\":false,\"normal_exit\":true,"
           "\"initial_b_slots\":",
           seq_index, seq_seed);
    emit_current_b();
    fputs(",\"actions\":[", stdout);

    for (i = 0u; i < action_count; i++) {
        char kind;
        capture_b(g_pre);

        if (fgets(line, sizeof line, stdin) == NULL || sscanf(line, " %c", &kind) != 1) {
            fprintf(stderr, "missing action line\n");
            return 2;
        }
        if (i != 0u) putchar(',');

        if (kind == 'E') {
            char mode[16], selector[32];
            unsigned long frames, budget;
            tape_info pre_info, post_info;
            uint64_t seek_frame;
            tape_result seek_rc, arm_rc, feed_rc, service_rc, commit_rc;
            tape_result unmount_rc, remount_rc;
            uint32_t accepted = 0u;
            struct event_list events;
            struct probe_obs probe;

            if (sscanf(line, "E %15s %31s %lu %lu", mode, selector, &frames, &budget) != 4
                || frames == 0u || frames > MAX_FEED_FRAMES || budget == 0u
                || budget > UINT32_MAX) {
                fprintf(stderr, "bad edit line\n");
                return 2;
            }
            if (tape_get_info(t, &pre_info) != TAPE_OK) {
                fprintf(stderr, "pre-action get_info failed\n");
                return 2;
            }
            seek_frame = resolve_selector(selector, pre_info.total_frames);
            memset(&events, 0, sizeof events);
            g_trace = &events;
            seek_rc = tape_seek(t, seek_frame);
            arm_rc = tape_arm(t, parse_mode(mode));
            feed_rc = tape_feed(t, g_pcm, (uint32_t)frames, &accepted);
            service_rc = service_until_done(t, (uint32_t)budget);
            commit_rc = tape_commit(t);
            unmount_rc = tape_unmount(t, NULL);
            remount_rc = open_mount(&t);
            g_trace = NULL;
            if (events.overflow) {
                fprintf(stderr, "edit event trace overflow\n");
                return 2;
            }
            if (tape_get_info(t, &post_info) != TAPE_OK) {
                fprintf(stderr, "post-edit get_info failed\n");
                return 2;
            }
            if (run_probe(&t, &probe) != 0) return 2;

            printf("{\"kind\":\"edit\",\"mode\":\"%s\",\"selector\":\"%s\","
                   "\"frames\":%lu,\"service_budget\":%lu,"
                   "\"pre_b_slots\":[", mode, selector, frames, budget);
            emit_slot(&g_pre[0]); putchar(','); emit_slot(&g_pre[1]);
            printf("],\"pre_total_frames\":%llu,"
                   "\"resolved_seek\":%llu,"
                   "\"seek_result\":\"%s\",\"arm_result\":\"%s\","
                   "\"feed_result\":\"%s\",\"accepted_frames\":%lu,"
                   "\"service_terminal_result\":\"%s\","
                   "\"commit_result\":\"%s\","
                   "\"unmount_result\":\"%s\",\"remount_result\":\"%s\","
                   "\"event_overflow\":false,\"write_events\":",
                   (unsigned long long)pre_info.total_frames,
                   (unsigned long long)seek_frame,
                   result_name(seek_rc), result_name(arm_rc),
                   result_name(feed_rc), (unsigned long)accepted,
                   result_name(service_rc), result_name(commit_rc),
                   result_name(unmount_rc), result_name(remount_rc));
            emit_events(&events);
            fputs(",\"post_b_slots\":", stdout);
            emit_current_b();
            printf(",\"post_info_total_frames\":%llu,\"allocation_probe\":",
                   (unsigned long long)post_info.total_frames);
            emit_probe(&probe);
            putchar('}');
        } else if (kind == 'R') {
            tape_result reset_rc, unmount_rc, remount_rc;
            tape_info post_info;
            uint64_t ns = 0u;
            struct event_list events;
            struct probe_obs probe;

            memset(&events, 0, sizeof events);
            g_trace = &events;
            reset_rc = timed_reset(t, &ns);
            unmount_rc = tape_unmount(t, NULL);
            remount_rc = open_mount(&t);
            g_trace = NULL;
            if (events.overflow) {
                fprintf(stderr, "reset event trace overflow\n");
                return 2;
            }
            if (tape_get_info(t, &post_info) != TAPE_OK) {
                fprintf(stderr, "post-reset get_info failed\n");
                return 2;
            }
            if (run_probe(&t, &probe) != 0) return 2;

            fputs("{\"kind\":\"reset\",\"pre_b_slots\":[", stdout);
            emit_slot(&g_pre[0]); putchar(','); emit_slot(&g_pre[1]);
            printf("],\"result\":\"%s\",\"timed_out\":false,"
                   "\"elapsed_ns\":%llu,\"event_overflow\":false,"
                   "\"write_events\":",
                   result_name(reset_rc), (unsigned long long)ns);
            emit_events(&events);
            fputs(",\"post_b_slots\":", stdout);
            emit_current_b();
            printf(",\"post_info_total_frames\":%llu,"
                   "\"unmount_result\":\"%s\",\"remount_result\":\"%s\","
                   "\"allocation_probe\":",
                   (unsigned long long)post_info.total_frames,
                   result_name(unmount_rc), result_name(remount_rc));
            emit_probe(&probe);
            putchar('}');
        } else {
            fprintf(stderr, "unknown action kind\n");
            return 2;
        }
    }

    fputs("]}\n", stdout);
    if (fflush(stdout) != 0) return 2;
    media_free();
    return 0;
}

static int run_reset_stress(const char *fixture)
{
    tape *t = NULL;
    tape_result mount_rc, reset_rc, unmount_rc, remount_rc;
    struct event_list events;
    uint64_t ns = 0u;

    if (media_load(fixture) != 0) return 2;
    dev_init();
    mount_rc = open_mount(&t);
    if (mount_rc != TAPE_OK) {
        fprintf(stderr, "stress initial mount failed: %s\n", result_name(mount_rc));
        return 2;
    }

    memset(&events, 0, sizeof events);
    g_trace = &events;
    reset_rc = timed_reset(t, &ns);
    unmount_rc = tape_unmount(t, NULL);
    remount_rc = open_mount(&t);
    g_trace = NULL;
    if (events.overflow) {
        fprintf(stderr, "stress event trace overflow\n");
        return 2;
    }

    printf("{\"format\":\"WP07-RESET-STRESS-1\","
           "\"result\":\"%s\",\"timed_out\":false,"
           "\"elapsed_ns\":%llu,\"event_overflow\":false,"
           "\"write_events\":",
           result_name(reset_rc), (unsigned long long)ns);
    emit_events(&events);
    fputs(",\"post_b_slots\":", stdout);
    emit_current_b();
    printf(",\"unmount_result\":\"%s\",\"remount_result\":\"%s\"}\n",
           result_name(unmount_rc), result_name(remount_rc));
    if (fflush(stdout) != 0) return 2;
    media_free();
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: %s sequence|reset-stress FIXTURE.vo08\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "sequence") == 0) {
        return run_sequence(argv[2]);
    }
    if (strcmp(argv[1], "reset-stress") == 0) {
        return run_reset_stress(argv[2]);
    }
    fprintf(stderr, "unknown worker mode\n");
    return 2;
}
