# WP14 tested physical delivery — Software #392 / Michael #386

Software/CI PASS: independently published Verification PR158 at
`cb81a5edd2c9e1b0039ed71ecdd61b54f91033e6`. Exact Product #390 head
`5e2df5aaf23e9ed0e230c444a40650da9459ddb2`, root
`7b8204085582bf5422cc902d82c4c02a6998fd98`, accepted engine
`d96b4245e04d74078f8938744b1394c3018516f7`.
Engine run `37881873450`, attempt 1. These are the shipped binaries actually
tested in that run, copied without rebuilding. Native instrumentation builds
are separate and must never be used on a physical card.

Release: https://github.com/mmsanders/Digital-Tape/releases/tag/wp14-tapectl-5e2df5aaf23e
Download the named assets, SHA256SUMS, build-info files and REAL-CARD.md there.
Release readiness requires Verification's served-asset authentication; publication
alone is not acceptance or permission to assume machine compatibility.

| Asset | Architecture / machine requirement | SHA-256 |
|---|---|---|
| tapectl-macos | Apple Silicon arm64, macOS 26.0 or later; tested 26.6.2 build25G83 | `e7550d8bedbb0c784fd528c387a87cca2bad8d1b411c39217d25377329bb0beb` |
| tapectl-windows.exe | x86_64; built/tested Server2025, physical Windows10 execution still required | `82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9` |
| tapectl-linux | x86_64 Ubuntu24.04.5 CI; supplemental, not either physical witness | `4d8c97a44f163bcd513c98c0903db6a01418001f169cfd6aa126823f6f7a785c` |

## Prepare without touching a card

On Mac, record `uname -m` and `sw_vers` first. An Intel Mac or macOS older than
26.0 cannot run this qualified asset; stop and report that actual mismatch to
#392/#146 before the witness. Do not substitute an untested build.
Save `shasum -a 256 tapectl-macos`; require the exact hash above, then
`cp tapectl-macos tapectl` and `chmod +x tapectl`. Preserve download provenance.
On Windows10, record the OS version/build and use
`Get-FileHash .\tapectl-windows.exe -Algorithm SHA256`; require the exact hash,
then `Copy-Item .\tapectl-windows.exe .\tapectl.exe`. If either executable
cannot launch, report the error and leave platform readiness held.

Get the source/checklist support files from the exact reviewed commit:

```sh
git clone https://github.com/mmsanders/Digital-Tape.git
cd Digital-Tape
git checkout --detach 5e2df5aaf23e9ed0e230c444a40650da9459ddb2
python3 -c "import sys; sys.path.insert(0,'tests/wp14_r1'); from runner import make_c60; make_c60('C60.wav')"
```

Python3 is used only to generate the canonical source; it rebuilds no Product
binary. C60.wav is 635,040,044 bytes, 158,760,000 signed16 stereo frames at
44.1kHz, SHA256
`c7369c6fdcb476fcc7f6a9d68aaab276f68a4d316ffb595faabb736e6046495d`.
Keep it and the unchanged `tests/golden/src/quiet.wav` off the card. Put the
verified shipped executable in this repository root so the checklist's relative
quiet.wav path resolves. Use this same exact C60 source on both machines.
The release REAL-CARD.md is byte-identical to the independently published
method. Its old awaiting-release heading is historical; this separate delivery
supplies actual binary identities without editing the imported verifier package.

## Physical execution and evidence

Follow REAL-CARD.md in order only after served-asset/readiness authentication.
Use one positively identified owned PNY64GB card; provisioning erases it.
Record part number/capacity/revision/CID (or explicitly unavailable), reader,
device number, OS/build, binary hash and exact target confirmation. Remove other
external disks. Never enable TAPECTL_TEST facts or bypass a safety refusal.

The original plain commands capture Mac provision/load times, physical
eject/reinsert, verify and exact A/B WAV comparisons, Finder partition1/README
bytes/screenshot, ten genuinely mid-load pulls, Windows10 readback of the Mac
card, then fresh Windows provision/load/reinsert/dumps/Explorer README. Record
all exit codes and WAV lengths/hashes; neither exit1 nor exit0 alone classifies
an interruption. Verification maps every pull to WP10 permitted outcomes.
Preserve failed/unclassified media before another write. Finish the successful
Mac roundtrip again after the pulls before moving the card to Windows.

Physical A6 additionally needs a native capture showing the exact shipped
binary's mirror IO at reported card capacity minus512, beyond4GiB. CI virtual
captures do not prove this physical access. If the actual machine lacks an
approved capture method, collect the other observations and keep A6 held;
do not substitute a test binary or infer the access from capacity alone.

Return observations to Verification #146 and Product #386. A9 reports actual
physical provision/load wall times without inventing a new timing gate.
Mac architecture/OS compatibility, physical Windows10, A1/A2/A3/A6/A9,
media/atomicity, hardware, target-system copy<30s, write/async/recording and
phase holds remain explicit until independently discharged. Server2025 is
supplemental. Michael alone merges #390; integration is not full WP14 acceptance.
