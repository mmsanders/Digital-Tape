# WP-11 finite interpolation differential, R63

Independent tests authored under Verification #143 before examining the candidate
implementation. `differential.c` includes only `tape_test_hooks.h` and calls
`int16_t tape_test_interp(int16_t,int16_t,uint32_t)` from the candidate's host/test
build. No engine implementation or reference algorithm is copied into this harness.

Expected values use signed 64-bit division and a negative-remainder correction to
floor; the executable oracle uses no bit shift on its signed product.

The census is 1,572,852 difference/boundary pairs, 10,000,000 PRNG triples, and 24
explicit extreme/boundary pairs: 11,572,876 comparisons per toolchain/configuration.
PRNG: xorshift32 (13,17,5), seed `0x63d10a5e`; three consecutive words per triple,
low 16 bits minus 32768 for each sample, full third word for the fraction. The
seed, draw order and signed mapping are part of the frozen test.

Build against the candidate object implementing the hook:

```
cc -std=c99 -O2 -Wall -Wextra -Werror -I engine/test tests/wp11_portability_r63/differential.c HOOK_OBJECTS -o build/wp11-differential
build/wp11-differential
```

Software owns that mechanical binding, linking and hook exposure. Stage 2 must
authenticate both toolchains (including the embedded target) and the narrow-int
configuration or the permitted `INT_MAX` assertion plus checked pre-subtraction
casts. A host synthetic pass is not that gate, and this finite suite is not a
claim to have executed the full ~5.6e14 domain. DRAFT-10 §8 supplies the proof.

`python3 selftest.py` runs a separately written synthetic conforming hook on GCC
and Clang and kills five causal arithmetic controls per toolchain. Local GCC
passes; Clang is absent locally and therefore is checked by the publication CI.
`--compiler gcc` selects just that local plumbing check. No Product verdict yet.
