CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
          -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
          -Wpointer-arith -Wwrite-strings -fno-common -g -O2
ENGINE_INC ?= ../../engine/include
ENGINE_LIB ?= ../../build/engine/libtape.a
OUT ?= build/wp08_adapter

# Public header only: no engine/src include path.
CPPFLAGS := -I$(ENGINE_INC)

.PHONY: all clean
all: $(OUT)

$(OUT): wp08_adapter.c $(ENGINE_LIB)
	@mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) wp08_adapter.c $(ENGINE_LIB) -o $@

clean:
	rm -rf build
