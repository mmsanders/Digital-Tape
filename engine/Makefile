# Digital Tape engine — Stream 1
#
# Two archives, deliberately:
#
#   libtape.a       engine/src — the engine proper. Subject to every gate:
#                   no allocation, no libc file I/O, stack <= 8 KiB,
#                   RAM <= 200 KiB, .rodata <= 32 KiB.
#
#   libtape_port.a  engine/port — block-device shims. NOT subject to those
#                   gates, and must not be: the file-backed port is libc file
#                   I/O by definition. That is exactly what the block-device
#                   boundary is for — the engine never learns a file exists.
#
# If a gate ever runs over libtape_port.a it will fail, and the fix is the gate,
# not the port.

CC      ?= cc
AR      ?= ar
BUILD   ?= ../build/engine

# -Werror is not negotiable. A warning in the engine is a defect in the engine.
# -fstack-usage + -fcallgraph-info feed the 8 KiB stack ceiling (tools/ci).
# -fno-common keeps COMMON symbols out of the memory audit's blind spot.
WARN     := -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
            -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
            -Wpointer-arith -Wwrite-strings
BASE     := -std=c99 $(WARN) -fno-common -g -Os
ANALYSIS := -fstack-usage -fcallgraph-info=su,da

CPPFLAGS += -Iinclude
ENGINE_CFLAGS := $(BASE) $(ANALYSIS) $(CFLAGS)
PORT_CFLAGS   := $(BASE) $(CFLAGS)

ENGINE_SRC := $(wildcard src/*.c)
PORT_SRC   := $(wildcard port/*.c)
ENGINE_OBJ := $(patsubst src/%.c,$(BUILD)/src/%.o,$(ENGINE_SRC))
PORT_OBJ   := $(patsubst port/%.c,$(BUILD)/port/%.o,$(PORT_SRC))

LIB      := $(BUILD)/libtape.a
PORTLIB  := $(BUILD)/libtape_port.a

.PHONY: all clean
all: $(LIB) $(PORTLIB)

$(LIB): $(ENGINE_OBJ)
	@if [ -z "$(ENGINE_OBJ)" ]; then \
	  echo "engine: no sources in src/ — nothing to archive."; exit 1; fi
	$(AR) rcs $@ $(ENGINE_OBJ)

$(PORTLIB): $(PORT_OBJ)
	@if [ -z "$(PORT_OBJ)" ]; then \
	  echo "engine: no sources in port/ — nothing to archive."; exit 1; fi
	$(AR) rcs $@ $(PORT_OBJ)

# .su and .ci land next to the object, which is where the stack gate looks.
$(BUILD)/src/%.o: src/%.c | $(BUILD)/src
	cd $(BUILD)/src && $(CC) $(CPPFLAGS:-I%=-I$(CURDIR)/%) $(ENGINE_CFLAGS) \
	    -c $(CURDIR)/$< -o $(notdir $@)

$(BUILD)/port/%.o: port/%.c | $(BUILD)/port
	$(CC) $(CPPFLAGS) -Iport -Isrc $(PORT_CFLAGS) -c $< -o $@

$(BUILD)/src $(BUILD)/port:
	@mkdir -p $@

clean:
	@rm -rf $(BUILD)
