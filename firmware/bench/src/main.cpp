/*
 * main.cpp — WP-17 bench firmware: Teensy 4.1 + SGTL5000 (contract FW-1).
 *
 * Mounts the cartridge in the built-in microSD slot, plays it through the
 * SGTL5000 headphone output, and answers the F1 golden commands over USB
 * serial. Everything audible comes out of tape_render; this file only wires
 * the card, the audio interrupt, two buttons and the serial port to the
 * portable modules (fw_part, fw_play) that CI also runs off target.
 *
 * Context rule (fw_play.h): the audio interrupt calls fw_player_render and
 * nothing else. The main loop makes every other engine call, and masks the
 * audio interrupt around each one while the player is rendering. While it is
 * not rendering, the interrupt never enters the engine, so no masking is needed.
 *
 * Output level: FIXED LOW until the WP-19 headphone cap lands (FW-1 §5). Not
 * reachable from any control. Nobody wears headphones on the bench without a
 * volume check.
 */

#include <Arduino.h>
#include <Audio.h>

extern "C" {
#include "tape.h"
#include "fw_part.h"
#include "fw_play.h"
#include "fw_sd.h"
#include "fw_sha256.h"
#include "fw_storage.h"
#if FW_SIZE_GATE_RODATA_CONTROL
extern const unsigned char tape_gate_control_rodata[];   /* controls/gate_rodata.h */
#endif
}

/* ---- pin map (also in README.md) ----------------------------------------
   The audio adaptor takes 7, 8, 20, 21, 23 (I2S) and 18, 19 (I2C). The
   built-in microSD slot is SDIO and uses no header pins. */
static const uint8_t PIN_PLAY = 2;   /* to GND through a momentary switch */
static const uint8_t PIN_STOP = 3;   /* to GND through a momentary switch */

/* SGTL5000 headphone volume, 0..1. Fixed, low, never user-reachable. */
static const float FW_HP_VOLUME = 0.20f;

static const uint32_t FW_DEBOUNCE_MS = 20;
static const uint32_t FW_CARD_POLL_MS = 250;

/* ---- painted stack (F2 target half) --------------------------------------
   On the Teensy 4 the stack grows down from _estack in DTCM toward _ebss;
   malloc lives in OCRAM, so nothing else uses the gap. setup() paints it and
   `info` reports how deep the stack has ever reached. The whole firmware's
   depth, interrupts included, bounds the engine's from above. */
extern "C" unsigned long _ebss;
extern "C" unsigned long _estack;
static const uint32_t FW_STACK_PAINT = 0xA5A5A5A5u;

static void stack_paint(void)
{
    volatile uint32_t here = 0;
    uint32_t *p = reinterpret_cast<uint32_t *>(&_ebss);
    uint32_t *stop = reinterpret_cast<uint32_t *>(reinterpret_cast<uintptr_t>(&here) - 256u);
    while (p < stop) { *p++ = FW_STACK_PAINT; }
}

static uint32_t stack_high_water(void)
{
    const uint32_t *p = reinterpret_cast<const uint32_t *>(&_ebss);
    const uint32_t *top = reinterpret_cast<const uint32_t *>(&_estack);
    while (p < top && *p == FW_STACK_PAINT) { p++; }
    return static_cast<uint32_t>(reinterpret_cast<uintptr_t>(top) - reinterpret_cast<uintptr_t>(p));
}

/* ---- audio graph --------------------------------------------------------- */

static struct fw_player g_player;

class AudioTapeSource : public AudioStream {
public:
    AudioTapeSource() : AudioStream(0, nullptr) {}
    void update() override
    {
        audio_block_t *l = allocate();
        audio_block_t *r = allocate();
        if (l == nullptr || r == nullptr) {
            if (l) { release(l); }
            if (r) { release(r); }
            return;
        }
        fw_player_render(&g_player, pcm_, FW_AUDIO_FRAMES);
        for (uint32_t i = 0; i < FW_AUDIO_FRAMES; i++) {
            l->data[i] = pcm_[2u * i];
            r->data[i] = pcm_[2u * i + 1u];
        }
        transmit(l, 0);
        transmit(r, 1);
        release(l);
        release(r);
    }
private:
    int16_t pcm_[FW_AUDIO_FRAMES * TAPE_CHANNELS];
};

static AudioTapeSource g_source;
static AudioOutputI2S g_i2s;
static AudioConnection g_patch_l(g_source, 0, g_i2s, 0);
static AudioConnection g_patch_r(g_source, 1, g_i2s, 1);
static AudioControlSGTL5000 g_codec;

/* ---- engine state -------------------------------------------------------- */

enum fw_state { NO_CARD, REFUSED, MOUNTED };

static enum fw_state g_state = NO_CARD;
static tape_dev g_card;
static struct fw_part g_part;
static tape_dev g_dev;
static tape *g_t = nullptr;
static tape_side g_side = TAPE_SIDE_A;
static uint32_t g_last_poll = 0;

/* An engine call from the main loop, masked against the audio interrupt only
   when the interrupt might be inside tape_render. */
template <typename F> static tape_result loop_call(F f)
{
    if (!g_player.playing) { return f(); }
    AudioNoInterrupts();
    tape_result r = f();
    AudioInterrupts();
    return r;
}

static void report(const char *what, int code)
{
    Serial.print(what);
    Serial.print(' ');
    Serial.println(code);
}

static void drop_card(const char *why)
{
    g_player.playing = 0;
    if (g_t != nullptr) {
        uint64_t pos = 0;
        /* Best effort: after a pull this usually fails, and that is fine. Play
           wrote nothing, so there is nothing to lose. */
        report("UNMOUNT", tape_unmount(g_t, &pos));
    }
    g_t = nullptr;
    fw_player_bind(&g_player, nullptr);
    g_state = NO_CARD;
    Serial.print("CARD GONE ");
    Serial.println(why);
}

static void try_card(void)
{
    if (fw_sd_begin(&g_card) != 0) { return; }
    fw_part_result pr = fw_part_open(&g_part, &g_card, &g_dev, 1);
    if (pr != FW_PART_OK) {
        g_state = REFUSED;
        Serial.println(pr == FW_PART_IO ? "CARD REFUSED IO" : "CARD REFUSED NOT_PROVISIONED");
        return;
    }
    tape_result r = tape_init(fw_engine_instance, fw_engine_instance_len, &g_dev,
                              fw_play_ring, sizeof fw_play_ring,
                              fw_rec_ring, sizeof fw_rec_ring, &g_t);
    if (r == TAPE_OK) { r = tape_mount(g_t, g_side, 0, nullptr); }
    if (r != TAPE_OK) {
        g_t = nullptr;
        g_state = REFUSED;
        report("CARD REFUSED MOUNT", r);
        return;
    }
    fw_player_bind(&g_player, g_t);
    g_state = MOUNTED;
    tape_info info;
    if (tape_get_info(g_t, &info) == TAPE_OK) {
        Serial.print("CARD MOUNTED side ");
        Serial.print(g_side == TAPE_SIDE_A ? 'A' : 'B');
        Serial.print(" frames ");
        Serial.print((unsigned long long)info.total_frames);
        Serial.print(" label ");
        Serial.println(info.label);
    }
}

/* ---- buttons ------------------------------------------------------------- */

struct button {
    uint8_t pin;
    uint8_t stable;      /* 1 = released (pull-up) */
    uint8_t last;
    uint32_t since;
};

static struct button g_play_btn = {PIN_PLAY, 1, 1, 0};
static struct button g_stop_btn = {PIN_STOP, 1, 1, 0};

/* True once per press, after FW_DEBOUNCE_MS of a steady low. */
static bool pressed(struct button *b)
{
    uint8_t v = (uint8_t)digitalReadFast(b->pin);
    uint32_t now = millis();
    if (v != b->last) { b->last = v; b->since = now; return false; }
    if (v != b->stable && now - b->since >= FW_DEBOUNCE_MS) {
        b->stable = v;
        return v == 0;
    }
    return false;
}

/* ---- F1 golden hook over USB serial -------------------------------------- */

struct sink_state {
    struct fw_sha256 sha;
    bool stream;
};

static void golden_sink(void *user, const int16_t *pcm, uint32_t frames)
{
    struct sink_state *s = static_cast<struct sink_state *>(user);
    fw_sha256_update(&s->sha, pcm, (size_t)frames * TAPE_FRAME_BYTES);
    if (s->stream) {
        /* Length-prefixed runs: u32 LE frame count, then the PCM bytes. */
        uint8_t n[4] = {(uint8_t)frames, (uint8_t)(frames >> 8), (uint8_t)(frames >> 16), (uint8_t)(frames >> 24)};
        Serial.write(n, 4);
        Serial.write(reinterpret_cast<const uint8_t *>(pcm), frames * TAPE_FRAME_BYTES);
    }
}

static void print_digest(struct fw_sha256 *sha, uint64_t frames, tape_result r)
{
    uint8_t d[32];
    char hex[65];
    fw_sha256_final(sha, d);
    fw_sha256_hex(d, hex);
    Serial.print("SHA256 ");
    Serial.print(hex);
    Serial.print(" FRAMES ");
    Serial.print((unsigned long long)frames);
    Serial.print(" RESULT ");
    Serial.println((int)r);
}

static tape_result select_side(char c)
{
    tape_side side = (c == 'B' || c == 'b') ? TAPE_SIDE_B : TAPE_SIDE_A;
    if (side == g_side) { return TAPE_OK; }
    tape_result r = tape_set_side(g_t, side);
    if (r == TAPE_OK) { g_side = side; }
    return r;
}

static int16_t g_golden_pcm[FW_AUDIO_FRAMES * TAPE_CHANNELS];

/* golden|stream SIDE FROM FRAMES: deterministic render, engine-api §6.3 order.
   live SIDE FROM: render in the audio interrupt exactly as heard, to the end
   of the side, hashing every frame the interrupt renders. */
static void command(char *line)
{
    char verb[8] = {0}, side = 'A';
    unsigned long long from = 0, frames = 0;
    int n = sscanf(line, "%7s %c %llu %llu", verb, &side, &from, &frames);
    if (n >= 1 && strcmp(verb, "info") == 0) {
        Serial.print("INFO state ");
        Serial.print((int)g_state);
        Serial.print(" instance ");
        Serial.print((unsigned long)tape_instance_size());
        Serial.print(" reserve ");
        Serial.print((unsigned long)fw_engine_instance_len);
        Serial.print(" card_blocks ");
        Serial.print((unsigned long)g_card.block_count);
        Serial.print(" p2_base ");
        Serial.print((unsigned long)g_part.base);
        Serial.print(" p2_blocks ");
        Serial.print((unsigned long)g_part.blocks);
        Serial.print(" stack_high_water ");
        Serial.print((unsigned long)stack_high_water());
        Serial.print(" underruns ");
        Serial.println((unsigned long)g_player.underruns);
        return;
    }
    if (n < 3 || g_state != MOUNTED) { Serial.println("ERR usage or no mounted card"); return; }
    if (g_player.playing) { (void)loop_call([] { return fw_player_stop(&g_player); }); }
    tape_result r = select_side(side);
    if (r != TAPE_OK) { report("ERR side", r); return; }

    struct sink_state s;
    fw_sha256_init(&s.sha);
    if (strcmp(verb, "golden") == 0 || strcmp(verb, "stream") == 0) {
        uint64_t done = 0;
        s.stream = verb[0] == 's';
        if (s.stream) { Serial.println("PCM"); }
        r = fw_golden_render(g_t, from, frames, g_golden_pcm, FW_AUDIO_FRAMES, golden_sink, &s, &done);
        if (s.stream) { uint8_t z[4] = {0, 0, 0, 0}; Serial.write(z, 4); }
        print_digest(&s.sha, done, r);
    } else if (strcmp(verb, "live") == 0) {
        r = tape_seek(g_t, from);
        if (r == TAPE_OK) {
            g_player.rendered = 0;
            g_player.underruns = 0;
            g_player.tap = &s.sha;
            r = fw_player_play(&g_player);
        }
        while (r == TAPE_OK && g_player.playing) {
            bool more = false;
            r = loop_call([&more] { return fw_player_service(&g_player, &more); });
        }
        g_player.playing = 0;
        g_player.tap = nullptr;
        if (r == TAPE_OK && g_player.failed) { r = TAPE_ERR_IO; }
        Serial.print("UNDERRUNS ");
        Serial.println((unsigned long)g_player.underruns);
        print_digest(&s.sha, g_player.rendered, r);
    } else {
        Serial.println("ERR unknown command");
    }
}

static char g_line[64];
static uint32_t g_line_len = 0;

static void poll_serial(void)
{
    while (Serial.available() > 0) {
        int c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (g_line_len > 0) { g_line[g_line_len] = '\0'; command(g_line); g_line_len = 0; }
        } else if (g_line_len + 1 < sizeof g_line) {
            g_line[g_line_len++] = (char)c;
        }
    }
}

/* ---- setup / loop -------------------------------------------------------- */

void setup()
{
    stack_paint();
    pinMode(PIN_PLAY, INPUT_PULLUP);
    pinMode(PIN_STOP, INPUT_PULLUP);
    Serial.begin(115200);
    fw_player_bind(&g_player, nullptr);

    AudioMemory(8);
    g_codec.enable();
    g_codec.volume(FW_HP_VOLUME);

    if (tape_instance_size() > fw_engine_instance_len) {
        /* The reserve is wrong for this build. Refuse to run rather than
           overrun caller storage. */
        for (;;) {
            Serial.print("FATAL instance ");
            Serial.print((unsigned long)tape_instance_size());
            Serial.print(" > reserve ");
            Serial.println((unsigned long)fw_engine_instance_len);
            delay(1000);
        }
    }
    Serial.println("DIGITAL-TAPE BENCH WP-17");
#if FW_SIZE_GATE_RODATA_CONTROL
    /* F2 negative control build only: keep the injected engine static linked. */
    Serial.println(tape_gate_control_rodata[0]);
#endif
}

void loop()
{
    uint32_t now = millis();
    poll_serial();

    if (g_state != MOUNTED) {
        if (now - g_last_poll >= FW_CARD_POLL_MS) {
            g_last_poll = now;
            if (g_state == NO_CARD) { try_card(); }
            else if (!fw_sd_present()) { g_state = NO_CARD; Serial.println("CARD GONE refused card"); }
        }
        return;
    }

    if (pressed(&g_play_btn) && !g_player.playing) {
        tape_result r = fw_player_play(&g_player);
        report(r == TAPE_OK ? "PLAY" : "PLAY FAILED", r);
    }
    if (pressed(&g_stop_btn) && g_player.playing) {
        tape_result r = loop_call([] { return fw_player_stop(&g_player); });
        uint64_t pos = 0;
        (void)tape_tell(g_t, &pos);
        report("STOP", r);
        Serial.print("POSITION ");
        Serial.println((unsigned long long)pos);
    }

    if (g_player.playing) {
        bool more = false;
        tape_result r = loop_call([&more] { return fw_player_service(&g_player, &more); });
        if (r != TAPE_OK) { drop_card("service failed"); return; }
    }
    if (g_player.ended) {
        g_player.ended = 0;
        (void)tape_set_rate(g_t, 0);
        Serial.println("END OF SIDE");
    }
    if (g_player.failed) {
        g_player.failed = 0;
        Serial.println("RENDER FAILED");
    }
    if (now - g_last_poll >= FW_CARD_POLL_MS) {
        g_last_poll = now;
        if (!fw_sd_present()) { drop_card("removed"); }
    }
}
