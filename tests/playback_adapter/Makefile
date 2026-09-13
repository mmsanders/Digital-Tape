# DRAFT-8 playback adapter build. Product-side plumbing only; no engine code.
#
# ENGINE_INC/ENGINE_LIB select which candidate engine is linked, so the same
# adapter source can target current main, a held branch, or a later candidate
# without being edited.
#
#   make ENGINE_INC=../../engine/include ENGINE_LIB=../../build/engine/libtape.a
#
# `compile` stops after -c so a compile gap and a link gap stay separable facts.

CC      ?= cc
CFLAGS  ?= -std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wstrict-prototypes \
           -Wmissing-prototypes -Wvla -Wcast-qual -Wpointer-arith -fno-common -g -O1
ENGINE_INC ?= ../../engine/include
ENGINE_LIB ?= ../../build/engine/libtape.a
OUT        ?= build/playback_probe
OBJ        ?= build/playback_probe.o

CPPFLAGS := -I$(ENGINE_INC) -DTAPE_PUBLIC_HEADER='"tape.h"'

.PHONY: all compile clean
all: $(OUT)

compile: $(OBJ)

$(OBJ): playback_probe.c
	@mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c playback_probe.c -o $(OBJ)

$(OUT): $(OBJ)
	@mkdir -p build
	$(CC) $(OBJ) $(ENGINE_LIB) -o $(OUT)

clean:
	rm -rf build
