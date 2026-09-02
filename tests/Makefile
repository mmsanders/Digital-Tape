# Test scaffolding — Software Lead.
#
# Builds the harness self-tests under harness/. golden/, crash/ and fuzz/ belong
# to the Verification Lead; when test source arrives from it, it lands there and
# this Makefile grows a rule, not an opinion.

CC    ?= cc
BUILD ?= ../build/tests
ENG   ?= ../build/engine

CFLAGS += -std=c99 -Wall -Wextra -Werror -pedantic -g -O1
CPPFLAGS += -I../engine/include -I../engine/port -Iharness

SRC  := $(wildcard harness/test_*.c)
BINS := $(patsubst harness/test_%.c,$(BUILD)/test_%,$(SRC))
TOOLS := $(BUILD)/golden_diff

# Verification Lead's infrastructure, pulled from Digital-Tape-Verification.
# Implementation-independent: it does not link the engine and does not inspect
# it. Landed unmodified -- both binaries built and passed as issued, so no
# mechanical fix was needed. Do not edit these to make something pass.
CRASH_SRC  := $(wildcard crash/test_*.c)
CRASH_BINS := $(patsubst crash/test_%.c,$(BUILD)/crash_%,$(CRASH_SRC))

.PHONY: all run clean
all: $(BINS) $(TOOLS) $(CRASH_BINS)

$(BUILD)/test_%: harness/test_%.c harness/wav.c $(ENG)/libtape.a $(ENG)/libtape_port.a | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) $< harness/wav.c $(ENG)/libtape_port.a $(ENG)/libtape.a -o $@

# Host tool for the golden runner. Not an engine artefact; no engine gates apply.
$(BUILD)/golden_diff: harness/golden_diff.c harness/wav.c | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@

$(BUILD)/crash_%: crash/test_%.c crash/fault_block_device.c crash/crash_harness.c | $(BUILD)
	$(CC) -std=c99 -Wall -Wextra -Werror -pedantic -g -Icrash $^ -o $@

$(BUILD):
	@mkdir -p $@

run: all
	@rc=0; \
	for t in $(BINS); do ./$$t || rc=1; done; \
	for t in $(CRASH_BINS); do \
	  if ./$$t; then echo "PASS  $$(basename $$t)   (silent on success, by design)"; \
	  else echo "FAIL  $$(basename $$t)"; rc=1; fi; done; \
	exit $$rc

clean:
	@rm -rf $(BUILD)
