CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -pedantic
PYTHON ?= python3
BUILD_DIR ?= build
.PHONY: check clean engine
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)
$(BUILD_DIR)/rejecting_probe: mount_probe.c candidate_api.h rejecting_stub.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) mount_probe.c rejecting_stub.c -o $@
$(BUILD_DIR)/probe_selftest: probe_selftest.c mount_probe.c candidate_api.h rejecting_stub.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) probe_selftest.c rejecting_stub.c -o $@
check: $(BUILD_DIR)/rejecting_probe $(BUILD_DIR)/probe_selftest
	$(PYTHON) -m unittest -v test_package.py
# Caller supplies production public-header definition/includes and actual engine objects.
# No default link target: a missing engine cannot turn green.
engine: | $(BUILD_DIR)
	test -n '$(PUBLIC_HEADER)' && test -n '$(ENGINE_OBJECTS)'
	$(CC) $(CFLAGS) $(CPPFLAGS) -DTAPE_PUBLIC_HEADER='"$(PUBLIC_HEADER)"' mount_probe.c $(ENGINE_OBJECTS) $(LDLIBS) -o $(BUILD_DIR)/engine_probe
clean:
	rm -f $(BUILD_DIR)/rejecting_probe $(BUILD_DIR)/engine_probe $(BUILD_DIR)/probe_selftest
