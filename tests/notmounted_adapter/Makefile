CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
          -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
          -Wpointer-arith -Wwrite-strings -fno-common -g -O1
ENGINE_INC ?= ../../engine/include
ENGINE_LIB ?= ../../build/engine/libtape.a
VERIFIER_PROBE ?= ../notmounted_draft8/wp06h_probe.c
OUT ?= build/wp06h_probe
OBJ ?= build/wp06h_probe.o

CPPFLAGS := -I$(ENGINE_INC) -DTAPE_PUBLIC_HEADER='"tape.h"'

.PHONY: all clean
all: $(OUT)

$(OBJ): $(VERIFIER_PROBE)
	@mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(OUT): $(OBJ)
	$(CC) $(OBJ) $(ENGINE_LIB) -o $@

clean:
	rm -rf build
