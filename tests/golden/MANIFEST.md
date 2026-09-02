# The golden-suite contract

**For the Verification Lead.** This directory is yours. This file describes the shape the runner
expects, so that test source you return lands and runs without anyone editing it.

The runner, the byte-exact comparison and the audible diff are built and working
(`tests/harness/`). What is missing is fixtures and a manifest. **Nothing here constrains what
you test or what you assert** — only how a case is named and invoked.

If this shape cannot express a case you need, that is a finding, not a reason to weaken the
case. Say so and the runner changes.

---

## `tests/golden/MANIFEST`

One case per line. Whitespace-separated. `#` begins a comment. Blank lines ignored.

```
<case-name>    <reference.wav>    <command...>
```

| Field | |
|---|---|
| `case-name` | Identifier, no spaces. Names the output and diff files |
| `reference.wav` | Path from the repository root. The definition of correct |
| `command` | Run from the repository root, via `sh -c`. Must write its WAV to `$GOLDEN_OUT` |

A case that exits non-zero fails without comparison, and its last five lines of output are
shown. A case that exits zero but writes nothing to `$GOLDEN_OUT` fails.

Example, once the engine has a CLI:

```
# name              reference                        command
play-1x             tests/golden/ref/play-1x.wav     build/host/tapectl play --rate 1.0 tests/golden/img/a.img -o "$GOLDEN_OUT"
scrub-4x            tests/golden/ref/scrub-4x.wav    build/host/tapectl play --rate 4.0 tests/golden/img/a.img -o "$GOLDEN_OUT"
overdub-softclip    tests/golden/ref/overdub.wav     build/host/tapectl overdub tests/golden/img/a.img tests/golden/src/voice.wav -o "$GOLDEN_OUT"
```

Run a subset by name substring: `tests/harness/run-golden.sh scrub`.

## WAV constraints

44.1 kHz, 16-bit, stereo, PCM. **Anything else is rejected, not converted.** Guardrail 01 fixes
the format and every other design decision rests on it — a reader that silently accepted a
48 kHz fixture would hide a guardrail violation inside a passing test. Extra chunks (`LIST`,
`INFO`) are skipped, so fixtures may carry metadata.

## Comparison is exact

No tolerance, no epsilon, and none will be added. Contract 3 makes the references the definition
of correct behaviour and requires firmware to be **bit-identical at 1.0× playback**. A "close
enough" golden suite cannot enforce a cross-target contract, because the divergence it permits is
exactly the divergence it exists to detect.

## The audible diff

Every failure writes `build/tests/golden/<case>.diff.wav` — reference minus actual, per sample.
Passages that agree are **silence**, so you hear only what went wrong and where. Alongside it:
first differing frame with a timestamp and channel, the two sample values and their delta, how
many samples differ, and the peak absolute delta.

That distinguishes failures a pass/fail bit cannot: a click at a splice, an inverted channel, a
one-frame offset, and a truncated tail all sound different and all report differently.

## Unit-style tests

If you return C rather than a fixture pair, it compiles against `engine/include/` and
`tests/harness/harness.h` — no framework dependency. `CHECK`, `CHECK_EQ_U32`, `CHECK_EQ_INT`,
`CHECK_MEM_EQ`, and `TAPE_TEST_REPORT(name)` as the return value of `main`. Drop it in
`tests/golden/`, `tests/crash/` or `tests/fuzz/` and it is wired in.

## Fault injection is already available

`engine/port/dev_sim.c` wraps any block device and injects:

- **power loss** — after N block writes, every subsequent write returns `TAPE_ERR_IO` forever.
  Blocks already written stay written
- **torn write** — the Nth write lands partially: `torn_bytes` of the block are written, the
  rest keeps its previous content, then the device dies. Real flash does not guarantee block
  atomicity, and a commit protocol that assumes it is untested against the thing it claims to
  survive

Counters (`writes_seen`, `reads_seen`, `flushes_seen`, `dead`) are readable, so a harness can
enumerate every write boundary rather than sampling. **The exhaustive harness over it is WP-10
and yours** — the device is only the capability.

Wrapping never manufactures a write path the inner device lacks, so a simulator over the source
slot still has `write == NULL` (guardrail 06).
