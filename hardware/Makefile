# hardware/ — Hardware Lead
#
# One command regenerates every artefact from source. If regenerating the plate
# is not one command, packets drift from source (Hardware Charter §09 ask #03).

PY      := python3
CAD     := cad/transport
THERMAL := thermal
CHAR    := characterisation

.PHONY: all packet-wp04 thermal thermal-check erc drc check clean tools

all: packet-wp04 thermal

## packet-wp04 — regenerate print packet WP04-01 (plate, STLs, manifest)
packet-wp04:
	$(PY) $(CAD)/build_packet.py

## thermal — regenerate the tables in spec/hw/thermal-budget.md
thermal:
	$(PY) $(THERMAL)/budget.py

## thermal-check — fail if the thermal budget is stale (CI gate)
thermal-check:
	$(PY) $(THERMAL)/budget.py --check

## drc — KiCad design rule check
drc:
ifeq ($(shell command -v kicad-cli 2>/dev/null),)
	@echo "SKIP drc: kicad-cli not installed, and there is no board yet."
	@echo "          See hardware/README.md for the environment gap (H-03)."
else
	@echo "SKIP drc: no board file yet. This gate goes live at WP-26/WP-27."
endif

## erc — KiCad electrical rule check
##
## Deliberately loud rather than silent. The only KiCad available to this
## environment is 7.0.11, whose kicad-cli has no `sch erc` subcommand -- that
## lands in KiCad 8. The charter requires a clean ERC report as part of the
## deliverable, so a gate that quietly passes would turn an artefact into a
## claim. It fails visibly instead, and names what would fix it.
erc:
	@if ! command -v kicad-cli >/dev/null 2>&1; then \
	  echo "SKIP erc: kicad-cli not installed (no board yet either)."; \
	  echo "          See hardware/README.md, gap H-03."; \
	elif ! kicad-cli sch erc --help >/dev/null 2>&1; then \
	  echo "BLOCKED erc: this kicad-cli has no 'sch erc' -- needs KiCad 8+."; \
	  echo "             Installed: $$(kicad-cli version 2>/dev/null || echo unknown)"; \
	  echo "             ERC cannot be automated until the toolchain is upgraded."; \
	  exit 1; \
	else \
	  echo "SKIP erc: no schematic yet. This gate goes live at WP-26."; \
	fi

## check — everything that can be checked today
check: thermal-check
	@$(PY) -c "import cadquery" 2>/dev/null && echo "OK  cadquery present" \
	  || { echo "FAIL cadquery missing: pip install cadquery"; exit 1; }
	@$(PY) $(CAD)/build_packet.py >/dev/null && echo "OK  WP04-01 plate rebuilds and fits the bed"
	@$(PY) -c "import ast,sys; ast.parse(open('$(CHAR)/measure_sustained_write.py').read())" \
	  && echo "OK  characterisation tool parses"
	@$(MAKE) --no-print-directory drc
	@$(MAKE) --no-print-directory erc

## tools — install what this directory needs
tools:
	pip install --break-system-packages cadquery
	@echo
	@echo "KiCad is NOT installed by this target on purpose."
	@echo "The distro package is 7.0.11, which cannot run ERC from the CLI."
	@echo "See hardware/README.md before installing it."

clean:
	rm -rf packets/wp04-01/stl packets/wp04-01/plate.stl packets/wp04-01/plate.3mf
