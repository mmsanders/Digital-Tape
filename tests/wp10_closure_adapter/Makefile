CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
          -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
          -Wpointer-arith -Wwrite-strings -fno-common -g -O2
ENGINE_INC ?= ../../engine/include
ENGINE_LIB ?= ../../build/engine/libtape.a
OUT ?= build/wp10c_adapter

# Public header only: no engine/src include path.
CPPFLAGS := -I$(ENGINE_INC)
LDLIBS := -lcrypto

.PHONY: all clean
all: $(OUT)

$(OUT): wp10c_adapter.c $(ENGINE_LIB)
	@mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -Wno-deprecated-declarations wp10c_adapter.c $(ENGINE_LIB) $(LDLIBS) -o $@

clean:
	rm -rf build
