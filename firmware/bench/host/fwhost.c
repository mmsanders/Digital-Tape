/*
 * fwhost.c — the firmware's portable modules, run off target (FW-1 §4, F1).
 *
 * Drives the same fw_part and fw_play code the Teensy runs, over
 * engine/port/dev_file on the host, so CI can check the partition view on
 * WP-14 image fixtures and the render loop against the WP-11 goldens without
 * hardware. host/run_checks.py builds the fixtures and judges the output; this
 * program only reports.
 *
 *   fwhost sha-selftest
 *   fwhost part  WHOLE.img [--writable]   partition view + mount, as the firmware does
 *   fwhost bare  BARE.img                 the same mount over a bare image (reference)
 *   fwhost write WHOLE.img LBA COUNT      write COUNT blocks of a pattern through the view
 *   fwhost viewio WHOLE.img               view reads/writes from stdin (partition_adapter.py)
 *   fwhost golden WHOLE.img --side A|B --from F --frames N --mode det|live -o OUT.pcm
 *                [--control flip|rate]
 *
 * --control exists only here, for F1's negative controls: `flip` alters one
 * sample after rendering, `rate` renders at 1.0x + 1 (65537). Each must make
 * the comparison fail.
 */

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "tape.h"
#include "dev_file.h"
#include "fw_part.h"
#include "fw_play.h"
#include "fw_sha256.h"

static union { uint64_t u; long double ld; void *p; unsigned char b[256u * 1024u]; } g_mem;
static unsigned char g_play[TAPE_PLAY_RING_MIN];
static unsigned char g_rec[TAPE_REC_RING_MIN];

/* A whole-card device that counts the calls the partition view makes. */
struct counting {
    tape_dev inner;
    uint32_t reads, writes, flushes, max_write_count;
};

static int c_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    struct counting *c = (struct counting *)ctx;
    c->reads++;
    return c->inner.read(c->inner.ctx, lba, count, dst);
}

static int c_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    struct counting *c = (struct counting *)ctx;
    c->writes++;
    if (count > c->max_write_count) { c->max_write_count = count; }
    return c->inner.write(c->inner.ctx, lba, count, src);
}

static int c_flush(void *ctx)
{
    struct counting *c = (struct counting *)ctx;
    c->flushes++;
    return c->inner.flush(c->inner.ctx);
}

static struct tape_dev_file g_file;
static struct counting g_count;
static tape_dev g_card;
static struct fw_part g_part;
static tape_dev g_dev;

static const char *part_name(fw_part_result r)
{
    return r == FW_PART_OK ? "OK" : r == FW_PART_IO ? "IO" : "NOT_PROVISIONED";
}

/* Open a whole image as the card and bind the partition view over it. */
static int open_whole(const char *path, int writable)
{
    tape_dev raw;
    fw_part_result pr;
    if (tape_dev_file_open(&g_file, &raw, path, writable) != 0) {
        printf("{\"open\":\"FAILED\"}\n");
        return 1;
    }
    memset(&g_count, 0, sizeof g_count);
    g_count.inner = raw;
    g_card.read = c_read;
    g_card.write = raw.write != NULL ? c_write : NULL;
    g_card.flush = c_flush;
    g_card.ctx = &g_count;
    g_card.block_count = raw.block_count;
    pr = fw_part_open(&g_part, &g_card, &g_dev, writable);
    printf("{\"part\":\"%s\"", part_name(pr));
    if (pr != FW_PART_OK) { printf("}\n"); return 2; }
    printf(",\"base\":%" PRIu32 ",\"blocks\":%" PRIu32 ",\"write_bound\":%s",
           g_part.base, g_part.blocks, g_dev.write != NULL ? "true" : "false");
    return 0;
}

static void print_mounts(const tape_dev *dev)
{
    int s;
    for (s = 0; s < 2; s++) {
        tape *t = NULL;
        tape_result r = tape_init(g_mem.b, sizeof g_mem.b, dev, g_play, sizeof g_play, g_rec, sizeof g_rec, &t);
        tape_info info;
        if (r == TAPE_OK) { r = tape_mount(t, s == 0 ? TAPE_SIDE_A : TAPE_SIDE_B, 0, NULL); }
        printf(",\"mount_%c\":%d", s == 0 ? 'A' : 'B', (int)r);
        if (r == TAPE_OK && tape_get_info(t, &info) == TAPE_OK) {
            printf(",\"frames_%c\":%" PRIu64 ",\"entries_%c\":%" PRIu32 ",\"side_b_valid_%c\":%s,\"needs_repair_%c\":%s",
                   s == 0 ? 'A' : 'B', info.total_frames, s == 0 ? 'A' : 'B', info.entry_count,
                   s == 0 ? 'A' : 'B', info.side_b_valid ? "true" : "false",
                   s == 0 ? 'A' : 'B', info.needs_repair ? "true" : "false");
        }
        if (r == TAPE_OK) { uint64_t pos; (void)tape_unmount(t, &pos); }
    }
}

static int cmd_part(int argc, char **argv)
{
    int writable = argc > 3 && strcmp(argv[3], "--writable") == 0;
    int rc = open_whole(argv[2], writable);
    if (rc == 0) {
        print_mounts(&g_dev);
        printf(",\"card_writes\":%" PRIu32 "}\n", g_count.writes);
    }
    tape_dev_file_close(&g_file);
    return rc;
}

static int cmd_bare(int argc, char **argv)
{
    tape_dev dev;
    (void)argc;
    if (tape_dev_file_open(&g_file, &dev, argv[2], 0) != 0) { printf("{\"open\":\"FAILED\"}\n"); return 1; }
    printf("{\"part\":\"BARE\",\"blocks\":%" PRIu32, dev.block_count);
    print_mounts(&dev);
    printf("}\n");
    tape_dev_file_close(&g_file);
    return 0;
}

static int cmd_write(int argc, char **argv)
{
    static uint8_t buf[64u * TAPE_BLOCK_SIZE];
    uint32_t lba, count, i;
    int rc, r;
    if (argc < 5) { return 64; }
    lba = (uint32_t)strtoul(argv[3], NULL, 10);
    count = (uint32_t)strtoul(argv[4], NULL, 10);
    if (count > 64u) { return 64; }
    for (i = 0; i < count * TAPE_BLOCK_SIZE; i++) { buf[i] = (uint8_t)(0xA5u ^ (i / TAPE_BLOCK_SIZE)); }
    rc = open_whole(argv[2], 1);
    if (rc != 0) { tape_dev_file_close(&g_file); return rc; }
    r = g_dev.write(g_dev.ctx, lba, count, buf);
    if (r == 0) { r = g_dev.flush(g_dev.ctx); }
    printf(",\"write\":%d,\"card_writes\":%" PRIu32 ",\"card_max_count\":%" PRIu32 ",\"card_flushes\":%" PRIu32 "}\n",
           r, g_count.writes, g_count.max_write_count, g_count.flushes);
    tape_dev_file_close(&g_file);
    return 0;
}

/* viewio: the partition view, driven one operation per stdin line, for
   host/partition_adapter.py (Verification's published adapter protocol):
     R LBA        -> "OK <hex of the 512-byte view block>" or "REFUSED <rc>"
     W LBA HEX    -> "OK <absolute card LBA written>"      or "REFUSED <rc>"
   LBAs are view LBAs, parsed signed and passed to the binding as uint32_t, so
   -1 reaches it as 0xFFFFFFFF, as a wild caller's would. */
static uint32_t g_last_abs;
static int v_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    g_last_abs = lba;
    return c_write(ctx, lba, count, src);
}

static int hexval(int c)
{
    return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
}

static int cmd_viewio(int argc, char **argv)
{
    static char line[2 * TAPE_BLOCK_SIZE + 64];
    uint8_t blk[TAPE_BLOCK_SIZE];
    int rc;
    (void)argc;
    rc = open_whole(argv[2], 1);
    if (rc != 0) { fflush(stdout); tape_dev_file_close(&g_file); return rc; }
    printf("}\n");
    fflush(stdout);
    g_card.write = v_write;
    while (fgets(line, sizeof line, stdin) != NULL) {
        char *p = line + 1;
        long lba = strtol(p, &p, 10);
        uint32_t i;
        int r;
        if (line[0] == 'R') {
            r = g_dev.read(g_dev.ctx, (uint32_t)lba, 1u, blk);
            if (r != 0) { printf("REFUSED %d\n", r); continue; }
            printf("OK ");
            for (i = 0; i < TAPE_BLOCK_SIZE; i++) { printf("%02x", blk[i]); }
            printf("\n");
        } else if (line[0] == 'W') {
            while (*p == ' ') { p++; }
            for (i = 0; i < TAPE_BLOCK_SIZE; i++) {
                int hi = hexval(p[2u * i]), lo = hi < 0 ? -1 : hexval(p[2u * i + 1u]);
                if (lo < 0) { break; }
                blk[i] = (uint8_t)(hi * 16 + lo);
            }
            if (i != TAPE_BLOCK_SIZE) { printf("REFUSED bad-hex\n"); continue; }
            g_last_abs = 0xFFFFFFFFu;
            r = g_dev.write(g_dev.ctx, (uint32_t)lba, 1u, blk);
            if (r == 0) { r = g_dev.flush(g_dev.ctx); }
            if (r != 0) { printf("REFUSED %d\n", r); continue; }
            printf("OK %" PRIu32 "\n", g_last_abs);
        }
        fflush(stdout);
    }
    tape_dev_file_close(&g_file);
    return 0;
}

static int cmd_sha_selftest(void)
{
    /* FIPS 180-4 examples. */
    static const struct { const char *msg; const char *hex; } v[] = {
        {"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
        {"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"},
        {"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
         "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"},
    };
    struct fw_sha256 s;
    uint8_t d[32];
    char hex[65];
    size_t i;
    int bad = 0;
    for (i = 0; i < sizeof v / sizeof v[0]; i++) {
        fw_sha256_init(&s);
        fw_sha256_update(&s, v[i].msg, strlen(v[i].msg));
        fw_sha256_final(&s, d);
        fw_sha256_hex(d, hex);
        if (strcmp(hex, v[i].hex) != 0) { printf("FAIL vector %zu: %s\n", i, hex); bad = 1; }
    }
    /* One million 'a' in uneven pieces, across block boundaries. */
    {
        static char a[1000];
        uint32_t left = 1000000u;
        memset(a, 'a', sizeof a);
        fw_sha256_init(&s);
        while (left > 0u) {
            uint32_t n = left < 997u ? left : 997u;
            fw_sha256_update(&s, a, n);
            left -= n;
        }
        fw_sha256_final(&s, d);
        fw_sha256_hex(d, hex);
        if (strcmp(hex, "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0") != 0) {
            printf("FAIL million-a: %s\n", hex);
            bad = 1;
        }
    }
    printf(bad ? "SHA256 SELFTEST FAIL\n" : "SHA256 SELFTEST PASS\n");
    return bad;
}

/* ---- F1 golden ---------------------------------------------------------- */

struct out_state {
    FILE *fp;
    struct fw_sha256 sha;
    int flip;          /* control: alter the first sample once */
};

static void sink(void *user, const int16_t *pcm, uint32_t frames)
{
    struct out_state *o = (struct out_state *)user;
    if (o->flip) {
        int16_t first = (int16_t)(pcm[0] ^ 1);
        o->flip = 0;
        fw_sha256_update(&o->sha, &first, sizeof first);
        fwrite(&first, sizeof first, 1, o->fp);
        fw_sha256_update(&o->sha, pcm + 1, (size_t)frames * TAPE_FRAME_BYTES - sizeof first);
        fwrite(pcm + 1, 1, (size_t)frames * TAPE_FRAME_BYTES - sizeof first, o->fp);
        return;
    }
    fw_sha256_update(&o->sha, pcm, (size_t)frames * TAPE_FRAME_BYTES);
    fwrite(pcm, 1, (size_t)frames * TAPE_FRAME_BYTES, o->fp);
}

static const char *opt(int argc, char **argv, const char *name)
{
    int i;
    for (i = 3; i + 1 < argc; i++) { if (strcmp(argv[i], name) == 0) { return argv[i + 1]; } }
    return NULL;
}

/* The firmware's live path, as main.cpp drives it: per audio interrupt one
   FW_AUDIO_FRAMES render, and between interrupts one main-loop service call.
   Stops at the end of the side or once `frames` (if non-zero) are out. */
static tape_result live(tape *t, uint64_t from, uint64_t frames, int32_t rate, struct out_state *o,
                        uint64_t *rendered, uint32_t *underruns)
{
    static struct fw_player p;
    int16_t pcm[FW_AUDIO_FRAMES * TAPE_CHANNELS];
    tape_result r;
    fw_player_bind(&p, t);
    r = tape_seek(t, from);
    if (r == TAPE_OK) { r = fw_player_play(&p); }
    if (r == TAPE_OK && rate != FW_RATE_1X) { r = tape_set_rate(t, rate); }
    while (r == TAPE_OK && p.playing && (frames == 0u || p.rendered < frames)) {
        uint64_t before = p.rendered;
        uint32_t got;
        bool more = false;
        fw_player_render(&p, pcm, FW_AUDIO_FRAMES);
        got = (uint32_t)(p.rendered - before);
        if (frames != 0u && before + got > frames) { got = (uint32_t)(frames - before); }
        if (got > 0u) { sink(o, pcm, got); }
        r = fw_player_service(&p, &more);
    }
    if (r == TAPE_OK && p.failed) { r = TAPE_ERR_IO; }
    *rendered = (frames != 0u && p.rendered > frames) ? frames : p.rendered;
    *underruns = p.underruns;
    return r;
}

static int cmd_golden(int argc, char **argv)
{
    static int16_t buf[FW_AUDIO_FRAMES * TAPE_CHANNELS];
    const char *side = opt(argc, argv, "--side"), *from = opt(argc, argv, "--from");
    const char *frames = opt(argc, argv, "--frames"), *mode = opt(argc, argv, "--mode");
    const char *out = opt(argc, argv, "-o"), *control = opt(argc, argv, "--control");
    struct out_state o;
    tape *t = NULL;
    tape_result r;
    uint64_t done = 0;
    uint32_t underruns = 0;
    int32_t rate = FW_RATE_1X;
    uint8_t d[32];
    char hex[65];
    int rc;

    if (!side || !from || !frames || !mode || !out) { return 64; }
    memset(&o, 0, sizeof o);
    if (control && strcmp(control, "flip") == 0) { o.flip = 1; }
    if (control && strcmp(control, "rate") == 0) { rate = FW_RATE_1X + 1; }
    o.fp = fopen(out, "wb");
    if (o.fp == NULL) { return 66; }
    fw_sha256_init(&o.sha);

    rc = open_whole(argv[2], 0);
    if (rc != 0) { fclose(o.fp); tape_dev_file_close(&g_file); return rc; }
    r = tape_init(g_mem.b, sizeof g_mem.b, &g_dev, g_play, sizeof g_play, g_rec, sizeof g_rec, &t);
    if (r == TAPE_OK) { r = tape_mount(t, side[0] == 'B' ? TAPE_SIDE_B : TAPE_SIDE_A, 0, NULL); }
    if (r == TAPE_OK && strcmp(mode, "live") == 0) {
        r = live(t, strtoull(from, NULL, 10), strtoull(frames, NULL, 10), rate, &o, &done, &underruns);
    } else if (r == TAPE_OK) {
        if (rate != FW_RATE_1X) {
            /* The deterministic loop is fixed at 1.0x; the rate control runs
               the same loop shape with the altered rate. */
            bool more = true;
            r = tape_seek(t, strtoull(from, NULL, 10));
            if (r == TAPE_OK) { r = tape_set_rate(t, rate); }
            while (r == TAPE_OK) {
                uint64_t want64 = strtoull(frames, NULL, 10) - done;
                uint32_t want = want64 < FW_AUDIO_FRAMES ? (uint32_t)want64 : FW_AUDIO_FRAMES, got = 0;
                if (want == 0u) { break; }
                more = true;
                while (r == TAPE_OK && more) { r = tape_service(t, FW_SERVICE_BUDGET, &more); }
                if (r == TAPE_OK) { r = tape_render(t, buf, want, &got); }
                if (r == TAPE_OK && got > 0u) { sink(&o, buf, got); done += got; }
                if (got < want) { break; }
            }
        } else {
            r = fw_golden_render(t, strtoull(from, NULL, 10), strtoull(frames, NULL, 10),
                                 buf, FW_AUDIO_FRAMES, sink, &o, &done);
        }
    }
    if (t != NULL) { uint64_t pos; (void)tape_unmount(t, &pos); }
    fclose(o.fp);
    fw_sha256_final(&o.sha, d);
    fw_sha256_hex(d, hex);
    printf(",\"result\":%d,\"frames\":%" PRIu64 ",\"underruns\":%" PRIu32 ",\"card_writes\":%" PRIu32 ",\"sha256\":\"%s\"}\n",
           (int)r, done, underruns, g_count.writes, hex);
    tape_dev_file_close(&g_file);
    return r == TAPE_OK ? 0 : 3;
}

int main(int argc, char **argv)
{
    if (argc >= 2 && strcmp(argv[1], "sha-selftest") == 0) { return cmd_sha_selftest(); }
    if (argc >= 3 && strcmp(argv[1], "part") == 0) { return cmd_part(argc, argv); }
    if (argc >= 3 && strcmp(argv[1], "bare") == 0) { return cmd_bare(argc, argv); }
    if (argc >= 3 && strcmp(argv[1], "write") == 0) { return cmd_write(argc, argv); }
    if (argc >= 3 && strcmp(argv[1], "viewio") == 0) { return cmd_viewio(argc, argv); }
    if (argc >= 3 && strcmp(argv[1], "golden") == 0) { return cmd_golden(argc, argv); }
    fprintf(stderr, "usage: fwhost sha-selftest | part IMG [--writable] | bare IMG | write IMG LBA COUNT |\n"
                    "       golden IMG --side A|B --from F --frames N --mode det|live -o OUT.pcm [--control flip|rate]\n");
    return 64;
}
