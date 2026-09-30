/* Public-arithmetic reference adapter. This is verifier self-test code, not Product. */
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#define MAX_FRAMES 12

struct vector {
    const char *id;
    const char *fixture_sha256;
    uint32_t frame_count;
    int16_t pcm[MAX_FRAMES][2];
    uint64_t seek;
    int32_t rate;
    uint32_t requested;
};

#include "vectors.h"

static int16_t interpolate(int16_t a, int16_t b, uint32_t f) {
    int64_t difference = (int64_t)((int32_t)b - (int32_t)a);
    int64_t d = difference * (int64_t)(uint64_t)f;
    int64_t q;
    if (d >= 0) {
        q = (int64_t)((uint64_t)d >> 32);
    } else {
        uint64_t magnitude = (uint64_t)(-d);
        q = -(int64_t)((magnitude + UINT32_C(0xffffffff)) >> 32);
    }
    return (int16_t)((int32_t)a + (int32_t)q);
}

static void emit_s16le(int16_t sample) {
    uint16_t bits = (uint16_t)sample;
    printf("%02x%02x", (unsigned)(bits & 0xffu), (unsigned)(bits >> 8));
}

static void run(const struct vector *v) {
    const uint64_t max_pos = (uint64_t)v->frame_count << 32;
    uint64_t position = v->seek < v->frame_count ? v->seek << 32 : max_pos;
    const int64_t step = (int64_t)v->rate * INT64_C(65536);
    bool at_start = false, at_end = false;
    int16_t output[MAX_FRAMES][2] = {{0}};
    uint32_t rendered = 0;

    if (v->frame_count == 0) {
        at_end = true;
    } else if (step != 0) {
        if (step < 0 && position >= max_pos) position = (uint64_t)(v->frame_count - 1) << 32;
        for (uint32_t n = 0; n < v->requested; ++n) {
            if (step > 0 && position >= max_pos) { at_end = true; break; }
            if (step < 0 && at_start) break;
            uint32_t i = (uint32_t)(position >> 32);
            uint32_t f = (uint32_t)position;
            uint32_t j = i + 1 < v->frame_count ? i + 1 : i;
            output[rendered][0] = interpolate(v->pcm[i][0], v->pcm[j][0], f);
            output[rendered][1] = interpolate(v->pcm[i][1], v->pcm[j][1], f);
            ++rendered;
            if (step > 0) {
                uint64_t distance = (uint64_t)step;
                at_start = false;
                if (position >= max_pos || distance >= max_pos - position) {
                    position = max_pos; at_end = true;
                } else position += distance;
            } else {
                uint64_t distance = (uint64_t)(-step);
                at_end = false;
                if (position == 0) at_start = true;
                else if (position <= distance) position = 0;
                else position -= distance;
            }
        }
    }

    printf("{\"at_end\":%s,\"at_start\":%s,\"case\":\"%s\",",
           at_end ? "true" : "false", at_start ? "true" : "false", v->id);
    printf("\"fixture_sha256\":\"%s\",\"pcm_hex\":\"", v->fixture_sha256);
    for (uint32_t n = 0; n < rendered; ++n) {
        emit_s16le(output[n][0]); emit_s16le(output[n][1]);
    }
    printf("\",\"rendered\":%" PRIu32 ",\"schema\":\"wp08-portability-r52-v1\",", rendered);
    printf("\"tell\":%" PRIu64 ",\"trace\":[", position >> 32);
    printf("{\"block_events\":[],\"fn\":\"tape_mount\",\"result\":\"TAPE_OK\"},");
    printf("{\"block_events\":[],\"fn\":\"tape_seek\",\"frame\":%" PRIu64 ",\"result\":\"TAPE_OK\"},", v->seek);
    printf("{\"block_events\":[],\"fn\":\"tape_set_rate\",\"rate_q16_16\":%" PRId32 ",\"result\":\"TAPE_OK\"},", v->rate);
    printf("{\"block_events\":[],\"budget\":7,\"fn\":\"tape_service\",\"more_work\":false,\"result\":\"TAPE_OK\"},");
    printf("{\"block_events\":[],\"fn\":\"tape_render\",\"rendered\":%" PRIu32 ",\"requested\":%" PRIu32 ",\"result\":\"TAPE_OK\"},", rendered, v->requested);
    printf("{\"fn\":\"tape_tell\",\"value\":%" PRIu64 "},", position >> 32);
    printf("{\"at_end\":%s,\"at_start\":%s,\"fn\":\"tape_status\",\"result\":\"TAPE_OK\"}]}\n",
           at_end ? "true" : "false", at_start ? "true" : "false");
}

int main(void) {
    for (uint32_t i = 0; i < VECTOR_COUNT; ++i) run(&VECTORS[i]);
    return 0;
}
