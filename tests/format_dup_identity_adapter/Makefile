CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
          -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
          -Wpointer-arith -Wwrite-strings -fno-common -g -O1
ENGINE_INC ?= ../../engine/include
ENGINE_SRC ?= ../../engine/src
ENGINE_LIB ?= ../../build/engine/libtape.a
OUT ?= build/r29_format_dup_worker
OBJ ?= build/r29_format_dup_worker.o

CPPFLAGS := -I$(ENGINE_INC) -I$(ENGINE_SRC) -DTAPE_PUBLIC_HEADER='"tape.h"'
LDLIBS := -lcrypto

.PHONY: all clean mutant
all: $(OUT)

# #467 control only: the source binding gets a write callback.
mutant: build/r29_format_dup_worker_s467_mutant
build/r29_format_dup_worker_s467_mutant: r29_format_dup_worker.c
	@mkdir -p build
	$(CC) $(CPPFLAGS) -DS467_SOURCE_WRITE_MUTANT $(CFLAGS) $< $(ENGINE_LIB) $(LDLIBS) -o $@

$(OBJ): r29_format_dup_worker.c
	@mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(OUT): $(OBJ)
	$(CC) $(OBJ) $(ENGINE_LIB) $(LDLIBS) -o $@

clean:
	rm -rf build
