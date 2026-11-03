# firmware/bench/host — the firmware's portable modules, built for the host.
#
# fwhost links the unchanged engine (engine/src), the desktop file port
# (engine/port/dev_file.c), tapectl's layout recognition (host/port/mbr.c) and
# the firmware's own portable sources (../src/fw_*.c, not the Teensy glue).
# Firmware sources get the engine's warning set with -Werror.

CC    ?= cc
ROOT  := ../../..
BUILD ?= $(ROOT)/build/fwhost

WARN := -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
        -Wstrict-prototypes -Wmissing-prototypes -Wvla -Wcast-qual \
        -Wpointer-arith -Wwrite-strings
CFLAGS ?= -O2
INC := -I$(ROOT)/engine/include -I$(ROOT)/engine/port -I$(ROOT)/host/port -I../src

ENGINE := $(wildcard $(ROOT)/engine/src/*.c)
FW     := ../src/fw_part.c ../src/fw_play.c ../src/fw_sha256.c
OTHER  := $(ROOT)/engine/port/dev_file.c $(ROOT)/host/port/mbr.c

.PHONY: all clean
all: $(BUILD)/fwhost

$(BUILD)/fwhost: fwhost.c $(FW) $(ENGINE) $(OTHER) ../src/*.h
	@mkdir -p $(BUILD)
	$(CC) -std=c99 $(WARN) $(CFLAGS) $(INC) -o $@ fwhost.c $(FW) $(ENGINE) $(OTHER)

clean:
	rm -rf $(BUILD)
