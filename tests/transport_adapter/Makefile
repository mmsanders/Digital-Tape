CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
          -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
          -Wpointer-arith -Wwrite-strings -fno-common -g -O1
ENGINE_INC ?= ../../engine/include
ENGINE_LIB ?= ../../build/engine/libtape.a
OUT ?= build/wp_transport_probe
OBJ ?= build/wp_transport_probe.o

CPPFLAGS := -I$(ENGINE_INC) -DTAPE_PUBLIC_HEADER='"tape.h"'

.PHONY: all clean
all: $(OUT)

$(OBJ): wp_transport_probe.c
	@mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(OUT): $(OBJ)
	$(CC) $(OBJ) $(ENGINE_LIB) -o $@

clean:
	rm -rf build
