/*
 * tapectl — host tooling for loading cartridges in tests and demos.
 *
 * Normative: docs/WP11-CLI-CONTRACT.md. It composes the public engine API
 * (engine/include/tape.h) over the file-backed port and reimplements no engine
 * behaviour (guardrail 12). It is not a player or a library (guardrail 03).
 *
 * Exit status: 0 success; 1 an engine result other than TAPE_OK, named on
 * stderr; 2 a usage or WAV-format error. No clock, randomness or environment:
 * the same arguments and input bytes give byte-identical outputs and images.
 */

#include "tape.h"
#include "dev_file.h"
#include "wav.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RENDER_MAX   128u        /* contract: render requests of at most 128 frames */
#define FEED_FRAMES  1024u       /* contract: record requests of 1024 frames */
#define BUDGET       1024u       /* service and long-operation block budget */

#define EXIT_ENGINE  1
#define EXIT_USAGE   2

/* One static, caller-owned block for the instance (engine-api §4). The RAM gate
   bounds tape_instance_size() at 200 KiB; main() checks it fits. */
static union { long double ld; uint64_t u; void *p; unsigned char b[256u * 1024u]; } g_mem;
static unsigned char g_play[TAPE_PLAY_RING_MIN];
static unsigned char g_rec[TAPE_REC_RING_MIN];
static int16_t g_pcm[FEED_FRAMES * 2u];

static struct tape_dev_file g_file;
static tape_dev g_dev;
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
        "       tapectl dump IMG --side A|B -o OUT.wav\n");
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

static int open_image(const char *img)
{
    if (tape_dev_file_open(&g_file, &g_dev, img, 1) != TAPE_DEV_OK) {
        fprintf(stderr, "tapectl: cannot open image %s\n", img);
        return EXIT_USAGE;
    }
    return 0;
}

static int mount(tape_side side)
{
    CHECK(tape_init(g_mem.b, tape_instance_size(), &g_dev, g_play, sizeof g_play, g_rec, sizeof g_rec, &g_t));
    CHECK(tape_mount(g_t, side, 0u, NULL));
    return 0;
}

static int finish(int rc)
{
    if (g_t != NULL) {
        uint64_t pos;
        (void)tape_unmount(g_t, &pos);
        g_t = NULL;
    }
    if (g_file.fp != NULL && tape_dev_file_close(&g_file) != TAPE_DEV_OK && rc == 0) {
        fprintf(stderr, "tapectl: cannot close image\n");
        rc = EXIT_USAGE;
    }
    return rc;
}

/* Contract: before every render or feed request, service until more == false. */
static int service(void)
{
    bool more = true;
    while (more) { CHECK(tape_service(g_t, BUDGET, &more)); }
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
    do {
        bool more = true;
        CHECK(tape_service(g_t, BUDGET, &more));
        CHECK(tape_status(g_t, &st));
    } while (st.frames_owed);
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
    if (tape_dev_file_create(&g_file, &g_dev, positional(argc, argv, 0), blocks) != TAPE_DEV_OK) {
        fprintf(stderr, "tapectl: cannot create image\n");
        return EXIT_USAGE;
    }
    CHECK(tape_format(&g_dev, uuid, epoch, label, length));
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
    if (!rc) { rc = mount(TAPE_SIDE_A); }
    if (!rc) {
        tape_result r = tape_set_side(g_t, TAPE_SIDE_B);
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

    rc = open_image(positional(argc, argv, 0));
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
    rc = open_image(positional(argc, argv, 0));
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

int main(int argc, char **argv)
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
    else { return usage("unknown command"); }
    return finish(rc);
}
