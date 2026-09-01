#!/usr/bin/env bash
# CI gate 2 — guardrail 08: no allocation after init, no libc file I/O.
#
# Undefined symbol references in the engine archive are the check. If the engine
# never references malloc, it cannot call it, on any target, in any build.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

LIB=build/engine/libtape.a
NM=${NM:-nm}

# Allocation, and the libc surface that allocates or does file I/O behind your back.
FORBIDDEN='^(malloc|calloc|realloc|reallocarray|free|aligned_alloc|posix_memalign|valloc|memalign|strdup|strndup|asprintf|vasprintf|getline|getdelim|fopen|fdopen|freopen|fclose|fread|fwrite|fseek|fseeko|ftell|ftello|rewind|fgets|fputs|fprintf|vfprintf|fscanf|printf|puts|open|close|read|write|lseek|mmap|munmap|brk|sbrk)$'

echo "== gate: static allocation audit =="
if [ ! -f "$LIB" ]; then
  echo "FAIL  $LIB not built — cannot audit"
  exit 1
fi

# Undefined (U) symbols only: what the archive expects the linker to supply.
hits=$($NM --undefined-only --format=posix "$LIB" 2>/dev/null \
  | awk '{print $1}' | sed 's/@.*//; s/^_//' | sort -u \
  | grep -E "$FORBIDDEN" || true)

if [ -n "$hits" ]; then
  echo "FAIL  engine references forbidden symbols:"
  printf '        %s\n' $hits
  echo
  echo "      Guardrail 08: no allocation in the engine after init, no libc file"
  echo "      I/O — desktop build included. Block access goes through the two"
  echo "      function pointers, not through the C library."
  exit 1
fi
echo "PASS  no allocation or libc file I/O referenced"
