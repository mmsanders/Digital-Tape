# Digital Tape engine — Stream 1
#
# Portable C99. No dependency beyond libc. No allocation after init.
# See CLAUDE.md §1 and engine/README.md before adding a flag here.

CC      ?= cc
AR      ?= ar
BUILD   ?= ../build/engine

# -Werror is not negotiable. A warning in the engine is a defect in the engine.
# -fstack-usage feeds the recursion audit. -g keeps symbols for the memory audit.
CFLAGS  += -std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion \
           -Wstrict-prototypes -Wmissing-prototypes -Wvla \
           -fno-common -fstack-usage -g -Os
CPPFLAGS += -Iinclude

SRC := $(wildcard src/*.c)
OBJ := $(patsubst src/%.c,$(BUILD)/%.o,$(SRC))
LIB := $(BUILD)/libtape.a

.PHONY: all clean
all: $(LIB)

$(LIB): $(OBJ)
	@if [ -z "$(OBJ)" ]; then \
	  echo "engine: no sources in src/ — nothing to archive."; \
	  echo "engine: this is expected until WP-06. CI treats it as a failing build."; \
	  exit 1; \
	fi
	$(AR) rcs $@ $(OBJ)

$(BUILD)/%.o: src/%.c | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(BUILD):
	@mkdir -p $(BUILD)

clean:
	@rm -rf $(BUILD)
