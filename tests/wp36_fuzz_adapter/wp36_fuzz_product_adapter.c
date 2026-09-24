/*
 * wp36_fuzz_product_adapter.c — mechanical real-product binding for the
 * independently published WP-36 100,000-sequence source-slot fuzz package.
 *
 * Contract: tests/wp36_fuzz_draft8/ADAPTER.md.
 *
 * Persistent protocol:
 *   wp36_fuzz_product_adapter --fixture SOURCE.vo08
 *   HELLO<TAB>WP36-FUZZ-ADAPTER-1<TAB>product<TAB>NULL<TAB>debug
 *   SEQ ... -> RES ...
 *
 * Every sequence receives a fresh tape instance and fresh caller-owned rings.
 * The source device has a literal write == NULL. Expectations remain exclusively
 * in the verifier-owned generator/runner.
 */
#ifndef TAPE_PUBLIC_HEADER
#define TAPE_PUBLIC_HEADER "tape.h"
#endif
#include TAPE_PUBLIC_HEADER

#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef NDEBUG
#error "WP-36 fuzz product evidence requires debug assertions enabled"
#endif

#define HELLO_FORMAT "WP36-FUZZ-ADAPTER-1"
#define RESULT_FORMAT "WP36-FUZZ-RESULT-1"
#define VO_BLOCK 512u
#define VO_SLOT_BYTES 65536u
#define VO_SLOT_BLOCKS (VO_SLOT_BYTES / VO_BLOCK)
#define VO_SLOTS 4u
#define VO_HEADER 8u
#define VO_SIZE (VO_HEADER + 2u * VO_BLOCK + VO_SLOTS * VO_SLOT_BYTES)
#define LBA_A0 8u
#define INSTANCE_BYTES 262144u
#define MAX_LINE 4096u
#define MAX_OPS 32u
#define MAX_RENDER_FRAMES 64u

struct media {
    uint32_t blocks;
    unsigned char primary[VO_BLOCK];
    unsigned char mirror[VO_BLOCK];
    unsigned char slots[VO_SLOTS][VO_SLOT_BYTES];
};

static struct media g_media;
static uint64_t g_read_callbacks;
static uint64_t g_flush_callbacks;
static bool g_event_overflow;

union aligned_instance {
    uint64_t align;
    unsigned char bytes[INSTANCE_BYTES];
};
static union aligned_instance g_instance;

union aligned_ring {
    uint64_t align;
    unsigned char bytes[TAPE_PLAY_RING_MIN];
};
static union aligned_ring g_play;
static union aligned_ring g_rec;

static int16_t g_pcm[MAX_RENDER_FRAMES * TAPE_CHANNELS];

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

static void counter_inc(uint64_t *counter)
{
    if (*counter == UINT64_MAX) {
        g_event_overflow = true;
        return;
    }
    *counter += 1u;
}

static bool range_ok(uint32_t lba, uint32_t count)
{
    return count != 0u
        && (uint64_t)lba + (uint64_t)count <= (uint64_t)g_media.blocks;
}

static const unsigned char *media_block(uint32_t lba)
{
    if (lba == 0u) {
        return g_media.primary;
    }
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
    (void)ctx;

    counter_inc(&g_read_callbacks);
    if (!range_ok(lba, count)) {
        return -1;
    }

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
    counter_inc(&g_flush_callbacks);
    return 0;
}

static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0]
         | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16)
         | ((uint32_t)p[3] << 24);
}

static int media_load(const char *path)
{
    static unsigned char buf[VO_SIZE];
    FILE *f;
    size_t got;
    size_t p;
    unsigned i;

    f = fopen(path, "rb");
    if (f == NULL) {
        return -1;
    }
    got = fread(buf, 1u, sizeof buf, f);
    if (got != sizeof buf || fgetc(f) != EOF) {
        fclose(f);
        return -1;
    }
    if (fclose(f) != 0 || memcmp(buf, "VO08", 4u) != 0) {
        return -1;
    }

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

static bool parse_u64(const char *s, uint64_t *out)
{
    char *end = NULL;
    unsigned long long v;

    if (s == NULL || *s == '\0' || *s == '-') {
        return false;
    }
    errno = 0;
    v = strtoull(s, &end, 10);
    if (errno != 0 || end == s || *end != '\0') {
        return false;
    }
    *out = (uint64_t)v;
    return true;
}

static bool parse_u32(const char *s, uint32_t *out)
{
    uint64_t v;
    if (!parse_u64(s, &v) || v > (uint64_t)UINT32_MAX) {
        return false;
    }
    *out = (uint32_t)v;
    return true;
}

static bool parse_i32(const char *s, int32_t *out)
{
    char *end = NULL;
    long long v;

    if (s == NULL || *s == '\0') {
        return false;
    }
    errno = 0;
    v = strtoll(s, &end, 10);
    if (errno != 0 || end == s || *end != '\0'
        || v < (long long)INT32_MIN || v > (long long)INT32_MAX) {
        return false;
    }
    *out = (int32_t)v;
    return true;
}

static bool seed_ok(const char *s)
{
    size_t i;
    if (s == NULL || strlen(s) != 16u) {
        return false;
    }
    for (i = 0u; i < 16u; i++) {
        char c = s[i];
        bool digit = c >= '0' && c <= '9';
        bool lower = c >= 'a' && c <= 'f';
        if (!digit && !lower) {
            return false;
        }
    }
    return true;
}

static bool split_fields(char *line, char *fields[6])
{
    unsigned i;
    char *p = line;

    fields[0] = p;
    for (i = 1u; i < 6u; i++) {
        p = strchr(p, '\t');
        if (p == NULL) {
            return false;
        }
        *p = '\0';
        p++;
        fields[i] = p;
    }
    return strchr(fields[5], '\t') == NULL;
}

static bool execute_token(tape *t, const char *tok, tape_result *out)
{
    uint64_t u64;
    uint32_t u32;
    int32_t i32;

    if (strncmp(tok, "seek=", 5u) == 0) {
        if (!parse_u64(tok + 5u, &u64)) {
            return false;
        }
        *out = tape_seek(t, u64);
        return true;
    }
    if (strcmp(tok, "tell") == 0) {
        uint64_t frame = UINT64_MAX;
        *out = tape_tell(t, &frame);
        return true;
    }
    if (strncmp(tok, "rate=", 5u) == 0) {
        if (!parse_i32(tok + 5u, &i32)) {
            return false;
        }
        *out = tape_set_rate(t, i32);
        return true;
    }
    if (strncmp(tok, "render=", 7u) == 0) {
        uint32_t rendered = 0u;
        if (!parse_u32(tok + 7u, &u32) || u32 == 0u || u32 > MAX_RENDER_FRAMES) {
            return false;
        }
        *out = tape_render(t, g_pcm, u32, &rendered);
        return true;
    }
    if (strncmp(tok, "service=", 8u) == 0) {
        bool more = false;
        if (!parse_u32(tok + 8u, &u32) || u32 == 0u) {
            return false;
        }
        *out = tape_service(t, u32, &more);
        return true;
    }
    if (strcmp(tok, "status") == 0) {
        tape_status_t status;
        memset(&status, 0, sizeof status);
        *out = tape_status(t, &status);
        return true;
    }
    if (strcmp(tok, "info") == 0) {
        tape_info info;
        memset(&info, 0, sizeof info);
        *out = tape_get_info(t, &info);
        return true;
    }
    if (strncmp(tok, "side=", 5u) == 0 && tok[6] == '\0') {
        if (tok[5] == 'A') {
            *out = tape_set_side(t, TAPE_SIDE_A);
            return true;
        }
        if (tok[5] == 'B') {
            *out = tape_set_side(t, TAPE_SIDE_B);
            return true;
        }
    }
    return false;
}

static int run_sequence(char *line)
{
    char *fields[6];
    char *tok;
    uint32_t index;
    uint32_t nops;
    uint32_t executed = 0u;
    uint32_t ok = 0u;
    uint32_t underrun = 0u;
    uint32_t other = 0u;
    tape_side side;
    tape_dev dev;
    tape *t = NULL;
    tape_result rc;
    tape_result mount_rc;
    tape_result unmount_rc;
    size_t instance_size;

    if (!split_fields(line, fields)
        || strcmp(fields[0], "SEQ") != 0
        || !parse_u32(fields[1], &index)
        || !seed_ok(fields[2])
        || !parse_u32(fields[4], &nops)
        || nops == 0u || nops > MAX_OPS) {
        return 2;
    }
    if (strcmp(fields[3], "A") == 0) {
        side = TAPE_SIDE_A;
    } else if (strcmp(fields[3], "B") == 0) {
        side = TAPE_SIDE_B;
    } else {
        return 2;
    }

    memset(&dev, 0, sizeof dev);
    dev.read = source_read;
    dev.write = NULL;
    dev.flush = source_flush;
    dev.ctx = &g_media;
    dev.block_count = g_media.blocks;

    instance_size = tape_instance_size();
    if (instance_size > sizeof g_instance.bytes) {
        return 2;
    }
    memset(&g_instance, 0, sizeof g_instance);
    memset(&g_play, 0, sizeof g_play);
    memset(&g_rec, 0, sizeof g_rec);
    memset(g_pcm, 0, sizeof g_pcm);
    g_read_callbacks = 0u;
    g_flush_callbacks = 0u;
    g_event_overflow = false;

    rc = tape_init(g_instance.bytes, instance_size, &dev,
                   g_play.bytes, sizeof g_play.bytes,
                   g_rec.bytes, sizeof g_rec.bytes, &t);
    if (rc != TAPE_OK) {
        return 2;
    }

    mount_rc = tape_mount(t, side, 0u, NULL);
    if (mount_rc != TAPE_OK) {
        return 2;
    }

    tok = fields[5];
    while (executed < nops) {
        char *sep = strchr(tok, ';');
        tape_result op_rc;

        if (executed + 1u < nops) {
            if (sep == NULL) {
                return 2;
            }
            *sep = '\0';
        } else if (sep != NULL) {
            return 2;
        }
        if (*tok == '\0' || !execute_token(t, tok, &op_rc)) {
            return 2;
        }

        if (op_rc == TAPE_OK) {
            ok++;
        } else if (op_rc == TAPE_ERR_UNDERRUN) {
            underrun++;
        } else {
            other++;
        }

        executed++;
        if (executed < nops) {
            tok = sep + 1;
        }
    }

    unmount_rc = tape_unmount(t, NULL);

    printf("RES\t%s\t%lu\t%s\t%lu\t%" PRIu64 "\t%" PRIu64
           "\t%d\t%s\t%s\t%lu\t%lu,%lu\n",
           RESULT_FORMAT,
           (unsigned long)index,
           fields[2],
           (unsigned long)executed,
           g_read_callbacks,
           g_flush_callbacks,
           g_event_overflow ? 1 : 0,
           result_name(mount_rc),
           result_name(unmount_rc),
           (unsigned long)ok,
           (unsigned long)underrun,
           (unsigned long)other);
    if (fflush(stdout) != 0) {
        return 2;
    }
    return 0;
}

int main(int argc, char **argv)
{
    char line[MAX_LINE];

    if (argc != 3 || strcmp(argv[1], "--fixture") != 0) {
        fprintf(stderr, "usage: %s --fixture SOURCE.vo08\n", argv[0]);
        return 2;
    }
    if (media_load(argv[2]) != 0) {
        fprintf(stderr, "failed to load verifier fixture\n");
        return 2;
    }

    printf("HELLO\t%s\tproduct\tNULL\tdebug\n", HELLO_FORMAT);
    if (fflush(stdout) != 0) {
        return 2;
    }

    while (fgets(line, sizeof line, stdin) != NULL) {
        size_t n = strlen(line);
        int rc;

        if (n == 0u || line[n - 1u] != '\n') {
            fprintf(stderr, "overlong or unterminated protocol line\n");
            return 2;
        }
        line[n - 1u] = '\0';
        if (strcmp(line, "DONE") == 0) {
            return 0;
        }

        rc = run_sequence(line);
        if (rc != 0) {
            fprintf(stderr, "malformed sequence or product setup failure\n");
            return rc;
        }
    }

    fprintf(stderr, "protocol ended before DONE\n");
    return 2;
}
