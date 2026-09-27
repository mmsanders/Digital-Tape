CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
          -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
          -Wpointer-arith -Wwrite-strings -fno-common -g -O1
ENGINE_INC ?= ../../engine/include
ENGINE_LIB ?= ../../build/engine/libtape.a

CPPFLAGS := -I$(ENGINE_INC) -DTAPE_PUBLIC_HEADER='"tape.h"'

.PHONY: all clean
all: build/librespool_full.so build/respool_longop_probe

build/respool_full_worker.o: respool_full_worker.c
	@mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -fPIC -c $< -o $@

build/librespool_full.so: build/respool_full_worker.o
	$(CC) -shared $< $(ENGINE_LIB) -lcrypto -o $@

build/respool_longop_probe.o: respool_longop_probe.c
	@mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

build/respool_longop_probe: build/respool_longop_probe.o
	$(CC) $< $(ENGINE_LIB) -o $@

clean:
	rm -rf build
