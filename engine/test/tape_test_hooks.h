/*
 * tape_test_hooks.h — test-only entry points (ADR-158 item 3, #366).
 *
 * HOST AND TEST BUILDS ONLY. Nothing here is part of the engine library, the
 * firmware objects or the public API (engine/include/), and the WP-13 gates do
 * not see it: they audit engine/src and engine/include.
 *
 * tape_test_interp() reaches spec/engine-api.md §8's interpolation for all 2^32
 * fractions, which the public API cannot: Q16.16 rates never produce a 32-bit
 * fraction with non-zero low bits. It is a thin call into the engine's own
 * function, compiled from the unmodified engine/src/play.c — not a copy of it.
 */

#ifndef TAPE_TEST_HOOKS_H
#define TAPE_TEST_HOOKS_H

#include <stdint.h>

/* §8: a + floor((b - a) * f / 2^32), exactly as tape_render computes it. */
int16_t tape_test_interp(int16_t a, int16_t b, uint32_t f);

#endif /* TAPE_TEST_HOOKS_H */
