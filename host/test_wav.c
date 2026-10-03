/*
 * test_wav.c — unit tests for tapectl's WAV reader and writer.
 *
 * The reader must reject anything but RIFF PCM 44.1 kHz / 16-bit / stereo
 * (48 kHz, mono and 24-bit named by #366), skip unknown chunks, and refuse a
 * data chunk that is not whole frames. The writer must emit a canonical 44-byte
 * header and round-trip samples exactly, including both int16 extremes.
 *
 * Usage: test_wav SCRATCH_DIR
 */

#include "wav.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures;
static char g_dir[512];

#define EXPECT(cond, what) do { if (cond) { printf("  ok    %s\n", what); } \
                                else { printf("  FAIL  %s\n", what); failures++; } } while (0)

static void put32(unsigned char *p, uint32_t v)
{
    p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8);
    p[2] = (unsigned char)(v >> 16); p[3] = (unsigned char)(v >> 24);
}

static void put16(unsigned char *p, uint16_t v)
{
    p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8);
}

static const char *path(const char *name)
{
    static char buf[600];
    (void)snprintf(buf, sizeof buf, "%s/%s", g_dir, name);
    return buf;
}

/* A hand-built WAV: fmt fields as given, an optional LIST chunk before fmt, a
   data chunk declaring `data_bytes`, of which `written` are actually present. */
static void make(const char *name, uint16_t tag, uint16_t ch, uint32_t rate, uint16_t bits,
                 int list, uint32_t data_bytes, uint32_t written)
{
    unsigned char b[256];
    size_t n = 12;
    uint16_t align = (uint16_t)(ch * (bits / 8u));
    FILE *fp;
    uint32_t i;

    memcpy(b, "RIFF", 4); memcpy(b + 8, "WAVE", 4);
    if (list) {                       /* odd-sized unknown chunk, so the pad byte matters */
        memcpy(b + n, "LIST", 4); put32(b + n + 4, 5u); memcpy(b + n + 8, "INFOx", 5);
        b[n + 13] = 0; n += 14;
    }
    memcpy(b + n, "fmt ", 4); put32(b + n + 4, 16u); put16(b + n + 8, tag); put16(b + n + 10, ch);
    put32(b + n + 12, rate); put32(b + n + 16, rate * align); put16(b + n + 20, align);
    put16(b + n + 22, bits); n += 24;
    memcpy(b + n, "data", 4); put32(b + n + 4, data_bytes); n += 8;
    put32(b + 4, (uint32_t)(n - 8u) + data_bytes);
    fp = fopen(path(name), "wb");
    if (fp == NULL) { perror("fopen"); exit(2); }
    (void)fwrite(b, 1, n, fp);
    for (i = 0; i < written; i++) { (void)fputc((int)(i * 7u + 3u) & 0xFF, fp); }
    (void)fclose(fp);
}

static int rejects(const char *name, const char *want)
{
    struct wav_in w;
    char err[96] = "";
    int rc = wav_open_read(&w, path(name), err, sizeof err);
    if (rc == 0) { wav_close_read(&w); return 0; }
    return strstr(err, want) != NULL;
}

int main(int argc, char **argv)
{
    struct wav_in in;
    struct wav_out out;
    char err[96];
    int16_t frames[6] = {32767, -32768, 0, 1, -1, 12345}, got[6];
    unsigned char hdr[44], expect_hdr[44];
    FILE *fp;
    int bad = 0;

    if (argc != 2) { fprintf(stderr, "usage: test_wav SCRATCH_DIR\n"); return 2; }
    (void)snprintf(g_dir, sizeof g_dir, "%s", argv[1]);
    {
        char cmd[600];
        (void)snprintf(cmd, sizeof cmd, "mkdir -p '%s'", g_dir);
        if (system(cmd) != 0) { return 2; }
    }

    printf("== WAV reader rejects, never converts ==\n");
    make("48k.wav", 1, 2, 48000, 16, 0, 16, 16);
    make("mono.wav", 1, 1, 44100, 16, 0, 16, 16);
    make("24bit.wav", 1, 2, 44100, 24, 0, 24, 24);
    make("float.wav", 3, 2, 44100, 16, 0, 16, 16);
    make("partial.wav", 1, 2, 44100, 16, 0, 6, 6);
    EXPECT(rejects("48k.wav", "44100"), "48 kHz rejected");
    EXPECT(rejects("mono.wav", "stereo"), "mono rejected");
    EXPECT(rejects("24bit.wav", "16-bit"), "24-bit rejected");
    EXPECT(rejects("float.wav", "PCM"), "non-PCM format tag rejected");
    EXPECT(rejects("partial.wav", "whole frames"), "data not whole frames rejected");

    printf("== WAV reader accepts the format, skipping unknown chunks ==\n");
    make("list.wav", 1, 2, 44100, 16, 1, 8, 8);
    if (wav_open_read(&in, path("list.wav"), err, sizeof err) == 0) {
        uint32_t n = wav_read_frames(&in, got, 4, &bad);
        EXPECT(in.frames == 2u && n == 2u && !bad, "LIST chunk (odd size, padded) skipped; 2 frames read");
        EXPECT((uint16_t)got[0] == 0x0A03u, "samples little-endian");
        wav_close_read(&in);
    } else {
        EXPECT(0, err);
    }

    printf("== WAV writer: canonical 44-byte header, exact round trip ==\n");
    if (wav_open_write(&out, path("rt.wav"), err, sizeof err) != 0 || wav_write_frames(&out, frames, 3) != 0
        || wav_close_write(&out) != 0) {
        EXPECT(0, "write rt.wav");
    } else {
        memcpy(expect_hdr, "RIFF", 4); put32(expect_hdr + 4, 36u + 12u); memcpy(expect_hdr + 8, "WAVEfmt ", 8);
        put32(expect_hdr + 16, 16u); put16(expect_hdr + 20, 1u); put16(expect_hdr + 22, 2u);
        put32(expect_hdr + 24, 44100u); put32(expect_hdr + 28, 176400u); put16(expect_hdr + 32, 4u);
        put16(expect_hdr + 34, 16u); memcpy(expect_hdr + 36, "data", 4); put32(expect_hdr + 40, 12u);
        fp = fopen(path("rt.wav"), "rb");
        EXPECT(fp != NULL && fread(hdr, 1, 44, fp) == 44 && memcmp(hdr, expect_hdr, 44) == 0
               && fseek(fp, 0, SEEK_END) == 0 && ftell(fp) == 56, "header canonical, 44 + 12 bytes");
        if (fp != NULL) { (void)fclose(fp); }
        if (wav_open_read(&in, path("rt.wav"), err, sizeof err) == 0) {
            uint32_t n = wav_read_frames(&in, got, 8, &bad);
            EXPECT(n == 3u && !bad && memcmp(got, frames, sizeof got) == 0, "int16 extremes round-trip exactly");
            EXPECT(wav_read_frames(&in, got, 8, &bad) == 0u && !bad, "end of data reads 0 frames");
            wav_close_read(&in);
        } else {
            EXPECT(0, err);
        }
    }

    printf("== WAV reader: truncated data is reported ==\n");
    make("short.wav", 1, 2, 44100, 16, 0, 16, 8);
    if (wav_open_read(&in, path("short.wav"), err, sizeof err) == 0) {
        uint32_t n = wav_read_frames(&in, got, 4, &bad);
        EXPECT(n == 0u && bad, "short data flagged as bad");
        wav_close_read(&in);
    } else {
        EXPECT(0, err);
    }

    printf("%s: %d failure(s)\n", failures ? "FAIL" : "PASS", failures);
    return failures ? 1 : 0;
}
