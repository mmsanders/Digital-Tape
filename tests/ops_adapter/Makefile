# VT8-001 mechanical adapter build.
#
# Nothing here is product code. ENGINE_INC/ENGINE_LIB select which candidate
# engine the probe is linked against, so the same adapter source can be pointed
# at main, a held branch, or a later candidate without editing it.
#
#   make ENGINE_INC=../../engine/include ENGINE_LIB=../../build/engine/libtape.a
#
# `compile` stops after -c so a compile gap and a link gap are separable facts.

CC      ?= cc
CFLAGS  ?= -std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wstrict-prototypes \
           -Wmissing-prototypes -Wvla -Wcast-qual -Wpointer-arith -fno-common -g -O1
ENGINE_INC ?= ../../engine/include
ENGINE_LIB ?= ../../build/engine/libtape.a
OUT        ?= build/vt8_ops_probe
OBJ        ?= build/vt8_ops_probe.o

CPPFLAGS := -I$(ENGINE_INC) -DTAPE_PUBLIC_HEADER='"tape.h"'

.PHONY: all compile clean
all: $(OUT)

compile: $(OBJ)

$(OBJ): vt8_ops_probe.c
	@mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c vt8_ops_probe.c -o $(OBJ)

$(OUT): $(OBJ)
	@mkdir -p build
	$(CC) $(OBJ) $(ENGINE_LIB) -o $(OUT)

clean:
	rm -rf build
