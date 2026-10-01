CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
          -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
          -Wpointer-arith -Wwrite-strings -fno-common -g -O2
ENGINE_INC ?= ../../engine/include
ENGINE_LIB ?= ../../build/engine/libtape.a
PROGS := build/str55_adapter build/str55_capacity

# Public header only: no engine/src include path, for every program here.
CPPFLAGS := -I$(ENGINE_INC) -DTAPE_PUBLIC_HEADER='"tape.h"'
LDLIBS := -lcrypto

.PHONY: all clean
all: $(PROGS)

build/%: %.c $(ENGINE_LIB)
	@mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -Wno-deprecated-declarations $< $(ENGINE_LIB) $(LDLIBS) -o $@

clean:
	rm -rf build
