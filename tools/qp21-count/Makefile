# tools/qp21-count — Q-P2-1(b) device-call counts (#385 Part C).
#
#   make -C tools/qp21-count          build ../../build/qp21-count/count
#   make -C tools/qp21-count run      build, then count into a scratch dir
#
# Links the unchanged engine (libtape.a) and its ports (libtape_port.a).

CC      ?= cc
BUILD   ?= ../../build/qp21-count
ENGINE  := ../../build/engine
WARN    := -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion -Wvla
CFLAGS  ?= -O2 -g
CPPFLAGS := -I../../engine/include -I../../engine/port

.PHONY: all run engine clean
all: $(BUILD)/count

engine:
	$(MAKE) -C ../../engine all

$(BUILD)/count: count.c engine
	@mkdir -p $(BUILD)
	$(CC) $(CPPFLAGS) -std=c99 $(WARN) $(CFLAGS) count.c $(ENGINE)/libtape_port.a $(ENGINE)/libtape.a -o $@

run: $(BUILD)/count
	@rm -rf $(BUILD)/work && mkdir -p $(BUILD)/work
	$(BUILD)/count $(BUILD)/work
	@rm -rf $(BUILD)/work

clean:
	@rm -rf $(BUILD)
