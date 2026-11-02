# firmware/bench/ — Stream 4 (WP-17 bench firmware)

Teensy 4.1 with the SGTL5000 audio adaptor, running the shared engine unchanged.
Contract: [FW-1](../../docs/WP17-FIRMWARE-CONTRACT.md). Round-1 scope (#642):
build, the SD partition view, the play path with Play/Stop, the F1 golden hook,
and the CI size gates. Recording, the second slot, copy, the speaker, aux,
depth-sensitive scrub and LEDs are WP-18 to WP-20.

**Packages:** WP-17, 18, 19, 20, 21. **Note:** the bench's second slot (WP-18) is
on SPI, so copy takes ~10 minutes here. That is expected: this build proves
function, not speed, and is never reported against guardrail 10 (Stream 5's).

> **Volume.** The headphone output is fixed LOW (`FW_HP_VOLUME` in `src/main.cpp`)
> until the WP-19 output cap lands. No control reaches it. **Nobody wears
> headphones on the bench without a volume check.**

## What is here

| Path | What it is |
|---|---|
| `platformio.ini` | The build, with every toolchain package pinned |
| `lib/tape_engine/` | Manifest that builds `engine/src` in place, unchanged, with the desktop warning set and `-Werror` (FW-1 §3). Nothing is copied |
| `lib/tape_layout/` | Builds `host/port/mbr.c` in place, so the firmware recognises a card exactly as `tapectl` does |
| `src/fw_part.c` | Partition 2 of a whole card as the engine's `tape_dev` (portable C) |
| `src/fw_play.c` | The render loop over the public API: audio-interrupt render, main-loop service, the F1 deterministic render (portable C) |
| `src/fw_sha256.c` | SHA-256 for the golden hook (portable C) |
| `src/fw_sd.cpp` | The built-in microSD slot (SDIO) as a whole-card `tape_dev` |
| `src/fw_storage.c` | Static, caller-owned engine storage in OCRAM: instance, play ring, record ring |
| `src/main.cpp` | Teensy glue: audio graph, buttons, card attach/removal, serial commands |
| `host/` | `fwhost` and `run_checks.py`: the portable modules run off target, in CI |
| `tools/size_gate.py` | F2 budgets from the linked image's map and symbols |
| `tools/engine_pin.sh` | F6 check that `engine/` equals `d96b4245` |
| `tools/golden_serial.py` | F1 on target, over USB serial (bench only) |
| `controls/` | F2 `.rodata` negative-control header (control build only) |

## Toolchain (pinned)

| Piece | Version | Pinned in |
|---|---|---|
| PlatformIO Core | 6.1.19 | `tools/requirements.txt` |
| Platform `platformio/teensy` | 6.0.0 | `platformio.ini` |
| `framework-arduinoteensy` (Teensyduino core and libraries) | 1.162.0 (Teensyduino 1.62) | `platformio.ini` |
| `tool-teensy` (loader) | 1.162.0 | `platformio.ini` |
| `toolchain-gccarmnoneeabi-teensy` | 1.150201.0 (GCC 15.2.1) | `platformio.ini` |
| Libraries used from the core | Audio 1.3, SdFat 2.1.2, SD 2.0.0, SPI, Wire, SerialFlash | come with the core |

## Build

```bash
python -m pip install -r firmware/bench/tools/requirements.txt
pio run -d firmware/bench -e teensy41
```

The image is `firmware/bench/.pio/build/teensy41/firmware.hex`. The size gate:

```bash
TC=~/.platformio/packages/toolchain-gccarmnoneeabi-teensy/bin
python firmware/bench/tools/size_gate.py --map firmware/bench/.pio/build/teensy41/firmware.map --elf firmware/bench/.pio/build/teensy41/firmware.elf --nm $TC/arm-none-eabi-nm --size-tool $TC/arm-none-eabi-size
```

The envs `teensy41_ctl_ram` and `teensy41_ctl_rodata` are F2 negative controls
that CI requires to fail the gate. **Never flash them.**

## Flash

Connect the Teensy over USB, then either:

```bash
pio run -d firmware/bench -e teensy41 -t upload
```

or open `firmware.hex` in the PJRC Teensy Loader and press the board's button.

## Pin map

| Function | Teensy 4.1 pin | Notes |
|---|---|---|
| Play | 2 | Momentary switch to GND; internal pull-up; 20 ms debounce |
| Stop | 3 | Momentary switch to GND; internal pull-up; 20 ms debounce |
| I²S to SGTL5000 | 7 (TX), 8 (RX), 20 (LRCLK), 21 (BCLK), 23 (MCLK) | Audio adaptor, used by the Audio library |
| I²C to SGTL5000 | 18 (SDA), 19 (SCL) | Audio adaptor control |
| Cartridge | built-in microSD slot | SDIO, no header pins. The adaptor's own SD socket is not used |

## Behaviour

- **Card in:** the firmware polls every 250 ms, reads the MBR, and mounts
  partition 2 Side A only if the card is exactly the WP-14 §3.1 layout. Any other
  card is refused (`CARD REFUSED NOT_PROVISIONED`) and never written.
- **Play** prefills the play ring, then renders from the current position at 1.0×.
- **Stop** stops rendering; the position is kept (`POSITION n` is printed).
- **End of side:** audio stops at `at_end` (`END OF SIDE`). LEDs come with WP-20.
- **Card out:** a failed status poll or service read stops audio and unmounts
  as cleanly as it can (`CARD GONE`). Play writes nothing, so a pull mid-play
  has nothing to tear.
- **Concurrency:** `tape_render` runs in the audio interrupt only. Every other
  engine call is from the main loop, with the audio interrupt masked around it
  while the player is rendering, so the engine never sees a preempted call.

Serial status lines are at 115200 on the USB serial port.

## Golden mode (F1)

Make a golden card from the WP-11 sources with `tapectl`, the same steps as
`tests/golden/MANIFEST` but on the card instead of a bare image. `tapectl`
device commands follow the WP-14 §5 disk-safety rules; Michael runs them. For
`play-1x-quiet`:

```bash
tapectl provision CARD --label R63 --length-s 60 --uuid 00112233445566778899aabbccddeeff --epoch 1 --erase CARD
```

```bash
tapectl load CARD tests/golden/src/quiet.wav
```

Put the card in the Teensy, then from the PC (needs `pip install pyserial`):

```bash
python firmware/bench/tools/golden_serial.py --port COM5 --ref tests/golden/ref/play-1x-quiet.wav --mode golden --side A --from 0 --frames 198450
```

Modes: `golden` prints the SHA-256 of the PCM rendered in the deterministic
order; `stream` sends the PCM back for a byte comparison; `live` plays through
the audio interrupt exactly as heard and hashes every frame it renders, to the
end of the side. The serial commands themselves are:

```text
info
golden A|B FROM FRAMES      FRAMES 0 = to the end of the side
stream A|B FROM FRAMES      "PCM", then runs of (u32 LE frame count, PCM), then a 0 count
live   A|B FROM
```

Each ends with `SHA256 <hex> FRAMES <n> RESULT <tape_result>`.

## Off-target checks (CI)

```bash
make -C engine all && make -C host && make -C firmware/bench/host
```

```bash
python3 firmware/bench/host/run_checks.py --fwhost build/fwhost/fwhost --tapectl build/host/tapectl --out build/fwhost/checks
```

This runs the firmware's own `fw_part`/`fw_play` over `engine/port/dev_file`:
the WP-14 image fixtures through the partition view (mount equivalence with the
bare fixtures, refusals, one-block writes); all seven WP-11 goldens at 1.0×
(`play-1x-quiet`, `play-1x-fortissimo`, `splice`, `overdub`, `overwrite`,
`reset-b` and `promote`), each in the deterministic and the live loop, byte-exact;
and the F1 negative controls (one altered sample, rate 1.0× + 1), which must fail.

## Not run without the bench

Actual playback through the SGTL5000, Play/Stop and removal on hardware (F5),
the stack high-water mark from the painted stack (F2 target half; `info` prints
`stack_high_water`), warm wake to
audio (F3), commit latency (F4, with WP-18/19), F1 on target, and the SDIO
flush busy-wait on a real card.
