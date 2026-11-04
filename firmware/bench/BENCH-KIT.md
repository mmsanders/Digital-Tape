# WP-17 first bench session: capture packet (BE-1)

This is the hand-held checklist for the first scoped bench session. It covers F1, F2 and F5 on target. It is **not an authorization**: a session needs parts in hand and a separately scoped Michael session (BE-1).

The interface is [BE1-IF/3](../../docs/WP17-BE1-INTERFACE.md); the contract is [BE-1](../../docs/WP17-BENCH-EVIDENCE.md).

**Out of this packet:**
- **F3** (wake time) stays NOT RUN until the dedicated witnessed timing method exists. Firmware timestamps are development aids only.
- **F4** (commit latency) stays with WP-18/19.
- **No** cells, charging, power-cut rig or automatic card preparation.
- **Power:** USB only.

## 1. Pinned inputs

Record each of these in the manifest's `candidate`.

| Input | Value |
|---|---|
| Product commit | The merged commit the firmware was built from |
| Engine tree | `d96b4245e04d74078f8938744b1394c3018516f7` |
| Firmware image | `firmware.hex` from the CI artifact `wp17-firmware-teensy41` for that commit. Its SHA-256 is `firmware_hex_sha256` and must match the artifact's `SHA256SUMS`. |
| Toolchain | PlatformIO 6.1.19 · `platformio/teensy@6.0.0` · `framework-arduinoteensy@1.162.0` · `tool-teensy@1.162.0` · `toolchain-gccarmnoneeabi-teensy@1.150201.0` |
| Capture | `firmware/bench/tools/bench_capture.py` (version `BE1-IF/3`) with pyserial |
| Checker | `firmware/bench/tools/bench_evidence.py`, offline |

**Keep from the CI artifact:** `firmware.hex`, `size-gate.txt` and `SHA256SUMS`. All three go in the bundle.

## 2. Wiring

| Function | Teensy 4.1 pin | Notes |
|---|---|---|
| Play | 2 | Momentary switch to GND; internal pull-up |
| Stop | 3 | Momentary switch to GND; internal pull-up |
| I²S to SGTL5000 | 7, 8, 20, 21, 23 | Audio adaptor stacked on the Teensy |
| I²C to SGTL5000 | 18, 19 | Audio adaptor control |
| Cartridge | Built-in microSD slot | The adaptor's own SD socket is not used |
| Power and serial | USB | 115200, USB serial |

## 3. First start (no card, nothing loud)

1. **Headphones off the ears.** Before any card plays, check that the output level is the fixed low FW-1 level (0.20). Raise nothing. The 85 dB cap is not claimed by this kit.
2. **Flash** the pinned `firmware.hex` with Teensy Loader.
3. **Check the boot banner.** Open the serial monitor. `DIGITAL-TAPE BENCH WP-17` must appear.
   - If a `FATAL instance …` line appears instead, stop. Capture it with `--until-info --send info` and return it; it is F2 evidence.

## 4. Cards (manual, Michael runs `tapectl`)

Card preparation follows the WP-14 §5 disk-safety contract. `tapectl` refuses unsafe targets itself; this kit never provisions or erases anything automatically.

**Preparing a golden card:**
- Repeat the case's `tests/golden/MANIFEST` steps on the card.
- `format IMAGE …` becomes `provision CARD … --erase CARD`, with the same `--label R63 --length-s 60 --uuid 00112233445566778899aabbccddeeff --epoch 1`.
- Each later step names `CARD` instead of the image.
- See README "Golden mode" for `play-1x-quiet`.
- Record the card identity (manufacturer, part number, capacity, revision, and CID if known) **before** each session.
- A USB reader usually cannot read the CID. Record `null`; this kit never claims WP-05 identity.

## 5. Captures

Each capture is a new file in the bundle. **Never overwrite or delete a failed attempt:** keep it, and mark it `superseded_by` the retry, with the reason.

### F1, seven cases

For each case, run all three steps:
1. Prepare its card (§4).
2. Insert the card and wait for `CARD MOUNTED`.
3. Run `bench_capture.py`.

The command is fixed by the MANIFEST; any other line is a `f1_command_mismatch`.

| Case | Command (`golden`; `stream` takes the same arguments) | `live` |
|---|---|---|
| `play-1x-quiet`, `play-1x-fortissimo` | `golden A 0 198450` | `live A 0` |
| `splice`, `overdub`, `overwrite`, `reset-b` | `golden B 0 0` | `live B 0` |
| `promote` | `golden A 0 0` | `live A 0` |

```bash
python firmware/bench/tools/bench_capture.py --port COM5 --out f1-play-1x-quiet-1.raw --until-digest --send "golden A 0 198450"
```

A `stream` capture holds the PCM itself; above 1 MiB it goes to a release asset with its hash (§7).

### F5, one observation

**Capture the session** without sending any command, and stop it with Ctrl+C after the card is out:

```bash
python firmware/bench/tools/bench_capture.py --port COM5 --out f5-1.raw --until-interrupt
```

**Michael's order of operations:**
1. Insert the card.
2. Play.
3. Wait a few seconds, then Stop.
4. Play.
5. Wait, then Stop. The second `POSITION` must exceed the first.
6. Play.
7. While audio is playing, pull the card.

**Afterwards, by hand:** run the verify on the same card, saving its output and exit status:

```bash
tapectl verify CARD > f5-verify.txt
```

Then record the card identity again and the witness statement. The witness must be present for `play_stop`, `removal` and `verify`.

### F2, last

`info` is sent **after** all F1 and F5 captures, so the stack high-water mark covers them:

```bash
python firmware/bench/tools/bench_capture.py --port COM5 --out f2-info-1.raw --until-info --send info
```

## 6. Bundle and manifest

Put every file in one directory with `manifest.json` (schema `digital-tape/be1-session/1`, §2 of BE1-IF/3).

| Key | What to record |
|---|---|
| `session.kind` | `physical` |
| `session.timestamp` | The session start, RFC 3339 with offset |
| `session.capture_tool` | `{"name": "bench_capture.py", "version": "BE1-IF/3"}` |
| `requested` | `["F1", "F2", "F5"]` |
| Each `files` entry | Path, SHA-256 and byte count |
| Each F1 observation | `case`, `mode`, the exact `command` that `bench_capture.py` printed, and `reference_wav_sha256` from `tests/golden/SHA256SUMS` |
| `sequence` | Numbered in capture order |

**Observations:**
- Anything not captured is a `not_run` observation with a reason. Do not leave it out, and never write a zero for a missing value.
- `provenance` is `actual` only for bytes that really came from the bench.

## 7. Check and return

**Check the bundle offline:**

```bash
python firmware/bench/tools/bench_evidence.py --offline BUNDLE --out REPORT.json
```

`CONSISTENT` with `complete: true` means only that the saved artifacts agree with each other and with the references. Verification still audits the raw bytes and the witness context, and nothing here is target acceptance.

**Return checklist:**
- [ ] The bundle directory, with nothing removed and failed attempts kept.
- [ ] Files over 1 MiB are uploaded as release assets, with `release_asset` and their hash in the manifest.
- [ ] `REPORT.json` and the checker's exit status.
- [ ] Card identity before and after, the witness statement, and the `tapectl verify` output and exit status.
- [ ] Anything unexpected heard or seen, in `note` fields. Silence or a loud output is recorded, not retried quietly.
