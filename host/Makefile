# host/ — tapectl (docs/WP11-CLI-CONTRACT.md) and its tests.
#
#   make -C host          build/host/tapectl (builds the engine archives first)
#   make -C host test     WAV unit tests and the format -> load -> dump smoke
#
# tapectl links the unchanged engine (libtape.a) and the file port
# (libtape_port.a). It composes the public API and reimplements no engine
# behaviour (guardrail 12).

CC      ?= cc
BUILD   ?= ../build/host
ENGINE  := ../build/engine
WARN    := -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
           -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
           -Wpointer-arith -Wwrite-strings
CFLAGS  ?= -O2 -g
ALL_CFLAGS := -std=c99 $(WARN) $(CFLAGS)
CPPFLAGS := -I../engine/include -I../engine/port

TAPECTL   := $(BUILD)/tapectl
TEST_WAV  := $(BUILD)/test_wav
LIBS      := $(ENGINE)/libtape.a $(ENGINE)/libtape_port.a

.PHONY: all test engine clean FORCE
all: $(TAPECTL)

# The engine's own Makefile decides whether its archives are current.
engine:
	$(MAKE) -C ../engine all

$(LIBS): engine

$(BUILD):
	@mkdir -p $@

$(TAPECTL): tapectl.c wav.c wav.h $(LIBS) | $(BUILD)
	$(CC) $(CPPFLAGS) $(ALL_CFLAGS) tapectl.c wav.c $(ENGINE)/libtape_port.a $(ENGINE)/libtape.a -o $@

$(TEST_WAV): test_wav.c wav.c wav.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(ALL_CFLAGS) test_wav.c wav.c -o $@

test: $(TAPECTL) $(TEST_WAV)
	$(TEST_WAV) $(BUILD)/test_wav.d
	./smoke.sh $(TAPECTL) $(BUILD)/smoke

clean:
	@rm -rf $(BUILD)
