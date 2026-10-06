/*
 * tapectl — host tooling for loading cartridges, on images and real cards.
 *
 * Normative: docs/WP11-CLI-CONTRACT.md, extended by docs/WP14-CLI-CONTRACT.md.
 * It composes the public engine API (engine/include/tape.h) over the WP-14 host
 * port (host/port/) and reimplements no engine behaviour (guardrail 12). It is
 * not a player or a library (guardrail 03). It never parses TAPEFS structures;
 * it owns only the MBR and partition 1, which the engine never sees.
 *
 * Exit status: 0 success; 1 an engine result other than TAPE_OK, named on
 * stderr, or a verify finding; 2 a usage, WAV-format, label, capacity or
 * NOT_PROVISIONED error; 3 a disk-safety refusal, with zero writes. No clock,
 * randomness or environment, except provision without --uuid/--epoch: the
 * same arguments and input bytes give byte-identical outputs and images.
 */

#include "tape.h"
#include "target.h"
#include "layout.h"
#include "entropy.h"
#include "tseam.h"

/* Engine call-site observations (test build only; no-ops when shipped). */
#ifdef TAPECTL_TEST
#define OBS_ENGINE()               tseam_engine_used()
#define OBS_PHASE(ph, sd, fr)      tseam_phase((ph), (sd), (fr))
#define OBS_MOUNT(sd, r)           tseam_mount((sd), 1, rname(r))
#define OBS_INFO(sd, i)            tseam_info((sd), (i).needs_repair, (i).side_b_valid)
#else
#define OBS_ENGINE()               ((void)0)
#define OBS_PHASE(ph, sd, fr)      ((void)0)
#define OBS_MOUNT(sd, r)           ((void)0)
#define OBS_INFO(sd, i)            ((void)0)
#endif
#include "wav.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RENDER_MAX   128u        /* contract: render requests of at most 128 frames */
#define FEED_FRAMES  1024u       /* contract: record requests of 1024 frames */
#define BUDGET       1024u       /* service and long-operation block budget */


/* One static, caller-owned block for the instance (engine-api §4). The RAM gate
   bounds tape_instance_size() at 200 KiB; main() checks it fits. */
static union { long double ld; uint64_t u; void *p; unsigned char b[256u * 1024u]; } g_mem;
static unsigned char g_play[TAPE_PLAY_RING_MIN];
static unsigned char g_rec[TAPE_REC_RING_MIN];
static int16_t g_pcm[FEED_FRAMES * 2u];

static struct target g_tgt;
static tape *g_t;

static const char *rname(tape_result r)
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

/* An engine result other than TAPE_OK ends the command with exit 1. */
#define CHECK(call) do { tape_result r_ = (call); if (r_ != TAPE_OK) { return engine_fail(#call, r_); } } while (0)

static int engine_fail(const char *what, tape_result r)
{
    fprintf(stderr, "tapectl: %s: %s\n", what, rname(r));
    return EXIT_ENGINE;
}

static int usage(const char *why)
{
    fprintf(stderr, "tapectl: %s\n", why);
    fprintf(stderr,
        "usage: tapectl format IMG --blocks N --uuid HEX32 --epoch E --label L --length-s S\n"
        "       tapectl load IMG SRC.wav\n"
        "       tapectl play IMG --side A|B --from F --frames N --rate R -o OUT.wav\n"
        "       tapectl scrub IMG --side A|B --from F --schedule R1:N1,R2:N2,... -o OUT.wav\n"
        "       tapectl record IMG --at F --mode overwrite|overdub|splice IN.wav\n"
        "       tapectl reset-b IMG | promote IMG | respool IMG\n"
        "       tapectl dump IMG --side A|B -o OUT.wav\n"
        "       tapectl provision TARGET --label L [--length-s S] [--uuid HEX32 --epoch E]\n"
        "                         [--image-bytes N] [--erase DEV]\n"
        "       tapectl verify TARGET\n"
        "TARGET (and IMG, except for format) is a bare image, a provisioned image or a whole removable device.\n");
    return EXIT_USAGE;
}

/* ------------------------------------------------------------------ parsing */

static int parse_u64(const char *s, unsigned long long max, unsigned long long *out)
{
    unsigned long long v = 0;
    if (s == NULL || *s == '\0') { return 1; }
    for (; *s; s++) {
        if (*s < '0' || *s > '9') { return 1; }
        if (v > (max - (unsigned long long)(*s - '0')) / 10u) { return 1; }
        v = v * 10u + (unsigned long long)(*s - '0');
    }
    *out = v;
    return 0;
}

static int parse_u32(const char *s, uint32_t *out)
{
    unsigned long long v;
    if (parse_u64(s, 0xFFFFFFFFull, &v)) { return 1; }
    *out = (uint32_t)v;
    return 0;
}

/* A decimal rate ("-1.5", "2", "0.25") to Q16.16, rounding half away from zero,
   in exact integer arithmetic: value = digits / 10^k, result = value * 65536. */
static int parse_rate(const char *s, size_t len, int32_t *out)
{
    unsigned long long num = 0, den = 1, q, r;
    int neg = 0, frac = 0, ndig = 0, nfrac = 0;
    size_t i = 0;

    if (len > 0 && (s[0] == '-' || s[0] == '+')) { neg = (s[0] == '-'); i = 1; }
    for (; i < len; i++) {
        char c = s[i];
        if (c == '.' && !frac) { frac = 1; continue; }
        if (c < '0' || c > '9') { return 1; }
        if (ndig >= 18 || (frac && nfrac >= 9)) { return 1; }
        num = num * 10u + (unsigned long long)(c - '0');
        ndig++;
        if (frac) { den *= 10u; nfrac++; }
    }
    if (ndig == 0) { return 1; }
    if (num / den > 32768u) { return 1; }                /* |rate| < 2^15 keeps the product small */
    q = (num * 65536u) / den;
    r = (num * 65536u) % den;
    if (2u * r >= den) { q++; }                          /* half away from zero (sign applied after) */
    if (neg ? q > 0x80000000ull : q > 0x7FFFFFFFull) { return 1; }
    *out = neg ? (int32_t)(-(long long)q) : (int32_t)q;
    return 0;
}

static int parse_side(const char *s, tape_side *out)
{
    if (s != NULL && strcmp(s, "A") == 0) { *out = TAPE_SIDE_A; return 0; }
    if (s != NULL && strcmp(s, "B") == 0) { *out = TAPE_SIDE_B; return 0; }
    return 1;
}

static int parse_uuid(const char *s, uint8_t out[16])
{
    int i;
    if (s == NULL || strlen(s) != 32u) { return 1; }
    for (i = 0; i < 32; i++) {
        char c = s[i];
        int v = (c >= '0' && c <= '9') ? c - '0' : (c >= 'a' && c <= 'f') ? c - 'a' + 10
              : (c >= 'A' && c <= 'F') ? c - 'A' + 10 : -1;
        if (v < 0) { return 1; }
        if (i % 2 == 0) { out[i / 2] = (uint8_t)(v << 4); } else { out[i / 2] |= (uint8_t)v; }
    }
    return 0;
}

/* The value after `--name` in argv, or NULL. A flag given twice is a usage error
   reported by its caller through `dup`. */
static const char *opt(int argc, char **argv, const char *name, int *dup)
{
    const char *v = NULL;
    int i;
    for (i = 0; i < argc; i++) {
        if (strcmp(argv[i], name) == 0) {
            if (v != NULL || i + 1 >= argc) { *dup = 1; return NULL; }
            v = argv[i + 1];
        }
    }
    return v;
}

/* Every argument must be a known option with its value, or a positional. */
static int check_args(int argc, char **argv, const char *const *flags, int npos)
{
    int i, pos = 0;
    for (i = 0; i < argc; i++) {
        if (argv[i][0] == '-' && argv[i][1] != '\0') {
            const char *const *f;
            for (f = flags; *f != NULL && strcmp(*f, argv[i]) != 0; f++) { }
            if (*f == NULL || i + 1 >= argc) { return 1; }
            i++;
        } else {
            pos++;
        }
    }
    return pos != npos;
}

static const char *positional(int argc, char **argv, int n)
{
    int i, pos = 0;
    for (i = 0; i < argc; i++) {
        if (argv[i][0] == '-' && argv[i][1] != '\0') { i++; continue; }
        if (pos++ == n) { return argv[i]; }
    }
    return NULL;
}

/* ------------------------------------------------------------------ engine */

/* Every engine command opens its target here: disk safety for a device, then
   the WP-14 §2 recognition. The engine sees partition 2 of a provisioned
   target, and a bare WP-11 image whole, exactly as before. */
static int open_image(const char *img)
{
    if (img == NULL) { return usage("missing target"); }
    return target_open(&g_tgt, img, 1);
}

/* play, scrub and dump only read. On a device they open read-only, with a NULL
   write callback: nothing is written to a card during playback, and the OS's
   own mount of partition 1 can stay. A bare or provisioned image keeps the
   WP-11 read-write open, so image behaviour is exactly as before. */
static int open_for_reading(const char *img)
{
    if (img == NULL) { return usage("missing target"); }
    return target_open(&g_tgt, img, target_names_device(img) ? 0 : 1);
}

static char g_side_letter;     /* the side last mounted or set, for observations */

/* Cold mount (warm start is out of scope), then tape_get_info, as observed. */
static int mount(tape_side side)
{
    tape_result r;
    char s = side == TAPE_SIDE_A ? 'A' : 'B';
    OBS_ENGINE();
    CHECK(tape_init(g_mem.b, tape_instance_size(), &g_tgt.dev, g_play, sizeof g_play, g_rec, sizeof g_rec, &g_t));
    OBS_PHASE("mount", s, -1);
    r = tape_mount(g_t, side, 0u, NULL);
    OBS_MOUNT(s, r);
    OBS_PHASE("other", 0, -1);
    if (r != TAPE_OK) { return engine_fail("tape_mount(g_t, side, 0u, NULL)", r); }
    g_side_letter = s;
#ifdef TAPECTL_TEST
    {
        tape_info info;
        if (tape_get_info(g_t, &info) == TAPE_OK) { OBS_INFO(s, info); }
    }
#endif
    return 0;
}

static int finish(int rc)
{
    if (g_t != NULL) {
        uint64_t pos;
        (void)tape_unmount(g_t, &pos);
        g_t = NULL;
    }
    /* ADR-164 §6: log which durable barrier ran. Always for a device; in the
       test build for images too. Images in the shipped build stay quiet, so
       WP-11 output is unchanged. */
#ifdef TAPECTL_TEST
    if (g_tgt.open && g_tgt.hp.flushes > 0) {
#else
    if (g_tgt.open && g_tgt.is_device && g_tgt.hp.flushes > 0) {
#endif
        fprintf(stderr, "tapectl: %llu flushes via %s\n", g_tgt.hp.flushes, g_tgt.hp.flush_how);
    }
    if (g_tgt.open && target_close(&g_tgt) != 0 && rc == 0) {
        fprintf(stderr, "tapectl: cannot close image\n");
        rc = EXIT_USAGE;
    }
    return rc;
}

/* Contract: before every render or feed request, service until more == false. */
static int service(void)
{
    bool more = true;
#ifdef TAPECTL_TEST
    {
        uint64_t pos = 0;
        (void)tape_tell(g_t, &pos);
        OBS_PHASE("service", g_side_letter, (int64_t)pos);
    }
#endif
    while (more) { CHECK(tape_service(g_t, BUDGET, &more)); }
    OBS_PHASE("other", 0, -1);
    return 0;
}

/* Renders up to `frames` at the current rate in <=128-frame requests. Stops
   early only where tape_render returns less (a boundary, or rate 0). */
static int render(struct wav_out *out, uint64_t frames)
{
    while (frames > 0u) {
        uint32_t want = frames > RENDER_MAX ? RENDER_MAX : (uint32_t)frames, got = 0;
        int rc = service();
        if (rc) { return rc; }
        CHECK(tape_render(g_t, g_pcm, want, &got));
        if (got > 0u && wav_write_frames(out, g_pcm, got) != 0) {
            fprintf(stderr, "tapectl: cannot write output WAV\n");
            return EXIT_USAGE;
        }
        if (got < want) { break; }
        frames -= got;
    }
    return 0;
}

/* Feeds all of `in` in 1024-frame requests, then services until no frames are
   owed and commits. */
static int feed_and_commit(struct wav_in *in)
{
    tape_status_t st;
    int bad = 0;

    for (;;) {
        uint32_t n = wav_read_frames(in, g_pcm, FEED_FRAMES, &bad), done = 0;
        if (bad) { fprintf(stderr, "tapectl: truncated WAV data\n"); return EXIT_USAGE; }
        if (n == 0u) { break; }
        while (done < n) {
            uint32_t acc = 0;
            int rc = service();
            if (rc) { return rc; }
            CHECK(tape_feed(g_t, g_pcm + (size_t)done * 2u, n - done, &acc));
            done += acc;
        }
    }
    OBS_PHASE("service", g_side_letter, -1);
    do {
        bool more = true;
        CHECK(tape_service(g_t, BUDGET, &more));
        CHECK(tape_status(g_t, &st));
    } while (st.frames_owed);
    OBS_PHASE("other", 0, -1);
    CHECK(tape_commit(g_t));
    return 0;
}

static int run_long(int promote)
{
    bool more = true;
    while (more) {
        if (promote) { CHECK(tape_promote(g_t, BUDGET, &more, NULL, NULL)); }
        else         { CHECK(tape_respool(g_t, BUDGET, &more)); }
    }
    return 0;
}

/* ------------------------------------------------------------------ commands */

/* format and its image: refused for a device or an already provisioned image. */
static int bare_only(const char *img)
{
    uint8_t lba0[512];
    struct hport hp;
    int provisioned = 0;

    if (target_names_device(img)) {
        fprintf(stderr, "tapectl: format is for bare images. Use provision for a card.\n");
        return 1;
    }
    if (hport_classify(img) == HPORT_REGULAR && hport_open(&hp, img, 0, 0) == 0) {
        provisioned = hp.bytes >= 512u && hport_read(&hp, 0, lba0, 512) == 0
                      && mbr_is_layout(lba0, hp.bytes / 512u);
        (void)hport_close(&hp);
    }
    if (provisioned) {
        fprintf(stderr, "tapectl: %s is a provisioned image. Use provision.\n", img);
        return 1;
    }
    return 0;
}

/* WP-14 A7: refuse, before any write, a source longer than the label. The
   cartridge's nominal length is read through a read-only binding, so even a
   mount that would otherwise repair a superblock writes nothing. */
static int capacity_check(uint32_t src_frames)
{
    tape_dev ro = g_tgt.dev;
    tape_info info;
    uint64_t limit, over, secs;
    uint32_t len;

    ro.write = NULL;
    OBS_ENGINE();
    CHECK(tape_init(g_mem.b, tape_instance_size(), &ro, g_play, sizeof g_play, g_rec, sizeof g_rec, &g_t));
    OBS_PHASE("mount", 'A', -1);
    {
        tape_result r = tape_mount(g_t, TAPE_SIDE_A, 0u, NULL);
        OBS_MOUNT('A', r);
        OBS_PHASE("other", 0, -1);
        if (r != TAPE_OK) { return engine_fail("tape_mount(capacity)", r); }
    }
    CHECK(tape_get_info(g_t, &info));
    OBS_INFO('A', info);
    {
        uint64_t pos;
        (void)tape_unmount(g_t, &pos);
        g_t = NULL;
    }
    len = info.nominal_length_s;
    limit = (uint64_t)len * WAV_RATE;
    if ((uint64_t)src_frames <= limit) { return 0; }
    over = (uint64_t)src_frames - limit;
    secs = (over + WAV_RATE - 1u) / WAV_RATE;           /* #384 Q8: round up */
    fprintf(stderr, "tapectl: Too long by ");
    if (secs >= 60u) { fprintf(stderr, "%llu min", (unsigned long long)(secs / 60u)); }
    if (secs >= 60u && secs % 60u) { fprintf(stderr, " "); }
    if (secs % 60u || secs < 60u) { fprintf(stderr, "%llu s", (unsigned long long)(secs % 60u)); }
    if (len % 60u == 0u) { fprintf(stderr, " for a %lu-minute cartridge\n", (unsigned long)(len / 60u)); }
    else                 { fprintf(stderr, " for a %lu-second cartridge\n", (unsigned long)len); }
    return EXIT_USAGE;
}

static int cmd_format(int argc, char **argv)
{
    static const char *const flags[] = {"--blocks", "--uuid", "--epoch", "--label", "--length-s", NULL};
    uint8_t uuid[16];
    uint32_t blocks, epoch, length;
    const char *label;
    int dup = 0;

    if (check_args(argc, argv, flags, 1)) { return usage("format: bad arguments"); }
    label = opt(argc, argv, "--label", &dup);
    if (parse_u32(opt(argc, argv, "--blocks", &dup), &blocks) || parse_uuid(opt(argc, argv, "--uuid", &dup), uuid)
        || parse_u32(opt(argc, argv, "--epoch", &dup), &epoch) || parse_u32(opt(argc, argv, "--length-s", &dup), &length)
        || label == NULL || dup) {
        return usage("format: bad or missing option");
    }
    /* WP-14 §4: format stays bare-image only. */
    if (bare_only(positional(argc, argv, 0))) { return EXIT_USAGE; }
    if (hport_create(&g_tgt.hp, positional(argc, argv, 0), (uint64_t)blocks * TAPE_BLOCK_SIZE) != 0) {
        fprintf(stderr, "tapectl: cannot create image\n");
        return EXIT_USAGE;
    }
    g_tgt.open = 1;
    partview_bind(&g_tgt.view, &g_tgt.dev, &g_tgt.hp, 0, blocks, 1);
    OBS_ENGINE();
    CHECK(tape_format(&g_tgt.dev, uuid, epoch, label, length));
    return 0;
}

static int cmd_load(int argc, char **argv)
{
    static const char *const flags[] = {NULL};
    struct wav_in in;
    char err[96];
    int rc;

    if (check_args(argc, argv, flags, 2)) { return usage("load: bad arguments"); }
    if (wav_open_read(&in, positional(argc, argv, 1), err, sizeof err)) { return usage(err); }
    rc = open_image(positional(argc, argv, 0));
    if (!rc) { rc = capacity_check(in.frames); }
    if (!rc) { rc = mount(TAPE_SIDE_A); }
    if (!rc) {
        tape_result r = tape_set_side(g_t, TAPE_SIDE_B);
        g_side_letter = 'B';
        if (r == TAPE_OK) { r = tape_seek(g_t, 0u); }
        if (r == TAPE_OK) { r = tape_arm(g_t, TAPE_REC_OVERWRITE); }
        rc = (r == TAPE_OK) ? feed_and_commit(&in) : engine_fail("load", r);
    }
    if (!rc) { rc = run_long(1); }
    wav_close_read(&in);
    return rc;
}

static int play_common(int argc, char **argv, int scrub)
{
    static const char *const pflags[] = {"--side", "--from", "--frames", "--rate", "-o", NULL};
    static const char *const sflags[] = {"--side", "--from", "--schedule", "-o", NULL};
    struct wav_out out;
    unsigned long long from, frames = 0;
    tape_side side;
    int32_t rate = 0;
    const char *sched = NULL, *path;
    char err[96];
    int dup = 0, rc;

    if (check_args(argc, argv, scrub ? sflags : pflags, 1)) { return usage("play/scrub: bad arguments"); }
    path = opt(argc, argv, "-o", &dup);
    if (parse_side(opt(argc, argv, "--side", &dup), &side) || parse_u64(opt(argc, argv, "--from", &dup), 0xFFFFFFFFull, &from)
        || path == NULL) {
        return usage("play/scrub: bad or missing option");
    }
    if (scrub) {
        sched = opt(argc, argv, "--schedule", &dup);
        if (sched == NULL) { return usage("scrub: missing --schedule"); }
    } else {
        const char *r = opt(argc, argv, "--rate", &dup);
        if (parse_u64(opt(argc, argv, "--frames", &dup), 0xFFFFFFFFull, &frames) || r == NULL
            || parse_rate(r, strlen(r), &rate)) {
            return usage("play: bad or missing --frames/--rate");
        }
    }
    if (dup) { return usage("play/scrub: option given twice"); }
    /* Validate the whole schedule before touching the image or the output. */
    if (scrub) {
        const char *p = sched;
        while (*p) {
            const char *colon = strchr(p, ':'), *end = strchr(p, ',');
            unsigned long long n;
            char nbuf[24];
            size_t nlen;
            if (end == NULL) { end = p + strlen(p); }
            if (colon == NULL || colon > end || parse_rate(p, (size_t)(colon - p), &rate)) { return usage("scrub: bad schedule"); }
            nlen = (size_t)(end - colon - 1);
            if (nlen == 0 || nlen >= sizeof nbuf) { return usage("scrub: bad schedule"); }
            memcpy(nbuf, colon + 1, nlen); nbuf[nlen] = '\0';
            if (parse_u64(nbuf, 0xFFFFFFFFull, &n)) { return usage("scrub: bad schedule"); }
            p = (*end == ',') ? end + 1 : end;
            if (*end == ',' && *p == '\0') { return usage("scrub: bad schedule"); }
        }
    }

    rc = open_for_reading(positional(argc, argv, 0));
    if (rc) { return rc; }
    rc = mount(side);
    if (rc) { return rc; }
    CHECK(tape_seek(g_t, from));
    if (wav_open_write(&out, path, err, sizeof err)) { return usage(err); }
    if (!scrub) {
        tape_result r = tape_set_rate(g_t, rate);
        rc = (r == TAPE_OK) ? render(&out, frames) : engine_fail("tape_set_rate", r);
    } else {
        const char *p = sched;
        while (!rc && *p) {
            const char *colon = strchr(p, ':'), *end = strchr(p, ',');
            unsigned long long n;
            char nbuf[24];
            tape_result r;
            if (end == NULL) { end = p + strlen(p); }
            (void)parse_rate(p, (size_t)(colon - p), &rate);
            memcpy(nbuf, colon + 1, (size_t)(end - colon - 1)); nbuf[end - colon - 1] = '\0';
            (void)parse_u64(nbuf, 0xFFFFFFFFull, &n);
            r = tape_set_rate(g_t, rate);
            rc = (r == TAPE_OK) ? render(&out, n) : engine_fail("tape_set_rate", r);
            p = (*end == ',') ? end + 1 : end;
        }
    }
    if (wav_close_write(&out) != 0 && !rc) {
        fprintf(stderr, "tapectl: cannot finish output WAV\n");
        rc = EXIT_USAGE;
    }
    return rc;
}

static int cmd_record(int argc, char **argv)
{
    static const char *const flags[] = {"--at", "--mode", NULL};
    struct wav_in in;
    unsigned long long at;
    tape_rec_mode mode;
    const char *m;
    char err[96];
    int dup = 0, rc;

    if (check_args(argc, argv, flags, 2)) { return usage("record: bad arguments"); }
    m = opt(argc, argv, "--mode", &dup);
    if (parse_u64(opt(argc, argv, "--at", &dup), 0xFFFFFFFFull, &at) || m == NULL || dup) {
        return usage("record: bad or missing option");
    }
    if (strcmp(m, "overwrite") == 0) { mode = TAPE_REC_OVERWRITE; }
    else if (strcmp(m, "overdub") == 0) { mode = TAPE_REC_OVERDUB; }
    else if (strcmp(m, "splice") == 0) { mode = TAPE_REC_SPLICE; }
    else { return usage("record: --mode must be overwrite, overdub or splice"); }
    if (wav_open_read(&in, positional(argc, argv, 1), err, sizeof err)) { return usage(err); }
    rc = open_image(positional(argc, argv, 0));
    if (!rc) { rc = mount(TAPE_SIDE_A); }
    if (!rc) {
        tape_result r = tape_set_side(g_t, TAPE_SIDE_B);
        g_side_letter = 'B';
        if (r == TAPE_OK) { r = tape_seek(g_t, at); }
        if (r == TAPE_OK) { r = tape_arm(g_t, mode); }
        rc = (r == TAPE_OK) ? feed_and_commit(&in) : engine_fail("record", r);
    }
    wav_close_read(&in);
    return rc;
}

static int cmd_simple(int argc, char **argv, const char *which)
{
    int rc;
    if (argc != 1) { return usage("expected exactly one IMG argument"); }
    rc = open_image(argv[0]);
    if (!rc) { rc = mount(TAPE_SIDE_A); }
    if (rc) { return rc; }
    if (strcmp(which, "reset-b") == 0) { CHECK(tape_reset_side_b(g_t)); return 0; }
    return run_long(strcmp(which, "promote") == 0);
}

static int cmd_dump(int argc, char **argv)
{
    static const char *const flags[] = {"--side", "-o", NULL};
    struct wav_out out;
    tape_info info;
    tape_side side;
    const char *path;
    char err[96];
    int dup = 0, rc;

    if (check_args(argc, argv, flags, 1)) { return usage("dump: bad arguments"); }
    path = opt(argc, argv, "-o", &dup);
    if (parse_side(opt(argc, argv, "--side", &dup), &side) || path == NULL || dup) {
        return usage("dump: bad or missing option");
    }
    rc = open_for_reading(positional(argc, argv, 0));
    if (!rc) { rc = mount(side); }
    if (rc) { return rc; }
    CHECK(tape_get_info(g_t, &info));
    CHECK(tape_seek(g_t, 0u));
    CHECK(tape_set_rate(g_t, 65536));
    if (wav_open_write(&out, path, err, sizeof err)) { return usage(err); }
    rc = render(&out, info.total_frames);
    if (wav_close_write(&out) != 0 && !rc) {
        fprintf(stderr, "tapectl: cannot finish output WAV\n");
        rc = EXIT_USAGE;
    }
    return rc;
}

/* ---------------------------------------------------------------- provision */

/* UTF-8, 1-32 bytes (WP-14 §3). Longer is refused, never truncated. */
static int label_ok(const char *s)
{
    size_t n = strlen(s), i = 0;
    if (n < 1u || n > 32u) { return 0; }
    while (i < n) {
        unsigned char c = (unsigned char)s[i];
        uint32_t cp;
        size_t k, j;
        if (c < 0x80u) { i++; continue; }
        if ((c & 0xE0u) == 0xC0u)      { k = 1; cp = c & 0x1Fu; }
        else if ((c & 0xF0u) == 0xE0u) { k = 2; cp = c & 0x0Fu; }
        else if ((c & 0xF8u) == 0xF0u) { k = 3; cp = c & 0x07u; }
        else { return 0; }
        if (i + k > n - 1u) { return 0; }
        for (j = 1; j <= k; j++) {
            unsigned char cc = (unsigned char)s[i + j];
            if ((cc & 0xC0u) != 0x80u) { return 0; }
            cp = (cp << 6) | (cc & 0x3Fu);
        }
        if ((k == 1u && cp < 0x80u) || (k == 2u && cp < 0x800u) || (k == 3u && (cp < 0x10000u || cp > 0x10FFFFu))
            || (cp >= 0xD800u && cp <= 0xDFFFu)) { return 0; }
        i += k + 1u;
    }
    return 1;
}

/* A device that answers nothing: used only to ask tape_format whether
   GEOMETRY_OK holds, before a single byte is written (WP-14 §3 order of work).
   tape_format checks geometry before any callback; past it, the first
   callback fails and the call returns TAPE_ERR_IO. */
static int dry_rw(void *ctx, uint32_t lba, uint32_t count, void *buf) { (void)ctx; (void)lba; (void)count; (void)buf; return 1; }
static int dry_w(void *ctx, uint32_t lba, uint32_t count, const void *buf) { (void)ctx; (void)lba; (void)count; (void)buf; return 1; }
static int dry_flush(void *ctx) { (void)ctx; return 1; }

static int put_p1(void *user, uint32_t sector, const uint8_t data[512])
{
    struct hport *hp = (struct hport *)user;
    return hport_write(hp, ((uint64_t)LAYOUT_P1_START + sector) * 512u, data, 512);
}

static int io_fail(const char *what)
{
    fprintf(stderr, "tapectl: provision: cannot %s\n", what);
    return EXIT_ENGINE;
}

static int cmd_provision(int argc, char **argv)
{
    static const char *const flags[] = {"--label", "--length-s", "--uuid", "--epoch", "--image-bytes", "--erase", NULL};
    const char *path, *label, *s_len, *s_uuid, *s_epoch, *s_bytes, *erase;
    unsigned long long image_bytes = 0;
    uint64_t sectors;
    uint32_t length = 3600u, epoch = 0, p2;
    uint8_t uuid[16], lba0[512], mbr[512];
    int dup = 0, is_dev, generated = 0, i, nonzero = 0, rc;
    tape_dev dry;
    tape_result r;

    if (check_args(argc, argv, flags, 1)) { return usage("provision: bad arguments"); }
    path = positional(argc, argv, 0);
    label = opt(argc, argv, "--label", &dup);
    s_len = opt(argc, argv, "--length-s", &dup);
    s_uuid = opt(argc, argv, "--uuid", &dup);
    s_epoch = opt(argc, argv, "--epoch", &dup);
    s_bytes = opt(argc, argv, "--image-bytes", &dup);
    erase = opt(argc, argv, "--erase", &dup);
    if (dup) { return usage("provision: option given twice"); }
    if (label == NULL || !label_ok(label)) { return usage("provision: --label must be 1 to 32 bytes of UTF-8"); }
    if (s_len != NULL && parse_u32(s_len, &length)) { return usage("provision: bad --length-s"); }
    if ((s_uuid == NULL) != (s_epoch == NULL)) { return usage("provision: give --uuid and --epoch together, or neither"); }
    if (s_uuid != NULL && (parse_uuid(s_uuid, uuid) || parse_u32(s_epoch, &epoch))) {
        return usage("provision: bad --uuid or --epoch");
    }
    is_dev = target_names_device(path);
    if (is_dev && s_bytes != NULL) { return usage("provision: --image-bytes is for an image, not a device"); }
    if (!is_dev) {
        if (s_bytes == NULL || parse_u64(s_bytes, ~0ull, &image_bytes) || image_bytes % 512u != 0u) {
            return usage("provision: an image needs --image-bytes N, a multiple of 512");
        }
    }

    /* 1. Every §5 rule first: zero writes on refusal. */
    if (is_dev) {
        rc = target_safety(path, 1, erase, 1);
        if (rc) { return rc; }
        memset(&g_tgt, 0, sizeof g_tgt);
        if (hport_open(&g_tgt.hp, path, 1, 1) != 0) {
            fprintf(stderr, "tapectl: cannot open device %s for writing (%s)\n", path, hport_error());
            return EXIT_USAGE;
        }
        g_tgt.open = 1;
        g_tgt.is_device = 1;
        sectors = g_tgt.hp.bytes / 512u;
#ifdef TAPECTL_TEST
        tseam_target(path, 1, g_tgt.hp.bytes);
#endif
    } else {
        sectors = image_bytes / 512u;
    }
    if (sectors > LAYOUT_P2_START && sectors - LAYOUT_P2_START > 0xFFFFFFFFull) {
        return usage("provision: target too large for partition 2");
    }
    p2 = sectors > LAYOUT_P2_START ? (uint32_t)(sectors - LAYOUT_P2_START) : 0u;

    if (s_uuid == NULL) {
        if (entropy_uuid(uuid) != 0 || entropy_epoch(&epoch) != 0) { return io_fail("get a UUID and epoch from the OS"); }
        generated = 1;
    }

    /* 2. GEOMETRY_OK for partition 2, asked of the engine itself: zero writes. */
    dry.read = dry_rw; dry.write = dry_w; dry.flush = dry_flush; dry.ctx = NULL; dry.block_count = p2;
    OBS_ENGINE();
    r = tape_format(&dry, uuid, epoch, label, length);
    if (r != TAPE_ERR_IO) { return engine_fail("provision", r == TAPE_OK ? TAPE_ERR_IO : r); }

    if (!is_dev) {
        if (hport_create(&g_tgt.hp, path, image_bytes) != 0) {
            fprintf(stderr, "tapectl: cannot create image %s\n", path);
            return EXIT_USAGE;
        }
        g_tgt.open = 1;
#ifdef TAPECTL_TEST
        tseam_target(path, 0, image_bytes);
#endif
    }

    /* 3. Zero LBA 0 if it is not already zero, so an interrupted provision is
          never a provisioned card. */
    if (hport_read(&g_tgt.hp, 0, lba0, 512) != 0) { return io_fail("read LBA 0"); }
    for (i = 0; i < 512; i++) { nonzero |= lba0[i]; }
    if (nonzero) {
        memset(lba0, 0, sizeof lba0);
        if (hport_write(&g_tgt.hp, 0, lba0, 512) != 0 || hport_flush(&g_tgt.hp) != 0) { return io_fail("clear LBA 0"); }
    }

    /* 4. Partition 2 via tape_format (the engine flushes its own writes). */
    partview_bind(&g_tgt.view, &g_tgt.dev, &g_tgt.hp, LAYOUT_P2_START, p2, 1);
    CHECK(tape_format(&g_tgt.dev, uuid, epoch, label, length));

    /* 5. Partition 1, then flush. */
    if (fat_build_p1(put_p1, &g_tgt.hp, label, uuid, epoch) != 0 || hport_flush(&g_tgt.hp) != 0) {
        return io_fail("write partition 1");
    }

    /* 6. The MBR last: it is the card's identity. */
    if (mbr_build(mbr, uuid, sectors) != 0) { return io_fail("build the MBR"); }
    if (hport_write(&g_tgt.hp, 0, mbr, 512) != 0 || hport_flush(&g_tgt.hp) != 0) { return io_fail("write the MBR"); }

    if (generated) {
        printf("uuid ");
        for (i = 0; i < 16; i++) { printf("%02x", uuid[i]); }
        printf("\nepoch %lu\n", (unsigned long)epoch);
    }
    return 0;
}

/* ------------------------------------------------------------------- verify */

/* One side of verify: cold mount, then read every referenced block through the
   engine (dump to nowhere). Results are collected, not printed, so cmd_verify
   can emit findings in the contract's order. */
struct side_result {
    tape_result mount;          /* TAPE_OK, or the MOUNT finding */
    int have_info;
    tape_info info;
    int read_error;             /* READ_ERROR at frame `frame` */
    uint64_t frame;
};

static void verify_side(tape_side side, struct side_result *s)
{
    tape_result r;
    uint64_t done = 0;

    char letter = side == TAPE_SIDE_A ? 'A' : 'B';

    (void)letter;
    memset(s, 0, sizeof *s);
    OBS_ENGINE();
    r = tape_init(g_mem.b, tape_instance_size(), &g_tgt.dev, g_play, sizeof g_play, g_rec, sizeof g_rec, &g_t);
    OBS_PHASE("mount", letter, -1);
    if (r == TAPE_OK) { r = tape_mount(g_t, side, 0u, NULL); OBS_MOUNT(letter, r); }
    OBS_PHASE("other", 0, -1);
    s->mount = r;
    if (r != TAPE_OK) { g_t = NULL; return; }          /* a failing mount is not read */
    s->have_info = tape_get_info(g_t, &s->info) == TAPE_OK;
    if (!s->have_info) { memset(&s->info, 0, sizeof s->info); }
    else { OBS_INFO(letter, s->info); }
    r = tape_seek(g_t, 0u);
    if (r == TAPE_OK) { r = tape_set_rate(g_t, 65536); }
    while (r == TAPE_OK && done < s->info.total_frames) {
        uint64_t left = s->info.total_frames - done;
        uint32_t want = left > RENDER_MAX ? RENDER_MAX : (uint32_t)left, got = 0;
        bool more = true;
        OBS_PHASE("service", letter, (int64_t)done);
        while (r == TAPE_OK && more) { r = tape_service(g_t, BUDGET, &more); }
        OBS_PHASE("other", 0, -1);
        if (r == TAPE_OK) { r = tape_render(g_t, g_pcm, want, &got); }
        if (r == TAPE_OK && got == 0u) { break; }
        done += got;
    }
    if (r != TAPE_OK) {
        /* Reported as READ_ERROR only: verify's output is exactly its findings. */
        s->read_error = 1;
        s->frame = done;
    }
    {
        uint64_t pos;
        (void)tape_unmount(g_t, &pos);
        g_t = NULL;
    }
}

/* Findings, in docs/WP14-CLI-CONTRACT.md §4.1 table order (ADR-164):
   MBR_LAYOUT, PARTITION_TYPE, PARTITION_TRUNCATED; MOUNT for each failed side,
   A before B; NEEDS_REPAIR; SIDE_B_DEGRADED; READ_ERROR by side, then frame. */
static int cmd_verify(int argc, char **argv)
{
    static const char *const flags[] = {NULL};
    struct side_result sr[2];
    const struct side_result *state = NULL;
    unsigned mf;
    int have_view, n = 0, rc, i;

    if (check_args(argc, argv, flags, 1)) { return usage("verify: bad arguments"); }
    rc = target_open_verify(&g_tgt, positional(argc, argv, 0), &mf, &have_view);
    if (rc) { return rc; }
    if (mf & MBR_F_LAYOUT)    { printf("MBR_LAYOUT\n"); n++; }
    if (mf & MBR_F_TYPE)      { printf("PARTITION_TYPE\n"); n++; }
    if (mf & MBR_F_TRUNCATED) { printf("PARTITION_TRUNCATED\n"); n++; }
    if (have_view) {
        verify_side(TAPE_SIDE_A, &sr[0]);
        verify_side(TAPE_SIDE_B, &sr[1]);
        for (i = 0; i < 2; i++) {
            if (sr[i].mount != TAPE_OK) { printf("MOUNT %s\n", rname(sr[i].mount)); n++; }
        }
        {
            int repair = 0, degraded = 0;
            for (i = 0; i < 2; i++) {
                if (sr[i].mount == TAPE_OK && sr[i].have_info) {
                    repair |= sr[i].info.needs_repair;
                    degraded |= !sr[i].info.side_b_valid;
                    state = &sr[i];
                }
            }
            (void)state;
            if (repair)   { printf("NEEDS_REPAIR\n"); n++; }
            if (degraded) { printf("SIDE_B_DEGRADED\n"); n++; }
        }
        for (i = 0; i < 2; i++) {
            if (sr[i].read_error) {
                printf("READ_ERROR SIDE %c FRAME %llu\n", i == 0 ? 'A' : 'B', (unsigned long long)sr[i].frame);
                n++;
            }
        }
    }
    if (n == 0) { printf("OK\n"); return 0; }
    return EXIT_ENGINE;
}

#ifdef TAPECTL_TEST
/* tapectl-test only: print what the real platform probe sees for DEV, in the
   facts-file format, plus the policy's verdict. The probe runs; the seam does
   not. Lets CI check the probe on loop devices and disk images. */
static int cmd_probe(int argc, char **argv)
{
    struct device_facts f;
    int i;
    if (argc != 1) { return usage("probe: expected exactly one DEV"); }
    (void)probe_device(argv[0], &f);
    tseam_target(argv[0], 1, f.bytes);
    tseam_facts(&f, refusal_id(safety_policy(&f, 0, 0)), 0);
    printf("whole=%d\nremovable=%d\nsd_bus=%d\nbytes=%llu\nholds_os=%d\nlayout_ok=%d\n",
           f.whole_device, f.removable, f.sd_bus, (unsigned long long)f.bytes, f.holds_os, f.layout_ok);
    for (i = 0; i < f.n_mounted && i < SAFETY_MAX_MOUNTS; i++) {
        printf("mounted=%d:%s\n", f.mounted[i].partition, f.mounted[i].where);
    }
    if (f.n_mounted > SAFETY_MAX_MOUNTS) { printf("mounted=0:(more than %d)\n", SAFETY_MAX_MOUNTS); }
    printf("refusal=%s\n", refusal_id(safety_policy(&f, 0, 0)));
    if (f.detail[0]) { printf("detail=%s\n", f.detail); }
    return 0;
}
#endif

#if defined(_WIN32)
#include <windows.h>
#include <shellapi.h>
#include <fcntl.h>
#include <io.h>
/* WP-14 runs on Windows 10 (D2). Labels and paths are UTF-8 everywhere in
   tapectl, but a Windows C runtime hands main() its arguments in the ANSI code
   page. Rebuild argv from the UTF-16 command line instead, and keep stdout in
   binary mode so verify's lines end in LF on every platform. */
static char g_argbuf[32768];
static char *g_argv[256];
static int utf8_argv(int *argc, char ***argv)
{
    int n = 0, i, used = 0;
    LPWSTR *w = CommandLineToArgvW(GetCommandLineW(), &n);
    if (w == NULL || n > 255) { return -1; }
    for (i = 0; i < n; i++) {
        int len = WideCharToMultiByte(CP_UTF8, 0, w[i], -1, g_argbuf + used, (int)sizeof g_argbuf - used, NULL, NULL);
        if (len <= 0) { LocalFree(w); return -1; }
        g_argv[i] = g_argbuf + used;
        used += len;
    }
    g_argv[n] = NULL;
    LocalFree(w);
    *argc = n;
    *argv = g_argv;
    (void)_setmode(_fileno(stdout), _O_BINARY);
    return 0;
}
#endif

static int tapectl_main(int argc, char **argv)
{
    const char *cmd;
    int rc;


    if (tape_instance_size() > sizeof g_mem.b) {
        fprintf(stderr, "tapectl: engine instance (%lu bytes) exceeds the static block\n",
                (unsigned long)tape_instance_size());
        return EXIT_USAGE;
    }
    if (argc < 3) { return usage("missing command or IMG"); }
    cmd = argv[1];
    argc -= 2; argv += 2;
    if (strcmp(cmd, "format") == 0) { rc = cmd_format(argc, argv); }
    else if (strcmp(cmd, "load") == 0) { rc = cmd_load(argc, argv); }
    else if (strcmp(cmd, "play") == 0) { rc = play_common(argc, argv, 0); }
    else if (strcmp(cmd, "scrub") == 0) { rc = play_common(argc, argv, 1); }
    else if (strcmp(cmd, "record") == 0) { rc = cmd_record(argc, argv); }
    else if (strcmp(cmd, "reset-b") == 0 || strcmp(cmd, "promote") == 0 || strcmp(cmd, "respool") == 0) {
        rc = cmd_simple(argc, argv, cmd);
    }
    else if (strcmp(cmd, "dump") == 0) { rc = cmd_dump(argc, argv); }
    else if (strcmp(cmd, "provision") == 0) { rc = cmd_provision(argc, argv); }
    else if (strcmp(cmd, "verify") == 0) { rc = cmd_verify(argc, argv); }
#ifdef TAPECTL_TEST
    else if (strcmp(cmd, "probe") == 0) { rc = cmd_probe(argc, argv); }
#endif
    else { return usage("unknown command"); }
    return finish(rc);
}

int main(int argc, char **argv)
{
    int rc;
#if defined(_WIN32)
    if (utf8_argv(&argc, &argv) != 0) { return usage("cannot read the command line"); }
#endif
#ifdef TAPECTL_TEST
    tseam_begin(argc, argv);
    rc = tapectl_main(argc, argv);
    return tseam_finish(rc);
#else
    rc = tapectl_main(argc, argv);
    return rc;
#endif
}
