# hardware/ — Hardware Lead
#
# One command regenerates every artefact from source. If regenerating the plate
# is not one command, packets drift from source (Hardware Charter §09 ask #03).

PY      := python3
CAD     := cad/transport
THERMAL := thermal
CHAR    := characterisation

.PHONY: all packet-wp04 packet-check packet-validate atomicity-test spec-check spec-bless thermal thermal-check charger solenoid erc drc check clean tools

all: packet-wp04 thermal

## packet-wp04 — regenerate print packet WP04-01 (plate, STLs, manifest)
packet-wp04:
	$(PY) $(CAD)/build_packet.py

## packet-validate — the plate must open in a slicer and sit on the bed
##
## A packet that will not open is exactly as broken as a schematic that fails ERC,
## and until now only one of those was checked. The 3MF that shipped had malformed
## XML from an octal-escape collision in a regex replacement, and an object at
## Y = -11 mm because the old bounds check tested only the far edges.
packet-validate:
	@$(PY) -c "import sys, json, zipfile, struct, os, xml.etree.ElementTree as ET; \
	d='packets/wp04-01'; \
	z=zipfile.ZipFile(d+'/plate.3mf'); \
	[ET.fromstring(z.read(e)) for e in ('[Content_Types].xml','_rels/.rels','3D/3dmodel.model')]; \
	ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}; \
	r=ET.fromstring(z.read('3D/3dmodel.model')); \
	vs=[(float(v.get('x')),float(v.get('y'))) for v in r.findall('.//m:vertex',ns)]; \
	bad=[c for c in vs if c[0]<-0.001 or c[1]<-0.001]; \
	sys.exit('FAIL %d vertices at negative X/Y' % len(bad)) if bad else None; \
	p=d+'/plate.stl'; n=os.path.getsize(p); \
	h=open(p,'rb').read(84); \
	t=struct.unpack('<I', h[80:84])[0]; \
	sys.exit('FAIL STL declares zero triangles') if t==0 else None; \
	sys.exit('FAIL STL length %d != %d triangles' % (n,t)) if n != 84+t*50 else None; \
	m=json.load(open(d+'/manifest.json')); \
	sys.exit('FAIL library deliverable is not plate.stl') if m.get('library_deliverable')!='plate.stl' else None; \
	sys.exit('FAIL estimated print time %.1f h exceeds the library limit' % m['estimated_print_hours']) \
	  if m['estimated_print_hours'] >= m['library_job_limit_hours'] else None; \
	print('OK  plate.stl %d triangles, plate.3mf well-formed, all geometry on the bed' % t); \
	print('OK  needs %dx%d mm, ~%.1f h print, within the library 6 h limit' % (m['minimum_bed_mm'][0], m['minimum_bed_mm'][1], m['estimated_print_hours']))"

## packet-check — fail if the committed plate is not what the source produces
##
## The plate is committed because Michael downloads it and cannot run `make`.
## That only works if it is reproducible, so this proves it is.
packet-check:
	@$(PY) $(CAD)/build_packet.py >/dev/null
	@if git diff --quiet -- packets/ 2>/dev/null; then \
	  echo "OK  committed plate matches source"; \
	else \
	  echo "FAIL committed plate differs from what the source produces:"; \
	  git diff --stat -- packets/; \
	  exit 1; \
	fi

## thermal — regenerate every generated table in spec/hw/thermal-budget.md
thermal:
	$(PY) $(THERMAL)/budget.py
	$(PY) $(THERMAL)/charger_ts.py
	$(PY) $(THERMAL)/solenoid_timing.py

## thermal-check — fail if any generated table is stale (CI gate)
thermal-check:
	$(PY) $(THERMAL)/budget.py --check
	$(PY) $(THERMAL)/charger_ts.py --check
	$(PY) $(THERMAL)/solenoid_timing.py --check

## charger / solenoid — print the design analyses without touching the spec
charger:
	$(PY) $(THERMAL)/charger_ts.py --report

solenoid:
	$(PY) $(THERMAL)/solenoid_timing.py --report

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

## atomicity-test — the media-atomicity judge, and proof it can go red
##
## This tool decides whether the format's central physical assumption holds, so a
## regression in it fails OPEN: a PASS nobody earned. IR-018-05. The --mutate run
## patches classify() to always return NEW -- the most plausible fail-open -- and
## asserts the suite catches it, per CLAUDE.md section 1.
atomicity-test:
	@cd $(CHAR) && $(PY) test_media_atomicity.py >/dev/null \
	  && echo "OK  atomicity judge: 43 checks pass, incl. end-to-end CLI"
	@cd $(CHAR) && $(PY) test_media_atomicity.py --mutate >/dev/null \
	  && echo "OK  atomicity judge: proven able to go red"

## spec-check — spec/hw content and revision must move together
##
## board-rev-a.md is what firmware/prod writes against, and its value rests on the
## document changing first with an explicit notification. A silent pin swap between
## revisions is how a week of bring-up goes to a problem that is not in the code.
## This turns that promise into a gate. PM Decisions 005 section 5.
spec-check:
	@$(PY) spec_manifest.py

## spec-bless — record an intended revision bump
spec-bless:
	@$(PY) spec_manifest.py --bless

## check — everything that can be checked today
check: thermal-check
	@$(PY) -c "import cadquery" 2>/dev/null && echo "OK  cadquery present" \
	  || { echo "FAIL cadquery missing: pip install cadquery"; exit 1; }
	@$(PY) $(CAD)/build_packet.py >/dev/null && echo "OK  WP04-01 plate rebuilds and fits the bed"
	@$(MAKE) --no-print-directory packet-check
	@$(MAKE) --no-print-directory packet-validate
	@$(PY) -c "import ast,sys; ast.parse(open('$(CHAR)/measure_sustained_write.py').read())" \
	  && echo "OK  characterisation tool parses"
	@$(MAKE) --no-print-directory atomicity-test
	@$(MAKE) --no-print-directory spec-check
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
