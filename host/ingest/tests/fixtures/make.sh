#!/bin/sh
# Regenerates the encoded fixtures: generated tones only (contract I8), ffmpeg 7.x.
# The committed bytes, not this script, are what the tests use; rerunning it with another
# ffmpeg build may produce different bytes and is not required.
set -eu
cd "$(dirname "$0")"
F="ffmpeg -nostdin -loglevel error -y -bitexact"
$F -f lavfi -i "sine=f=440:d=1:r=44100" -ac 2 -c:a libmp3lame -b:a 128k tone_cbr.mp3
$F -f lavfi -i "sine=f=440:d=1:r=48000" -ac 1 -c:a libmp3lame -q:a 4 tone_vbr_mono.mp3
$F -f lavfi -i "sine=f=440:d=1:r=44100" -ac 2 -c:a libmp3lame -b:a 128k -write_xing 0 tone_noxing.mp3
$F -f lavfi -i "sine=f=440:d=1:r=22050" -ac 2 -c:a libmp3lame -b:a 64k tone_mpeg2.mp3
$F -f lavfi -i "sine=f=440:d=1:r=48000" -ac 2 -c:a aac -b:a 128k tone.m4a
$F -f lavfi -i "sine=f=440:d=1:r=44100" -ac 2 -c:a aac -b:a 128k -movie_timescale 44100 tone_ts.m4a
$F -f lavfi -i "sine=f=440:d=1:r=32000" -ac 1 -c:a aac -b:a 64k -f adts tone.aac
$F -f lavfi -i "sine=f=440:d=1:r=44100" -ac 2 -c:a flac tone16.flac
$F -f lavfi -i "sine=f=440:d=0.25:r=96000" -ac 2 -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 tone24.flac
$F -f lavfi -i "sine=f=440:d=1:r=44100" -ac 2 -c:a mp2 -b:a 192k tone.mp2
$F -f lavfi -i "sine=f=440:d=1:r=44100" -ac 2 -c:a alac tone_alac.m4a
$F -f lavfi -i "sine=f=440:d=1:r=44100" -f lavfi -i "color=c=black:s=16x16:d=1" -c:a aac -c:v mpeg4 -shortest tone_video.mp4
$F -f lavfi -i "sine=f=440:d=1:r=44100" -ac 2 -c:a flac -f ogg tone.oga
