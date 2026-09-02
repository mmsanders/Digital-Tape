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

.PHONY: all run clean
all: $(BINS)

$(BUILD)/test_%: harness/test_%.c $(ENG)/libtape.a $(ENG)/libtape_port.a | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) $< $(ENG)/libtape_port.a $(ENG)/libtape.a -o $@

$(BUILD):
	@mkdir -p $@

run: all
	@rc=0; for t in $(BINS); do ./$$t || rc=1; done; exit $$rc

clean:
	@rm -rf $(BUILD)
