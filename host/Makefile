# host/ — tapectl (docs/WP11-CLI-CONTRACT.md, extended by docs/WP14-CLI-CONTRACT.md).
#
#   make -C host          build/host/tapectl and build/host/tapectl-test
#   make -C host test     WAV + port unit tests, the WP-11 smoke, the WP-14 image smoke,
#                         and the TAPECTL_TEST seam check
#
# tapectl links the unchanged engine (libtape.a) and the WP-14 host port in
# host/port/. It composes the public API and reimplements no engine behaviour
# (guardrail 12). tapectl-test is the same program with -DTAPECTL_TEST: it adds
# the disk-safety facts seam (host/port/facts_test.c) and nothing else. The
# shipped binary is tapectl, which must not contain the seam (test_seam.sh).

CC      ?= cc
BUILD   ?= ../build/host
ENGINE  := ../build/engine
WARN    := -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
           -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
           -Wpointer-arith -Wwrite-strings
CFLAGS  ?= -O2 -g
ALL_CFLAGS := -std=c99 $(WARN) $(CFLAGS)
CPPFLAGS := -I../engine/include -I. -Iport

COMMON  := target.c port/mbr.c port/fat.c port/safety.c port/partview.c port/entropy.c

ifeq ($(OS),Windows_NT)
  EXE      := .exe
  PLATFORM := port/hport_win.c port/probe_win.c
  SYSLIBS  := -lbcrypt -lpsapi -lshell32
else
  EXE      :=
  UNAME    := $(shell uname -s)
  ifeq ($(UNAME),Darwin)
    PLATFORM := port/hport_posix.c port/probe_macos.c
    SYSLIBS  := -framework CoreFoundation -framework DiskArbitration -framework IOKit -framework Security
  else
    PLATFORM := port/hport_posix.c port/probe_linux.c
    SYSLIBS  :=
  endif
endif

PORT_SRC  := $(COMMON) $(PLATFORM)
PORT_HDR  := target.h port/hport.h port/layout.h port/safety.h port/entropy.h port/winutf.h

TAPECTL   := $(BUILD)/tapectl$(EXE)
TAPECTL_T := $(BUILD)/tapectl-test$(EXE)
TEST_WAV  := $(BUILD)/test_wav$(EXE)
TEST_PORT := $(BUILD)/test_port$(EXE)
LIBS      := $(ENGINE)/libtape.a

.PHONY: all test test-bins engine clean
all: $(TAPECTL) $(TAPECTL_T)

# The engine's own Makefile decides whether its archives are current.
engine:
	$(MAKE) -C ../engine all

$(LIBS): engine

$(BUILD):
	@mkdir -p $@

$(TAPECTL): tapectl.c wav.c wav.h $(PORT_SRC) $(PORT_HDR) $(LIBS) | $(BUILD)
	$(CC) $(CPPFLAGS) $(ALL_CFLAGS) tapectl.c wav.c $(PORT_SRC) $(ENGINE)/libtape.a $(SYSLIBS) -o $@

$(TAPECTL_T): tapectl.c wav.c wav.h $(PORT_SRC) $(PORT_HDR) port/facts_test.c $(LIBS) | $(BUILD)
	$(CC) $(CPPFLAGS) -DTAPECTL_TEST $(ALL_CFLAGS) tapectl.c wav.c $(PORT_SRC) port/facts_test.c \
	    $(ENGINE)/libtape.a $(SYSLIBS) -o $@

$(TEST_WAV): test_wav.c wav.c wav.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(ALL_CFLAGS) test_wav.c wav.c -o $@

$(TEST_PORT): test_port.c $(PORT_SRC) $(PORT_HDR) | $(BUILD)
	$(CC) $(CPPFLAGS) $(ALL_CFLAGS) test_port.c $(PORT_SRC) $(SYSLIBS) -o $@

test-bins: $(TAPECTL) $(TAPECTL_T) $(TEST_WAV) $(TEST_PORT)

test: test-bins
	./run_tests.sh $(BUILD) $(EXE)

clean:
	@rm -rf $(BUILD)
