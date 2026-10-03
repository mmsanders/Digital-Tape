/*
 * tape_test_hooks.c — see tape_test_hooks.h. HOST AND TEST BUILDS ONLY.
 *
 * play_interpolate() is static in engine/src/play.c, and the engine source is
 * not changed to expose it. Instead this translation unit compiles that exact
 * file and adds one wrapper. Consequences, by construction:
 *
 *   - libtape.a and every firmware object are byte-identical with or without
 *     this file; it is never in engine/Makefile's sources.
 *   - A program links this object AHEAD of libtape.a. This object defines every
 *     external symbol play.c defines, so the linker never extracts play.o from
 *     the archive and there is exactly one copy of each.
 *   - The differential harness exercises the same source text tape_render runs.
 *
 * Build with the engine's include paths: -Iengine/include -Iengine/src.
 */

#include "../src/play.c"
#include "tape_test_hooks.h"

int16_t tape_test_interp(int16_t a, int16_t b, uint32_t f)
{
    return play_interpolate(a, b, f);
}
