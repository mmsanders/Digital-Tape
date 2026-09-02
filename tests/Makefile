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

.PHONY: all run clean
all: $(BINS) $(TOOLS)

$(BUILD)/test_%: harness/test_%.c harness/wav.c $(ENG)/libtape.a $(ENG)/libtape_port.a | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) $< harness/wav.c $(ENG)/libtape_port.a $(ENG)/libtape.a -o $@

# Host tool for the golden runner. Not an engine artefact; no engine gates apply.
$(BUILD)/golden_diff: harness/golden_diff.c harness/wav.c | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@

$(BUILD):
	@mkdir -p $@

run: all
	@rc=0; for t in $(BINS); do ./$$t || rc=1; done; exit $$rc

clean:
	@rm -rf $(BUILD)
