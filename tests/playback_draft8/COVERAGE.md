# P1-R2-V coverage and assertion matrix

| ID | Assertion | DRAFT-8 authority | Control |
|---|---|---|---|
| PB8-A01 | Exact issued spec bytes, fixture archive/raw, metadata and candidate PCM hashes authenticate; all fixture/candidate bytes equal deterministic regeneration | `VERSION`; WP-11 | regeneration check; spec/fixture/PCM tamper |
| PB8-A02 | Valid three-run 15-frame non-constant Side-A fixture; expected timeline extracted from VO08 | TapeFS layout/index; WP-08 | fixture validation |
| PB8-A03 | +1.0x emits all 15 frames byte-exact, fetch-before-advance | Engine API §§6.2,6.3; WP-08 | exact comparison |
| PB8-A04 | Seek targets cover every run boundary and +/-1: 0,1,4,5,6,8,9,10 | §6.3; WP-08 V4-010 | wrong first frame |
| PB8-A05 | First output after each seek is frame N across run transitions | §6.3; WP-08 | run-boundary off-by-one |
| PB8-A06 | Reverse-from-end at -1.0x snaps to last frame on 32.32 grid | §§6.2,6.3; WP-08 V5-005 | historical `max_pos-1` |
| PB8-A07 | Exact full 15-frame reverse sequence, not first-sample-only | §§6.2,6.3; WP-08 | grid-drift mutation |
| PB8-A08 | Portable signed-floor interpolation rule; integral +/-1.0x remains grid aligned | §8; WP-11 | off-grid reverse differs |
| PB8-A09 | Public call results, rates, seeks, render counts and service completion match scripts | §§6.2,6.3 | wrong seek call |
| PB8-A10 | Whole callback trace is successful in-range reads only during mount/service | §§3,6.3 | injected render I/O |
| PB8-A11 | Offline replay hash-binds every evidence file and records declared verifier source identity before recomputing exact verdict | WP-11 | missing/tampered evidence; verifier-source-hash tamper |
| PB8-A12 | Mismatch identifies first frame/channel/values/delta/count/peak and can emit diff WAV | WP-11 | PCM mutations |
| PB8-A13 | Manifest adapter kind/ID equals observation kind/ID; source/build declarations exist; execution record and retained exit file prove zero exit | WP-11 evidence integrity | manifest-only kind relabel; manifest-only ID change; missing/nonzero exit |
| PB8-A14 | Runner never erases a nonempty evidence destination and bounds adapter execution while preserving failure diagnostics | WP-11 evidence retention | sentinel retention; timeout record |

Explicitly excluded: rate ramps; zero/one-frame/extreme-rate boundaries; `tape_set_side`; warm descriptors; recording; crash/recovery; long operations/state matrix; performance; human listening. Fixture creation is not golden acceptance; this package makes no product claim until separately run and dispositioned.
