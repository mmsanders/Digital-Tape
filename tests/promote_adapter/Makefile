CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
          -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
          -Wpointer-arith -Wwrite-strings -fno-common -g -O2
ENGINE_INC ?= ../../engine/include
ENGINE_SRC ?= ../../engine/src
ENGINE_LIB ?= ../../build/engine/libtape.a
OUT ?= build/r29a_promote_worker
OBJ ?= build/r29a_promote_worker.o

CPPFLAGS := -I$(ENGINE_INC) -I$(ENGINE_SRC)
LDLIBS := -lcrypto

.PHONY: all clean
all: $(OUT)

$(OBJ): r29a_promote_worker.c
	@mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -Wno-deprecated-declarations -c $< -o $@

$(OUT): $(OBJ) $(ENGINE_LIB)
	$(CC) $(OBJ) $(ENGINE_LIB) $(LDLIBS) -o $@

clean:
	rm -rf build
