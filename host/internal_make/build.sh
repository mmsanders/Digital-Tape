#!/usr/bin/env bash
# Compile exact reference and retained-session component; NEVER execute either here.
set -euo pipefail
export PATH="/c/mingw64/bin:$PATH"
ref=bf2381c9c187c14ce65cc501b13f9eb512c99693
out=build/internal-make
mkdir -p "$out" host/internal_make/reference
git show "$ref:host/tapectl.c" > host/internal_make/reference/tapectl.c
git show "$ref:host/target.c" > host/internal_make/reference/target.c
git rev-parse HEAD > "$out/source-head.txt"
git rev-parse "$ref:host/tapectl.c" "$ref:host/target.c" HEAD:engine HEAD:spec > "$out/source-trees.txt"
gcc --version > "$out/compiler.txt"
MAKE=$(command -v mingw32-make || command -v make)
"$MAKE" -C engine CC=gcc all
# Debug adapter build avoids optimizing unused embedded shipping entrypoints.
# All warnings remain fatal; engine keeps its unchanged strict optimized build.
flags=(-std=c99 -O0 -g -Wall -Wextra -Werror -Iengine/include -Ihost -Ihost/port -Ihost/internal_make)
head=$(git rev-parse HEAD)
platform=(host/port/hport.c host/port/hport_win.c host/port/probe_win.c host/port/discover_win.c)
support=(host/wav.c host/report.c host/port/discover.c host/port/mbr.c host/port/fat.c host/port/safety.c host/port/entropy.c)
objects=()
for f in "${platform[@]}"; do
  obj="$out/$(basename "$f" .c).o"
  gcc "${flags[@]}" -c "$f" -o "$obj"
  objects+=("$obj")
done
observed=()
for f in "${support[@]}" host/port/partview.c; do
  obj="$out/$(basename "$f" .c).o"
  gcc "${flags[@]}" -include host/internal_make/observe.h -c "$f" -o "$obj"
  observed+=("$obj")
done
for mode in reference composition; do
  extra=(); target=host/target.c
  if [ "$mode" = reference ]; then extra=(-DIM_REFERENCE); target=host/internal_make/reference/target.c; fi
  gcc "${flags[@]}" -DTAPECTL_INTERNAL_COMPOSE -include host/internal_make/observe.h -c "$target" -o "$out/target-$mode.o"
  gcc "${flags[@]}" "${extra[@]}" -DTAPECTL_INTERNAL_COMPOSE -DIM_HEAD=\""$head"\" \
    host/internal_make/adapter.c host/internal_make/core.c "$out/target-$mode.o" \
    "${objects[@]}" "${observed[@]}" build/engine/libtape.a -lbcrypt -lpsapi -lshell32 -lsetupapi \
    -o "$out/$mode.exe"
done
sha256sum "$out/reference.exe" "$out/composition.exe" > "$out/binaries.sha256"
git status --short > "$out/build-working-tree.txt"
echo 'Compiled exact ordinary-file adapters; ZERO Product/image/runtime execution'
