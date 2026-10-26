# Supplemental CC0 encodings

short-trim.mp3: fixtures.signal(44100,256,1), formats.wave signed16, encoded
with FFmpeg6.1.1 `-map_metadata -1 -c:a libmp3lame -q:a 3`. Actual raw interval
2304 frames, declared head1105/tail943, effective256. Its out-of-range negative
changes only delay/padding to4095/4095 and repairs the valid writer tag CRC.

Input: fixtures.signal(44100,44100,channels1/2), independent mathematical CC0
signal, quantized by formats.wave to signed16-bit. No music downloaded.
Reference encoder: public mstorsjo/fdk-aac commit
c41c3c7516ea8d0d78a53b96b30bed3a29745cc6, CMake Release/GCC13.3, local build.
Only harness change: immediately before AACENC_TRANSMUX, call
`aacEncoder_SetParam(handle,AACENC_PROTECTION,1)`.

Commands: aac-enc source-1.wav fdk-crc-1.aac;
aac-enc source-2.wav fdk-crc-2.aac;
aac-enc -t5 source-2.wav he-aac.aac;
aac-enc -t29 source-2.wav he-aac-v2.aac. All encoder exits0/stderr empty.
Raw output bytes are frozen, per-file hashes in SOURCES.json. Candidate platforms
fetch these bytes, never rebuild the encoder. LC protected-frame positives and
checksum-byte-only negative derivatives establish a causal CRC requirement;
independently written minimal SCE/CPE vectors also verify CRC bit arithmetic.
HE profiles are actual generated outside-scope encodings, not renamed LC headers.

Supplemental exclusions: FFmpeg6.1.1 `-i source-2.wav -map_metadata -1
-c:a pcm_s16le -f w64 wave64.w64`; `-i source-2.wav -f lavfi -i
color=c=black:s=16x16:r=1 -map0:a:0 -map1:v:0 -map_metadata -1 -c:a aac
-c:v mpeg4 -t1 audio-video.mp4` (option/value spacing as normal CLI). Both exits0.
LayerI: independently generated4 MPEG1/LayerI mono44.1k128kbps frames, header
FFFF40C0 and132 zero bytes per frame, all32 subband bit allocations zero. Actual
FFmpeg decode exits0 and yields1536 mono zero frames. All three are recognized
valid outside-scope formats, not corrupt substitutes. Original signal/black frame
and derived bytes are CC0; source hashes and recipe identity are pinned.

The optional local aac-dec executable lacked execute permission and was not run;
no permission bypass or native decoder qualification is claimed. Authoring uses
FFmpeg6.1.1 only for raw count/profile checks (not CRC validation); generated CRC
arithmetic is checked independently. No external codec code/binary is distributed.
